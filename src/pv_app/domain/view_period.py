"""Okres widoku: cały okres, rok, kwartał albo miesiąc; zapisywany w adresie strony.

Wartość w adresie: ``caly``, ``2026``, ``2026-K4`` (kwartał), ``2026-10`` (miesiąc).
"""

import calendar
import re
from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from pv_app.domain.invoice import DateRange


class ViewPeriodKind(StrEnum):
    WHOLE = "Cały okres"
    YEAR = "Rok"
    QUARTER = "Kwartał"
    MONTH = "Miesiąc"


_MONTHS_PER_KIND = {ViewPeriodKind.YEAR: 12, ViewPeriodKind.QUARTER: 3, ViewPeriodKind.MONTH: 1}
_WHOLE_QUERY = "caly"
MONTH_NAMES = (
    "styczeń",
    "luty",
    "marzec",
    "kwiecień",
    "maj",
    "czerwiec",
    "lipiec",
    "sierpień",
    "wrzesień",
    "październik",
    "listopad",
    "grudzień",
)
_QUARTER_NUMERALS = ("I", "II", "III", "IV")


def month_index(day: date) -> int:
    """Numer miesiąca liczony od roku 0, do przesuwania o miesiące."""
    return day.year * 12 + day.month - 1


def first_day(index: int) -> date:
    return date(index // 12, index % 12 + 1, 1)


def last_day(index: int) -> date:
    start = first_day(index)
    return date(start.year, start.month, calendar.monthrange(start.year, start.month)[1])


def month_label(index: int) -> str:
    """Miesiąc po polsku: ``maj 2026``."""
    return f"{MONTH_NAMES[index % 12]} {index // 12}"


@dataclass(frozen=True)
class ViewPeriod:
    kind: ViewPeriodKind
    first_month: int = 0
    """Pierwszy miesiąc okresu (``month_index``); bez znaczenia dla całego okresu."""

    @staticmethod
    def whole() -> "ViewPeriod":
        return ViewPeriod(ViewPeriodKind.WHOLE)

    @staticmethod
    def containing(kind: ViewPeriodKind, day: date) -> "ViewPeriod":
        """Okres danego rodzaju, w którym leży dzień."""
        if kind is ViewPeriodKind.WHOLE:
            return ViewPeriod.whole()
        length = _MONTHS_PER_KIND[kind]
        index = month_index(day)
        return ViewPeriod(kind, index - index % length)

    @staticmethod
    def default_for(extent: DateRange | None) -> "ViewPeriod":
        """Widok na start: ostatni miesiąc, który Faktury (``extent``: od początku pierwszej
        do końca ostatniej) obejmują w całości; cały okres bez Faktur."""
        if extent is None:
            return ViewPeriod.whole()
        last = ViewPeriod.containing(ViewPeriodKind.MONTH, extent.end)
        dates = last.dates
        if dates is not None and dates.end != extent.end and dates.start > extent.start:
            return last.shifted(-1)
        return last

    @staticmethod
    def from_query(value: str) -> "ViewPeriod | None":
        """Okres widoku z adresu strony; ``None`` dla nieznanej wartości."""
        if value == _WHOLE_QUERY:
            return ViewPeriod.whole()
        if match := re.fullmatch(r"(\d{4})", value):
            return ViewPeriod(ViewPeriodKind.YEAR, int(match[1]) * 12)
        if (match := re.fullmatch(r"(\d{4})-K([1-4])", value)) is not None:
            return ViewPeriod(ViewPeriodKind.QUARTER, int(match[1]) * 12 + (int(match[2]) - 1) * 3)
        if (match := re.fullmatch(r"(\d{4})-(\d{2})", value)) and 1 <= int(match[2]) <= 12:
            return ViewPeriod(ViewPeriodKind.MONTH, int(match[1]) * 12 + int(match[2]) - 1)
        return None

    def to_query(self) -> str:
        year, month = divmod(self.first_month, 12)
        match self.kind:
            case ViewPeriodKind.WHOLE:
                return _WHOLE_QUERY
            case ViewPeriodKind.YEAR:
                return f"{year}"
            case ViewPeriodKind.QUARTER:
                return f"{year}-K{month // 3 + 1}"
            case ViewPeriodKind.MONTH:
                return f"{year}-{month + 1:02d}"

    @property
    def months(self) -> int:
        """Liczba miesięcy; 0 dla całego okresu."""
        return _MONTHS_PER_KIND.get(self.kind, 0)

    @property
    def dates(self) -> DateRange | None:
        """Zakres dat; ``None`` dla całego okresu (zależy od danych)."""
        if self.kind is ViewPeriodKind.WHOLE:
            return None
        return DateRange(first_day(self.first_month), last_day(self.first_month + self.months - 1))

    @property
    def label(self) -> str:
        year, month = divmod(self.first_month, 12)
        match self.kind:
            case ViewPeriodKind.WHOLE:
                return "cały okres"
            case ViewPeriodKind.YEAR:
                return f"rok {year}"
            case ViewPeriodKind.QUARTER:
                return f"{_QUARTER_NUMERALS[month // 3]} kwartał {year}"
            case ViewPeriodKind.MONTH:
                return month_label(self.first_month)

    def shifted(self, steps: int) -> "ViewPeriod":
        """Sąsiedni okres tego samego rodzaju (strzałki ◀ ▶); cały okres się nie przesuwa."""
        return ViewPeriod(self.kind, self.first_month + steps * self.months)

    def year_earlier(self) -> "ViewPeriod":
        return ViewPeriod(self.kind, self.first_month - 12) if self.months else self
