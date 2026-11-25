from dataclasses import dataclass, field

from pv_app.domain.debit_note import DebitNote
from pv_app.domain.hourly_profile import HourlyValuesReport
from pv_app.domain.invoice import Invoice


@dataclass(frozen=True)
class ImportResult:
    """Wynik importu jednego pliku: Faktura, Nota obciążeniowa, Raport wartości godzinowych
    albo przyczyna odrzucenia, plus ostrzeżenia."""

    file_name: str
    invoice: Invoice | None = None
    rejection: str | None = None
    """Przyczyna odrzucenia po polsku, do pokazania użytkownikowi."""
    warnings: tuple[str, ...] = field(default=())
    debit_note: DebitNote | None = None
    hourly_report: HourlyValuesReport | None = None
