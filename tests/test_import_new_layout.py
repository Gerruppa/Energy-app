"""Seam importu: surowe wiersze Faktury w nowym układzie → wynik importu (ADR 0005).

Fixture'y w ``tests/fixtures/`` mają wymyślone numery i kwoty.
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
    SettlementBasis,
    SettlementType,
    Source,
)
from pv_app.ingest import import_document
from pv_app.ingest.raw import RawDocument, RawPage

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> RawDocument:
    return RawDocument.from_json(FIXTURES / f"{name}.json")


MONTHLY = "new_layout_net_metering_monthly"


def test_reads_header_of_net_metering_invoice() -> None:
    result = import_document(load(MONTHLY))

    assert result.rejection is None
    assert result.invoice is not None
    invoice = result.invoice
    assert invoice.kind is DocumentKind.SETTLEMENT_INVOICE
    assert invoice.layout is Layout.NEW
    header = invoice.header
    assert header.number == "T/K1/BN000001/0004/26"
    assert header.issue_date == date(2026, 11, 9)
    assert header.billing_period == DateRange(date(2026, 10, 1), date(2026, 10, 31))
    assert header.ppe_number == "590000000000000001"
    assert header.site_name == "TESTOWY PUNKT DOM"
    assert header.address == "UL. PRZYKŁADOWA 1, 00-001 TESTOWO"
    assert header.tariff_group == "G11"
    assert header.contracted_power_kw == Decimal("13")
    assert header.settlement_type is SettlementType.NET_METERING
    assert header.billing_frequency_months == 1
    assert header.source == Source("T/K1/BN000001/0004/26", 3)


def test_reads_settlement_summary_with_balance_excise_and_last_year() -> None:
    invoice = import_document(load(MONTHLY)).invoice
    assert invoice is not None

    summary = invoice.summary
    assert summary.sales == Amount(Decimal("0.00"), Decimal("0.00"), Decimal("0.00"))
    assert summary.distribution == Amount(Decimal("26.05"), Decimal("5.99"), Decimal("32.04"))
    assert summary.result == Amount(Decimal("26.05"), Decimal("5.99"), Decimal("32.04"))
    assert summary.previous_forecast is None
    assert summary.additional_payments == Decimal("32.04")
    assert summary.amount_due == Decimal("0.00")
    assert summary.account_balance == Decimal("1234.56")
    assert summary.excise_kwh == Decimal("200")
    assert summary.excise_amount == Decimal("1.00")
    assert summary.same_period_last_year_kwh == Decimal("170")
    assert summary.source == Source("T/K1/BN000001/0004/26", 3)
    assert invoice.period_cost == Decimal("32.04")


def test_reads_meter_readings_with_reading_type() -> None:
    invoice = import_document(load(MONTHLY)).invoice
    assert invoice is not None

    assert invoice.readings == (
        MeterReading(
            meter_number="10000001",
            direction=MeterDirection.IMPORT,
            zone="całodobowa",
            reading_date=date(2026, 10, 31),
            reading_type=ReadingType.REMOTE,
            previous=None,
            current=None,
            quantity_kwh=Decimal("150"),
            source=Source("T/K1/BN000001/0004/26", 3),
        ),
        MeterReading(
            meter_number="10000001",
            direction=MeterDirection.EXPORT,
            zone="całodobowa",
            reading_date=date(2026, 10, 31),
            reading_type=ReadingType.REMOTE,
            previous=None,
            current=None,
            quantity_kwh=Decimal("300"),
            source=Source("T/K1/BN000001/0004/26", 3),
        ),
    )
    assert invoice.settlement_basis is SettlementBasis.ACTUAL_READING


def test_reads_energy_settlement_of_net_metering_invoice() -> None:
    invoice = import_document(load(MONTHLY)).invoice
    assert invoice is not None

    assert invoice.energy_settlement == EnergySettlement(
        imported_kwh=Decimal("150"),
        exported_kwh=Decimal("300"),
        store_start_kwh=Decimal("1000"),
        discount_coefficient=Decimal("0.8"),
        exported_after_coefficient_kwh=Decimal("240"),
        remaining_from_this_period_kwh=Decimal("240"),
        seller_share_kwh=Decimal("60"),
        store_end_kwh=Decimal("1090"),
        source=Source("T/K1/BN000001/0004/26", 4),
    )
    assert invoice.imported_kwh == Decimal("150")
    assert invoice.exported_kwh == Decimal("300")


def test_reads_all_invoice_lines_with_components_and_sources() -> None:
    invoice = import_document(load(MONTHLY)).invoice
    assert invoice is not None

    summary = [
        (line.section, line.component, line.quantity, line.unit, line.gross)
        for line in invoice.lines
    ]
    sales, distribution = InvoiceSection.SALES, InvoiceSection.DISTRIBUTION
    assert summary == [
        (sales, LineComponent.ACTIVE_ENERGY, Decimal("0"), "kWh", Decimal("0.00")),
        (distribution, LineComponent.VARIABLE_NETWORK, Decimal("0"), "kWh", Decimal("0.00")),
        (distribution, LineComponent.QUALITY, Decimal("0"), "kWh", Decimal("0.00")),
        (distribution, LineComponent.OZE, Decimal("150"), "kWh", Decimal("1.35")),
        (distribution, LineComponent.COGENERATION, Decimal("150"), "kWh", Decimal("0.55")),
        (distribution, LineComponent.CAPACITY, Decimal("1"), "mc", Decimal("18.45")),
        (distribution, LineComponent.SUBSCRIPTION, Decimal("1"), "mc", Decimal("0.00")),
        (distribution, LineComponent.FIXED_NETWORK, Decimal("1"), "mc", Decimal("11.69")),
    ]
    oze = invoice.lines[3]
    assert oze == InvoiceLine(
        section=distribution,
        name="Opłata OZE",
        component=LineComponent.OZE,
        zone="całodobowa",
        sub_period=1,
        quantity=Decimal("150"),
        unit="kWh",
        unit_price_net=Decimal("0.00730"),
        net=Decimal("1.10"),
        vat_rate=Decimal("23"),
        vat=Decimal("0.25"),
        gross=Decimal("1.35"),
        source=Source("T/K1/BN000001/0004/26", 4),
    )
    assert invoice.lines[5].zone is None
    assert invoice.lines[5].name == "Opłata mocowa"


HALF_YEAR = "new_layout_standard_half_year"


def test_reads_december_2025_variant_of_invoice_without_photovoltaics() -> None:
    result = import_document(load(HALF_YEAR))

    assert result.rejection is None
    assert result.invoice is not None
    header = result.invoice.header
    assert header.number == "E/TM3/BN000002/0002/26"
    assert header.issue_date == date(2026, 3, 16)
    assert header.billing_period == DateRange(date(2025, 9, 20), date(2026, 3, 9))
    assert header.address == "UL. PRZYKŁADOWA 2/3, 00-002 TESTOWO"
    assert (header.tariff_group, header.contracted_power_kw) == ("G11", Decimal("5"))
    assert header.settlement_type is SettlementType.STANDARD
    assert header.billing_frequency_months == 6
    assert result.invoice.energy_settlement is None
    assert result.invoice.exported_kwh is None


def test_reads_meter_states_with_multiplier_column() -> None:
    invoice = import_document(load(HALF_YEAR)).invoice
    assert invoice is not None

    states = [
        (r.reading_date, r.reading_type, r.previous, r.current, r.quantity_kwh)
        for r in invoice.readings
    ]
    assert states == [
        (date(2026, 1, 2), ReadingType.CUSTOMER, Decimal("1000"), Decimal("1200"), Decimal("200")),
        (date(2026, 3, 9), ReadingType.REMOTE, Decimal("1200"), Decimal("1300"), Decimal("100")),
    ]
    assert {r.meter_number for r in invoice.readings} == {"S000000000002"}
    assert invoice.imported_kwh == Decimal("300")


def test_numbers_sub_periods_and_follows_a_component_onto_the_next_page() -> None:
    invoice = import_document(load(HALF_YEAR)).invoice
    assert invoice is not None

    fixed = [
        (line.sub_period, line.quantity)
        for line in invoice.lines
        if line.component is LineComponent.FIXED_NETWORK
    ]
    assert fixed == [(1, Decimal("3")), (2, Decimal("0")), (3, Decimal("3"))]
    cogeneration = [line for line in invoice.lines if line.component is LineComponent.COGENERATION]
    assert [(c.quantity, c.gross, c.source.page) for c in cogeneration] == [
        (Decimal("300"), Decimal("1.11"), 4)
    ]
    capacity = next(line for line in invoice.lines if line.component is LineComponent.CAPACITY)
    assert capacity.unit == "mc"
    assert len(invoice.lines) == 13


def test_reads_previous_forecast_and_refund() -> None:
    invoice = import_document(load(HALF_YEAR)).invoice
    assert invoice is not None

    assert invoice.summary.previous_forecast == Amount(
        Decimal("-400.00"), Decimal("-92.00"), Decimal("-492.00")
    )
    assert invoice.summary.amount_due == Decimal("-59.13")
    assert invoice.summary.account_balance is None
    assert invoice.summary.excise_kwh == Decimal("-10")
    assert invoice.summary.same_period_last_year_kwh == Decimal("320")


def test_reads_forecast_schedule() -> None:
    invoice = import_document(load(HALF_YEAR)).invoice
    assert invoice is not None

    assert invoice.forecasts[0] == Forecast(
        number="E/TM3/BN000002/0002/26/1",
        period=DateRange(date(2026, 3, 10), date(2026, 4, 30)),
        import_kwh=Decimal("150"),
        export_kwh=None,
        net=Decimal("120.00"),
        vat=Decimal("27.60"),
        gross=Decimal("147.60"),
        discount=Decimal("0.00"),
        balance_adjustment=Decimal("-59.13"),
        amount_due=Decimal("88.47"),
        due_date=date(2026, 4, 1),
        source=Source("E/TM3/BN000002/0002/26", 2),
    )
    assert [f.due_date for f in invoice.forecasts] == [date(2026, 4, 1), date(2026, 5, 4)]


def load_with(name: str, old: str, new: str) -> RawDocument:
    """Fixture z jednym wierszem podmienionym, żeby zepsuć sumy."""
    document = load(name)
    pages = tuple(
        RawPage(page.number, tuple(new if line == old else line for line in page.lines))
        for page in document.pages
    )
    assert pages != document.pages, f"w fixture'ze nie ma wiersza {old!r}"
    return RawDocument(pages)


def test_rejects_invoice_whose_lines_do_not_add_up_to_settlement_result() -> None:
    document = load_with(
        HALF_YEAR,
        "całodobowa 300 kWh 0,00730 2,19 23 0,50 2,69",
        "całodobowa 300 kWh 0,00730 2,19 23 0,50 3,69",
    )

    result = import_document(document)

    assert result.invoice is None
    assert result.rejection is not None
    assert "Wynikiem rozliczenia" in result.rejection


def test_rejects_invoice_whose_energy_store_does_not_balance() -> None:
    document = load_with(
        MONTHLY,
        "Informujemy, że zgodnie z Ustawą o OZE do wykorzystania pozostaje łączna ilość "
        "energii elektrycznej 1090 kWh.",
        "Informujemy, że zgodnie z Ustawą o OZE do wykorzystania pozostaje łączna ilość "
        "energii elektrycznej 1190 kWh.",
    )

    result = import_document(document)

    assert result.invoice is None
    assert result.rejection is not None
    assert "Magazynu energii" in result.rejection


def test_accepts_energy_store_off_by_balancing_tolerance() -> None:
    document = load_with(
        MONTHLY,
        "Informujemy, że zgodnie z Ustawą o OZE do wykorzystania pozostaje łączna ilość "
        "energii elektrycznej 1090 kWh.",
        "Informujemy, że zgodnie z Ustawą o OZE do wykorzystania pozostaje łączna ilość "
        "energii elektrycznej 1091 kWh.",
    )

    assert import_document(document).rejection is None


def test_rejects_invoice_whose_amount_due_does_not_follow_from_result_and_payments() -> None:
    document = load_with(MONTHLY, "Razem (3-4) 0,00", "Razem (3-4) 5,00")

    result = import_document(document)

    assert result.rejection is not None
    assert "Do zapłaty" in result.rejection


ANNUAL = "new_layout_net_metering_annual"


def test_reads_annual_net_metering_invoice_with_forecasts_for_import_and_export() -> None:
    result = import_document(load(ANNUAL))

    assert result.rejection is None
    invoice = result.invoice
    assert invoice is not None
    assert invoice.header.settlement_type is SettlementType.NET_METERING
    assert invoice.header.billing_frequency_months == 12
    assert invoice.header.contracted_power_kw == Decimal("13")
    assert [(r.direction, r.quantity_kwh) for r in invoice.readings] == [
        (MeterDirection.IMPORT, Decimal("2000")),
        (MeterDirection.EXPORT, Decimal("3000")),
    ]
    assert invoice.energy_settlement is not None
    assert invoice.energy_settlement.store_end_kwh == Decimal("900")
    assert [(f.import_kwh, f.export_kwh, f.amount_due) for f in invoice.forecasts] == [
        (Decimal("100"), Decimal("200"), Decimal("0.00"))
    ]
    assert invoice.summary.excise_amount == Decimal("0.25")


def test_estimated_reading_makes_settlement_basis_estimated() -> None:
    document = load_with(
        ANNUAL, "całodobowa 30/11/2025 (Z) 2 000,0000", "całodobowa 30/11/2025 (S) 2 000,0000"
    )

    invoice = import_document(document).invoice

    assert invoice is not None
    assert invoice.readings[0].reading_type is ReadingType.ESTIMATED
    assert invoice.settlement_basis is SettlementBasis.ESTIMATED_READING


def test_warns_about_unrecognised_invoice_line_but_keeps_it() -> None:
    document = load_with(
        ANNUAL,
        "Stawka opłaty abonamentowej 12 zł/mc 0,40000 4,80 23 1,10 5,90",
        "Nowa opłata testowa 12 zł/mc 0,40000 4,80 23 1,10 5,90",
    )

    result = import_document(document)

    assert result.invoice is not None
    assert any("Nowa opłata testowa" in w for w in result.warnings)
    unknown = [line for line in result.invoice.lines if line.name == "Nowa opłata testowa"]
    assert [line.component for line in unknown] == [None]


def test_rejects_document_that_is_not_a_settlement_invoice() -> None:
    document = RawDocument(
        (RawPage(1, ("Sprzedawca:", "FAKTURA VAT KOREKTA NR 1/2026 DO FAKTURY VAT NR 2/2025")),)
    )

    result = import_document(document, "korekta.pdf")

    assert result.invoice is None
    assert result.file_name == "korekta.pdf"
    assert result.rejection is not None
    assert result.rejection.startswith("Nieobsługiwany rodzaj dokumentu")


def test_values_found_on_other_pages_carry_their_own_page() -> None:
    monthly = import_document(load(MONTHLY)).invoice
    half_year = import_document(load(HALF_YEAR)).invoice
    assert monthly is not None and half_year is not None

    assert monthly.header.site_source == Source("T/K1/BN000001/0004/26", 1)
    assert monthly.summary.same_period_last_year_source == Source("T/K1/BN000001/0004/26", 4)
    assert half_year.summary.same_period_last_year_source == Source("E/TM3/BN000002/0002/26", 3)
    assert monthly.energy_settlement is not None
    assert monthly.energy_settlement.source.page == 4
