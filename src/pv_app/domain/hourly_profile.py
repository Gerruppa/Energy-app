"""Profil godzinowy: Energia pobrana i oddana w PPE godzina po godzinie."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal


def day_of_hour(hour_end: datetime) -> date:
    """Dzień, do którego należy godzina oznaczona końcem: ``0:00`` zamyka poprzedni dzień."""
    return (hour_end - timedelta(hours=1)).date()


@dataclass(frozen=True)
class HourlyReading:
    """Jedna godzina Profilu godzinowego.

    Godzina jest oznaczona końcem w czasie lokalnym, jak w Raporcie wartości godzinowych:
    ``1:00`` to godzina od północy do pierwszej, ``0:00`` zamyka poprzedni dzień. Przy
    zmianie czasu na zimowy godzina ``3:00`` występuje dwa razy; druga ma ``extra_hour``.
    """

    ppe_number: str
    hour_end: datetime
    extra_hour: bool
    imported_kwh: Decimal
    """Energia pobrana po zbilansowaniu godzinowym (ta trafia do rozliczenia)."""
    exported_kwh: Decimal
    """Energia oddana po zbilansowaniu godzinowym (ta trafia do rozliczenia)."""
    unbalanced_imported_kwh: Decimal
    """Energia pobrana przed zbilansowaniem godzinowym."""
    unbalanced_exported_kwh: Decimal
    """Energia oddana przed zbilansowaniem godzinowym."""

    @property
    def day(self) -> date:
        """Dzień, do którego należy godzina."""
        return day_of_hour(self.hour_end)

    @property
    def key(self) -> tuple[str, datetime, bool]:
        """Tożsamość odczytu: ten sam klucz w nowszym raporcie zastępuje wartości."""
        return (self.ppe_number, self.hour_end, self.extra_hour)


def _last_sunday(year: int, month: int) -> date:
    """Ostatnia niedziela miesiąca o 31 dniach (marzec, październik)."""
    last = date(year, month, 31)
    return last - timedelta(days=(last.weekday() + 1) % 7)


def hours_in_day(day: date) -> int:
    """Ile godzin ma doba w czasie polskim: 23 w ostatnią niedzielę marca (zmiana na czas
    letni), 25 w ostatnią niedzielę października (na zimowy), inaczej 24."""
    if day == _last_sunday(day.year, 3):
        return 23
    if day == _last_sunday(day.year, 10):
        return 25
    return 24


@dataclass(frozen=True)
class HourlyValuesReport:
    """Raport wartości godzinowych jednego PPE (plik od Tauron Dystrybucji)."""

    ppe_number: str
    readings: tuple[HourlyReading, ...]
    """Godziny od najstarszej; co najmniej jedna."""

    @property
    def first_day(self) -> date:
        return self.readings[0].day

    @property
    def last_day(self) -> date:
        return self.readings[-1].day

    @property
    def label(self) -> str:
        """Opis do podsumowania importu i rejestru wgranych plików."""
        return f"{self.first_day:%d.%m.%Y}–{self.last_day:%d.%m.%Y}"
