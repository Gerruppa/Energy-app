"""Strona danych: usunięcie Faktury i przebudowa bazy z archiwum plików, na Repository
w pamięci i prawdziwym archiwum w katalogu tymczasowym; pliki to zrzuty wierszy z fixture'ów."""

from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

from pv_app.app.batch_import import UploadedFile, import_files
from pv_app.app.data_maintenance import delete_invoice, rebuild
from pv_app.ingest import ImportResult
from pv_app.storage.archive import FileArchive
from pv_app.storage.in_memory import InMemoryRepository
from test_batch_import import (
    HOME,
    MONTHLY,
    hourly_report_file,
    read_fixture,
    read_sheet_or_fixture,
    upload,
)


@pytest.fixture
def repository() -> InMemoryRepository:
    repo = InMemoryRepository()
    repo.add_metering_point(HOME)
    return repo


@pytest.fixture
def archive(tmp_path: Path) -> FileArchive:
    return FileArchive(tmp_path / "archive")


def test_deleted_invoice_leaves_database_and_archive_so_its_file_imports_again(
    repository: InMemoryRepository, archive: FileArchive
) -> None:
    file = upload(MONTHLY)
    (imported,) = import_files(repository, archive, [file], read=read_fixture).imported

    delete_invoice(repository, archive, imported.invoice_number)

    assert repository.list_invoices(HOME.ppe_number) == []
    assert not archive.path(imported.archive_name).exists()
    again = import_files(repository, archive, [file], read=read_fixture)
    assert [f.invoice_number for f in again.imported] == [imported.invoice_number]


def read_with_old_parser(file: UploadedFile) -> ImportResult:
    """Czytnik „przed poprawką parsera”: myli nazwę obiektu na Fakturze."""
    result = read_fixture(file)
    assert result.invoice is not None
    header = replace(result.invoice.header, site_name="BŁĄD PARSERA")
    return replace(result, invoice=replace(result.invoice, header=header))


def test_rebuild_reads_every_archived_file_again_with_current_parser(
    repository: InMemoryRepository, archive: FileArchive
) -> None:
    import_files(repository, archive, [upload(MONTHLY)], read=read_with_old_parser)

    summary = rebuild(repository, archive, read=read_fixture)

    assert [f.file_name for f in summary.imported] == [f"{MONTHLY}.pdf"]
    assert summary.duplicates == []
    [invoice] = repository.list_invoices(HOME.ppe_number)
    assert invoice == read_fixture(upload(MONTHLY)).invoice
    assert repository.list_metering_points() == [HOME]


def test_rebuild_keeps_import_order_so_newer_hourly_report_wins(
    repository: InMemoryRepository, archive: FileArchive
) -> None:
    older = hourly_report_file("b-wrzesień.xlsx", HOME.ppe_number, (1, 0.25))
    newer = hourly_report_file("a-październik.xlsx", HOME.ppe_number, (1, 0.75))
    import_files(repository, archive, [older, newer], read=read_sheet_or_fixture)

    rebuild(repository, archive, read=read_sheet_or_fixture)

    assert [r.imported_kwh for r in repository.list_hourly_readings(HOME.ppe_number)] == [
        Decimal("0.75")
    ]


def test_document_whose_archived_copy_is_missing_is_reported_as_rejected(
    repository: InMemoryRepository, archive: FileArchive
) -> None:
    (imported,) = import_files(repository, archive, [upload(MONTHLY)], read=read_fixture).imported
    archive.remove(imported.archive_name)

    summary = rebuild(repository, archive, read=read_fixture)

    assert [f.file_name for f in summary.rejected] == [f"{MONTHLY}.pdf"]
    assert "archiwum" in summary.rejected[0].reason
    assert repository.list_invoices(HOME.ppe_number) == []


def read_nothing(file: UploadedFile) -> ImportResult:
    """Czytnik z błędem, który odrzuca każdy plik."""
    return ImportResult(file.name, rejection="Nie udało się odczytać Faktury.")


def test_file_rejected_by_a_rebuild_comes_back_with_the_next_rebuild(
    repository: InMemoryRepository, archive: FileArchive
) -> None:
    import_files(repository, archive, [upload(MONTHLY)], read=read_fixture)
    rebuild(repository, archive, read=read_nothing)

    summary = rebuild(repository, archive, read=read_fixture)

    assert [f.file_name for f in summary.imported] == [f"{MONTHLY}.pdf"]
    assert len(repository.list_invoices(HOME.ppe_number)) == 1
