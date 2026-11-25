"""Analiza widoku Faktury („Faktura po ludzku”) na Repository w pamięci."""

from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path

from factories import invoice_for
from pv_app.domain.cost_groups import CostGroup
from pv_app.domain.debit_note import DebitNote
from pv_app.domain.invoice import DateRange, DocumentKind, Invoice, Source
from pv_app.domain.view_period import ViewPeriod
from pv_app.features.invoice_view.analysis import invoice_sheet
from pv_app.ingest import import_document
from pv_app.ingest.raw import RawDocument
from pv_app.storage.in_memory import InMemoryRepository
from pv_app.storage.repository import SourceFile

FIXTURES = Path(__file__).parent / "fixtures"
HOME = "590000000000000001"
FLAT = "590000000000000002"


def fixture_invoice(name: str) -> Invoice:
    invoice = import_document(RawDocument.from_json(FIXTURES / f"{name}.json")).invoice
    assert invoice is not None
    return invoice


def fixture_debit_note() -> DebitNote:
    note = import_document(RawDocument.from_json(FIXTURES / "debit_note_correction.json"))
    assert note.debit_note is not None
    return note.debit_note


def repository_with(*invoices: Invoice) -> InMemoryRepository:
    repository = InMemoryRepository()
    for invoice in invoices:
        repository.add_invoice(invoice)
    return repository


def test_costs_fall_into_five_cost_groups_that_add_up_to_the_period_cost() -> None:
    october = fixture_invoice("new_layout_net_metering_monthly")
    repository = repository_with(october)

    sheet = invoice_sheet(repository, HOME, october.number)

    assert sheet is not None
    assert [(g.group, g.gross) for g in sheet.cost_groups] == [
        (CostGroup.ENERGY, Decimal("0.00")),
        (CostGroup.VARIABLE_DISTRIBUTION, Decimal("0.00")),
        (CostGroup.PER_KWH_FEES, Decimal("1.90")),
        (CostGroup.CAPACITY, Decimal("18.45")),
        (CostGroup.FIXED_FEES, Decimal("11.69")),
    ]
    assert sheet.period_cost == Decimal("32.04")
    assert sheet.average_price == Decimal("0.2136")


def test_unknown_invoice_or_invoice_of_another_metering_point_has_no_sheet() -> None:
    october = fixture_invoice("new_layout_net_metering_monthly")
    repository = repository_with(october)

    assert invoice_sheet(repository, HOME, "T/NIE/MA/TAKIEJ") is None
    assert invoice_sheet(repository, FLAT, october.number) is None


def test_debit_note_of_the_period_lowers_period_cost_and_is_listed_on_the_sheet() -> None:
    half_year = fixture_invoice("new_layout_standard_half_year")
    note = fixture_debit_note()
    repository = repository_with(half_year)
    repository.add_debit_note(note)

    sheet = invoice_sheet(repository, FLAT, half_year.number)

    # Data sprzedaży Noty (1.02.2026) leży w Okresie rozliczeniowym 20.09.2025 – 9.03.2026.
    assert sheet is not None
    assert sheet.debit_notes == (note,)
    assert sum(g.gross for g in sheet.cost_groups) == Decimal("432.87")
    assert sheet.period_cost == Decimal("432.87") - Decimal("47.70")


def test_invoice_replaced_by_correcting_invoice_names_its_correction() -> None:
    correcting = fixture_invoice("old_layout_correcting_standard")
    original = replace(
        correcting,
        kind=DocumentKind.SETTLEMENT_INVOICE,
        header=replace(correcting.header, number="E/TM3/0000005/24"),
        correction=None,
    )
    repository = repository_with(original, correcting)

    replaced = invoice_sheet(repository, FLAT, original.number)
    correction = invoice_sheet(repository, FLAT, correcting.number)

    assert replaced is not None and correction is not None
    assert replaced.superseded_by == correcting.number
    assert correction.superseded_by is None
    assert correction.period_cost == Decimal("44.28")


def month(year: int, number: int) -> DateRange:
    end = date(year + number // 12, number % 12 + 1, 1)
    return DateRange(date(year, number, 1), date.fromordinal(end.toordinal() - 1))


def test_previous_and_next_invoice_follow_billing_periods_of_the_metering_point() -> None:
    august = invoice_for(month(2026, 8), "100", "200")
    september = invoice_for(month(2026, 9), "110", "210")
    october = invoice_for(month(2026, 10), "120", "220")
    repository = repository_with(october, august, september)

    first = invoice_sheet(repository, HOME, august.number)
    middle = invoice_sheet(repository, HOME, september.number)
    last = invoice_sheet(repository, HOME, october.number)

    assert first is not None and middle is not None and last is not None
    assert (first.previous_number, first.next_number) == (None, september.number)
    assert (middle.previous_number, middle.next_number) == (august.number, october.number)
    assert (last.previous_number, last.next_number) == (september.number, None)


def test_same_period_a_year_earlier_comes_from_own_invoice_and_from_tauron() -> None:
    last_year = invoice_for(month(2025, 10), "90", "200", variable_gross="5", fixed_gross="25")
    october = invoice_for(month(2026, 10), "120", "220", same_period_last_year="95")
    repository = repository_with(last_year, october)

    sheet = invoice_sheet(repository, HOME, october.number)

    assert sheet is not None
    earlier = sheet.year_earlier
    assert earlier.period == month(2025, 10)
    assert (earlier.imported_kwh, earlier.exported_kwh) == (Decimal("90"), Decimal("200"))
    assert earlier.period_cost == Decimal("30")
    assert earlier.invoice_numbers == (last_year.number,)
    assert not earlier.approximate
    assert earlier.tauron_imported_kwh == Decimal("95")
    assert earlier.tauron_source == Source(october.number, 2)


def test_same_period_a_year_earlier_is_cut_out_of_a_longer_invoice_and_marked_approximate() -> None:
    annual = invoice_for(
        DateRange(date(2024, 12, 1), date(2025, 11, 30)),
        "365",
        "730",
        variable_gross="365",
        fixed_gross="120",
    )
    october = invoice_for(month(2026, 10), "120", "220")
    repository = repository_with(annual, october)

    sheet = invoice_sheet(repository, HOME, october.number)

    # Rozkład na miesiące: kWh i Składniki zmienne po dniach (31 z 365), stałe po równo (1/12).
    assert sheet is not None
    earlier = sheet.year_earlier
    assert (earlier.imported_kwh, earlier.exported_kwh) == (Decimal("31"), Decimal("62"))
    assert earlier.period_cost == Decimal("41")
    assert earlier.invoice_numbers == (annual.number,)
    assert earlier.approximate


def test_same_period_a_year_earlier_without_own_invoices_keeps_only_tauron_value() -> None:
    october = invoice_for(month(2026, 10), "120", "220", same_period_last_year="95")
    repository = repository_with(
        invoice_for(DateRange(date(2025, 10, 10), date(2025, 10, 31)), "70"), october
    )

    sheet = invoice_sheet(repository, HOME, october.number)

    assert sheet is not None
    earlier = sheet.year_earlier
    assert (earlier.imported_kwh, earlier.period_cost, earlier.invoice_numbers) == (None, None, ())
    assert earlier.tauron_imported_kwh == Decimal("95")


def test_sheet_points_to_the_archived_pdf_of_the_invoice() -> None:
    october = fixture_invoice("new_layout_net_metering_monthly")
    repository = repository_with(october)
    source_file = SourceFile("ab" * 32, "faktura.pdf", "abababababab-faktura.pdf", october.number)
    repository.add_source_file(source_file)

    sheet = invoice_sheet(repository, HOME, october.number)

    assert sheet is not None
    assert sheet.source_file == source_file


def test_overview_period_is_the_smallest_view_period_holding_the_billing_period() -> None:
    october = invoice_for(month(2026, 10), "120")
    autumn = invoice_for(DateRange(date(2026, 7, 1), date(2026, 9, 30)), "300")
    half_year = invoice_for(DateRange(date(2025, 3, 22), date(2025, 9, 19)), "600")
    winter = invoice_for(DateRange(date(2025, 9, 20), date(2026, 3, 9)), "600")
    repository = repository_with(october, autumn, half_year, winter)

    periods = [
        sheet.overview_period.to_query()
        for invoice in (october, autumn, half_year, winter)
        if (sheet := invoice_sheet(repository, HOME, invoice.number)) is not None
    ]

    assert periods == ["2026-10", "2026-K3", "2025", ViewPeriod.whole().to_query()]
