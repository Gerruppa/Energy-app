"""Wykresy Magazynu energii (Plotly): stan w czasie i porcje w stanie.

Stan znamy tylko z Faktur, na start i na koniec Okresu rozliczeniowego, więc punkty łączy
kropkowana linia: przebieg w trakcie okresu jest nieznany. Porcje i ich Wygaśnięcia to
szacunek modelu porcji (``domain/energy_store.py``).
"""

import plotly.graph_objects as go

from pv_app.domain.energy_store import MovementKind, Portion, StoreState
from pv_app.features import formatting as fmt
from pv_app.features.energy_store.analysis import EnergyStoreView

SUN = "#e8a10c"
SUN_INK = "#9a6a00"
CRITICAL = "#c93c2e"
PORTION_SHADES = ("#e8a10c", "#efbd55", "#f4d38f", "#f8e4ba")


def _layout(figure: go.Figure, height: int) -> go.Figure:
    figure.update_layout(
        height=height,
        margin={"l": 10, "r": 10, "t": 10, "b": 10},
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        hoverlabel={"align": "left"},
        legend={"orientation": "h", "y": -0.15},
        separators=", ",
    )
    return figure


def store_figure(view: EnergyStoreView) -> go.Figure:
    """Stan z Faktur (pełne kropki: na koniec, puste: na start), Wygaśnięcia między
    Fakturami i porcje, które jeszcze wygasną (szacunek)."""
    figure = go.Figure()
    invoices = [m for m in view.history if m.kind is MovementKind.INVOICE]
    for movement in invoices:
        figure.add_trace(
            go.Scatter(
                x=[movement.period.start, movement.period.end],
                y=[float(movement.start_kwh), float(movement.end_kwh)],
                mode="lines",
                line={"color": SUN_INK, "dash": "dot", "width": 2},
                hoverinfo="skip",
                showlegend=False,
            )
        )
    figure.add_trace(
        go.Scatter(
            x=[m.period.start for m in invoices],
            y=[float(m.start_kwh) for m in invoices],
            mode="markers",
            marker={"color": "white", "size": 8, "line": {"color": SUN_INK, "width": 2}},
            name="na start okresu",
            hovertext=[
                f"Na start okresu {fmt.day(m.period.start)}: {fmt.kwh(m.start_kwh)}<br>"
                f"{fmt.source(m.start_source)}"
                for m in invoices
            ],
            hoverinfo="text",
        )
    )
    figure.add_trace(
        go.Scatter(
            x=[m.period.end for m in invoices],
            y=[float(m.end_kwh) for m in invoices],
            mode="markers",
            marker={"color": SUN, "size": 11, "line": {"color": SUN_INK, "width": 1.5}},
            name="Magazyn energii na koniec okresu (z Faktury)",
            hovertext=[
                f"Magazyn energii {fmt.day(m.period.end)}: {fmt.kwh(m.end_kwh)}<br>"
                f"Przybyło: +{fmt.kwh(m.credited_kwh)} (oddane × "
                f"{fmt.decimal_pl(m.discount_coefficient)})<br>"
                f"Opust: −{fmt.kwh(m.discount_kwh)}<br>"
                f"Udział Sprzedawcy: {fmt.kwh(m.seller_share_kwh)}<br>"
                f"{fmt.source(m.end_source)}"
                for m in invoices
            ],
            hoverinfo="text",
        )
    )
    expiries = [m for m in view.history if m.kind is MovementKind.EXPIRY]
    if expiries:
        figure.add_trace(
            go.Scatter(
                x=[m.period.start for m in expiries],
                y=[float(m.start_kwh) for m in expiries],
                mode="text",
                text=[f"−{fmt.kwh(m.expired_kwh)} wygasło" for m in expiries],
                textposition="top left",
                textfont={"color": CRITICAL},
                hovertext=[
                    f"Wygasło {fmt.kwh(m.expired_kwh)} przed {fmt.day(m.period.start)}<br>"
                    f"Spadek ze stanu na koniec poprzedniej Faktury ({fmt.kwh(m.start_kwh)}) "
                    f"do stanu na start ({fmt.kwh(m.end_kwh)}).<br>"
                    f"{fmt.source(m.start_source)} → {fmt.source(m.end_source)}"
                    for m in expiries
                ],
                hoverinfo="text",
                showlegend=False,
            )
        )
    portions = view.state.portions if view.state is not None else ()
    upcoming = [p for p in portions if p.expires_on is not None]
    if upcoming:
        figure.add_trace(
            go.Bar(
                x=[p.expires_on for p in upcoming],
                y=[float(p.remaining_kwh) for p in upcoming],
                marker={"color": CRITICAL, "opacity": 0.5},
                width=12 * 24 * 3600 * 1000,
                name="porcje, które wygasną (szacunek)",
                hovertext=[_portion_hover(p) for p in upcoming],
                hoverinfo="text",
            )
        )
    figure.update_yaxes(title_text="kWh", rangemode="tozero", gridcolor="#e6e6e6")
    figure.update_xaxes(showgrid=False)
    return _layout(figure, 320)


def _portion_hover(portion: Portion) -> str:
    origin = (
        f"Porcja z Faktury {portion.invoice_number} ({fmt.period(portion.period)})"
        if portion.invoice_number is not None and portion.period is not None
        else "Stan sprzed pierwszej Faktury w danych"
    )
    expires = (
        f"ważne do {fmt.day(portion.expires_on)}"
        if portion.expires_on is not None
        else "data Wygaśnięcia nieznana"
    )
    return f"Szacunek: {fmt.kwh(portion.remaining_kwh)} {expires}<br>{origin}"


def portions_figure(state: StoreState) -> go.Figure:
    """Pasek porcji od najwcześniej wygasającej; porcje wygasające wkrótce na czerwono."""
    figure = go.Figure()
    shade = 0
    expiring = state.expiring
    for portion in state.portions:
        urgent = portion in expiring
        color = CRITICAL if urgent else PORTION_SHADES[min(shade, len(PORTION_SHADES) - 1)]
        if not urgent:
            shade += 1
        figure.add_trace(
            go.Bar(
                x=[float(portion.remaining_kwh)],
                y=[""],
                orientation="h",
                marker={"color": color, "line": {"color": "white", "width": 2}},
                hovertext=[_portion_hover(portion)],
                hoverinfo="text",
                showlegend=False,
            )
        )
    figure.update_layout(barmode="stack")
    figure.update_xaxes(visible=False)
    figure.update_yaxes(visible=False)
    return _layout(figure, 70)
