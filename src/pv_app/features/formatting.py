"""Liczby i daty na ekranie, po polsku."""

from datetime import date

from pv_app.domain.formatting import decimal_pl, kwh, zl
from pv_app.domain.invoice import DateRange, SettlementBasis, Source

__all__ = ["BASIS_BADGES", "day", "decimal_pl", "kwh", "period", "source", "zl"]

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
