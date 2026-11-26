"""Strona „Ustawienia” wybranego PPE: nazwa, ikona, ładowanie auta, adres strony, które
zakładki są widoczne i usunięcie PPE z jego danymi.

Otwierana z paska bocznego, jak strona „Dane”; nie jest zakładką.
"""

from dataclasses import replace

import streamlit as st

from pv_app.app.data_maintenance import delete_metering_point
from pv_app.domain.metering_point import MeteringPoint, SiteIcon
from pv_app.features import available_features
from pv_app.features.navigation import METERING_POINT_QUERY_KEY, forget_view
from pv_app.features.visibility import shows_car, shows_day_by_day
from pv_app.storage.archive import FileArchive
from pv_app.storage.repository import Repository

SETTINGS_PAGE = "settings_page"
"""Klucz ``st.session_state``: strona „Ustawienia” jest otwarta."""
DELETED_METERING_POINT = "deleted_metering_point"
"""Klucz ``st.session_state``: nazwa usuniętego PPE do komunikatu po przejściu dalej."""
_SAVED = "settings_saved"


def close_settings_page() -> None:
    for key in (SETTINGS_PAGE, _SAVED):
        st.session_state.pop(key, None)


def render_settings_page(
    repository: Repository, archive: FileArchive, point: MeteringPoint
) -> None:
    st.title(f"Ustawienia: {point.icon.emoji} {point.name}")
    st.caption(f"Numer PPE {point.ppe_number} · {point.address}")
    if st.button("Wróć do dashboardu"):
        close_settings_page()
        st.rerun()
    if st.session_state.pop(_SAVED, False):
        st.success("Zapisano ustawienia.")

    _render_form(repository, point)
    _render_address(point)
    _render_tabs(repository, point)
    _render_delete(repository, archive, point)


def _key(name: str, point: MeteringPoint) -> str:
    """Klucz pola formularza osobny dla każdego PPE, żeby nie przenosić wpisanych wartości."""
    return f"settings_{name}_{point.slug}"


def _render_form(repository: Repository, point: MeteringPoint) -> None:
    with st.form(_key("form", point)):
        name = st.text_input("Nazwa punktu poboru", value=point.name, key=_key("name", point))
        icons = list(SiteIcon)
        icon = (
            st.radio(
                "Ikona",
                icons,
                index=icons.index(point.icon),
                format_func=lambda i: f"{i.emoji} {i.value}",
                horizontal=True,
                key=_key("icon", point),
            )
            or point.icon
        )
        charges_car = st.checkbox(
            "Ładuję tu auto",
            value=point.charges_car,
            help="Włącza zakładkę Auto z kosztem Ładowań w tym punkcie poboru.",
            key=_key("charges_car", point),
        )
        submitted = st.form_submit_button("Zapisz", type="primary")
    if not submitted:
        return
    if not name.strip():
        st.error("Podaj nazwę punktu poboru.")
        return
    repository.update_metering_point(
        replace(point, name=name.strip(), icon=icon, charges_car=charges_car)
    )
    st.session_state[_SAVED] = True
    st.rerun()


def _render_address(point: MeteringPoint) -> None:
    st.subheader("Adres strony")
    st.code(f"?{METERING_POINT_QUERY_KEY}={point.slug}", language=None)
    st.write(
        "Ten punkt poboru ma własny adres strony: dopisz go do adresu aplikacji i zapisz w "
        "zakładkach przeglądarki, żeby otwierać od razu jego dashboard. Adres zostaje taki sam "
        "po zmianie nazwy."
    )


def _render_tabs(repository: Repository, point: MeteringPoint) -> None:
    st.subheader("Zakładki")
    titles = ", ".join(f.title for f in available_features(repository, point))
    notes = [f"Widoczne: {titles}."]
    if not point.net_metering:
        notes.append(
            "Magazyn energii pojawia się tylko przy rozliczeniu w net-meteringu (fotowoltaika); "
            "rodzaj rozliczenia aplikacja odczytuje z Faktur."
        )
    if shows_day_by_day(repository, point):
        notes.append("Dzień po dniu: Profil godzinowy jest wgrany.")
    else:
        notes.append(
            "Dzień po dniu pojawi się po wgraniu Raportu wartości godzinowych "
            "z eLicznika (plik xlsx od Tauron Dystrybucji) na stronie „Wgraj pliki”."
        )
    if shows_car(repository, point):
        notes.append("Auto (w przygotowaniu): ładowanie auta jest włączone.")
    else:
        notes.append("Auto (w przygotowaniu) pojawi się po zaznaczeniu „Ładuję tu auto”.")
    for note in notes:
        st.markdown(f"- {note}")


def _render_delete(repository: Repository, archive: FileArchive, point: MeteringPoint) -> None:
    with st.expander("Usuń punkt poboru"):
        st.write(
            f"Usuwa punkt poboru {point.name} z tej kopii aplikacji razem z jego Fakturami, "
            "Notami obciążeniowymi, Profilem godzinowym i plikami w archiwum. Tego nie da się "
            "cofnąć; żeby wrócić, trzeba dodać punkt poboru i wgrać pliki ponownie. Inne "
            "punkty poboru zostają."
        )
        confirmation_key = _key("delete_name", point)
        typed = st.text_input(f"Wpisz nazwę „{point.name}”, żeby potwierdzić", key=confirmation_key)
        if st.button("Usuń punkt poboru", type="primary", disabled=typed.strip() != point.name):
            delete_metering_point(repository, archive, point.ppe_number)
            close_settings_page()
            st.session_state.pop(confirmation_key, None)
            st.session_state[DELETED_METERING_POINT] = point.name
            forget_view(metering_point=True)
            st.rerun()
