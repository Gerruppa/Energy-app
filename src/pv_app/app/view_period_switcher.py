"""Przełącznik Okresu widoku pod nazwą PPE, wspólny dla wszystkich zakładek.

Okres widoku jest w adresie strony (``?ppe=dom&okres=2026-10``, wartości w
``domain/view_period.py``). Bez ``okres`` w adresie widok zaczyna od
``ViewPeriod.default_for`` i od razu zapisuje go w adresie.
"""

import streamlit as st

from pv_app.domain.invoice import DateRange
from pv_app.domain.view_period import ViewPeriod, ViewPeriodKind
from pv_app.features.navigation import VIEW_PERIOD_QUERY_KEY as QUERY_KEY


def _set(period: ViewPeriod) -> None:
    st.query_params[QUERY_KEY] = period.to_query()


def _change_kind(current: ViewPeriod, extent: DateRange, widget_key: str) -> None:
    kind = st.session_state.get(widget_key)
    if kind is None or kind is current.kind:
        return
    dates = current.dates
    anchor = min(dates.end, extent.end) if dates is not None else extent.end
    _set(ViewPeriod.containing(kind, anchor))


def current_view_period(extent: DateRange | None) -> ViewPeriod:
    """Okres widoku z adresu strony; bez niego ``ViewPeriod.default_for`` zapisany w adresie."""
    requested = ViewPeriod.from_query(st.query_params.get(QUERY_KEY, ""))
    if requested is not None:
        return requested
    period = ViewPeriod.default_for(extent)
    if extent is not None:
        _set(period)
    return period


def render_view_period_switcher(period: ViewPeriod, extent: DateRange | None) -> None:
    """Cały okres · Rok · Kwartał · Miesiąc i strzałki ◀ ▶ do sąsiednich okresów z Fakturami."""
    if extent is None:
        return
    kind_column, previous_column, label_column, next_column = st.columns(
        [5, 1, 3, 1], vertical_alignment="center"
    )
    # Klucz zależy od Okresu widoku: kontrolka zawsze pokazuje rodzaj z adresu strony,
    # także po wpisaniu adresu ręcznie albo cofnięciu w przeglądarce.
    widget_key = f"view_period_kind_{period.to_query()}"
    with kind_column:
        st.segmented_control(
            "Okres widoku",
            options=list(ViewPeriodKind),
            format_func=lambda kind: kind.value,
            default=period.kind,
            required=True,
            key=widget_key,
            on_change=_change_kind,
            args=(period, extent, widget_key),
            label_visibility="collapsed",
        )
    if period.kind is ViewPeriodKind.WHOLE:
        with label_column:
            st.markdown(f"**{extent.start:%d.%m.%Y} – {extent.end:%d.%m.%Y}**")
        return
    previous, following = period.shifted(-1), period.shifted(1)
    with previous_column:
        st.button(
            "◀",
            key="view_period_previous",
            help=f"Poprzedni: {previous.label}",
            disabled=not _has_invoices(previous, extent),
            on_click=_set,
            args=(previous,),
        )
    with label_column:
        st.markdown(f"**{period.label}**")
    with next_column:
        st.button(
            "▶",
            key="view_period_next",
            help=f"Następny: {following.label}",
            disabled=not _has_invoices(following, extent),
            on_click=_set,
            args=(following,),
        )


def _has_invoices(period: ViewPeriod, extent: DateRange) -> bool:
    dates = period.dates
    return dates is None or dates.overlaps(extent)
