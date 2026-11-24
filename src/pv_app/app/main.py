"""Powłoka Streamlit. Uruchamiana przez ``Start.bat`` (``python -m pv_app``)."""

import streamlit as st

from pv_app.app.settings import database_path
from pv_app.app.wizard_page import ADDING_METERING_POINT, render_wizard
from pv_app.features import available_features
from pv_app.features.base import FeatureContext
from pv_app.storage.sqlite import SqliteRepository

st.set_page_config(page_title="PV app", page_icon="⚡", layout="wide")

repository = SqliteRepository(database_path())
try:
    metering_points = repository.list_metering_points()

    if st.session_state.get(ADDING_METERING_POINT):
        render_wizard(repository)
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
        requested = st.query_params.get("ppe")
        point = next((p for p in metering_points if p.slug == requested), metering_points[0])
        st.title(f"{point.icon.emoji} {point.name}")
        st.caption(point.address)
        features = available_features(point)
        context = FeatureContext(repository=repository, metering_point=point)
        for tab, feature in zip(st.tabs([f.title for f in features]), features, strict=True):
            with tab:
                feature.render(context)
finally:
    repository.close()
