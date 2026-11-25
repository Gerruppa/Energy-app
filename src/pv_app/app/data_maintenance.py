"""Narzędzia porządkowe strony danych bez Streamlita: usunięcie Faktury i przebudowa bazy
z archiwum plików (np. po poprawce parsera)."""

from dataclasses import replace

from pv_app.app.batch_import import (
    ImportSummary,
    Reader,
    SkippedFile,
    UploadedFile,
    import_files,
    read_file,
)
from pv_app.storage.archive import FileArchive
from pv_app.storage.repository import Repository

MISSING_COPY = (
    "Brak kopii pliku w archiwum, więc jego dokumentu nie ma już w aplikacji. Wgraj plik ponownie."
)


def delete_invoice(repository: Repository, archive: FileArchive, number: str) -> None:
    """Usuwa Fakturę z bazy razem z kopią jej pliku w archiwum, żeby przebudowa bazy jej nie
    przywróciła; ten sam plik można potem wgrać ponownie."""
    source_file = repository.delete_invoice(number)
    if source_file is not None:
        archive.remove(source_file.archive_name)


def rebuild(
    repository: Repository, archive: FileArchive, *, read: Reader = read_file
) -> ImportSummary:
    """Czyta od nowa wszystkie pliki z archiwum i zapisuje je zamiast dotychczasowych
    dokumentów; PPE i ich ustawienia zostają. Podsumowanie jak przy imporcie.

    Najpierw pliki znane bazie, w kolejności ich wgrania (nowszy Raport wartości godzinowych
    dalej nadpisuje starszy), potem kopie, których baza nie zna (np. odrzucone przy poprzedniej
    przebudowie), od najdawniej zapisanej. Plik znany bazie bez kopii w archiwum jest
    odrzucony."""
    files: list[UploadedFile] = []
    missing: list[SkippedFile] = []
    known: set[str] = set()
    for source_file in repository.list_source_files():
        known.add(source_file.archive_name)
        path = archive.path(source_file.archive_name)
        if path.is_file():
            files.append(UploadedFile(source_file.file_name, path.read_bytes()))
        else:
            missing.append(SkippedFile(source_file.file_name, MISSING_COPY))
    for name in archive.names():
        if name not in known:
            files.append(UploadedFile(archive.file_name(name), archive.path(name).read_bytes()))
    repository.clear_documents()
    summary = import_files(repository, archive, files, read=read)
    return replace(summary, rejected=missing + summary.rejected)
