"""Kontrola wydruku „Faktura po ludzku”: każda Faktura z katalogu danych → PDF → liczba stron.

    uv run python scripts/print_check.py KATALOG [--url http://localhost:8502] [--ppe dom-1]
        [--keep KATALOG_PDF]

Wymaga działającej aplikacji na tych samych danych (podgląd „demo” z ``.claude/launch.json``
albo ``python -m pv_app --data-dir KATALOG --port 8502``). Drukuje headless Edge (albo
Chrome) przez DevTools Protocol: czeka, aż strona Faktury się wyrenderuje, i drukuje ją jak
Ctrl+P, z pełną listą Pozycji faktury zwiniętą. Kod wyjścia 1, gdy któraś Faktura nie mieści
się na 1 stronie A4 albo się nie wyrenderowała.

Serwer wczytuje zmieniony kod dopiero przy rerunie w otwartej karcie (klawisz R) albo po
restarcie: nowa karta, jak ta z wydruku, dostaje kod sprzed zmiany.
"""

import argparse
import asyncio
import base64
import itertools
import json
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import pdfplumber
from websockets.asyncio.client import ClientConnection, connect

from pv_app.storage.sqlite import SqliteRepository

BROWSERS = (
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
)
RENDER_TIMEOUT_S = 30
PRINT_ATTEMPTS = 3
RENDERED = """(() => {
  const title = document.querySelector("h1");
  const ready = [...document.querySelectorAll("h3")].some(
    h => h.innerText.startsWith("Ten sam okres rok wcześniej"));
  const printStyle = [...document.querySelectorAll("style")].some(
    s => s.textContent.includes("st-key-invoice-lines"));
  return !!title && title.innerText.includes(%s) && ready && printStyle
    && document.fonts.status === "loaded";
})()"""
"""Strona gotowa: tytuł z numerem Faktury, ostatnia sekcja przed listą Pozycji faktury, styl
druku i czcionki (bez nich pierwszy wydruk po starcie przeglądarki wychodzi na kilka stron)."""


class DevTools:
    """Jedna karta przeglądarki sterowana przez DevTools Protocol."""

    def __init__(self, connection: ClientConnection) -> None:
        self._connection = connection
        self._ids = itertools.count(1)

    async def call(self, method: str, **params: Any) -> dict[str, Any]:
        message_id = next(self._ids)
        await self._connection.send(
            json.dumps({"id": message_id, "method": method, "params": params})
        )
        while True:
            reply = json.loads(await self._connection.recv())
            if reply.get("id") == message_id:
                if "error" in reply:
                    raise RuntimeError(f"{method}: {reply['error']}")
                result: dict[str, Any] = reply["result"]
                return result

    async def print_invoice(self, url: str, number: str) -> bytes | None:
        """PDF strony Faktury; ``None``, gdy strona się nie wyrenderowała."""
        await self.call("Page.navigate", url=url)
        check = RENDERED % json.dumps(number)
        deadline = time.monotonic() + RENDER_TIMEOUT_S
        while time.monotonic() < deadline:
            result = await self.call("Runtime.evaluate", expression=check)
            if result["result"].get("value") is True:
                await asyncio.sleep(1)  # dorysowanie tabel i czcionek
                return await self._print_to_pdf()
            await asyncio.sleep(0.5)
        return None

    async def _print_to_pdf(self) -> bytes:
        """Wydruk jak Ctrl+P; przeglądarka czasem chwilowo odpowiada „Printing is not available”."""
        for attempt in range(PRINT_ATTEMPTS):
            try:
                pdf = await self.call(
                    "Page.printToPDF", preferCSSPageSize=True, displayHeaderFooter=False
                )
                return base64.b64decode(pdf["data"])
            except RuntimeError:
                if attempt == PRINT_ATTEMPTS - 1:
                    raise
                await asyncio.sleep(2)
        raise AssertionError("nieosiągalne")


def _browser() -> Path:
    found = next((b for b in BROWSERS if b.exists()), None)
    if found is None:
        sys.exit("Nie znaleziono Edge ani Chrome.")
    return found


def _read_port(port_file: Path) -> str | None:
    """Port DevTools z pliku, który przeglądarka zapisuje po starcie (w trakcie zapisu
    Windows blokuje go do odczytu)."""
    try:
        lines = port_file.read_text().splitlines()
    except OSError:
        return None
    return lines[0] if lines else None


def _start_browser(profile: Path) -> tuple[subprocess.Popen[bytes], str]:
    """Headless przeglądarka i adres websocket jej karty."""
    process = subprocess.Popen(
        [
            str(_browser()),
            "--headless=new",
            "--disable-gpu",
            "--no-first-run",
            "--disable-sync",
            "--disable-extensions",
            "--remote-debugging-port=0",
            "--remote-allow-origins=*",
            f"--user-data-dir={profile}",
            "--window-size=1200,1600",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    port_file = profile / "DevToolsActivePort"
    deadline = time.monotonic() + 30
    while not (port := _read_port(port_file)):
        if time.monotonic() > deadline:
            process.kill()
            sys.exit("Przeglądarka nie wystartowała.")
        time.sleep(0.2)
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list") as response:
        targets = json.load(response)
    # Edge potrafi otworzyć własne okna (np. edge://sync-confirmation-dialog/); karta do
    # wydruku to ta pusta, otwarta przy starcie.
    page = next(t for t in targets if t["type"] == "page" and t["url"] == "about:blank")
    return process, str(page["webSocketDebuggerUrl"])


async def _check(args: argparse.Namespace, work: Path) -> int:
    process, socket_url = _start_browser(work / "profil")
    repository = SqliteRepository(args.data_dir / "pv_app.sqlite3")
    failed = 0
    try:
        async with connect(socket_url, max_size=None) as connection:
            tab = DevTools(connection)
            for point in repository.list_metering_points():
                if args.ppe and point.slug != args.ppe:
                    continue
                for n, invoice in enumerate(repository.list_invoices(point.ppe_number)):
                    query = urllib.parse.urlencode({"ppe": point.slug, "faktura": invoice.number})
                    pdf = await tab.print_invoice(f"{args.url}/?{query}", invoice.number)
                    if pdf is None:
                        verdict = "NIE WYRENDEROWANO"
                    else:
                        out = (args.keep or work) / f"{point.slug}-{n}.pdf"
                        out.write_bytes(pdf)
                        with pdfplumber.open(out) as document:
                            pages = len(document.pages)
                        verdict = "1 strona" if pages == 1 else f"{pages} STRONY"
                    failed += verdict != "1 strona"
                    print(f"{point.slug}  {invoice.number}  {verdict}", flush=True)
    finally:
        repository.close()
        process.kill()
        process.wait()
    return failed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("data_dir", type=Path)
    parser.add_argument("--url", default="http://localhost:8502")
    parser.add_argument("--ppe", help="tylko ten PPE (wartość ?ppe=…)")
    parser.add_argument("--keep", type=Path, help="zapisz PDF-y w tym katalogu")
    args = parser.parse_args()
    if args.keep:
        args.keep.mkdir(parents=True, exist_ok=True)
    # Procesy potomne przeglądarki potrafią jeszcze chwilę trzymać pliki profilu.
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        failed = asyncio.run(_check(args, Path(tmp)))
    if failed:
        sys.exit(f"{failed} Faktur nie mieści się na 1 stronie albo się nie wyrenderowało.")


if __name__ == "__main__":
    main()
