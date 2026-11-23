import sqlite3
from pathlib import Path

from pv_app.domain.metering_point import MeteringPoint

_SCHEMA = """
CREATE TABLE IF NOT EXISTS metering_point (
    ppe_number TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    slug       TEXT NOT NULL UNIQUE
);
"""


class SqliteRepository:
    """Repository w pliku SQLite, używane przez aplikację."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(path)
        self._connection.executescript(_SCHEMA)

    def close(self) -> None:
        self._connection.close()

    def add_metering_point(self, metering_point: MeteringPoint) -> None:
        with self._connection:
            self._connection.execute(
                "INSERT INTO metering_point (ppe_number, name, slug) VALUES (?, ?, ?)",
                (metering_point.ppe_number, metering_point.name, metering_point.slug),
            )

    def list_metering_points(self) -> list[MeteringPoint]:
        rows = self._connection.execute(
            "SELECT ppe_number, name, slug FROM metering_point ORDER BY rowid"
        ).fetchall()
        return [MeteringPoint(ppe_number=r[0], name=r[1], slug=r[2]) for r in rows]
