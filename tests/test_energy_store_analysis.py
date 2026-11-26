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
from pv_app.features.store_expiry import outlook_help, outlook_line
from pv_app.storage.in_memory import InMemoryRepository

DECEMBER_2024 = DateRange(date(2024, 12, 1), date(2024, 12, 31))
JAN_NOV_2025 = DateRange(date(2025, 1, 1), date(2025, 11, 30))
DECEMBER_2025 = DateRange(date(2025, 12, 1), date(2025, 12, 31))
JANUARY_2026 = DateRange(date(2026, 1, 1), date(2026, 1, 31))
SEPTEMBER_2024 = DateRange(date(2024, 9, 1), date(2024, 9, 30))
OCTOBER_2024 = DateRange(date(2024, 10, 1), date(2024, 10, 31))
NOVEMBER_2024 = DateRange(date(2024, 11, 1), date(2024, 11, 30))
OCT_2024_JUN_2025 = DateRange(date(2024, 10, 1), date(2025, 6, 30))
DEC_2025_JAN_2026 = DateRange(date(2025, 12, 1), date(2026, 1, 31))
DEC_2024_SEP_2025 = DateRange(date(2024, 12, 1), date(2025, 9, 30))


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
    result = store_tile(history(), view("2025-11"))

    assert result is not None
    tile = result.state
    assert (tile.balance_kwh, tile.as_of, tile.source) == (
        Decimal("220"),
        date(2025, 11, 30),
        Source("F/25", 4),
    )
    assert (tile.movement.credited_kwh, tile.movement.period) == (Decimal("200"), JAN_NOV_2025)
    assert (tile.expiring_kwh, tile.expiring_until) == (Decimal("20"), date(2026, 2, 28))


def test_portion_that_import_cannot_use_up_is_lost_and_counted_in_days_of_import() -> None:
    # Stan na 31.12.2025: porcja grudniowa (20 kWh) wygasa w dniu stanu, więc pobór jej
    # nie zdąży zużyć. W grudniu 2024 dom pobrał 100 kWh przez 31 dni.
    result = energy_store_view(history(), view("2025-12"))

    assert result is not None
    [outlook] = result.outlook
    assert (outlook.portion.invoice_number, outlook.lost_kwh) == ("F/12/24", Decimal("20"))
    assert outlook.year_earlier
    assert outlook.lost_days is not None and round(outlook.lost_days) == 6
    assert outlook_line(outlook) == (
        "⚠ 20 kWh wygaśnie 31.12.2025: nie zdążycie jej odebrać, to mniej więcej tyle, ile dom "
        "pobiera z sieci przez 6 dni w grudniu"
    )
    assert "Szacunek" in outlook_help(outlook) and "rok wcześniej" in outlook_help(outlook)


def test_portion_that_import_uses_up_before_expiry_is_not_lost() -> None:
    # Stan na 30.11.2025: z porcji grudniowej zostało 20 kWh do 31.12.2025, a w grudniu
    # 2024 dom pobrał 100 kWh.
    result = store_tile(history(), view("2025-11"))

    assert result is not None
    [outlook] = result.outlook
    assert outlook.portion.invoice_number == "F/12/24"
    assert outlook.used and outlook.lost_kwh == 0
    assert outlook_line(outlook).startswith("✓ 20 kWh ważne do 31.12.2025: zdążycie ją odebrać")


def test_months_without_history_a_year_earlier_take_the_average_of_recent_invoices() -> None:
    # Stan na 30.6.2025: z porcji wrześniowej zostało 28 kWh do 30.9.2025. Lipca i sierpnia
    # 2024 nie ma w Fakturach, więc liczą się średnio: 4 kWh przez 303 dni ostatnich Faktur;
    # we wrześniu 2024 dom pobrał 2 kWh. Pobór zużyje 2 + 62 × 4/303 ≈ 2,82 kWh.
    repository = repository_with(
        store_invoice(SEPTEMBER_2024, "0", "30", "30", number="F/9/24", imported="2"),
        store_invoice(OCT_2024_JUN_2025, "30", "10", "38", number="F/6/25", imported="2"),
    )

    result = energy_store_view(repository, view("2025-06"))

    assert result is not None
    [outlook] = result.outlook
    assert outlook.portion.invoice_number == "F/9/24"
    assert not outlook.year_earlier
    assert "średnio" in outlook_help(outlook)
    assert outlook.lost_kwh.quantize(Decimal("0.01")) == Decimal("25.18")


def test_portions_expiring_in_one_window_share_the_import_oldest_first() -> None:
    # Stan na 30.9.2025: po 30 kWh z października i listopada 2024, a dom pobierał wtedy po
    # 20 kWh na miesiąc. Październik zużyje 20 z pierwszej porcji (10 wygasa); listopad
    # zużyje 20 z drugiej (10 wygasa), bo wygasła część pierwszej poboru nie pokrywa.
    repository = repository_with(
        store_invoice(OCTOBER_2024, "0", "30", "30", number="F/10/24", imported="20"),
        store_invoice(NOVEMBER_2024, "30", "30", "60", number="F/11/24", imported="20"),
        store_invoice(DEC_2024_SEP_2025, "60", "0", "60", number="F/9/25"),
    )

    result = energy_store_view(repository, view("2025-09"))

    assert result is not None
    assert [(o.portion.invoice_number, o.lost_kwh) for o in result.outlook] == [
        ("F/10/24", Decimal("10")),
        ("F/11/24", Decimal("10")),
    ]
    assert all(o.year_earlier for o in result.outlook)
    assert outlook_line(result.outlook[0]).startswith(
        "⚠ 30 kWh ważne do 31.10.2025: zdążycie odebrać część, a ok. 10 kWh wygaśnie"
    )


def test_portion_past_its_expiry_date_on_the_state_day_expires_before_the_next_invoice() -> None:
    # Faktura za grudzień 2025 i styczeń 2026: porcja z grudnia 2024 (20 kWh) minęła
    # 31.12.2025, ale stan na 31.1.2026 z Faktury jeszcze ją zawiera.
    repository = repository_with(
        store_invoice(DECEMBER_2024, "0", "50", "50", number="F/12/24"),
        store_invoice(JAN_NOV_2025, "50", "200", "220", number="F/25"),
        store_invoice(DEC_2025_JAN_2026, "220", "10", "230", number="F/1/26"),
    )

    result = energy_store_view(repository, view("2026-01"))

    assert result is not None
    [outlook] = result.outlook
    assert outlook.overdue and outlook.lost_kwh == Decimal("20")
    assert outlook_line(outlook).startswith(
        "⚠ 20 kWh po terminie 31.12.2025: wygaśnie przed następną Fakturą"
    )
