"""Oś czasu Faktur na stronie danych: luki, nakładanie się, korekty, Noty, Prognozy i odczyty
szacunkowe, na Repository w pamięci; „dziś” podawane z zewnątrz."""

from dataclasses import replace
from datetime import date
from decimal import Decimal

from factories import HOME, correcting, forecast, invoice_for
from pv_app.domain.debit_note import DebitNote, DebitNoteItem
from pv_app.domain.invoice import (
    DateRange,
    DocumentKind,
    Invoice,
    ReadingType,
    SettlementBasis,
    Source,
)
from pv_app.domain.view_period import month_label
from pv_app.features.invoice_timeline.analysis import invoice_timeline
from pv_app.storage.in_memory import InMemoryRepository

TODAY = date(2026, 11, 25)


def repository_with(*invoices: Invoice) -> InMemoryRepository:
    repository = InMemoryRepository()
    for invoice in invoices:
        repository.add_invoice(invoice)
    return repository


def month(year: int, month_: int, last: int, number: str) -> Invoice:
    return invoice_for(
        DateRange(date(year, month_, 1), date(year, month_, last)), "100", number=number
    )


def estimated(invoice: Invoice) -> Invoice:
    return replace(
        invoice,
        readings=tuple(replace(r, reading_type=ReadingType.ESTIMATED) for r in invoice.readings),
    )


def note(number: str, sale_date: date) -> DebitNote:
    return DebitNote(
        number=number,
        corrected_note_number=None,
        issue_date=date(2026, 11, 1),
        sale_date=sale_date,
        ppe_number=HOME,
        items=(DebitNoteItem("Obniżka kwoty należności", Decimal("5.00"), Decimal("5.00")),),
        amount_due=Decimal("-5.00"),
        due_date=None,
        source=Source(number, 1),
    )


def test_days_between_invoices_without_invoice_are_a_gap() -> None:
    repository = repository_with(
        month(2026, 7, 31, "T/07"),
        month(2026, 10, 31, "T/10"),
    )

    timeline = invoice_timeline(repository, HOME, TODAY)

    assert timeline is not None
    assert timeline.gaps == (DateRange(date(2026, 8, 1), date(2026, 9, 30)),)


def test_invoices_sharing_days_are_an_overlap_not_a_gap() -> None:
    repository = repository_with(
        invoice_for(DateRange(date(2026, 1, 1), date(2026, 6, 30)), "600", number="T/H1"),
        month(2026, 6, 30, "T/06"),
        month(2026, 7, 31, "T/07"),
    )

    timeline = invoice_timeline(repository, HOME, TODAY)

    assert timeline is not None
    assert timeline.gaps == ()
    [overlap] = timeline.overlaps
    assert overlap.period == DateRange(date(2026, 6, 1), date(2026, 6, 30))
    assert overlap.invoice_numbers == ("T/H1", "T/06")


def test_each_invoice_is_a_period_with_settlement_basis_and_correction() -> None:
    september = estimated(month(2026, 9, 30, "T/09"))
    repository = repository_with(
        september, correcting(september, "K/09"), month(2026, 10, 31, "T/10")
    )

    timeline = invoice_timeline(repository, HOME, TODAY)

    assert timeline is not None
    assert timeline.overlaps == ()
    rows = {p.number: (p.basis, p.corrects, p.superseded_by) for p in timeline.periods}
    assert rows == {
        "T/09": (SettlementBasis.ESTIMATED_READING, None, "K/09"),
        "K/09": (SettlementBasis.ACTUAL_READING, "T/09", None),
        "T/10": (SettlementBasis.ACTUAL_READING, None, None),
    }
    assert [p.number for p in timeline.periods if p.kind is DocumentKind.CORRECTING_INVOICE] == [
        "K/09"
    ]


def test_counts_months_of_last_twelve_settled_on_estimated_reading() -> None:
    repository = repository_with(
        estimated(month(2025, 10, 31, "T/2510")),
        estimated(
            invoice_for(DateRange(date(2025, 12, 1), date(2026, 1, 31)), "200", number="T/2512")
        ),
        month(2026, 2, 28, "T/2602"),
        estimated(month(2026, 3, 31, "T/2603")),
        estimated(month(2026, 11, 30, "T/2611")),
    )

    timeline = invoice_timeline(repository, HOME, TODAY)

    assert timeline is not None
    estimate = timeline.estimated_months
    assert estimate.window == DateRange(date(2025, 11, 1), date(2026, 10, 31))
    assert [month_label(m) for m in estimate.months] == [
        "grudzień 2025",
        "styczeń 2026",
        "marzec 2026",
    ]


def test_estimated_month_stays_estimated_after_correcting_invoice_on_actual_reading() -> None:
    september = estimated(month(2026, 9, 30, "T/09"))
    repository = repository_with(september, correcting(september, "K/09"))

    timeline = invoice_timeline(repository, HOME, TODAY)

    assert timeline is not None
    assert [month_label(m) for m in timeline.estimated_months.months] == ["wrzesień 2026"]


def test_shows_debit_notes_and_only_forecasts_after_last_invoice() -> None:
    october = replace(
        month(2026, 10, 31, "T/10"),
        forecasts=(
            forecast(
                "T/10/1", DateRange(date(2026, 10, 1), date(2026, 10, 31)), date(2026, 10, 15)
            ),
            forecast(
                "T/10/2", DateRange(date(2026, 11, 1), date(2026, 12, 31)), date(2026, 11, 15)
            ),
        ),
    )
    repository = repository_with(month(2026, 9, 30, "T/09"), october)
    repository.add_debit_note(note("N/1", sale_date=date(2026, 9, 20)))
    repository.add_debit_note(note("N/2", sale_date=date(2025, 1, 20)))

    timeline = invoice_timeline(repository, HOME, TODAY)

    assert timeline is not None
    assert [(f.forecast_number, f.period.end) for f in timeline.forecasts] == [
        ("T/10/2", date(2026, 12, 31))
    ]
    assert [(n.number, n.sale_date, n.invoice_number) for n in timeline.debit_notes] == [
        ("N/2", date(2025, 1, 20), None),
        ("N/1", date(2026, 9, 20), "T/09"),
    ]


def test_months_of_last_twelve_without_invoice_are_counted_apart_from_estimates() -> None:
    repository = repository_with(
        estimated(month(2026, 8, 31, "T/08")),
        month(2026, 9, 30, "T/09"),
    )

    timeline = invoice_timeline(repository, HOME, TODAY)

    assert timeline is not None
    assert [month_label(m) for m in timeline.estimated_months.months] == ["sierpień 2026"]
    assert len(timeline.estimated_months.without_invoice) == 10
    assert month_label(timeline.estimated_months.without_invoice[-1]) == "październik 2026"
