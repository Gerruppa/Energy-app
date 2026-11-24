"""Seam importu: surowe wiersze Faktury w starym układzie (do 2025) → wynik importu (ADR 0005).

Fixture'y w ``tests/fixtures/old_layout_*.json`` mają wymyślone numery i kwoty; wiersz
tabeli jest w nich listą komórek, tak jak adapter PDF dzieli go po położeniu znaków.
"""

from datetime import date
from decimal import Decimal
from pathlib import Path

from pv_app.domain.invoice import (
    Amount,
    DateRange,
    DocumentKind,
    EnergySettlement,
    Forecast,
    InvoiceLine,
    InvoiceSection,
    Layout,
    LineComponent,
    MeterDirection,
    MeterReading,
    ReadingType,
    SettlementType,
    Source,
)
from pv_app.ingest import import_document
from pv_app.ingest.raw import RawDocument, RawPage, Row

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> RawDocument:
    return RawDocument.from_json(FIXTURES / f"{name}.json")


ANNUAL = "old_layout_net_metering_annual"


def test_reads_header_of_annual_net_metering_invoice() -> None:
    result = import_document(load(ANNUAL))

    assert result.rejection is None
    assert result.invoice is not None
    invoice = result.invoice
    assert invoice.kind is DocumentKind.SETTLEMENT_INVOICE
    assert invoice.layout is Layout.OLD
    header = invoice.header
    assert header.number == "T/K1/0000001/24"
    assert header.issue_date == date(2024, 12, 15)
    assert header.billing_period == DateRange(date(2023, 12, 1), date(2024, 11, 30))
    assert header.ppe_number == "590000000000000001"
    assert header.site_name == "TESTOWY PUNKT DOM"
    assert header.address == "UL. PRZYKŁADOWA 1, 00-001 TESTOWO"
    assert header.tariff_group == "G11"
    assert header.contracted_power_kw == Decimal("13")
    assert header.settlement_type is SettlementType.NET_METERING
    assert header.billing_frequency_months is None
    assert header.source == Source("T/K1/0000001/24", 1)
    assert header.site_source == Source("T/K1/0000001/24", 4)


def test_reads_net_metering_readings_and_energy_settlement() -> None:
    invoice = import_document(load(ANNUAL)).invoice
    assert invoice is not None

    assert invoice.readings[0] == MeterReading(
        meter_number="10000001",
        direction=MeterDirection.IMPORT,
        zone="całodobowa",
        reading_date=date(2024, 11, 30),
        reading_type=ReadingType.REMOTE,
        previous=None,
        current=None,
        quantity_kwh=Decimal("3100"),
        source=Source("T/K1/0000001/24", 4),
    )
    assert [(r.direction, r.quantity_kwh) for r in invoice.readings] == [
        (MeterDirection.IMPORT, Decimal("3100")),
        (MeterDirection.EXPORT, Decimal("5000")),
    ]
    assert invoice.energy_settlement == EnergySettlement(
        imported_kwh=Decimal("3100"),
        exported_kwh=Decimal("5000"),
        store_start_kwh=Decimal("0"),
        discount_coefficient=Decimal("0.8"),
        exported_after_coefficient_kwh=Decimal("4000"),
        remaining_from_this_period_kwh=Decimal("900"),
        seller_share_kwh=Decimal("1000"),
        store_end_kwh=Decimal("900"),
        source=Source("T/K1/0000001/24", 4),
    )
    assert invoice.discount_kwh == Decimal("3100")


def test_joins_names_wrapped_around_the_numbers_row_and_counts_sub_periods() -> None:
    invoice = import_document(load(ANNUAL)).invoice
    assert invoice is not None

    fixed = [line for line in invoice.lines if line.component is LineComponent.FIXED_NETWORK]
    assert [(f.name, f.sub_period, f.quantity, f.unit_price_net) for f in fixed] == [
        ("Składnik stały stawki sieciowej", 1, Decimal("1"), Decimal("6.00000")),
        ("Składnik stały stawki sieciowej", 2, Decimal("6"), Decimal("6.00000")),
        ("Składnik stały stawki sieciowej", 3, Decimal("5"), Decimal("10.00000")),
    ]
    variable = [line for line in invoice.lines if line.component is LineComponent.VARIABLE_NETWORK]
    assert [(v.name, v.zone) for v in variable] == [
        ("Składnik zmienny stawki sieciowej", "całodobowa"),
        ("Składnik zmienny stawki sieciowej", "całodobowa"),
    ]
    subscription = [line for line in invoice.lines if line.component is LineComponent.SUBSCRIPTION]
    assert [(s.name, s.quantity, s.unit) for s in subscription] == [
        ("Stawka opłaty abonamentowej", Decimal("12"), "mc")
    ]
    assert len(invoice.lines) == 22
    assert all(line.component is not None for line in invoice.lines)


def test_tells_thousands_in_quantity_from_the_coefficient_column() -> None:
    invoice = import_document(load(ANNUAL)).invoice
    assert invoice is not None

    oze = [line for line in invoice.lines if line.component is LineComponent.OZE]
    assert [line.quantity for line in oze] == [Decimal("800"), Decimal("1300"), Decimal("1000")]
    assert oze[2] == InvoiceLine(
        section=InvoiceSection.DISTRIBUTION,
        name="Opłata OZE",
        component=LineComponent.OZE,
        zone="całodobowa",
        sub_period=3,
        quantity=Decimal("1000"),
        unit="kWh",
        unit_price_net=Decimal("0.00370"),
        net=Decimal("3.70"),
        vat_rate=Decimal("23"),
        vat=Decimal("0.85"),
        gross=Decimal("4.55"),
        source=Source("T/K1/0000001/24", 5),
    )


def test_reads_summary_with_refund_excise_and_last_year() -> None:
    invoice = import_document(load(ANNUAL)).invoice
    assert invoice is not None

    summary = invoice.summary
    assert summary.sales == Amount(Decimal("0.00"), Decimal("0.00"), Decimal("0.00"))
    assert summary.distribution == Amount(Decimal("218.90"), Decimal("50.34"), Decimal("269.24"))
    assert summary.result == Amount(Decimal("218.90"), Decimal("50.34"), Decimal("269.24"))
    assert summary.previous_forecast == Amount(
        Decimal("-800.00"), Decimal("-184.00"), Decimal("-984.00")
    )
    assert summary.additional_payments is None
    assert summary.amount_due == Decimal("-714.76")
    assert summary.account_balance is None
    assert (summary.excise_kwh, summary.excise_amount) == (Decimal("3000"), Decimal("15.00"))
    assert summary.same_period_last_year_kwh == Decimal("7000")
    assert summary.same_period_last_year_source == Source("T/K1/0000001/24", 4)
    assert summary.source == Source("T/K1/0000001/24", 1)


def test_reads_forecast_schedule_with_import_and_export() -> None:
    invoice = import_document(load(ANNUAL)).invoice
    assert invoice is not None

    assert invoice.forecasts[0] == Forecast(
        number="T/K1/0000001/24/1",
        period=DateRange(date(2024, 12, 1), date(2025, 5, 31)),
        import_kwh=Decimal("700"),
        export_kwh=Decimal("1100"),
        net=Decimal("40.00"),
        vat=Decimal("9.20"),
        gross=Decimal("49.20"),
        discount=Decimal("0.00"),
        balance_adjustment=Decimal("-49.20"),
        amount_due=Decimal("0.00"),
        due_date=date(2025, 1, 31),
        source=Source("T/K1/0000001/24", 2),
    )
    assert [(f.import_kwh, f.export_kwh) for f in invoice.forecasts] == [
        (Decimal("700"), Decimal("1100")),
        (Decimal("650"), Decimal("1200")),
    ]


HALF_YEAR = "old_layout_standard_half_year"


def test_reads_half_year_invoice_without_photovoltaics() -> None:
    result = import_document(load(HALF_YEAR))

    assert result.rejection is None
    assert result.invoice is not None
    invoice = result.invoice
    header = invoice.header
    assert header.number == "E/TM3/0000002/24"
    assert header.issue_date == date(2024, 4, 2)
    assert header.billing_period == DateRange(date(2023, 10, 1), date(2024, 3, 31))
    assert header.ppe_number == "590000000000000002"
    assert (header.site_name, header.address) == (
        "LOKAL TESTOWY",
        "UL. PRZYKŁADOWA 2/3, 00-002 TESTOWO",
    )
    assert (header.tariff_group, header.contracted_power_kw) == ("G11", Decimal("5"))
    assert header.settlement_type is SettlementType.STANDARD
    assert invoice.energy_settlement is None
    assert [
        (r.meter_number, r.reading_type, r.previous, r.current, r.quantity_kwh)
        for r in invoice.readings
    ] == [("20000002", ReadingType.PHYSICAL, Decimal("5000"), Decimal("5600"), Decimal("600"))]
    assert invoice.imported_kwh == Decimal("600")


def test_keeps_vat_5_and_23_percent_rows_as_separate_sub_periods() -> None:
    invoice = import_document(load(HALF_YEAR)).invoice
    assert invoice is not None

    variable = [
        (line.sub_period, line.unit_price_net, line.vat_rate, line.gross)
        for line in invoice.lines
        if line.component is LineComponent.VARIABLE_NETWORK
    ]
    assert variable == [
        (1, Decimal("0.25000"), Decimal("5"), Decimal("78.75")),
        (2, Decimal("0.26000"), Decimal("23"), Decimal("95.94")),
    ]
    energy = [line for line in invoice.lines if line.component is LineComponent.ACTIVE_ENERGY]
    assert [(e.vat_rate, e.gross) for e in energy] == [
        (Decimal("5"), Decimal("126.00")),
        (Decimal("23"), Decimal("184.50")),
    ]
    assert invoice.summary.sales == Amount(Decimal("270.00"), Decimal("40.50"), Decimal("310.50"))


def test_follows_distribution_table_onto_the_next_page() -> None:
    invoice = import_document(load(HALF_YEAR)).invoice
    assert invoice is not None

    capacity = [line for line in invoice.lines if line.component is LineComponent.CAPACITY]
    assert [(c.sub_period, c.gross, c.source.page) for c in capacity] == [
        (1, Decimal("31.50"), 4),
        (2, Decimal("44.28"), 4),
    ]
    assert len(invoice.lines) == 10


def test_reads_additional_payments_and_forecasts_with_underpayment() -> None:
    invoice = import_document(load(HALF_YEAR)).invoice
    assert invoice is not None

    summary = invoice.summary
    assert summary.previous_forecast == Amount(
        Decimal("-100.00"), Decimal("-15.00"), Decimal("-115.00")
    )
    assert summary.additional_payments == Decimal("200.00")
    assert summary.amount_due == Decimal("314.37")
    assert summary.excise_kwh == Decimal("600")
    assert summary.same_period_last_year_kwh is None
    assert invoice.forecasts[0] == Forecast(
        number="E/TM3/0000002/24/1",
        period=DateRange(date(2024, 4, 1), date(2024, 4, 30)),
        import_kwh=Decimal("100"),
        export_kwh=None,
        net=Decimal("80.00"),
        vat=Decimal("18.40"),
        gross=Decimal("98.40"),
        discount=Decimal("0.00"),
        balance_adjustment=Decimal("314.37"),
        amount_due=Decimal("412.77"),
        due_date=date(2024, 4, 10),
        source=Source("E/TM3/0000002/24", 2),
    )
    assert [f.amount_due for f in invoice.forecasts] == [Decimal("412.77"), Decimal("88.56")]


METER_REPLACEMENT = "old_layout_meter_replacement"


def test_reads_2025_variant_with_summary_page_and_two_column_attachment() -> None:
    result = import_document(load(METER_REPLACEMENT))

    assert result.rejection is None
    assert result.invoice is not None
    header = result.invoice.header
    assert header.number == "E/TM3/0000003/25"
    assert header.billing_period == DateRange(date(2025, 3, 22), date(2025, 9, 19))
    assert header.issue_date == date(2025, 9, 25)
    assert header.ppe_number == "590000000000000003"
    assert header.site_name == "LOKAL TESTOWY"
    assert header.tariff_group == "G11"
    assert header.billing_frequency_months is None  # tylko na stronie podsumowania, bez Source
    assert header.source == Source("E/TM3/0000003/25", 3)
    assert header.site_source == Source("E/TM3/0000003/25", 5)


def test_sums_energy_from_both_meters_when_the_meter_was_replaced() -> None:
    invoice = import_document(load(METER_REPLACEMENT)).invoice
    assert invoice is not None

    assert [(r.meter_number, r.reading_date, r.quantity_kwh) for r in invoice.readings] == [
        ("30000003", date(2025, 5, 5), Decimal("200")),
        ("S000000000003", date(2025, 9, 19), Decimal("300")),
    ]
    assert invoice.imported_kwh == Decimal("500")
    assert invoice.summary.excise_amount == Decimal("2.45")


def test_reads_forecast_whose_amount_and_due_date_share_a_cell() -> None:
    invoice = import_document(load(METER_REPLACEMENT)).invoice
    assert invoice is not None

    assert [
        (f.gross, f.balance_adjustment, f.amount_due, f.due_date) for f in invoice.forecasts
    ] == [(Decimal("184.50"), Decimal("373.92"), Decimal("558.42"), date(2025, 10, 13))]


def load_with(name: str, old: Row, new: Row) -> RawDocument:
    """Fixture z jednym wierszem tabeli podmienionym."""
    document = load(name)
    pages = tuple(
        RawPage(
            page.number,
            tuple(" ".join(new) if line == " ".join(old) else line for line in page.lines),
            tuple(new if row == old else row for row in page.rows),
        )
        for page in document.pages
    )
    assert pages != document.pages, f"w fixture'ze nie ma wiersza {old!r}"
    return RawDocument(pages)


def test_rejects_invoice_whose_lines_do_not_add_up_to_settlement_result() -> None:
    document = load_with(
        HALF_YEAR,
        ("Opłata mocowa", "zł/mc", "3", "12,00000", "36,00", "23", "8,28", "44,28"),
        ("Opłata mocowa", "zł/mc", "3", "12,00000", "36,00", "23", "8,28", "45,28"),
    )

    result = import_document(document)

    assert result.invoice is None
    assert result.rejection is not None
    assert "Wynikiem rozliczenia" in result.rejection


def test_rejects_forecast_whose_amounts_do_not_add_up() -> None:
    document = load_with(
        METER_REPLACEMENT,
        (
            "E/TM3/0000003/25/1",
            "20/09/2025 - 31/10/2025",
            "150",
            "150,00",
            "x",
            "34,50",
            "184,50",
            "0,00",
            "373,92",
            "558,42 13/10/2025",
        ),
        (
            "E/TM3/0000003/25/1",
            "20/09/2025 - 31/10/2025",
            "150",
            "150,00",
            "x",
            "34,50",
            "185,50",
            "0,00",
            "373,92",
            "558,42 13/10/2025",
        ),
    )

    result = import_document(document)

    assert result.invoice is None
    assert result.rejection == "Nie udało się odczytać Prognozy E/TM3/0000003/25/1 (strona 4)."


def test_warns_about_unrecognised_invoice_line_but_keeps_it() -> None:
    document = load_with(
        METER_REPLACEMENT,
        ("Opłata mocowa", "zł/mc", "6", "10,00000", "60,00", "23", "13,80", "73,80"),
        ("Nowa opłata testowa", "zł/mc", "6", "10,00000", "60,00", "23", "13,80", "73,80"),
    )

    result = import_document(document)

    assert result.invoice is not None
    assert result.warnings == ("Nierozpoznana Pozycja faktury „Nowa opłata testowa” (strona 5).",)


def test_rejects_old_layout_dump_without_table_cells() -> None:
    document = load(ANNUAL)
    lines_only = RawDocument(tuple(RawPage(page.number, page.lines) for page in document.pages))

    result = import_document(lines_only)

    assert result.invoice is None
    assert result.rejection is not None
    assert "jako PDF" in result.rejection
