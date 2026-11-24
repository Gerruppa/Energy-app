"""Okres widoku: wartość w adresie strony, sąsiednie okresy i ten sam okres rok wcześniej."""

from datetime import date

import pytest

from pv_app.domain.invoice import DateRange
from pv_app.domain.view_period import ViewPeriod, ViewPeriodKind, month_index, month_label


@pytest.mark.parametrize(
    ("query", "kind", "dates"),
    [
        ("2026-10", ViewPeriodKind.MONTH, DateRange(date(2026, 10, 1), date(2026, 10, 31))),
        ("2026-02", ViewPeriodKind.MONTH, DateRange(date(2026, 2, 1), date(2026, 2, 28))),
        ("2026-K4", ViewPeriodKind.QUARTER, DateRange(date(2026, 10, 1), date(2026, 12, 31))),
        ("2025", ViewPeriodKind.YEAR, DateRange(date(2025, 1, 1), date(2025, 12, 31))),
    ],
)
def test_view_period_round_trips_through_page_address(
    query: str, kind: ViewPeriodKind, dates: DateRange
) -> None:
    period = ViewPeriod.from_query(query)

    assert period is not None
    assert period.kind is kind
    assert period.dates == dates
    assert period.to_query() == query


@pytest.mark.parametrize("query", ["", "abc", "2026-13", "2026-K5", "cały-2026"])
def test_unknown_address_value_gives_no_view_period(query: str) -> None:
    assert ViewPeriod.from_query(query) is None


def test_whole_period_has_no_dates_of_its_own() -> None:
    period = ViewPeriod.from_query("caly")

    assert period == ViewPeriod.whole()
    assert period is not None and period.dates is None
    assert period.to_query() == "caly"


@pytest.mark.parametrize(
    ("query", "previous", "following"),
    [
        ("2026-01", "2025-12", "2026-02"),
        ("2026-K1", "2025-K4", "2026-K2"),
        ("2026", "2025", "2027"),
    ],
)
def test_arrows_move_to_neighbouring_period_of_the_same_kind(
    query: str, previous: str, following: str
) -> None:
    period = ViewPeriod.from_query(query)
    assert period is not None

    assert period.shifted(-1).to_query() == previous
    assert period.shifted(1).to_query() == following


def test_year_earlier_is_the_same_period_twelve_months_back() -> None:
    period = ViewPeriod.from_query("2026-K3")
    assert period is not None

    assert period.year_earlier().to_query() == "2025-K3"


def test_kind_switch_keeps_the_period_containing_the_given_day() -> None:
    day = date(2026, 8, 15)

    assert ViewPeriod.containing(ViewPeriodKind.MONTH, day).to_query() == "2026-08"
    assert ViewPeriod.containing(ViewPeriodKind.QUARTER, day).to_query() == "2026-K3"
    assert ViewPeriod.containing(ViewPeriodKind.YEAR, day).to_query() == "2026"
    assert ViewPeriod.containing(ViewPeriodKind.WHOLE, day) == ViewPeriod.whole()


@pytest.mark.parametrize(
    ("query", "label"),
    [
        ("2026-10", "październik 2026"),
        ("2026-K4", "IV kwartał 2026"),
        ("2026", "rok 2026"),
        ("caly", "cały okres"),
    ],
)
def test_view_period_label_in_polish(query: str, label: str) -> None:
    period = ViewPeriod.from_query(query)
    assert period is not None

    assert period.label == label


@pytest.mark.parametrize(
    ("extent", "default"),
    [
        (DateRange(date(2025, 1, 1), date(2026, 10, 31)), "2026-10"),
        # Ostatnia Faktura kończy się 9.03: marzec nie jest objęty w całości.
        (DateRange(date(2025, 9, 20), date(2026, 3, 9)), "2026-02"),
        # Jedyna Faktura w środku miesiąca: pokazujemy jej miesiąc.
        (DateRange(date(2026, 3, 2), date(2026, 3, 9)), "2026-03"),
    ],
)
def test_default_view_is_last_month_fully_covered_by_invoices(
    extent: DateRange, default: str
) -> None:
    assert ViewPeriod.default_for(extent).to_query() == default


def test_default_view_without_invoices_is_whole_period() -> None:
    assert ViewPeriod.default_for(None) == ViewPeriod.whole()


def test_month_label_of_month_index() -> None:
    assert month_label(month_index(date(2026, 5, 1))) == "maj 2026"
