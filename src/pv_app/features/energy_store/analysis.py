"""Magazyn energii: czyste analizy na ``Repository``."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from pv_app.domain.energy_store import EnergyStore, StoreMovement, StoreState
from pv_app.features.base import Filters
from pv_app.features.store_expiry import ExpiryOutlook, expiry_outlook
from pv_app.storage.repository import Repository


@dataclass(frozen=True)
class EnergyStoreView:
    state: StoreState | None
    """Stan z Faktury na koniec Okresu widoku; ``None``, gdy żadna Faktura się wtedy nie
    skończyła."""
    movements: tuple[StoreMovement, ...]
    """Ruchy zachodzące na Okres widoku, od najnowszego."""
    seller_share_kwh: Decimal
    """Udział Sprzedawcy z Faktur w ``movements``."""
    history: tuple[StoreMovement, ...]
    """Wszystkie ruchy od najstarszego (wykres stanu w czasie)."""
    outlook: tuple[ExpiryOutlook, ...]
    """Porcje wygasające wkrótce i ile z nich wygaśnie (szacunek)."""


def view_end(filters: Filters) -> date:
    """Dzień, na który pokazujemy stan: koniec Okresu widoku, a dla całego okresu ostatnia
    Faktura."""
    dates = filters.view_period.dates
    return dates.end if dates is not None else date.max


def energy_store_view(repository: Repository, filters: Filters) -> EnergyStoreView | None:
    """Magazyn energii PPE w Okresie widoku; ``None`` bez Faktur z Rozliczeniem OZE."""
    store = EnergyStore.from_invoices(repository.list_invoices(filters.ppe_number))
    if not store.movements:
        return None
    dates = filters.view_period.dates
    movements = tuple(
        m for m in reversed(store.movements) if dates is None or dates.overlaps(m.period)
    )
    state = store.state_on(view_end(filters))
    return EnergyStoreView(
        state=state,
        movements=movements,
        seller_share_kwh=sum((m.seller_share_kwh for m in movements), Decimal(0)),
        history=store.movements,
        outlook=expiry_outlook(repository, filters.ppe_number, state) if state else (),
    )
