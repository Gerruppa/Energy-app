from dataclasses import dataclass, field

from pv_app.domain.invoice import Invoice


@dataclass(frozen=True)
class ImportResult:
    """Wynik importu jednego pliku: Faktura albo przyczyna odrzucenia, plus ostrzeżenia."""

    file_name: str
    invoice: Invoice | None = None
    rejection: str | None = None
    """Przyczyna odrzucenia po polsku, do pokazania użytkownikowi."""
    warnings: tuple[str, ...] = field(default=())
