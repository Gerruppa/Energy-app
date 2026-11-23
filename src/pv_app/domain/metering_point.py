from dataclasses import dataclass


@dataclass(frozen=True)
class MeteringPoint:
    """PPE: miejsce dostarczania energii z numerem PPE i nazwą nadaną przez użytkownika."""

    ppe_number: str
    name: str
    slug: str
    """Identyfikator w adresie widoku, np. ``?ppe=dom``."""
