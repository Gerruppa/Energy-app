"""Start aplikacji: ``uv run python -m pv_app`` (tak robi ``Start.bat``).

Uruchamia serwer Streamlit bez pytań w konsoli i otwiera przeglądarkę, gdy serwer
odpowiada. Jeśli aplikacja już działa, tylko otwiera przeglądarkę.

    uv run python -m pv_app --data-dir KATALOG --port 8502 --no-browser

uruchamia drugą kopię na innych danych (np. z ``scripts/seed_demo.py``), bez otwierania
przeglądarki: tak startuje podgląd „demo” z ``.claude/launch.json``. ``--today RRRR-MM-DD``
ustawia „dziś” aplikacji (jak ``PV_APP_TODAY``), np. w podglądzie „demo-pozniej”, żeby na
stałych danych demo widać było Brakującą Fakturę i Zaległy Profil godzinowy.
"""

import argparse
import os
import socket
import sys
import threading
import time
import webbrowser
from collections.abc import Sequence
from datetime import date
from pathlib import Path

from streamlit.web import cli

from pv_app.app.settings import DATA_DIR_ENV, TODAY_ENV, parse_today, today

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


def _today_option(text: str) -> date:
    try:
        return parse_today(text)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from None


def configure(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Czyta opcje startu i przekazuje katalog danych i „dziś” aplikacji serwerowi przez
    zmienne środowiskowe; nieprawidłowa data (w ``--today`` albo w samej ``PV_APP_TODAY``)
    kończy start błędem."""
    parser = argparse.ArgumentParser(prog="python -m pv_app", description=__doc__.splitlines()[0])
    parser.add_argument("--data-dir", type=Path, help=f"katalog danych (jak {DATA_DIR_ENV})")
    parser.add_argument(
        "--today",
        type=_today_option,
        metavar="RRRR-MM-DD",
        help=f"„dziś” aplikacji zamiast prawdziwej daty (jak {TODAY_ENV})",
    )
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--no-browser", action="store_true", help="nie otwieraj przeglądarki")
    args = parser.parse_args(argv)
    if args.data_dir is not None:
        os.environ[DATA_DIR_ENV] = str(args.data_dir.resolve())
    if args.today is not None:
        os.environ[TODAY_ENV] = args.today.isoformat()
    else:
        try:
            today()  # sama PV_APP_TODAY: sprawdzona przed startem serwera, nie w trakcie
        except ValueError as error:
            parser.error(str(error))
    return args


def main() -> None:
    args = configure()

    url = f"http://{HOST}:{args.port}"
    if _is_listening(args.port):
        print(f"Aplikacja już działa: {url}")
        if args.data_dir is not None or args.today is not None:
            print(
                "Uwaga: działająca aplikacja zostaje przy swoim katalogu danych i dacie; "
                "--data-dir i --today działają tylko przy nowym starcie (inny --port)."
            )
        if not args.no_browser:
            webbrowser.open(url)
        return
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
