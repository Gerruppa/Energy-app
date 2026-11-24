"""Cienki adapter: PDF → surowe wiersze (ADR 0005)."""

import re
from pathlib import Path
from typing import BinaryIO, cast

import pdfplumber

from pv_app.ingest.raw import RawDocument, RawPage

_GLYPH_CODES = re.compile(r"\(cid:\d+\)")


def read_pdf(file: Path | BinaryIO) -> RawDocument:
    """Tekst każdej strony, wiersz po wierszu.

    Pogrubienia w PDF-ach Taurona są drukowane trzykrotnie w tym samym miejscu, stąd
    ``dedupe_chars``; kody QR i kreskowe dają ciągi ``(cid:N)``, które usuwamy.
    """
    pages = []
    with pdfplumber.open(cast(Path, file)) as pdf:  # przyjmuje też strumień binarny
        for number, page in enumerate(pdf.pages, 1):
            text = page.dedupe_chars().extract_text() or ""
            lines = (
                re.sub(r"\s+", " ", _GLYPH_CODES.sub("", line)).strip()
                for line in text.splitlines()
            )
            pages.append(RawPage(number=number, lines=tuple(line for line in lines if line)))
    return RawDocument(pages=tuple(pages))
