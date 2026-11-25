"""Rozkład Faktury na miesiące kalendarzowe."""

from datetime import date
from decimal import Decimal

from factories import invoice_for
from pv_app.domain.cost_groups import CostGroup
from pv_app.domain.invoice import DateRange
from pv_app.domain.monthly_split import MonthShare, split_into_months
from pv_app.domain.view_period import month_index


def test_kwh_and_variable_components_by_days_fixed_components_equally() -> None:
    # 20.01–9.03.2026: 12 + 28 + 9 = 49 dni.
    invoice = invoice_for(
        DateRange(date(2026, 1, 20), date(2026, 3, 9)),
        imported="490",
        exported="980",
        variable_gross="98",
        fixed_gross="30",
    )

    shares = split_into_months(invoice, period_cost=Decimal("177"))

    # Reszta Kosztu okresu (177 − 98 − 30 = 49 zł: VAT-owe zaokrąglenia, Bonifikaty) po dniach.
    assert [
        (s.month, s.days, s.imported_kwh, s.exported_kwh, s.variable_cost, s.fixed_cost)
        for s in shares
    ] == [
        (
            month_index(date(2026, 1, 1)),
            12,
            Decimal("120"),
            Decimal("240"),
            Decimal("24"),
            Decimal("10"),
        ),
        (
            month_index(date(2026, 2, 1)),
            28,
            Decimal("280"),
            Decimal("560"),
            Decimal("56"),
            Decimal("10"),
        ),
        (
            month_index(date(2026, 3, 1)),
            9,
            Decimal("90"),
            Decimal("180"),
            Decimal("18"),
            Decimal("10"),
        ),
    ]
    assert [s.period_cost for s in shares] == [Decimal("46"), Decimal("94"), Decimal("37")]
    assert all(not s.whole_invoice for s in shares)


def test_rounded_shares_add_up_to_invoice_totals() -> None:
    invoice = invoice_for(
        DateRange(date(2026, 1, 1), date(2026, 3, 31)),
        imported="100",
        exported="0",
        variable_gross="10",
        fixed_gross="1",
    )

    shares = split_into_months(invoice, period_cost=Decimal("12.34"))

    assert sum(s.imported_kwh for s in shares) == Decimal("100")
    assert sum(s.variable_cost for s in shares) == Decimal("10")
    assert sum(s.fixed_cost for s in shares) == Decimal("1")
    assert sum(s.period_cost for s in shares) == Decimal("12.34")
    assert [s.fixed_cost for s in shares] == [Decimal("0.33"), Decimal("0.33"), Decimal("0.34")]


def test_monthly_invoice_is_one_share_with_invoice_values() -> None:
    invoice = invoice_for(
        DateRange(date(2026, 10, 1), date(2026, 10, 31)),
        imported="150",
        exported="300",
        variable_gross="2",
        fixed_gross="30",
    )

    assert split_into_months(invoice, period_cost=Decimal("32.04")) == [
        MonthShare(
            month=month_index(date(2026, 10, 1)),
            days=31,
            imported_kwh=Decimal("150"),
            exported_kwh=Decimal("300"),
            stored_kwh=Decimal("240"),
            variable_cost=Decimal("2"),
            fixed_cost=Decimal("30"),
            period_cost=Decimal("32.04"),
            invoice_number=invoice.number,
            whole_invoice=True,
            cost_groups={
                CostGroup.ENERGY: Decimal("0"),
                CostGroup.VARIABLE_DISTRIBUTION: Decimal("2"),
                CostGroup.PER_KWH_FEES: Decimal("0"),
                CostGroup.CAPACITY: Decimal("30"),
                CostGroup.FIXED_FEES: Decimal("0"),
            },
        )
    ]


def test_cost_groups_split_like_their_components_and_add_up_to_invoice() -> None:
    # 20.01–9.03.2026: 12 + 28 + 9 = 49 dni.
    invoice = invoice_for(
        DateRange(date(2026, 1, 20), date(2026, 3, 9)),
        imported="490",
        variable_gross="98",
        fixed_gross="30",
    )

    shares = split_into_months(invoice, period_cost=Decimal("128"))

    assert [s.cost_groups[CostGroup.VARIABLE_DISTRIBUTION] for s in shares] == [
        Decimal("24"),
        Decimal("56"),
        Decimal("18"),
    ]
    assert [s.cost_groups[CostGroup.CAPACITY] for s in shares] == [
        Decimal("10"),
        Decimal("10"),
        Decimal("10"),
    ]
