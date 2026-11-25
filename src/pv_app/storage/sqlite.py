import sqlite3
from collections.abc import Iterable
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from pv_app.domain.debit_note import DebitNote
from pv_app.domain.hourly_profile import HourlyReading
from pv_app.domain.invoice import Invoice
from pv_app.domain.metering_point import MeteringPoint, SiteIcon
from pv_app.storage.codec import from_json, to_json
from pv_app.storage.repository import SourceFile

_MIGRATIONS = (
    """
    CREATE TABLE IF NOT EXISTS metering_point (
        ppe_number TEXT PRIMARY KEY,
        name       TEXT NOT NULL,
        slug       TEXT NOT NULL UNIQUE
    );
    """,
    """
    ALTER TABLE metering_point ADD COLUMN icon TEXT NOT NULL DEFAULT 'inne';
    ALTER TABLE metering_point ADD COLUMN charges_car INTEGER NOT NULL DEFAULT 0;
    ALTER TABLE metering_point ADD COLUMN address TEXT NOT NULL DEFAULT '';
    ALTER TABLE metering_point ADD COLUMN net_metering INTEGER NOT NULL DEFAULT 0;
    CREATE TABLE invoice (
        number       TEXT PRIMARY KEY,
        ppe_number   TEXT NOT NULL,
        period_start TEXT NOT NULL,
        period_end   TEXT NOT NULL,
        payload      TEXT NOT NULL
    );
    CREATE INDEX invoice_by_ppe ON invoice (ppe_number, period_start);
    """,
    """
    CREATE TABLE source_file (
        sha256         TEXT PRIMARY KEY,
        file_name      TEXT NOT NULL,
        archive_name   TEXT NOT NULL,
        invoice_number TEXT NOT NULL
    );
    """,
    """
    CREATE TABLE debit_note (
        number     TEXT PRIMARY KEY,
        ppe_number TEXT NOT NULL,
        issue_date TEXT NOT NULL,
        payload    TEXT NOT NULL
    );
    CREATE INDEX debit_note_by_ppe ON debit_note (ppe_number, issue_date);
    """,
    """
    CREATE TABLE hourly_reading (
        ppe_number              TEXT NOT NULL,
        hour_end                TEXT NOT NULL,
        extra_hour              INTEGER NOT NULL,
        imported_kwh            TEXT NOT NULL,
        exported_kwh            TEXT NOT NULL,
        unbalanced_imported_kwh TEXT NOT NULL,
        unbalanced_exported_kwh TEXT NOT NULL,
        PRIMARY KEY (ppe_number, hour_end, extra_hour)
    ) WITHOUT ROWID;
    """,
)
"""Kolejne wersje schematu; ``PRAGMA user_version`` mówi, ile już wykonano."""


class SqliteRepository:
    """Repository w pliku SQLite, używane przez aplikację.

    Faktura jest zapisana w całości jako JSON (``payload``); kolumny obok służą zapytaniom.
    """

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(path)
        self._migrate()

    def _migrate(self) -> None:
        (version,) = self._connection.execute("PRAGMA user_version").fetchone()
        for number, script in enumerate(_MIGRATIONS[version:], version + 1):
            with self._connection:
                self._connection.executescript(script)
                self._connection.execute(f"PRAGMA user_version = {number}")

    def close(self) -> None:
        self._connection.close()

    def add_metering_point(self, metering_point: MeteringPoint) -> None:
        with self._connection:
            self._connection.execute(
                "INSERT INTO metering_point"
                " (ppe_number, name, slug, icon, charges_car, address, net_metering)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    metering_point.ppe_number,
                    metering_point.name,
                    metering_point.slug,
                    metering_point.icon.value,
                    metering_point.charges_car,
                    metering_point.address,
                    metering_point.net_metering,
                ),
            )

    def list_metering_points(self) -> list[MeteringPoint]:
        rows = self._connection.execute(
            "SELECT ppe_number, name, slug, icon, charges_car, address, net_metering"
            " FROM metering_point ORDER BY rowid"
        ).fetchall()
        return [
            MeteringPoint(
                ppe_number=r[0],
                name=r[1],
                slug=r[2],
                icon=SiteIcon(r[3]),
                charges_car=bool(r[4]),
                address=r[5],
                net_metering=bool(r[6]),
            )
            for r in rows
        ]

    def add_invoice(self, invoice: Invoice) -> None:
        period = invoice.header.billing_period
        with self._connection:
            self._connection.execute(
                "INSERT INTO invoice (number, ppe_number, period_start, period_end, payload)"
                " VALUES (?, ?, ?, ?, ?)",
                (
                    invoice.number,
                    invoice.header.ppe_number,
                    period.start.isoformat(),
                    period.end.isoformat(),
                    to_json(invoice),
                ),
            )

    def has_invoice(self, number: str) -> bool:
        row = self._connection.execute(
            "SELECT 1 FROM invoice WHERE number = ?", (number,)
        ).fetchone()
        return row is not None

    def list_invoices(self, ppe_number: str) -> list[Invoice]:
        rows = self._connection.execute(
            "SELECT payload FROM invoice WHERE ppe_number = ? ORDER BY period_start, number",
            (ppe_number,),
        ).fetchall()
        return [from_json(Invoice, r[0]) for r in rows]

    def add_debit_note(self, note: DebitNote) -> None:
        with self._connection:
            self._connection.execute(
                "INSERT INTO debit_note (number, ppe_number, issue_date, payload)"
                " VALUES (?, ?, ?, ?)",
                (note.number, note.ppe_number, note.issue_date.isoformat(), to_json(note)),
            )

    def has_debit_note(self, number: str) -> bool:
        row = self._connection.execute(
            "SELECT 1 FROM debit_note WHERE number = ?", (number,)
        ).fetchone()
        return row is not None

    def list_debit_notes(self, ppe_number: str) -> list[DebitNote]:
        rows = self._connection.execute(
            "SELECT payload FROM debit_note WHERE ppe_number = ? ORDER BY issue_date, number",
            (ppe_number,),
        ).fetchall()
        return [from_json(DebitNote, r[0]) for r in rows]

    def add_source_file(self, source_file: SourceFile) -> None:
        with self._connection:
            self._connection.execute(
                "INSERT INTO source_file (sha256, file_name, archive_name, invoice_number)"
                " VALUES (?, ?, ?, ?)",
                (
                    source_file.sha256,
                    source_file.file_name,
                    source_file.archive_name,
                    source_file.invoice_number,
                ),
            )

    def find_source_file(self, sha256: str) -> SourceFile | None:
        row = self._connection.execute(
            "SELECT sha256, file_name, archive_name, invoice_number FROM source_file"
            " WHERE sha256 = ?",
            (sha256,),
        ).fetchone()
        return SourceFile(*row) if row else None

    def find_source_file_for(self, document_number: str) -> SourceFile | None:
        row = self._connection.execute(
            "SELECT sha256, file_name, archive_name, invoice_number FROM source_file"
            " WHERE invoice_number = ? ORDER BY rowid LIMIT 1",
            (document_number,),
        ).fetchone()
        return SourceFile(*row) if row else None

    def add_hourly_readings(self, readings: Iterable[HourlyReading]) -> int:
        with self._connection:
            before = self._count_hourly_readings()
            self._connection.executemany(
                "INSERT INTO hourly_reading (ppe_number, hour_end, extra_hour, imported_kwh,"
                " exported_kwh, unbalanced_imported_kwh, unbalanced_exported_kwh)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)"
                " ON CONFLICT (ppe_number, hour_end, extra_hour) DO UPDATE SET"
                " imported_kwh = excluded.imported_kwh, exported_kwh = excluded.exported_kwh,"
                " unbalanced_imported_kwh = excluded.unbalanced_imported_kwh,"
                " unbalanced_exported_kwh = excluded.unbalanced_exported_kwh",
                (
                    (
                        r.ppe_number,
                        r.hour_end.isoformat(),
                        r.extra_hour,
                        str(r.imported_kwh),
                        str(r.exported_kwh),
                        str(r.unbalanced_imported_kwh),
                        str(r.unbalanced_exported_kwh),
                    )
                    for r in readings
                ),
            )
            return self._count_hourly_readings() - before

    def _count_hourly_readings(self) -> int:
        (count,) = self._connection.execute("SELECT COUNT(*) FROM hourly_reading").fetchone()
        return int(count)

    def list_hourly_readings(self, ppe_number: str) -> list[HourlyReading]:
        rows = self._connection.execute(
            "SELECT ppe_number, hour_end, extra_hour, imported_kwh, exported_kwh,"
            " unbalanced_imported_kwh, unbalanced_exported_kwh FROM hourly_reading"
            " WHERE ppe_number = ? ORDER BY hour_end, extra_hour",
            (ppe_number,),
        ).fetchall()
        return [
            HourlyReading(
                ppe_number=r[0],
                hour_end=datetime.fromisoformat(r[1]),
                extra_hour=bool(r[2]),
                imported_kwh=Decimal(r[3]),
                exported_kwh=Decimal(r[4]),
                unbalanced_imported_kwh=Decimal(r[5]),
                unbalanced_exported_kwh=Decimal(r[6]),
            )
            for r in rows
        ]
