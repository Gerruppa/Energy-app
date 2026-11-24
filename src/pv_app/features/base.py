from dataclasses import dataclass
from typing import Protocol

from pv_app.domain.metering_point import MeteringPoint
from pv_app.storage.repository import Repository


@dataclass(frozen=True)
class FeatureContext:
    repository: Repository
    metering_point: MeteringPoint


class Feature(Protocol):
    """Zakładka dashboardu; rejestrowana w ``features/__init__.py``."""

    id: str
    title: str
    order: int

    def is_available(self, metering_point: MeteringPoint) -> bool: ...

    def render(self, context: FeatureContext) -> None: ...
