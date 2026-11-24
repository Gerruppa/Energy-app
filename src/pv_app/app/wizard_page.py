"""Ekran kreatora „Dodaj punkt poboru”: Faktura → potwierdzenie danych → nazwa, ikona, auto."""

import streamlit as st

from pv_app.app.wizard import MeteringPointAlreadyExists, add_metering_point_from_invoice
from pv_app.domain.invoice import Invoice, SettlementType
from pv_app.domain.metering_point import SiteIcon
from pv_app.features import formatting as fmt
from pv_app.ingest import import_file
from pv_app.storage.repository import Repository

ADDING_METERING_POINT = "adding_metering_point"
"""Klucz ``st.session_state``: kreator jest otwarty."""


def _settlement_text(invoice: Invoice) -> str:
    if invoice.header.settlement_type is SettlementType.NET_METERING:
        store = invoice.energy_settlement
        coefficient = (
            f", Współczynnik opustu {fmt.decimal_pl(store.discount_coefficient)}" if store else ""
        )
        return f"Net-metering (fotowoltaika){coefficient}"
    return "standardowe (bez fotowoltaiki)"


def render_wizard(repository: Repository) -> None:
    st.title("Dodaj punkt poboru")
    st.write(
        "Wgraj jedną Fakturę Tauron (PDF) z tego punktu. Aplikacja odczyta z niej dane punktu, "
        "a Ty nadasz mu tylko nazwę."
    )
    upload = st.file_uploader("Faktura (PDF)", type="pdf")
    if upload is None:
        return
    # Formularz poniżej uruchamia skrypt od nowa; ten sam plik czytamy tylko raz.
    cache = st.session_state.setdefault("wizard_import", {})
    if upload.file_id not in cache:
        cache.clear()
        cache[upload.file_id] = import_file(upload, upload.name)
    result = cache[upload.file_id]
    if result.invoice is None:
        st.error(result.rejection or "Nie udało się odczytać Faktury.")
        return
    invoice = result.invoice
    header = invoice.header
    for warning in result.warnings:
        st.warning(warning)

    st.subheader("Czy to ten punkt poboru?")
    st.table(
        {
            "": ["Numer PPE", "Adres", "Grupa taryfowa", "Moc umowna", "Rodzaj rozliczenia"],
            "Odczytane z Faktury": [
                header.ppe_number,
                header.address,
                header.tariff_group,
                f"{fmt.decimal_pl(header.contracted_power_kw)} kW",
                _settlement_text(invoice),
            ],
        }
    )
    st.caption(
        f"{fmt.source(header.source)} · Okres rozliczeniowy {fmt.period(header.billing_period)}"
    )

    with st.form("add_metering_point"):
        name = st.text_input("Nazwa punktu poboru", placeholder="np. Dom")
        icon = (
            st.radio(
                "Ikona",
                list(SiteIcon),
                format_func=lambda i: f"{i.emoji} {i.value}",
                horizontal=True,
            )
            or SiteIcon.OTHER
        )
        charges_car = st.checkbox("Ładuję tu auto")
        submitted = st.form_submit_button("Zapisz punkt poboru", type="primary")
    if not submitted:
        return
    if not name.strip():
        st.error("Podaj nazwę punktu poboru.")
        return
    try:
        point = add_metering_point_from_invoice(
            repository, invoice, name=name, icon=icon, charges_car=charges_car
        )
    except MeteringPointAlreadyExists:
        st.error("Ten punkt poboru jest już w aplikacji.")
        return
    st.session_state.pop(ADDING_METERING_POINT, None)
    st.session_state.pop("wizard_import", None)
    st.query_params["ppe"] = point.slug
    st.rerun()
