"""Oś czasu Faktur (Plotly) z wyniku ``invoice_timeline``.

Pas „Faktury”: Okres rozliczeniowy jako prostokąt w kolorze Podstawy rozliczenia, luki bez
Faktury czerwonym konturem, nakładanie się ciemnym paskiem, Prognozy po ostatniej Fakturze
szarym przerywanym konturem. Pas „Zastąpione”: Faktury, które zastąpiła Faktura korygująca.
Pas „Noty”: Noty obciążeniowe w dniu sprzedaży. Prostokąt Faktury niesie jej numer
(``customdata``), żeby kliknięcie otwierało widok Faktury.
"""

from datetime import date, datetime, time, timedelta

import plotly.graph_objects as go

from pv_app.domain.invoice import DateRange, SettlementBasis
from pv_app.features import formatting as fmt
from pv_app.features.invoice_timeline.analysis import InvoiceTimeline, TimelinePeriod

BASIS_COLORS = {
    SettlementBasis.ACTUAL_READING: "#3f9a5b",
    SettlementBasis.ESTIMATED_READING: "#e0a800",
}
FORECAST_INK = "#7a8691"
CRITICAL = "#c93c2e"
INK = "#44505c"
NOTE_INK = "#8a5cb8"
INVOICES_ROW = "Faktury"
SUPERSEDED_ROW = "Zastąpione"
NOTES_ROW = "Noty"
_DAY_MS = 24 * 3600 * 1000


def _start(day: date) -> datetime:
    return datetime.combine(day, time())


def _end(day: date) -> datetime:
    return datetime.combine(day + timedelta(days=1), time())


def _hover(period: TimelinePeriod) -> str:
    lines = [f"{period.kind.value} {period.number}", fmt.period(period.period)]
    lines.append(fmt.BASIS_BADGES[period.basis])
    if period.corrects:
        lines.append(f"koryguje {period.corrects}")
    if period.superseded_by:
        lines.append(f"zastąpiona przez {period.superseded_by}; liczy się korekta")
    lines.append(f"Koszt okresu: {fmt.zl(period.period_cost)} (Wynik rozliczenia − Bonifikaty)")
    lines.append(f"Wynik rozliczenia: {fmt.source(period.result_source)}")
    lines.append("(kliknij, żeby otworzyć Fakturę)")
    return "<br>".join(lines)


def _bars(periods: list[TimelinePeriod], row: str, opacity: float) -> list[go.Bar]:
    bars = []
    for basis, color in BASIS_COLORS.items():
        chosen = [p for p in periods if p.basis is basis]
        if not chosen:
            continue
        bars.append(
            go.Bar(
                y=[row] * len(chosen),
                base=[_start(p.period.start) for p in chosen],
                x=[p.period.days * _DAY_MS for p in chosen],
                orientation="h",
                marker={"color": color, "opacity": opacity, "line": {"color": "white", "width": 1}},
                customdata=[p.number for p in chosen],
                hovertext=[_hover(p) for p in chosen],
                hoverinfo="text",
                name=fmt.BASIS_BADGES[basis],
                legendgroup=basis.value,
                showlegend=row == INVOICES_ROW,
            )
        )
    return bars


def _outline(
    figure: go.Figure,
    row: int,
    dates: DateRange,
    style: tuple[str, str],
    hover: str,
    name: str,
    first: bool,
) -> None:
    """Prostokąt bez wypełnienia na pasie Faktur (luka, Prognoza) z pustym kwadratem
    w środku, który niesie podpowiedź i wpis w legendzie; bez ``customdata``, więc
    kliknięcie niczego nie otwiera.

    Kontur to kształt układu, nie seria: nałożona druga oś przejmowałaby kliknięcia słupków."""
    color, dash = style
    x0, x1 = _start(dates.start), _end(dates.end)
    figure.add_shape(
        type="rect",
        x0=x0,
        x1=x1,
        y0=row - 0.3,
        y1=row + 0.3,
        line={"color": color, "dash": dash, "width": 1.5},
        layer="below",
    )
    figure.add_trace(
        go.Scatter(
            x=[x0 + (x1 - x0) / 2],
            y=[INVOICES_ROW],
            mode="markers",
            marker={"symbol": "square-open", "size": 9, "color": color},
            hoverinfo="text",
            hovertext=[hover],
            name=name,
            legendgroup=name,
            showlegend=first,
        )
    )


def timeline_figure(timeline: InvoiceTimeline, today: date) -> go.Figure:
    figure = go.Figure()
    settled = [p for p in timeline.periods if p.superseded_by is None]
    superseded = [p for p in timeline.periods if p.superseded_by is not None]
    rows = [NOTES_ROW] * bool(timeline.debit_notes)
    rows += [SUPERSEDED_ROW] * bool(superseded) + [INVOICES_ROW]
    row = rows.index(INVOICES_ROW)
    for bar in _bars(settled, INVOICES_ROW, 0.85) + _bars(superseded, SUPERSEDED_ROW, 0.45):
        figure.add_trace(bar)
    for i, gap in enumerate(timeline.gaps):
        _outline(
            figure,
            row,
            gap,
            (CRITICAL, "dash"),
            f"Luka: {gap.days} dni bez Faktury<br>{fmt.period(gap)}",
            "luka bez Faktury",
            i == 0,
        )
    for i, forecast in enumerate(timeline.forecasts):
        _outline(
            figure,
            row,
            forecast.period,
            (FORECAST_INK, "dot"),
            f"⚪ Prognoza {forecast.forecast_number}<br>{fmt.period(forecast.period)}<br>"
            f"{fmt.kwh(forecast.import_kwh)}, {fmt.zl(forecast.gross)}, "
            f"termin {fmt.day(forecast.due_date)}<br>z Faktury {forecast.invoice_number}<br>"
            "Prognoza nie wchodzi do Kosztu okresu ani kWh.",
            "⚪ Prognoza",
            i == 0,
        )
    for i, overlap in enumerate(timeline.overlaps):
        x0, x1 = _start(overlap.period.start), _end(overlap.period.end)
        first, second = overlap.invoice_numbers
        figure.add_shape(
            type="line",
            x0=x0,
            x1=x1,
            y0=row + 0.45,
            y1=row + 0.45,
            line={"color": INK, "width": 4},
        )
        figure.add_trace(
            go.Scatter(
                x=[x0 + (x1 - x0) / 2],
                y=[INVOICES_ROW],
                mode="markers",
                marker={"symbol": "x-thin-open", "size": 10, "color": INK, "line": {"width": 2}},
                hoverinfo="text",
                hovertext=[
                    f"Nakładanie się: {overlap.period.days} dni rozliczone dwa razy<br>"
                    f"{fmt.period(overlap.period)}<br>{first} i {second}"
                ],
                name="nakładanie się Faktur",
                legendgroup="overlap",
                showlegend=i == 0,
            )
        )
    if timeline.debit_notes:
        notes = timeline.debit_notes
        figure.add_trace(
            go.Scatter(
                x=[_start(n.sale_date) for n in notes],
                y=[NOTES_ROW] * len(notes),
                mode="markers",
                marker={"symbol": "diamond", "size": 11, "color": NOTE_INK},
                hoverinfo="text",
                hovertext=[
                    f"Nota obciążeniowa {n.number}<br>sprzedaż {fmt.day(n.sale_date)}<br>"
                    + (
                        f"pomniejsza Koszt okresu Faktury {n.invoice_number}"
                        if n.invoice_number
                        else "nie dotyczy żadnej Faktury z aplikacji"
                    )
                    + f"<br>{fmt.source(n.source)}"
                    for n in notes
                ],
                name="Nota obciążeniowa",
            )
        )
    figure.add_vline(x=_start(today), line={"color": INK, "dash": "dot", "width": 1})
    figure.add_annotation(
        x=_start(today), y=1, yref="paper", text="dziś", showarrow=False, xanchor="left"
    )
    figure.update_layout(
        height=110 + 45 * len(rows),
        barmode="overlay",
        margin={"l": 10, "r": 10, "t": 20, "b": 10},
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        hoverlabel={"align": "left"},
        legend={"orientation": "h", "y": -0.25},
        separators=", ",
        xaxis={"type": "date", "showgrid": True, "dtick": "M12", "tickformat": "%Y"},
        yaxis={
            "categoryorder": "array",
            "categoryarray": rows,
            "range": [-0.5, len(rows) - 0.5],
            "fixedrange": True,
        },
    )
    return figure
