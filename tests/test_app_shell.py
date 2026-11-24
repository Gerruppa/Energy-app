"""Powłoka Streamlit: co widzi użytkownik po starcie."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

from pv_app.app.settings import database_path
from pv_app.domain.metering_point import MeteringPoint, SiteIcon
from pv_app.ingest import import_document
from pv_app.ingest.raw import RawDocument
from pv_app.storage.sqlite import SqliteRepository

FIXTURES = Path(__file__).parent / "fixtures"

HOME = MeteringPoint(
    ppe_number="590000000000000001",
    name="Dom",
    slug="dom",
    icon=SiteIcon.HOUSE,
    charges_car=False,
    address="UL. PRZYKŁADOWA 1, 00-001 TESTOWO",
    net_metering=True,
)


def test_without_data_shows_welcome_screen_with_add_metering_point_button(
    app: AppTest,
) -> None:
    app.run()

    assert not app.exception
    assert [b.label for b in app.button] == ["Dodaj punkt poboru"]


def test_add_metering_point_button_opens_wizard_asking_for_an_invoice(
    app: AppTest,
) -> None:
    app.run()

    app.button[0].click().run()

    assert not app.exception
    assert app.title[0].value == "Dodaj punkt poboru"
    assert "Faktur" in app.markdown[0].value


def test_with_a_metering_point_does_not_show_welcome_screen(app: AppTest) -> None:
    repo = SqliteRepository(database_path())
    repo.add_metering_point(HOME)
    repo.close()

    app.run()

    assert not app.exception
    assert "Dodaj punkt poboru" not in [b.label for b in app.button]
    assert "Dom" in app.title[0].value


def test_costs_tab_lists_invoices_of_the_metering_point(app: AppTest) -> None:
    invoice = import_document(
        RawDocument.from_json(FIXTURES / "new_layout_net_metering_monthly.json")
    ).invoice
    assert invoice is not None
    repo = SqliteRepository(database_path())
    repo.add_metering_point(HOME)
    repo.add_invoice(invoice)
    repo.close()

    app.run()

    assert not app.exception
    assert [t.label for t in app.tabs] == ["Koszty i Faktury"]
    table = app.dataframe[0].value
    assert list(table["Okres"]) == ["01.10.2026 – 31.10.2026"]
    assert list(table["Podstawa rozliczenia"]) == ["🟢 odczyt rzeczywisty"]
    assert list(table["Koszt okresu"]) == ["32,04 zł"]
    assert "Faktura rozliczeniowa" in table["Dokument"][0]
