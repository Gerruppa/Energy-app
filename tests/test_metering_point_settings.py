"""Ustawienia PPE i wybór PPE przez adres strony, w powłoce Streamlit."""

from dataclasses import replace

from streamlit.testing.v1 import AppTest

from pv_app.app.settings import database_path
from pv_app.domain.metering_point import MeteringPoint, SiteIcon
from pv_app.storage.sqlite import SqliteRepository

HOME = MeteringPoint(
    ppe_number="590000000000000001",
    name="Dom",
    slug="dom",
    icon=SiteIcon.HOUSE,
    charges_car=False,
    address="UL. PRZYKŁADOWA 1, 00-001 TESTOWO",
    net_metering=True,
)
FLAT = replace(
    HOME,
    ppe_number="590000000000000002",
    name="Mieszkanie",
    slug="mieszkanie",
    icon=SiteIcon.FLAT,
    net_metering=False,
)


def _save(*points: MeteringPoint) -> None:
    repo = SqliteRepository(database_path())
    for point in points:
        repo.add_metering_point(point)
    repo.close()


def _saved() -> list[MeteringPoint]:
    repo = SqliteRepository(database_path())
    points = repo.list_metering_points()
    repo.close()
    return points


def _sidebar(app: AppTest, label: str) -> None:
    next(b for b in app.sidebar.button if b.label == label).click().run()


def test_page_address_chooses_the_metering_point_and_shows_only_its_tabs(app: AppTest) -> None:
    _save(HOME, FLAT)
    app.query_params["ppe"] = "mieszkanie"

    app.run()

    assert not app.exception
    assert "Mieszkanie" in app.title[0].value
    assert [t.label for t in app.tabs] == ["Przegląd", "Koszty i Faktury"]


def test_without_known_address_shows_first_metering_point_and_puts_it_in_the_address(
    app: AppTest,
) -> None:
    _save(HOME, FLAT)
    app.query_params["ppe"] = "nieznany"

    app.run()

    assert not app.exception
    assert "Dom" in app.title[0].value
    assert app.query_params["ppe"] == "dom"
    assert [i.value for i in app.info][0].startswith("Nie ma punktu poboru o adresie ?ppe=nieznany")


def test_sidebar_switches_to_another_metering_point_through_the_address(app: AppTest) -> None:
    _save(HOME, FLAT)
    app.run()

    _sidebar(app, "🏢 Mieszkanie")

    assert not app.exception
    assert app.query_params["ppe"] == "mieszkanie"
    assert "Mieszkanie" in app.title[0].value


def test_settings_change_name_icon_and_car_charging_but_keep_the_address(app: AppTest) -> None:
    _save(HOME, FLAT)
    app.run()
    _sidebar(app, "Ustawienia")

    app.text_input(key="settings_name_dom").set_value("Dom rodziców")
    app.radio(key="settings_icon_dom").set_value(SiteIcon.OTHER)
    app.checkbox(key="settings_charges_car_dom").check()
    next(b for b in app.button if b.label == "Zapisz").click().run()

    assert not app.exception
    assert _saved() == [
        replace(HOME, name="Dom rodziców", icon=SiteIcon.OTHER, charges_car=True),
        FLAT,
    ]
    assert app.query_params["ppe"] == "dom"
    assert "Dom rodziców" in app.title[0].value


def test_settings_do_not_save_an_empty_name(app: AppTest) -> None:
    _save(HOME)
    app.run()
    _sidebar(app, "Ustawienia")

    app.text_input(key="settings_name_dom").set_value("  ")
    next(b for b in app.button if b.label == "Zapisz").click().run()

    assert [e.value for e in app.error] == ["Podaj nazwę punktu poboru."]
    assert _saved() == [HOME]


def test_metering_point_is_deleted_only_after_typing_its_name(app: AppTest) -> None:
    _save(HOME, FLAT)
    app.run()
    _sidebar(app, "Ustawienia")
    delete = next(b for b in app.button if b.label == "Usuń punkt poboru")
    assert delete.disabled

    app.text_input(key="settings_delete_name_dom").set_value("Dom").run()
    next(b for b in app.button if b.label == "Usuń punkt poboru").click().run()

    assert not app.exception
    assert _saved() == [FLAT]
    assert "Mieszkanie" in app.title[0].value
    assert app.query_params["ppe"] == "mieszkanie"
    assert [s.value for s in app.success] == ["Usunięto punkt poboru Dom z jego danymi."]


def test_another_metering_point_is_added_from_the_sidebar_and_the_wizard_can_be_closed(
    app: AppTest,
) -> None:
    _save(HOME)
    app.run()

    _sidebar(app, "Dodaj punkt poboru")
    assert app.title[0].value == "Dodaj punkt poboru"
    next(b for b in app.button if b.label == "Anuluj").click().run()

    assert not app.exception
    assert "Dom" in app.title[0].value
