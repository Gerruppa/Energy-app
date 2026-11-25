"""Niezastąpione Faktury PPE rozłożone na miesiące: sumy Okresu widoku, rok do roku i wykres
miesiąc po miesiącu. Wspólne dla zakładek (Przegląd, Koszty i Faktury); czyste analizy na
``Repository``."""

import calendar
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from pv_app.domain.cost_groups import CostGroup
from pv_app.domain.invoice import DateRange, Forecast, Invoice, Source
from pv_app.domain.monthly_split import MonthShare, split_into_months
from pv_app.domain.period_cost import PeriodCosts
from pv_app.domain.view_period import first_day, last_day, month_index
from pv_app.features.base import Filters
from pv_app.storage.repository import Repository


@dataclass(frozen=True)
class InvoiceRef:
    """Faktura, z której pochodzą liczby Okresu widoku."""

    number: str
    period: DateRange
    """Okres rozliczeniowy."""
    energy_source: Source
    """Strona z Energią pobraną i oddaną."""
    cost_source: Source
    """Strona z Wynikiem rozliczenia (Koszt okresu)."""
    part_of_longer: bool
    """Faktura rozlicza dłuższy okres niż Okres widoku, więc liczby pochodzą z rozkładu."""


@dataclass(frozen=True)
class PeriodTotals:
    """Sumy części Faktur (rozkład na miesiące) za wybrane miesiące."""

    months: tuple[int, ...]
    """Miesiące (``month_index``), których dotyczą sumy."""
    imported_kwh: Decimal
    exported_kwh: Decimal | None
    stored_kwh: Decimal | None
    """Przyrost Magazynu energii z Faktur (Energia oddana × Współczynnik opustu)."""
    period_cost: Decimal
    invoices: tuple[InvoiceRef, ...]
    cost_groups: Mapping[CostGroup, Decimal] = field(default_factory=dict)
    """Grupy kosztów z rozkładu na miesiące: pięć grup (i Pozycje nierozpoznane, gdy są)."""

    @property
    def discounts(self) -> Decimal:
        """Koszt okresu minus Grupy kosztów: Bonifikaty (ujemne) i groszowe zaokrąglenia VAT."""
        return self.period_cost - sum(self.cost_groups.values(), Decimal(0))

    @property
    def approximate(self) -> bool:
        """Choć część liczb pochodzi z rozkładu dłuższej Faktury (≈)."""
        return any(ref.part_of_longer for ref in self.invoices)

    @property
    def average_price(self) -> Decimal | None:
        """Cena średnia kWh: Koszt okresu ÷ Energia pobrana; ``None`` przy zerowej Energii
        pobranej."""
        return self.period_cost / self.imported_kwh if self.imported_kwh else None


@dataclass(frozen=True)
class YearOverYear:
    """Ten Okres widoku a ten sam okres rok wcześniej."""

    current: PeriodTotals
    year_earlier: PeriodTotals | None
    """Z własnej historii; ``None``, gdy brak Faktur za któryś miesiąc rok wcześniej."""
    missing_months: tuple[int, ...]
    """Miesiące Okresu widoku bez pełnego pokrycia Fakturami; nie wchodzą do porównania."""
    tauron_last_year_kwh: Decimal | None = None
    """Energia pobrana w „analogicznym okresie” według Faktur za ten Okres widoku."""
    tauron_sources: tuple[Source, ...] = ()

    @property
    def tauron_differs(self) -> bool:
        """Wartość Taurona różni się od własnej historii o więcej niż 5%."""
        if self.tauron_last_year_kwh is None or self.year_earlier is None:
            return False
        own = self.year_earlier.imported_kwh
        if own == 0:
            return self.tauron_last_year_kwh != 0
        return abs(self.tauron_last_year_kwh - own) / own > TAURON_CHECK_TOLERANCE


TAURON_CHECK_TOLERANCE = Decimal("0.05")


class History:
    """Niezastąpione Faktury PPE rozłożone na miesiące."""

    def __init__(self, repository: Repository, ppe_number: str) -> None:
        costs = PeriodCosts(
            invoices=repository.list_invoices(ppe_number),
            debit_notes=repository.list_debit_notes(ppe_number),
        )
        superseded = costs.superseded_invoices
        self.invoices = [i for i in costs.invoices if i.number not in superseded]
        self._by_number = {i.number: i for i in self.invoices}
        self._period_costs = {i.number: costs.period_cost(i) for i in self.invoices}
        self.shares: list[MonthShare] = [
            share
            for invoice in self.invoices
            for share in split_into_months(invoice, self.period_cost(invoice))
        ]

    def invoice(self, number: str) -> Invoice:
        return self._by_number[number]

    def period_cost(self, invoice: Invoice) -> Decimal:
        """Koszt okresu Faktury, z Bonifikatami z Not obciążeniowych."""
        return self._period_costs[invoice.number]

    def compare(
        self, months: Iterable[int], with_year_earlier: bool = True
    ) -> tuple[PeriodTotals, PeriodTotals | None, tuple[int, ...]] | None:
        """Sumy miesięcy objętych Fakturami w całości, te same miesiące rok wcześniej (``None``,
        gdy któregoś brakuje albo bez ``with_year_earlier``) i miesiące pominięte; ``None``, gdy
        żaden miesiąc nie jest objęty."""
        wanted = list(months)
        covered = [m for m in wanted if self.covered(m)]
        if not covered:
            return None
        earlier_months = [m - 12 for m in covered]
        earlier = (
            self.totals(earlier_months)
            if with_year_earlier and all(self.covered(m) for m in earlier_months)
            else None
        )
        missing = tuple(m for m in wanted if m not in covered)
        return self.totals(covered), earlier, missing

    def covered(self, month: int) -> bool:
        """Faktury obejmują każdy dzień miesiąca."""
        days = sum(s.days for s in self.shares if s.month == month)
        start = first_day(month)
        return days >= calendar.monthrange(start.year, start.month)[1]

    def totals(self, months: Iterable[int]) -> PeriodTotals:
        """Sumy za niepuste ``months``."""
        wanted = tuple(sorted(months))
        shares = [s for s in self.shares if s.month in wanted]
        exported = [s.exported_kwh for s in shares if s.exported_kwh is not None]
        stored = [s.stored_kwh for s in shares if s.stored_kwh is not None]
        dates = DateRange(first_day(wanted[0]), last_day(wanted[-1]))
        refs = []
        for number in dict.fromkeys(s.invoice_number for s in shares):
            invoice = self.invoice(number)
            period = invoice.header.billing_period
            refs.append(
                InvoiceRef(
                    number=number,
                    period=period,
                    energy_source=invoice.energy_source,
                    cost_source=invoice.summary.source,
                    part_of_longer=not dates.contains(period),
                )
            )
        return PeriodTotals(
            months=wanted,
            imported_kwh=sum((s.imported_kwh for s in shares), Decimal(0)),
            exported_kwh=sum(exported, Decimal(0)) if exported else None,
            stored_kwh=sum(stored, Decimal(0)) if stored else None,
            period_cost=sum((s.period_cost for s in shares), Decimal(0)),
            invoices=tuple(refs),
            cost_groups=_sum_groups(shares),
        )


def _sum_groups(shares: Iterable[MonthShare]) -> dict[CostGroup, Decimal]:
    totals: dict[CostGroup, Decimal] = {}
    for share in shares:
        for group, value in share.cost_groups.items():
            totals[group] = totals.get(group, Decimal(0)) + value
    return totals


def months_of(dates: DateRange) -> range:
    return range(month_index(dates.start), month_index(dates.end) + 1)


def year_over_year(repository: Repository, filters: Filters) -> YearOverYear | None:
    """Porównanie z tym samym okresem rok wcześniej; ``None`` dla całego okresu albo gdy
    w Okresie widoku nie ma żadnej Faktury."""
    dates = filters.view_period.dates
    if dates is None:
        return None
    history = History(repository, filters.ppe_number)
    comparison = history.compare(months_of(dates))
    if comparison is None:
        return None
    current, earlier, missing = comparison
    tauron_kwh, tauron_sources = _tauron_last_year(history.invoices, dates)
    return YearOverYear(
        current=current,
        year_earlier=earlier,
        missing_months=missing,
        tauron_last_year_kwh=tauron_kwh,
        tauron_sources=tauron_sources,
    )


def _tauron_last_year(
    invoices: Iterable[Invoice], dates: DateRange
) -> tuple[Decimal | None, tuple[Source, ...]]:
    """Suma „analogicznego okresu” z Faktur, gdy ich Okresy rozliczeniowe pokrywają dokładnie
    Okres widoku (np. miesiąc z własną Fakturą); inaczej wartość Taurona dotyczy innego okresu."""
    inside = [i for i in invoices if dates.contains(i.header.billing_period)]
    if not inside or sum(i.header.billing_period.days for i in inside) != dates.days:
        return None, ()
    values = [i.summary.same_period_last_year_kwh for i in inside]
    sources = [i.summary.same_period_last_year_source for i in inside]
    if any(v is None for v in values) or any(s is None for s in sources):
        return None, ()
    return (
        sum((v for v in values if v is not None), Decimal(0)),
        tuple(s for s in sources if s is not None),
    )


AVERAGE_MONTH_DAYS = Decimal("30.44")
"""Średnia długość miesiąca: średnia miesięczna Faktury = suma / dni × 30,44."""


def per_month(total: Decimal, period: DateRange, single_month: bool) -> Decimal:
    """Wysokość na wykresie: suma dla miesiąca z własną Fakturą, inaczej średnia miesięczna."""
    return total if single_month else total / period.days * AVERAGE_MONTH_DAYS


@dataclass(frozen=True)
class ChartBlock:
    """Faktura na wykresie miesiąc po miesiącu (kWh i Koszt okresu): słupek (miesiąc z własną
    Fakturą) albo płaski blok przez cały Okres rozliczeniowy na wysokości średniej miesięcznej."""

    invoice_number: str
    period: DateRange
    """Okres rozliczeniowy."""
    drawn: DateRange
    """Gdzie rysować: Okres rozliczeniowy, a dla roku wcześniej przesunięty o 12 miesięcy."""
    imported_kwh: Decimal
    exported_kwh: Decimal | None
    imported_per_month: Decimal
    exported_per_month: Decimal | None
    single_month: bool
    source: Source
    """Strona z Energią pobraną i oddaną."""
    period_cost: Decimal
    cost_per_month: Decimal
    cost_source: Source
    """Strona z Wynikiem rozliczenia (Koszt okresu)."""


@dataclass(frozen=True)
class MonthlyChart:
    months: tuple[int, ...]
    """Miesiące na osi (``month_index``)."""
    selected: tuple[int, ...]
    """Miesiące Okresu widoku, wyróżnione na wykresie."""
    blocks: tuple[ChartBlock, ...]
    year_earlier: tuple[ChartBlock, ...]
    """Kontur: Faktury sprzed roku przesunięte o 12 miesięcy."""
    missing_months: tuple[int, ...]
    """Luki: miesiące bez żadnej Faktury między pierwszą a ostatnią Fakturą (znacznik „?”)."""


def _year_later(day: date) -> date:
    try:
        return day.replace(year=day.year + 1)
    except ValueError:  # 29 lutego
        return day.replace(year=day.year + 1, day=28)


def _block(invoice: Invoice, period_cost: Decimal, year_earlier: bool) -> ChartBlock:
    period = invoice.header.billing_period
    single = month_index(period.start) == month_index(period.end)

    def block_per_month(total: Decimal) -> Decimal:
        return per_month(total, period, single)

    exported = invoice.exported_kwh
    return ChartBlock(
        invoice_number=invoice.number,
        period=period,
        drawn=DateRange(_year_later(period.start), _year_later(period.end))
        if year_earlier
        else period,
        imported_kwh=invoice.imported_kwh,
        exported_kwh=exported,
        imported_per_month=block_per_month(invoice.imported_kwh),
        exported_per_month=block_per_month(exported) if exported is not None else None,
        single_month=single,
        source=invoice.energy_source,
        period_cost=period_cost,
        cost_per_month=block_per_month(period_cost),
        cost_source=invoice.summary.source,
    )


def monthly_chart(repository: Repository, filters: Filters) -> MonthlyChart | None:
    """Bloki Faktur miesiąc po miesiącu (kWh i Koszt okresu) z rokiem wcześniej; ``None`` bez
    Faktur. Rysują go wykres energii w Przeglądzie i „Koszt miesięcznie” w Kosztach.

    Okno: miesiąc i kwartał w 12 miesiącach kończących się na Okresie widoku, rok jako swoje
    12 miesięcy, cały okres od pierwszej do ostatniej Faktury."""
    history = History(repository, filters.ppe_number)
    if not history.invoices:
        return None
    first, last = invoice_months(history)
    dates = filters.view_period.dates
    if dates is None:
        months = range(first, last + 1)
        selected = months
    else:
        selected = months_of(dates)
        months = range(min(selected[0], selected[-1] - 11), selected[-1] + 1)
    return build_chart(history, months, selected, with_year_earlier=True)


def invoice_months(history: History) -> tuple[int, int]:
    """Pierwszy i ostatni miesiąc objęty Fakturami."""
    first = min(month_index(i.header.billing_period.start) for i in history.invoices)
    last = max(month_index(i.header.billing_period.end) for i in history.invoices)
    return first, last


def build_chart(
    history: History, months: range, selected: range, *, with_year_earlier: bool
) -> MonthlyChart:
    first, last = invoice_months(history)
    window = DateRange(first_day(months[0]), last_day(months[-1]))

    def visible(block: ChartBlock) -> bool:
        return window.overlaps(block.drawn)

    blocks = [_block(i, history.period_cost(i), year_earlier=False) for i in history.invoices]
    earlier = (
        [_block(i, history.period_cost(i), year_earlier=True) for i in history.invoices]
        if with_year_earlier
        else []
    )
    with_invoice = {s.month for s in history.shares}
    return MonthlyChart(
        months=tuple(months),
        selected=tuple(selected),
        blocks=tuple(b for b in blocks if visible(b)),
        year_earlier=tuple(b for b in earlier if visible(b)),
        missing_months=tuple(m for m in months if first <= m <= last and m not in with_invoice),
    )


@dataclass(frozen=True)
class ForecastLine:
    """Prognoza z harmonogramu jako przerywana linia na wysokości średniej miesięcznej."""

    forecast_number: str
    invoice_number: str
    """Faktura, której harmonogram zawiera tę Prognozę."""
    period: DateRange
    import_kwh: Decimal
    per_month: Decimal
    single_month: bool
    gross: Decimal
    due_date: date
    source: Source


def _forecast_line(invoice: Invoice, forecast: Forecast) -> ForecastLine:
    period = forecast.period
    single = month_index(period.start) == month_index(period.end)
    average = per_month(forecast.import_kwh, period, single)
    return ForecastLine(
        forecast_number=forecast.number,
        invoice_number=invoice.number,
        period=period,
        import_kwh=forecast.import_kwh,
        per_month=average,
        single_month=single,
        gross=forecast.gross,
        due_date=forecast.due_date,
        source=forecast.source,
    )


def current_forecasts(invoices: list[Invoice]) -> list[ForecastLine]:
    """Prognozy z harmonogramów; Prognozę zastępuje Prognoza na ten sam czas z później
    wystawionej Faktury (nowszy harmonogram)."""
    lines = []
    for invoice in invoices:
        newer = [i for i in invoices if i.header.issue_date > invoice.header.issue_date]
        for forecast in invoice.forecasts:
            replaced = any(forecast.period.overlaps(f.period) for i in newer for f in i.forecasts)
            if not replaced:
                lines.append(_forecast_line(invoice, forecast))
    return sorted(lines, key=lambda line: line.period.start)
