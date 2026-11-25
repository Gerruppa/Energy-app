"""Koszty i Faktury: czyste analizy na ``Repository``."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from pv_app.domain.invoice import (
    DateRange,
    DocumentKind,
    InvoiceLine,
    LineComponent,
    SettlementBasis,
    Source,
)
from pv_app.domain.period_cost import PeriodCosts
from pv_app.domain.view_period import first_day, last_day
from pv_app.features.base import Filters
from pv_app.features.monthly import (
    History,
    PeriodTotals,
    invoice_months,
    months_of,
)
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

    @property
    def average_price(self) -> Decimal | None:
        """Cena średnia kWh: Koszt okresu ÷ Energia pobrana; ``None`` przy zerowej Energii
        pobranej."""
        return self.period_cost / self.imported_kwh if self.imported_kwh else None


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


@dataclass(frozen=True)
class CostSummary:
    """Koszt okresu w Okresie widoku i ten sam okres rok wcześniej."""

    current: PeriodTotals
    year_earlier: PeriodTotals | None
    """``None`` dla całego okresu albo gdy Faktury nie obejmują któregoś miesiąca rok wcześniej."""
    missing_months: tuple[int, ...]
    """Miesiące Okresu widoku bez pełnego pokrycia Fakturami; nie wchodzą do sum."""
    excise: Decimal | None
    """Akcyza z Faktur (tylko informacyjnie: jest już w cenach Pozycji faktury); część dłuższej
    Faktury po dniach; ``None``, gdy żadna Faktura jej nie podaje."""


def cost_summary(repository: Repository, filters: Filters) -> CostSummary | None:
    """Koszt okresu, Cena średnia kWh i rok wcześniej; ``None``, gdy żaden miesiąc Okresu widoku
    nie jest objęty Fakturami w całości."""
    history = History(repository, filters.ppe_number)
    if not history.invoices:
        return None
    dates = filters.view_period.dates
    if dates is None:
        first, last = invoice_months(history)
        months = range(first, last + 1)
    else:
        months = months_of(dates)
    comparison = history.compare(months, with_year_earlier=dates is not None)
    if comparison is None:
        return None
    current, earlier, missing = comparison
    return CostSummary(
        current=current,
        year_earlier=earlier,
        missing_months=missing,
        excise=_excise(history, current),
    )


def _excise(history: History, totals: PeriodTotals) -> Decimal | None:
    """Akcyza Faktur z ``totals``: z każdej Faktury część jej dni leżących w miesiącach sum."""
    amounts = []
    for ref in totals.invoices:
        excise = history.invoice(ref.number).summary.excise_amount
        if excise is None:
            continue
        days = sum(
            max(
                0, (min(ref.period.end, last_day(m)) - max(ref.period.start, first_day(m))).days + 1
            )
            for m in totals.months
        )
        amounts.append(excise * days / ref.period.days)
    if not amounts:
        return None
    return sum(amounts, Decimal(0)).quantize(Decimal("0.01"))


def _overlaps(period: DateRange, filters: Filters) -> bool:
    dates = filters.view_period.dates
    return dates is None or dates.overlaps(period)


@dataclass(frozen=True)
class UnitPrice:
    """Cena jednostkowa netto jednego składnika w jednym podokresie Faktury."""

    invoice_number: str
    period: DateRange
    """Okres rozliczeniowy Faktury."""
    sub_period: int
    sub_periods: int
    """Ile podokresów z tym składnikiem ma Faktura; daty podokresów nie są na Fakturze."""
    price_net: Decimal
    source: Source


@dataclass(frozen=True)
class UnitPriceSeries:
    """Cena jednego składnika (w jednej strefie) Faktura po Fakturze."""

    component: LineComponent
    zone: str | None
    unit: str
    """``kWh`` (cena za kWh) albo ``mc`` (opłata za miesiąc)."""
    prices: tuple[UnitPrice, ...]


def unit_price_history(repository: Repository, filters: Filters) -> list[UnitPriceSeries]:
    """Ceny jednostkowe z Pozycji faktury wszystkich niezastąpionych Faktur PPE, od najstarszej;
    seria na składnik, strefę i jednostkę w kolejności składników z ``LineComponent``."""
    history = History(repository, filters.ppe_number)
    invoices = sorted(history.invoices, key=lambda i: i.header.billing_period.start)
    series: dict[tuple[LineComponent, str | None, str], list[UnitPrice]] = {}
    for invoice in invoices:
        found: dict[tuple[LineComponent, str | None, str], dict[int, InvoiceLine]] = {}
        for line in invoice.lines:
            if line.component is not None:
                key = (line.component, line.zone, line.unit)
                found.setdefault(key, {}).setdefault(line.sub_period, line)
        for key, by_sub_period in found.items():
            series.setdefault(key, []).extend(
                UnitPrice(
                    invoice_number=invoice.number,
                    period=invoice.header.billing_period,
                    sub_period=sub_period,
                    sub_periods=len(by_sub_period),
                    price_net=line.unit_price_net,
                    source=line.source,
                )
                for sub_period, line in sorted(by_sub_period.items())
            )
    order = list(LineComponent)
    return [
        UnitPriceSeries(component, zone, unit, tuple(prices))
        for (component, zone, unit), prices in sorted(
            series.items(), key=lambda item: (order.index(item[0][0]), item[0][1] or "", item[0][2])
        )
    ]
