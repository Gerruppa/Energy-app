"""Status Profilu godzinowego: czy trzeba pobrać nowy Raport wartości godzinowych, na Repository
w pamięci. Doba pełna przy 23, 24 albo 25 godzinach."""

from datetime import date

from factories import HOME, days
from pv_app.domain.hourly_profile import HourlyReading
from pv_app.domain.invoice import DateRange
from pv_app.features.profile_status import PROFILE_OVERDUE_DAYS, profile_status
from pv_app.storage.in_memory import InMemoryRepository

TODAY = date(2026, 11, 26)


def repository_with(readings: list[HourlyReading]) -> InMemoryRepository:
    repository = InMemoryRepository()
    repository.add_hourly_readings(readings)
    return repository


def test_profile_ending_within_the_threshold_is_current() -> None:
    repository = repository_with(days(date(2026, 11, 1), date(2026, 11, 12)))

    status = profile_status(repository, HOME, TODAY)

    assert PROFILE_OVERDUE_DAYS == 14
    assert status is not None
    assert status.last_complete_day == date(2026, 11, 12)
    assert status.days_behind == 14
    assert not status.overdue


def test_profile_ending_more_than_the_threshold_ago_is_overdue() -> None:
    repository = repository_with(days(date(2026, 10, 1), date(2026, 10, 30)))

    status = profile_status(repository, HOME, TODAY)

    assert status is not None
    assert (status.last_complete_day, status.days_behind) == (date(2026, 10, 30), 27)
    assert status.overdue


def test_incomplete_last_day_does_not_count_as_the_end_of_the_profile() -> None:
    readings = days(date(2026, 11, 1), date(2026, 11, 12))
    repository = repository_with(readings + days(date(2026, 11, 13), date(2026, 11, 13))[:20])

    status = profile_status(repository, HOME, TODAY)

    assert status is not None
    assert status.last_complete_day == date(2026, 11, 12)


def test_day_with_25_hours_at_the_end_is_complete_only_with_the_extra_hour() -> None:
    whole = days(date(2026, 10, 20), date(2026, 10, 25))
    without_extra = [r for r in whole if not r.extra_hour]

    with_extra_status = profile_status(repository_with(whole), HOME, TODAY)
    without_extra_status = profile_status(repository_with(without_extra), HOME, TODAY)

    assert with_extra_status is not None and without_extra_status is not None
    assert with_extra_status.last_complete_day == date(2026, 10, 25)
    assert without_extra_status.last_complete_day == date(2026, 10, 24)


def test_profile_without_any_complete_day_is_overdue_without_an_end() -> None:
    repository = repository_with(days(date(2026, 11, 20), date(2026, 11, 20))[:5])

    status = profile_status(repository, HOME, TODAY)

    assert status is not None
    assert status.last_complete_day is None
    assert status.overdue


def test_metering_point_without_hourly_profile_has_no_status() -> None:
    assert profile_status(InMemoryRepository(), HOME, TODAY) is None


def test_overdue_profile_reminds_only_in_view_periods_reaching_past_its_end() -> None:
    status = profile_status(
        repository_with(days(date(2026, 10, 1), date(2026, 10, 30))), HOME, TODAY
    )
    current = profile_status(
        repository_with(days(date(2026, 11, 1), date(2026, 11, 20))), HOME, TODAY
    )

    assert status is not None and current is not None
    assert status.reminds_in(DateRange(date(2026, 10, 1), date(2026, 10, 31)))
    assert status.reminds_in(None)  # cały okres
    assert not status.reminds_in(DateRange(date(2026, 9, 1), date(2026, 9, 30)))
    assert not current.reminds_in(DateRange(date(2026, 11, 1), date(2026, 11, 30)))
