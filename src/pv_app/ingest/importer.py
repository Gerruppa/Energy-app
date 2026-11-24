from pathlib import Path
from typing import BinaryIO

from pv_app.domain.invoice_checks import check_totals
from pv_app.ingest.new_layout import ParseError, is_new_layout, parse_new_layout
from pv_app.ingest.pdf_adapter import read_pdf
from pv_app.ingest.raw import RawDocument
from pv_app.ingest.result import ImportResult


def import_file(file: Path | BinaryIO, file_name: str | None = None) -> ImportResult:
    """Odczytuje plik PDF Faktury Tauron; nic nie zapisuje."""
    name = file_name or (file.name if isinstance(file, Path) else "plik")
    try:
        document = read_pdf(file)
    except Exception:
        return ImportResult(file_name=name, rejection="Plik nie jest czytelnym PDF-em.")
    return import_document(document, name)


def import_document(document: RawDocument, file_name: str = "") -> ImportResult:
    """Rozpoznaje rodzaj dokumentu i odczytuje go z surowych wierszy."""
    if not is_new_layout(document):
        return ImportResult(
            file_name=file_name,
            rejection="Nieobsługiwany rodzaj dokumentu: aplikacja czyta na razie "
            "Faktury rozliczeniowe Tauron w nowym układzie (od grudnia 2025).",
        )
    try:
        invoice, warnings = parse_new_layout(document)
    except ParseError as error:
        return ImportResult(file_name=file_name, rejection=str(error))
    problems = check_totals(invoice)
    if problems:
        return ImportResult(
            file_name=file_name,
            rejection=f"Faktura {invoice.number} odrzucona: " + " ".join(problems),
            warnings=tuple(warnings),
        )
    return ImportResult(file_name=file_name, invoice=invoice, warnings=tuple(warnings))
