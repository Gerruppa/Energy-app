"""Strona „Wgraj pliki”: wiele PDF-ów Faktur i Raportów wartości godzinowych (xlsx) naraz →
podsumowanie i pytanie o nowe PPE."""

import streamlit as st

from pv_app.app.batch_import import ImportSummary, UploadedFile, import_files
from pv_app.features.navigation import IMPORTING
from pv_app.storage.archive import FileArchive
from pv_app.storage.repository import Repository

__all__ = [
    "EXISTING_METERING_POINT",
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
ADDED_METERING_POINT = "added_metering_point"
"""Klucz ``st.session_state``: nazwa PPE dodanego kreatorem, który prosi o pozostałe Faktury."""
EXISTING_METERING_POINT = "existing_metering_point"
"""Klucz ``st.session_state``: nazwa PPE, który już był w aplikacji, gdy kreator chciał go
dodać; czekające Faktury trafiły do niego."""
_UPLOADER_ROUND = "import_uploader_round"
_CONFIRM_LEAVE = "import_confirm_leave"


def render_import_page(repository: Repository, archive: FileArchive) -> None:
    st.title("Wgraj pliki")
    if (added := st.session_state.get(ADDED_METERING_POINT)) is not None:
        st.success(
            f"Dodano punkt poboru {added} z jego pierwszą Fakturą. Wgraj teraz pozostałe "
            "Faktury (możesz zaznaczyć wiele PDF-ów naraz), żeby zobaczyć pełną historię; "
            "potem wróć do dashboardu."
        )
    if (existing := st.session_state.get(EXISTING_METERING_POINT)) is not None:
        st.info(
            f"Punkt poboru {existing} już był w aplikacji; jego Faktury z paczki dodano do "
            "niego, a jego nazwa i ustawienia się nie zmieniły."
        )
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
        previous: ImportSummary | None = st.session_state.get(IMPORT_SUMMARY)
        with st.spinner("Odczytuję pliki…"):
            # Faktury czekające na nowy PPE z poprzedniej paczki dołączają do tej.
            st.session_state[IMPORT_SUMMARY] = import_files(
                repository,
                archive,
                files,
                waiting=previous.new_metering_points if previous else (),
            )
        st.session_state.pop(EXISTING_METERING_POINT, None)
        st.session_state.pop(_CONFIRM_LEAVE, None)
        # Nowy klucz czyści listę wybranych plików, żeby nie wgrać ich drugi raz.
        st.session_state[_UPLOADER_ROUND] = round_ + 1
        st.rerun()
    summary = st.session_state.get(IMPORT_SUMMARY)
    if summary is not None:
        render_summary(summary)
    waiting = summary.waiting_file_count if summary is not None else 0
    if st.session_state.get(_CONFIRM_LEAVE) and waiting:
        st.warning(
            "Faktury czekające na nowy punkt poboru nie są zapisane. Po wyjściu trzeba będzie "
            f"wgrać je ponownie (plików do ponownego wgrania: {waiting})."
        )
        leave, stay = st.columns(2)
        if leave.button("Wyjdź bez dodawania punktu poboru", type="primary"):
            _leave()
        if stay.button("Zostań"):
            st.session_state.pop(_CONFIRM_LEAVE, None)
            st.rerun()
    elif st.button("Wróć do dashboardu"):
        if waiting:
            st.session_state[_CONFIRM_LEAVE] = True
            st.rerun()
        _leave()


def _leave() -> None:
    for key in (
        IMPORTING,
        IMPORT_SUMMARY,
        ADDED_METERING_POINT,
        EXISTING_METERING_POINT,
        _CONFIRM_LEAVE,
    ):
        st.session_state.pop(key, None)
    st.rerun()


def render_summary(summary: ImportSummary) -> None:
    st.subheader("Podsumowanie")
    waiting = summary.waiting_file_count
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
                # Po powrocie z kreatora strona nie pyta od razu o wyjście.
                st.session_state.pop(_CONFIRM_LEAVE, None)
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
