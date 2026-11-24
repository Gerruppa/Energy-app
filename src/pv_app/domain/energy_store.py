"""Magazyn energii: porcje Energii oddanej × Współczynnik opustu i ich Wygaśnięcia.

Faktura podaje tylko stan łączny (na start i na koniec Okresu rozliczeniowego), więc stan
łączny zawsze pochodzi z Faktury, a podział na porcje i daty Wygaśnięcia są szacunkiem:
porcja wygasa 12 miesięcy po końcu okresu, w którym ją oddano, a Opust zdejmowany jest od
najstarszej porcji. Spadek stanu na start Faktury poniżej stanu na koniec poprzedniej
Faktury to Wygaśnięcie; spadek w granicy tolerancji bilansu (``ENERGY_BALANCE_TOLERANCE_KWH``)
to zaokrąglenie Taurona, nie Wygaśnięcie.
"""

import calendar
from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import date, timedelta
from decimal import Decimal
from enum import StrEnum

from pv_app.domain.invoice import DateRange, Invoice, Source
from pv_app.domain.invoice_checks import ENERGY_BALANCE_TOLERANCE_KWH
from pv_app.domain.period_cost import superseded_invoices

EXPIRY_MONTHS = 12
"""Porcja wygasa tyle miesięcy po końcu okresu, w którym ją oddano."""
EXPIRING_SOON_MONTHS = 3
"""Okno „wygaśnie wkrótce” na ekranie: tyle miesięcy od dnia stanu."""


@dataclass(frozen=True)
class Portion:
    """Porcja Magazynu energii z jednej Faktury (szacunek)."""

    invoice_number: str | None
    """``None``: stan na start pierwszej Faktury w danych, nieznanego pochodzenia."""
    period: DateRange | None
    """Okres rozliczeniowy, w którym oddano energię tej porcji."""
    credited_kwh: Decimal
    """Przyrost Magazynu energii w tym okresie (Energia oddana × Współczynnik opustu)."""
    remaining_kwh: Decimal
    """Ile z porcji zostało (szacunek)."""
    expires_on: date | None
    """Dzień Wygaśnięcia (szacunek); ``None`` dla porcji nieznanego pochodzenia."""


class MovementKind(StrEnum):
    INVOICE = "Faktura"
    EXPIRY = "Wygaśnięcie"


@dataclass(frozen=True)
class StoreMovement:
    """Ruch w Magazynie energii: Okres rozliczeniowy Faktury albo Wygaśnięcie między
    Fakturami. Na start + przybyło − Opust − wygasło = na koniec, z dokładnością do
    zaokrąglenia Taurona (``rounding_kwh``)."""

    kind: MovementKind
    invoice_number: str
    """Faktura rozliczająca ten okres; przy Wygaśnięciu ta, której stan na start spadł."""
    period: DateRange
    """Okres rozliczeniowy; przy Wygaśnięciu dzień startu Faktury, w którym widać spadek."""
    start_kwh: Decimal
    credited_kwh: Decimal
    """Przyrost: Energia oddana × Współczynnik opustu."""
    discount_kwh: Decimal
    """Opust: część Energii pobranej pokryta z Magazynu energii, wyliczona z Faktury jak
    ``Invoice.discount_kwh`` (Energia pobrana − kWh energii czynnej)."""
    expired_kwh: Decimal
    """Wygaśnięcie, wyliczone: stan na koniec poprzedniej Faktury − stan na start tej."""
    end_kwh: Decimal
    start_source: Source
    """Strona ze stanem na start (przy Wygaśnięciu: Rozliczenie OZE poprzedniej Faktury)."""
    end_source: Source
    """Strona ze stanem na koniec (przy Wygaśnięciu: stan na start następnej Faktury)."""
    discount_coefficient: Decimal
    """Współczynnik opustu z Faktury."""
    seller_share_kwh: Decimal = Decimal(0)
    """Udział Sprzedawcy: Energia oddana, która nie trafiła do Magazynu energii."""
    imported_kwh: Decimal = Decimal(0)
    """Energia pobrana w okresie; Opust to jej część pokryta z Magazynu energii."""

    @property
    def rounding_kwh(self) -> Decimal:
        """O ile stan na koniec z Faktury różni się od bilansu ruchu (na start + przybyło −
        Opust − wygasło); Tauron bilansuje godzinowo i zaokrągla, zwykle do 1 kWh."""
        return self.end_kwh - (
            self.start_kwh + self.credited_kwh - self.discount_kwh - self.expired_kwh
        )


@dataclass(frozen=True)
class StoreState:
    """Magazyn energii po Fakturze: stan łączny z Faktury i jego podział (szacunek)."""

    movement: StoreMovement
    """Ruch Faktury, z której jest stan."""
    portions: tuple[Portion, ...]
    """Porcje w stanie, od najwcześniej wygasającej (szacunek)."""
    expiring_until: date
    """Koniec okna „wygaśnie wkrótce”."""

    @property
    def balance_kwh(self) -> Decimal:
        return self.movement.end_kwh

    @property
    def as_of(self) -> date:
        """Koniec Okresu rozliczeniowego Faktury, z której jest stan."""
        return self.movement.period.end

    @property
    def source(self) -> Source:
        return self.movement.end_source

    @property
    def expiring(self) -> tuple[Portion, ...]:
        """Porcje, które wygasną do ``expiring_until`` (szacunek); także porcja z datą
        Wygaśnięcia przed dniem stanu, bo jest jeszcze w stanie z Faktury."""
        return tuple(
            p
            for p in self.portions
            if p.expires_on is not None and p.expires_on <= self.expiring_until
        )

    @property
    def expiring_kwh(self) -> Decimal:
        return sum((p.remaining_kwh for p in self.expiring), Decimal(0))


@dataclass(frozen=True)
class _Snapshot:
    movement: StoreMovement
    portions: tuple[Portion, ...]


def add_months(day: date, months: int) -> date:
    """Ten sam dzień ``months`` miesięcy później; ostatni dzień miesiąca, gdy go brak."""
    index = day.year * 12 + day.month - 1 + months
    year, month = divmod(index, 12)
    month += 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def _take(portions: list[Portion], kwh: Decimal) -> None:
    """Zdejmuje ``kwh`` od najstarszej porcji; puste porcje znikają."""
    while kwh > 0 and portions:
        oldest = portions[0]
        taken = min(oldest.remaining_kwh, kwh)
        kwh -= taken
        if taken == oldest.remaining_kwh:
            portions.pop(0)
        else:
            portions[0] = replace(oldest, remaining_kwh=oldest.remaining_kwh - taken)


def _match(portions: list[Portion], target: Decimal) -> None:
    """Dopasowuje sumę porcji do stanu z Faktury: nadmiar zdejmuje od najstarszej porcji,
    brak (zaokrąglenia, luka w Fakturach) dopisuje do najnowszej albo do porcji nieznanego
    pochodzenia."""
    difference = target - sum((p.remaining_kwh for p in portions), Decimal(0))
    if difference < 0:
        _take(portions, -difference)
    elif difference > 0:
        if portions:
            newest = portions[-1]
            portions[-1] = replace(newest, remaining_kwh=newest.remaining_kwh + difference)
        else:
            portions.append(Portion(None, None, difference, difference, None))


class EnergyStore:
    """Księga Magazynu energii jednego PPE zbudowana z historii Faktur."""

    def __init__(self, snapshots: tuple[_Snapshot, ...]) -> None:
        self._snapshots = snapshots

    @classmethod
    def from_invoices(cls, invoices: Iterable[Invoice]) -> "EnergyStore":
        """Z Faktur PPE; Faktury zastąpione i bez Rozliczenia OZE są pomijane."""
        invoices = list(invoices)
        superseded = superseded_invoices(invoices)
        settled = sorted(
            (i for i in invoices if i.number not in superseded and i.energy_settlement),
            key=lambda i: (i.header.billing_period.start, i.number),
        )
        portions: list[Portion] = []
        snapshots: list[_Snapshot] = []
        previous: StoreMovement | None = None
        for invoice in settled:
            store = invoice.energy_settlement
            assert store is not None
            period = invoice.header.billing_period
            start = store.store_start_kwh
            contiguous = previous is not None and previous.period.end + timedelta(1) == (
                period.start
            )
            drop = previous.end_kwh - start if previous is not None else Decimal(0)
            if previous is not None and contiguous and drop > ENERGY_BALANCE_TOLERANCE_KWH:
                expired = drop
                _take(portions, expired)
                snapshots.append(
                    _Snapshot(
                        StoreMovement(
                            kind=MovementKind.EXPIRY,
                            invoice_number=invoice.number,
                            period=DateRange(period.start, period.start),
                            start_kwh=previous.end_kwh,
                            credited_kwh=Decimal(0),
                            discount_kwh=Decimal(0),
                            expired_kwh=expired,
                            end_kwh=start,
                            start_source=previous.end_source,
                            end_source=store.source,
                            discount_coefficient=store.discount_coefficient,
                        ),
                        tuple(portions),
                    )
                )
            _match(portions, start)
            credited = store.exported_after_coefficient_kwh
            portions.append(
                Portion(
                    invoice.number,
                    period,
                    credited,
                    credited,
                    add_months(period.end, EXPIRY_MONTHS),
                )
            )
            discount = invoice.discount_kwh
            _take(portions, discount)
            _match(portions, store.store_end_kwh)
            previous = StoreMovement(
                kind=MovementKind.INVOICE,
                invoice_number=invoice.number,
                period=period,
                start_kwh=start,
                credited_kwh=credited,
                discount_kwh=discount,
                expired_kwh=Decimal(0),
                end_kwh=store.store_end_kwh,
                start_source=store.source,
                end_source=store.source,
                discount_coefficient=store.discount_coefficient,
                seller_share_kwh=store.seller_share_kwh,
                imported_kwh=store.imported_kwh,
            )
            snapshots.append(_Snapshot(previous, tuple(portions)))
        return cls(tuple(snapshots))

    @property
    def movements(self) -> tuple[StoreMovement, ...]:
        """Ruchy od najstarszego: Faktury i Wygaśnięcia między nimi."""
        return tuple(s.movement for s in self._snapshots)

    def _last_before(self, day: date) -> _Snapshot | None:
        known = [
            s
            for s in self._snapshots
            if s.movement.kind is MovementKind.INVOICE and s.movement.period.end <= day
        ]
        return known[-1] if known else None

    def portions_on(self, day: date) -> tuple[Portion, ...]:
        """Porcje po ostatniej Fakturze, której okres skończył się do ``day`` (szacunek),
        od najstarszej."""
        snapshot = self._last_before(day)
        return snapshot.portions if snapshot is not None else ()

    def state_on(self, day: date, expiring_months: int = EXPIRING_SOON_MONTHS) -> StoreState | None:
        """Stan po ostatniej Fakturze, której okres skończył się do ``day``, z porcjami
        wygasającymi w ``expiring_months`` miesięcy od dnia stanu; ``None`` bez takiej
        Faktury."""
        snapshot = self._last_before(day)
        if snapshot is None:
            return None
        as_of = snapshot.movement.period.end
        return StoreState(
            movement=snapshot.movement,
            portions=tuple(sorted(snapshot.portions, key=lambda p: p.expires_on or date.min)),
            expiring_until=add_months(as_of, expiring_months),
        )
