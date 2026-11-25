"""Liczby po polsku (``1 234,56 zł``), wspólne dla komunikatów domeny i ekranów."""

from decimal import Decimal


def decimal_pl(value: Decimal) -> str:
    """Liczba bez zbędnych zer, z przecinkiem: ``0,8``, ``13``."""
    return f"{value.normalize():f}".replace(".", ",")


def _grouped(value: Decimal, decimals: int) -> str:
    return f"{value:,.{decimals}f}".replace(",", " ").replace(".", ",")


def zl(value: Decimal) -> str:
    return f"{_grouped(value, 2)} zł"


def kwh(value: Decimal, decimals: int = 0) -> str:
    return f"{_grouped(value, decimals)} kWh"
