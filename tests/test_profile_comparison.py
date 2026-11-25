"""Porównanie Profilu godzinowego z Fakturami na stronie „Dane”, na Repository w pamięci (ADR 0003:
różnicę się pokazuje, nie wyrównuje)."""

from datetime import date, datetime
from decimal import Decimal

from factories import HOME, correcting, days, invoice_for, reading
from pv_app.domain.hourly_profile import HourlyReading
from pv_app.domain.invoice import DateRange, Invoice
from pv_app.features.profile_comparison.analysis import profile_comparison
from pv_app.storage.in_memory import InMemoryRepository

OCTOBER = DateRange(date(2026, 10, 1), date(2026, 10, 31))


def repository_with(invoices: list[Invoice], readings: list[HourlyReading]) -> InMemoryRepository:
    repository = InMemoryRepository()
    for invoice in invoices:
        repository.add_invoice(invoice)
    repository.add_hourly_readings(readings)
    return repository


def test_matching_period_shows_both_sums_and_small_difference() -> None:
    # Październik: 31 dni, w tym 25.10 z 25 godzinami = 745 godzin × 0,5 / 0,25 kWh.
    invoice = invoice_for(OCTOBER, "370", "186.5", number="T/1")
    repository = repository_with([invoice], days(OCTOBER.start, OCTOBER.end))

    comparison = profile_comparison(repository, HOME)

    assert comparison is not None
    (period,) = comparison.periods
    assert period.invoice_number == "T/1"
    assert period.missing_days == 0
    assert period.imported is not None and period.exported is not None
    assert (period.imported.invoice_kwh, period.imported.profile_kwh) == (
        Decimal("370"),
        Decimal("372.5"),
    )
    assert period.imported.difference_kwh == Decimal("2.5")
    assert round(period.imported.difference_percent or 0, 2) == Decimal("0.68")
    assert period.exported.difference_kwh == Decimal("-0.25")
    assert not period.to_check


def test_difference_above_two_percent_marks_period_to_check() -> None:
    # Profil: 372,5 kWh pobranej; Faktura 360 → +3,5%. Energia oddana zgodna.
    invoice = invoice_for(OCTOBER, "360", "186.25", number="T/1")
    repository = repository_with([invoice], days(OCTOBER.start, OCTOBER.end))

    comparison = profile_comparison(repository, HOME)

    assert comparison is not None
    (period,) = comparison.periods
    assert period.imported is not None and period.exported is not None
    assert period.imported.exceeds_threshold
    assert not period.exported.exceeds_threshold
    assert period.to_check


def test_difference_of_exactly_two_percent_is_not_to_check() -> None:
    # 10 dni × 24 godziny × 1,0625 kWh = 255 kWh wobec 250 z Faktury: dokładnie 2%.
    june = DateRange(date(2026, 6, 1), date(2026, 6, 10))
    invoice = invoice_for(june, "250", "60", number="T/1")
    readings = days(june.start, june.end, imported="1.0625", exported="0.25")

    comparison = profile_comparison(repository_with([invoice], readings), HOME)

    assert comparison is not None
    (period,) = comparison.periods
    assert period.imported is not None
    assert period.imported.difference_percent == Decimal(2)
    assert not period.to_check


def test_partially_covered_period_shows_missing_days_instead_of_difference() -> None:
    invoice = invoice_for(OCTOBER, "370", "186.5", number="T/1")
    readings = days(date(2026, 10, 1), date(2026, 10, 20))

    comparison = profile_comparison(repository_with([invoice], readings), HOME)

    assert comparison is not None
    (period,) = comparison.periods
    assert period.missing_days == 11
    assert period.imported is None and period.exported is None
    assert not period.to_check


def test_hour_ending_at_midnight_belongs_to_the_previous_day() -> None:
    # Godzina „0:00” 1.11 zamyka 31.10, a „0:00” 1.10 należy do 30.09, poza okresem.
    invoice = invoice_for(OCTOBER, "372.5", "186.25", number="T/1")
    september_last = reading(datetime(2026, 10, 1, 0), imported="100")
    november_first = reading(datetime(2026, 11, 1, 1), imported="100")
    readings = [september_last, *days(OCTOBER.start, OCTOBER.end), november_first]

    comparison = profile_comparison(repository_with([invoice], readings), HOME)

    assert comparison is not None
    (period,) = comparison.periods
    assert period.missing_days == 0
    assert period.imported is not None
    assert period.imported.profile_kwh == Decimal("372.5")
    assert not period.to_check


def test_day_with_25_hours_needs_the_extra_hour_to_be_complete() -> None:
    day = DateRange(date(2026, 10, 25), date(2026, 10, 25))
    invoice = invoice_for(day, "12.5", "6.25", number="T/1")
    full = days(day.start, day.end)
    without_extra = [r for r in full if not r.extra_hour]

    complete = profile_comparison(repository_with([invoice], full), HOME)
    incomplete = profile_comparison(repository_with([invoice], without_extra), HOME)

    assert complete is not None and incomplete is not None
    (period,) = complete.periods
    assert period.missing_days == 0
    assert period.imported is not None and period.imported.profile_kwh == Decimal("12.5")
    assert incomplete.periods[0].missing_days == 1


def test_day_with_23_hours_is_complete() -> None:
    day = DateRange(date(2026, 3, 29), date(2026, 3, 29))
    invoice = invoice_for(day, "11.5", "5.75", number="T/1")

    comparison = profile_comparison(repository_with([invoice], days(day.start, day.end)), HOME)

    assert comparison is not None
    assert comparison.periods[0].missing_days == 0


def test_superseded_invoices_and_periods_without_profile_are_left_out() -> None:
    september = DateRange(date(2026, 9, 1), date(2026, 9, 30))
    old = invoice_for(september, "300", "100", number="T/0")
    invoice = invoice_for(OCTOBER, "372.5", "186.25", number="T/1")
    corrected = correcting(invoice, "K/1")

    comparison = profile_comparison(
        repository_with([old, invoice, corrected], days(OCTOBER.start, OCTOBER.end)), HOME
    )

    assert comparison is not None
    assert [p.invoice_number for p in comparison.periods] == ["K/1"]
    assert comparison.without_profile == 1


def test_metering_point_without_profile_has_no_comparison() -> None:
    invoice = invoice_for(OCTOBER, "370", "186.5", number="T/1")

    assert profile_comparison(repository_with([invoice], []), HOME) is None
