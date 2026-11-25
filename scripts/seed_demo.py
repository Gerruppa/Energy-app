"""Osobny katalog danych z Fakturami, do oglądania ekranów bez ruszania ``data/``.

    uv run python scripts/seed_demo.py KATALOG             # fixture'y z tests/fixtures
    uv run python scripts/seed_demo.py KATALOG --references # prawdziwe pliki z References/

Potem (PowerShell): ``$env:PV_APP_DATA_DIR = "KATALOG"; uv run python -m pv_app``.
Pliki przechodzą przez ``import_files`` jak na stronie importu (duplikaty pomijane, kopie
w ``KATALOG/archive``), a każdy nowy PPE powstaje przez ``add_new_metering_point`` jak
w kreatorze. Pliki, które nie przeszły importu, są wypisane z przyczyną.
"""

import argparse
from pathlib import Path

from pv_app.app.batch_import import (
    ImportSummary,
    Reader,
    UploadedFile,
    add_new_metering_point,
    import_files,
    read_file,
)
from pv_app.domain.invoice import SettlementType
from pv_app.domain.metering_point import SiteIcon
from pv_app.ingest import ImportResult, import_document
from pv_app.ingest.raw import RawDocument
from pv_app.storage.archive import FileArchive
from pv_app.storage.sqlite import SqliteRepository

ROOT = Path(__file__).resolve().parent.parent


def read_fixture(file: UploadedFile) -> ImportResult:
    """Zrzut wierszy (JSON z ``tests/fixtures``) zamiast PDF-a."""
    return import_document(RawDocument.loads(file.content), file.name)


def _report(summary: ImportSummary) -> None:
    for skipped in summary.rejected + summary.duplicates:
        print(f"pominięto {skipped.file_name}: {skipped.reason}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("data_dir", type=Path)
    parser.add_argument("--references", action="store_true", help="prawdziwe pliki z References/")
    args = parser.parse_args()

    paths: list[Path]
    read: Reader
    if args.references:
        references = ROOT / "References"
        paths = sorted([*references.rglob("*.pdf"), *references.rglob("*.xlsx")])
        read = read_file
    else:
        paths, read = sorted((ROOT / "tests" / "fixtures").glob("*.json")), read_fixture
    files = [UploadedFile(p.name, p.read_bytes()) for p in paths]

    repository = SqliteRepository(args.data_dir / "pv_app.sqlite3")
    archive = FileArchive(args.data_dir / "archive")
    try:
        summary = import_files(repository, archive, files, read=read)
        _report(summary)
        for new_point in summary.new_metering_points:
            net_metering = new_point.first_invoice.header.settlement_type is (
                SettlementType.NET_METERING
            )
            count = len(repository.list_metering_points()) + 1
            added = add_new_metering_point(
                repository,
                archive,
                new_point,
                name=f"{'Dom' if net_metering else 'Mieszkanie'} {count}",
                icon=SiteIcon.HOUSE if net_metering else SiteIcon.FLAT,
                charges_car=net_metering,
            )
            _report(added.summary)
        # Raport wartości godzinowych nieznanego PPE jest odrzucany; PPE dodaje dopiero kreator.
        rejected = {skipped.file_name for skipped in summary.rejected}
        retry = [f for f in files if f.name in rejected and f.name.endswith(".xlsx")]
        _report(import_files(repository, archive, retry, read=read))
        for point in repository.list_metering_points():
            invoices = len(repository.list_invoices(point.ppe_number))
            notes = len(repository.list_debit_notes(point.ppe_number))
            hours = len(repository.list_hourly_readings(point.ppe_number))
            print(
                f"{point.name} (?ppe={point.slug}): {invoices} Faktur, "
                f"{notes} Not obciążeniowych, {hours} godzin Profilu godzinowego"
            )
    finally:
        repository.close()


if __name__ == "__main__":
    main()
