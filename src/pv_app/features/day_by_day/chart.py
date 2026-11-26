"""Wykresy zakładki Dzień po dniu (Plotly): dni Okresu widoku, godziny dnia, Typowa doba.

Jak wykres miesięczny w Przeglądzie: oddane do sieci w górę, pobrane z sieci w dół, wspólna skala.
"""

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol

import plotly.graph_objects as go

from pv_app.domain.formatting import kwh
from pv_app.features import formatting as fmt
from pv_app.features.day_by_day.analysis import Day, Hour, TypicalHour, hour_range
from pv_app.features.monthly_figure import INK, NET, SUN, nice_scale

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


class _Energy(Protocol):
    @property
    def imported_kwh(self) -> Decimal: ...

    @property
    def exported_kwh(self) -> Decimal: ...


@dataclass(frozen=True)
class Series:
    """Jedna ilość na wykresach: oddane do sieci w górę, pobrane z sieci w dół."""

    label: str
    color: str
    sign: int
    direction: str
    amount: Callable[[_Energy], Decimal]
    area: bool
    """Na Typowej dobie pole pod linią (oddane), inaczej sama linia."""


EXPORTED = Series("Oddane do sieci", SUN, 1, "w górę", lambda e: e.exported_kwh, area=True)
IMPORTED = Series("Pobrane z sieci", NET, -1, "w dół", lambda e: e.imported_kwh, area=False)


def series(net_metering: bool) -> tuple[Series, ...]:
    """Co pokazać: bez net-meteringu PPE nie oddaje prądu, więc tylko pobrane."""
    return (EXPORTED, IMPORTED) if net_metering else (IMPORTED,)


def amounts(shown: Sequence[Series], item: _Energy, decimals: int) -> list[str]:
    """``Oddane do sieci: 12,5 kWh`` dla każdej pokazanej serii."""
    return [f"{s.label}: {kwh(s.amount(item), decimals)}" for s in shown]


def _mirrored_axis(figure: go.Figure, shown: Sequence[Series], items: Sequence[_Energy]) -> None:
    """Wspólna skala w górę i w dół, podpisy osi bez minusa (pobrane to też dodatnie kWh);
    bez serii w górę tylko w dół."""
    values = [s.amount(i) for s in shown for i in items]
    highest = float(max([*values, Decimal("0.01")]))
    step = nice_scale(highest)
    bottom = math.ceil(highest / step - 1e-9) * step
    top = bottom if any(s.sign > 0 for s in shown) else 0
    ticks = [v * step for v in range(-round(bottom / step), round(top / step) + 1)]
    figure.update_yaxes(
        range=[-bottom * 1.05, top * 1.05],
        tickvals=ticks,
        ticktext=[fmt.decimal_pl(Decimal(str(abs(round(v, 6))))) for v in ticks],
    )


def _day_hover(day: Day, shown: Sequence[Series]) -> str:
    lines = [f"{_WEEKDAYS[day.day.weekday()]} {fmt.day(day.day)}", *amounts(shown, day, 1)]
    if not day.complete:
        lines.append(f"Niepełny Profil: {day.hour_count} z {day.expected_hours} godzin")
    lines.append("Kliknij, żeby zobaczyć godziny")
    return "<br>".join(lines)


def days_figure(days: Sequence[Day], shown: Sequence[Series], selected: date | None) -> go.Figure:
    """Słupek na każdy dzień; dzień bez pełnego Profilu kreskowany, wybrany dzień z obwódką."""
    hover = [_day_hover(d, shown) for d in days]
    patterns = ["" if d.complete else INCOMPLETE_PATTERN for d in days]
    outline = [2 if d.day == selected else 0 for d in days]
    figure = go.Figure()
    for s in shown:
        figure.add_bar(
            x=[d.day for d in days],
            y=[s.sign * float(s.amount(d)) for d in days],
            name=s.label,
            marker={
                "color": s.color,
                "pattern": {"shape": patterns},
                "line": {"width": outline, "color": INK},
            },
            customdata=[d.day.isoformat() for d in days],
            hovertext=hover,
            hoverinfo="text",
        )
    _layout(figure, 320)
    _mirrored_axis(figure, shown, days)
    figure.update_xaxes(tickformat="%d.%m")
    return figure


def hours_figure(hours: Sequence[Hour], shown: Sequence[Series]) -> go.Figure:
    """Godziny jednego dnia jako kategorie, więc dzień ma 23 albo 25 słupków przy zmianie czasu."""
    hover = ["<br>".join([h.label, *amounts(shown, h, 2)]) for h in hours]
    figure = go.Figure()
    for s in shown:
        figure.add_bar(
            x=[h.label for h in hours],
            y=[s.sign * float(s.amount(h)) for h in hours],
            name=s.label,
            marker={"color": s.color},
            hovertext=hover,
            hoverinfo="text",
        )
    _layout(figure, 300)
    _mirrored_axis(figure, shown, hours)
    # Podpisy co 3 godziny po godzinie doby, więc w dniach 23- i 25-godzinnych zostają równe.
    ticks = [h for h in hours if h.start_hour % 3 == 0 and not h.extra_hour]
    figure.update_xaxes(
        type="category",
        tickvals=[h.label for h in ticks],
        ticktext=[f"{h.start_hour}:00" for h in ticks],
    )
    return figure


def typical_day_figure(
    typical: Sequence[TypicalHour], shown: Sequence[Series], period_label: str
) -> go.Figure:
    """Średnia każdej godziny doby: oddane jako pole nad osią, pobrane jako linia."""
    hover = [
        "<br>".join(
            [f"{hour_range(h.start_hour)}, średnio ({period_label})", *amounts(shown, h, 2)]
        )
        for h in typical
    ]
    figure = go.Figure()
    for s in shown:
        figure.add_scatter(
            x=[h.start_hour + 0.5 for h in typical],
            y=[float(s.amount(h)) for h in typical],
            name=s.label,
            mode="lines",
            line={"color": s.color, "width": 2.5, "shape": "spline"},
            fill="tozeroy" if s.area else None,
            hovertext=hover,
            hoverinfo="text",
        )
    _layout(figure, 280)
    figure.update_yaxes(title={"text": "kWh w godzinie"}, rangemode="tozero", tickformat=",.2f")
    figure.update_xaxes(
        range=[0, 24], tickvals=list(range(0, 25, 3)), ticktext=[f"{h}:00" for h in range(0, 25, 3)]
    )
    return figure
