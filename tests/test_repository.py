"""Kontrakt Repository: każdy adapter zachowuje się tak samo."""

import sqlite3
from collections.abc import Iterator
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from pv_app.domain.invoice import DateRange, Invoice
from pv_app.domain.metering_point import MeteringPoint, SiteIcon
from pv_app.ingest import import_document
from pv_app.ingest.raw import RawDocument
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
