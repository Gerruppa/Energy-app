"""Koszt okresu: która Faktura rozlicza okres i które Noty obciążeniowe go pomniejszają.

Faktura korygująca zastępuje korygowaną Fakturę (obie zostają w bazie), a Nota korygująca
zastępuje korygowaną Notę. Nota dotyczy Okresu rozliczeniowego, w którym leży jej data
sprzedaży: Nota nie podaje okresu wprost.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from decimal import Decimal
from functools import cached_property

from pv_app.domain.debit_note import DebitNote
from pv_app.domain.invoice import Invoice


def superseded_invoices(invoices: Iterable[Invoice]) -> dict[str, str]:
    """Numer zastąpionej Faktury → numer Faktury korygującej, która ją zastępuje.

    Gdy tę samą Fakturę koryguje kilka korekt, zastępuje ją najpóźniej wystawiona.
    """
    result: dict[str, str] = {}
    corrections = sorted(
        (i for i in invoices if i.correction is not None),
        key=lambda i: (i.header.issue_date, i.number),
    )
    for invoice in corrections:
        assert invoice.correction is not None
        result[invoice.correction.corrected_invoice_number] = invoice.number
    return result


def superseded_debit_notes(notes: Iterable[DebitNote]) -> dict[str, str]:
    """Numer zastąpionej Noty → numer Noty, która ją koryguje (najpóźniej wystawionej)."""
    result: dict[str, str] = {}
    for note in sorted(notes, key=lambda n: (n.issue_date, n.number)):
        if note.corrected_note_number is not None:
            result[note.corrected_note_number] = note.number
    return result


@dataclass(frozen=True)
class PeriodCosts:
    """Faktury i Noty jednego PPE z przypisaniem Not do Faktur."""

    invoices: Sequence[Invoice]
    debit_notes: Sequence[DebitNote]

    @cached_property
    def superseded_invoices(self) -> dict[str, str]:
        return superseded_invoices(self.invoices)

    @cached_property
    def superseded_debit_notes(self) -> dict[str, str]:
        return superseded_debit_notes(self.debit_notes)

    def invoice_for(self, note: DebitNote) -> Invoice | None:
        """Niezastąpiona Faktura, której Okres rozliczeniowy obejmuje datę sprzedaży Noty;
        ``None`` dla Noty zastąpionej albo bez Faktury za ten okres."""
        if note.number in self.superseded_debit_notes:
            return None
        superseded = self.superseded_invoices
        for invoice in self.invoices:
            period = invoice.header.billing_period
            if (
                invoice.number not in superseded
                and invoice.header.ppe_number == note.ppe_number
                and period.start <= note.sale_date <= period.end
            ):
                return invoice
        return None

    def debit_notes_for(self, invoice: Invoice) -> list[DebitNote]:
        return [
            note
            for note in self.debit_notes
            if (assigned := self.invoice_for(note)) is not None
            and assigned.number == invoice.number
        ]

    def period_cost(self, invoice: Invoice) -> Decimal:
        """Koszt okresu: Wynik rozliczenia brutto minus Bonifikata z Faktury i bonifikaty
        z Not obciążeniowych dotyczących tego okresu."""
        discounts = sum((note.discount for note in self.debit_notes_for(invoice)), Decimal(0))
        return invoice.result_after_discount - discounts
