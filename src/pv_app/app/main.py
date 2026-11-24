"""Powłoka Streamlit. Uruchamiana przez ``Start.bat`` (``python -m pv_app``)."""

import streamlit as st

from pv_app.app.import_page import IMPORTING, NEW_METERING_POINT, render_import_page
from pv_app.app.settings import archive_dir, database_path
from pv_app.app.view_period_switcher import current_view_period, render_view_period_switcher
from pv_app.app.wizard_page import ADDING_METERING_POINT, render_naming_step, render_wizard
from pv_app.features import available_features
from pv_app.features.base import FeatureContext, invoice_extent
from pv_app.storage.archive import FileArchive
from pv_app.storage.sqlite import SqliteRepository

st.set_page_config(page_title="PV app", page_icon="⚡", layout="wide")

repository = SqliteRepository(database_path())
archive = FileArchive(archive_dir())
try:
    metering_points = repository.list_metering_points()

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
        if st.sidebar.button("Wgraj Faktury", type="primary"):
            st.session_state[IMPORTING] = True
            st.rerun()
        requested = st.query_params.get("ppe")
        point = next((p for p in metering_points if p.slug == requested), metering_points[0])
        st.title(f"{point.icon.emoji} {point.name}")
        st.caption(point.address)
        extent = invoice_extent(repository, point.ppe_number)
        view_period = current_view_period(extent)
        render_view_period_switcher(view_period, extent)
        features = available_features(point)
        context = FeatureContext(
            repository=repository, metering_point=point, view_period=view_period
        )
        for tab, feature in zip(st.tabs([f.title for f in features]), features, strict=True):
            with tab:
                feature.render(context)
finally:
    repository.close()
