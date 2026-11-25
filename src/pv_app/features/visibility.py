"""Reguły widoczności zakładek: kiedy zakładka pojawia się dla PPE.

Wspólne dla ``is_available`` zakładek i ustawień PPE (podpowiedzi, czego brakuje). Zakładki
Dzień po dniu (F4/F5) i Auto (F6) jeszcze nie istnieją, ale ich reguły już tak, żeby ustawienia
PPE i dane w bazie od początku decydowały o widoczności.
"""

from pv_app.domain.metering_point import MeteringPoint
from pv_app.storage.repository import Repository


def shows_energy_store(repository: Repository, metering_point: MeteringPoint) -> bool:
    """Magazyn energii: tylko PPE rozliczany w net-meteringu (z Faktury)."""
    return metering_point.net_metering


def shows_day_by_day(repository: Repository, metering_point: MeteringPoint) -> bool:
    """Dzień po dniu: po wgraniu Profilu godzinowego tego PPE (Raport wartości godzinowych)."""
    return repository.has_hourly_readings(metering_point.ppe_number)


def shows_car(repository: Repository, metering_point: MeteringPoint) -> bool:
    """Auto: po włączeniu ładowania auta w ustawieniach PPE."""
    return metering_point.charges_car
