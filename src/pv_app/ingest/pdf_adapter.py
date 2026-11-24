"""Cienki adapter: PDF → surowe wiersze i komórki tabel (ADR 0005)."""

import re
from pathlib import Path
from typing import Any, BinaryIO, cast

import pdfplumber

from pv_app.ingest.raw import RawDocument, RawPage, Row

_GLYPH_CODES = re.compile(r"\(cid:\d+\)")

CELL_GAP_PT = 5.0
"""Odstęp między znakami (w punktach), od którego zaczyna się nowa komórka.

Spacja między słowami i odstęp tysięcy mają 1–3 pt, kolumny tabel Faktur 10 pt i więcej."""

_SPACE_GAP_EM = 0.15
"""Odstęp (w ułamku wielkości czcionki), od którego między znakami stoi spacja."""


def read_pdf(file: Path | BinaryIO) -> RawDocument:
    """Tekst każdej strony, wiersz po wierszu, oraz te same wiersze podzielone na komórki.

    Pogrubienia w PDF-ach Taurona są drukowane trzykrotnie w tym samym miejscu, stąd
    ``dedupe_chars``; kody QR i kreskowe dają ciągi ``(cid:N)``, które usuwamy.
    """
    pages = []
    with pdfplumber.open(cast(Path, file)) as pdf:  # przyjmuje też strumień binarny
        for number, page in enumerate(pdf.pages, 1):
            page = page.dedupe_chars()
            text = page.extract_text() or ""
            lines = (_clean(line) for line in text.splitlines())
            rows = (_cells(line["chars"]) for line in page.extract_text_lines(return_chars=True))
            pages.append(
                RawPage(
                    number=number,
                    lines=tuple(line for line in lines if line),
                    rows=tuple(row for row in rows if row),
                )
            )
    return RawDocument(pages=tuple(pages))


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", _GLYPH_CODES.sub("", text)).strip()


def _cells(chars: list[dict[str, Any]]) -> Row:
    """Komórki wiersza: znaki rozdzielone odstępem większym niż ``CELL_GAP_PT``."""
    cells: list[str] = []
    current = ""
    previous: dict[str, Any] | None = None
    for char in chars:
        if not char["text"].strip():
            continue
        if previous is not None:
            gap = char["x0"] - previous["x1"]
            if gap > CELL_GAP_PT:
                cells.append(current)
                current = ""
            elif gap > _SPACE_GAP_EM * min(char["size"], previous["size"]):
                current += " "
        current += char["text"]
        previous = char
    cells.append(current)
    return tuple(cell for cell in (_clean(cell) for cell in cells) if cell)
