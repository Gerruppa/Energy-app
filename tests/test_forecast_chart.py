"""Wykres „Prognozy Taurona a rzeczywistość” (PPE bez fotowoltaiki) na Repository w pamięci."""

from dataclasses import replace
from datetime import date
from decimal import Decimal

from factories import HOME, forecast, invoice_for
from pv_app.domain.invoice import DateRange, Invoice
from pv_app.domain.view_period import ViewPeriod, month_index
from pv_app.features.base import Filters
from pv_app.features.overview.analysis import forecast_chart, year_over_year
from pv_app.storage.in_memory import InMemoryRepository


def view(query: str) -> Filters:
    period = ViewPeriod.from_query(query)
    assert period is not None
    return Filters(ppe_number=HOME, view_period=period)


def issued(invoice: Invoice, day: date) -> Invoice:
    return replace(invoice, header=replace(invoice.header, issue_date=day))


WINTER = DateRange(date(2025, 9, 1), date(2026, 2, 28))
SUMMER = DateRange(date(2026, 3, 1), date(2026, 8, 31))
SEP_OCT = DateRange(date(2026, 9, 1), date(2026, 10, 31))


def repository() -> InMemoryRepository:
    winter = replace(
        issued(invoice_for(WINTER, "600", number="Z/26"), date(2026, 3, 5)),
        forecasts=(
            forecast(
                "Z/26/1",
                DateRange(date(2026, 3, 1), date(2026, 3, 31)),
                date(2026, 3, 20),
                import_kwh="90",
            ),
            forecast(
                "Z/26/2",
                DateRange(date(2026, 4, 1), date(2026, 8, 31)),
                date(2026, 4, 20),
                import_kwh="459",
            ),
            # Stary plan na wrzesień i październik; nowszy harmonogram go zastępuje.
            forecast("Z/26/3", SEP_OCT, date(2026, 9, 20), import_kwh="999"),
        ),
    )
    summer = replace(
        issued(invoice_for(SUMMER, "400", number="L/26"), date(2026, 9, 5)),
        forecasts=(forecast("L/26/1", SEP_OCT, date(2026, 9, 20), import_kwh="122"),),
    )
    result = InMemoryRepository()
    result.add_invoice(winter)
    result.add_invoice(summer)
    return result


def test_forecasts_from_the_latest_schedule_are_lines_next_to_invoices() -> None:
    chart = forecast_chart(repository(), view("2026-08"))

    assert chart is not None
    assert [(f.forecast_number, f.import_kwh) for f in chart.forecasts] == [
        ("Z/26/1", Decimal("90")),
        ("Z/26/2", Decimal("459")),
        ("L/26/1", Decimal("122")),
    ]
    march = chart.forecasts[0]
    assert march.single_month and march.per_month == Decimal("90")
    # 459 kWh przez 153 dni = 3 kWh dziennie, × 30,44 dnia na miesiąc.
    assert chart.forecasts[1].per_month == Decimal("91.32")
    assert [b.invoice_number for b in chart.energy.blocks] == ["Z/26", "L/26"]
    assert chart.energy.months[0] == month_index(date(2025, 9, 1))
    assert chart.energy.months[-1] == month_index(date(2026, 10, 1))
    assert chart.energy.year_earlier == ()


def test_forecasts_never_count_as_energy_or_cost() -> None:
    comparison = year_over_year(repository(), view("2026-K3"))

    assert comparison is not None
    # Lipiec i sierpień z Faktury L/26 (400 kWh przez 184 dni); wrzesień bez Faktury.
    assert comparison.missing_months == (month_index(date(2026, 9, 1)),)
    assert comparison.current.imported_kwh.quantize(Decimal("0.01")) == Decimal("134.78")


def test_no_forecast_chart_without_forecasts() -> None:
    plain = InMemoryRepository()
    plain.add_invoice(invoice_for(SUMMER, "400", number="L/26"))

    assert forecast_chart(plain, view("2026-08")) is None
