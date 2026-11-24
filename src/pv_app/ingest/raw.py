"""Surowe wiersze dokumentu: granica między adapterem PDF a parserem (ADR 0005)."""

import json
from dataclasses import dataclass
from pathlib import Path

Row = tuple[str, ...]
"""Wiersz strony podzielony na komórki tabeli po położeniu znaków (odstęp między kolumnami)."""


@dataclass(frozen=True)
class RawPage:
    number: int
    """Numer strony w PDF-ie, od 1."""
    lines: tuple[str, ...]
    rows: tuple[Row, ...] = ()
    """Wiersze z komórkami; stary układ czyta z nich tabele, bo w samym tekście odstęp
    tysięcy (``1 722``) wygląda jak granica kolumn. Pusta krotka, gdy zrzut ma tylko wiersze."""


@dataclass(frozen=True)
class RawDocument:
    pages: tuple[RawPage, ...]

    @classmethod
    def from_json(cls, path: Path) -> "RawDocument":
        """Zrzut wierszy zapisany jako ``{"pages": [[wiersz, ...], ...]}``."""
        return cls.loads(path.read_bytes())

    @classmethod
    def loads(cls, text: str | bytes) -> "RawDocument":
        """Zrzut wierszy z treści JSON, np. wgranego pliku.

        Wiersz to tekst albo lista komórek; strona z choć jednym wierszem z komórkami
        dostaje ``rows`` (wiersz tekstowy = jedna komórka), a ``lines`` to komórki
        połączone spacją.
        """
        data = json.loads(text)
        return cls(pages=tuple(_page(i, items) for i, items in enumerate(data["pages"], 1)))


def _page(number: int, items: list[str | list[str]]) -> RawPage:
    if all(isinstance(item, str) for item in items):
        return RawPage(number=number, lines=tuple(str(item) for item in items))
    rows = tuple((item,) if isinstance(item, str) else tuple(item) for item in items)
    return RawPage(number=number, lines=tuple(" ".join(row) for row in rows), rows=rows)
