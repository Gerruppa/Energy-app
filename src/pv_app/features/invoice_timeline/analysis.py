"""Oś czasu Faktur PPE: kompletność i wiarygodność danych.

Czysta analiza na ``Repository``; „dziś” podaje wywołujący.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from pv_app.domain.debit_note import DebitNote
from pv_app.domain.invoice import DateRange, DocumentKind, Invoice, SettlementBasis, Source
from pv_app.domain.period_cost import PeriodCosts
from pv_app.domain.view_period import first_day, last_day, month_index
from pv_app.features.monthly import ForecastLine, current_forecasts
from pv_app.storage.repository import Repository


@dataclass(frozen=True)
class TimelinePeriod:
    """Okres rozliczeniowy jednej Faktury na osi czasu (także zastąpionej)."""

    number: str
    kind: DocumentKind
    period: DateRange
    basis: SettlementBasis
    corrects: str | None
    """Numer Faktury, którą koryguje ta Faktura korygująca."""
    superseded_by: str | None
    """Numer Faktury korygującej, która zastępuje tę Fakturę."""
    period_cost: Decimal
    """Wyliczony: Wynik rozliczenia minus Bonifikaty (``PeriodCosts.period_cost``)."""
    result_source: Source
    """Strona z Wynikiem rozliczenia, z którego wyliczono Koszt okresu."""


@dataclass(frozen=True)
class Overlap:
    """Dni rozliczone przez dwie Faktury naraz (żadna nie koryguje drugiej)."""

    period: DateRange
    invoice_numbers: tuple[str, str]
    """Wcześniej zaczynająca się Faktura i ta, która na nią zachodzi."""


@dataclass(frozen=True)
class TimelineNote:
    """Nota obciążeniowa na osi czasu, w dniu sprzedaży."""

    number: str
    sale_date: date
    invoice_number: str | None
    """Faktura, której Koszt okresu pomniejsza Nota; ``None``: zastąpiona albo bez Faktury
    za ten okres."""
    source: Source


ESTIMATE_WINDOW_MONTHS = 12


@dataclass(frozen=True)
class EstimatedMonths:
    """Które z ostatnich 12 pełnych miesięcy przed „dziś” rozliczono na odczycie szacunkowym.

    Miesiąc liczy się, gdy choć jeden jego dzień rozlicza Faktura na odczycie szacunkowym;
    zostaje policzony także po wyrównaniu kolejną Fakturą i po zastąpieniu tej Faktury Fakturą
    korygującą."""

    window: DateRange
    months: tuple[int, ...]
    """``month_index`` miesięcy na odczycie szacunkowym, od najstarszego."""
    without_invoice: tuple[int, ...]
    """``month_index`` miesięcy okna, których żaden dzień nie ma Faktury."""


@dataclass(frozen=True)
class InvoiceTimeline:
    periods: tuple[TimelinePeriod, ...]
    """Wszystkie Faktury PPE od najstarszego Okresu rozliczeniowego."""
    gaps: tuple[DateRange, ...]
    """Dni bez Faktury między pierwszą a ostatnią Fakturą."""
    overlaps: tuple[Overlap, ...]
    estimated_months: EstimatedMonths
    debit_notes: tuple[TimelineNote, ...]
    """Od najstarszej daty sprzedaży."""
    forecasts: tuple[ForecastLine, ...]
    """Prognozy z aktualnych harmonogramów kończące się po ostatniej Fakturze; nie wchodzą
    do żadnych sum."""


def _timeline_period(invoice: Invoice, costs: PeriodCosts) -> TimelinePeriod:
    return TimelinePeriod(
        number=invoice.number,
        kind=invoice.kind,
        period=invoice.header.billing_period,
        basis=invoice.settlement_basis,
        corrects=invoice.correction.corrected_invoice_number if invoice.correction else None,
        superseded_by=costs.superseded_invoices.get(invoice.number),
        period_cost=costs.period_cost(invoice),
        result_source=invoice.summary.source,
    )


def _note(note: DebitNote, costs: PeriodCosts) -> TimelineNote:
    invoice = costs.invoice_for(note)
    return TimelineNote(
        note.number, note.sale_date, invoice.number if invoice else None, note.source
    )


def _months(invoice: Invoice) -> range:
    period = invoice.header.billing_period
    return range(month_index(period.start), month_index(period.end) + 1)


def _estimated_months(
    invoices: list[Invoice], counted: list[Invoice], today: date
) -> EstimatedMonths:
    """``invoices``: wszystkie Faktury PPE (szacunek); ``counted``: bez zastąpionych (pokrycie)."""
    last = month_index(today) - 1
    window = range(last - ESTIMATE_WINDOW_MONTHS + 1, last + 1)
    covered = {m for invoice in counted for m in _months(invoice)}
    estimated = {
        m
        for invoice in invoices
        if invoice.settlement_basis is SettlementBasis.ESTIMATED_READING
        for m in _months(invoice)
    }
    return EstimatedMonths(
        DateRange(first_day(window[0]), last_day(window[-1])),
        months=tuple(m for m in window if m in estimated),
        without_invoice=tuple(m for m in window if m not in covered),
    )


def invoice_timeline(
    repository: Repository, ppe_number: str, today: date
) -> InvoiceTimeline | None:
    """Oś czasu Faktur PPE; ``None`` bez Faktur."""
    invoices = repository.list_invoices(ppe_number)
    if not invoices:
        return None
    costs = PeriodCosts(invoices, repository.list_debit_notes(ppe_number))
    superseded = costs.superseded_invoices
    counted = [i for i in invoices if i.number not in superseded]
    gaps: list[DateRange] = []
    overlaps: list[Overlap] = []
    reaching = counted[0]
    """Faktura, której Okres rozliczeniowy sięga najdalej spośród dotychczasowych."""
    for invoice in counted[1:]:
        period = invoice.header.billing_period
        covered_to = reaching.header.billing_period.end
        if period.start > covered_to + timedelta(days=1):
            gaps.append(DateRange(covered_to + timedelta(days=1), period.start - timedelta(days=1)))
        elif period.start <= covered_to:
            overlaps.append(
                Overlap(
                    DateRange(period.start, min(period.end, covered_to)),
                    (reaching.number, invoice.number),
                )
            )
        if period.end > covered_to:
            reaching = invoice
    return InvoiceTimeline(
        periods=tuple(_timeline_period(i, costs) for i in invoices),
        gaps=tuple(gaps),
        overlaps=tuple(overlaps),
        estimated_months=_estimated_months(invoices, counted, today),
        debit_notes=tuple(
            sorted(
                (_note(note, costs) for note in costs.debit_notes),
                key=lambda n: (n.sale_date, n.number),
            )
        ),
        forecasts=tuple(
            f
            for f in current_forecasts(invoices)
            if f.period.end > reaching.header.billing_period.end
        ),
    )
