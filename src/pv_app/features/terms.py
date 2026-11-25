"""Podpowiedzi „?” wspólne dla kilku widoków."""

from decimal import Decimal

from pv_app.domain.cost_groups import CostGroup
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


STORED_HELP = (
    "Ile kWh przybyło w Magazynie energii: oddane do sieci × Współczynnik opustu z Faktury "
    "(np. 0,8 kWh za każdą oddaną kWh)."
)


FORECAST_HELP = (
    "Prognoza to zaliczka za przyszły okres, wyliczona przez Tauron z przewidywanej "
    "Energii pobranej i rozliczana w następnej Fakturze."
)


GROUP_TEXTS = {
    CostGroup.ENERGY: (
        "Cena za sam prąd pobrany z sieci.",
        " kWh pokryte z Magazynu energii są tu za darmo, dlatego często 0 zł.",
    ),
    CostGroup.VARIABLE_DISTRIBUTION: (
        "Opłata za przesłanie każdej kWh siecią Taurona (składnik zmienny stawki sieciowej "
        "i stawka jakościowa).",
        " Też pokrywana z Magazynu energii.",
    ),
    CostGroup.PER_KWH_FEES: (
        "Opłata OZE i kogeneracyjna: małe dopłaty do zielonej energii i elektrociepłowni, "
        "liczone od każdej pobranej kWh.",
        " Liczone także od kWh z Magazynu energii, dlatego nigdy nie są zerowe.",
    ),
    CostGroup.CAPACITY: (
        "Stała miesięczna kwota za gotowość elektrowni na szczyty zużycia w kraju. Jej "
        "wysokość zależy od tego, ile prądu pobieracie w ciągu roku.",
        "",
    ),
    CostGroup.FIXED_FEES: (
        "Podłączenie do sieci (składnik stały stawki sieciowej), odczyty i rozliczenia "
        "(opłata abonamentowa) i opłata przejściowa. Płacone co miesiąc niezależnie od zużycia.",
        "",
    ),
    CostGroup.UNRECOGNIZED: (
        "Pozycje, których nazwy aplikacja nie zna. Sprawdźcie je w oryginale PDF.",
        "",
    ),
}
"""Opis grupy prostym językiem; drugi tekst dochodzi przy net-meteringu."""


def group_text(group: CostGroup, net_metering: bool) -> str:
    """Opis Grupy kosztów prostym językiem, z dopiskiem o Magazynie energii przy net-meteringu."""
    base, with_pv = GROUP_TEXTS[group]
    return base + (with_pv if net_metering else "")
