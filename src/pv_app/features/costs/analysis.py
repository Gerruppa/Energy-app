"""Koszty i Faktury: czyste analizy na ``Repository``."""

from dataclasses import dataclass
from decimal import Decimal

from pv_app.domain.invoice import DateRange, DocumentKind, SettlementBasis, Source
from pv_app.storage.repository import Repository


@dataclass(frozen=True)
class InvoiceListRow:
    number: str
    period: DateRange
    kind: DocumentKind
    basis: SettlementBasis
    """Podstawa rozliczenia."""
    imported_kwh: Decimal
    exported_kwh: Decimal | None
    period_cost: Decimal
    """Koszt okresu (brutto)."""
    source: Source


def invoice_list(repository: Repository, ppe_number: str) -> list[InvoiceListRow]:
    """Faktury PPE od najnowszego Okresu rozliczeniowego."""
    return [
        InvoiceListRow(
            number=invoice.number,
            period=invoice.header.billing_period,
            kind=invoice.kind,
            basis=invoice.settlement_basis,
            imported_kwh=invoice.imported_kwh,
            exported_kwh=invoice.exported_kwh,
            period_cost=invoice.period_cost,
            source=invoice.summary.source,
        )
        for invoice in reversed(repository.list_invoices(ppe_number))
    ]
