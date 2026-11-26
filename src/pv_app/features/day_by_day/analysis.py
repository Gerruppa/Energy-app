"""Dzień po dniu: Profil godzinowy PPE w Okresie widoku.

Wszystkie ilości po Zbilansowaniu godzinowym, czyli te same, które rozlicza Faktura; ilości przed
zbilansowaniem nie są pokazywane. Godzina jest oznaczona końcem: ``0:00`` zamyka poprzedni dzień.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

from pv_app.domain.hourly_profile import HourlyReading, hours_in_day
from pv_app.features.base import Filters
from pv_app.storage.repository import Repository


def hour_range(start_hour: int) -> str:
    """Godzina doby jako przedział: ``23`` → ``23:00–24:00``."""
    return f"{start_hour}:00–{start_hour + 1}:00"


@dataclass(frozen=True)
class Hour:
    """Jedna godzina dnia z Profilu godzinowego."""

    hour_end: datetime
    extra_hour: bool
    """Druga godzina ``2:00–3:00`` w dniu zmiany czasu na zimowy."""
    imported_kwh: Decimal
    exported_kwh: Decimal

    @property
    def start_hour(self) -> int:
        """Godzina doby, w której się zaczyna (0–23): ``1:00`` → 0, ``0:00`` → 23."""
        return (self.hour_end - timedelta(hours=1)).hour

    @property
    def label(self) -> str:
        """``13:00–14:00``; druga godzina przy zmianie czasu z dopiskiem."""
        text = hour_range(self.start_hour)
        return f"{text} (druga, zmiana czasu)" if self.extra_hour else text


@dataclass(frozen=True)
class Day:
    """Dzień w Okresie widoku: suma jego godzin z Profilu godzinowego."""

    day: date
    hours: tuple[Hour, ...]
    """Godziny dnia od najwcześniejszej; pusta krotka, gdy Profil nie ma żadnej godziny dnia."""

    @property
    def imported_kwh(self) -> Decimal:
        return sum((h.imported_kwh for h in self.hours), Decimal(0))

    @property
    def exported_kwh(self) -> Decimal:
        return sum((h.exported_kwh for h in self.hours), Decimal(0))

    @property
    def hour_count(self) -> int:
        return len(self.hours)

    @property
    def expected_hours(self) -> int:
        """23 albo 25 w dniach zmiany czasu, inaczej 24."""
        return hours_in_day(self.day)

    @property
    def complete(self) -> bool:
        """Profil ma wszystkie godziny tego dnia."""
        return self.hour_count == self.expected_hours


@dataclass(frozen=True)
class TypicalHour:
    """Godzina Typowej doby: średnia z tej godziny we wszystkich dniach Okresu widoku."""

    start_hour: int
    """0–23: godzina ``start_hour:00–start_hour+1:00``."""
    imported_kwh: Decimal
    exported_kwh: Decimal


@dataclass(frozen=True)
class DayByDay:
    days: tuple[Day, ...]
    """Dni Okresu widoku, które Profil godzinowy obejmuje (od jego pierwszego do ostatniego dnia
    w tym okresie), od najstarszego; dzień bez żadnej godziny też ma wpis. Pusta, gdy Profil
    nie sięga Okresu widoku."""
    typical_day: tuple[TypicalHour, ...]
    """Typowa doba: 24 godziny; pusta bez dni."""

    @property
    def default_day(self) -> date | None:
        """Dzień pokazany na start: ostatni w Okresie widoku z jakąkolwiek godziną Profilu."""
        return next((d.day for d in reversed(self.days) if d.hours), None)

    @property
    def surplus_hours(self) -> tuple[int, int] | None:
        """Kiedy panele dają nadwyżkę: od początku pierwszej do końca ostatniej godziny Typowej
        doby, w której oddane przewyższa pobrane; ``None``, gdy żadna."""
        surplus = [h.start_hour for h in self.typical_day if h.exported_kwh > h.imported_kwh]
        if not surplus:
            return None
        return surplus[0], surplus[-1] + 1

    def find(self, day: date) -> Day | None:
        return next((d for d in self.days if d.day == day), None)


def _hour(reading: HourlyReading) -> Hour:
    return Hour(reading.hour_end, reading.extra_hour, reading.imported_kwh, reading.exported_kwh)


def _typical_day(days: list[Day]) -> tuple[TypicalHour, ...]:
    """Średnia każdej godziny doby z godzin, które są w Profilu: dodatkowa godzina przy zmianie
    czasu to jeszcze jedna próbka, brakująca godzina nie zaniża średniej."""
    slots: dict[int, list[Hour]] = defaultdict(list)
    for day in days:
        for hour in day.hours:
            slots[hour.start_hour].append(hour)
    if not slots:
        return ()

    def mean(values: list[Decimal]) -> Decimal:
        return sum(values, Decimal(0)) / len(values) if values else Decimal(0)

    return tuple(
        TypicalHour(
            slot,
            mean([h.imported_kwh for h in slots[slot]]),
            mean([h.exported_kwh for h in slots[slot]]),
        )
        for slot in range(24)
    )


def day_by_day(repository: Repository, filters: Filters) -> DayByDay | None:
    """Profil godzinowy PPE w Okresie widoku; ``None``, gdy PPE nie ma Profilu godzinowego."""
    readings = repository.list_hourly_readings(filters.ppe_number)
    if not readings:
        return None
    by_day: dict[date, list[Hour]] = defaultdict(list)
    for reading in readings:
        by_day[reading.day].append(_hour(reading))
    first, last = min(by_day), max(by_day)
    dates = filters.view_period.dates
    if dates is not None:
        first, last = max(first, dates.start), min(last, dates.end)
    days = [
        Day(
            day,
            tuple(sorted(by_day.get(day, []), key=lambda h: (h.hour_end, h.extra_hour))),
        )
        for day in (first + timedelta(days=n) for n in range((last - first).days + 1))
    ]
    return DayByDay(tuple(days), _typical_day(days))
