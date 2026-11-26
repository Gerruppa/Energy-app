"""Status Profilu godzinowego: czy trzeba pobrać nowy Raport wartości godzinowych.

Wspólne dla Przeglądu i zakładki Dzień po dniu (jak ``store_expiry.py``). Profil wchodzi
wsadowo, z Raportu pobieranego ręcznie z eLicznika, więc po kilku tygodniach bez nowego Raportu
przypominamy o nim, tak jak o Brakującej Fakturze.
"""

from dataclasses import dataclass
from datetime import date

from pv_app.domain.hourly_profile import hours_in_day
from pv_app.domain.invoice import DateRange
from pv_app.features import formatting as fmt
from pv_app.storage.repository import Repository

PROFILE_OVERDUE_DAYS = 14
"""Profil godzinowy jest zaległy, gdy jego ostatni pełny dzień jest starszy niż tyle dni."""


@dataclass(frozen=True)
class ProfileStatus:
    """Koniec Profilu godzinowego PPE na dany dzień."""

    last_complete_day: date | None
    """Ostatni dzień z pełną dobą (23, 24 albo 25 godzin); ``None``, gdy żadna doba nie jest
    pełna."""
    days_behind: int | None
    """Ile dni minęło od ``last_complete_day`` do dziś; ``None`` bez pełnej doby."""

    @property
    def overdue(self) -> bool:
        """Zaległy Profil godzinowy: czas pobrać nowy Raport wartości godzinowych."""
        return self.days_behind is None or self.days_behind > PROFILE_OVERDUE_DAYS

    def reminds_in(self, dates: DateRange | None) -> bool:
        """Przypomnienie w Okresie widoku (Dzień po dniu): Profil zaległy, a okres sięga za jego
        koniec; ``dates`` ``None`` to cały okres."""
        if not self.overdue:
            return False
        end = self.last_complete_day
        return dates is None or end is None or dates.end > end


def profile_status(repository: Repository, ppe_number: str, today: date) -> ProfileStatus | None:
    """Status Profilu godzinowego PPE na ``today``; ``None`` bez Profilu godzinowego."""
    readings = repository.list_hourly_readings(ppe_number)
    if not readings:
        return None
    hours: dict[date, int] = {}
    for reading in readings:
        hours[reading.day] = hours.get(reading.day, 0) + 1
    last = max((day for day, count in hours.items() if count >= hours_in_day(day)), default=None)
    return ProfileStatus(last, (today - last).days if last is not None else None)


def reminder_text(status: ProfileStatus) -> str:
    """Zdanie przypomnienia o nowym Raporcie wartości godzinowych (zwykły tekst)."""
    end = status.last_complete_day
    where = (
        f"Profil godzinowy z eLicznika kończy się {fmt.day(end)}."
        if end is not None
        else "Profil godzinowy z eLicznika nie ma żadnej pełnej doby."
    )
    return f"{where} Pobierz nowy Raport wartości godzinowych i wgraj go na stronie „Wgraj pliki”."
