"""Kontrakt Repository: każdy adapter zachowuje się tak samo."""

import json
import sqlite3
from collections.abc import Iterator
from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from pv_app.domain.debit_note import DebitNote
from pv_app.domain.hourly_profile import HourlyReading
from pv_app.domain.invoice import DateRange, Invoice
from pv_app.domain.metering_point import MeteringPoint, SiteIcon
from pv_app.ingest import import_document
from pv_app.ingest.raw import RawDocument
from pv_app.storage.codec import to_json
from pv_app.storage.in_memory import InMemoryRepository
from pv_app.storage.repository import Repository, SourceFile
from pv_app.storage.sqlite import SqliteRepository

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(params=["in_memory", "sqlite"])
def repository(request: pytest.FixtureRequest, tmp_path: Path) -> Iterator[Repository]:
    if request.param == "in_memory":
        yield InMemoryRepository()
    else:
        repo = SqliteRepository(tmp_path / "pv.sqlite3")
        yield repo
        repo.close()


HOME = MeteringPoint(
    ppe_number="590000000000000001",
    name="Dom",
    slug="dom",
    icon=SiteIcon.HOUSE,
    charges_car=True,
    address="UL. PRZYKŁADOWA 1, 00-001 TESTOWO",
    net_metering=True,
)


def fixture_invoice(name: str) -> Invoice:
    invoice = import_document(RawDocument.from_json(FIXTURES / f"{name}.json")).invoice
    assert invoice is not None
    return invoice


def test_new_repository_has_no_metering_points(repository: Repository) -> None:
    assert repository.list_metering_points() == []


def test_added_metering_point_can_be_listed(repository: Repository) -> None:
    repository.add_metering_point(HOME)

    assert repository.list_metering_points() == [HOME]


def test_saved_invoice_comes_back_with_everything_read_from_it(repository: Repository) -> None:
    invoice = fixture_invoice("new_layout_net_metering_monthly")
    repository.add_metering_point(HOME)

    repository.add_invoice(invoice)

    assert repository.list_invoices(HOME.ppe_number) == [invoice]


def test_invoices_are_listed_per_metering_point_in_period_order(repository: Repository) -> None:
    october = fixture_invoice("new_layout_net_metering_monthly")
    september = replace(
        october,
        header=replace(
            october.header,
            number="T/K1/BN000001/0003/26",
            billing_period=DateRange(date(2026, 9, 1), date(2026, 9, 30)),
        ),
    )
    other_point = fixture_invoice("new_layout_standard_half_year")
    for invoice in (october, other_point, september):
        repository.add_invoice(invoice)

    assert repository.list_invoices(october.header.ppe_number) == [september, october]
    assert repository.list_invoices(other_point.header.ppe_number) == [other_point]
    assert repository.list_invoices("590000000000000099") == []


def test_database_from_previous_version_gets_new_columns_and_tables(tmp_path: Path) -> None:
    path = tmp_path / "old.sqlite3"
    old = sqlite3.connect(path)
    old.execute(
        "CREATE TABLE metering_point (ppe_number TEXT PRIMARY KEY, name TEXT NOT NULL,"
        " slug TEXT NOT NULL UNIQUE)"
    )
    old.close()

    repo = SqliteRepository(path)
    repo.add_metering_point(HOME)
    repo.add_invoice(fixture_invoice("new_layout_net_metering_monthly"))

    assert repo.list_metering_points() == [HOME]
    repo.close()


def test_knows_whether_an_invoice_number_is_saved(repository: Repository) -> None:
    invoice = fixture_invoice("new_layout_net_metering_monthly")
    repository.add_invoice(invoice)

    assert repository.has_invoice(invoice.number)
    assert not repository.has_invoice("T/K1/BN000001/0099/26")


def test_source_file_is_found_by_its_hash(repository: Repository) -> None:
    source_file = SourceFile(
        sha256="ab" * 32,
        file_name="faktura.pdf",
        archive_name="abababababab-faktura.pdf",
        invoice_number="T/K1/BN000001/0004/26",
    )

    repository.add_source_file(source_file)

    assert repository.find_source_file("ab" * 32) == source_file
    assert repository.find_source_file("cd" * 32) is None


def test_source_file_is_found_by_the_number_of_its_document(repository: Repository) -> None:
    source_file = SourceFile(
        sha256="ab" * 32,
        file_name="faktura.pdf",
        archive_name="abababababab-faktura.pdf",
        invoice_number="T/K1/BN000001/0004/26",
    )

    repository.add_source_file(source_file)

    assert repository.find_source_file_for("T/K1/BN000001/0004/26") == source_file
    assert repository.find_source_file_for("T/K1/BN000001/0099/26") is None


def fixture_debit_note() -> DebitNote:
    note = import_document(RawDocument.from_json(FIXTURES / "debit_note_correction.json"))
    assert note.debit_note is not None
    return note.debit_note


def test_saved_debit_note_comes_back_for_its_metering_point(repository: Repository) -> None:
    note = fixture_debit_note()

    repository.add_debit_note(note)

    assert repository.list_debit_notes(note.ppe_number) == [note]
    assert repository.list_debit_notes("590000000000000099") == []
    assert repository.has_debit_note(note.number)
    assert not repository.has_debit_note("TM3NBN000002/099")


def test_correcting_invoice_comes_back_with_its_correction(repository: Repository) -> None:
    invoice = fixture_invoice("old_layout_correcting_net_metering")

    repository.add_invoice(invoice)

    assert repository.list_invoices(invoice.header.ppe_number) == [invoice]


def test_invoice_saved_before_corrections_existed_is_read_back(tmp_path: Path) -> None:
    invoice = fixture_invoice("new_layout_net_metering_monthly")
    payload = json.loads(to_json(invoice))
    del payload["correction"]
    del payload["summary"]["discount"]
    path = tmp_path / "pv.sqlite3"
    repo = SqliteRepository(path)
    repo.add_invoice(invoice)
    repo.close()
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE invoice SET payload = ?", (json.dumps(payload),))
    connection.close()

    repo = SqliteRepository(path)
    assert repo.list_invoices(invoice.header.ppe_number) == [invoice]
    repo.close()


def hour(
    day: int, hour_end: int, imported: str, *, extra: bool = False, ppe: str = HOME.ppe_number
) -> HourlyReading:
    return HourlyReading(
        ppe_number=ppe,
        hour_end=datetime(2025, 10, day, hour_end),
        extra_hour=extra,
        imported_kwh=Decimal(imported),
        exported_kwh=Decimal("1.25"),
        unbalanced_imported_kwh=Decimal(imported),
        unbalanced_exported_kwh=Decimal("1.5"),
    )


def test_hourly_readings_are_listed_per_metering_point_in_time_order(
    repository: Repository,
) -> None:
    later, extra, earlier = hour(26, 3, "0.4", extra=True), hour(26, 3, "0.3"), hour(1, 1, "0.1")
    other = hour(1, 1, "0.9", ppe="590000000000000002")

    added = repository.add_hourly_readings([later, extra, earlier, other])

    assert added == 4
    assert repository.list_hourly_readings(HOME.ppe_number) == [earlier, extra, later]


def test_newer_report_replaces_values_of_the_same_hour(repository: Repository) -> None:
    repository.add_hourly_readings([hour(1, 1, "0.1"), hour(1, 2, "0.2")])

    added = repository.add_hourly_readings([hour(1, 2, "0.25"), hour(1, 3, "0.3")])

    assert added == 1
    assert [r.imported_kwh for r in repository.list_hourly_readings(HOME.ppe_number)] == [
        Decimal("0.1"),
        Decimal("0.25"),
        Decimal("0.3"),
    ]


def source_file_for(number: str, sha: str) -> SourceFile:
    return SourceFile(sha * 32, f"{sha}.pdf", f"{sha * 6}-{sha}.pdf", number)


def test_deleted_invoice_is_gone_together_with_its_source_file(repository: Repository) -> None:
    october = fixture_invoice("new_layout_net_metering_monthly")
    other = fixture_invoice("new_layout_standard_half_year")
    for invoice, sha in ((october, "ab"), (other, "cd")):
        repository.add_invoice(invoice)
        repository.add_source_file(source_file_for(invoice.number, sha))

    deleted = repository.delete_invoice(october.number)

    assert deleted == source_file_for(october.number, "ab")
    assert not repository.has_invoice(october.number)
    assert repository.find_source_file("ab" * 32) is None
    assert repository.has_invoice(other.number)
    assert repository.find_source_file("cd" * 32) == source_file_for(other.number, "cd")


def test_source_files_are_listed_in_the_order_they_were_added(repository: Repository) -> None:
    files = [
        source_file_for("B/1", "ff"),
        source_file_for("A/1", "00"),
        source_file_for("C/1", "aa"),
    ]
    for source_file in files:
        repository.add_source_file(source_file)

    assert repository.list_source_files() == files


def test_clearing_documents_keeps_metering_points(repository: Repository) -> None:
    invoice = fixture_invoice("new_layout_net_metering_monthly")
    repository.add_metering_point(HOME)
    repository.add_invoice(invoice)
    repository.add_debit_note(fixture_debit_note())
    repository.add_source_file(source_file_for(invoice.number, "ab"))
    repository.add_hourly_readings([hour(1, 1, "0.1")])

    repository.clear_documents()

    assert repository.list_metering_points() == [HOME]
    assert repository.list_invoices(HOME.ppe_number) == []
    assert repository.list_debit_notes(fixture_debit_note().ppe_number) == []
    assert repository.list_source_files() == []
    assert repository.list_hourly_readings(HOME.ppe_number) == []
