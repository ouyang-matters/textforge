"""Desktop server entry point.

Starts the FastAPI server with embedded static frontend,
opens the browser, and handles graceful shutdown.
"""

from __future__ import annotations

import os
import signal
import socket
import sys
import threading
import time
import webbrowser

import uvicorn


def find_free_port(start: int = 18157, end: int = 18257) -> int:
    """Find an available port in range."""
    for port in range(start, end):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"No free port found in range {start}-{end}")


def open_browser_delayed(port: int, delay: float = 1.5) -> None:
    """Open the browser after a short delay to let the server start."""
    time.sleep(delay)
    webbrowser.open(f"http://127.0.0.1:{port}")


def main() -> None:
    port = find_free_port()

    # Write port to a file so other processes can discover it
    data_dir = os.environ.get(
        "TEXTFORGE_DATA_DIR",
        os.path.join(
            os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
            "TextForge",
        ),
    )
    os.makedirs(data_dir, exist_ok=True)
    port_file = os.path.join(data_dir, "port")
    with open(port_file, "w") as f:
        f.write(str(port))

    # Set database path to user data dir
    db_path = os.path.join(data_dir, "textforge.db")
    os.environ.setdefault(
        "TEXTFORGE_DATABASE_URL",
        f"sqlite+aiosqlite:///{db_path}",
    )

    # Open browser in background thread
    browser_thread = threading.Thread(
        target=open_browser_delayed, args=(port,), daemon=True
    )
    browser_thread.start()

    # Start uvicorn
    config = uvicorn.Config(
        "textforge.api:app",
        host="127.0.0.1",
        port=port,
        log_level="warning",
    )
    server = uvicorn.Server(config)

    # Handle clean shutdown
    def shutdown_handler(signum, frame):
        server.should_exit = True

    if sys.platform == "win32":
        signal.signal(signal.SIGBREAK, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)
    signal.signal(signal.SIGINT, shutdown_handler)

    server.run()

    # Cleanup port file
    try:
        os.remove(port_file)
    except OSError:
        pass


if __name__ == "__main__":
    main()
