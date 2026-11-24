"""Start aplikacji: ``uv run python -m pv_app`` (tak robi ``Start.bat``).

Uruchamia serwer Streamlit bez pytań w konsoli i otwiera przeglądarkę, gdy serwer
odpowiada. Jeśli aplikacja już działa, tylko otwiera przeglądarkę.

    uv run python -m pv_app --data-dir KATALOG --port 8502 --no-browser

uruchamia drugą kopię na innych danych (np. z ``scripts/seed_demo.py``), bez otwierania
przeglądarki: tak startuje podgląd „demo” z ``.claude/launch.json``.
"""

import argparse
import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

from streamlit.web import cli

from pv_app.app.settings import DATA_DIR_ENV

HOST = "localhost"
DEFAULT_PORT = 8501
PACKAGE = Path(__file__).resolve().parent
MAIN = PACKAGE / "app" / "main.py"


def _is_listening(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((HOST, port)) == 0


def _open_browser_when_ready(url: str, port: int, timeout_s: float = 60) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if _is_listening(port):
            webbrowser.open(url)
            return
        time.sleep(0.3)


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m pv_app", description=__doc__.splitlines()[0])
    parser.add_argument("--data-dir", type=Path, help=f"katalog danych (jak {DATA_DIR_ENV})")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--no-browser", action="store_true", help="nie otwieraj przeglądarki")
    args = parser.parse_args()

    url = f"http://{HOST}:{args.port}"
    if _is_listening(args.port):
        print(f"Aplikacja już działa: {url}")
        if not args.no_browser:
            webbrowser.open(url)
        return
    if args.data_dir is not None:
        os.environ[DATA_DIR_ENV] = str(args.data_dir.resolve())
    # Streamlit przeładowuje po zmianie tylko moduły obok main.py albo w PYTHONPATH; z src/
    # w PYTHONPATH zmiana w features/ czy domain/ działa bez restartu serwera.
    paths = [str(PACKAGE.parent), *filter(None, [os.environ.get("PYTHONPATH")])]
    os.environ["PYTHONPATH"] = os.pathsep.join(paths)
    if not args.no_browser:
        threading.Thread(
            target=_open_browser_when_ready, args=(url, args.port), daemon=True
        ).start()
    sys.argv = [
        "streamlit",
        "run",
        str(MAIN),
        "--server.headless=true",
        f"--server.port={args.port}",
        f"--server.address={HOST}",
        "--browser.gatherUsageStats=false",
        "--client.toolbarMode=minimal",
    ]
    cli.main()


if __name__ == "__main__":
    main()
