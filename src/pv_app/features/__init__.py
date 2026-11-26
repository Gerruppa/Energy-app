"""Rejestr funkcji dashboardu; każda funkcja to pakiet features/<nazwa>/."""

from pv_app.domain.metering_point import MeteringPoint
from pv_app.features.base import Feature
from pv_app.features.costs.page import CostsFeature
from pv_app.features.day_by_day.page import DayByDayFeature
from pv_app.features.energy_store.page import EnergyStoreFeature
from pv_app.features.overview.page import OverviewFeature
from pv_app.storage.repository import Repository

FEATURES: tuple[Feature, ...] = (
    OverviewFeature(),
    EnergyStoreFeature(),
    CostsFeature(),
    DayByDayFeature(),
)


def available_features(repository: Repository, metering_point: MeteringPoint) -> list[Feature]:
    """Zakładki dla PPE, w kolejności ``order``."""
    return sorted(
        (f for f in FEATURES if f.is_available(repository, metering_point)), key=lambda f: f.order
    )
