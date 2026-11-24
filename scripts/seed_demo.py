"""Osobny katalog danych z Fakturami, do oglądania ekranów bez ruszania ``data/``.

    uv run python scripts/seed_demo.py KATALOG             # fixture'y z tests/fixtures
    uv run python scripts/seed_demo.py KATALOG --references # prawdziwe PDF-y z References/

Potem (PowerShell): ``$env:PV_APP_DATA_DIR = "KATALOG"; uv run python -m pv_app``.
Każdy PPE powstaje przez ``add_metering_point_from_invoice`` jak w kreatorze; Faktury,
które nie przeszły importu, są wypisane z przyczyną.
"""

import argparse
from collections.abc import Iterator
from pathlib import Path

from pv_app.app.wizard import add_metering_point_from_invoice
from pv_app.domain.invoice import SettlementType
from pv_app.domain.metering_point import SiteIcon
from pv_app.ingest import ImportResult, import_document, import_file
from pv_app.ingest.raw import RawDocument
from pv_app.storage.sqlite import SqliteRepository

ROOT = Path(__file__).resolve().parent.parent


def _results(references: bool) -> Iterator[ImportResult]:
    if references:
        for path in sorted((ROOT / "References").rglob("*.pdf")):
            yield import_file(path)
    else:
        for path in sorted((ROOT / "tests" / "fixtures").glob("*.json")):
            yield import_document(RawDocument.from_json(path), path.name)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("data_dir", type=Path)
    parser.add_argument("--references", action="store_true", help="prawdziwe PDF-y z References/")
    args = parser.parse_args()

    repository = SqliteRepository(args.data_dir / "pv_app.sqlite3")
    try:
        points = {p.ppe_number for p in repository.list_metering_points()}
        numbers = {i.number for p in points for i in repository.list_invoices(p)}
        for result in _results(args.references):
            invoice = result.invoice
            if invoice is None:
                print(f"pominięto {result.file_name}: {result.rejection}")
                continue
            if invoice.number in numbers:
                continue
            numbers.add(invoice.number)
            if invoice.header.ppe_number in points:
                repository.add_invoice(invoice)
                continue
            net_metering = invoice.header.settlement_type is SettlementType.NET_METERING
            add_metering_point_from_invoice(
                repository,
                invoice,
                name=f"{'Dom' if net_metering else 'Mieszkanie'} {len(points) + 1}",
                icon=SiteIcon.HOUSE if net_metering else SiteIcon.FLAT,
                charges_car=net_metering,
            )
            points.add(invoice.header.ppe_number)
        for point in repository.list_metering_points():
            count = len(repository.list_invoices(point.ppe_number))
            print(f"{point.name} (?ppe={point.slug}): {count} Faktur")
    finally:
        repository.close()


if __name__ == "__main__":
    main()
