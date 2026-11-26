"""Saldo w czasie i sygnał rosnącej nadpłaty na Repository w pamięci; liczby wymyślone."""

from dataclasses import replace
from datetime import date
from decimal import Decimal

from factories import HOME, correcting, forecast, invoice_for
from pv_app.domain.debit_note import DebitNote, DebitNoteItem
from pv_app.domain.invoice import DateRange, Invoice, ReadingType, SettlementBasis, Source
from pv_app.domain.view_period import ViewPeriod
from pv_app.features.balance import balance_history
from pv_app.features.base import Filters
from pv_app.features.overview.tiles import overpayment_signal
from pv_app.storage.in_memory import InMemoryRepository


def month(year: int, number: int) -> DateRange:
    start = date(year, number, 1)
    end = date(year + number // 12, number % 12 + 1, 1)
    return DateRange(start, date.fromordinal(end.toordinal() - 1))


def settled(
    period: DateRange,
    balance: str | None,
    *,
    issued: date | None = None,
    amount_due: str = "0.00",
    cost: str = "40.00",
) -> Invoice:
    """Miesięczna Faktura z Saldem ``balance`` (``None``: Faktura go nie podaje), wystawiona
    domyślnie 5 dni po końcu okresu."""
    number = f"S/{period.start:%Y%m}"
    invoice = invoice_for(period, "150", "300", number=number, fixed_gross=cost)
    issue_date = issued or date.fromordinal(period.end.toordinal() + 5)
    return replace(
        invoice,
        header=replace(invoice.header, issue_date=issue_date, billing_frequency_months=1),
        summary=replace(
            invoice.summary,
            account_balance=Decimal(balance) if balance is not None else None,
            amount_due=Decimal(amount_due),
        ),
    )


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


def repository_with(*invoices: Invoice, notes: tuple[DebitNote, ...] = ()) -> InMemoryRepository:
    repository = InMemoryRepository()
    for invoice in invoices:
        repository.add_invoice(invoice)
    for note in notes:
        repository.add_debit_note(note)
    return repository


def test_balance_after_each_invoice_with_its_source_and_settlement_basis() -> None:
    estimated = settled(month(2026, 10), "130.00")
    estimated = replace(
        estimated,
        readings=tuple(replace(r, reading_type=ReadingType.ESTIMATED) for r in estimated.readings),
    )
    repository = repository_with(estimated, settled(month(2026, 9), "120.00"))

    points = balance_history(repository, HOME)

    assert [(p.day, p.amount, p.document, p.source, p.basis) for p in points] == [
        (
            date(2026, 10, 5),
            Decimal("120.00"),
            "S/202609",
            Source("S/202609", 3),
            SettlementBasis.ACTUAL_READING,
        ),
        (
            date(2026, 11, 5),
            Decimal("130.00"),
            "S/202610",
            Source("S/202610", 3),
            SettlementBasis.ESTIMATED_READING,
        ),
    ]
    assert all(p.from_account and not p.is_debit_note for p in points)


def test_invoice_without_balance_gives_only_amount_due_or_refund() -> None:
    repository = repository_with(settled(month(2026, 10), None, amount_due="-66.67"))

    [point] = balance_history(repository, HOME)

    assert point.amount == Decimal("66.67")
    assert not point.from_account


def test_debit_note_between_invoices_changes_the_balance_from_its_issue_date() -> None:
    repository = repository_with(
        settled(month(2026, 9), "100.00"),
        settled(month(2026, 10), "90.00"),
        notes=(
            refund_note("N/2", issued=date(2026, 10, 20), refund="5.00"),
            refund_note("N/1", issued=date(2026, 10, 10), refund="25.00"),
            refund_note("N/0", issued=date(2026, 9, 20), refund="7.00"),
        ),
    )

    points = balance_history(repository, HOME)

    assert [(p.day, p.document, p.amount, p.is_debit_note) for p in points] == [
        (date(2026, 10, 5), "S/202609", Decimal("100.00"), False),
        (date(2026, 10, 10), "N/1", Decimal("125.00"), True),
        (date(2026, 10, 20), "N/2", Decimal("130.00"), True),
        (date(2026, 11, 5), "S/202610", Decimal("90.00"), False),
    ]
    assert points[1].source == Source("N/1", 1)


def test_debit_note_after_invoice_without_balance_has_no_made_up_state() -> None:
    repository = repository_with(
        settled(month(2026, 10), None, amount_due="12.00"),
        notes=(refund_note("N/1", issued=date(2026, 11, 20), refund="25.00"),),
    )

    assert [p.document for p in balance_history(repository, HOME)] == ["S/202610"]


def test_correcting_invoice_replaces_corrected_one_and_points_to_its_difference_page() -> None:
    original = settled(month(2026, 9), None, amount_due="30.00")
    correction = correcting(original, "K/1")
    assert correction.correction is not None
    correction = replace(
        correction, correction=replace(correction.correction, difference=Decimal("-8.00"))
    )
    repository = repository_with(original, correction)

    [point] = balance_history(repository, HOME)

    assert (point.document, point.amount, point.source) == (
        "K/1",
        Decimal("8.00"),
        Source("K/1", 2),
    )


def whole() -> Filters:
    period = ViewPeriod.from_query("caly")
    assert period is not None
    return Filters(ppe_number=HOME, view_period=period)


TODAY = date(2026, 11, 26)


def with_schedule(invoice: Invoice, amount_due: str = "40.00") -> Invoice:
    """Harmonogram Prognoz na grudzień i styczeń; ``amount_due`` z każdej do zapłaty."""
    adjustment = str(Decimal(amount_due) - Decimal("100.00"))
    return replace(
        invoice,
        forecasts=(
            forecast(
                f"{invoice.number}/1",
                month(2026, 12),
                date(2026, 12, 15),
                "100.00",
                balance_adjustment=adjustment,
            ),
            forecast(
                f"{invoice.number}/2",
                month(2027, 1),
                date(2027, 1, 15),
                "100.00",
                balance_adjustment=adjustment,
            ),
        ),
    )


def rising(*balances: str, forecasts_due: str | None = "40.00") -> InMemoryRepository:
    """Faktury za kolejne miesiące od lipca 2026 z ``balances`` i Kosztem okresu 40 zł;
    ostatnia z harmonogramem Prognoz, z których każda ma ``forecasts_due`` do zapłaty
    (``None``: bez harmonogramu)."""
    invoices = [settled(month(2026, 7 + i), b) for i, b in enumerate(balances)]
    if forecasts_due is not None:
        invoices[-1] = with_schedule(invoices[-1], forecasts_due)
    return repository_with(*invoices)


def test_overpayment_rising_on_three_last_invoices_with_forecasts_due_gives_signal() -> None:
    repository = rising("100.00", "200.00", "300.00", "400.00")

    signal = overpayment_signal(repository, whole(), TODAY)

    assert signal is not None
    assert signal.overpayment == Decimal("400.00")
    assert signal.invoices == ("S/202608", "S/202609", "S/202610")
    assert signal.average_monthly_cost == Decimal("40.00")
    assert signal.cost_months == 4
    assert signal.months_covered == 10


def test_no_signal_when_overpayment_falls_on_the_last_invoice() -> None:
    assert (
        overpayment_signal(rising("100.00", "200.00", "300.00", "290.00"), whole(), TODAY) is None
    )


def test_no_signal_after_only_two_rises() -> None:
    assert overpayment_signal(rising("200.00", "300.00", "400.00"), whole(), TODAY) is None


def test_no_signal_when_underpayment_shrinks() -> None:
    repository = rising("-400.00", "-300.00", "-200.00", "-100.00")

    assert overpayment_signal(repository, whole(), TODAY) is None


def test_no_signal_when_one_of_the_invoices_has_no_balance() -> None:
    repository = repository_with(
        settled(month(2026, 7), "100.00"),
        settled(month(2026, 8), None, amount_due="-150.00"),
        settled(month(2026, 9), "300.00"),
        with_schedule(settled(month(2026, 10), "400.00")),
    )

    assert overpayment_signal(repository, whole(), TODAY) is None


def test_no_signal_without_forecasts_or_when_they_need_no_payment() -> None:
    without = rising("100.00", "200.00", "300.00", "400.00", forecasts_due=None)
    covered = rising("100.00", "200.00", "300.00", "400.00", forecasts_due="0.00")

    assert overpayment_signal(without, whole(), TODAY) is None
    assert overpayment_signal(covered, whole(), TODAY) is None
    assert overpayment_signal(rising("1", "2", "3", "4"), whole(), date(2027, 2, 1)) is None


def test_debit_note_between_invoices_does_not_break_the_rise_and_counts_in_overpayment() -> None:
    repository = rising("100.00", "200.00", "300.00", "400.00")
    repository.add_debit_note(refund_note("N/1", issued=date(2026, 9, 20), refund="500.00"))
    repository.add_debit_note(refund_note("N/2", issued=date(2026, 11, 20), refund="40.00"))

    signal = overpayment_signal(repository, whole(), TODAY)

    assert signal is not None
    assert signal.overpayment == Decimal("440.00")
    assert signal.months_covered == 11


def test_signal_follows_the_view_period() -> None:
    # Do października nadpłata spadła w sierpniu; od sierpnia do listopada rośnie.
    balances = ("300.00", "100.00", "200.00", "300.00", "400.00")
    invoices = [settled(month(2026, 7 + i), b) for i, b in enumerate(balances)]
    repository = repository_with(*invoices[:3], *(with_schedule(i) for i in invoices[3:]))
    october = ViewPeriod.from_query("2026-10")
    assert october is not None

    assert overpayment_signal(repository, Filters(HOME, october), TODAY) is None
    assert overpayment_signal(repository, whole(), TODAY) is not None


def test_rise_may_start_from_underpayment() -> None:
    signal = overpayment_signal(rising("-50.00", "10.00", "20.00", "30.00"), whole(), TODAY)

    assert signal is not None and signal.invoices == ("S/202608", "S/202609", "S/202610")
