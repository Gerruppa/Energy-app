"""Zakładka Dzień po dniu: dni w Okresie widoku, godziny dnia i Typowa doba, na Repository
w pamięci. Ilości po Zbilansowaniu godzinowym."""

from datetime import date, datetime
from decimal import Decimal

from factories import HOME, days, invoice_for, reading
from pv_app.domain.hourly_profile import HourlyReading
from pv_app.domain.invoice import DateRange
from pv_app.domain.view_period import ViewPeriod, ViewPeriodKind
from pv_app.features.base import Filters, invoice_extent, view_extent
from pv_app.features.day_by_day.analysis import day_by_day
from pv_app.storage.in_memory import InMemoryRepository

OCTOBER = ViewPeriod.containing(ViewPeriodKind.MONTH, date(2026, 10, 1))


def repository_with(readings: list[HourlyReading]) -> InMemoryRepository:
    repository = InMemoryRepository()
    repository.add_hourly_readings(readings)
    return repository


def test_day_sums_hours_ending_from_one_to_midnight_of_the_next_day() -> None:
    readings = [
        reading(datetime(2026, 10, 5, 0), "9", "9"),  # 23:00–0:00 → 4.10
        reading(datetime(2026, 10, 5, 1), "1", "0"),
        reading(datetime(2026, 10, 5, 13), "0.5", "2"),
        reading(datetime(2026, 10, 6, 0), "0.25", "0"),  # 23:00–0:00 → 5.10
    ]

    view = day_by_day(repository_with(readings), Filters(HOME, OCTOBER))

    assert view is not None
    fourth = view.find(date(2026, 10, 4))
    assert fourth is not None and fourth.imported_kwh == Decimal("9")
    fifth = next(d for d in view.days if d.day == date(2026, 10, 5))
    assert (fifth.imported_kwh, fifth.exported_kwh) == (Decimal("1.75"), Decimal("2"))
    assert fifth.hour_count == 3
    assert not fifth.complete


def test_days_with_clock_change_have_23_and_25_hours_and_count_as_complete() -> None:
    readings = days(date(2026, 3, 29), date(2026, 3, 29)) + days(
        date(2026, 10, 25), date(2026, 10, 25)
    )
    repository = repository_with(readings)
    whole = Filters(HOME, ViewPeriod.whole())

    view = day_by_day(repository, whole)

    assert view is not None
    spring, autumn = view.find(date(2026, 3, 29)), view.find(date(2026, 10, 25))
    assert spring is not None and autumn is not None
    assert (spring.hour_count, spring.complete) == (23, True)
    assert spring.imported_kwh == Decimal("11.5")
    assert (autumn.hour_count, autumn.complete) == (25, True)
    labels = [h.label for h in autumn.hours]
    assert labels[:4] == ["0:00–1:00", "1:00–2:00", "2:00–3:00", "2:00–3:00 (druga, zmiana czasu)"]
    assert labels[-1] == "23:00–24:00"


def test_day_missing_hours_or_without_any_is_marked_incomplete() -> None:
    readings = (
        days(date(2026, 10, 1), date(2026, 10, 1)) + days(date(2026, 10, 3), date(2026, 10, 3))[:-2]
    )

    view = day_by_day(repository_with(readings), Filters(HOME, OCTOBER))

    assert view is not None
    assert [(d.day.day, d.hour_count, d.complete) for d in view.days] == [
        (1, 24, True),
        (2, 0, False),
        (3, 22, False),
    ]


def test_view_period_limits_days_and_default_day_is_its_last_day_with_profile() -> None:
    repository = repository_with(days(date(2026, 9, 28), date(2026, 10, 3)))

    october = day_by_day(repository, Filters(HOME, OCTOBER))
    november = day_by_day(
        repository, Filters(HOME, ViewPeriod.containing(ViewPeriodKind.MONTH, date(2026, 11, 1)))
    )

    assert october is not None and november is not None
    assert [d.day.day for d in october.days] == [1, 2, 3]
    assert october.default_day == date(2026, 10, 3)
    assert november.days == () and november.default_day is None
    assert november.typical_day == ()


def test_no_profile_gives_none() -> None:
    assert day_by_day(InMemoryRepository(), Filters(HOME, OCTOBER)) is None


def test_typical_day_averages_each_hour_of_day_over_the_view_period() -> None:
    # 1.10 i 2.10: w godzinie 12:00–13:00 pobrane 1 i 3 kWh, oddane 2 i 0 kWh.
    readings = [
        reading(datetime(2026, 10, 1, 13), "1", "2"),
        reading(datetime(2026, 10, 2, 13), "3", "0"),
        reading(datetime(2026, 10, 2, 0), "0.5", "0"),  # 23:00–0:00 dnia 1.10
        reading(datetime(2026, 10, 3, 0), "1.5", "0"),  # 23:00–0:00 dnia 2.10
    ]

    view = day_by_day(repository_with(readings), Filters(HOME, OCTOBER))

    assert view is not None
    typical = {h.start_hour: h for h in view.typical_day}
    assert len(view.typical_day) == 24
    assert (typical[12].imported_kwh, typical[12].exported_kwh) == (Decimal(2), Decimal(1))
    assert typical[23].imported_kwh == Decimal(1)
    assert typical[5].imported_kwh == Decimal(0)


def test_typical_day_counts_the_extra_autumn_hour_as_one_more_sample() -> None:
    readings = days(date(2026, 10, 24), date(2026, 10, 25), imported="1")
    readings = [reading(r.hour_end, "4", "0", extra=True) if r.extra_hour else r for r in readings]

    view = day_by_day(repository_with(readings), Filters(HOME, OCTOBER))

    assert view is not None
    # Godzina 2:00–3:00: 1 kWh (24.10), 1 kWh i 4 kWh (25.10) → średnio 2 kWh.
    assert view.typical_day[2].imported_kwh == Decimal(2)
    assert view.typical_day[3].imported_kwh == Decimal(1)


def test_view_period_switcher_reaches_the_last_day_of_the_hourly_profile() -> None:
    repository = repository_with(days(date(2026, 9, 20), date(2026, 11, 10)))
    repository.add_invoice(invoice_for(DateRange(date(2026, 9, 1), date(2026, 10, 31)), "300"))

    assert view_extent(repository, HOME) == DateRange(date(2026, 9, 1), date(2026, 11, 10))
    # Widok na start dalej z Faktur: ostatni miesiąc objęty nimi w całości.
    assert ViewPeriod.default_for(invoice_extent(repository, HOME)).to_query() == "2026-10"


def test_view_extent_from_profile_alone_or_invoices_alone() -> None:
    profile_only = repository_with(days(date(2026, 10, 1), date(2026, 10, 2)))
    invoices_only = InMemoryRepository()
    invoices_only.add_invoice(invoice_for(DateRange(date(2026, 9, 1), date(2026, 9, 30)), "100"))

    assert view_extent(profile_only, HOME) == DateRange(date(2026, 10, 1), date(2026, 10, 2))
    assert view_extent(invoices_only, HOME) == DateRange(date(2026, 9, 1), date(2026, 9, 30))
    assert view_extent(InMemoryRepository(), HOME) is None


def test_surplus_hours_are_where_typical_day_exports_more_than_it_imports() -> None:
    readings = [
        reading(datetime(2026, 10, 1, hour), "0.5", exported)
        for hour, exported in [(9, "0.5"), (11, "1"), (12, "2"), (15, "0.75"), (16, "0.25")]
    ]
    without_panels = [reading(datetime(2026, 10, 1, 12), "0.5", "0")]

    view = day_by_day(repository_with(readings), Filters(HOME, OCTOBER))
    flat = day_by_day(repository_with(without_panels), Filters(HOME, OCTOBER))

    assert view is not None and flat is not None
    # Nadwyżka 10:00–12:00 i 14:00–15:00; godziny 12:00–14:00 bez nadwyżki rozdzielają przedziały.
    assert view.surplus_hours == ((10, 12), (14, 15))
    assert flat.surplus_hours == ()
