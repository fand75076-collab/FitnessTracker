from __future__ import annotations

import os
import queue
import socket
import sys
import threading
import time
from pathlib import Path

os.environ.setdefault("STREAMLIT_SERVER_ENABLE_CORS", "true")
os.environ.setdefault("STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION", "false")

from streamlit import config as st_config
from streamlit.web import bootstrap
from streamlit.web.server.server import Server


APP_TITLE = "健身趋势追踪"
WINDOW_WIDTH = 1480
WINDOW_HEIGHT = 980

# Shared state for graceful shutdown
_server_instance: Server | None = None
_server_thread: threading.Thread | None = None


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_for_server(url: str, errors: "queue.Queue[BaseException]") -> None:
    port = int(url.rsplit(":", 1)[1])
    deadline = time.time() + 30
    while time.time() < deadline:
        if not errors.empty():
            raise errors.get()
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return
        except OSError:
            time.sleep(0.5)
    raise TimeoutError(f"Streamlit server did not start within 30 seconds: {url}")


def run_streamlit_server(app_path: Path, errors: "queue.Queue[BaseException]") -> None:
    global _server_instance
    try:
        bootstrap._fix_sys_path(str(app_path))
        bootstrap._fix_tornado_crash()
        bootstrap._fix_sys_argv(str(app_path), [])
        bootstrap._fix_pydeck_mapbox_api_warning()
        bootstrap._install_config_watchers({})

        _server_instance = Server(str(app_path), False)

        async def main() -> None:
            await _server_instance.start()
            bootstrap._on_server_start(_server_instance)
            await _server_instance.stopped

        import asyncio

        asyncio.run(main())
    except BaseException as exc:
        errors.put(exc)


def _stop_server() -> None:
    """Signal the Streamlit server to shut down."""
    global _server_instance
    if _server_instance is not None:
        try:
            _server_instance.stop()
        except Exception:
            pass


def open_native_window(url: str) -> None:
    import webview

    window = webview.create_window(
        APP_TITLE,
        url,
        width=WINDOW_WIDTH,
        height=WINDOW_HEIGHT,
        min_size=(1180, 780),
        text_select=True,
    )

    # pywebview 5.x+: hook window close so we can stop the backend first
    if hasattr(window, "events") and hasattr(window.events, "closing"):
        window.events.closing += _stop_server

    # If Edge Chromium is unavailable, pywebview will raise an error.
    # We catch it and fall back to the system default renderer.
    try:
        webview.start(gui="edgechromium", debug=False)
    except Exception as exc:
        fallback_msg = (
            f"Edge Chromium 渲染器不可用 ({exc})，"
            "尝试使用系统默认渲染器..."
        )
        print(fallback_msg, file=sys.stderr)
        try:
            webview.start(debug=False)
        except Exception as exc2:
            raise RuntimeError(
                f"无法启动原生窗口。请确认已安装 WebView2 Runtime。\n"
                f"原始错误：{exc}\n"
                f"回退错误：{exc2}"
            ) from exc2


def _sigint_handler(signum: int, frame: object | None) -> None:
    """Handle Ctrl+C gracefully."""
    _stop_server()
    sys.exit(0)


def main() -> None:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        app_path = Path(sys._MEIPASS) / "app.py"
    else:
        app_path = Path(__file__).resolve().with_name("app.py")

    port = int(os.environ.get("FITNESS_TRACKER_PORT", "0")) or find_free_port()
    url = f"http://127.0.0.1:{port}"

    st_config.set_option("server.port", port)
    st_config.set_option("server.address", "127.0.0.1")
    st_config.set_option("server.headless", True)
    st_config.set_option("browser.gatherUsageStats", False)
    st_config.set_option("global.developmentMode", False)
    st_config.set_option("server.fileWatcherType", "none")
    st_config.set_option("server.runOnSave", False)
    st_config.set_option("server.enableCORS", True)
    st_config.set_option("server.enableXsrfProtection", False)

    errors: "queue.Queue[BaseException]" = queue.Queue()

    global _server_thread
    _server_thread = threading.Thread(
        target=run_streamlit_server,
        args=(app_path, errors),
        daemon=False,  # non-daemon so we can join it cleanly
    )
    _server_thread.start()

    # Graceful shutdown on Ctrl+C
    signal_handler = getattr(__import__("signal"), "signal", None)
    if signal_handler:
        signal_handler(__import__("signal").SIGINT, _sigint_handler)

    try:
        wait_for_server(url, errors)
        open_native_window(url)
    except KeyboardInterrupt:
        pass
    finally:
        # Window closed (or Ctrl+C) → stop server → wait for thread to finish
        _stop_server()
        if _server_thread is not None and _server_thread.is_alive():
            _server_thread.join(timeout=5.0)
        # If thread is still alive after 5s, the process will exit anyway
        # because the main thread is done.


if __name__ == "__main__":
    main()