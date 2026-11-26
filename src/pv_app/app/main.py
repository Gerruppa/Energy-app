"""Powłoka Streamlit. Uruchamiana przez ``Start.bat`` (``python -m pv_app``)."""

from datetime import date

import streamlit as st

from pv_app.app.data_page import DATA_PAGE, close_data_page, render_data_page
from pv_app.app.import_page import IMPORTING, NEW_METERING_POINT, render_import_page
from pv_app.app.settings import archive_dir, database_path
from pv_app.app.settings_page import (
    DELETED_METERING_POINT,
    SETTINGS_PAGE,
    close_settings_page,
    render_settings_page,
)
from pv_app.app.view_period_switcher import current_view_period, render_view_period_switcher
from pv_app.app.wizard_page import ADDING_METERING_POINT, render_naming_step, render_wizard
from pv_app.features import available_features
from pv_app.features.base import FeatureContext, invoice_extent, view_extent
from pv_app.features.invoice_view.page import render_invoice_page
from pv_app.features.navigation import METERING_POINT_QUERY_KEY, forget_view, requested_invoice
from pv_app.storage.archive import FileArchive
from pv_app.storage.sqlite import SqliteRepository

st.set_page_config(page_title="PV app", page_icon="⚡", layout="wide")

repository = SqliteRepository(database_path())
archive = FileArchive(archive_dir())


def _close_pages() -> None:
    close_data_page()
    close_settings_page()


def _switch_to(slug: str) -> None:
    """Inny PPE ma własny adres strony; Okres widoku i otwarta Faktura go nie dotyczą."""
    _close_pages()
    forget_view()
    st.query_params[METERING_POINT_QUERY_KEY] = slug


try:
    metering_points = repository.list_metering_points()
    if (deleted := st.session_state.pop(DELETED_METERING_POINT, None)) is not None:
        st.success(f"Usunięto punkt poboru {deleted} z jego danymi.")

    if (new_point := st.session_state.get(NEW_METERING_POINT)) is not None:
        render_naming_step(repository, archive, new_point)
    elif st.session_state.get(ADDING_METERING_POINT):
        render_wizard(repository, archive)
    elif st.session_state.get(IMPORTING):
        render_import_page(repository, archive)
    elif not metering_points:
        st.title("Witaj!")
        st.write(
            "Aplikacja pokazuje koszty i energię z Twoich Faktur Tauron. "
            "Zacznij od dodania punktu poboru — wystarczy dowolna jego Faktura."
        )
        if st.button("Dodaj punkt poboru", type="primary"):
            st.session_state[ADDING_METERING_POINT] = True
            st.rerun()
    else:
        requested = st.query_params.get(METERING_POINT_QUERY_KEY)
        point = next((p for p in metering_points if p.slug == requested), metering_points[0])
        if requested != point.slug:
            if requested:
                st.info(
                    f"Nie ma punktu poboru o adresie ?{METERING_POINT_QUERY_KEY}={requested} "
                    f"(może został usunięty); pokazuję {point.name}."
                )
                forget_view()
            # Adres strony zawsze wskazuje oglądany PPE, więc da się go zapisać w zakładkach.
            st.query_params[METERING_POINT_QUERY_KEY] = point.slug
        if st.sidebar.button("Wgraj pliki", type="primary"):
            _close_pages()
            st.session_state[IMPORTING] = True
            st.rerun()
        if st.sidebar.button("Dane", help="Oś czasu Faktur, usuwanie Faktur, przebudowa bazy"):
            close_settings_page()
            st.session_state[DATA_PAGE] = True
            st.rerun()
        if st.sidebar.button(
            "Ustawienia", help="Nazwa, ikona, ładowanie auta, adres strony, usunięcie punktu poboru"
        ):
            close_data_page()
            st.session_state[SETTINGS_PAGE] = True
            st.rerun()
        st.sidebar.subheader("Punkty poboru")
        for other in metering_points:
            # Każdy PPE osobno, bez sum ani porównań między nimi.
            if st.sidebar.button(
                f"{other.icon.emoji} {other.name}",
                key=f"ppe_{other.slug}",
                disabled=other == point,
                width="stretch",
            ):
                _switch_to(other.slug)
                st.rerun()
        if st.sidebar.button("Dodaj punkt poboru"):
            _close_pages()
            st.session_state[ADDING_METERING_POINT] = True
            st.rerun()
        # Widok na start z Faktur; strzałki ◀ ▶ sięgają też do końca Profilu godzinowego.
        view_period = current_view_period(invoice_extent(repository, point.ppe_number))
        extent = view_extent(repository, point.ppe_number)
        context = FeatureContext(
            repository=repository, metering_point=point, view_period=view_period
        )
        if st.session_state.get(SETTINGS_PAGE):
            render_settings_page(repository, archive, point)
        elif st.session_state.get(DATA_PAGE):
            render_data_page(context, archive, today=date.today())
        elif (invoice_number := requested_invoice()) is not None:
            render_invoice_page(context, archive, invoice_number)
        else:
            st.title(f"{point.icon.emoji} {point.name}")
            st.caption(point.address)
            render_view_period_switcher(view_period, extent)
            features = available_features(repository, point)
            for tab, feature in zip(st.tabs([f.title for f in features]), features, strict=True):
                with tab:
                    feature.render(context)
finally:
    repository.close()
