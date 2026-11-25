from collections.abc import Iterable
from datetime import datetime

from pv_app.domain.debit_note import DebitNote
from pv_app.domain.hourly_profile import HourlyReading
from pv_app.domain.invoice import Invoice
from pv_app.domain.metering_point import MeteringPoint
from pv_app.storage.repository import SourceFile


class InMemoryRepository:
    """Repository w pamięci, do testów funkcji."""

    def __init__(self) -> None:
        self._metering_points: list[MeteringPoint] = []
        self._invoices: list[Invoice] = []
        self._debit_notes: list[DebitNote] = []
        self._source_files: dict[str, SourceFile] = {}
        self._hourly_readings: dict[tuple[str, datetime, bool], HourlyReading] = {}

    def add_metering_point(self, metering_point: MeteringPoint) -> None:
        self._metering_points.append(metering_point)

    def list_metering_points(self) -> list[MeteringPoint]:
        return list(self._metering_points)

    def add_invoice(self, invoice: Invoice) -> None:
        self._invoices.append(invoice)

    def has_invoice(self, number: str) -> bool:
        return any(i.number == number for i in self._invoices)

    def list_invoices(self, ppe_number: str) -> list[Invoice]:
        return sorted(
            (i for i in self._invoices if i.header.ppe_number == ppe_number),
            key=lambda i: (i.header.billing_period.start, i.number),
        )

    def add_debit_note(self, note: DebitNote) -> None:
        self._debit_notes.append(note)

    def has_debit_note(self, number: str) -> bool:
        return any(n.number == number for n in self._debit_notes)

    def list_debit_notes(self, ppe_number: str) -> list[DebitNote]:
        return sorted(
            (n for n in self._debit_notes if n.ppe_number == ppe_number),
            key=lambda n: (n.issue_date, n.number),
        )

    def add_source_file(self, source_file: SourceFile) -> None:
        self._source_files[source_file.sha256] = source_file

    def find_source_file(self, sha256: str) -> SourceFile | None:
        return self._source_files.get(sha256)

    def find_source_file_for(self, document_number: str) -> SourceFile | None:
        return next(
            (f for f in self._source_files.values() if f.invoice_number == document_number),
            None,
        )

    def add_hourly_readings(self, readings: Iterable[HourlyReading]) -> int:
        before = len(self._hourly_readings)
        for reading in readings:
            self._hourly_readings[reading.key] = reading
        return len(self._hourly_readings) - before

    def list_hourly_readings(self, ppe_number: str) -> list[HourlyReading]:
        return sorted(
            (r for r in self._hourly_readings.values() if r.ppe_number == ppe_number),
            key=lambda r: (r.hour_end, r.extra_hour),
        )
