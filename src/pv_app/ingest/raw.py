"""Surowe wiersze dokumentu: granica między adapterem PDF a parserem (ADR 0005)."""

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RawPage:
    number: int
    """Numer strony w PDF-ie, od 1."""
    lines: tuple[str, ...]


@dataclass(frozen=True)
class RawDocument:
    pages: tuple[RawPage, ...]

    @classmethod
    def from_json(cls, path: Path) -> "RawDocument":
        """Zrzut wierszy zapisany jako ``{"pages": [[wiersz, ...], ...]}``."""
        return cls.loads(path.read_bytes())

    @classmethod
    def loads(cls, text: str | bytes) -> "RawDocument":
        """Zrzut wierszy z treści JSON, np. wgranego pliku."""
        data = json.loads(text)
        return cls(
            pages=tuple(
                RawPage(number=i, lines=tuple(lines)) for i, lines in enumerate(data["pages"], 1)
            )
        )
