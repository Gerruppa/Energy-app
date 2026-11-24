"""Analizy Magazynu energii (zakładka i kafelek Przeglądu) na Repository w pamięci."""

from datetime import date
from decimal import Decimal

from factories import HOME, invoice_for, store_invoice
from pv_app.domain.energy_store import MovementKind
from pv_app.domain.invoice import DateRange, Invoice, Source
from pv_app.domain.view_period import ViewPeriod
from pv_app.features.base import Filters
from pv_app.features.energy_store.analysis import energy_store_view
from pv_app.features.overview.analysis import store_tile
from pv_app.storage.in_memory import InMemoryRepository

DECEMBER_2024 = DateRange(date(2024, 12, 1), date(2024, 12, 31))
JAN_NOV_2025 = DateRange(date(2025, 1, 1), date(2025, 11, 30))
DECEMBER_2025 = DateRange(date(2025, 12, 1), date(2025, 12, 31))
JANUARY_2026 = DateRange(date(2026, 1, 1), date(2026, 1, 31))


def view(query: str) -> Filters:
    period = ViewPeriod.from_query(query)
    assert period is not None
    return Filters(ppe_number=HOME, view_period=period)


def repository_with(*invoices: Invoice) -> InMemoryRepository:
    repository = InMemoryRepository()
    for invoice in invoices:
        repository.add_invoice(invoice)
    return repository


def history() -> InMemoryRepository:
    return repository_with(
        store_invoice(DECEMBER_2024, "0", "50", "50", number="F/12/24"),
        store_invoice(JAN_NOV_2025, "50", "200", "220", number="F/25"),
        store_invoice(DECEMBER_2025, "220", "10", "230", number="F/12/25"),
        store_invoice(JANUARY_2026, "210", "5", "215", number="F/1/26", exported="6.25"),
    )


def test_view_shows_state_at_end_of_view_period_and_its_movements() -> None:
    result = energy_store_view(history(), view("2025-12"))

    assert result is not None
    state = result.state
    assert state is not None
    assert (state.balance_kwh, state.source) == (Decimal("230"), Source("F/12/25", 4))
    assert [(p.invoice_number, p.remaining_kwh) for p in state.portions] == [
        ("F/12/24", Decimal("20")),
        ("F/25", Decimal("200")),
        ("F/12/25", Decimal("10")),
    ]
    # Porcja grudniowa wygasa 31.12.2025, w dniu stanu: jeszcze w stanie, ale do Wygaśnięcia.
    assert state.expiring_kwh == Decimal("20")
    assert [m.invoice_number for m in result.movements] == ["F/12/25"]


def test_movements_newest_first_with_expiry_between_invoices() -> None:
    result = energy_store_view(history(), view("caly"))

    assert result is not None
    assert [(m.kind, m.invoice_number) for m in result.movements[:3]] == [
        (MovementKind.INVOICE, "F/1/26"),
        (MovementKind.EXPIRY, "F/1/26"),
        (MovementKind.INVOICE, "F/12/25"),
    ]
    assert result.state is not None and result.state.balance_kwh == Decimal("215")
    # Udział Sprzedawcy: 12,5 + 50 + 2,5 + 1,25 (po 20% Energii oddanej).
    assert result.seller_share_kwh == Decimal("66.25")


def test_no_view_without_energy_settlement() -> None:
    repository = repository_with(invoice_for(JANUARY_2026, "100"))

    assert energy_store_view(repository, view("caly")) is None
    assert store_tile(repository, view("caly")) is None


def test_overview_tile_state_credited_in_last_invoice_and_expiring_in_three_months() -> None:
    tile = store_tile(history(), view("2025-11"))

    assert tile is not None
    assert (tile.balance_kwh, tile.as_of, tile.source) == (
        Decimal("220"),
        date(2025, 11, 30),
        Source("F/25", 4),
    )
    assert (tile.movement.credited_kwh, tile.movement.period) == (Decimal("200"), JAN_NOV_2025)
    assert (tile.expiring_kwh, tile.expiring_until) == (Decimal("20"), date(2026, 2, 28))
