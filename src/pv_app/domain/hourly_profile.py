"""Profil godzinowy: Energia pobrana i oddana w PPE godzina po godzinie."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal


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
        return (self.hour_end - timedelta(hours=1)).date()

    @property
    def key(self) -> tuple[str, datetime, bool]:
        """Tożsamość odczytu: ten sam klucz w nowszym raporcie zastępuje wartości."""
        return (self.ppe_number, self.hour_end, self.extra_hour)


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
