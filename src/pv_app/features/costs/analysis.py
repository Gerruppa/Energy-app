"""Koszty i Faktury: czyste analizy na ``Repository``."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from pv_app.domain.invoice import DateRange, DocumentKind, SettlementBasis, Source
from pv_app.domain.period_cost import PeriodCosts
from pv_app.features.base import Filters
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
    """Koszt okresu (brutto), po bonifikatach z Faktury i Not obciążeniowych."""
    source: Source
    corrects: str | None = None
    """Numer Faktury, którą ta Faktura korygująca zastępuje."""
    superseded_by: str | None = None
    """Numer Faktury korygującej, która zastępuje tę Fakturę; jej Koszt okresu się nie liczy."""
    debit_notes: tuple[str, ...] = ()
    """Numery Not obciążeniowych, których bonifikaty pomniejszają Koszt okresu."""


@dataclass(frozen=True)
class DebitNoteListRow:
    number: str
    issue_date: date
    sale_date: date
    discount: Decimal
    """Bonifikata po korekcie."""
    amount_due: Decimal
    invoice_number: str | None
    """Faktura, której Koszt okresu pomniejsza; ``None``, gdy nie ma jej w danych."""
    superseded_by: str | None
    source: Source


def _period_costs(repository: Repository, ppe_number: str) -> PeriodCosts:
    return PeriodCosts(
        invoices=repository.list_invoices(ppe_number),
        debit_notes=repository.list_debit_notes(ppe_number),
    )


def invoice_list(repository: Repository, filters: Filters) -> list[InvoiceListRow]:
    """Faktury PPE od najnowszego Okresu rozliczeniowego, także zastąpione korektą; tylko te,
    których Okres rozliczeniowy zachodzi na Okres widoku."""
    costs = _period_costs(repository, filters.ppe_number)
    superseded = costs.superseded_invoices
    return [
        InvoiceListRow(
            number=invoice.number,
            period=invoice.header.billing_period,
            kind=invoice.kind,
            basis=invoice.settlement_basis,
            imported_kwh=invoice.imported_kwh,
            exported_kwh=invoice.exported_kwh,
            period_cost=costs.period_cost(invoice),
            source=invoice.summary.source,
            corrects=invoice.correction.corrected_invoice_number if invoice.correction else None,
            superseded_by=superseded.get(invoice.number),
            debit_notes=tuple(note.number for note in costs.debit_notes_for(invoice)),
        )
        for invoice in sorted(
            (i for i in costs.invoices if _overlaps(i.header.billing_period, filters)),
            key=lambda i: (i.header.billing_period.start, i.header.issue_date, i.number),
            reverse=True,
        )
    ]


def debit_note_list(repository: Repository, filters: Filters) -> list[DebitNoteListRow]:
    """Noty obciążeniowe PPE od najnowszej, z Fakturą, której okres pomniejszają; tylko te,
    których data sprzedaży albo Faktura leży w Okresie widoku."""
    costs = _period_costs(repository, filters.ppe_number)
    superseded = costs.superseded_debit_notes
    rows = []
    for note in reversed(costs.debit_notes):
        invoice = costs.invoice_for(note)
        period = (
            invoice.header.billing_period if invoice else DateRange(note.sale_date, note.sale_date)
        )
        if not _overlaps(period, filters):
            continue
        rows.append(
            DebitNoteListRow(
                number=note.number,
                issue_date=note.issue_date,
                sale_date=note.sale_date,
                discount=note.discount,
                amount_due=note.amount_due,
                invoice_number=invoice.number if invoice else None,
                superseded_by=superseded.get(note.number),
                source=note.source,
            )
        )
    return rows


def _overlaps(period: DateRange, filters: Filters) -> bool:
    dates = filters.view_period.dates
    return dates is None or dates.overlaps(period)
