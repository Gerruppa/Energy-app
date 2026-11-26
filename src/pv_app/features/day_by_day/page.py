"""Zakładka Dzień po dniu: dni Okresu widoku, godziny klikniętego dnia, Typowa doba."""

from collections.abc import Sequence
from datetime import date

import streamlit as st

from pv_app.domain.metering_point import MeteringPoint
from pv_app.features import formatting as fmt
from pv_app.features.base import FeatureContext
from pv_app.features.day_by_day.analysis import Day, DayByDay, day_by_day
from pv_app.features.day_by_day.chart import (
    EXPORTED,
    Series,
    amounts,
    days_figure,
    hours_figure,
    series,
    typical_day_figure,
)
from pv_app.features.navigation import open_import
from pv_app.features.profile_status import profile_status, reminder_text
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
        reminded = _render_reminder(context)
        if view is None or not view.days:
            if not reminded:
                st.info(
                    f"Brak Profilu godzinowego za {label}. Wgraj nowszy Raport wartości "
                    "godzinowych na stronie „Wgraj pliki”."
                )
            return
        shown = series(context.metering_point.net_metering)
        selected = _render_days(view, shown, label)
        day = view.find(selected) if selected is not None else None
        if day is not None:
            _render_hours(day, shown)
        _render_typical_day(view, shown, label)


def _render_reminder(context: FeatureContext) -> bool:
    """Przypomnienie o nowym Raporcie, gdy Profil jest zaległy, a Okres widoku sięga za jego
    koniec; zwraca, czy je pokazano."""
    status = profile_status(context.repository, context.metering_point.ppe_number, context.today)
    if status is None or not status.reminds_in(context.view_period.dates):
        return False
    text, button = st.columns([3, 1], vertical_alignment="center")
    text.warning(reminder_text(status), icon="⚠")
    button.button("Wgraj Raport", on_click=open_import, key="day_by_day_import")
    return True


def _render_days(view: DayByDay, shown: Sequence[Series], label: str) -> date | None:
    """Wykres dni; zwraca dzień, którego godziny pokazać (kliknięty albo domyślny)."""
    st.subheader(
        f"Dzień po dniu: {label}",
        help=" i ".join(f"**{s.label}** ({s.direction})" for s in shown)
        + f" każdego dnia. {BALANCING_HELP} Kreskowany słupek: Profil nie ma wszystkich godzin "
        "tego dnia.",
    )
    clicked = st.session_state.get(SELECTED_DAY_KEY)
    selected = clicked if clicked is not None and view.find(clicked) else view.default_day
    st.plotly_chart(
        days_figure(view.days, shown, selected),
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


def _render_hours(day: Day, shown: Sequence[Series]) -> None:
    st.subheader(
        f"Godzina po godzinie: {fmt.day(day.day)}",
        help="Każdy słupek to jedna godzina; oś pokazuje jej początek, a podpowiedź cały "
        f"przedział. W dniu zmiany czasu doba ma 23 albo 25 godzin. {BALANCING_HELP}",
    )
    if not day.hours:
        st.info("Profil godzinowy nie ma żadnej godziny tego dnia.")
        return
    st.plotly_chart(hours_figure(day.hours, shown), config={"displayModeBar": False})
    totals = " · ".join(amounts(shown, day, 1))
    if not day.complete:
        totals += f" · niepełny Profil: {day.hour_count} z {day.expected_hours} godzin"
    st.caption(totals)


def _render_typical_day(view: DayByDay, shown: Sequence[Series], label: str) -> None:
    st.subheader(
        f"Typowa doba: {label}",
        help=f"Średnio w każdej godzinie doby, ze wszystkich dni Okresu widoku. {BALANCING_HELP}",
    )
    st.plotly_chart(
        typical_day_figure(view.typical_day, shown, label),
        config={"displayModeBar": False},
    )
    if EXPORTED not in shown:
        return
    if surplus := view.surplus_hours:
        ranges = " oraz między ".join(f"{start}:00 a {end}:00" for start, end in surplus)
        st.caption(
            f"Panele dają zwykle nadwyżkę między {ranges}: wtedy najlepiej "
            "włączać pralkę czy zmywarkę, a od 2027 ładować auto."
        )
    else:
        st.caption("W tym okresie panele nie dawały nadwyżki w żadnej godzinie doby (średnio).")
