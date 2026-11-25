"""Cienki adapter: arkusz xlsx → surowe wiersze komórek (ADR 0005).

Czyta pierwszy arkusz skoroszytu bibliotekami standardowymi (xlsx to zip z plikami XML),
strumieniowo, bo Raport wartości godzinowych za kilka lat ma kilkadziesiąt tysięcy wierszy.
Daty zostają liczbami seryjnymi Excela; zamienia je parser, który wie, która kolumna to czas.
"""

import posixpath
import re
import zipfile
from collections.abc import Iterator
from pathlib import Path
from typing import IO, BinaryIO
from xml.etree import ElementTree

from pv_app.ingest.raw import SheetCell, SheetRow

_MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_PACKAGE_REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"
_ZIP_MAGIC = b"PK\x03\x04"
_COLUMN = re.compile(r"[A-Z]+")


def is_xlsx(file: Path | BinaryIO) -> bool:
    """Plik zaczyna się jak archiwum zip (xlsx); PDF zaczyna się od ``%PDF``."""
    if isinstance(file, Path):
        with file.open("rb") as stream:
            return stream.read(4) == _ZIP_MAGIC
    position = file.tell()
    head = file.read(4)
    file.seek(position)
    return head == _ZIP_MAGIC


def read_xlsx(file: Path | BinaryIO) -> list[SheetRow]:
    with zipfile.ZipFile(file) as workbook:
        strings = _shared_strings(workbook)
        with workbook.open(_first_sheet(workbook)) as sheet:
            return list(_rows(sheet, strings))


def _first_sheet(workbook: zipfile.ZipFile) -> str:
    root = ElementTree.fromstring(workbook.read("xl/workbook.xml"))
    first = root.find(f"{_MAIN}sheets/{_MAIN}sheet")
    if first is None:
        raise ValueError("skoroszyt bez arkuszy")
    relation_id = first.get(f"{_REL}id")
    relations = ElementTree.fromstring(workbook.read("xl/_rels/workbook.xml.rels"))
    for relation in relations.iter(f"{_PACKAGE_REL}Relationship"):
        if relation.get("Id") == relation_id:
            target = relation.get("Target", "")
            return target.lstrip("/") if target.startswith("/") else posixpath.join("xl", target)
    raise ValueError("brak pliku pierwszego arkusza")


def _shared_strings(workbook: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in workbook.namelist():
        return []
    root = ElementTree.fromstring(workbook.read("xl/sharedStrings.xml"))
    return ["".join(t.text or "" for t in item.iter(f"{_MAIN}t")) for item in root]


def _rows(sheet: IO[bytes], strings: list[str]) -> Iterator[SheetRow]:
    for _, element in ElementTree.iterparse(sheet):
        if element.tag != f"{_MAIN}row":
            continue
        cells: dict[int, SheetCell] = {}
        for cell in element.iter(f"{_MAIN}c"):
            cells[_column_index(cell.get("r", ""), len(cells))] = _value(cell, strings)
        yield tuple(cells.get(i) for i in range(max(cells, default=-1) + 1))
        element.clear()


def _column_index(reference: str, fallback: int) -> int:
    match = _COLUMN.match(reference)
    if match is None:
        return fallback
    index = 0
    for letter in match.group():
        index = index * 26 + ord(letter) - ord("A") + 1
    return index - 1


def _value(cell: ElementTree.Element, strings: list[str]) -> SheetCell:
    kind = cell.get("t", "n")
    if kind == "inlineStr":
        return "".join(t.text or "" for t in cell.iter(f"{_MAIN}t"))
    raw = cell.findtext(f"{_MAIN}v")
    if raw is None:
        return None
    if kind == "s":
        return strings[int(raw)]
    if kind in ("str", "e"):
        return raw
    return float(raw)  # liczba, data (liczba seryjna) albo wartość logiczna 0/1
