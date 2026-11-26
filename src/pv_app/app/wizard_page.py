"""Ekran kreatora „Dodaj punkt poboru”: Faktura → potwierdzenie danych → nazwa, ikona, auto.

Ze strony importu kreator zaczyna się od razu od nazwy (``render_naming_step``), bo
Faktura nowego PPE jest już odczytana.
"""

import streamlit as st

from pv_app.app.batch_import import (
    NewMeteringPoint,
    UploadedFile,
    add_new_metering_point,
    import_files,
)
from pv_app.app.import_page import (
    ADDED_METERING_POINT,
    EXISTING_METERING_POINT,
    IMPORT_SUMMARY,
    IMPORTING,
    NEW_METERING_POINT,
)
from pv_app.domain.invoice import Invoice, SettlementType
from pv_app.domain.metering_point import SiteIcon
from pv_app.features import formatting as fmt
from pv_app.features.navigation import METERING_POINT_QUERY_KEY, forget_view
from pv_app.storage.archive import FileArchive
from pv_app.storage.repository import Repository

ADDING_METERING_POINT = "adding_metering_point"
"""Klucz ``st.session_state``: kreator jest otwarty."""
_WIZARD_UPLOAD = "wizard_upload"


def _settlement_text(invoice: Invoice) -> str:
    if invoice.header.settlement_type is SettlementType.NET_METERING:
        store = invoice.energy_settlement
        coefficient = (
            f", Współczynnik opustu {fmt.decimal_pl(store.discount_coefficient)}" if store else ""
        )
        return f"Net-metering (fotowoltaika){coefficient}"
    return "standardowe (bez fotowoltaiki)"


def render_wizard(repository: Repository, archive: FileArchive) -> None:
    st.title("Dodaj punkt poboru")
    st.write(
        "Wgraj jedną Fakturę Tauron (PDF) z tego punktu poboru. Aplikacja odczyta z niej "
        "numer PPE, adres i taryfę, a Ty nadasz punktowi poboru tylko nazwę."
    )
    if repository.list_metering_points() and st.button("Anuluj", key="wizard_cancel"):
        # Z paska bocznego (są już PPE) kreator da się zamknąć przed wgraniem Faktury.
        st.session_state.pop(ADDING_METERING_POINT, None)
        st.session_state.pop(_WIZARD_UPLOAD, None)
        st.rerun()
    upload = st.file_uploader("Faktura (PDF)", type="pdf")
    if upload is None:
        return
    # Ten sam wybrany plik czytamy tylko raz, choć skrypt uruchamia się wielokrotnie.
    file_id, summary = st.session_state.get(_WIZARD_UPLOAD, (None, None))
    if file_id != upload.file_id or summary is None:
        summary = import_files(repository, archive, [UploadedFile(upload.name, upload.getvalue())])
        st.session_state[_WIZARD_UPLOAD] = (upload.file_id, summary)
    if summary.new_metering_points:
        st.session_state[IMPORT_SUMMARY] = summary
        st.session_state[NEW_METERING_POINT] = summary.new_metering_points[0]
        st.rerun()
    for file in summary.rejected + summary.duplicates:
        st.error(file.reason)
    if summary.imported:
        st.info(
            "Ta Faktura należy do punktu poboru, który już jest w aplikacji; "
            "dodano ją do jego Faktur."
        )


def render_naming_step(
    repository: Repository, archive: FileArchive, new_point: NewMeteringPoint
) -> None:
    st.title("Dodaj punkt poboru")
    invoice = new_point.first_invoice
    header = invoice.header
    for waiting in new_point.files:
        for warning in waiting.result.warnings:
            st.warning(f"**{waiting.file.name}**: {warning}")

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
    if st.button("Anuluj"):
        # Ze strony importu wraca do podsumowania, z ekranu powitalnego zamyka kreator.
        for key in (NEW_METERING_POINT, _WIZARD_UPLOAD, ADDING_METERING_POINT):
            st.session_state.pop(key, None)
        if not st.session_state.get(IMPORTING):
            st.session_state.pop(IMPORT_SUMMARY, None)
        st.rerun()
    if not submitted:
        return
    if not name.strip():
        st.error("Podaj nazwę punktu poboru.")
        return
    # PPE, który już jest w aplikacji (podwójne kliknięcie, dodany w międzyczasie), dostaje
    # czekające Faktury bez zmiany ustawień, a kreator wraca do podsumowania.
    added = add_new_metering_point(
        repository, archive, new_point, name=name, icon=icon, charges_car=charges_car
    )
    point = added.point
    st.session_state.pop(NEW_METERING_POINT, None)
    st.session_state.pop(_WIZARD_UPLOAD, None)
    if added.already_existed:
        st.session_state[EXISTING_METERING_POINT] = point.name
    summary = st.session_state.get(IMPORT_SUMMARY)
    if summary is not None:
        st.session_state[IMPORT_SUMMARY] = summary.after_adding(new_point, added.summary)
    if not st.session_state.get(IMPORTING):
        # Kreator z ekranu powitalnego albo paska bocznego kończy się na stronie „Wgraj
        # pliki”, żeby od razu wgrać pozostałe Faktury nowego PPE.
        st.session_state.pop(ADDING_METERING_POINT, None)
        st.session_state.pop(IMPORT_SUMMARY, None)
        st.session_state[IMPORTING] = True
        if not added.already_existed:
            st.session_state[ADDED_METERING_POINT] = point.name
        # Nowy PPE otwiera się na Przeglądzie; Okres widoku i zakładka dotyczyły poprzedniego.
        forget_view()
        st.query_params[METERING_POINT_QUERY_KEY] = point.slug
    st.rerun()
