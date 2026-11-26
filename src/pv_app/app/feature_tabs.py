"""Zakładki PPE z rejestru ``features``, z wybraną zakładką w adresie strony.

Adres niesie ``Feature.id`` (``&zakladka=koszty``), nie tytuł, więc zmiana tytułu na ekranie
nie psuje zapisanych linków. Przegląd (pierwsza zakładka) nie ma klucza w adresie, także
wpisany ręcznie (``&zakladka=przeglad``). Zakładka niewidoczna dla PPE albo nieznana otwiera
Przegląd i znika z adresu.
"""

from collections.abc import Sequence

import streamlit as st

from pv_app.features.base import Feature, FeatureContext
from pv_app.features.navigation import open_tab, requested_tab


def _active(features: Sequence[Feature]) -> Feature:
    requested = requested_tab()
    active = next((f for f in features if f.id == requested), features[0])
    if requested is not None and active is features[0]:
        open_tab(None)
    return active


def _select(features: Sequence[Feature], widget_key: str) -> None:
    title = st.session_state.get(widget_key)
    selected = next((f for f in features if f.title == title), None)
    if selected is not None:
        open_tab(None if selected is features[0] else selected.id)


def render_feature_tabs(features: Sequence[Feature], context: FeatureContext) -> None:
    """Rysuje wszystkie ``features`` (pierwsza to Przegląd) i otwiera zakładkę z adresu."""
    active = _active(features)
    # Klucz zależy od zakładki z adresu: kontrolka zawsze pokazuje zakładkę z adresu strony,
    # także po cofnięciu w przeglądarce albo po linku, który zakładkę ustawia.
    widget_key = f"feature_tab_{context.metering_point.slug}_{active.id}"
    tabs = st.tabs(
        [f.title for f in features],
        default=active.title,
        key=widget_key,
        on_change=_select,
        args=(features, widget_key),
    )
    for tab, feature in zip(tabs, features, strict=True):
        with tab:
            feature.render(context)
