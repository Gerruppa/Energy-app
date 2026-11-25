"""Raport wartości godzinowych z Tauron Dystrybucji (xlsx) → Profil godzinowy.

Wiersze arkusza w testach są wymyślone; numer PPE fikcyjny. Czas w komórce to liczba
seryjna Excela (dni od 30.12.1899), tak jak w pliku od Taurona.
"""

import zipfile
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from xml.sax.saxutils import escape

from pv_app.ingest import import_file, import_sheet
from pv_app.ingest.raw import SheetRow

PPE = "590000000000000001"
HEADER = (
    "PPE",
    '"Flaga prosum."',
    "Godz.",
    '"Godz dodat"',
    "Ilość energii pobranej w danej godzinie przed zbilansowaniem - ECP kWh",
    "Ilość energii oddanej w danej godzinie przed zbilansowaniem - ECO kWh",
    "Ilość energii pobranej w danej godzinie po zbilansowaniu - ECBP kWh",
    "Ilość energii oddane w danej godzinie po zbilansowaniu - ECBO kWh",
    "Ilość energii biernej indukcyjnej EBI",
    "Ilość energii biernej pojemnościowej EBP",
)
OCT_1_2025 = 45931.0
"""1.10.2025 0:00 jako liczba seryjna Excela."""


def serial(day_offset: int, hour: int) -> float:
    return OCT_1_2025 + day_offset + hour / 24


def sheet(*rows: SheetRow) -> list[SheetRow]:
    return [("Raport wartości godzinowych dla wskazanego PPE",), (), HEADER, *rows]


def row(
    time: float, before: tuple[float, float], after: tuple[float, float], extra: str = "0"
) -> SheetRow:
    return (PPE, 1, time, extra, *before, *after, None, None)


def test_reads_hourly_readings_of_metering_point() -> None:
    result = import_sheet(
        sheet(
            row(serial(0, 1), (0.25, 0.0), (0.25, 0.0)),
            row(serial(0, 12), (0.1, 2.30000000000001), (0.0, 2.2)),
        ),
        "raport.xlsx",
    )

    report = result.hourly_report
    assert result.rejection is None
    assert report is not None
    assert report.ppe_number == PPE
    first, second = report.readings
    assert first.hour_end == datetime(2025, 10, 1, 1)
    assert first.imported_kwh == Decimal("0.25")
    assert second.unbalanced_exported_kwh == Decimal("2.300")
    assert second.exported_kwh == Decimal("2.2")
    assert second.unbalanced_imported_kwh == Decimal("0.1")
    assert second.imported_kwh == Decimal("0")


def test_repeated_hour_at_change_to_winter_time_is_marked_as_extra_hour() -> None:
    result = import_sheet(
        sheet(
            row(serial(25, 3), (0.5, 0.0), (0.5, 0.0), extra="1"),
            row(serial(25, 3), (0.4, 0.0), (0.4, 0.0)),
            row(serial(25, 2), (0.3, 0.0), (0.3, 0.0)),
        )
    )

    assert result.hourly_report is not None
    readings = result.hourly_report.readings
    assert [(r.hour_end.hour, r.extra_hour, r.imported_kwh) for r in readings] == [
        (2, False, Decimal("0.3")),
        (3, False, Decimal("0.4")),
        (3, True, Decimal("0.5")),
    ]


def test_midnight_closes_previous_day() -> None:
    result = import_sheet(
        sheet(row(serial(0, 1), (0.1, 0.0), (0.1, 0.0)), row(serial(1, 0), (0.2, 0.0), (0.2, 0.0)))
    )

    report = result.hourly_report
    assert report is not None
    assert report.readings[-1].day == datetime(2025, 10, 1).date()
    assert (report.first_day, report.last_day) == (report.readings[0].day,) * 2
    assert report.label == "01.10.2025–01.10.2025"


def test_hours_without_energy_values_are_skipped_with_warning() -> None:
    result = import_sheet(
        sheet(
            row(serial(0, 1), (0.1, 0.0), (0.1, 0.0)),
            (PPE, 1, serial(0, 2), "0", None, None, None, None, None, None),
        )
    )

    assert result.hourly_report is not None
    assert len(result.hourly_report.readings) == 1
    assert result.warnings == ("Pominięto godziny bez wartości energii: 1.",)


def test_report_of_several_metering_points_is_rejected() -> None:
    other = ("590000000000000002", 1, serial(0, 2), "0", 0.1, 0.0, 0.1, 0.0, None, None)

    result = import_sheet(sheet(row(serial(0, 1), (0.1, 0.0), (0.1, 0.0)), other))

    assert result.hourly_report is None
    assert result.rejection is not None
    assert "kilka punktów poboru" in result.rejection


def test_other_spreadsheet_is_rejected() -> None:
    result = import_sheet([("Data", "Zużycie"), (45931.0, 1.5)], "inny.xlsx")

    assert result.hourly_report is None
    assert result.rejection is not None
    assert "Raport wartości godzinowych" in result.rejection


def test_xlsx_file_is_read_as_hourly_report(tmp_path: Path) -> None:
    path = tmp_path / "raport.xlsx"
    write_xlsx(path, sheet(row(serial(0, 1), (0.17, 0.0), (0.17, 0.0))))

    result = import_file(path)

    assert result.rejection is None
    assert result.hourly_report is not None
    reading = result.hourly_report.readings[0]
    assert (reading.ppe_number, reading.hour_end) == (PPE, datetime(2025, 10, 1, 1))
    assert reading.imported_kwh == Decimal("0.17")


def write_xlsx(path: Path, rows: list[SheetRow]) -> None:
    """Najmniejszy skoroszyt jak od Taurona: teksty we wspólnej tabeli, liczby w komórkach."""
    strings: list[str] = []
    xml_rows = []
    for number, values in enumerate(rows, 1):
        cells = []
        for column, value in enumerate(values):
            ref = f"{chr(ord('A') + column)}{number}"
            if value is None:
                cells.append(f'<c r="{ref}"/>')
            elif isinstance(value, str):
                strings.append(value)
                cells.append(f'<c r="{ref}" t="s"><v>{len(strings) - 1}</v></c>')
            else:
                cells.append(f'<c r="{ref}"><v>{value}</v></c>')
        if cells:
            xml_rows.append(f'<row r="{number}">{"".join(cells)}</row>')
    main = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    rel = 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
    with zipfile.ZipFile(path, "w") as workbook:
        workbook.writestr(
            "xl/workbook.xml",
            f'<workbook {main} {rel}><sheets><sheet name="R" sheetId="1" r:id="rId1"/>'
            "</sheets></workbook>",
        )
        workbook.writestr(
            "xl/_rels/workbook.xml.rels",
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Target="worksheets/sheet1.xml" Type="worksheet"/>'
            "</Relationships>",
        )
        shared = "".join(f"<si><t>{escape(s)}</t></si>" for s in strings)
        workbook.writestr("xl/sharedStrings.xml", f"<sst {main}>{shared}</sst>")
        workbook.writestr(
            "xl/worksheets/sheet1.xml",
            f"<worksheet {main}><sheetData>{''.join(xml_rows)}</sheetData></worksheet>",
        )


def test_hour_repeated_without_extra_hour_flag_is_reported_as_warning() -> None:
    result = import_sheet(
        sheet(row(serial(0, 1), (0.1, 0.0), (0.1, 0.0)), row(serial(0, 1), (0.2, 0.0), (0.2, 0.0)))
    )

    assert result.hourly_report is not None
    assert [r.imported_kwh for r in result.hourly_report.readings] == [Decimal("0.2")]
    assert result.warnings == (
        "Godziny powtórzone w raporcie bez oznaczenia „Godz dodat”: 1; "
        "zostawiono wartości z niższego wiersza.",
    )
