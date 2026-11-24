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

    def is_available(self, metering_point: MeteringPoint) -> bool: ...

    def render(self, context: FeatureContext) -> None: ...


def invoice_extent(repository: Repository, ppe_number: str) -> DateRange | None:
    """Od początku pierwszego do końca ostatniego Okresu rozliczeniowego PPE; ``None`` bez Faktur.

    Granice przełącznika Okresu widoku (strzałki ◀ ▶) i podstawa widoku na start."""
    periods = [i.header.billing_period for i in repository.list_invoices(ppe_number)]
    if not periods:
        return None
    return DateRange(min(p.start for p in periods), max(p.end for p in periods))
