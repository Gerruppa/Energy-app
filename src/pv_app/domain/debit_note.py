"""Nota obciążeniowa: dokument Tauron bez kWh z bonifikatą dla PPE; pojęcia z ``GLOSSARY.md``."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from pv_app.domain.formatting import zl
from pv_app.domain.invoice import Source

MONEY_TOLERANCE = Decimal("0.01")

_DISCOUNT_NAMES = ("obniżka kwoty należności",)
"""Początki nazw pozycji, które są bonifikatą (pomniejszają Koszt okresu)."""


def is_discount(name: str) -> bool:
    """Czy pozycja Noty obciążeniowej o tej nazwie jest bonifikatą."""
    return " ".join(name.lower().split()).startswith(_DISCOUNT_NAMES)


@dataclass(frozen=True)
class DebitNoteItem:
    """Pozycja Noty obciążeniowej korekty: kwota „policzono” i „należało policzyć”."""

    name: str
    charged: Decimal
    should_have_charged: Decimal


@dataclass(frozen=True)
class DebitNote:
    number: str
    corrected_note_number: str | None
    """Nota, którą ta Nota koryguje (``do noty nr …``)."""
    issue_date: date
    """Data wystawienia: od niej Nota liczy się w Saldzie."""
    sale_date: date
    """Data sprzedaży: wskazuje Okres rozliczeniowy, którego Nota dotyczy."""
    ppe_number: str
    items: tuple[DebitNoteItem, ...]
    amount_due: Decimal
    """Do zapłaty; ujemna kwota = do zwrotu."""
    due_date: date | None
    source: Source
    """Nota ma jedną stronę, więc wszystkie jej wartości mają to samo źródło."""

    @property
    def discount(self) -> Decimal:
        """Bonifikata po korekcie („należało policzyć”), dodatnia; pomniejsza Koszt okresu."""
        return sum(
            (item.should_have_charged for item in self.items if is_discount(item.name)),
            Decimal(0),
        )


def check_debit_note(note: DebitNote) -> list[str]:
    """Opisy niezgodności po polsku; pusta lista = Nota się zgadza.

    Bonifikata zmniejsza należność, więc do zapłaty jest jej spadek: „policzono” minus
    „należało policzyć”.
    """
    charged = sum((item.charged for item in note.items), Decimal(0))
    should_have = sum((item.should_have_charged for item in note.items), Decimal(0))
    if abs(charged - should_have - note.amount_due) > MONEY_TOLERANCE:
        return [
            f"Do zapłaty ({zl(note.amount_due)}) nie jest różnicą bonifikaty "
            f"„policzono” ({zl(charged)}) i „należało policzyć” ({zl(should_have)})."
        ]
    return []
