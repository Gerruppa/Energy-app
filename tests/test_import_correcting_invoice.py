"""Seam importu: surowe wiersze Faktury korygującej (stary układ) → wynik importu (ADR 0005).

Fixture'y ``tests/fixtures/old_layout_correcting_*.json`` mają wymyślone numery i kwoty.
Do obliczeń liczy się część „należało policzyć”; część „policzono” zostaje jako opis korekty.
"""

from datetime import date
from decimal import Decimal
from pathlib import Path

from pv_app.domain.invoice import (
    Amount,
    Correction,
    DateRange,
    DocumentKind,
    Layout,
    SettlementBasis,
    SettlementType,
    Source,
)
from pv_app.ingest import import_document
from pv_app.ingest.raw import RawDocument

FIXTURES = Path(__file__).parent / "fixtures"
NET_METERING = "old_layout_correcting_net_metering"
STANDARD = "old_layout_correcting_standard"


def load(name: str) -> RawDocument:
    return RawDocument.from_json(FIXTURES / f"{name}.json")


def test_correcting_invoice_refers_to_corrected_invoice_and_gives_reason() -> None:
    result = import_document(load(NET_METERING))

    assert result.rejection is None
    assert result.invoice is not None
    invoice = result.invoice
    assert invoice.kind is DocumentKind.CORRECTING_INVOICE
    assert invoice.layout is Layout.OLD
    assert invoice.number == "T/K1/BN000001/0001/26"
    assert invoice.correction == Correction(
        corrected_invoice_number="T/K1/0000009/23",
        corrected_invoice_issue_date=date(2023, 12, 6),
        reason="zmieniliśmy sposób naliczenia premii prądowej przyznanej w roku 2024 zgodnie "
        "z obowiązującymi przepisami Rozporządzenia MKiŚ z dnia 9 września 2023 r. "
        "(Dz.U. 2023 poz. 1847).",
        charged_result=Amount(Decimal("274.50"), Decimal("56.48"), Decimal("330.98")),
        charged_amount_due=Decimal("225.98"),
        difference=Decimal("-49.20"),
        source=Source("T/K1/BN000001/0001/26", 1),
        difference_source=Source("T/K1/BN000001/0001/26", 2),
    )


def test_correcting_invoice_header_comes_from_title_page_and_attachment() -> None:
    invoice = import_document(load(NET_METERING)).invoice
    assert invoice is not None

    header = invoice.header
    assert header.issue_date == date(2026, 3, 17)
    assert header.billing_period == DateRange(date(2022, 12, 1), date(2023, 11, 30))
    assert header.ppe_number == "590000000000000001"
    assert header.site_name == "TESTOWY PUNKT DOM"
    assert header.address == "UL. PRZYKŁADOWA 1, 00-001 TESTOWO"
    assert header.tariff_group == "G11"
    assert header.contracted_power_kw == Decimal("13")
    assert header.settlement_type is SettlementType.NET_METERING
    assert header.source == Source("T/K1/BN000001/0001/26", 1)
    assert header.site_source == Source("T/K1/BN000001/0001/26", 3)
    assert header.issue_date_source == Source("T/K1/BN000001/0001/26", 2)


def test_values_come_from_should_have_charged_part() -> None:
    invoice = import_document(load(NET_METERING)).invoice
    assert invoice is not None

    summary = invoice.summary
    # Podsumowanie z dwiema stawkami VAT: wiersze tej samej etykiety się sumują.
    assert summary.sales == Amount(Decimal("81.50"), Decimal("15.15"), Decimal("96.65"))
    assert summary.distribution == Amount(Decimal("193.00"), Decimal("41.33"), Decimal("234.33"))
    assert summary.result == Amount(Decimal("274.50"), Decimal("56.48"), Decimal("330.98"))
    assert summary.discount == Amount(Decimal("-40.00"), Decimal("-9.20"), Decimal("-49.20"))
    assert summary.amount_due == Decimal("176.78")
    assert summary.source == Source("T/K1/BN000001/0001/26", 1)
    assert {line.source.page for line in invoice.lines} == {4}
    assert {reading.source.page for reading in invoice.readings} == {4}
    assert len(invoice.readings) == 2
    assert invoice.forecasts == ()


def test_energy_settlement_reads_zone_named_in_one_cell_with_energy() -> None:
    invoice = import_document(load(NET_METERING)).invoice
    assert invoice is not None

    store = invoice.energy_settlement
    assert store is not None
    assert (store.imported_kwh, store.exported_kwh) == (Decimal("3200"), Decimal("4000"))
    assert (store.store_start_kwh, store.store_end_kwh) == (Decimal("1000"), Decimal("1200"))
    assert store.exported_after_coefficient_kwh == Decimal("3200")
    assert store.source == Source("T/K1/BN000001/0001/26", 4)
    assert invoice.discount_kwh == Decimal("3000")


def test_correcting_invoice_without_photovoltaics_with_estimated_reading() -> None:
    result = import_document(load(STANDARD))

    assert result.rejection is None
    assert result.invoice is not None
    invoice = result.invoice
    assert invoice.header.ppe_number == "590000000000000002"
    assert invoice.header.issue_date == date(2026, 2, 7)
    assert invoice.energy_settlement is None
    assert invoice.settlement_basis is SettlementBasis.ESTIMATED_READING
    assert invoice.imported_kwh == Decimal("50")
    assert invoice.summary.excise_kwh == Decimal("50")
    assert invoice.summary.discount == Amount(
        Decimal("-10.00"), Decimal("-2.30"), Decimal("-12.30")
    )
    assert invoice.correction is not None
    assert invoice.correction.corrected_invoice_number == "E/TM3/0000005/24"
    assert invoice.correction.charged_amount_due == Decimal("56.58")
    assert invoice.correction.difference == Decimal("-12.30")


def test_result_after_discount_of_correcting_invoice() -> None:
    invoice = import_document(load(STANDARD)).invoice
    assert invoice is not None

    assert invoice.result_after_discount == Decimal("44.28")
