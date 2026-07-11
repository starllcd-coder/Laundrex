from __future__ import annotations

import os
import base64
import argparse
import socket
import sys
import time
from typing import Optional

from PySide6.QtCore import QStandardPaths, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QIcon
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtPrintSupport import QPrintDialog, QPrinter

from PySide6.QtCore import QProcess, QProcessEnvironment

if __package__ is None:
    project_root = os.path.dirname(os.path.dirname(__file__))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

from desktop_app.config import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    DESKTOP_SETTINGS_MODULE,
    SYNC_ENABLED,
    SYNC_INTERVAL_SECONDS,
    desktop_db_path,
    find_project_root,
)
from desktop_app.server import DjangoServer

try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
except Exception as exc:  # pragma: no cover - import failure should show a dialog
    QWebEngineView = None
    _WEBENGINE_IMPORT_ERROR = exc
else:
    _WEBENGINE_IMPORT_ERROR = None


def _is_port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.3):
            return True
    except OSError:
        return False


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Laundrex Desktop Launcher")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Host for Django server")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port for Django server")
    parser.add_argument("--no-server", action="store_true", help="Do not start Django server")
    return parser


def _run_manage_passthrough(argv: list[str], project_root: str) -> Optional[int]:
    """
    When packaged with PyInstaller, subprocess calls use sys.executable (the app EXE).
    The backend bootstrap calls look like: <exe> manage.py migrate --noinput
    This handler lets the EXE execute Django management commands instead of treating
    them as launcher CLI args.
    """
    if not argv or argv[0] != "manage.py":
        return None
    try:
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", DESKTOP_SETTINGS_MODULE)
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        import django
        from django.core.management import execute_from_command_line

        django.setup()
        execute_from_command_line(argv)
        return 0
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
        return code
    except Exception as exc:  # pragma: no cover
        print(str(exc), file=sys.stderr)
        return 1

def _find_open_port(host: str, start_port: int, end_port: int = 8999) -> int:
    for port in range(start_port, end_port + 1):
        if not _is_port_open(host, port):
            return port
    return start_port


def main(argv: Optional[list[str]] = None) -> int:
    raw_argv = list(argv) if argv is not None else sys.argv[1:]
    try:
        project_root = str(find_project_root())
    except FileNotFoundError:
        project_root = os.path.dirname(os.path.dirname(__file__))

    passthrough_code = _run_manage_passthrough(raw_argv, project_root)
    if passthrough_code is not None:
        return passthrough_code

    args = _build_arg_parser().parse_args(raw_argv)

    app = QApplication(sys.argv)
    app.setApplicationName("Laundrex Desktop")

    if QWebEngineView is None:
        QMessageBox.critical(
            None,
            "Missing QtWebEngine",
            "QtWebEngine is required for the embedded browser.\n"
            "Install PySide6 with its WebEngine components.",
        )
        return 1

    try:
        project_root = find_project_root()
    except FileNotFoundError as exc:
        QMessageBox.critical(None, "Project not found", str(exc))
        return 1

    ok, prep_message = DjangoServer.prepare_desktop_backend(sys.executable, str(project_root))
    if not ok:
        QMessageBox.critical(
            None,
            "Desktop backend setup failed",
            prep_message or "Could not initialize local desktop backend.",
        )
        return 1

    server = DjangoServer()
    if not args.no_server:
        if _is_port_open(args.host, args.port):
            args.port = _find_open_port(args.host, args.port + 1)
        server.start(sys.executable, str(project_root), args.host, args.port)

    icon_path = project_root / "static" / "assets" / "favicon.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    window = QMainWindow()
    window.setWindowTitle("Laundrex")
    if icon_path.exists():
        window.setWindowIcon(QIcon(str(icon_path)))
    window.resize(1280, 800)

    view = QWebEngineView(window)
    window.setCentralWidget(view)
    view.settings().setAttribute(QWebEngineSettings.JavascriptCanOpenWindows, True)
    # Keep session/cookies by default so desktop "Remember me" works as expected.
    # Set LAUNDREX_DESKTOP_CLEAR_SESSION=1 only when you explicitly want a clean session.
    profile = view.page().profile()
    try:
        if os.getenv("LAUNDREX_DESKTOP_CLEAR_SESSION", "0") == "1":
            profile.clearHttpCache()
            cookie_store = profile.cookieStore()
            cookie_store.deleteAllCookies()
    except Exception:
        # If cache/cookie reset is not available on a platform build,
        # continue with default behavior instead of blocking startup.
        pass

    status_bar = window.statusBar()
    local_ready = False
    sync_status = "idle"
    sync_last = ""
    ui_loaded = False
    loading_in_progress = False
    target_page_requested = False
    download_in_progress = False
    last_good_url = ""

    def render_status() -> None:
        local_text = "Local: OK" if local_ready else "Local: starting"
        sync_text = f"Sync: {sync_status}"
        if sync_last:
            sync_text = f"{sync_text} ({sync_last})"
        status_bar.showMessage(f"{local_text} | {sync_text}")

    def handle_new_window(request) -> None:
        nonlocal loading_in_progress, target_page_requested
        requested = request.requestedUrl()
        is_local = requested.host() in ("127.0.0.1", "localhost") and requested.port() in (-1, args.port)
        if is_local:
            loading_in_progress = True
            target_page_requested = True
            view.load(requested)
        else:
            QDesktopServices.openUrl(requested)
        if hasattr(request, "reject"):
            request.reject()

    view.page().newWindowRequested.connect(handle_new_window)

    def handle_download(download) -> None:
        nonlocal download_in_progress
        download_in_progress = True
        downloads_dir = QStandardPaths.writableLocation(QStandardPaths.DownloadLocation)
        if not downloads_dir:
            downloads_dir = str(project_root / "desktop_app" / "downloads")
        os.makedirs(downloads_dir, exist_ok=True)

        file_name = ""
        try:
            file_name = download.downloadFileName() or ""
        except Exception:
            file_name = ""
        if not file_name:
            try:
                file_name = os.path.basename(download.url().path()) or "download"
            except Exception:
                file_name = "download"

        try:
            download.setDownloadDirectory(downloads_dir)
            download.setDownloadFileName(file_name)
        except Exception:
            try:
                download.setPath(os.path.join(downloads_dir, file_name))
            except Exception:
                pass

        download.accept()
        status_bar.showMessage(f"Downloading {file_name} to {downloads_dir}", 5000)

    try:
        profile.downloadRequested.connect(handle_download)
    except Exception:
        pass

    def handle_print_requested() -> None:
        printer = QPrinter(QPrinter.HighResolution)
        dialog = QPrintDialog(printer, window)
        if dialog.exec() != QPrintDialog.Accepted:
            return

        def _print_done(success: bool) -> None:
            status_bar.showMessage("Print complete" if success else "Print failed", 4000)

        view.page().print(printer, _print_done)

    try:
        view.page().printRequested.connect(handle_print_requested)
    except Exception:
        pass

    url = QUrl(f"http://{args.host}:{args.port}/?_desktop={int(time.time())}")

    def _embed_logo_data_uri() -> str:
        logo_path = project_root / "static" / "assets" / "laundrex-icon-512x512.png"
        if not logo_path.exists():
            return ""
        try:
            data = logo_path.read_bytes()
            b64 = base64.b64encode(data).decode("ascii")
            return f"data:image/png;base64,{b64}"
        except Exception:
            return ""

    def show_error_page(message: str) -> None:
        logo_uri = _embed_logo_data_uri()
        html = f"""
        <html>
        <head>
          <meta charset="utf-8" />
          <style>
            :root {{
              --blue-700: #1E6CCB;
              --blue-800: #144F9C;
              --ink: #0f172a;
              --muted: #64748b;
              --line: #e5e7eb;
            }}
            html, body {{ height: 100%; }}
            body {{
              margin: 0;
              font-family: "Segoe UI", Arial, sans-serif;
              background: radial-gradient(1200px 600px at 20% 10%, #f1f6ff 0%, #f8fbff 45%, #f5f7fb 100%);
              color: var(--ink);
              display: flex;
              align-items: center;
              justify-content: center;
            }}
            .splash {{
              text-align: center;
              padding: 32px 28px;
              background: #fff;
              border: 1px solid var(--line);
              border-radius: 20px;
              box-shadow: 0 18px 50px rgba(15, 23, 42, 0.12);
              min-width: 420px;
            }}
            .logo {{
              width: 96px;
              height: 96px;
              margin: 0 auto 14px;
              border-radius: 24px;
              background: linear-gradient(145deg, var(--blue-700), var(--blue-800));
              display: grid;
              place-items: center;
              color: #fff;
              font-weight: 800;
              font-size: 28px;
              overflow: hidden;
            }}
            .logo img {{
              width: 100%;
              height: 100%;
              object-fit: contain;
              background: #fff;
              border-radius: 24px;
            }}
            h1 {{ margin: 6px 0 4px; font-size: 22px; }}
            p {{ margin: 6px 0; color: var(--muted); }}
            .spinner {{
              width: 36px;
              height: 36px;
              border-radius: 50%;
              border: 4px solid #e2e8f0;
              border-top-color: var(--blue-700);
              margin: 16px auto 8px;
              animation: spin 0.9s linear infinite;
            }}
            .hint {{ font-size: 12px; color: #94a3b8; margin-top: 8px; }}
            .btn {{
              display: inline-block;
              margin-top: 14px;
              padding: 10px 16px;
              background: var(--blue-700);
              color: #fff;
              text-decoration: none;
              border-radius: 10px;
              font-weight: 700;
            }}
            @keyframes spin {{
              to {{ transform: rotate(360deg); }}
            }}
          </style>
        </head>
        <body>
          <div class="splash">
            <div class="logo">
              {"<img src='" + logo_uri + "' alt='Laundrex' />" if logo_uri else "L"}
            </div>
            <h1>Starting Laundrex</h1>
            <p>{message}</p>
            <div class="spinner"></div>
            <div class="hint">Local server is warming upâ€¦</div>
            <a class="btn" href="{url.toString()}">Retry</a>
          </div>
        </body>
        </html>
        """
        view.setHtml(html, url)

    def handle_load_finished(ok: bool) -> None:
        nonlocal ui_loaded, loading_in_progress, target_page_requested, download_in_progress, last_good_url
        loading_in_progress = False

        current_url = ""
        try:
            current_url = view.url().toString()
        except Exception:
            current_url = ""

        is_target = current_url.startswith(f"http://{args.host}:{args.port}/")

        # Download endpoints may return non-HTML and report load failure even when successful.
        if download_in_progress:
            download_in_progress = False
            if ui_loaded:
                status_bar.showMessage("Download started", 2000)
                return

        # Ignore initial framework/internal loads (about:blank, data:, etc.)
        # so first launch never gets stuck on a white page.
        if not target_page_requested and not is_target:
            return

        if ok and is_target:
            ui_loaded = True
            last_good_url = current_url
            timer.stop()
            status_bar.showMessage("Local: OK | Sync: " + sync_status, 3000)
            return

        target_page_requested = False

        # After app is already loaded, do not show startup splash for export/download
        # navigation failures. Stay on the app and show a short status hint instead.
        if ui_loaded:
            status_bar.showMessage("Export started (check Downloads folder).", 3000)
            if last_good_url:
                view.load(QUrl(last_good_url))
            return

        show_error_page("Could not load the local web app. Please wait a few seconds and retry.")
        if not timer.isActive():
            timer.start()

    def try_load() -> None:
        nonlocal local_ready, loading_in_progress, target_page_requested
        if ui_loaded or loading_in_progress:
            return
        if _is_port_open(args.host, args.port):
            local_ready = True
            render_status()
            loading_in_progress = True
            target_page_requested = True
            view.load(url)
        else:
            show_error_page("Starting local server…")

    timer = QTimer(window)
    timer.setInterval(400)
    timer.timeout.connect(try_load)
    timer.start()
    view.loadFinished.connect(handle_load_finished)
    # Always show a startup splash immediately so first launch never appears blank.
    show_error_page("Starting local server…")

    sync_process = QProcess(window)
    sync_process.setProcessChannelMode(QProcess.MergedChannels)

    def handle_sync_finished(exit_code, _exit_status) -> None:
        nonlocal sync_status, sync_last
        if exit_code == 0:
            sync_status = "ok"
        elif exit_code == 3:
            sync_status = "disabled"
        else:
            sync_status = "error"
        sync_last = time.strftime("%H:%M:%S")
        render_status()

    def run_sync() -> None:
        if sync_process.state() != QProcess.NotRunning:
            return
        nonlocal sync_status
        sync_status = "running"
        render_status()
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONUNBUFFERED", "1")
        env.insert("DJANGO_SETTINGS_MODULE", DESKTOP_SETTINGS_MODULE)
        env.insert("DESKTOP_DB_PATH", str(desktop_db_path(project_root)))
        sync_process.setProcessEnvironment(env)
        sync_process.setWorkingDirectory(str(project_root))
        sync_process.start(sys.executable, ["manage.py", "sync_with_cloud"])

    sync_process.finished.connect(handle_sync_finished)

    sync_timer = QTimer(window)
    if SYNC_ENABLED:
        sync_timer.setInterval(max(30, SYNC_INTERVAL_SECONDS) * 1000)
        sync_timer.timeout.connect(run_sync)
        sync_timer.start()
        run_sync()
    else:
        sync_status = "disabled"

    render_status()

    app.aboutToQuit.connect(server.stop)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())







