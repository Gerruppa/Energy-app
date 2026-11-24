"""Lokalny test na prawdziwych Fakturach z ``References/`` (ADR 0005).

Na GitHubie katalogu nie ma (ADR 0004), więc test jest pomijany. Asercje nie wypisują
kwot ani numerów z Faktur, żeby nie trafiły do logów.
"""

import hashlib
from pathlib import Path

import pytest

from pv_app.ingest import import_file

REFERENCES = Path(__file__).resolve().parent.parent / "References"
UNSUPPORTED = "Nieobsługiwany rodzaj dokumentu"

pytestmark = pytest.mark.real_pdfs


def _unique_pdfs() -> list[Path]:
    if not REFERENCES.is_dir():
        return []
    seen: set[str] = set()
    unique = []
    for path in sorted(REFERENCES.rglob("*.pdf")):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest not in seen:
            seen.add(digest)
            unique.append(path)
    return unique


PDFS = _unique_pdfs()


@pytest.mark.skipif(not PDFS, reason="brak katalogu References/ z Fakturami")
# Identyfikatory to numery kolejne: nazwy plików zawierają numery Faktur.
@pytest.mark.parametrize("path", PDFS, ids=[f"pdf{i}" for i in range(len(PDFS))])
def test_invoice_is_imported_with_agreeing_totals_or_rejected_as_unsupported(path: Path) -> None:
    result = import_file(path)

    if result.invoice is None:
        assert result.rejection is not None
        assert result.rejection.startswith(UNSUPPORTED), "Faktura w nowym układzie odrzucona"
        return
    assert result.rejection is None
    assert result.warnings == ()
    invoice = result.invoice
    assert invoice.number.replace("/", "_") in path.stem
    assert invoice.lines
    assert invoice.readings
    period = invoice.header.billing_period
    assert period.start < period.end <= invoice.header.issue_date
