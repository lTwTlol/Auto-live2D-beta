"""OpenSeeFace UDP receiver.

Two face-tracking sources are supported, both streamed over UDP to the same
port (default 11573):

  1. VSeeFace / VMC protocol  — one JSON object per datagram (ARKit blendshape
     names plus a ``r`` head-rotation vector in radians).
  2. OpenSeeFace (facetracker) — a raw binary struct per datagram (floats),
     which is what the bundled ``opennseeface/Binary/facetracker.exe`` emits.

This module listens on the port, parses each packet into a compact snapshot,
and exposes the latest snapshot thread-safely to the webview host.

The app's animation layer consumes a fixed set of normalized fields
(``ax``, ``ay``, ``az``, ``eL``, ``eR``, ``mo``, ``ex``, ``ey``, ``mouthForm``)
— the same fields MediaPipe FaceMesh produces — so OpenSeeFace can reuse the
exact same animation code path.
"""

import json
import math
import socket
import struct
import threading
import time

# Head-rotation mapping. OpenSeeFace reports rotation in degrees as
# ``euler = [rx, ry, rz]`` (X = pitch, Y = yaw, Z = roll); VSeeFace reports it
# in radians as ``r = [rx, ry, rz]``. The exact axis convention / sign differs
# slightly between builds, so the scale and sign live here as easy-to-tune
# constants:
#   * turn the head left/right  -> whichever of ax/az moves is YAW
#   * nod the head up/down      -> whichever of ay moves is PITCH
#   * tilt the head to a side   -> whichever of ax/az remains is ROLL
# Flip a sign by negating the SCALE, or scale the response by its magnitude.
SCALE_YAW   = 1.6    # applied to yaw   -> app "angleX" (horizontal)
SCALE_PITCH = 1.6    # applied to pitch -> app "angleY" (vertical)
SCALE_ROLL  = 1.6    # applied to roll  -> app "angleZ" (tilt)

DEG2RAD = math.pi / 180.0

# OpenSeeFace feature scaling. The raw features are ratios of face distances
# (e.g. mouth_open = upper-lip/lower-lip gap / nose height) and are not
# normalised to 0..1, so they are scaled here before being clamped.
MOUTH_OPEN_SCALE = 2.0   # mouth_open  -> app "mouthOpen" (0..1)
MOUTH_FORM_SCALE = 3.0   # mouth corner up/down (smile) -> app "mouthForm" (-1..1)

# Gaze scaling. The raw gaze direction is the pupil-to-eyeball-centre offset
# divided by the eyeball depth, i.e. the tangent of the gaze angle (roughly
# +/-0.4 at the extremes). Scaling up maps it onto the app's -1..1 eye range.
GAZE_SCALE = 2.5


def _f(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _clamp(v, a=-1.0, b=1.0):
    return a if v < a else (b if v > b else v)


def _wrap180(d):
    """Wrap an angle in degrees to [-180, 180)."""
    d = d % 360.0
    return d - 360.0 if d > 180.0 else d


def _blend(arr, indices):
    """Average the blendshape values at the given ARKit indices (0..1)."""
    if not isinstance(arr, (list, tuple)):
        return 0.0
    acc, n = 0.0, 0
    for i in indices:
        if 0 <= i < len(arr):
            acc += _f(arr[i])
            n += 1
    return acc / n if n else 0.0


def parse_packet(obj):
    """Parse one VSeeFace / VMC JSON object into a normalized snapshot dict.

    Accepts both the "osfv2" shape (everything nested under ``i``) and flat
    packets. Missing fields are simply omitted, so a malformed / partial
    packet never blocks the rest. Returns None if nothing usable was found.
    """
    if not isinstance(obj, dict):
        return None

    inner = obj.get("i") if isinstance(obj.get("i"), dict) else obj
    out = {"live": True}

    # --- head rotation ---
    r = inner.get("r")
    if isinstance(r, (list, tuple)) and len(r) >= 3:
        rx, ry, rz = _f(r[0]), _f(r[1]), _f(r[2])
        out["ax"] = _clamp(-ry * SCALE_YAW)
        out["ay"] = _clamp(rx * SCALE_PITCH)
        out["az"] = _clamp(-rz * SCALE_ROLL)

    # --- blendshapes (ARKit 52) ---
    b = inner.get("b")

    # eye openness: prefer the dedicated ``e`` field, else 1 - eyeBlink blendshape
    e = inner.get("e")
    eye_l = eye_r = None
    if isinstance(e, dict):
        el, er = e.get("l"), e.get("r")
        if isinstance(el, (list, tuple)) and len(el) >= 1:
            eye_l = _f(el[0])
        if isinstance(er, (list, tuple)) and len(er) >= 1:
            eye_r = _f(er[0])
    elif isinstance(e, (list, tuple)) and len(e) >= 2:
        el, er = e[0], e[1]
        if isinstance(el, (list, tuple)) and len(el) >= 1:
            eye_l = _f(el[0])
        if isinstance(er, (list, tuple)) and len(er) >= 1:
            eye_r = _f(er[0])
    if eye_l is None:
        eye_l = 1.0 - _blend(b, [8])   # ARKit eyeBlinkLeft
    if eye_r is None:
        eye_r = 1.0 - _blend(b, [9])   # ARKit eyeBlinkRight
    out["eL"] = _clamp(eye_l, 0.0, 1.0)
    out["eR"] = _clamp(eye_r, 0.0, 1.0)

    # mouth open: jawOpen; mouth form (smile) folded into a gentle offset
    mo = _blend(b, [24])               # ARKit jawOpen
    smile = _blend(b, [43, 44])        # ARKit mouthSmileLeft/Right
    out["mo"] = _clamp(mo, 0.0, 1.0)
    out["mouthForm"] = _clamp(smile - _blend(b, [31]), -1.0, 1.0)  # funnel subtracts

    # gaze: eyeLook* blendshapes (10..17)
    look_out = _blend(b, [14, 15])     # eyeLookOutLeft/Right
    look_in = _blend(b, [12, 13])      # eyeLookInLeft/Right
    look_up = _blend(b, [16, 17])      # eyeLookUpLeft/Right
    look_dn = _blend(b, [10, 11])      # eyeLookDownLeft/Right
    out["ex"] = _clamp((look_out - look_in))
    out["ey"] = _clamp((look_up - look_dn))

    return out


# ---- OpenSeeFace binary format -------------------------------------------------
#
# facetracker.py packs one struct per detected face:
#   <d i f f f f B f 4f 3f 3f>  header  (timestamp, id, w, h, blink_r, blink_l,
#                                          success, pnp_error, quaternion*4,
#                                          euler*3, translation*3)
#   then   N * f                  landmark confidence (N landmarks)
#   then 2N * f                  landmark x/y (packed y then x)
#   then  70*3 * f                normalized 3D points (x, -y, -z)
#   then  14 * f                  features (see facetracker.py `features` list)
#
# The header (eye blink + head rotation) and the trailing 14 feature floats are
# all we need, so we read those without depending on the landmark count.

_FEATURE_COUNT = 14
# feature index -> meaning (facetracker.py `features` order)
#   8  mouth_corner_updown_l    10 mouth_corner_updown_r    12 mouth_open
_FEAT_MOUTH_OPEN = 12
_FEAT_CORNER_L = 8
_FEAT_CORNER_R = 10

_HEADER_FMT = "<di4fBf4f3f3f"
_HEADER_SIZE = struct.calcsize(_HEADER_FMT)

# The 70 3D points are packed immediately before the trailing features, so their
# base offset can be computed from the END of the datagram (independent of the
# landmark count). Points 66/67 are the pupils, 68/69 the eyeball centres.
_3D_POINT_COUNT = 70
_3D_OFFSET_FROM_END = (_3D_POINT_COUNT * 3 + _FEATURE_COUNT) * 4
_PUPIL_R, _PUPIL_L = 66, 67
_EYEBALL_R, _EYEBALL_L = 68, 69


def _gaze_3d(raw):
    """Extract a conjugate gaze direction from the packed 3D points.

    Each point is packed as ``(x, -y, -z)`` in model space (+x = subject's
    right, +y = up, +z = toward the camera). Gaze is pupil minus eyeball centre,
    normalised by depth (the eyeball is offset back along +z from the pupil).
    Returns ``(ex_raw, ey_raw)`` where a positive value means the subject looks
    right / up, matching the sign convention of the MediaPipe camera path.
    Returns ``(0.0, 0.0)`` if the points are missing or degenerate (e.g. a
    failed fit leaves them all zero).
    """
    if len(raw) < _3D_OFFSET_FROM_END + _HEADER_SIZE:
        return 0.0, 0.0
    base = len(raw) - _3D_OFFSET_FROM_END

    def _pt(i):
        x, y, z = struct.unpack_from("<3f", raw, base + i * 12)
        return x, y, z

    def _eye(pupil, eyeball):
        px, py, pz = _pt(pupil)
        ex, ey, ez = _pt(eyeball)
        depth = ez - pz  # eyeball centre is behind the pupil -> positive
        if depth <= 1e-6:
            return 0.0, 0.0
        # horizontal = pupil.x - eyeball.x (+x = look right)
        # vertical   = pupil.y - eyeball.y in model space = eyeball.py - pupil.py
        #              in packed coords (+y = look up)
        return (px - ex) / depth, (ey - py) / depth

    hr, vr = _eye(_PUPIL_R, _EYEBALL_R)
    hl, vl = _eye(_PUPIL_L, _EYEBALL_L)
    return 0.5 * (hr + hl), 0.5 * (vr + vl)


def parse_packet_binary(raw):
    """Parse one OpenSeeFace binary datagram into a normalized snapshot dict.

    Returns None if the datagram is too short or malformed.
    """
    if len(raw) < _HEADER_SIZE + _FEATURE_COUNT * 4:
        return None
    try:
        h = struct.unpack_from(_HEADER_FMT, raw, 0)
        feats = struct.unpack_from(
            "<%df" % _FEATURE_COUNT, raw, len(raw) - _FEATURE_COUNT * 4
        )
    except struct.error:
        return None

    # header layout:
    #   0 time  1 face_id  2 width  3 height
    #   4 blink_r  5 blink_l  6 success  7 pnp_error
    #   8..11 quaternion  12..14 euler  15..17 translation
    blink_r = _f(h[4], 1.0)
    blink_l = _f(h[5], 1.0)
    qx, qy, qz = _f(h[12]), _f(h[13]), _f(h[14])

    # The raw euler comes from OpenCV's RQDecomp3x3 in OpenCV's *camera* frame,
    # so a neutral (straight-on) face reports ~[180, 0, 90] instead of [0, 0, 0].
    # Normalise to face-relative degrees exactly like OpenSeeFace's Unity
    # ``OpenSee`` component (pitch = -(Qx+180), yaw = Qy, roll = Qz-90), then
    # map to the app's ax/ay/az (yaw/pitch/roll) with the same sign convention
    # as the JSON (VMC) path above.
    pitch = _wrap180(-(qx + 180.0))
    yaw = _wrap180(qy)
    roll = _wrap180(qz - 90.0)

    mouth_open = _f(feats[_FEAT_MOUTH_OPEN])
    smile = 0.5 * (_f(feats[_FEAT_CORNER_L]) + _f(feats[_FEAT_CORNER_R]))

    out = {"live": True}
    out["eL"] = _clamp(blink_l, 0.0, 1.0)
    out["eR"] = _clamp(blink_r, 0.0, 1.0)
    out["ax"] = _clamp(-yaw * DEG2RAD * SCALE_YAW)
    out["ay"] = _clamp(pitch * DEG2RAD * SCALE_PITCH)
    out["az"] = _clamp(-roll * DEG2RAD * SCALE_ROLL)
    out["mo"] = _clamp(mouth_open * MOUTH_OPEN_SCALE, 0.0, 1.0)
    out["mouthForm"] = _clamp(smile * MOUTH_FORM_SCALE, -1.0, 1.0)

    # Gaze: the iris/pupil points are only valid on a successful fit (otherwise
    # they are all zeros), so guard on the header `success` flag before reading.
    if h[6] != 0:
        ex_raw, ey_raw = _gaze_3d(raw)
        out["ex"] = _clamp(ex_raw * GAZE_SCALE)
        out["ey"] = _clamp(ey_raw * GAZE_SCALE)
    else:
        out["ex"] = 0.0
        out["ey"] = 0.0
    return out


class OpenSeeFaceReceiver:
    """Background thread that keeps the latest parsed snapshot."""

    def __init__(self, host="127.0.0.1", port=11573):
        self.host = host
        self.port = port
        self._sock = None
        self._thread = None
        self._running = False
        self._lock = threading.Lock()
        self._latest = None
        self._last_seen = 0.0
        self.error = None
        self.last_raw = None  # last raw text (debug aid)

    def start(self):
        if self._running:
            return
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._sock.bind((self.host, self.port))
            self._sock.settimeout(0.5)
        except OSError as exc:
            self.error = f"OpenSeeFace UDP bind failed on {self.host}:{self.port} ({exc})"
            self._sock = None
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None

    def _parse(self, raw):
        # JSON datagrams (VSeeFace / VMC) start with '{'. Anything else is
        # assumed to be the OpenSeeFace binary format.
        if raw[:1] == b"{":
            try:
                return parse_packet(json.loads(raw.decode("utf-8", "replace")))
            except (ValueError, TypeError):
                return None
        return parse_packet_binary(raw)

    def _loop(self):
        buf = bytearray(65536)
        while self._running:
            try:
                n, _addr = self._sock.recvfrom_into(buf)
            except socket.timeout:
                continue
            except OSError:
                break
            raw = bytes(buf[:n])
            snap = self._parse(raw)
            if snap:
                with self._lock:
                    self._latest = snap
                    self._last_seen = time.monotonic()
            self.last_raw = raw

    def snapshot(self, max_age=1.0):
        """Return the latest snapshot, or ``{"live": False}`` if stale."""
        with self._lock:
            snap = self._latest
            age = time.monotonic() - self._last_seen
        if snap is None or age > max_age:
            return {"live": False}
        return snap
