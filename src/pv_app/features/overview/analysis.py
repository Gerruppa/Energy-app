"""Przegląd: Prognozy Taurona a rzeczywistość i kafelek Magazynu energii; czyste analizy na
``Repository``. Wykres miesiąc po miesiącu i rok do roku są w ``features/monthly.py``."""

from dataclasses import dataclass
from datetime import date

from pv_app.domain.energy_store import EnergyStore, StoreState
from pv_app.domain.invoice import DateRange
from pv_app.domain.view_period import first_day, last_day, month_index
from pv_app.features.base import Filters
from pv_app.features.monthly import (
    ForecastLine,
    History,
    MonthlyChart,
    build_chart,
    current_forecasts,
    invoice_months,
    months_of,
)
from pv_app.storage.repository import Repository

FORECAST_MONTHS_AHEAD = 12
"""Ile miesięcy Prognoz po Okresie widoku pokazuje wykres Prognoz."""


@dataclass(frozen=True)
class ForecastChart:
    """Prognozy Taurona a rzeczywistość: Faktury jak na wykresie miesiąc po miesiącu (bez
    roku wcześniej) i Prognozy z harmonogramów. Prognozy są tylko liniami: nie wchodzą do
    Kosztu okresu ani kWh."""

    energy: MonthlyChart
    forecasts: tuple[ForecastLine, ...]


def forecast_chart(repository: Repository, filters: Filters) -> ForecastChart | None:
    """Prognozy Taurona a rzeczywistość; ``None`` bez Faktur albo bez Prognoz.

    Okno: 12 miesięcy do końca Okresu widoku i Prognozy do 12 miesięcy po nim, w granicach
    danych; cały okres od pierwszej Faktury do ostatniej Prognozy."""
    history = History(repository, filters.ppe_number)
    forecasts = current_forecasts(history.invoices)
    if not history.invoices or not forecasts:
        return None
    first, last = invoice_months(history)
    last = max(last, *(month_index(f.period.end) for f in forecasts))
    dates = filters.view_period.dates
    if dates is None:
        selected = months = range(first, last + 1)
    else:
        selected = months_of(dates)
        end = max(selected[-1], min(last, selected[-1] + FORECAST_MONTHS_AHEAD))
        months = range(max(first, selected[-1] - 11), end + 1)
    window = DateRange(first_day(months[0]), last_day(months[-1]))
    return ForecastChart(
        energy=build_chart(history, months, selected, with_year_earlier=False),
        forecasts=tuple(f for f in forecasts if window.overlaps(f.period)),
    )


def store_tile(repository: Repository, filters: Filters) -> StoreState | None:
    """Kafelek Magazynu energii: stan z Faktury na koniec Okresu widoku; ``None`` bez Faktur
    z Rozliczeniem OZE albo bez Faktury zakończonej do końca Okresu widoku."""
    dates = filters.view_period.dates
    store = EnergyStore.from_invoices(repository.list_invoices(filters.ppe_number))
    return store.state_on(dates.end if dates is not None else date.max)
