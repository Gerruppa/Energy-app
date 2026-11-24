"""Powłoka Streamlit: co widzi użytkownik po starcie."""

from dataclasses import replace
from pathlib import Path

from streamlit.testing.v1 import AppTest

from pv_app.app.settings import database_path
from pv_app.domain.metering_point import MeteringPoint, SiteIcon
from pv_app.domain.view_period import ViewPeriodKind
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
    assert [t.label for t in app.tabs] == ["Przegląd", "Koszty i Faktury"]
    table = app.tabs[1].dataframe[0].value
    assert list(table["Okres"]) == ["01.10.2026 – 31.10.2026"]
    assert list(table["Podstawa rozliczenia"]) == ["🟢 odczyt rzeczywisty"]
    assert list(table["Koszt okresu"]) == ["32,04 zł"]
    assert "Faktura rozliczeniowa" in table["Dokument"][0]


def test_import_page_accepts_many_files_and_summarises_rejected_ones(app: AppTest) -> None:
    repo = SqliteRepository(database_path())
    repo.add_metering_point(HOME)
    repo.close()
    app.run()
    app.sidebar.button[0].click().run()
    assert app.title[0].value == "Wgraj Faktury"

    app.file_uploader[0].set_value(
        [("a.pdf", b"to nie PDF", "application/pdf"), ("b.pdf", b"ani to", "application/pdf")]
    ).run()
    next(b for b in app.button if b.label == "Wgraj").click().run()

    assert not app.exception
    metrics = {m.label: m.value for m in app.metric}
    assert metrics == {"Zaimportowane": "0", "Duplikaty": "0", "Odrzucone": "2"}
    assert [e.value for e in app.error] == [
        "**a.pdf**: Plik nie jest czytelnym PDF-em.",
        "**b.pdf**: Plik nie jest czytelnym PDF-em.",
    ]


def _home_with_october_invoice() -> None:
    invoice = import_document(
        RawDocument.from_json(FIXTURES / "new_layout_net_metering_monthly.json")
    ).invoice
    assert invoice is not None
    repo = SqliteRepository(database_path())
    repo.add_metering_point(HOME)
    repo.add_invoice(invoice)
    repo.close()


def test_view_period_defaults_to_month_of_latest_invoice_with_chart_and_comparison(
    app: AppTest,
) -> None:
    _home_with_october_invoice()

    app.run()

    assert not app.exception
    assert app.segmented_control[0].value == ViewPeriodKind.MONTH
    assert "**październik 2026**" in [m.value for m in app.markdown]
    overview = app.tabs[0]
    assert len(overview.get("plotly_chart")) == 1
    table = overview.dataframe[0].value
    assert list(table[""]) == ["Pobrane z sieci", "Oddane do sieci", "Koszt okresu"]
    assert list(table["październik 2026"]) == ["150 kWh", "300 kWh", "32,04 zł"]
    # Bez własnej historii: „analogiczny okres” z Faktury (170 kWh w fixture'ze).
    assert list(table["październik 2025"])[0] == "170 kWh (Tauron)"
    # Widok na start trafia do adresu strony, więc da się go udostępnić.
    assert app.query_params["okres"] == "2026-10"


def test_view_period_is_kept_in_page_address_and_filters_every_tab(app: AppTest) -> None:
    _home_with_october_invoice()
    app.query_params["okres"] = "2026-09"

    app.run()

    assert not app.exception
    assert "**wrzesień 2026**" in [m.value for m in app.markdown]
    costs = app.tabs[1]
    assert [i.value for i in costs.info] == ["Brak Faktur za wrzesień 2026."]

    next(b for b in app.button if b.label == "▶").click().run()

    assert app.query_params["okres"] == "2026-10"
    assert len(app.tabs[1].dataframe) == 1


def test_switching_kind_keeps_the_viewed_moment(app: AppTest) -> None:
    _home_with_october_invoice()
    app.run()

    app.segmented_control[0].set_value(ViewPeriodKind.QUARTER).run()

    assert not app.exception
    assert app.query_params["okres"] == "2026-K4"
    assert "**IV kwartał 2026**" in [m.value for m in app.markdown]


def test_default_view_is_last_month_fully_covered_by_invoices(app: AppTest) -> None:
    # Okres rozliczeniowy fixture'a: 20.09.2025 – 9.03.2026.
    invoice = import_document(
        RawDocument.from_json(FIXTURES / "new_layout_standard_half_year.json")
    ).invoice
    assert invoice is not None
    repo = SqliteRepository(database_path())
    repo.add_metering_point(replace(HOME, ppe_number=invoice.header.ppe_number, net_metering=False))
    repo.add_invoice(invoice)
    repo.close()

    app.run()

    assert not app.exception
    assert "**luty 2026**" in [m.value for m in app.markdown]
