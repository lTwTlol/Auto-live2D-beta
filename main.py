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

Run:
    pip install -r requirements.txt
    python main.py
"""

import base64
import json
import os
import sys

# OBS / 屏幕捕获友好化：WebView2 默认在窗口被其它窗口完全遮挡时，会为了省电
# 停止合成画面，导致 OBS 捕获到黑屏/定格。关闭该“原生窗口遮挡检测”，窗口即便
# 被挡在后面也会继续渲染，方便后台捕获。（真正最小化时系统仍不渲染，见 README。）
os.environ.setdefault(
    "WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS",
    "--disable-features=CalculateNativeWinOcclusion",
)

os.chdir(os.path.dirname(os.path.abspath(__file__)))  # resolve files relative to main.py

import webview

# 优先使用随 EXE 分发的固定版本 WebView2 Runtime，避免目标机器上的旧 Runtime 缺少
# ICoreWebView2Environment10 接口而启动失败（E_NOINTERFACE）。找不到时回退到系统 Runtime。
def _resolve_webview2_runtime():
    dirs = []
    if getattr(sys, "frozen", False):
        dirs.append(os.path.dirname(sys.executable))
        if getattr(sys, "_MEIPASS", None):  # PyInstaller 解包目录（onedir 为 _internal，onefile 为临时目录）
            dirs.append(sys._MEIPASS)
    else:
        dirs.append(os.path.dirname(os.path.abspath(__file__)))
    for base in dirs:
        candidate = os.path.join(base, "WebView2Runtime")
        if os.path.isfile(os.path.join(candidate, "msedgewebview2.exe")):
            return candidate
    return None

_webview2_runtime = _resolve_webview2_runtime()
if _webview2_runtime:
    webview.settings["WEBVIEW2_RUNTIME_PATH"] = _webview2_runtime

from osf import OpenSeeFaceReceiver

# ---- configuration (override with environment variables) ----
OSF_HOST = os.environ.get("AUTO_OSF_HOST", "127.0.0.1")
OSF_PORT = int(os.environ.get("AUTO_OSF_PORT", "11573"))  # OpenSeeFace / VSeeFace UDP

osf = OpenSeeFaceReceiver(OSF_HOST, OSF_PORT)


# ---- persistent settings (survive app restarts; stored in user data) ----
def _data_dir():
    if getattr(sys, "frozen", False):
        # 打包成 EXE 后：记忆文件放到 EXE 同目录
        return os.path.dirname(sys.executable)
    # 开发运行时：放到 main.py 同目录
    return os.path.dirname(os.path.abspath(__file__))


def _settings_file():
    return os.path.join(_data_dir(), "settings.json")


def _last_psd_file():
    return os.path.join(_data_dir(), "last.psd")


class Api:
    """Native bridge exposed to the JS side as ``window.pywebview.api``."""

    def getOsf(self):
        return osf.snapshot()

    def get_settings(self):
        try:
            with open(_settings_file(), "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    def save_settings(self, data):
        try:
            with open(_settings_file(), "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            return True
        except (OSError, TypeError, ValueError):
            return False

    def save_last_psd(self, b64):
        try:
            with open(_last_psd_file(), "wb") as f:
                f.write(base64.b64decode(b64))
            return True
        except (OSError, ValueError):
            return False

    def load_last_psd(self):
        try:
            with open(_last_psd_file(), "rb") as f:
                data = f.read()
        except OSError:
            return None
        return base64.b64encode(data).decode("ascii") if data else None


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
