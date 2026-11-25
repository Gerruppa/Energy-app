"""Strona „Wgraj pliki”: wiele PDF-ów Faktur i Raportów wartości godzinowych (xlsx) naraz →
podsumowanie i pytanie o nowe PPE."""

import streamlit as st

from pv_app.app.batch_import import ImportSummary, UploadedFile, import_files
from pv_app.features.navigation import IMPORTING
from pv_app.storage.archive import FileArchive
from pv_app.storage.repository import Repository

__all__ = [
    "IMPORTING",
    "IMPORT_SUMMARY",
    "NEW_METERING_POINT",
    "render_import_page",
    "render_summary",
]

IMPORT_SUMMARY = "import_summary"
"""Klucz ``st.session_state``: podsumowanie ostatniej paczki (``ImportSummary``)."""
NEW_METERING_POINT = "new_metering_point"
"""Klucz ``st.session_state``: ``NewMeteringPoint``, dla którego otwarto kreator."""
_UPLOADER_ROUND = "import_uploader_round"


def render_import_page(repository: Repository, archive: FileArchive) -> None:
    st.title("Wgraj pliki")
    st.write(
        "Wybierz jeden lub wiele PDF-ów Faktur Tauron (także korygujących) i Not "
        "obciążeniowych albo Raport wartości godzinowych (xlsx) od Tauron Dystrybucji. "
        "Pliki i dokumenty, które już są w aplikacji, zostaną pominięte; godziny z raportu, "
        "które już są w aplikacji, dostaną wartości z nowszego raportu."
    )
    round_ = st.session_state.setdefault(_UPLOADER_ROUND, 0)
    uploads = st.file_uploader(
        "Faktury (PDF) i Raporty wartości godzinowych (xlsx)",
        type=["pdf", "xlsx"],
        accept_multiple_files=True,
        key=f"uploads_{round_}",
    )
    if st.button("Wgraj", type="primary", disabled=not uploads):
        files = [UploadedFile(u.name, u.getvalue()) for u in uploads or []]
        with st.spinner("Odczytuję pliki…"):
            st.session_state[IMPORT_SUMMARY] = import_files(repository, archive, files)
        # Nowy klucz czyści listę wybranych plików, żeby nie wgrać ich drugi raz.
        st.session_state[_UPLOADER_ROUND] = round_ + 1
        st.rerun()
    summary = st.session_state.get(IMPORT_SUMMARY)
    if summary is not None:
        render_summary(summary)
    if st.button("Wróć do dashboardu"):
        st.session_state.pop(IMPORTING, None)
        st.session_state.pop(IMPORT_SUMMARY, None)
        st.rerun()


def render_summary(summary: ImportSummary) -> None:
    st.subheader("Podsumowanie")
    waiting = sum(len(p.files) for p in summary.new_metering_points)
    columns = st.columns(4 if waiting else 3)
    columns[0].metric("Zaimportowane", len(summary.imported))
    columns[1].metric("Duplikaty", len(summary.duplicates))
    columns[2].metric("Odrzucone", len(summary.rejected))
    if waiting:
        columns[3].metric("Czekają na nowy punkt poboru", waiting)

    for point in summary.new_metering_points:
        count = len(point.files)
        with st.container(border=True):
            st.write(
                f"To Faktura z nowego punktu poboru ({point.address}). Dodać go?"
                if count == 1
                else f"To Faktury ({count}) z nowego punktu poboru ({point.address}). Dodać go?"
            )
            st.caption(", ".join(point.file_names))
            if st.button("Dodaj punkt poboru", key=f"add_{point.ppe_number}", type="primary"):
                st.session_state[NEW_METERING_POINT] = point
                st.rerun()

    for skipped in summary.rejected:
        st.error(f"**{skipped.file_name}**: {skipped.reason}")
    for skipped in summary.duplicates:
        st.info(f"**{skipped.file_name}**: {skipped.reason}")
    for file in summary.imported:
        details = (
            ""
            if file.new_hours is None
            else f" (nowe godziny: {file.new_hours:,})".replace(",", " ")
        )
        st.success(f"**{file.file_name}**: {file.kind.value} {file.invoice_number}{details}")
        for warning in file.warnings:
            st.warning(f"**{file.file_name}**: {warning}")
