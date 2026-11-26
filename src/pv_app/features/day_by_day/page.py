"""Zakładka Dzień po dniu: dni Okresu widoku, godziny klikniętego dnia, Typowa doba."""

from datetime import date

import streamlit as st

from pv_app.domain.formatting import kwh
from pv_app.domain.metering_point import MeteringPoint
from pv_app.features import formatting as fmt
from pv_app.features.base import FeatureContext
from pv_app.features.day_by_day.analysis import Day, DayByDay, day_by_day
from pv_app.features.day_by_day.chart import days_figure, hours_figure, typical_day_figure
from pv_app.features.visibility import shows_day_by_day
from pv_app.storage.repository import Repository

BALANCING_HELP = (
    "Liczby są po Zbilansowaniu godzinowym, tak jak na Fakturze: gdy w tej samej godzinie "
    "panele oddały prąd do sieci, a dom pobrał prąd z sieci, Tauron odejmuje mniejsze od "
    "większego i liczy tylko różnicę."
)
DAYS_CHART_KEY = "day_by_day_days"
SELECTED_DAY_KEY = "day_by_day_selected"
"""Klucz ``st.session_state``: kliknięty dzień; poza Okresem widoku pokazany jest dzień domyślny."""
SOURCE_NOTE = "Z Raportu wartości godzinowych (eLicznik Tauron Dystrybucji)."


class DayByDayFeature:
    id = "dzien"
    title = "Dzień po dniu"
    order = 40

    def is_available(self, repository: Repository, metering_point: MeteringPoint) -> bool:
        return shows_day_by_day(repository, metering_point)

    def render(self, context: FeatureContext) -> None:
        view = day_by_day(context.repository, context.filters)
        label = context.view_period.label
        if view is None or not view.days:
            st.info(
                f"Brak Profilu godzinowego za {label}. Wgraj nowszy Raport wartości godzinowych "
                "na stronie „Wgraj pliki”."
            )
            return
        net_metering = context.metering_point.net_metering
        selected = _render_days(view, net_metering, label)
        day = view.find(selected) if selected is not None else None
        if day is not None:
            _render_hours(day, net_metering)
        _render_typical_day(view, net_metering, label)


def _render_days(view: DayByDay, net_metering: bool, label: str) -> date | None:
    """Wykres dni; zwraca dzień, którego godziny pokazać (kliknięty albo domyślny)."""
    st.subheader(
        f"Dzień po dniu: {label}",
        help=(
            "**Oddane do sieci** (w górę) i **pobrane z sieci** (w dół) każdego dnia. "
            if net_metering
            else "**Pobrane z sieci** każdego dnia. "
        )
        + f"{BALANCING_HELP} Kreskowany słupek: Profil nie ma wszystkich godzin tego dnia.",
    )
    clicked = st.session_state.get(SELECTED_DAY_KEY)
    selected = clicked if clicked is not None and view.find(clicked) else view.default_day
    st.plotly_chart(
        days_figure(view.days, net_metering, selected),
        config={"displayModeBar": False},
        key=DAYS_CHART_KEY,
        on_select=_select_clicked_day,
        selection_mode="points",
    )
    incomplete = sum(1 for d in view.days if not d.complete)
    note = "Kliknij dzień, żeby zobaczyć jego godziny niżej."
    if incomplete:
        note += f" Dni bez pełnego Profilu (kreskowane): {incomplete}."
    st.caption(f"{note} {SOURCE_NOTE}")
    return selected


def _select_clicked_day() -> None:
    """Zapamiętuje kliknięty dzień (``customdata`` słupka) i czyści zaznaczenie na wykresie."""
    points = st.session_state[DAYS_CHART_KEY].selection.points
    del st.session_state[DAYS_CHART_KEY]
    clicked = next((p.get("customdata") for p in points if p.get("customdata")), None)
    if clicked:
        st.session_state[SELECTED_DAY_KEY] = date.fromisoformat(str(clicked))


def _render_hours(day: Day, net_metering: bool) -> None:
    st.subheader(
        f"Godzina po godzinie: {fmt.day(day.day)}",
        help="Każdy słupek to jedna godzina; oś pokazuje jej początek, a podpowiedź cały "
        f"przedział. W dniu zmiany czasu doba ma 23 albo 25 godzin. {BALANCING_HELP}",
    )
    if not day.hours:
        st.info("Profil godzinowy nie ma żadnej godziny tego dnia.")
        return
    st.plotly_chart(hours_figure(day.hours, net_metering), config={"displayModeBar": False})
    totals = f"Pobrane z sieci: {kwh(day.imported_kwh, 1)}"
    if net_metering:
        totals = f"Oddane do sieci: {kwh(day.exported_kwh, 1)} · {totals}"
    if not day.complete:
        totals += f" · niepełny Profil: {day.hour_count} z {day.expected_hours} godzin"
    st.caption(totals)


def _render_typical_day(view: DayByDay, net_metering: bool, label: str) -> None:
    st.subheader(
        f"Typowa doba: {label}",
        help=f"Średnio w każdej godzinie doby, ze wszystkich dni Okresu widoku. {BALANCING_HELP}",
    )
    st.plotly_chart(
        typical_day_figure(view.typical_day, net_metering, label),
        config={"displayModeBar": False},
    )
    if net_metering and (surplus := view.surplus_hours) is not None:
        start, end = surplus
        st.caption(
            f"Panele dają zwykle nadwyżkę między {start}:00 a {end}:00: wtedy najlepiej "
            "włączać pralkę czy zmywarkę, a od 2027 ładować auto."
        )
    elif net_metering:
        st.caption("W tym okresie panele nie dawały nadwyżki w żadnej godzinie doby (średnio).")
