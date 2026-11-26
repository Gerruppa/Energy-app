"""Wygaśnięcie porcji Magazynu energii w przeliczeniu na dni Energii pobranej (szacunek).

Wspólne dla zakładki Magazyn energii i kafelka w Przeglądzie; czyste analizy na
``Repository``. Do Wygaśnięcia porcji dom pobiera z sieci tyle, ile w tych samych miesiącach
rok wcześniej (z Faktur, rozkład na miesiące); miesiąc bez pełnej historii rok wcześniej
dostaje średnią dzienną Energię pobraną z Faktur z ostatnich ``AVERAGE_MONTHS`` miesięcy
przed dniem stanu. Prąd pobrany z sieci pokrywa najpierw najstarsza porcja (Opust), a część
porcji, która wygaśnie, niczego już nie pokrywa.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from pv_app.domain.energy_store import Portion, StoreState, add_months
from pv_app.domain.view_period import first_day, last_day, month_index
from pv_app.features import formatting as fmt
from pv_app.features.monthly import History
from pv_app.storage.repository import Repository

AVERAGE_MONTHS = 12
"""Z Faktur z tylu miesięcy przed dniem stanu liczymy średnią, gdy brak roku wcześniej."""


@dataclass(frozen=True)
class ImportedEstimate:
    """Szacunek Energii pobranej."""

    kwh: Decimal
    year_earlier: bool
    """Całość z tych samych miesięcy rok wcześniej; ``False``: choć część ze średniej
    z ostatnich Faktur."""


@dataclass(frozen=True)
class ExpiryOutlook:
    """Porcja wygasająca wkrótce: ile z niej wygaśnie według szacunku Energii pobranej."""

    portion: Portion
    lost_kwh: Decimal
    """Ile z porcji wygaśnie, zanim dom ją odbierze (szacunek)."""
    month: int
    """``month_index`` miesiąca Wygaśnięcia: w nim przeliczamy na dni."""
    daily_imported_kwh: Decimal
    """Szacunek Energii pobranej na dzień w miesiącu Wygaśnięcia."""
    year_earlier: bool
    """Każdy miesiąc do Wygaśnięcia i miesiąc Wygaśnięcia z roku wcześniej; ``False``: choć
    jeden ze średniej z ostatnich Faktur."""
    overdue: bool
    """Data Wygaśnięcia przed dniem stanu: porcja jest jeszcze w stanie z Faktury, ale
    wygaśnie przed następną Fakturą."""

    @property
    def used(self) -> bool:
        """Dom odbierze całą porcję przed Wygaśnięciem."""
        return self.lost_kwh <= 0

    @property
    def lost_days(self) -> Decimal | None:
        """Część, która wygaśnie, w dniach Energii pobranej w miesiącu Wygaśnięcia; ``None``
        przy zerowej Energii pobranej."""
        return self.lost_kwh / self.daily_imported_kwh if self.daily_imported_kwh else None


def lost_portions(outlook: Iterable[ExpiryOutlook]) -> list[Portion]:
    """Porcje, z których według szacunku coś wygaśnie (⚠, czerwone na pasku)."""
    return [o.portion for o in outlook if not o.used]


class _ImportedHistory:
    def __init__(self, history: History, as_of: date) -> None:
        self._history = history
        since = add_months(as_of, -AVERAGE_MONTHS)
        recent = [i for i in history.invoices if since < i.header.billing_period.end <= as_of]
        imported = sum((i.imported_kwh for i in recent), Decimal(0))
        days = sum(i.header.billing_period.days for i in recent)
        self._average = imported / days if days else Decimal(0)

    def daily(self, month: int) -> ImportedEstimate:
        """Energia pobrana na dzień w ``month``: z tego miesiąca rok wcześniej albo średnia."""
        earlier = month - 12
        if self._history.covered(earlier):
            days = (last_day(earlier) - first_day(earlier)).days + 1
            return ImportedEstimate(self._history.totals([earlier]).imported_kwh / days, True)
        return ImportedEstimate(self._average, False)

    def between(self, start: date, end: date) -> ImportedEstimate:
        """Energia pobrana od ``start`` do ``end`` włącznie (zero, gdy ``start > end``)."""
        total, year_earlier = Decimal(0), True
        if start <= end:
            for month in range(month_index(start), month_index(end) + 1):
                days = (min(end, last_day(month)) - max(start, first_day(month))).days + 1
                daily = self.daily(month)
                total += daily.kwh * days
                year_earlier = year_earlier and daily.year_earlier
        return ImportedEstimate(total, year_earlier)


def expiry_outlook(
    repository: Repository, ppe_number: str, state: StoreState
) -> tuple[ExpiryOutlook, ...]:
    """Porcje wygasające do ``state.expiring_until``, od najwcześniej wygasającej, z tym, ile
    z nich wygaśnie (szacunek)."""
    expiring = state.expiring
    if not expiring:
        return ()
    imported = _ImportedHistory(History(repository, ppe_number), state.as_of)
    first_day_after = state.as_of + timedelta(1)
    # Energia pobrana, którą pokryją porcje odbierane wcześniej (od najstarszej).
    taken = Decimal(0)
    result = []
    for portion in state.portions:
        if portion.expires_on is None:
            taken += portion.remaining_kwh
            continue
        if portion not in expiring:
            break
        until_expiry = imported.between(first_day_after, portion.expires_on)
        used = min(portion.remaining_kwh, max(Decimal(0), until_expiry.kwh - taken))
        taken += used
        month = month_index(portion.expires_on)
        daily = imported.daily(month)
        result.append(
            ExpiryOutlook(
                portion=portion,
                lost_kwh=portion.remaining_kwh - used,
                month=month,
                daily_imported_kwh=daily.kwh,
                year_earlier=until_expiry.year_earlier and daily.year_earlier,
                overdue=portion.expires_on < state.as_of,
            )
        )
    return tuple(result)


def _days(value: Decimal) -> str:
    days = int(value.quantize(Decimal(1), ROUND_HALF_UP))
    if days == 0:
        return "niecały dzień"
    return "1 dzień" if days == 1 else f"{days} dni"


def _lost(outlook: ExpiryOutlook) -> str:
    if outlook.overdue:
        return "wygaśnie przed następną Fakturą"
    if outlook.lost_kwh == outlook.portion.remaining_kwh:
        return "nie zdążycie jej odebrać"
    return f"zdążycie odebrać część, a ok. {fmt.kwh(outlook.lost_kwh)} wygaśnie"


def outlook_text(outlook: ExpiryOutlook) -> str:
    """Zdanie prostym językiem: czy porcja zdąży się odebrać, a jeśli nie, ile z niej
    wygaśnie w dniach Energii pobranej."""
    if outlook.used:
        return "zdążycie ją odebrać: dom pobierze tyle z sieci przed Wygaśnięciem"
    days = outlook.lost_days
    if days is None:
        return _lost(outlook)
    return (
        f"{_lost(outlook)}, to mniej więcej tyle, ile dom pobiera z sieci przez {_days(days)} "
        f"{fmt.in_month_name(outlook.month)}"
    )


def outlook_line(outlook: ExpiryOutlook) -> str:
    """„⚠ 20 kWh wygaśnie 31.12.2025: …” z ``outlook_text``; ✓ przy porcji, którą dom
    odbierze. „Wygaśnie” tylko przy całej porcji; przy części „ważne do”, bo ile wygaśnie,
    mówi zdanie."""
    portion = outlook.portion
    assert portion.expires_on is not None
    mark = "✓" if outlook.used else "⚠"
    if outlook.overdue:
        when = "po terminie"
    elif outlook.lost_kwh == portion.remaining_kwh:
        when = "wygaśnie"
    else:
        when = "ważne do"
    return (
        f"{mark} {fmt.kwh(portion.remaining_kwh)} {when} {fmt.day(portion.expires_on)}: "
        f"{outlook_text(outlook)}"
    )


def outlook_help(outlook: ExpiryOutlook) -> str:
    """Podpowiedź „?”: jak wyliczono zdanie z ``outlook_text``."""
    basis = "tyle, ile w tych samych miesiącach rok wcześniej (z Faktur, rozkład na miesiące)"
    if not outlook.year_earlier:
        basis += (
            ", a w miesiącach bez Faktur rok wcześniej średnio tyle, ile dziennie w Fakturach "
            f"z ostatnich {AVERAGE_MONTHS} miesięcy"
        )
    return (
        f"Szacunek. Zakładamy, że do dnia Wygaśnięcia dom pobierze z sieci {basis}. Prąd "
        "pobrany z sieci pokrywa najpierw najstarsza porcja; czego nie zdążycie odebrać, to "
        "wygasa. Dni: część, która wygaśnie, podzielona przez prąd pobierany z sieci na dzień "
        f"{fmt.in_month_name(outlook.month)} (ok. {fmt.kwh(outlook.daily_imported_kwh, 1)} "
        "dziennie)."
    )
