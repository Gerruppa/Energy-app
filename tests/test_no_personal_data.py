"""Kontrola prywatności: dane z prawdziwych Faktur nie trafiają do plików w gicie (ADR 0004).

Z PDF-ów w ``References/`` zbiera identyfikatory (numery PPE, klienta, liczników, rachunków,
serie numerów Faktur, imiona, nazwiska, ulice i miejscowości) oraz charakterystyczne wartości
(Saldo, stany Magazynu energii, Wynik rozliczenia) i szuka ich w plikach z ``git ls-files``.
Wyniki odczytu PDF-ów są w ``data/personal_tokens.json`` (poza gitem), więc kolejne
uruchomienia trwają sekundy. Bez ``References/`` (np. w CI) test jest pomijany.
Uruchamiany też przez hook ``.githooks/pre-commit``.
"""

import hashlib
import json
import re
import subprocess
from decimal import Decimal
from pathlib import Path

import pytest

from pv_app.ingest import import_document
from pv_app.ingest.pdf_adapter import read_pdf
from pv_app.ingest.raw import RawDocument

ROOT = Path(__file__).resolve().parent.parent
REFERENCES = ROOT / "References"
CACHE = ROOT / "data" / "personal_tokens.json"
CACHE_VERSION = 2
SKIPPED_FILES = {"uv.lock"}

_UPPER = "[A-ZĄĆĘŁŃÓŚŹŻ]+"
"""Słowo pisane wersalikami, jak imię i nazwisko Klienta na Fakturze."""

GENERIC_WORDS = {"TAURON", "SPRZEDAŻ", "LOKAL", "MIESZKALNY", "DOM", "UL", "AL", "OS", "PL"}
"""Słowa z nazw i adresów, które same niczego nie zdradzają."""


def _pl_money(value: Decimal) -> str:
    return f"{value:,.2f}".replace(",", " ").replace(".", ",")


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[A-ZĄĆĘŁŃÓŚŹŻ]{4,}", text.upper()) if w not in GENERIC_WORDS}


def _tokens(document: RawDocument) -> dict[str, list[str]]:
    """Wrażliwe ciągi z jednej Faktury, pogrupowane według rodzaju."""
    lines = [line for page in document.pages for line in page.lines]
    text = "\n".join(lines)
    found: dict[str, set[str]] = {
        "numer PPE": set(re.findall(r"\b59\d{16}\b", text)),
        "numer klienta": set(
            re.findall(r"(?:Numer Klienta:?|Adresat:|Tytuł płatności)\s*(\d{8})", text)
        ),
        "numer rachunku": {
            re.sub(r"\s", "", m) for m in re.findall(r"\b\d{2}(?: \d{4}){6}\b", text)
        },
        "numer licznika": set(re.findall(r"Licznik energii[^\n]*?(?:-| nr )(\w{6,})", text))
        | set(re.findall(r"^nr (\w{6,})$", text, re.MULTILINE)),
        "seria numerów Faktur": set(re.findall(r"/([A-Z]{1,3}\d{6})/", text)),
        "imię, nazwisko lub adres": set(),
        "kwota lub stan z Faktury": set(),
    }
    for i, line in enumerate(lines):
        if match := re.match(r"^Punkt Poboru Energii: \d+ \| (.+)$", line):
            found["imię, nazwisko lub adres"] |= _words(match.group(1))
            if i + 1 < len(lines):
                address = lines[i + 1]
                found["imię, nazwisko lub adres"] |= _words(address)
                found["imię, nazwisko lub adres"] |= set(re.findall(r"\b\d{2}-\d{3}\b", address))
        if match := re.match(
            rf"^TAURON Sprzedaż sp\. z o\.o\. ({_UPPER}(?: {_UPPER}){{1,3}})$", line
        ):
            found["imię, nazwisko lub adres"] |= _words(match.group(1))
    invoice = import_document(document).invoice
    if invoice is not None:
        values = found["kwota lub stan z Faktury"]
        summary = invoice.summary
        for amount in (summary.account_balance, summary.result.gross):
            if amount is not None and abs(amount) >= 100:
                values.add(_pl_money(abs(amount)))
        store = invoice.energy_settlement
        if store is not None:
            for kwh in (store.store_start_kwh, store.store_end_kwh):
                if kwh >= 1000:
                    values.add(str(int(kwh)))
    return {kind: sorted(values) for kind, values in found.items() if values}


def _load_tokens() -> dict[str, set[str]]:
    cache: dict[str, dict[str, list[str]]] = {}
    if CACHE.exists():
        stored = json.loads(CACHE.read_text(encoding="utf-8"))
        if stored.get("version") == CACHE_VERSION:
            cache = stored["files"]
    merged: dict[str, set[str]] = {}
    current: dict[str, dict[str, list[str]]] = {}
    for path in sorted(REFERENCES.rglob("*.pdf")):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest not in current:
            current[digest] = cache.get(digest) or _tokens(read_pdf(path))
    for tokens in current.values():
        for kind, values in tokens.items():
            merged.setdefault(kind, set()).update(values)
    if current != cache:
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(
            json.dumps({"version": CACHE_VERSION, "files": current}, ensure_ascii=False),
            encoding="utf-8",
        )
    return merged


def _tracked_files() -> list[Path]:
    names = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True
    ).stdout.split(b"\0")
    return [ROOT / n.decode() for n in names if n and n.decode() not in SKIPPED_FILES]


def _masked(token: str) -> str:
    return token[:2] + "…" if len(token) > 2 else "…"


@pytest.mark.skipif(not REFERENCES.is_dir(), reason="brak katalogu References/ z Fakturami")
def test_tracked_files_contain_no_data_from_real_invoices() -> None:
    tokens = _load_tokens()
    assert tokens.get("numer PPE"), "nie odczytano numerów PPE z References/"
    patterns = {
        kind: re.compile(
            r"(?<![\w,])(?:" + "|".join(re.escape(v) for v in values) + r")(?![\w,])",
            re.IGNORECASE,
        )
        for kind, values in tokens.items()
    }
    problems = []
    for path in _tracked_files():
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for number, line in enumerate(text.splitlines(), 1):
            for kind, pattern in patterns.items():
                if match := pattern.search(line):
                    where = path.relative_to(ROOT).as_posix()
                    problems.append(f"{where}:{number}: {kind} ({_masked(match.group(0))})")
    assert not problems, "Dane z prawdziwych Faktur w plikach gita:\n" + "\n".join(problems)
