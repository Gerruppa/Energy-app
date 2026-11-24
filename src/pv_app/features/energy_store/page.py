from decimal import Decimal
from functools import partial

import streamlit as st

from pv_app.domain.energy_store import (
    EXPIRING_SOON_MONTHS,
    MovementKind,
    Portion,
    StoreMovement,
    StoreState,
)
from pv_app.domain.metering_point import MeteringPoint
from pv_app.features import formatting as fmt
from pv_app.features.base import FeatureContext
from pv_app.features.energy_store.analysis import EnergyStoreView, energy_store_view
from pv_app.features.energy_store.chart import portions_figure, store_figure
from pv_app.features.navigation import open_invoice
from pv_app.features.terms import ESTIMATE_HELP, seller_share_help, store_help

MOVEMENTS_KEY = "store_movements"
ROUNDING_HELP = (
    "Zaokrąglenie Taurona: stan na koniec z Faktury różni się czasem o 1–2 kWh od bilansu "
    "wiersza, bo Tauron rozlicza Magazyn energii godzina po godzinie i zaokrągla."
)


class EnergyStoreFeature:
    id = "magazyn"
    title = "Magazyn energii"
    order = 20

    def is_available(self, metering_point: MeteringPoint) -> bool:
        return metering_point.net_metering

    def render(self, context: FeatureContext) -> None:
        view = energy_store_view(context.repository, context.filters)
        if view is None:
            st.info("Brak Faktur z Rozliczeniem OZE dla tego punktu poboru.")
            return
        if view.state is None:
            st.info("Żadna Faktura nie kończy się przed końcem wybranego okresu.")
        else:
            _render_state(view, view.state)
        st.subheader("Magazyn energii w czasie", help=ESTIMATE_HELP)
        st.plotly_chart(store_figure(view), config={"displayModeBar": False})
        st.caption(
            "Stan znamy tylko z Faktur: na start i na koniec każdego okresu. Kropkowana linia "
            "między nimi oznacza, że przebieg w trakcie okresu jest nieznany. Czerwone słupki "
            "to porcje, które wygasną, jeśli ich nie odbierzecie (szacunek)."
        )
        _render_movements(view, context.view_period.label)


def _render_state(view: EnergyStoreView, state: StoreState) -> None:
    coefficient = state.movement.discount_coefficient
    balance, expiring, seller = st.columns(3)
    balance.metric("Magazyn energii", fmt.kwh(state.balance_kwh), help=store_help(coefficient))
    balance.caption(f"Stan na {fmt.day(state.as_of)}, {fmt.source(state.source)}")
    expiring.metric(
        f"Wygaśnie do {fmt.day(state.expiring_until)}",
        fmt.kwh(state.expiring_kwh),
        help=ESTIMATE_HELP,
    )
    expiring.caption(f"szacunek: porcje, które wygasną w {EXPIRING_SOON_MONTHS} miesiące od stanu")
    seller.metric(
        "Udział Sprzedawcy",
        fmt.kwh(view.seller_share_kwh),
        help=seller_share_help(coefficient),
    )
    seller.caption("z Faktur w tabeli niżej (część Energii oddanej)")
    if state.portions:
        st.plotly_chart(portions_figure(state), config={"displayModeBar": False})
        st.caption(" · ".join(_portion_text(p, state) for p in state.portions) + " (szacunek)")
    with st.expander("Co to jest Magazyn energii?"):
        st.write(f"{store_help(coefficient)} {ESTIMATE_HELP}")


def _portion_text(portion: Portion, state: StoreState) -> str:
    amount = fmt.kwh(portion.remaining_kwh)
    if portion.expires_on is None:
        return f"{amount} sprzed pierwszej Faktury"
    expires = fmt.day(portion.expires_on)
    if portion.expires_on < state.as_of:
        return f"{amount} po terminie {expires}, wygaśnie przed następną Fakturą"
    if portion.expires_on <= state.expiring_until:
        return f"{amount} wygaśnie {expires}"
    return f"{amount} ważne do {expires}"


def _render_movements(view: EnergyStoreView, period_label: str) -> None:
    st.subheader(
        "Ruch w Magazynie energii, Faktura po Fakturze",
        help="W każdym wierszu: na start + przybyło − w tym z Magazynu − wygasło = na koniec, "
        f"z dokładnością do zaokrąglenia Taurona. {ROUNDING_HELP} Wygaśnięcie widać jako "
        "spadek stanu na start Faktury poniżej stanu na koniec poprzedniej Faktury; Faktura "
        "nie podaje go wprost.",
    )
    if not view.movements:
        st.info(f"Brak Faktur za {period_label}.")
        return
    rounding = any(m.rounding_kwh for m in view.movements)
    st.dataframe(
        [_movement_entry(m, rounding) for m in view.movements],
        hide_index=True,
        key=MOVEMENTS_KEY,
        on_select=partial(_open_selected, [m.invoice_number for m in view.movements]),
        selection_mode="single-row",
    )
    st.caption(
        "Kliknij wiersz, żeby otworzyć Fakturę po ludzku. Stany na start i na koniec są "
        "z Faktur. „W tym z Magazynu” to część prądu pobranego z sieci pokryta z Magazynu "
        "energii (na Fakturze: Opust): pobrane z sieci minus kWh, za które Faktura liczy "
        "cenę energii. Wygasło: stan na koniec poprzedniej Faktury minus stan na start "
        "następnej." + (f" {ROUNDING_HELP}" if rounding else "")
    )


def _movement_entry(movement: StoreMovement, rounding: bool) -> dict[str, object]:
    """Wiersz tabeli; z ``rounding`` także kolumna zaokrąglenia Taurona."""

    def change(sign: str, value: Decimal) -> str:
        return f"{sign}{fmt.kwh(value)}" if value else "—"

    if movement.kind is MovementKind.EXPIRY:
        label = f"Wygaśnięcie przed {fmt.day(movement.period.start)}"
        source = f"{fmt.source(movement.start_source)} → {fmt.source(movement.end_source)}"
    else:
        label = fmt.period(movement.period)
        source = fmt.source(movement.end_source)
    coefficient = fmt.decimal_pl(movement.discount_coefficient)
    entry: dict[str, object] = {
        "Okres": label,
        "Na start": fmt.kwh(movement.start_kwh),
        f"+ przybyło (×{coefficient})": change("+", movement.credited_kwh),
        "Pobrane z sieci": change("", movement.imported_kwh),
        "− w tym z Magazynu": change("−", movement.discount_kwh),
        "− wygasło": change("−", movement.expired_kwh),
        "Na koniec": fmt.kwh(movement.end_kwh),
    }
    if rounding:
        entry["Zaokrąglenie Taurona"] = change(
            "+" if movement.rounding_kwh > 0 else "", movement.rounding_kwh
        )
    entry["Udział Sprzedawcy"] = change("", movement.seller_share_kwh)
    entry["Źródło"] = source
    return entry


def _open_selected(numbers: list[str]) -> None:
    """Otwiera Fakturę z zaznaczonego wiersza i czyści zaznaczenie."""
    selected = st.session_state[MOVEMENTS_KEY].selection.rows
    del st.session_state[MOVEMENTS_KEY]
    if selected:
        open_invoice(numbers[selected[0]])
