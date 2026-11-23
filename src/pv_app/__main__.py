"""Start aplikacji: ``uv run python -m pv_app`` (tak robi ``Start.bat``).

Uruchamia serwer Streamlit bez pytań w konsoli i otwiera przeglądarkę, gdy serwer
odpowiada. Jeśli aplikacja już działa, tylko otwiera przeglądarkę.
"""

import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

from streamlit.web import cli

HOST = "localhost"
PORT = 8501
URL = f"http://{HOST}:{PORT}"
MAIN = Path(__file__).resolve().parent / "app" / "main.py"


def _is_listening() -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((HOST, PORT)) == 0


def _open_browser_when_ready(timeout_s: float = 60) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if _is_listening():
            webbrowser.open(URL)
            return
        time.sleep(0.3)


def main() -> None:
    if _is_listening():
        print(f"Aplikacja już działa: {URL}")
        webbrowser.open(URL)
        return
    threading.Thread(target=_open_browser_when_ready, daemon=True).start()
    sys.argv = [
        "streamlit",
        "run",
        str(MAIN),
        "--server.headless=true",
        f"--server.port={PORT}",
        f"--server.address={HOST}",
        "--browser.gatherUsageStats=false",
        "--client.toolbarMode=minimal",
    ]
    cli.main()


if __name__ == "__main__":
    main()
