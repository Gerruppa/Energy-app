"""Reguły widoczności zakładek (``is_available``) na Repository w pamięci."""

from dataclasses import replace
from datetime import datetime
from decimal import Decimal

from pv_app.domain.hourly_profile import HourlyReading
from pv_app.domain.metering_point import MeteringPoint, SiteIcon
from pv_app.features import available_features
from pv_app.features.visibility import shows_car, shows_day_by_day, shows_energy_store
from pv_app.storage.in_memory import InMemoryRepository

HOME = MeteringPoint(
    ppe_number="590000000000000001",
    name="Dom",
    slug="dom",
    icon=SiteIcon.HOUSE,
    charges_car=False,
    address="UL. PRZYKŁADOWA 1, 00-001 TESTOWO",
    net_metering=True,
)
FLAT = replace(
    HOME, ppe_number="590000000000000002", name="Mieszkanie", slug="mieszkanie", net_metering=False
)


def hour_of(ppe_number: str) -> HourlyReading:
    return HourlyReading(
        ppe_number=ppe_number,
        hour_end=datetime(2026, 10, 1, 1),
        extra_hour=False,
        imported_kwh=Decimal("0.5"),
        exported_kwh=Decimal("0"),
        unbalanced_imported_kwh=Decimal("0.5"),
        unbalanced_exported_kwh=Decimal("0"),
    )


def titles(repository: InMemoryRepository, point: MeteringPoint) -> list[str]:
    return [f.title for f in available_features(repository, point)]


def test_energy_store_tab_only_with_net_metering() -> None:
    repository = InMemoryRepository()

    assert titles(repository, HOME) == ["Przegląd", "Magazyn energii", "Koszty i Faktury"]
    assert titles(repository, FLAT) == ["Przegląd", "Koszty i Faktury"]
    assert shows_energy_store(repository, HOME)
    assert not shows_energy_store(repository, FLAT)


def test_day_by_day_after_hourly_profile_of_that_metering_point_is_uploaded() -> None:
    repository = InMemoryRepository()
    assert not shows_day_by_day(repository, HOME)

    repository.add_hourly_readings([hour_of(HOME.ppe_number)])

    assert shows_day_by_day(repository, HOME)
    assert not shows_day_by_day(repository, FLAT)
    assert titles(repository, HOME) == [
        "Przegląd",
        "Magazyn energii",
        "Koszty i Faktury",
        "Dzień po dniu",
    ]


def test_car_tab_after_charging_is_switched_on() -> None:
    repository = InMemoryRepository()

    assert not shows_car(repository, HOME)
    assert shows_car(repository, replace(HOME, charges_car=True))
