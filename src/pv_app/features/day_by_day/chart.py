"""Wykresy zakładki Dzień po dniu (Plotly): dni Okresu widoku, godziny dnia, Typowa doba.

Jak wykres miesięczny w Przeglądzie: oddane do sieci w górę, pobrane z sieci w dół, wspólna skala.
"""

import math
from collections.abc import Sequence
from datetime import date
from decimal import Decimal

import plotly.graph_objects as go

from pv_app.domain.formatting import kwh
from pv_app.features import formatting as fmt
from pv_app.features.day_by_day.analysis import Day, Hour, TypicalHour, hour_range
from pv_app.features.monthly_figure import NET, SUN, nice_scale

INCOMPLETE_PATTERN = "/"
"""Kreskowanie słupka dnia bez pełnego Profilu godzinowego."""
_WEEKDAYS = ("pon", "wt", "śr", "czw", "pt", "sob", "niedz")


def _layout(figure: go.Figure, height: int) -> None:
    figure.update_layout(
        barmode="relative",
        height=height,
        margin={"l": 10, "r": 10, "t": 30, "b": 10},
        legend={"orientation": "h", "y": 1.14, "x": 0},
        hovermode="closest",
        yaxis={"title": {"text": "kWh"}, "zeroline": True, "zerolinecolor": "#b4bcc3"},
        separators=", ",
    )


def _mirrored_axis(figure: go.Figure, up: Sequence[Decimal], down: Sequence[Decimal]) -> None:
    """Wspólna skala w górę i w dół, podpisy osi bez minusa (pobrane to też dodatnie kWh);
    bez oddanych (``up`` puste) tylko w dół."""
    highest = float(max([*up, *down, Decimal("0.01")]))
    step = nice_scale(highest)
    bottom = math.ceil(highest / step - 1e-9) * step
    top = bottom if up else 0
    ticks = [v * step for v in range(-round(bottom / step), round(top / step) + 1)]
    figure.update_yaxes(
        range=[-bottom * 1.05, top * 1.05],
        tickvals=ticks,
        ticktext=[fmt.decimal_pl(Decimal(str(abs(round(v, 6))))) for v in ticks],
    )


def _day_hover(day: Day, net_metering: bool) -> str:
    lines = [f"{_WEEKDAYS[day.day.weekday()]} {fmt.day(day.day)}"]
    if net_metering:
        lines.append(f"Oddane do sieci: {kwh(day.exported_kwh, 1)}")
    lines.append(f"Pobrane z sieci: {kwh(day.imported_kwh, 1)}")
    if not day.complete:
        lines.append(f"Niepełny Profil: {day.hour_count} z {day.expected_hours} godzin")
    lines.append("Kliknij, żeby zobaczyć godziny")
    return "<br>".join(lines)


def days_figure(days: Sequence[Day], net_metering: bool, selected: date | None) -> go.Figure:
    """Słupek na każdy dzień; dzień bez pełnego Profilu kreskowany, wybrany dzień z obwódką."""
    x = [d.day for d in days]
    hover = [_day_hover(d, net_metering) for d in days]
    patterns = ["" if d.complete else INCOMPLETE_PATTERN for d in days]
    outline = [2 if d.day == selected else 0 for d in days]
    custom = [d.day.isoformat() for d in days]
    figure = go.Figure()
    if net_metering:
        figure.add_bar(
            x=x,
            y=[float(d.exported_kwh) for d in days],
            name="Oddane do sieci",
            marker={
                "color": SUN,
                "pattern": {"shape": patterns},
                "line": {"width": outline, "color": "#44505c"},
            },
            customdata=custom,
            hovertext=hover,
            hoverinfo="text",
        )
    figure.add_bar(
        x=x,
        y=[-float(d.imported_kwh) for d in days],
        name="Pobrane z sieci",
        marker={
            "color": NET,
            "pattern": {"shape": patterns},
            "line": {"width": outline, "color": "#44505c"},
        },
        customdata=custom,
        hovertext=hover,
        hoverinfo="text",
    )
    _layout(figure, 320)
    _mirrored_axis(
        figure,
        [d.exported_kwh for d in days] if net_metering else [],
        [d.imported_kwh for d in days],
    )
    figure.update_xaxes(tickformat="%d.%m")
    return figure


def hours_figure(hours: Sequence[Hour], net_metering: bool) -> go.Figure:
    """Godziny jednego dnia jako kategorie, więc dzień ma 23 albo 25 słupków przy zmianie czasu."""
    x = [h.label for h in hours]
    figure = go.Figure()
    if net_metering:
        figure.add_bar(
            x=x,
            y=[float(h.exported_kwh) for h in hours],
            name="Oddane do sieci",
            marker={"color": SUN},
            hovertext=[f"{h.label}<br>Oddane do sieci: {kwh(h.exported_kwh, 2)}" for h in hours],
            hoverinfo="text",
        )
    figure.add_bar(
        x=x,
        y=[-float(h.imported_kwh) for h in hours],
        name="Pobrane z sieci",
        marker={"color": NET},
        hovertext=[f"{h.label}<br>Pobrane z sieci: {kwh(h.imported_kwh, 2)}" for h in hours],
        hoverinfo="text",
    )
    _layout(figure, 300)
    _mirrored_axis(
        figure,
        [h.exported_kwh for h in hours] if net_metering else [],
        [h.imported_kwh for h in hours],
    )
    # Podpisy co 3 godziny po godzinie doby, więc w dniach 23- i 25-godzinnych zostają równe.
    ticks = [h for h in hours if h.start_hour % 3 == 0 and not h.extra_hour]
    figure.update_xaxes(
        type="category",
        tickvals=[h.label for h in ticks],
        ticktext=[f"{h.start_hour}:00" for h in ticks],
    )
    return figure


def typical_day_figure(
    typical: Sequence[TypicalHour], net_metering: bool, period_label: str
) -> go.Figure:
    """Średnia każdej godziny doby: oddane jako pole nad osią, pobrane jako linia."""
    x = [h.start_hour + 0.5 for h in typical]
    figure = go.Figure()

    def hover(h: TypicalHour) -> str:
        lines = [f"{hour_range(h.start_hour)}, średnio ({period_label})"]
        if net_metering:
            lines.append(f"Oddane do sieci: {kwh(h.exported_kwh, 2)}")
        lines.append(f"Pobrane z sieci: {kwh(h.imported_kwh, 2)}")
        return "<br>".join(lines)

    text = [hover(h) for h in typical]
    if net_metering:
        figure.add_scatter(
            x=x,
            y=[float(h.exported_kwh) for h in typical],
            name="Oddane do sieci",
            mode="lines",
            line={"color": SUN, "width": 2.5, "shape": "spline"},
            fill="tozeroy",
            hovertext=text,
            hoverinfo="text",
        )
    figure.add_scatter(
        x=x,
        y=[float(h.imported_kwh) for h in typical],
        name="Pobrane z sieci",
        mode="lines",
        line={"color": NET, "width": 2.5, "shape": "spline"},
        hovertext=text,
        hoverinfo="text",
    )
    _layout(figure, 280)
    figure.update_yaxes(title={"text": "kWh w godzinie"}, rangemode="tozero", tickformat=",.2f")
    figure.update_xaxes(
        range=[0, 24], tickvals=list(range(0, 25, 3)), ticktext=[f"{h}:00" for h in range(0, 25, 3)]
    )
    return figure
