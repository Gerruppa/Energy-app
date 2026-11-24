"""Widok Faktury („Faktura po ludzku”): czyste analizy na ``Repository``."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum

from pv_app.domain.debit_note import DebitNote
from pv_app.domain.invoice import DateRange, Invoice, InvoiceLine, LineComponent, Source
from pv_app.domain.monthly_split import split_into_months
from pv_app.domain.period_cost import PeriodCosts
from pv_app.domain.view_period import ViewPeriod, ViewPeriodKind, first_day, last_day
from pv_app.storage.repository import Repository, SourceFile


class CostGroup(StrEnum):
    """Grupa kosztów: Pozycje faktury zebrane tak, jak opisuje je „Faktura po ludzku”."""

    ENERGY = "Energia"
    VARIABLE_DISTRIBUTION = "Dystrybucja zmienna"
    PER_KWH_FEES = "Opłaty od kWh"
    CAPACITY = "Opłata mocowa"
    FIXED_FEES = "Opłaty stałe"
    UNRECOGNIZED = "Pozycje nierozpoznane"
    """Tylko gdy import nie rozpoznał nazwy którejś Pozycji faktury."""


_GROUP_OF_COMPONENT = {
    LineComponent.ACTIVE_ENERGY: CostGroup.ENERGY,
    LineComponent.VARIABLE_NETWORK: CostGroup.VARIABLE_DISTRIBUTION,
    LineComponent.QUALITY: CostGroup.VARIABLE_DISTRIBUTION,
    LineComponent.OZE: CostGroup.PER_KWH_FEES,
    LineComponent.COGENERATION: CostGroup.PER_KWH_FEES,
    LineComponent.CAPACITY: CostGroup.CAPACITY,
    LineComponent.FIXED_NETWORK: CostGroup.FIXED_FEES,
    LineComponent.TRANSITIONAL: CostGroup.FIXED_FEES,
    LineComponent.SUBSCRIPTION: CostGroup.FIXED_FEES,
}


def cost_group(line: InvoiceLine) -> CostGroup:
    if line.component is None:
        return CostGroup.UNRECOGNIZED
    return _GROUP_OF_COMPONENT[line.component]


@dataclass(frozen=True)
class CostGroupTotal:
    group: CostGroup
    gross: Decimal
    """Suma brutto Pozycji faktury tej grupy."""
    lines: tuple[InvoiceLine, ...]
    """Pozycje faktury w kolejności z Faktury."""


@dataclass(frozen=True)
class YearEarlier:
    """Ten sam Okres rozliczeniowy rok wcześniej: z własnych Faktur i według Taurona."""

    period: DateRange
    imported_kwh: Decimal | None
    """Energia pobrana z własnych Faktur; ``None``, gdy nie pokrywają całego okresu."""
    exported_kwh: Decimal | None
    period_cost: Decimal | None
    invoice_numbers: tuple[str, ...]
    """Faktury, z których wyliczono liczby."""
    approximate: bool
    """Liczby wycięte z dłuższej Faktury (rozkład na miesiące), oznaczone ≈."""
    tauron_imported_kwh: Decimal | None
    """Energia pobrana w „analogicznym okresie” według tej Faktury."""
    tauron_source: Source | None


@dataclass(frozen=True)
class InvoiceSheet:
    """Wszystko, co pokazuje strona jednej Faktury i jej wydruk."""

    invoice: Invoice
    cost_groups: tuple[CostGroupTotal, ...]
    """Pięć grup kosztów w stałej kolejności (także puste), plus pozycje nierozpoznane."""
    period_cost: Decimal
    """Koszt okresu: po Bonifikacie z Faktury i z Not obciążeniowych za ten okres."""
    average_price: Decimal | None
    """Cena średnia kWh; ``None``, gdy Energia pobrana jest zerowa."""
    debit_notes: tuple[DebitNote, ...]
    """Noty obciążeniowe, których bonifikaty pomniejszają Koszt okresu."""
    superseded_by: str | None
    """Faktura korygująca, która zastępuje tę Fakturę w obliczeniach."""
    previous_number: str | None
    """Faktura PPE z poprzednim Okresem rozliczeniowym (strzałka „poprzednia Faktura”)."""
    next_number: str | None
    year_earlier: YearEarlier
    overview_period: ViewPeriod
    """Okres widoku dla „pokaż ten okres w Przeglądzie”: najmniejszy miesiąc, kwartał albo rok
    obejmujący Okres rozliczeniowy, a gdy żaden go nie obejmuje, cały okres."""
    source_file: SourceFile | None
    """Wgrany PDF w archiwum (``FileArchive``); ``None`` dla Faktury dodanej bez pliku."""


def _cost_groups(invoice: Invoice) -> tuple[CostGroupTotal, ...]:
    groups = []
    for group in CostGroup:
        lines = tuple(x for x in invoice.lines if cost_group(x) is group)
        if group is CostGroup.UNRECOGNIZED and not lines:
            continue
        groups.append(CostGroupTotal(group, sum((x.gross for x in lines), Decimal("0.00")), lines))
    return tuple(groups)


def _year_before(day: date) -> date:
    try:
        return day.replace(year=day.year - 1)
    except ValueError:  # 29 lutego
        return day.replace(year=day.year - 1, day=28)


_KWH = Decimal("0.001")
_ZL = Decimal("0.01")


def _common_days(a: DateRange, b: DateRange) -> int:
    return max(0, (min(a.end, b.end) - max(a.start, b.start)).days + 1)


@dataclass(frozen=True)
class _Part:
    """Część Faktury przypadająca na zadany zakres dat."""

    imported_kwh: Decimal
    exported_kwh: Decimal | None
    period_cost: Decimal
    approximate: bool


def _part(invoice: Invoice, period_cost: Decimal, dates: DateRange) -> _Part:
    """Cała Faktura, gdy leży w ``dates``; inaczej z rozkładu na miesiące, a w miesiącu
    przeciętym granicą ``dates`` proporcjonalnie do dni."""
    period = invoice.header.billing_period
    if dates.contains(period):
        return _Part(invoice.imported_kwh, invoice.exported_kwh, period_cost, False)
    imported = exported = cost = Decimal(0)
    for share in split_into_months(invoice, period_cost):
        month = DateRange(first_day(share.month), last_day(share.month))
        common = _common_days(
            DateRange(max(period.start, month.start), min(period.end, month.end)), dates
        )
        if not common:
            continue
        fraction = Decimal(common) / share.days
        imported += share.imported_kwh * fraction
        exported += (share.exported_kwh or Decimal(0)) * fraction
        cost += share.period_cost * fraction
    return _Part(
        imported_kwh=imported.quantize(_KWH),
        exported_kwh=exported.quantize(_KWH) if invoice.exported_kwh is not None else None,
        period_cost=cost.quantize(_ZL),
        approximate=True,
    )


def _covered_days(invoices: list[Invoice], dates: DateRange) -> int:
    """Dni ``dates`` objęte choć jedną Fakturą (nakładające się Faktury liczone raz)."""
    days: set[int] = set()
    for invoice in invoices:
        period = invoice.header.billing_period
        first = max(period.start, dates.start).toordinal()
        last = min(period.end, dates.end).toordinal()
        days.update(range(first, last + 1))
    return len(days)


def _year_earlier(invoice: Invoice, costs: PeriodCosts) -> YearEarlier:
    """Ten sam Okres rozliczeniowy rok wcześniej; z własnych Faktur tylko, gdy pokrywają go
    w całości."""
    period = invoice.header.billing_period
    earlier = DateRange(_year_before(period.start), _year_before(period.end))
    superseded = costs.superseded_invoices
    found = [
        i
        for i in costs.invoices
        if i.number not in superseded
        and i.number != invoice.number
        and i.header.billing_period.overlaps(earlier)
    ]
    parts = [_part(i, costs.period_cost(i), earlier) for i in found]
    summary = invoice.summary
    tauron = (summary.same_period_last_year_kwh, summary.same_period_last_year_source)
    if not parts or _covered_days(found, earlier) < earlier.days:
        return YearEarlier(earlier, None, None, None, (), False, *tauron)
    exported = [p.exported_kwh for p in parts if p.exported_kwh is not None]
    return YearEarlier(
        period=earlier,
        imported_kwh=sum((p.imported_kwh for p in parts), Decimal(0)),
        exported_kwh=sum(exported, Decimal(0)) if exported else None,
        period_cost=sum((p.period_cost for p in parts), Decimal(0)),
        invoice_numbers=tuple(i.number for i in found),
        approximate=any(p.approximate for p in parts),
        tauron_imported_kwh=tauron[0],
        tauron_source=tauron[1],
    )


def _overview_period(period: DateRange) -> ViewPeriod:
    for kind in (ViewPeriodKind.MONTH, ViewPeriodKind.QUARTER, ViewPeriodKind.YEAR):
        candidate = ViewPeriod.containing(kind, period.start)
        dates = candidate.dates
        if dates is not None and dates.contains(period):
            return candidate
    return ViewPeriod.whole()


def invoice_sheet(
    repository: Repository, ppe_number: str, invoice_number: str
) -> InvoiceSheet | None:
    """„Faktura po ludzku” dla Faktury PPE; ``None``, gdy PPE nie ma Faktury o tym numerze."""
    costs = PeriodCosts(
        invoices=repository.list_invoices(ppe_number),
        debit_notes=repository.list_debit_notes(ppe_number),
    )
    ordered = sorted(
        costs.invoices, key=lambda i: (i.header.billing_period.start, i.header.issue_date, i.number)
    )
    position = next((n for n, i in enumerate(ordered) if i.number == invoice_number), None)
    if position is None:
        return None
    invoice = ordered[position]
    period_cost = costs.period_cost(invoice)
    imported = invoice.imported_kwh
    return InvoiceSheet(
        invoice=invoice,
        cost_groups=_cost_groups(invoice),
        period_cost=period_cost,
        average_price=period_cost / imported if imported else None,
        debit_notes=tuple(costs.debit_notes_for(invoice)),
        superseded_by=costs.superseded_invoices.get(invoice.number),
        previous_number=ordered[position - 1].number if position > 0 else None,
        next_number=ordered[position + 1].number if position + 1 < len(ordered) else None,
        year_earlier=_year_earlier(invoice, costs),
        overview_period=_overview_period(invoice.header.billing_period),
        source_file=repository.find_source_file_for(invoice.number),
    )
