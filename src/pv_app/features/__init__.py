"""Rejestr funkcji dashboardu; każda funkcja to pakiet features/<nazwa>/."""

from pv_app.domain.metering_point import MeteringPoint
from pv_app.features.base import Feature
from pv_app.features.costs.page import CostsFeature
from pv_app.features.overview.page import OverviewFeature

FEATURES: tuple[Feature, ...] = (OverviewFeature(), CostsFeature())


def available_features(metering_point: MeteringPoint) -> list[Feature]:
    """Zakładki dla PPE, w kolejności ``order``."""
    return sorted((f for f in FEATURES if f.is_available(metering_point)), key=lambda f: f.order)
