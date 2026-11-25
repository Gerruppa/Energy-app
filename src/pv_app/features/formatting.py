"""Liczby i daty na ekranie, po polsku."""

from datetime import date

from pv_app.domain.formatting import decimal_pl, kwh, zl
from pv_app.domain.invoice import DateRange, SettlementBasis, Source
from pv_app.domain.view_period import calendar_month, month_label

__all__ = [
    "BASIS_BADGES",
    "day",
    "decimal_pl",
    "during",
    "for_period",
    "in_month",
    "kwh",
    "period",
    "source",
    "zl",
]

BASIS_BADGES = {
    SettlementBasis.ACTUAL_READING: "🟢 odczyt rzeczywisty",
    SettlementBasis.ESTIMATED_READING: "🟡 odczyt szacunkowy",
    SettlementBasis.FORECAST: "⚪ Prognoza",
}


def day(value: date) -> str:
    return value.strftime("%d.%m.%Y")


def period(value: DateRange) -> str:
    return f"{day(value.start)} – {day(value.end)}"


def source(value: Source) -> str:
    return f"Faktura {value.invoice_number}, str. {value.page}"


_MONTHS_LOCATIVE = (
    "styczniu",
    "lutym",
    "marcu",
    "kwietniu",
    "maju",
    "czerwcu",
    "lipcu",
    "sierpniu",
    "wrześniu",
    "październiku",
    "listopadzie",
    "grudniu",
)


def in_month(index: int) -> str:
    """„w październiku 2026” dla ``month_index``."""
    return f"w {_MONTHS_LOCATIVE[index % 12]} {index // 12}"


def for_period(value: DateRange) -> str:
    """„za październik 2026” dla miesiąca kalendarzowego, inaczej „za 01.03.2026 – 31.08.2026”."""
    month = calendar_month(value)
    return f"za {month_label(month)}" if month is not None else f"za {period(value)}"


def during(value: DateRange) -> str:
    """„w październiku 2026” dla miesiąca kalendarzowego, inaczej „w okresie 01.03.2026 – …”."""
    month = calendar_month(value)
    return in_month(month) if month is not None else f"w okresie {period(value)}"
