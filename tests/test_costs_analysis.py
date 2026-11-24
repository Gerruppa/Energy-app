"""Analiza zakładki Koszty i Faktury na Repository w pamięci."""

from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path

from pv_app.domain.invoice import (
    DateRange,
    DocumentKind,
    Invoice,
    ReadingType,
    SettlementBasis,
    Source,
)
from pv_app.features.costs.analysis import InvoiceListRow, invoice_list
from pv_app.ingest import import_document
from pv_app.ingest.raw import RawDocument
from pv_app.storage.in_memory import InMemoryRepository

FIXTURES = Path(__file__).parent / "fixtures"


def fixture_invoice(name: str) -> Invoice:
    invoice = import_document(RawDocument.from_json(FIXTURES / f"{name}.json")).invoice
    assert invoice is not None
    return invoice


def test_invoice_list_shows_period_kind_basis_and_period_cost_newest_first() -> None:
    october = fixture_invoice("new_layout_net_metering_monthly")
    september = replace(
        october,
        header=replace(
            october.header,
            number="T/K1/BN000001/0003/26",
            billing_period=DateRange(date(2026, 9, 1), date(2026, 9, 30)),
        ),
        readings=tuple(replace(r, reading_type=ReadingType.ESTIMATED) for r in october.readings),
    )
    repository = InMemoryRepository()
    for invoice in (september, october, fixture_invoice("new_layout_standard_half_year")):
        repository.add_invoice(invoice)

    rows = invoice_list(repository, "590000000000000001")

    assert rows == [
        InvoiceListRow(
            number="T/K1/BN000001/0004/26",
            period=DateRange(date(2026, 10, 1), date(2026, 10, 31)),
            kind=DocumentKind.SETTLEMENT_INVOICE,
            basis=SettlementBasis.ACTUAL_READING,
            imported_kwh=Decimal("150"),
            exported_kwh=Decimal("300"),
            period_cost=Decimal("32.04"),
            source=Source("T/K1/BN000001/0004/26", 3),
        ),
        InvoiceListRow(
            number="T/K1/BN000001/0003/26",
            period=DateRange(date(2026, 9, 1), date(2026, 9, 30)),
            kind=DocumentKind.SETTLEMENT_INVOICE,
            basis=SettlementBasis.ESTIMATED_READING,
            imported_kwh=Decimal("150"),
            exported_kwh=Decimal("300"),
            period_cost=Decimal("32.04"),
            source=Source("T/K1/BN000001/0004/26", 3),
        ),
    ]


def test_invoice_list_is_empty_for_metering_point_without_invoices() -> None:
    assert invoice_list(InMemoryRepository(), "590000000000000001") == []
