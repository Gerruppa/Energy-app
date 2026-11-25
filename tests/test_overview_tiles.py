"""Górna część Przeglądu (status Faktur, Saldo, najbliższa płatność, ostatnia Faktura) na
Repository w pamięci; „dziś” podawane z zewnątrz."""

from dataclasses import replace
from datetime import date
from decimal import Decimal

from factories import HOME, forecast, invoice_for
from pv_app.domain.debit_note import DebitNote, DebitNoteItem
from pv_app.domain.invoice import (
    Amount,
    Correction,
    DateRange,
    DocumentKind,
    Forecast,
    Invoice,
    ReadingType,
    SettlementBasis,
    Source,
)
from pv_app.domain.view_period import ViewPeriod
from pv_app.features.base import Filters
from pv_app.features.overview.tiles import (
    StatusKind,
    balance,
    invoice_status,
    last_invoice,
    next_payment,
)
from pv_app.storage.in_memory import InMemoryRepository

OCTOBER_2026 = DateRange(date(2026, 10, 1), date(2026, 10, 31))


def repository_with(*invoices: Invoice) -> InMemoryRepository:
    repository = InMemoryRepository()
    for invoice in invoices:
        repository.add_invoice(invoice)
    return repository


def refund_note(number: str, issued: date, refund: str) -> DebitNote:
    """Nota obciążeniowa zwracająca ``refund`` zł (ujemne do zapłaty)."""
    return DebitNote(
        number=number,
        corrected_note_number=None,
        issue_date=issued,
        sale_date=issued,
        ppe_number=HOME,
        items=(DebitNoteItem("Obniżka kwoty należności", Decimal(refund), Decimal(0)),),
        amount_due=-Decimal(refund),
        due_date=None,
        source=Source(number, 1),
    )


def monthly(period: DateRange, number: str) -> Invoice:
    invoice = invoice_for(period, "150", "300", number=number)
    return replace(invoice, header=replace(invoice.header, billing_frequency_months=1))


def test_monthly_invoices_are_current_until_two_weeks_after_next_month() -> None:
    repository = repository_with(monthly(OCTOBER_2026, "M/10/26"))

    status = invoice_status(repository, HOME, today=date(2026, 12, 14))

    assert status is not None
    assert status.kind is StatusKind.CURRENT
    assert status.expected_period == DateRange(date(2026, 11, 1), date(2026, 11, 30))
    assert status.expected_by == date(2026, 12, 14)


def test_invoice_is_missing_two_weeks_after_the_expected_period() -> None:
    repository = repository_with(monthly(OCTOBER_2026, "M/10/26"))

    status = invoice_status(repository, HOME, today=date(2026, 12, 15))

    assert status is not None
    assert status.kind is StatusKind.MISSING
    assert status.expected_period == DateRange(date(2026, 11, 1), date(2026, 11, 30))


def test_without_monthly_billing_next_invoice_is_expected_after_the_forecast_schedule() -> None:
    half_year = DateRange(date(2026, 3, 1), date(2026, 8, 31))
    invoice = invoice_for(half_year, "400", number="P/26")
    invoice = replace(
        invoice,
        header=replace(invoice.header, billing_frequency_months=6),
        forecasts=(
            forecast("P/26/1", DateRange(date(2026, 9, 1), date(2026, 10, 31)), date(2026, 9, 15)),
            forecast("P/26/2", DateRange(date(2026, 11, 1), date(2027, 2, 28)), date(2026, 11, 15)),
        ),
    )
    repository = repository_with(invoice)

    status = invoice_status(repository, HOME, today=date(2027, 3, 1))

    assert status is not None
    assert status.kind is StatusKind.CURRENT
    assert status.expected_period == DateRange(date(2026, 9, 1), date(2027, 2, 28))
    assert status.expected_by == date(2027, 3, 14)


def test_last_invoice_on_estimated_reading_is_flagged() -> None:
    invoice = monthly(OCTOBER_2026, "M/10/26")
    estimated = replace(
        invoice,
        readings=tuple(replace(r, reading_type=ReadingType.ESTIMATED) for r in invoice.readings),
    )
    repository = repository_with(estimated)

    status = invoice_status(repository, HOME, today=date(2026, 11, 20))

    assert status is not None
    assert status.kind is StatusKind.ESTIMATED
    assert status.last_invoice == "M/10/26"


def with_balance(invoice: Invoice, balance: str | None, amount_due: str = "0.00") -> Invoice:
    return replace(
        invoice,
        summary=replace(
            invoice.summary,
            account_balance=Decimal(balance) if balance is not None else None,
            amount_due=Decimal(amount_due),
        ),
    )


def view(query: str) -> Filters:
    period = ViewPeriod.from_query(query)
    assert period is not None
    return Filters(ppe_number=HOME, view_period=period)


SEPTEMBER_2026 = DateRange(date(2026, 9, 1), date(2026, 9, 30))


def test_balance_at_end_of_view_period_is_from_the_last_invoice_ended_by_then() -> None:
    repository = repository_with(
        with_balance(monthly(SEPTEMBER_2026, "M/09/26"), "200.00"),
        with_balance(monthly(OCTOBER_2026, "M/10/26"), "-35.50"),
    )

    september = balance(repository, view("2026-09"))
    latest = balance(repository, view("caly"))

    assert september is not None and latest is not None
    assert (september.amount, september.invoice_number) == (Decimal("200.00"), "M/09/26")
    assert september.from_account
    assert (latest.amount, latest.invoice_number) == (Decimal("-35.50"), "M/10/26")
    assert latest.source == Source("M/10/26", 3)


def test_debit_note_issued_after_the_invoice_changes_the_balance() -> None:
    invoice = with_balance(monthly(OCTOBER_2026, "M/10/26"), "100.00")
    invoice = replace(invoice, header=replace(invoice.header, issue_date=date(2026, 11, 5)))
    repository = repository_with(invoice)
    repository.add_debit_note(refund_note("N/1", issued=date(2026, 11, 20), refund="25.00"))
    repository.add_debit_note(refund_note("N/0", issued=date(2026, 11, 1), refund="7.00"))

    result = balance(repository, view("caly"))

    assert result is not None
    assert result.amount == Decimal("125.00")
    assert result.debit_notes == ("N/1",)


def test_without_balance_on_the_invoice_only_amount_due_is_known() -> None:
    repository = repository_with(with_balance(monthly(OCTOBER_2026, "R/26"), None, "-66.67"))

    result = balance(repository, view("caly"))

    assert result is not None
    assert result.amount == Decimal("66.67")
    assert not result.from_account


def test_no_balance_before_the_first_invoice_ends() -> None:
    repository = repository_with(with_balance(monthly(OCTOBER_2026, "M/10/26"), "1.00"))

    assert balance(repository, view("2026-09")) is None


HALF_YEAR = DateRange(date(2026, 3, 1), date(2026, 8, 31))


def with_forecasts(invoice: Invoice, *forecasts: Forecast) -> Invoice:
    return replace(invoice, forecasts=forecasts)


def test_next_payment_is_the_earliest_forecast_not_yet_due() -> None:
    invoice = with_forecasts(
        invoice_for(HALF_YEAR, "400", number="P/26"),
        forecast("P/26/1", DateRange(date(2026, 9, 1), date(2026, 10, 31)), date(2026, 9, 15)),
        forecast(
            "P/26/2",
            DateRange(date(2026, 11, 1), date(2026, 12, 31)),
            date(2026, 11, 16),
            gross="90.00",
            balance_adjustment="-30.00",
        ),
    )
    repository = repository_with(invoice)

    payment = next_payment(repository, HOME, today=date(2026, 9, 16))

    assert payment is not None
    assert payment.amount == Decimal("60.00")
    assert payment.due_date == date(2026, 11, 16)
    assert payment.forecast_number == "P/26/2"
    assert payment.overpayment_used == Decimal("30.00")
    assert not payment.nothing_to_pay


def test_forecast_covered_by_overpayment_is_nothing_to_pay() -> None:
    invoice = with_forecasts(
        invoice_for(HALF_YEAR, "400", number="P/26"),
        forecast(
            "P/26/1",
            DateRange(date(2026, 9, 1), date(2026, 10, 31)),
            date(2026, 9, 15),
            gross="90.00",
            balance_adjustment="-500.00",
        ),
    )

    payment = next_payment(repository_with(invoice), HOME, today=date(2026, 9, 1))

    assert payment is not None
    assert payment.nothing_to_pay
    assert payment.overpayment_used == Decimal("90.00")


def test_without_forecasts_the_last_invoice_amount_due_is_the_next_payment() -> None:
    covered = with_balance(monthly(SEPTEMBER_2026, "M/09/26"), "50.00", "0.00")
    due = with_balance(monthly(OCTOBER_2026, "M/10/26"), "-20.00", "20.00")

    covered_payment = next_payment(repository_with(covered), HOME, today=date(2026, 10, 5))
    due_payment = next_payment(repository_with(covered, due), HOME, today=date(2026, 11, 5))

    assert covered_payment is not None and covered_payment.nothing_to_pay
    assert covered_payment.forecast_number is None
    assert due_payment is not None
    assert (due_payment.amount, due_payment.due_date) == (Decimal("20.00"), None)
    assert due_payment.source == Source("M/10/26", 3)


def test_no_next_payment_after_the_forecast_schedule_ends() -> None:
    invoice = with_forecasts(
        invoice_for(HALF_YEAR, "400", number="P/26"),
        forecast("P/26/1", DateRange(date(2026, 9, 1), date(2026, 10, 31)), date(2026, 9, 15)),
    )

    assert next_payment(repository_with(invoice), HOME, today=date(2026, 9, 16)) is None


def test_last_invoice_tile_shows_period_cost_after_correction_and_debit_note() -> None:
    original = monthly(OCTOBER_2026, "M/10/26")
    correction = replace(
        invoice_for(OCTOBER_2026, "150", "300", number="K/10/26", fixed_gross="80.00"),
        kind=DocumentKind.CORRECTING_INVOICE,
        correction=Correction(
            corrected_invoice_number="M/10/26",
            corrected_invoice_issue_date=date(2026, 11, 5),
            reason="błędny odczyt",
            charged_result=Amount(None, None, Decimal("0")),
            charged_amount_due=Decimal("0"),
            difference=Decimal("0"),
            source=Source("K/10/26", 1),
            difference_source=Source("K/10/26", 2),
        ),
    )
    repository = repository_with(original, correction)
    note = refund_note("N/1", issued=date(2026, 11, 20), refund="5.00")
    repository.add_debit_note(
        replace(
            note,
            sale_date=date(2026, 10, 15),
            items=(DebitNoteItem("Obniżka kwoty należności", Decimal("5.00"), Decimal("5.00")),),
        )
    )

    tile = last_invoice(repository, view("2026-10"))

    assert tile is not None
    assert tile.number == "K/10/26"
    assert tile.period == OCTOBER_2026
    # Wynik rozliczenia 80,00 zł minus bonifikata 5,00 zł z Noty za ten okres.
    assert tile.period_cost == Decimal("75.00")
    assert tile.basis is SettlementBasis.ACTUAL_READING
    assert (tile.imported_kwh, tile.exported_kwh) == (Decimal("150"), Decimal("300"))
    assert last_invoice(repository, view("2026-09")) is None


def test_after_a_correcting_invoice_next_payment_follows_the_corrected_schedule() -> None:
    original = with_forecasts(
        invoice_for(HALF_YEAR, "400", number="P/26"),
        forecast("P/26/1", DateRange(date(2026, 9, 1), date(2026, 10, 31)), date(2026, 9, 15)),
    )
    correction = replace(
        with_balance(invoice_for(HALF_YEAR, "390", number="K/26"), None, "-12.30"),
        kind=DocumentKind.CORRECTING_INVOICE,
        correction=Correction(
            corrected_invoice_number="P/26",
            corrected_invoice_issue_date=date(2026, 9, 5),
            reason="błędny odczyt",
            charged_result=Amount(None, None, Decimal("0")),
            charged_amount_due=Decimal("0"),
            difference=Decimal("-12.30"),
            source=Source("K/26", 1),
            difference_source=Source("K/26", 2),
        ),
    )

    payment = next_payment(repository_with(original, correction), HOME, today=date(2026, 9, 10))

    assert payment is not None
    assert (payment.forecast_number, payment.due_date) == ("P/26/1", date(2026, 9, 15))
