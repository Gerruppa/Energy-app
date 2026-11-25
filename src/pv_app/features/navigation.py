"""Przejścia przez adres strony: Okres widoku (``&okres=…``) i otwarta Faktura (``&faktura=…``),
oraz otwarcie strony importu.

Wspólne dla zakładek i powłoki, więc każda zakładka może otworzyć widok Faktury albo stronę
„Wgraj pliki” bez importowania innej zakładki ani powłoki.
"""

from urllib.parse import urlencode

import streamlit as st

from pv_app.domain.view_period import ViewPeriod

VIEW_PERIOD_QUERY_KEY = "okres"
INVOICE_QUERY_KEY = "faktura"
IMPORTING = "importing"
"""Klucz ``st.session_state``: strona importu jest otwarta."""


def requested_invoice() -> str | None:
    """Numer Faktury otwartej w adresie strony."""
    return st.query_params.get(INVOICE_QUERY_KEY) or None


def invoice_href(number: str) -> str:
    """Adres widoku Faktury z bieżącym PPE i Okresem widoku, do linku w HTML (``?…``)."""
    return "?" + urlencode({**st.query_params.to_dict(), INVOICE_QUERY_KEY: number})


def open_invoice(number: str) -> None:
    st.query_params[INVOICE_QUERY_KEY] = number


def close_invoice(view_period: ViewPeriod | None = None) -> None:
    """Wraca do zakładek; z ``view_period`` od razu ustawia Okres widoku."""
    if INVOICE_QUERY_KEY in st.query_params:
        del st.query_params[INVOICE_QUERY_KEY]
    if view_period is not None:
        st.query_params[VIEW_PERIOD_QUERY_KEY] = view_period.to_query()


def open_import() -> None:
    """Otwiera stronę „Wgraj pliki” (np. z przycisku „Wgraj Fakturę” przy Brakującej Fakturze)."""
    st.session_state[IMPORTING] = True
