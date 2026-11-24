"""Rozkład Faktury na miesiące kalendarzowe.

kWh i Składniki zmienne proporcjonalnie do dni, Składniki stałe po równo na miesiące okresu.
Reszta Kosztu okresu (zaokrąglenia VAT, Bonifikaty) proporcjonalnie do dni. Części są
zaokrąglone (kWh do 0,001, zł do 0,01), a ostatni miesiąc dostaje resztę, więc suma
części równa się wartości z Faktury.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from pv_app.domain.invoice import Invoice
from pv_app.domain.view_period import first_day, last_day, month_index

_KWH = Decimal("0.001")
_ZL = Decimal("0.01")


@dataclass(frozen=True)
class MonthShare:
    """Część Faktury przypadająca na jeden miesiąc kalendarzowy."""

    month: int
    """``month_index`` miesiąca."""
    days: int
    """Dni Okresu rozliczeniowego w tym miesiącu."""
    imported_kwh: Decimal
    exported_kwh: Decimal | None
    variable_cost: Decimal
    """Składniki zmienne brutto."""
    fixed_cost: Decimal
    """Składniki stałe brutto."""
    period_cost: Decimal
    """Część Kosztu okresu."""
    invoice_number: str
    whole_invoice: bool
    """Faktura rozlicza tylko ten miesiąc (wartości dokładne, nie z rozkładu)."""


def _split(total: Decimal, weights: Sequence[int], step: Decimal) -> list[Decimal]:
    parts = [(total * w / sum(weights)).quantize(step) for w in weights[:-1]]
    return [*parts, total - sum(parts, Decimal(0))]


def _days_per_month(start: date, end: date) -> list[tuple[int, int]]:
    result = []
    for index in range(month_index(start), month_index(end) + 1):
        first = max(start, first_day(index))
        last = min(end, last_day(index))
        result.append((index, (last - first).days + 1))
    return result


def split_into_months(invoice: Invoice, period_cost: Decimal) -> list[MonthShare]:
    """Części Faktury na miesiące jej Okresu rozliczeniowego; ``period_cost`` to Koszt okresu
    (z Bonifikatami z Not obciążeniowych, ``PeriodCosts.period_cost``)."""
    period = invoice.header.billing_period
    months = _days_per_month(period.start, period.end)
    days = [d for _, d in months]
    variable = sum(
        (x.gross for x in invoice.lines if x.component is not None and x.component.is_variable),
        Decimal(0),
    )
    fixed = sum(
        (x.gross for x in invoice.lines if x.component is not None and not x.component.is_variable),
        Decimal(0),
    )
    rest = period_cost - variable - fixed
    imported = _split(invoice.imported_kwh, days, _KWH)
    exported = (
        _split(invoice.exported_kwh, days, _KWH)
        if invoice.exported_kwh is not None
        else [None] * len(days)
    )
    variable_parts = _split(variable, days, _ZL)
    fixed_parts = _split(fixed, [1] * len(days), _ZL)
    rest_parts = _split(rest, days, _ZL)
    return [
        MonthShare(
            month=index,
            days=d,
            imported_kwh=imported[i],
            exported_kwh=exported[i],
            variable_cost=variable_parts[i],
            fixed_cost=fixed_parts[i],
            period_cost=variable_parts[i] + fixed_parts[i] + rest_parts[i],
            invoice_number=invoice.number,
            whole_invoice=len(months) == 1,
        )
        for i, (index, d) in enumerate(months)
    ]
