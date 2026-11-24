"""Model porcji Magazynu energii (``EnergyStore``) na Fakturach z wymyślonymi liczbami."""

from dataclasses import replace
from datetime import date
from decimal import Decimal

from factories import store_invoice
from pv_app.domain.energy_store import (
    EnergyStore,
    MovementKind,
    Portion,
    StoreMovement,
)
from pv_app.domain.invoice import Amount, Correction, DateRange, DocumentKind, Source

JANUARY = DateRange(date(2026, 1, 1), date(2026, 1, 31))
FEBRUARY = DateRange(date(2026, 2, 1), date(2026, 2, 28))
MARCH = DateRange(date(2026, 3, 1), date(2026, 3, 31))


def test_portion_is_credited_kwh_expiring_twelve_months_after_its_period() -> None:
    store = EnergyStore.from_invoices([store_invoice(JANUARY, "0", "40", "40", number="F/1")])

    assert store.portions_on(date(2026, 1, 31)) == (
        Portion("F/1", JANUARY, Decimal("40"), Decimal("40"), date(2027, 1, 31)),
    )


def test_used_kwh_come_from_the_oldest_portion_first() -> None:
    # Luty: 40 na start + 30 przyrostu − 20 odebrane = 50 na koniec.
    store = EnergyStore.from_invoices(
        [
            store_invoice(FEBRUARY, "40", "30", "50", number="F/2"),
            store_invoice(JANUARY, "0", "40", "40", number="F/1"),
        ]
    )

    assert [(p.invoice_number, p.remaining_kwh) for p in store.portions_on(date(2026, 2, 28))] == [
        ("F/1", Decimal("20")),
        ("F/2", Decimal("30")),
    ]
    # Z 100 kWh pobranych w lutym 20 kWh pokrył Magazyn energii.
    assert (store.movements[-1].imported_kwh, store.movements[-1].discount_kwh) == (
        Decimal("100"),
        Decimal("20"),
    )


DECEMBER_2024 = DateRange(date(2024, 12, 1), date(2024, 12, 31))
JAN_NOV_2025 = DateRange(date(2025, 1, 1), date(2025, 11, 30))
DECEMBER_2025 = DateRange(date(2025, 12, 1), date(2025, 12, 31))
JANUARY_2026 = DateRange(date(2026, 1, 1), date(2026, 1, 31))


def test_drop_of_start_below_previous_end_is_expiry_of_the_oldest_portion() -> None:
    store = EnergyStore.from_invoices(
        [
            store_invoice(DECEMBER_2024, "0", "50", "50", number="F/12/24"),
            # 30 kWh odebrane z porcji grudniowej; zostaje z niej 20, ważne do 31.12.2025.
            store_invoice(JAN_NOV_2025, "50", "200", "220", number="F/25"),
            store_invoice(DECEMBER_2025, "220", "10", "230", number="F/12/25"),
            # Na start 210, a poprzednia Faktura kończy się na 230: wygasło 20 kWh.
            store_invoice(JANUARY_2026, "210", "5", "215", number="F/1/26"),
        ]
    )

    expiry = store.movements[-2]
    assert expiry == StoreMovement(
        kind=MovementKind.EXPIRY,
        invoice_number="F/1/26",
        period=DateRange(date(2026, 1, 1), date(2026, 1, 1)),
        start_kwh=Decimal("230"),
        credited_kwh=Decimal(0),
        discount_kwh=Decimal(0),
        expired_kwh=Decimal("20"),
        end_kwh=Decimal("210"),
        # Wyliczone z dwóch Faktur: stan na koniec grudniowej i stan na start styczniowej.
        start_source=Source("F/12/25", 4),
        end_source=Source("F/1/26", 4),
        discount_coefficient=Decimal("0.8"),
    )
    assert [(p.invoice_number, p.remaining_kwh) for p in store.portions_on(date(2026, 1, 31))] == [
        ("F/25", Decimal("200")),
        ("F/12/25", Decimal("10")),
        ("F/1/26", Decimal("5")),
    ]


def test_total_follows_the_invoice_when_the_split_rounds_differently() -> None:
    # Bilans Faktury różni się o 1 kWh (bilansowanie godzinowe): 40 + 30 − 20 ≠ 51.
    store = EnergyStore.from_invoices(
        [
            store_invoice(JANUARY, "0", "40", "40", number="F/1"),
            store_invoice(FEBRUARY, "40", "30", "51", number="F/2"),
        ]
    )

    state = store.state_on(date(2026, 3, 15))
    assert state is not None
    assert (state.balance_kwh, state.as_of, state.source) == (
        Decimal("51"),
        date(2026, 2, 28),
        Source("F/2", 4),
    )
    assert sum(p.remaining_kwh for p in state.portions) == Decimal("51")


def test_start_of_first_invoice_is_a_portion_of_unknown_origin_used_first() -> None:
    store = EnergyStore.from_invoices([store_invoice(JANUARY, "25", "40", "55", number="F/1")])

    assert store.portions_on(date(2026, 1, 31)) == (
        Portion(None, None, Decimal("25"), Decimal("15"), None),
        Portion("F/1", JANUARY, Decimal("40"), Decimal("40"), date(2027, 1, 31)),
    )


def test_drop_across_a_gap_between_invoices_is_not_called_expiry() -> None:
    # Brak Faktury za luty: spadek z 40 do 25 to może być odbiór, nie Wygaśnięcie.
    store = EnergyStore.from_invoices(
        [
            store_invoice(JANUARY, "0", "40", "40", number="F/1"),
            store_invoice(MARCH, "25", "10", "35", number="F/3"),
        ]
    )

    assert [m.kind for m in store.movements] == [MovementKind.INVOICE, MovementKind.INVOICE]
    assert sum(p.remaining_kwh for p in store.portions_on(date(2026, 3, 31))) == Decimal("35")


def test_superseded_invoice_gives_way_to_its_correction() -> None:
    original = store_invoice(JANUARY, "0", "40", "40", number="F/1")
    correction = replace(
        store_invoice(JANUARY, "0", "48", "48", number="K/1"),
        kind=DocumentKind.CORRECTING_INVOICE,
        correction=Correction(
            "F/1",
            date(2026, 2, 5),
            "zmiana odczytu",
            Amount(None, None, Decimal(0)),
            Decimal(0),
            Decimal(0),
            Source("K/1", 1),
            Source("K/1", 2),
        ),
    )

    store = EnergyStore.from_invoices([original, correction])

    assert [m.invoice_number for m in store.movements] == ["K/1"]


def test_state_lists_portions_expiring_within_the_window() -> None:
    store = EnergyStore.from_invoices(
        [
            store_invoice(DECEMBER_2024, "0", "50", "50", number="F/12/24"),
            store_invoice(JAN_NOV_2025, "50", "200", "220", number="F/25"),
        ]
    )

    # Na 30.11.2025: porcja grudniowa (20 kWh) wygasa 31.12.2025, roczna dopiero w 2026.
    state = store.state_on(date(2025, 11, 30), expiring_months=3)
    assert state is not None
    assert state.expiring_until == date(2026, 2, 28)
    assert [(p.invoice_number, p.remaining_kwh) for p in state.expiring] == [
        ("F/12/24", Decimal("20"))
    ]
