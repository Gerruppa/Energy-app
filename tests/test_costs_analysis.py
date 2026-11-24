"""Analiza zakładki Koszty i Faktury na Repository w pamięci."""

from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path

from pv_app.domain.debit_note import DebitNote
from pv_app.domain.invoice import (
    DateRange,
    DocumentKind,
    Invoice,
    ReadingType,
    SettlementBasis,
    Source,
)
from pv_app.domain.view_period import ViewPeriod
from pv_app.features.base import Filters
from pv_app.features.costs.analysis import (
    DebitNoteListRow,
    InvoiceListRow,
    debit_note_list,
    invoice_list,
)
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
