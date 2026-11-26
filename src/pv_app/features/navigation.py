"""Przejścia przez adres strony: PPE (``?ppe=…``), Okres widoku (``&okres=…``), zakładka
(``&zakladka=…``) i otwarta Faktura (``&faktura=…``), oraz otwarcie strony importu.

Wspólne dla zakładek i powłoki, więc każda zakładka może otworzyć widok Faktury albo stronę
„Wgraj pliki” bez importowania innej zakładki ani powłoki.
"""

from urllib.parse import urlencode

import streamlit as st

from pv_app.domain.view_period import ViewPeriod

METERING_POINT_QUERY_KEY = "ppe"
VIEW_PERIOD_QUERY_KEY = "okres"
INVOICE_QUERY_KEY = "faktura"
TAB_QUERY_KEY = "zakladka"
IMPORTING = "importing"
"""Klucz ``st.session_state``: strona importu jest otwarta."""


def requested_tab() -> str | None:
    """Identyfikator zakładki z adresu strony (``Feature.id``); bez niego Przegląd."""
    return st.query_params.get(TAB_QUERY_KEY) or None


def open_tab(feature_id: str | None) -> None:
    """Ustawia zakładkę w adresie strony; ``None`` to Przegląd, bez klucza w adresie."""
    if feature_id is not None:
        st.query_params[TAB_QUERY_KEY] = feature_id
    elif TAB_QUERY_KEY in st.query_params:
        del st.query_params[TAB_QUERY_KEY]


def requested_invoice() -> str | None:
    """Numer Faktury otwartej w adresie strony."""
    return st.query_params.get(INVOICE_QUERY_KEY) or None


def invoice_href(number: str) -> str:
    """Adres widoku Faktury z bieżącym PPE i Okresem widoku, do linku w HTML (``?…``)."""
    return "?" + urlencode({**st.query_params.to_dict(), INVOICE_QUERY_KEY: number})


def open_invoice(number: str) -> None:
    st.query_params[INVOICE_QUERY_KEY] = number


def close_invoice(view_period: ViewPeriod | None = None) -> None:
    """Wraca do zakładki, z której otwarto Fakturę; z ``view_period`` do Przeglądu
    w tym Okresie widoku („pokaż ten okres w Przeglądzie”)."""
    if INVOICE_QUERY_KEY in st.query_params:
        del st.query_params[INVOICE_QUERY_KEY]
    if view_period is not None:
        st.query_params[VIEW_PERIOD_QUERY_KEY] = view_period.to_query()
        open_tab(None)


def forget_view(*, metering_point: bool = False) -> None:
    """Usuwa z adresu Okres widoku, zakładkę i otwartą Fakturę (dotyczą jednego PPE), z
    ``metering_point`` także sam PPE."""
    keys = [VIEW_PERIOD_QUERY_KEY, TAB_QUERY_KEY, INVOICE_QUERY_KEY]
    if metering_point:
        keys.append(METERING_POINT_QUERY_KEY)
    for key in keys:
        if key in st.query_params:
            del st.query_params[key]


def open_import() -> None:
    """Otwiera stronę „Wgraj pliki” (np. z przycisku „Wgraj Fakturę” przy Brakującej Fakturze)."""
    st.session_state[IMPORTING] = True
