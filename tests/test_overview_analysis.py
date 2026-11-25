"""Analizy Przeglądu (wykres miesiąc po miesiącu, rok do roku) na Repository w pamięci."""

from dataclasses import replace
from datetime import date
from decimal import Decimal

from factories import HOME, invoice_for
from pv_app.domain.invoice import Amount, Correction, DateRange, DocumentKind, Invoice, Source
from pv_app.domain.view_period import ViewPeriod, month_index
from pv_app.features.base import Filters
from pv_app.features.monthly import ChartBlock, InvoiceRef, monthly_chart, year_over_year
from pv_app.storage.in_memory import InMemoryRepository


def view(query: str) -> Filters:
    period = ViewPeriod.from_query(query)
    assert period is not None
    return Filters(ppe_number=HOME, view_period=period)


def month(year: int, number: int) -> int:
    return month_index(date(year, number, 1))


OCTOBER_2026 = DateRange(date(2026, 10, 1), date(2026, 10, 31))
# 1.12.2024 – 30.11.2025: 365 dni, z tego 31 w październiku 2025.
YEAR_2025 = DateRange(date(2024, 12, 1), date(2025, 11, 30))


def repository_with(*invoices: Invoice) -> InMemoryRepository:
    repository = InMemoryRepository()
    for invoice in invoices:
        repository.add_invoice(invoice)
    return repository


def test_month_compared_with_same_month_a_year_earlier_from_own_history() -> None:
    repository = repository_with(
        invoice_for(OCTOBER_2026, "150", "300", number="M/10/26", fixed_gross="30"),
        invoice_for(YEAR_2025, "3650", "7300", number="R/25", fixed_gross="120"),
    )

    result = year_over_year(repository, view("2026-10"))

    assert result is not None
    assert (result.current.imported_kwh, result.current.exported_kwh) == (
        Decimal("150"),
        Decimal("300"),
    )
    assert result.current.period_cost == Decimal("30")
    assert not result.current.approximate
    assert result.current.invoices == (
        InvoiceRef(
            "M/10/26",
            OCTOBER_2026,
            Source("M/10/26", 4),
            Source("M/10/26", 3),
            part_of_longer=False,
        ),
    )
    earlier = result.year_earlier
    assert earlier is not None
    assert (earlier.imported_kwh, earlier.exported_kwh) == (Decimal("310"), Decimal("620"))
    # Przyrost Magazynu energii z Faktur (Energia oddana × 0,8), rozłożony jak Energia oddana.
    assert (result.current.stored_kwh, earlier.stored_kwh) == (Decimal("240"), Decimal("496"))
    # Składniki stałe po równo na 12 miesięcy.
    assert earlier.period_cost == Decimal("10")
    assert earlier.approximate
    assert earlier.invoices == (
        InvoiceRef("R/25", YEAR_2025, Source("R/25", 4), Source("R/25", 3), part_of_longer=True),
    )


def test_without_own_history_tauron_same_period_last_year_is_the_fallback() -> None:
    repository = repository_with(
        invoice_for(OCTOBER_2026, "150", "300", number="M/10/26", same_period_last_year="170"),
    )

    result = year_over_year(repository, view("2026-10"))

    assert result is not None
    assert result.year_earlier is None
    assert result.tauron_last_year_kwh == Decimal("170")
    assert result.tauron_sources == (Source("M/10/26", 2),)


def test_tauron_value_checks_own_history_and_flags_difference_above_five_percent() -> None:
    def compared(tauron: str) -> bool:
        repository = repository_with(
            invoice_for(OCTOBER_2026, "150", "300", number="M/10/26", same_period_last_year=tauron),
            invoice_for(YEAR_2025, "3650", "7300", number="R/25"),
        )
        result = year_over_year(repository, view("2026-10"))
        assert result is not None
        return result.tauron_differs

    # Własna historia: 310 kWh w październiku 2025.
    assert not compared("320")
    assert compared("330")


def test_tauron_value_only_when_invoices_cover_exactly_the_view_period() -> None:
    repository = repository_with(
        invoice_for(
            DateRange(date(2026, 9, 1), date(2026, 11, 30)),
            "300",
            number="K/26",
            same_period_last_year="280",
        ),
    )

    result = year_over_year(repository, view("2026-10"))

    assert result is not None
    assert result.tauron_last_year_kwh is None


def test_months_without_invoice_are_left_out_of_both_sides_of_comparison() -> None:
    repository = repository_with(
        invoice_for(OCTOBER_2026, "150", "300", number="M/10/26"),
        invoice_for(YEAR_2025, "3650", "7300", number="R/25"),
    )

    result = year_over_year(repository, view("2026-K4"))

    assert result is not None
    assert result.missing_months == (month(2026, 11), month(2026, 12))
    assert result.current.months == (month(2026, 10),)
    assert result.year_earlier is not None
    assert result.year_earlier.months == (month(2025, 10),)
    assert result.year_earlier.imported_kwh == Decimal("310")


def test_superseded_invoice_does_not_count() -> None:
    original = invoice_for(OCTOBER_2026, "150", "300", number="M/10/26")
    correction = invoice_for(OCTOBER_2026, "140", "300", number="K/10/26")
    assert correction.correction is None

    correction = replace(
        correction,
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

    result = year_over_year(repository, view("2026-10"))

    assert result is not None
    assert result.current.imported_kwh == Decimal("140")
    assert [ref.number for ref in result.current.invoices] == ["K/10/26"]


def test_whole_period_has_no_year_over_year_comparison() -> None:
    repository = repository_with(invoice_for(OCTOBER_2026, "150", "300"))

    assert year_over_year(repository, view("caly")) is None


def test_chart_shows_twelve_months_up_to_viewed_month_with_blocks_and_year_earlier() -> None:
    repository = repository_with(
        invoice_for(OCTOBER_2026, "150", "300", number="M/10/26"),
        invoice_for(YEAR_2025, "3650", "7300", number="R/25"),
    )

    chart = monthly_chart(repository, view("2026-10"))

    assert chart is not None
    assert chart.months == tuple(range(month(2025, 11), month(2026, 10) + 1))
    assert chart.selected == (month(2026, 10),)
    assert [(b.invoice_number, b.single_month, b.drawn) for b in chart.blocks] == [
        ("R/25", False, YEAR_2025),
        ("M/10/26", True, OCTOBER_2026),
    ]
    annual, monthly = chart.blocks
    # Średnia na miesiąc: suma z Faktury / 365 dni × 30,44.
    assert annual.imported_per_month == Decimal("304.4")
    assert annual.exported_per_month == Decimal("608.8")
    assert (monthly.imported_per_month, monthly.exported_per_month) == (
        Decimal("150"),
        Decimal("300"),
    )
    # Rok wcześniej: te same Faktury przesunięte o 12 miesięcy, o ile trafiają w okno wykresu.
    assert chart.year_earlier == (
        ChartBlock(
            invoice_number="R/25",
            period=YEAR_2025,
            drawn=DateRange(date(2025, 12, 1), date(2026, 11, 30)),
            imported_kwh=Decimal("3650"),
            exported_kwh=Decimal("7300"),
            imported_per_month=Decimal("304.4"),
            exported_per_month=Decimal("608.8"),
            single_month=False,
            source=Source("R/25", 4),
            period_cost=Decimal("0"),
            cost_per_month=Decimal("0"),
            cost_source=Source("R/25", 3),
        ),
    )
    # Między Fakturą R/25 (do XI 2025) a M/10/26 nie ma Faktur.
    assert chart.missing_months == tuple(range(month(2025, 12), month(2026, 9) + 1))


def test_chart_marks_gaps_only_between_first_and_last_invoice() -> None:
    repository = repository_with(
        invoice_for(DateRange(date(2026, 3, 1), date(2026, 3, 31)), "100", "100"),
        invoice_for(DateRange(date(2026, 6, 1), date(2026, 6, 30)), "100", "100"),
    )

    chart = monthly_chart(repository, view("2026"))

    assert chart is not None
    assert chart.selected == chart.months == tuple(range(month(2026, 1), month(2026, 12) + 1))
    assert chart.missing_months == (month(2026, 4), month(2026, 5))


def test_whole_period_chart_spans_all_invoices() -> None:
    repository = repository_with(
        invoice_for(DateRange(date(2025, 3, 1), date(2025, 3, 31)), "100"),
        invoice_for(DateRange(date(2026, 6, 1), date(2026, 6, 30)), "100"),
    )

    chart = monthly_chart(repository, view("caly"))

    assert chart is not None
    assert chart.months == tuple(range(month(2025, 3), month(2026, 6) + 1))
    assert chart.blocks[0].exported_per_month is None


def test_no_chart_without_invoices() -> None:
    assert monthly_chart(InMemoryRepository(), view("2026-10")) is None
