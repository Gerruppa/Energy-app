"""Powłoka Streamlit. Uruchamiana przez ``Start.bat`` (``python -m pv_app``)."""

import streamlit as st

from pv_app.app.settings import database_path
from pv_app.storage.sqlite import SqliteRepository

st.set_page_config(page_title="PV app", page_icon="⚡", layout="wide")

repository = SqliteRepository(database_path())
try:
    metering_points = repository.list_metering_points()
finally:
    repository.close()

if not metering_points:
    st.title("Witaj!")
    st.write(
        "Aplikacja pokazuje koszty i energię z Twoich Faktur Tauron. "
        "Zacznij od dodania punktu poboru — wystarczy dowolna jego Faktura."
    )
    if st.button("Dodaj punkt poboru", type="primary"):
        st.info("Kreator dodawania punktu poboru pojawi się w kolejnej wersji aplikacji.")
else:
    st.title(metering_points[0].name)
    st.caption("Zakładki pojawią się po wgraniu Faktur.")
