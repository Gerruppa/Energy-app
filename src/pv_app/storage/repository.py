from dataclasses import dataclass
from typing import Protocol

from pv_app.domain.debit_note import DebitNote
from pv_app.domain.invoice import Invoice
from pv_app.domain.metering_point import MeteringPoint


@dataclass(frozen=True)
class SourceFile:
    """Wgrany plik, z którego pochodzi Faktura albo Nota obciążeniowa; rozpoznawany po hashu."""

    sha256: str
    file_name: str
    """Nazwa pliku przy wgraniu."""
    archive_name: str
    """Nazwa kopii w archiwum (``FileArchive``)."""
    invoice_number: str
    """Numer Faktury albo Noty obciążeniowej z tego pliku."""


class Repository(Protocol):
    """Zapis obiektów domeny i zapytania potrzebne funkcjom dashboardu."""

    def add_metering_point(self, metering_point: MeteringPoint) -> None: ...

    def list_metering_points(self) -> list[MeteringPoint]: ...

    def add_invoice(self, invoice: Invoice) -> None: ...

    def has_invoice(self, number: str) -> bool: ...

    def list_invoices(self, ppe_number: str) -> list[Invoice]:
        """Faktury PPE (także korygujące i zastąpione) od najstarszego Okresu rozliczeniowego."""
        ...

    def add_debit_note(self, note: DebitNote) -> None: ...

    def has_debit_note(self, number: str) -> bool: ...

    def list_debit_notes(self, ppe_number: str) -> list[DebitNote]:
        """Noty obciążeniowe PPE od najstarszej daty wystawienia."""
        ...

    def add_source_file(self, source_file: SourceFile) -> None: ...

    def find_source_file(self, sha256: str) -> SourceFile | None: ...
