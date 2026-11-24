"""Wykres miesiąc po miesiącu (Plotly) z wyniku ``energy_chart``.

Miesiąc z własną Fakturą to słupek. Faktura za kilka miesięcy to jeden płaski blok przez cały
Okres rozliczeniowy na wysokości średniej miesięcznej: Faktura podaje tylko sumę, więc wykres
nie udaje, że zna podział na miesiące. Rok wcześniej to przerywany kontur tych samych Faktur
przesuniętych o 12 miesięcy. Oddane do sieci w górę, pobrane z sieci w dół, wspólna skala.
"""

import math
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta
from decimal import Decimal

import plotly.graph_objects as go

from pv_app.domain.formatting import kwh
from pv_app.domain.view_period import first_day, last_day, month_index, month_label
from pv_app.features import formatting as fmt
from pv_app.features.overview.analysis import ChartBlock, EnergyChart

SUN = "#e8a10c"
NET = "#2f5d8a"
INK = "#44505c"
CRITICAL = "#c93c2e"
BLOCK_NOTE = (
    "Faktura podaje tylko sumę za cały okres, więc to średnia. Podział na miesiące da eLicznik."
)
SHORT_MONTHS = ("sty", "lut", "mar", "kwi", "maj", "cze", "lip", "sie", "wrz", "paź", "lis", "gru")


@dataclass(frozen=True)
class _Field:
    label: str
    color: str
    sign: int
    total: Callable[[ChartBlock], Decimal | None]
    per_month: Callable[[ChartBlock], Decimal | None]


EXPORTED = _Field(
    "Oddane do sieci", SUN, 1, lambda b: b.exported_kwh, lambda b: b.exported_per_month
)
IMPORTED = _Field(
    "Pobrane z sieci", NET, -1, lambda b: b.imported_kwh, lambda b: b.imported_per_month
)


def _start(day: date) -> datetime:
    return datetime.combine(day, time())


def _end(day: date) -> datetime:
    return datetime.combine(day + timedelta(days=1), time())


def nice_scale(top: float, ticks: int = 4) -> float:
    """Krok osi na okrągłej podziałce (1, 2 lub 5 × 10ⁿ), tak by ``ticks`` kroków objęło ``top``."""
    raw = max(top, 1e-9) / ticks
    power = 10.0 ** math.floor(math.log10(raw))
    return next(m * power for m in (1, 2, 5, 10) if m * power >= raw - 1e-9)


def _hover(block: ChartBlock, fields: list[_Field], earlier: bool) -> str:
    period = fmt.period(block.period)
    head = (
        f"{month_label(month_index(block.period.start))} (własna Faktura)"
        if block.single_month
        else f"Faktura {period}"
    )
    lines = [("Rok wcześniej: " if earlier else "") + head]
    for field in fields:
        total, average = field.total(block), field.per_month(block)
        if total is None or average is None:
            continue
        if block.single_month:
            lines.append(f"{field.label}: {kwh(total)}")
        else:
            lines.append(f"{field.label}: {kwh(total)} łącznie, ≈ {kwh(average)} na miesiąc")
    if not block.single_month:
        lines.append(BLOCK_NOTE)
    lines.append(f"Źródło: {fmt.source(block.source)}")
    return "<br>".join(lines)


def energy_figure(chart: EnergyChart, net_metering: bool, compare: bool) -> go.Figure:
    # Bez fotowoltaiki pobrane rysujemy w górę: nie ma czego pokazać nad osią.
    fields = [EXPORTED, IMPORTED] if net_metering else [replace(IMPORTED, sign=1)]
    figure = go.Figure()
    window_start, window_end = _start(first_day(chart.months[0])), _end(last_day(chart.months[-1]))
    figure.add_vrect(
        x0=_start(first_day(chart.selected[0])),
        x1=_end(last_day(chart.selected[-1])),
        fillcolor="rgba(68, 80, 92, 0.06)",
        line_width=0,
        layer="below",
    )
    highest = 1.0
    shown_blocks = chart.blocks + (chart.year_earlier if compare else ())
    for block in shown_blocks:
        for field in fields:
            value = field.per_month(block)
            if value is not None:
                highest = max(highest, float(value))
    step = nice_scale(highest)
    top = math.ceil(highest / step - 1e-9) * step
    bottom = top if len(fields) == 2 else 0

    legend_seen: set[str] = set()

    def legend(name: str) -> dict[str, object]:
        first = name not in legend_seen
        legend_seen.add(name)
        return {"name": name, "legendgroup": name, "showlegend": first}

    for field in fields:
        for block in chart.blocks:
            value = field.per_month(block)
            if value is None:
                continue
            y = field.sign * float(value)
            start, end = _start(block.drawn.start), _end(block.drawn.end)
            span = (end - start).total_seconds() * 1000
            hover = _hover(block, fields, earlier=False)
            if block.single_month:
                figure.add_bar(
                    x=[start + (end - start) / 2],
                    y=[y],
                    width=[span * 0.56],
                    marker_color=field.color,
                    hovertext=[hover],
                    hoverinfo="text",
                    **legend(field.label),
                )
                continue
            figure.add_bar(
                x=[start + (end - start) / 2],
                y=[y],
                width=[span * 0.98],
                marker_color=field.color,
                opacity=0.28,
                hovertext=[hover],
                hoverinfo="text",
                **legend("Faktura za kilka miesięcy: średnia na miesiąc"),
            )
            figure.add_scatter(
                x=[start, end],
                y=[y, y],
                mode="lines",
                line={"color": field.color, "width": 3},
                hoverinfo="skip",
                showlegend=False,
            )
            if (end - start).days >= 80:
                figure.add_annotation(
                    x=start + (end - start) / 2,
                    y=y,
                    text=f"≈ {kwh(Decimal(abs(y)))} / mies.",
                    showarrow=False,
                    yshift=-12 * field.sign,
                    font={"size": 11, "color": INK},
                )
        if not compare:
            continue
        for block in chart.year_earlier:
            value = field.per_month(block)
            if value is None:
                continue
            y = field.sign * float(value)
            start, end = _start(block.drawn.start), _end(block.drawn.end)
            if block.single_month:
                margin = (end - start) * 0.1
                start, end = start + margin, end - margin
            figure.add_scatter(
                x=[start, start, end, end, start],
                y=[0, y, y, 0, 0],
                mode="lines",
                line={"color": INK, "width": 1, "dash": "dash"},
                hovertext=_hover(block, fields, earlier=True),
                hoverinfo="text",
                hoveron="fills+points",
                **legend("rok wcześniej"),
            )

    if chart.missing_months:
        figure.add_scatter(
            x=[
                _start(first_day(m)) + (_end(last_day(m)) - _start(first_day(m))) / 2
                for m in chart.missing_months
            ],
            y=[0] * len(chart.missing_months),
            mode="text",
            text=["?"] * len(chart.missing_months),
            textfont={"color": CRITICAL, "size": 16},
            hovertext=[f"{month_label(m)}: brak Faktury" for m in chart.missing_months],
            hoverinfo="text",
            name="brak Faktury",
        )

    ticks = [v * step for v in range(-round(bottom / step), round(top / step) + 1)]
    figure.update_layout(
        barmode="overlay",
        height=340,
        margin={"l": 10, "r": 10, "t": 30, "b": 10},
        legend={"orientation": "h", "y": 1.12, "x": 0},
        hovermode="closest",
        yaxis={
            "title": {"text": "kWh na miesiąc"},
            "range": [-bottom * 1.05, top * 1.05],
            "tickvals": ticks,
            "ticktext": [fmt.decimal_pl(Decimal(str(abs(round(v, 6))))) for v in ticks],
            "zeroline": True,
            "zerolinecolor": "#b4bcc3",
        },
        xaxis={
            "range": [window_start, window_end],
            "tickvals": [_start(first_day(m)) + timedelta(days=15) for m in chart.months],
            "ticktext": [
                SHORT_MONTHS[first_day(m).month - 1]
                + (f" {first_day(m):%y}" if first_day(m).month == 1 or i == 0 else "")
                for i, m in enumerate(chart.months)
            ],
        },
    )
    return figure
