"""Profil godzinowy a Faktury: sumy kWh z obu źródeł dla każdego Okresu rozliczeniowego.

ADR 0003: Faktura jest źródłem prawdy dla kwot, Profil godzinowy dla rozkładu w czasie; gdy sumy
się różnią, pokazujemy różnicę zamiast ją wyrównywać. Profil liczony po Zbilansowaniu godzinowym,
bo te ilości rozlicza Faktura.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from pv_app.domain.hourly_profile import HourlyReading, hours_in_day
from pv_app.domain.invoice import DateRange, Invoice, SettlementBasis, Source
from pv_app.domain.period_cost import superseded_invoices
from pv_app.storage.repository import Repository

THRESHOLD_PERCENT = Decimal(2)
"""Różnica powyżej tylu procent (Energia pobrana albo oddana) oznacza okres „do sprawdzenia”."""


@dataclass(frozen=True)
class EnergyComparison:
    """Jedna ilość (Energia pobrana albo oddana) z Faktury i z Profilu godzinowego."""

    invoice_kwh: Decimal
    profile_kwh: Decimal

    @property
    def difference_kwh(self) -> Decimal:
        """Profil minus Faktura."""
        return self.profile_kwh - self.invoice_kwh

    @property
    def difference_percent(self) -> Decimal | None:
        """Różnica w procentach ilości z Faktury; ``None``, gdy Faktura podaje 0 kWh."""
        if self.invoice_kwh == 0:
            return None
        return self.difference_kwh / self.invoice_kwh * 100

    @property
    def exceeds_threshold(self) -> bool:
        """Różnica powyżej ``THRESHOLD_PERCENT``; przy 0 kWh na Fakturze każda różnica."""
        percent = self.difference_percent
        if percent is None:
            return self.difference_kwh != 0
        return abs(percent) > THRESHOLD_PERCENT


@dataclass(frozen=True)
class PeriodComparison:
    """Okres rozliczeniowy niezastąpionej Faktury obok Profilu godzinowego."""

    invoice_number: str
    period: DateRange
    basis: SettlementBasis
    energy_source: Source
    """Strona Faktury z Energią pobraną i oddaną."""
    missing_days: int
    """Dni Okresu rozliczeniowego bez pełnej doby w Profilu godzinowym (23, 24 albo 25 godzin)."""
    imported: EnergyComparison | None
    """Energia pobrana; ``None``, gdy Profil nie pokrywa okresu w całości."""
    exported: EnergyComparison | None
    """Energia oddana; ``None`` bez fotowoltaiki albo gdy Profil nie pokrywa okresu w całości."""

    @property
    def to_check(self) -> bool:
        """Różnica powyżej progu w Energii pobranej albo oddanej."""
        return any(c is not None and c.exceeds_threshold for c in (self.imported, self.exported))


@dataclass(frozen=True)
class ProfileComparison:
    """Profil godzinowy PPE obok jego Faktur."""

    periods: tuple[PeriodComparison, ...]
    """Okresy rozliczeniowe od pierwszego, który Profil godzinowy pokrywa choć jednym dniem, od
    najstarszego. Okres po końcu Profilu ma wiersz z samymi brakującymi dniami: przypomina
    o wgraniu nowego Raportu wartości godzinowych."""
    before_profile: int
    """Ile niezastąpionych Okresów rozliczeniowych kończy się przed pierwszym dniem Profilu
    (tylko policzone, bez wiersza: dla tych lat Raportu zwykle nie ma)."""


@dataclass
class _Day:
    hours: int = 0
    imported_kwh: Decimal = Decimal(0)
    exported_kwh: Decimal = Decimal(0)


def _days(readings: list[HourlyReading]) -> dict[date, _Day]:
    result: dict[date, _Day] = defaultdict(_Day)
    for reading in readings:
        day = result[reading.day]
        day.hours += 1
        day.imported_kwh += reading.imported_kwh
        day.exported_kwh += reading.exported_kwh
    return result


def _period_days(period: DateRange) -> list[date]:
    return [period.start + timedelta(days=n) for n in range(period.days)]


def _compare(invoice: Invoice, profile: dict[date, _Day]) -> PeriodComparison:
    period = invoice.header.billing_period
    period_days = _period_days(period)
    covered = [profile[d] for d in period_days if d in profile]
    missing = sum(1 for d in period_days if d not in profile or profile[d].hours < hours_in_day(d))
    imported = exported = None
    if missing == 0:
        imported = EnergyComparison(
            invoice.imported_kwh, sum((d.imported_kwh for d in covered), Decimal(0))
        )
        if invoice.exported_kwh is not None:
            exported = EnergyComparison(
                invoice.exported_kwh, sum((d.exported_kwh for d in covered), Decimal(0))
            )
    return PeriodComparison(
        invoice_number=invoice.number,
        period=period,
        basis=invoice.settlement_basis,
        energy_source=invoice.energy_source,
        missing_days=missing,
        imported=imported,
        exported=exported,
    )


def profile_comparison(repository: Repository, ppe_number: str) -> ProfileComparison | None:
    """Porównanie dla PPE; ``None``, gdy PPE nie ma Profilu godzinowego."""
    readings = repository.list_hourly_readings(ppe_number)
    if not readings:
        return None
    profile = _days(readings)
    invoices = repository.list_invoices(ppe_number)
    superseded = superseded_invoices(invoices)
    counted = [i for i in invoices if i.number not in superseded]
    first_day = min(profile)
    compared = [i for i in counted if i.header.billing_period.end >= first_day]
    return ProfileComparison(
        tuple(_compare(i, profile) for i in compared),
        before_profile=len(counted) - len(compared),
    )
