"""Seam importu paczki: wgrane pliki → zapis w Repository i archiwum, podsumowanie.

Pliki w testach to zrzuty wierszy z ``tests/fixtures/`` (ADR 0005), czytane wstrzykniętym
czytnikiem zamiast PDF-a; liczby w nich są wymyślone.
"""

import json
from decimal import Decimal
from pathlib import Path

import pytest

from pv_app.app.batch_import import UploadedFile, add_new_metering_point, import_files
from pv_app.domain.invoice import DocumentKind
from pv_app.domain.metering_point import MeteringPoint, SiteIcon
from pv_app.ingest import ImportResult, import_document, import_sheet
from pv_app.ingest.raw import RawDocument
from pv_app.storage.archive import FileArchive
from pv_app.storage.in_memory import InMemoryRepository

FIXTURES = Path(__file__).parent / "fixtures"
MONTHLY = "new_layout_net_metering_monthly"
HALF_YEAR = "new_layout_standard_half_year"

HOME = MeteringPoint(
    ppe_number="590000000000000001",
    name="Dom",
    slug="dom",
    icon=SiteIcon.HOUSE,
    charges_car=False,
    address="UL. PRZYKŁADOWA 1, 00-001 TESTOWO",
    net_metering=True,
)


def read_fixture(file: UploadedFile) -> ImportResult:
    return import_document(RawDocument.loads(file.content), file.name)


def upload(
    fixture: str, name: str | None = None, *, replace: tuple[str, str] = ("", "")
) -> UploadedFile:
    text = (FIXTURES / f"{fixture}.json").read_text(encoding="utf-8")
    old, new = replace
    if old:
        assert old in text, f"w fixture'ze nie ma {old!r}"
        text = text.replace(old, new)
    return UploadedFile(name=name or f"{fixture}.pdf", content=text.encode())


@pytest.fixture
def repository() -> InMemoryRepository:
    repo = InMemoryRepository()
    repo.add_metering_point(HOME)
    return repo


@pytest.fixture
def archive(tmp_path: Path) -> FileArchive:
    return FileArchive(tmp_path / "archive")


def test_imports_invoice_of_known_metering_point(
    repository: InMemoryRepository, archive: FileArchive
) -> None:
    summary = import_files(repository, archive, [upload(MONTHLY)], read=read_fixture)

    assert [f.file_name for f in summary.imported] == [f"{MONTHLY}.pdf"]
    assert [f.invoice_number for f in summary.imported] == ["T/K1/BN000001/0004/26"]
    assert [i.number for i in repository.list_invoices(HOME.ppe_number)] == [
        "T/K1/BN000001/0004/26"
    ]


def test_rejects_invoice_whose_totals_do_not_add_up_with_reason(
    repository: InMemoryRepository, archive: FileArchive
) -> None:
    broken = upload(MONTHLY, "zepsuta.pdf", replace=("Razem (3-4) 0,00", "Razem (3-4) 5,00"))

    summary = import_files(repository, archive, [broken, upload(MONTHLY)], read=read_fixture)

    assert [r.file_name for r in summary.rejected] == ["zepsuta.pdf"]
    assert "Do zapłaty" in summary.rejected[0].reason
    assert [f.file_name for f in summary.imported] == [f"{MONTHLY}.pdf"]
    assert len(repository.list_invoices(HOME.ppe_number)) == 1


def test_same_file_under_another_name_is_a_duplicate(
    repository: InMemoryRepository, archive: FileArchive
) -> None:
    original = upload(MONTHLY, "faktura.pdf")
    copy = UploadedFile(name="faktura (1).pdf", content=original.content)

    summary = import_files(repository, archive, [original, copy], read=read_fixture)

    assert [f.file_name for f in summary.imported] == ["faktura.pdf"]
    assert [d.file_name for d in summary.duplicates] == ["faktura (1).pdf"]
    assert "faktura.pdf" in summary.duplicates[0].reason
    assert len(repository.list_invoices(HOME.ppe_number)) == 1


def test_another_file_with_the_same_invoice_number_is_a_duplicate(
    repository: InMemoryRepository, archive: FileArchive
) -> None:
    import_files(repository, archive, [upload(MONTHLY)], read=read_fixture)
    regenerated = UploadedFile(name="pobrana-ponownie.pdf", content=upload(MONTHLY).content + b"\n")

    summary = import_files(repository, archive, [regenerated], read=read_fixture)

    assert summary.imported == []
    assert [d.file_name for d in summary.duplicates] == ["pobrana-ponownie.pdf"]
    assert "T/K1/BN000001/0004/26" in summary.duplicates[0].reason


def test_importing_the_same_batch_again_changes_nothing(
    repository: InMemoryRepository, archive: FileArchive
) -> None:
    batch = [upload(MONTHLY)]
    import_files(repository, archive, batch, read=read_fixture)
    before = repository.list_invoices(HOME.ppe_number)
    archived = sorted(archive.directory.iterdir())

    summary = import_files(repository, archive, batch, read=read_fixture)

    assert summary.imported == []
    assert [d.file_name for d in summary.duplicates] == [f"{MONTHLY}.pdf"]
    assert repository.list_invoices(HOME.ppe_number) == before
    assert sorted(archive.directory.iterdir()) == archived


def test_every_imported_file_lands_in_the_archive(
    repository: InMemoryRepository, archive: FileArchive
) -> None:
    file = upload(MONTHLY, "październik.pdf")

    summary = import_files(repository, archive, [file], read=read_fixture)

    stored = archive.path(summary.imported[0].archive_name)
    assert stored.read_bytes() == file.content
    assert stored.name.endswith("październik.pdf")


FLAT_PPE = "590000000000000002"
NEXT_HALF_YEAR = ("E/TM3/BN000002/0002/26", "E/TM3/BN000002/0003/26")


def test_invoices_of_unknown_metering_point_wait_for_it_to_be_added(
    repository: InMemoryRepository, archive: FileArchive
) -> None:
    first = upload(HALF_YEAR, "mieszkanie-1.pdf")
    second = upload(HALF_YEAR, "mieszkanie-2.pdf", replace=NEXT_HALF_YEAR)

    summary = import_files(repository, archive, [first, upload(MONTHLY), second], read=read_fixture)

    assert [f.file_name for f in summary.imported] == [f"{MONTHLY}.pdf"]
    [new_point] = summary.new_metering_points
    assert new_point.ppe_number == FLAT_PPE
    assert new_point.address == "UL. PRZYKŁADOWA 2/3, 00-002 TESTOWO"
    assert new_point.file_names == ("mieszkanie-1.pdf", "mieszkanie-2.pdf")
    assert repository.list_invoices(FLAT_PPE) == []
    assert [p.ppe_number for p in repository.list_metering_points()] == [HOME.ppe_number]


def test_adding_the_new_metering_point_continues_its_import(
    repository: InMemoryRepository, archive: FileArchive
) -> None:
    first = upload(HALF_YEAR, "mieszkanie-1.pdf")
    second = upload(HALF_YEAR, "mieszkanie-2.pdf", replace=NEXT_HALF_YEAR)
    [new_point] = import_files(
        repository, archive, [first, second], read=read_fixture
    ).new_metering_points

    point, summary = add_new_metering_point(
        repository, archive, new_point, name="Mieszkanie", icon=SiteIcon.FLAT, charges_car=False
    )

    assert point.ppe_number == FLAT_PPE
    assert point.slug == "mieszkanie"
    assert repository.list_metering_points()[-1] == point
    assert [f.file_name for f in summary.imported] == ["mieszkanie-1.pdf", "mieszkanie-2.pdf"]
    assert [i.number for i in repository.list_invoices(FLAT_PPE)] == [
        "E/TM3/BN000002/0002/26",
        "E/TM3/BN000002/0003/26",
    ]
    for imported in summary.imported:
        assert archive.path(imported.archive_name).exists()


def test_duplicate_of_a_waiting_invoice_is_skipped_in_the_same_batch(
    repository: InMemoryRepository, archive: FileArchive
) -> None:
    file = upload(HALF_YEAR, "mieszkanie.pdf")
    copy = UploadedFile(name="mieszkanie (1).pdf", content=file.content)

    summary = import_files(repository, archive, [file, copy], read=read_fixture)

    assert summary.new_metering_points[0].file_names == ("mieszkanie.pdf",)
    assert [d.file_name for d in summary.duplicates] == ["mieszkanie (1).pdf"]


def test_summary_after_adding_a_metering_point_counts_its_invoices_as_imported(
    repository: InMemoryRepository, archive: FileArchive
) -> None:
    summary = import_files(
        repository,
        archive,
        [upload(MONTHLY), upload(HALF_YEAR, "mieszkanie.pdf")],
        read=read_fixture,
    )
    [new_point] = summary.new_metering_points
    _, continuation = add_new_metering_point(
        repository, archive, new_point, name="Mieszkanie", icon=SiteIcon.FLAT, charges_car=False
    )

    after = summary.after_adding(new_point, continuation)

    assert [f.file_name for f in after.imported] == [f"{MONTHLY}.pdf", "mieszkanie.pdf"]
    assert after.new_metering_points == []


def test_copy_of_a_rejected_file_in_the_same_batch_is_a_duplicate(
    repository: InMemoryRepository, archive: FileArchive
) -> None:
    broken = upload(MONTHLY, "zepsuta.pdf", replace=("Razem (3-4) 0,00", "Razem (3-4) 5,00"))
    copy = UploadedFile(name="zepsuta (1).pdf", content=broken.content)

    summary = import_files(repository, archive, [broken, copy], read=read_fixture)

    assert [r.file_name for r in summary.rejected] == ["zepsuta.pdf"]
    assert [d.file_name for d in summary.duplicates] == ["zepsuta (1).pdf"]


NOTE = "debit_note_correction"
NOTE_FOR_HOME = ("590000000000000002", HOME.ppe_number)


def test_imports_debit_note_of_known_metering_point(
    repository: InMemoryRepository, archive: FileArchive
) -> None:
    summary = import_files(
        repository, archive, [upload(NOTE, replace=NOTE_FOR_HOME)], read=read_fixture
    )

    assert [f.invoice_number for f in summary.imported] == ["TM3NBN000002/001"]
    assert [n.number for n in repository.list_debit_notes(HOME.ppe_number)] == ["TM3NBN000002/001"]
    assert archive.path(summary.imported[0].archive_name).exists()


def test_debit_note_with_the_same_number_is_a_duplicate(
    repository: InMemoryRepository, archive: FileArchive
) -> None:
    import_files(repository, archive, [upload(NOTE, replace=NOTE_FOR_HOME)], read=read_fixture)
    # Inny plik (inny hash) z tą samą Notą.
    copy = upload(NOTE, "kopia.pdf", replace=NOTE_FOR_HOME)
    copy = UploadedFile(copy.name, copy.content + b" ")

    summary = import_files(repository, archive, [copy], read=read_fixture)

    assert [d.reason for d in summary.duplicates] == [
        "Nota obciążeniowa TM3NBN000002/001 jest już w aplikacji."
    ]


def test_debit_note_of_new_metering_point_waits_with_its_invoices_even_if_uploaded_first(
    repository: InMemoryRepository, archive: FileArchive
) -> None:
    files = [upload(NOTE), upload(HALF_YEAR)]
    summary = import_files(repository, archive, files, read=read_fixture)

    (new_point,) = summary.new_metering_points
    assert new_point.file_names == (f"{HALF_YEAR}.pdf", f"{NOTE}.pdf")
    assert new_point.first_invoice.number == "E/TM3/BN000002/0002/26"

    _, continuation = add_new_metering_point(
        repository, archive, new_point, name="Mieszkanie", icon=SiteIcon.FLAT, charges_car=False
    )

    assert [f.invoice_number for f in continuation.imported] == [
        "E/TM3/BN000002/0002/26",
        "TM3NBN000002/001",
    ]
    assert [n.number for n in repository.list_debit_notes("590000000000000002")] == [
        "TM3NBN000002/001"
    ]


def test_debit_note_of_unknown_metering_point_without_its_invoice_is_rejected(
    repository: InMemoryRepository, archive: FileArchive
) -> None:
    summary = import_files(repository, archive, [upload(NOTE)], read=read_fixture)

    assert summary.new_metering_points == []
    assert [r.reason for r in summary.rejected] == [
        "Nota obciążeniowa TM3NBN000002/001 dotyczy punktu poboru, którego nie ma "
        "w aplikacji. Wgraj ją razem z Fakturą tego punktu poboru albo po jego dodaniu."
    ]


def hourly_report_file(name: str, ppe: str, *hours: tuple[int, float]) -> UploadedFile:
    """Raport wartości godzinowych jako JSON wierszy arkusza (zamiast xlsx); liczby wymyślone."""
    header = ["PPE", "Godz.", '"Godz dodat"'] + [
        f"Ilość energii - {code} kWh" for code in ("ECP", "ECO", "ECBP", "ECBO")
    ]
    rows = [[ppe, 45931 + hour / 24, "0", kwh, 0, kwh, 0] for hour, kwh in hours]
    return UploadedFile(name=name, content=json.dumps([header, *rows]).encode())


def read_sheet_or_fixture(file: UploadedFile) -> ImportResult:
    data = json.loads(file.content)
    return import_sheet(data, file.name) if isinstance(data, list) else read_fixture(file)


def test_hourly_report_of_known_metering_point_is_saved_and_archived(
    repository: InMemoryRepository, archive: FileArchive
) -> None:
    file = hourly_report_file("godzinowe.xlsx", HOME.ppe_number, (1, 0.25), (2, 0.5))

    summary = import_files(repository, archive, [file], read=read_sheet_or_fixture)

    (imported,) = summary.imported
    assert imported.kind is DocumentKind.HOURLY_VALUES_REPORT
    assert imported.invoice_number == "01.10.2025–01.10.2025"
    assert imported.new_hours == 2
    assert [r.imported_kwh for r in repository.list_hourly_readings(HOME.ppe_number)] == [
        Decimal("0.25"),
        Decimal("0.5"),
    ]
    assert archive.path(imported.archive_name).read_bytes() == file.content


def test_overlapping_hourly_report_adds_only_new_hours(
    repository: InMemoryRepository, archive: FileArchive
) -> None:
    first = hourly_report_file("wrzesień.xlsx", HOME.ppe_number, (1, 0.25), (2, 0.5))
    import_files(repository, archive, [first], read=read_sheet_or_fixture)
    second = hourly_report_file("październik.xlsx", HOME.ppe_number, (2, 0.5), (3, 0.75))

    summary = import_files(repository, archive, [second], read=read_sheet_or_fixture)

    assert [f.new_hours for f in summary.imported] == [1]
    assert len(repository.list_hourly_readings(HOME.ppe_number)) == 3


def test_hourly_report_of_unknown_metering_point_is_rejected(
    repository: InMemoryRepository, archive: FileArchive
) -> None:
    file = hourly_report_file("godzinowe.xlsx", FLAT_PPE, (1, 0.25))

    summary = import_files(repository, archive, [file], read=read_sheet_or_fixture)

    assert summary.imported == []
    (rejected,) = summary.rejected
    assert "punktu poboru, którego nie ma w aplikacji" in rejected.reason
    assert repository.list_hourly_readings(FLAT_PPE) == []
