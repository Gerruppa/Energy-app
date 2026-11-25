"""Wykres cen jednostkowych w czasie (Plotly) z wyniku ``unit_price_history``.

Cena to pozioma kreska przez Okres rozliczeniowy Faktury. Faktura z kilkoma podokresami (zmiana
ceny w trakcie okresu) dzieli kreskę na równe części: Faktura nie podaje dat podokresów, więc
podpowiedź mówi, który to podokres.
"""

from datetime import date, datetime, time, timedelta

import plotly.graph_objects as go

from pv_app.domain.invoice import DateRange, LineComponent
from pv_app.features import formatting as fmt
from pv_app.features.costs.analysis import UnitPrice, UnitPriceSeries

COLORS = {
    LineComponent.ACTIVE_ENERGY: "#e8a10c",
    LineComponent.VARIABLE_NETWORK: "#2f5d8a",
    LineComponent.QUALITY: "#6f9ccf",
    LineComponent.OZE: "#3c8a5a",
    LineComponent.COGENERATION: "#8a6fb0",
    LineComponent.CAPACITY: "#c96a2e",
    LineComponent.FIXED_NETWORK: "#2f5d8a",
    LineComponent.TRANSITIONAL: "#8a6fb0",
    LineComponent.SUBSCRIPTION: "#3c8a5a",
}

UNIT_LABELS = {"kWh": "zł za kWh (netto)", "mc": "zł za miesiąc (netto)"}


def _start(day: date) -> datetime:
    return datetime.combine(day, time())


def _end(day: date) -> datetime:
    return datetime.combine(day + timedelta(days=1), time())


def _span(price: UnitPrice) -> tuple[datetime, datetime]:
    start, end = _start(price.period.start), _end(price.period.end)
    part = (end - start) / price.sub_periods
    return start + part * (price.sub_period - 1), start + part * price.sub_period


def series_name(series: UnitPriceSeries, with_zone: bool = True) -> str:
    """Nazwa składnika z wielkiej litery; strefa tylko, gdy ``with_zone`` (składnik ma kilka
    stref, np. dzień i noc w G12)."""
    value = series.component.value
    name = value[0].upper() + value[1:]
    return f"{name} ({series.zone})" if with_zone and series.zone else name


def _month_ticks(history: list[UnitPriceSeries]) -> tuple[list[datetime], list[str]]:
    """Podziałka co pół roku (styczeń i lipiec) z polskimi skrótami miesięcy."""
    days = [d for s in history for p in s.prices for d in (p.period.start, p.period.end)]
    first, last = min(days), max(days)
    ticks, labels = [], []
    for year in range(first.year, last.year + 2):
        for month in (1, 7):
            day = date(year, month, 1)
            if first <= day <= last + timedelta(days=1):
                ticks.append(_start(day))
                labels.append(f"{'sty' if month == 1 else 'lip'} {year}")
    return ticks, labels


def _hover(series: UnitPriceSeries, price: UnitPrice, with_zone: bool) -> str:
    unit = "zł/kWh" if series.unit == "kWh" else f"zł/{series.unit}"
    lines = [
        f"{series_name(series, with_zone)}: {fmt.decimal_pl(price.price_net)} {unit} netto",
        f"Faktura {fmt.period(price.period)}",
    ]
    if price.sub_periods > 1:
        lines.append(
            f"Podokres {price.sub_period} z {price.sub_periods}: cena zmieniła się w trakcie "
            "okresu (Faktura nie podaje dat podokresów)."
        )
    lines.append(f"Źródło: {fmt.source(price.source)}")
    return "<br>".join(lines)


def unit_price_figure(
    history: list[UnitPriceSeries], unit: str, selected: DateRange | None
) -> go.Figure:
    """Ceny składników o jednostce ``unit``; ``selected`` (Okres widoku) jest wyróżniony."""
    figure = go.Figure()
    if selected is not None:
        figure.add_vrect(
            x0=_start(selected.start),
            x1=_end(selected.end),
            fillcolor="rgba(68, 80, 92, 0.06)",
            line_width=0,
            layer="below",
        )
    shown = [s for s in history if s.unit == unit]
    zoned = {s.component for s in shown if sum(t.component is s.component for t in shown) > 1}
    for series in shown:
        with_zone = series.component in zoned
        xs: list[datetime | None] = []
        ys: list[float | None] = []
        hovers: list[str | None] = []
        for price in series.prices:
            start, end = _span(price)
            hover = _hover(series, price, with_zone)
            xs += [start, end, None]
            ys += [float(price.price_net), float(price.price_net), None]
            hovers += [hover, hover, None]
        figure.add_scatter(
            x=xs,
            y=ys,
            mode="lines",
            line={"color": COLORS[series.component], "width": 3},
            name=series_name(series, with_zone),
            hovertext=hovers,
            hoverinfo="text",
        )
    ticks, labels = _month_ticks(shown)
    figure.update_layout(
        height=260,
        margin={"l": 10, "r": 10, "t": 30, "b": 10},
        legend={"orientation": "h", "y": 1.18, "x": 0},
        hovermode="closest",
        yaxis={
            "title": {"text": UNIT_LABELS.get(unit, f"zł za {unit}")},
            "rangemode": "tozero",
            "tickformat": ".2f" if unit == "kWh" else ".0f",
        },
        separators=", ",
        xaxis={"tickvals": ticks, "ticktext": labels},
    )
    return figure


def units(history: list[UnitPriceSeries]) -> list[str]:
    """Jednostki w kolejności: najpierw ceny za kWh, potem opłaty miesięczne i inne."""
    found = list(dict.fromkeys(s.unit for s in history))
    return sorted(found, key=lambda u: (u != "kWh", u != "mc", u))
