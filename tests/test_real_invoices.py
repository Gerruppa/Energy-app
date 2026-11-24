"""Lokalny test na prawdziwych Fakturach z ``References/`` (ADR 0005).

Na GitHubie katalogu nie ma (ADR 0004), więc test jest pomijany. Asercje nie wypisują
kwot ani numerów z Faktur, żeby nie trafiły do logów.
"""

import functools
import hashlib
from pathlib import Path

import pytest

from pv_app.domain.invoice import DocumentKind, Layout
from pv_app.ingest import ImportResult, import_file

REFERENCES = Path(__file__).resolve().parent.parent / "References"

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
no_references = pytest.mark.skipif(not PDFS, reason="brak katalogu References/ z Fakturami")


@functools.cache
def _import(path: Path) -> ImportResult:
    return import_file(path)


@no_references
# Identyfikatory to numery kolejne: nazwy plików zawierają numery Faktur.
@pytest.mark.parametrize("path", PDFS, ids=[f"pdf{i}" for i in range(len(PDFS))])
def test_document_is_imported_with_agreeing_totals(path: Path) -> None:
    """Faktury (rozliczeniowe w obu układach i korygujące) oraz Noty obciążeniowe wchodzą."""
    result = _import(path)

    assert result.rejection is None, "dokument odrzucony"
    assert result.warnings == ()
    if result.debit_note is not None:
        note = result.debit_note
        assert note.number.replace("/", "_") in path.stem
        assert note.items
        assert note.sale_date <= note.issue_date
        return
    invoice = result.invoice
    assert invoice is not None
    assert invoice.number.replace("/", "_") in path.stem
    assert invoice.lines
    assert invoice.readings
    period = invoice.header.billing_period
    assert period.start < period.end <= invoice.header.issue_date
    if invoice.correction is not None:
        assert invoice.correction.corrected_invoice_number != invoice.number
        assert invoice.correction.reason
    elif invoice.header.billing_frequency_months != 1:
        assert invoice.forecasts, "Faktura nie miesięczna bez harmonogramu Prognoz"


@no_references
def test_invoices_of_both_layouts_are_imported() -> None:
    """Pilnuje, żeby żadnego układu nie odrzucono po cichu jako nieobsługiwanego."""
    layouts = {result.invoice.layout for result in map(_import, PDFS) if result.invoice is not None}

    assert layouts == {Layout.OLD, Layout.NEW}


@no_references
def test_correcting_invoices_and_debit_notes_are_imported() -> None:
    """Pilnuje, żeby Faktury korygujące i Noty obciążeniowe nie zniknęły z importu."""
    results = list(map(_import, PDFS))
    kinds = {r.invoice.kind for r in results if r.invoice is not None}

    assert DocumentKind.CORRECTING_INVOICE in kinds
    assert any(r.debit_note is not None for r in results)
