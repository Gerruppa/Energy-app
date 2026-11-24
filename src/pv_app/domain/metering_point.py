import re
import unicodedata
from collections.abc import Collection
from dataclasses import dataclass
from enum import StrEnum


class SiteIcon(StrEnum):
    """Ikona PPE wybrana w kreatorze."""

    HOUSE = "dom"
    FLAT = "mieszkanie"
    OTHER = "inne"

    @property
    def emoji(self) -> str:
        return {SiteIcon.HOUSE: "🏠", SiteIcon.FLAT: "🏢", SiteIcon.OTHER: "📍"}[self]


@dataclass(frozen=True)
class MeteringPoint:
    """PPE: miejsce dostarczania energii z numerem PPE i nazwą nadaną przez użytkownika."""

    ppe_number: str
    name: str
    slug: str
    """Identyfikator w adresie widoku, np. ``?ppe=dom``."""
    icon: SiteIcon
    charges_car: bool
    """Czy w tym PPE ładowane jest auto (zakładka Auto)."""
    address: str
    """Adres z Faktury, potwierdzony w kreatorze."""
    net_metering: bool
    """Rozliczenie w net-meteringu (zakładka Magazyn energii)."""


_POLISH = str.maketrans("łŁ", "lL")


def make_slug(name: str, taken: Collection[str] = ()) -> str:
    """Identyfikator do adresu z nazwy PPE (``Mieszkanie Łódź`` → ``mieszkanie-lodz``), unikalny."""
    ascii_name = (
        unicodedata.normalize("NFKD", name.translate(_POLISH)).encode("ascii", "ignore").decode()
    )
    base = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-") or "ppe"
    slug, suffix = base, 2
    while slug in taken:
        slug, suffix = f"{base}-{suffix}", suffix + 1
    return slug
