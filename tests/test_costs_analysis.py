"""Analiza zakładki Koszty i Faktury na Repository w pamięci."""

from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path

from factories import HOME, invoice_for
from pv_app.domain.cost_groups import CostGroup
from pv_app.domain.debit_note import DebitNote
from pv_app.domain.invoice import (
    DateRange,
    DocumentKind,
    Invoice,
    LineComponent,
    ReadingType,
    SettlementBasis,
    Source,
)
from pv_app.domain.view_period import ViewPeriod
from pv_app.features.base import Filters
from pv_app.features.costs.analysis import (
    DebitNoteListRow,
    InvoiceListRow,
    cost_summary,
    debit_note_list,
    invoice_list,
    unit_price_history,
)
from pv_app.features.monthly import monthly_chart
from pv_app.ingest import import_document
from pv_app.ingest.raw import RawDocument
from pv_app.storage.in_memory import InMemoryRepository

FIXTURES = Path(__file__).parent / "fixtures"


def whole(ppe_number: str) -> Filters:
    return Filters(ppe_number, ViewPeriod.whole())


def fixture_invoice(name: str) -> Invoice:
    invoice = import_document(RawDocument.from_json(FIXTURES / f"{name}.json")).invoice
    assert invoice is not None
    return invoice


def test_invoice_list_shows_period_kind_basis_and_period_cost_newest_first() -> None:
    october = fixture_invoice("new_layout_net_metering_monthly")
    september = replace(
        october,
        header=replace(
            october.header,
            number="T/K1/BN000001/0003/26",
            billing_period=DateRange(date(2026, 9, 1), date(2026, 9, 30)),
        ),
        readings=tuple(replace(r, reading_type=ReadingType.ESTIMATED) for r in october.readings),
    )
    repository = InMemoryRepository()
    for invoice in (september, october, fixture_invoice("new_layout_standard_half_year")):
        repository.add_invoice(invoice)

    rows = invoice_list(repository, whole("590000000000000001"))

    assert rows == [
        InvoiceListRow(
            number="T/K1/BN000001/0004/26",
            period=DateRange(date(2026, 10, 1), date(2026, 10, 31)),
            kind=DocumentKind.SETTLEMENT_INVOICE,
            basis=SettlementBasis.ACTUAL_READING,
            imported_kwh=Decimal("150"),
            exported_kwh=Decimal("300"),
            period_cost=Decimal("32.04"),
            source=Source("T/K1/BN000001/0004/26", 3),
        ),
        InvoiceListRow(
            number="T/K1/BN000001/0003/26",
            period=DateRange(date(2026, 9, 1), date(2026, 9, 30)),
            kind=DocumentKind.SETTLEMENT_INVOICE,
            basis=SettlementBasis.ESTIMATED_READING,
            imported_kwh=Decimal("150"),
            exported_kwh=Decimal("300"),
            period_cost=Decimal("32.04"),
            source=Source("T/K1/BN000001/0004/26", 3),
        ),
    ]


def test_invoice_list_is_empty_for_metering_point_without_invoices() -> None:
    assert invoice_list(InMemoryRepository(), whole("590000000000000001")) == []


APARTMENT = "590000000000000002"


def fixture_debit_note() -> DebitNote:
    note = import_document(RawDocument.from_json(FIXTURES / "debit_note_correction.json"))
    assert note.debit_note is not None
    return note.debit_note


def corrected_invoice() -> Invoice:
    """Faktura, którą koryguje fixture ``old_layout_correcting_standard``."""
    original = fixture_invoice("old_layout_standard_half_year")
    return replace(
        original,
        header=replace(
            original.header,
            number="E/TM3/0000005/24",
            billing_period=DateRange(date(2023, 12, 4), date(2024, 3, 24)),
        ),
    )


def test_correcting_invoice_replaces_corrected_one_which_stays_in_list() -> None:
    repository = InMemoryRepository()
    repository.add_invoice(corrected_invoice())
    repository.add_invoice(fixture_invoice("old_layout_correcting_standard"))

    rows = invoice_list(repository, whole(APARTMENT))

    assert [(r.number, r.kind, r.superseded_by, r.period_cost) for r in rows] == [
        ("E/TM3/BN000002/0001/26", DocumentKind.CORRECTING_INVOICE, None, Decimal("44.28")),
        (
            "E/TM3/0000005/24",
            DocumentKind.SETTLEMENT_INVOICE,
            "E/TM3/BN000002/0001/26",
            Decimal("629.37"),
        ),
    ]
    assert rows[0].corrects == "E/TM3/0000005/24"


def test_debit_note_discount_lowers_period_cost_of_period_it_concerns() -> None:
    repository = InMemoryRepository()
    repository.add_invoice(fixture_invoice("old_layout_correcting_standard"))
    repository.add_invoice(fixture_invoice("new_layout_standard_half_year"))
    repository.add_debit_note(fixture_debit_note())

    rows = invoice_list(repository, whole(APARTMENT))

    # Data sprzedaży Noty (1.02.2026) leży w Okresie rozliczeniowym 20.09.2025 – 9.03.2026.
    assert [(r.number, r.period_cost, r.debit_notes) for r in rows] == [
        ("E/TM3/BN000002/0002/26", Decimal("432.87") - Decimal("47.70"), ("TM3NBN000002/001",)),
        ("E/TM3/BN000002/0001/26", Decimal("44.28"), ()),
    ]


def test_corrected_debit_note_no_longer_counts() -> None:
    correction = fixture_debit_note()
    original = replace(
        correction,
        number="T3N0000007",
        corrected_note_number=None,
        issue_date=date(2026, 1, 10),
    )
    repository = InMemoryRepository()
    repository.add_invoice(fixture_invoice("new_layout_standard_half_year"))
    repository.add_debit_note(original)
    repository.add_debit_note(correction)

    (row,) = invoice_list(repository, whole(APARTMENT))

    assert row.debit_notes == ("TM3NBN000002/001",)
    assert row.period_cost == Decimal("432.87") - Decimal("47.70")
    notes = debit_note_list(repository, whole(APARTMENT))
    assert [(n.number, n.superseded_by, n.invoice_number) for n in notes] == [
        ("TM3NBN000002/001", None, "E/TM3/BN000002/0002/26"),
        ("T3N0000007", "TM3NBN000002/001", None),
    ]


def test_debit_note_without_invoice_for_its_period_is_listed_unassigned() -> None:
    repository = InMemoryRepository()
    repository.add_debit_note(fixture_debit_note())

    assert debit_note_list(repository, whole(APARTMENT)) == [
        DebitNoteListRow(
            number="TM3NBN000002/001",
            issue_date=date(2026, 2, 7),
            sale_date=date(2026, 2, 1),
            discount=Decimal("47.70"),
            amount_due=Decimal("12.30"),
            invoice_number=None,
            superseded_by=None,
            source=Source("TM3NBN000002/001", 1),
        )
    ]


def test_lists_only_invoices_and_notes_overlapping_view_period() -> None:
    repository = InMemoryRepository()
    repository.add_invoice(fixture_invoice("old_layout_correcting_standard"))
    repository.add_invoice(fixture_invoice("new_layout_standard_half_year"))
    repository.add_debit_note(fixture_debit_note())
    december_2025 = ViewPeriod.from_query("2025-12")
    assert december_2025 is not None

    rows = invoice_list(repository, Filters(APARTMENT, december_2025))
    notes = debit_note_list(repository, Filters(APARTMENT, december_2025))

    # Okres rozliczeniowy 20.09.2025 – 9.03.2026 obejmuje grudzień; Nota (sprzedaż 1.02.2026)
    # dotyczy tej samej Faktury, więc też zostaje.
    assert [r.number for r in rows] == ["E/TM3/BN000002/0002/26"]
    assert [n.number for n in notes] == ["TM3NBN000002/001"]


# Koszt okresu w Okresie widoku: z rozkładu Faktur na miesiące, jak w Przeglądzie.

OCTOBER_2026 = DateRange(date(2026, 10, 1), date(2026, 10, 31))
# 1.12.2024 – 30.11.2025: 365 dni, z tego 31 w październiku 2025.
YEAR_2025 = DateRange(date(2024, 12, 1), date(2025, 11, 30))


def view(query: str) -> Filters:
    period = ViewPeriod.from_query(query)
    assert period is not None
    return Filters(HOME, period)


def repository_with(*invoices: Invoice) -> InMemoryRepository:
    repository = InMemoryRepository()
    for invoice in invoices:
        repository.add_invoice(invoice)
    return repository


def test_period_cost_and_average_price_compared_with_year_earlier() -> None:
    repository = repository_with(
        invoice_for(OCTOBER_2026, "200", "300", variable_gross="20", fixed_gross="30"),
        invoice_for(YEAR_2025, "3650", "7300", variable_gross="3650"),
    )

    summary = cost_summary(repository, view("2026-10"))

    assert summary is not None
    assert summary.current.period_cost == Decimal("50")
    # Cena średnia kWh = Koszt okresu ÷ Energia pobrana, nie wartość z Faktury.
    assert summary.current.average_price == Decimal("0.25")
    assert not summary.current.approximate
    assert summary.year_earlier is not None
    # Październik 2025 z Faktury rocznej: 31/365 kWh i Składników zmiennych.
    assert summary.year_earlier.period_cost == Decimal("310")
    assert summary.year_earlier.average_price == Decimal("1")
    assert summary.year_earlier.approximate


def test_whole_period_has_no_year_earlier_and_no_invoices_means_no_summary() -> None:
    repository = repository_with(
        invoice_for(OCTOBER_2026, "200", "300", variable_gross="20", fixed_gross="30"),
    )

    summary = cost_summary(repository, whole(HOME))

    assert summary is not None
    assert summary.current.period_cost == Decimal("50")
    assert summary.year_earlier is None
    assert cost_summary(InMemoryRepository(), whole(HOME)) is None


def test_cost_groups_of_view_period_cut_from_longer_invoice_like_monthly_split() -> None:
    repository = repository_with(
        invoice_for(YEAR_2025, "3650", "7300", variable_gross="3650", fixed_gross="120"),
    )

    summary = cost_summary(repository, view("2025-10"))

    assert summary is not None
    # Dystrybucja zmienna po dniach (31/365), Opłata mocowa po równo na 12 miesięcy.
    assert summary.current.cost_groups == {
        CostGroup.ENERGY: Decimal("0"),
        CostGroup.VARIABLE_DISTRIBUTION: Decimal("310"),
        CostGroup.PER_KWH_FEES: Decimal("0"),
        CostGroup.CAPACITY: Decimal("10"),
        CostGroup.FIXED_FEES: Decimal("0"),
    }
    assert summary.current.discounts == Decimal("0")
    assert summary.current.period_cost == Decimal("320")


def test_discounts_from_debit_notes_close_cost_groups_to_period_cost() -> None:
    # Data sprzedaży Noty (1.02.2026) leży w Okresie rozliczeniowym Faktury za luty.
    repository = repository_with(
        invoice_for(
            DateRange(date(2026, 2, 1), date(2026, 2, 28)),
            "100",
            variable_gross="20",
            fixed_gross="30",
        )
    )
    repository.add_debit_note(replace(fixture_debit_note(), ppe_number=HOME))

    summary = cost_summary(repository, view("2026-02"))

    assert summary is not None
    totals = summary.current
    assert totals.period_cost == Decimal("2.30")
    assert totals.discounts == Decimal("-47.70")
    assert sum(totals.cost_groups.values()) + totals.discounts == totals.period_cost


def with_excise(invoice: Invoice, amount: str) -> Invoice:
    return replace(invoice, summary=replace(invoice.summary, excise_amount=Decimal(amount)))


def test_excise_is_shown_for_information_and_not_added_to_period_cost() -> None:
    repository = repository_with(
        with_excise(invoice_for(YEAR_2025, "3650", "7300", variable_gross="3650"), "36.50"),
        with_excise(
            invoice_for(OCTOBER_2026, "200", "300", variable_gross="20", fixed_gross="30"), "1.20"
        ),
    )

    october_2026 = cost_summary(repository, view("2026-10"))
    october_2025 = cost_summary(repository, view("2025-10"))

    assert october_2026 is not None and october_2025 is not None
    assert october_2026.excise == Decimal("1.20")
    assert october_2026.current.period_cost == Decimal("50")
    # Część Faktury rocznej po dniach: 31/365.
    assert october_2025.excise == Decimal("3.10")


def test_cost_chart_draws_invoice_for_several_months_as_flat_monthly_average() -> None:
    repository = repository_with(
        invoice_for(YEAR_2025, "3650", "7300", number="R/25", variable_gross="365"),
        invoice_for(OCTOBER_2026, "200", "300", number="M/10/26", fixed_gross="30"),
    )

    chart = monthly_chart(repository, view("2026-10"))

    assert chart is not None
    by_number = {b.invoice_number: b for b in chart.blocks}
    # Faktura roczna: 365 zł / 365 dni × 30,44 = 30,44 zł na miesiąc, przez cały okres.
    assert (by_number["R/25"].period_cost, by_number["R/25"].cost_per_month) == (
        Decimal("365"),
        Decimal("30.44"),
    )
    assert by_number["R/25"].cost_source == Source("R/25", 3)
    # Miesiąc z własną Fakturą: słupek z Kosztem okresu.
    assert (by_number["M/10/26"].cost_per_month, by_number["M/10/26"].single_month) == (
        Decimal("30"),
        True,
    )
    # Kontur roku wcześniej: te same Faktury przesunięte o 12 miesięcy.
    (earlier,) = chart.year_earlier
    assert (earlier.invoice_number, earlier.drawn) == (
        "R/25",
        DateRange(date(2025, 12, 1), date(2026, 11, 30)),
    )


def priced(invoice: Invoice, *prices: tuple[LineComponent, str, str, int]) -> Invoice:
    """Faktura z Pozycjami (składnik, jednostka, cena netto, podokres) zamiast własnych."""
    template = invoice.lines[0]
    return replace(
        invoice,
        lines=tuple(
            replace(
                template,
                component=component,
                unit=unit,
                unit_price_net=Decimal(price),
                sub_period=sub_period,
                source=Source(invoice.number, 2),
            )
            for component, unit, price, sub_period in prices
        ),
    )


SEPTEMBER_2026 = DateRange(date(2026, 9, 1), date(2026, 9, 30))


def test_unit_price_history_per_component_with_price_changes_inside_invoice() -> None:
    repository = repository_with(
        priced(
            invoice_for(SEPTEMBER_2026, "100", number="M/09/26"),
            (LineComponent.ACTIVE_ENERGY, "kWh", "0.5", 1),
            (LineComponent.CAPACITY, "mc", "10", 1),
        ),
        priced(
            invoice_for(OCTOBER_2026, "100", number="M/10/26"),
            (LineComponent.ACTIVE_ENERGY, "kWh", "0.5", 1),
            (LineComponent.ACTIVE_ENERGY, "kWh", "0.6", 2),
            (LineComponent.CAPACITY, "mc", "12", 1),
        ),
    )

    history = unit_price_history(repository, whole(HOME))

    energy = next(s for s in history if s.component is LineComponent.ACTIVE_ENERGY)
    assert energy.unit == "kWh"
    assert [
        (p.invoice_number, p.sub_period, p.sub_periods, p.price_net) for p in energy.prices
    ] == [
        ("M/09/26", 1, 1, Decimal("0.5")),
        ("M/10/26", 1, 2, Decimal("0.5")),
        ("M/10/26", 2, 2, Decimal("0.6")),
    ]
    assert energy.prices[0].source == Source("M/09/26", 2)
    capacity = next(s for s in history if s.component is LineComponent.CAPACITY)
    assert (capacity.unit, [p.price_net for p in capacity.prices]) == (
        "mc",
        [Decimal("10"), Decimal("12")],
    )


def test_invoice_list_row_has_average_price_from_period_cost_and_imported_energy() -> None:
    repository = repository_with(
        invoice_for(OCTOBER_2026, "200", "300", variable_gross="20", fixed_gross="30"),
        invoice_for(SEPTEMBER_2026, "0", "300", fixed_gross="30"),
    )

    rows = invoice_list(repository, whole(HOME))

    assert [row.average_price for row in rows] == [Decimal("0.25"), None]
