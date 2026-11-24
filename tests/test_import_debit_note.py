"""Seam importu: surowe wiersze Noty obciążeniowej → wynik importu (ADR 0005).

Fixture ``tests/fixtures/debit_note_correction.json`` ma wymyślone numery i kwoty.
"""

from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path

from pv_app.domain.debit_note import DebitNote, DebitNoteItem
from pv_app.domain.invoice import Source
from pv_app.ingest import import_document
from pv_app.ingest.raw import RawDocument, RawPage

FIXTURE = Path(__file__).parent / "fixtures" / "debit_note_correction.json"
NUMBER = "TM3NBN000002/001"


def load() -> RawDocument:
    return RawDocument.from_json(FIXTURE)


def test_debit_note_correction_is_read_without_kwh() -> None:
    result = import_document(load())

    assert result.rejection is None
    assert result.invoice is None
    assert result.warnings == ()
    assert result.debit_note == DebitNote(
        number=NUMBER,
        corrected_note_number="T3N0000007",
        issue_date=date(2026, 2, 7),
        sale_date=date(2026, 2, 1),
        ppe_number="590000000000000002",
        items=(
            DebitNoteItem(
                name="Obniżka kwoty należności (Rozp. MKiŚ z 09.09.2023)",
                charged=Decimal("60.00"),
                should_have_charged=Decimal("47.70"),
            ),
        ),
        amount_due=Decimal("12.30"),
        due_date=date(2026, 2, 23),
        source=Source(NUMBER, 1),
    )


def test_discount_of_debit_note_is_what_should_have_been_charged() -> None:
    note = import_document(load()).debit_note
    assert note is not None

    assert note.discount == Decimal("47.70")


def test_rejects_debit_note_whose_amount_due_is_not_the_difference() -> None:
    document = load()
    page = document.pages[0]
    changed = tuple(
        ("Do zapłaty:", "13,30 zł") if row == ("Do zapłaty:", "12,30 zł") else row
        for row in page.rows
    )
    document = RawDocument((RawPage(1, tuple(" ".join(r) for r in changed), changed),))

    result = import_document(document)

    assert result.debit_note is None
    assert result.rejection is not None
    assert result.rejection.startswith(f"Nota obciążeniowa {NUMBER} odrzucona:")


def test_warns_about_item_that_is_not_a_known_discount() -> None:
    document = load()
    page = document.pages[0]
    rows = tuple(
        tuple("Inna opłata testowa" if cell.startswith("Obniżka") else cell for cell in row)
        for row in page.rows
    )
    document = RawDocument((replace(page, lines=tuple(" ".join(r) for r in rows), rows=rows),))

    result = import_document(document)

    assert result.debit_note is not None
    assert result.debit_note.discount == Decimal(0)
    assert result.warnings == (
        "Nierozpoznana pozycja Noty obciążeniowej „Inna opłata testowa” (strona 1); "
        "nie pomniejsza Kosztu okresu.",
    )
