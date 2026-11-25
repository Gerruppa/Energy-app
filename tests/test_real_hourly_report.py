"""Lokalny test na prawdziwych Raportach wartości godzinowych (xlsx) z ``References/``.

Na GitHubie katalogu nie ma (ADR 0004), więc test jest pomijany. Asercje nie wypisują
ilości ani numerów, żeby nie trafiły do logów.
"""

import functools
from decimal import Decimal
from pathlib import Path

import pytest

from pv_app.domain.hourly_profile import HourlyValuesReport
from pv_app.domain.invoice import Invoice
from pv_app.ingest import import_file

REFERENCES = Path(__file__).resolve().parent.parent / "References"
REPORTS = sorted(REFERENCES.rglob("*.xlsx")) if REFERENCES.is_dir() else []
TOLERANCE = Decimal("0.01")
"""Godziny Profilu godzinowego a Faktura: Tauron rozlicza z odczytów licznika, więc suma
godzin może się nieznacznie różnić."""

pytestmark = [
    pytest.mark.real_pdfs,
    pytest.mark.skipif(not REPORTS, reason="brak Raportów wartości godzinowych w References/"),
]


@functools.cache
def _report(path: Path) -> HourlyValuesReport:
    result = import_file(path)
    assert result.rejection is None, "raport odrzucony"
    assert result.hourly_report is not None
    return result.hourly_report


@functools.cache
def _invoices(directory: Path) -> tuple[Invoice, ...]:
    """Faktury z katalogu raportu (Faktury innych PPE leżą w innych katalogach)."""
    by_number = {}
    for path in sorted(directory.rglob("*.pdf")):
        invoice = import_file(path).invoice
        if invoice is not None:
            by_number[invoice.number] = invoice
    return tuple(by_number.values())


def _close(hourly: Decimal, invoice: Decimal) -> bool:
    return abs(hourly - invoice) <= TOLERANCE * max(invoice, Decimal(1))


@pytest.mark.parametrize("path", REPORTS, ids=lambda p: p.parent.name)
def test_balanced_hours_add_up_to_invoices_of_covered_periods(path: Path) -> None:
    report = _report(path)
    covered = [
        i
        for i in _invoices(path.parent)
        if i.header.ppe_number == report.ppe_number
        and report.first_day <= i.header.billing_period.start
        and i.header.billing_period.end <= report.last_day
    ]
    assert covered, "żadna Faktura nie leży w całości w okresie raportu"
    for invoice in covered:
        period = invoice.header.billing_period
        hours = [r for r in report.readings if period.start <= r.day <= period.end]
        imported = sum((r.imported_kwh for r in hours), Decimal())
        exported = sum((r.exported_kwh for r in hours), Decimal())
        imported_ok = _close(imported, invoice.imported_kwh)
        exported_ok = _close(exported, invoice.exported_kwh or Decimal())
        assert imported_ok, f"Energia pobrana różni się od Faktury za okres od {period.start}"
        assert exported_ok, f"Energia oddana różni się od Faktury za okres od {period.start}"
