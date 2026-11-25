from collections.abc import Callable, Sequence
from pathlib import Path
from typing import BinaryIO

from pv_app.domain.debit_note import check_debit_note
from pv_app.domain.invoice import Invoice
from pv_app.domain.invoice_checks import check_totals
from pv_app.ingest.debit_note import is_debit_note, parse_debit_note
from pv_app.ingest.hourly_report import is_hourly_report, parse_hourly_report
from pv_app.ingest.new_layout import is_new_layout, parse_new_layout
from pv_app.ingest.old_layout import (
    is_correcting_invoice,
    is_old_layout,
    parse_correcting_invoice,
    parse_old_layout,
)
from pv_app.ingest.parse_error import ParseError
from pv_app.ingest.pdf_adapter import read_pdf
from pv_app.ingest.raw import RawDocument, SheetRow
from pv_app.ingest.result import ImportResult
from pv_app.ingest.xlsx_adapter import is_xlsx, read_xlsx


def import_file(file: Path | BinaryIO, file_name: str | None = None) -> ImportResult:
    """Odczytuje plik PDF Faktury Tauron albo Raport wartości godzinowych (xlsx); nic nie
    zapisuje."""
    name = file_name or (file.name if isinstance(file, Path) else "plik")
    if is_xlsx(file):
        try:
            rows = read_xlsx(file)
        except Exception:
            return ImportResult(file_name=name, rejection="Plik nie jest czytelnym arkuszem xlsx.")
        return import_sheet(rows, name)
    try:
        document = read_pdf(file)
    except Exception:
        return ImportResult(file_name=name, rejection="Plik nie jest czytelnym PDF-em.")
    return import_document(document, name)


def import_document(document: RawDocument, file_name: str = "") -> ImportResult:
    """Rozpoznaje rodzaj dokumentu i odczytuje go z surowych wierszy."""
    parse: Callable[[RawDocument], tuple[Invoice, list[str]]]
    if is_new_layout(document):
        parse = parse_new_layout
    elif is_old_layout(document):
        parse = parse_old_layout
    elif is_correcting_invoice(document):
        parse = parse_correcting_invoice
    elif is_debit_note(document):
        return _import_debit_note(document, file_name)
    else:
        return ImportResult(
            file_name=file_name,
            rejection="Nieobsługiwany rodzaj dokumentu: aplikacja czyta Faktury rozliczeniowe "
            "Tauron (stary i nowy układ), Faktury korygujące i Noty obciążeniowe korekty.",
        )
    try:
        invoice, warnings = parse(document)
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


def import_sheet(rows: Sequence[SheetRow], file_name: str = "") -> ImportResult:
    """Odczytuje Raport wartości godzinowych z wierszy arkusza."""
    if not is_hourly_report(rows):
        return ImportResult(
            file_name=file_name,
            rejection="Nieobsługiwany arkusz: aplikacja czyta Raport wartości godzinowych "
            "dla wskazanego PPE od Tauron Dystrybucji.",
        )
    try:
        report, warnings = parse_hourly_report(rows)
    except ParseError as error:
        return ImportResult(file_name=file_name, rejection=str(error))
    return ImportResult(file_name=file_name, hourly_report=report, warnings=tuple(warnings))


def _import_debit_note(document: RawDocument, file_name: str) -> ImportResult:
    try:
        note, warnings = parse_debit_note(document)
    except ParseError as error:
        return ImportResult(file_name=file_name, rejection=str(error))
    problems = check_debit_note(note)
    if problems:
        return ImportResult(
            file_name=file_name,
            rejection=f"Nota obciążeniowa {note.number} odrzucona: " + " ".join(problems),
            warnings=tuple(warnings),
        )
    return ImportResult(file_name=file_name, debit_note=note, warnings=tuple(warnings))
