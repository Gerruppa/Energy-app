from dataclasses import dataclass
from typing import Protocol

from pv_app.domain.invoice import DateRange
from pv_app.domain.metering_point import MeteringPoint
from pv_app.domain.view_period import ViewPeriod
from pv_app.storage.repository import Repository


@dataclass(frozen=True)
class Filters:
    """Co oglądamy: jeden PPE w jednym Okresie widoku."""

    ppe_number: str
    view_period: ViewPeriod


@dataclass(frozen=True)
class FeatureContext:
    repository: Repository
    metering_point: MeteringPoint
    view_period: ViewPeriod

    @property
    def filters(self) -> Filters:
        return Filters(self.metering_point.ppe_number, self.view_period)


class Feature(Protocol):
    """Zakładka dashboardu; rejestrowana w ``features/__init__.py``."""

    id: str
    title: str
    order: int

    def is_available(self, repository: Repository, metering_point: MeteringPoint) -> bool:
        """Czy zakładka pojawia się dla PPE; reguły w ``features/visibility.py``."""
        ...

    def render(self, context: FeatureContext) -> None: ...


def invoice_extent(repository: Repository, ppe_number: str) -> DateRange | None:
    """Od początku pierwszego do końca ostatniego Okresu rozliczeniowego PPE; ``None`` bez Faktur.

    Granice przełącznika Okresu widoku (strzałki ◀ ▶) i podstawa widoku na start."""
    periods = [i.header.billing_period for i in repository.list_invoices(ppe_number)]
    if not periods:
        return None
    return DateRange(min(p.start for p in periods), max(p.end for p in periods))


def view_extent(repository: Repository, ppe_number: str) -> DateRange | None:
    """Zakres Faktur i Profilu godzinowego PPE razem; ``None`` bez obu.

    Granice przełącznika Okresu widoku (strzałki ◀ ▶): dni po ostatniej Fakturze są dostępne,
    gdy Profil godzinowy je obejmuje. Widok na start dalej liczy się z ``invoice_extent``."""
    invoices = invoice_extent(repository, ppe_number)
    ranges = [invoices] if invoices is not None else []
    days = [r.day for r in repository.list_hourly_readings(ppe_number)]
    if days:
        ranges.append(DateRange(min(days), max(days)))
    if not ranges:
        return None
    return DateRange(min(r.start for r in ranges), max(r.end for r in ranges))
