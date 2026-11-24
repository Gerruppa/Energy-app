"""Głęboki moduł: komórki wierszy Noty obciążeniowej korekty → ``DebitNote``.

Nota ma jedną stronę: tytuł z numerem korygowanej noty, datę sprzedaży, tabele pozycji
„POLICZONO” i „NALEŻAŁO POLICZYĆ” (nazwa usługi, PPE, wartość) i kwotę do zapłaty.
"""

import re
from decimal import Decimal

from pv_app.domain.debit_note import DebitNote, DebitNoteItem, is_discount
from pv_app.domain.invoice import Source
from pv_app.ingest.parse_error import ParseError
from pv_app.ingest.polish_format import DATE, NUMBER, parse_date, parse_number
from pv_app.ingest.raw import RawDocument, RawPage

_TITLE = re.compile(r"^NOTA OBCIĄŻENIOWA KOREKTA NR (\S+)(?: do noty nr (\S+))? - ")
_PARTS = {"POLICZONO:": "charged", "NALEŻAŁO POLICZYĆ:": "should_have_charged"}


def is_debit_note(document: RawDocument) -> bool:
    return any(_TITLE.match(line) for page in document.pages for line in page.lines)


def parse_debit_note(document: RawDocument) -> tuple[DebitNote, list[str]]:
    """Nota i ostrzeżenia o pozycjach, które nie są znaną bonifikatą."""
    page = next(p for p in document.pages if any(_TITLE.match(line) for line in p.lines))
    if not page.rows:
        raise ParseError("Brak komórek tabel: Notę obciążeniową trzeba wgrać jako PDF.")
    title = next(m for line in page.lines if (m := _TITLE.match(line)))
    number = title.group(1)
    values = _item_values(page)
    names = list(values["charged"])
    if not names or names != list(values["should_have_charged"]):
        raise ParseError(f"Pozycje „policzono” i „należało policzyć” Noty {number} się różnią.")
    ppe_numbers = {values["charged"][name][0] for name in names}
    if len(ppe_numbers) != 1:
        raise ParseError(f"Nota obciążeniowa {number} dotyczy kilku PPE albo żadnego.")
    settled = _require(page, rf"^Do (zapłaty|zwrotu): ({NUMBER}) zł$", "kwota do zapłaty")
    due_date = _find(page, rf"^Termin płatności: ({DATE})$")
    amount = parse_number(settled.group(2))
    warnings = [
        f"Nierozpoznana pozycja Noty obciążeniowej „{name}” (strona {page.number}); "
        "nie pomniejsza Kosztu okresu."
        for name in names
        if not is_discount(name)
    ]
    note = DebitNote(
        number=number,
        corrected_note_number=title.group(2),
        issue_date=parse_date(_require(page, rf"^Data wystawienia: ({DATE})$", "data").group(1)),
        sale_date=parse_date(
            _require(page, rf"^Data sprzedaży: ({DATE})$", "data sprzedaży").group(1)
        ),
        ppe_number=ppe_numbers.pop(),
        items=tuple(
            DebitNoteItem(
                name=name,
                charged=values["charged"][name][1],
                should_have_charged=values["should_have_charged"][name][1],
            )
            for name in names
        ),
        amount_due=-amount if settled.group(1) == "zwrotu" else amount,
        due_date=parse_date(due_date.group(1)) if due_date else None,
        source=Source(number, page.number),
    )
    return note, warnings


def _item_values(page: RawPage) -> dict[str, dict[str, tuple[str, Decimal]]]:
    """Pozycje każdej części: nazwa usługi → (numer PPE, wartość)."""
    parts: dict[str, dict[str, tuple[str, Decimal]]] = {key: {} for key in _PARTS.values()}
    current: str | None = None
    for cells in page.rows:
        text = " ".join(cells)
        if text in _PARTS:
            current = _PARTS[text]
            continue
        if (
            current is not None
            and len(cells) == 4
            and re.fullmatch(r"\d+", cells[0])
            and re.fullmatch(r"\d+", cells[2])
            and re.fullmatch(NUMBER, cells[3])
        ):
            parts[current][" ".join(cells[1].split())] = (cells[2], parse_number(cells[3]))
    return parts


def _find(page: RawPage, pattern: str) -> re.Match[str] | None:
    regex = re.compile(pattern)
    return next((m for line in page.lines if (m := regex.match(line))), None)


def _require(page: RawPage, pattern: str, what: str) -> re.Match[str]:
    match = _find(page, pattern)
    if match is None:
        raise ParseError(f"Nie znaleziono na Nocie obciążeniowej: {what}.")
    return match
