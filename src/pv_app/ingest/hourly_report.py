"""Raport wartości godzinowych (xlsx od Tauron Dystrybucji): wiersze arkusza → Profil godzinowy.

Kolumny wybiera nagłówek tabeli po oznaczeniach Taurona (``ECP``, ``ECO``, ``ECBP``,
``ECBO``, ``Godz.``, ``Godz dodat``), nie ich kolejność.
"""

import re
from collections.abc import Sequence
from datetime import datetime, timedelta
from decimal import Decimal

from pv_app.domain.hourly_profile import HourlyReading, HourlyValuesReport
from pv_app.ingest.parse_error import ParseError
from pv_app.ingest.raw import SheetRow

TITLE = "Raport wartości godzinowych"

_ENERGY_COLUMN = re.compile(r"-\s*(ECP|ECO|ECBP|ECBO)\s+kWh", re.IGNORECASE)
_EXCEL_EPOCH = datetime(1899, 12, 30)
_HEADER_SEARCH_ROWS = 20
"""Nagłówek tabeli leży w pierwszych wierszach (w raporcie Taurona w trzecim)."""
_KWH_PLACES = 3
"""Raport podaje kWh z dokładnością do 1 Wh (format ``0.000``)."""


def is_hourly_report(rows: Sequence[SheetRow]) -> bool:
    return _header_index(rows) is not None


def parse_hourly_report(rows: Sequence[SheetRow]) -> tuple[HourlyValuesReport, list[str]]:
    header_index = _header_index(rows)
    if header_index is None:
        raise ParseError(f"To nie jest {TITLE}: brak nagłówka tabeli z kolumnami ECP i ECBP.")
    columns = _columns(rows[header_index])
    readings: list[HourlyReading] = []
    ppe_numbers: set[str] = set()
    skipped = 0
    for row in rows[header_index + 1 :]:
        ppe = _text(_cell(row, columns["PPE"]))
        if not ppe:
            continue
        energy = [_cell(row, columns[name]) for name in ("ECP", "ECO", "ECBP", "ECBO")]
        if any(value is None or value == "" for value in energy):
            skipped += 1
            continue
        ppe_numbers.add(ppe)
        before_in, before_out, after_in, after_out = (_kwh(value) for value in energy)
        readings.append(
            HourlyReading(
                ppe_number=ppe,
                hour_end=_time(_cell(row, columns["Godz."])),
                extra_hour=_text(_cell(row, columns["Godz dodat"])) in ("1", "1.0"),
                imported_kwh=after_in,
                exported_kwh=after_out,
                unbalanced_imported_kwh=before_in,
                unbalanced_exported_kwh=before_out,
            )
        )
    if not readings:
        raise ParseError(f"{TITLE} nie zawiera żadnej godziny z wartościami energii.")
    if len(ppe_numbers) > 1:
        raise ParseError(f"{TITLE} zawiera kilka punktów poboru; wgraj osobny raport dla każdego.")
    by_key = {reading.key: reading for reading in readings}
    repeated = len(readings) - len(by_key)
    unique = sorted(by_key.values(), key=lambda r: (r.hour_end, r.extra_hour))
    warnings = []
    if skipped:
        warnings.append(f"Pominięto godziny bez wartości energii: {skipped}.")
    if repeated:
        warnings.append(
            f"Godziny powtórzone w raporcie bez oznaczenia „Godz dodat”: {repeated}; "
            "zostawiono wartości z niższego wiersza."
        )
    return HourlyValuesReport(ppe_number=ppe_numbers.pop(), readings=tuple(unique)), warnings


def _header_index(rows: Sequence[SheetRow]) -> int | None:
    for index, row in enumerate(rows[:_HEADER_SEARCH_ROWS]):
        found = {m.group(1).upper() for cell in row if (m := _ENERGY_COLUMN.search(_text(cell)))}
        if found == {"ECP", "ECO", "ECBP", "ECBO"}:
            return index
    return None


def _columns(header: SheetRow) -> dict[str, int]:
    columns: dict[str, int] = {}
    for index, cell in enumerate(header):
        text = _text(cell).strip('"').strip()
        if match := _ENERGY_COLUMN.search(text):
            columns[match.group(1).upper()] = index
        elif text in ("PPE", "Godz.", "Godz dodat"):
            columns[text] = index
    missing = {"PPE", "Godz.", "Godz dodat"} - columns.keys()
    if missing:
        raise ParseError(f"{TITLE}: brak kolumn {', '.join(sorted(missing))}.")
    return columns


def _cell(row: SheetRow, index: int) -> object:
    return row[index] if index < len(row) else None


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _number(value: object, what: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ParseError(f"{TITLE}: nieczytelna {what} {value!r}.")
    return float(value)


def _kwh(value: object) -> Decimal:
    return Decimal(f"{_number(value, 'ilość energii'):.{_KWH_PLACES}f}")


def _time(value: object) -> datetime:
    """Czas zapisany przez Excela jako liczba dni od 30.12.1899, do pełnej minuty."""
    return _EXCEL_EPOCH + timedelta(minutes=round(_number(value, "godzina") * 24 * 60))
