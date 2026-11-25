"""Podpowiedzi „?” wspólne dla kilku widoków."""

from decimal import Decimal

from pv_app.domain.energy_store import EXPIRY_MONTHS
from pv_app.features import formatting as fmt


def store_help(discount_coefficient: Decimal) -> str:
    """Co to jest Magazyn energii, ze Współczynnikiem opustu z Faktury."""
    return (
        "Magazyn energii to nie bateria. To „konto” w Tauronie: za każdą kWh oddaną do sieci "
        f"dostajecie {fmt.decimal_pl(discount_coefficient)} kWh do odebrania później, "
        f"przez {EXPIRY_MONTHS} miesięcy."
    )


def seller_share_help(discount_coefficient: Decimal) -> str:
    return (
        f"Za 1 kWh oddaną do sieci dostajecie {fmt.decimal_pl(discount_coefficient)} kWh "
        "w Magazynie energii. Reszta to Udział Sprzedawcy: tak działają zasady net-meteringu."
    )


ESTIMATE_HELP = (
    "Faktura podaje tylko stan łączny Magazynu energii. Podział na porcje i daty Wygaśnięcia "
    f"to szacunek: każda porcja wygasa {EXPIRY_MONTHS} miesięcy po końcu okresu, w którym "
    "oddaliście prąd, a prąd pobrany z Magazynu bierzemy najpierw z najstarszej porcji."
)


FORECAST_HELP = (
    "Prognoza to zaliczka za przyszły okres, wyliczona przez Tauron z przewidywanej "
    "Energii pobranej i rozliczana w następnej Fakturze."
)
