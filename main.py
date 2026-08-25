"""Auto虚拟形象 — desktop host (Python + webview).

Wraps the browser app (index.html + lib/*.js) in a native desktop window and
adds one native bridge that a plain browser cannot provide:

  * OpenSeeFace input  — UDP listener (osf.py), polled by the JS UI.

Camera tracking (webcam / MediaPipe FaceMesh) is implemented entirely in JS
and needs no native bridge, so it works both in the browser and in this host.

OpenSeeFace tracking needs a data source on the same machine, e.g. the bundled
`opennseeface/Binary/facetracker.exe` (or VSeeFace sending VMC on the port
below). Run it alongside this app; the OSF toggle in the UI then drives the
avatar from that stream.

Run ``run.bat``. It creates and uses the project-local ``.venv`` automatically.
"""

import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))  # resolve files relative to main.py

import webview

from osf import OpenSeeFaceReceiver

# ---- configuration (override with environment variables) ----
OSF_HOST = os.environ.get("AUTO_OSF_HOST", "127.0.0.1")
OSF_PORT = int(os.environ.get("AUTO_OSF_PORT", "11573"))  # OpenSeeFace / VSeeFace UDP

osf = OpenSeeFaceReceiver(OSF_HOST, OSF_PORT)


class Api:
    """Native bridge exposed to the JS side as ``window.pywebview.api``."""

    def getOsf(self):
        return osf.snapshot()


def main():
    osf.start()
    window = webview.create_window(
        "Auto虚拟形象",
        "index.html",
        width=1280,
        height=840,
        min_size=(960, 640),
        background_color="#0d0d0f",
        js_api=Api(),
    )
    try:
        webview.start(http_server=True)
    finally:
        osf.stop()


if __name__ == "__main__":
    main()
