"""Faktura i jej części, tak jak je podaje Tauron; pojęcia z ``GLOSSARY.md``."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum


@dataclass(frozen=True)
class Source:
    """Skąd pochodzi wartość: numer Faktury i strona PDF-a (od 1)."""

    invoice_number: str
    page: int


@dataclass(frozen=True)
class DateRange:
    start: date
    end: date
    """Ostatni dzień zakresu (włącznie)."""

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1


class DocumentKind(StrEnum):
    SETTLEMENT_INVOICE = "Faktura rozliczeniowa"
    CORRECTING_INVOICE = "Faktura korygująca"
    DEBIT_NOTE = "Nota obciążeniowa"


class Layout(StrEnum):
    OLD = "stary"
    NEW = "nowy"


class SettlementType(StrEnum):
    STANDARD = "standardowe"
    NET_METERING = "Net-metering"


class ReadingType(StrEnum):
    """Typ odczytu."""

    REMOTE = "zdalny"
    PHYSICAL = "fizyczny"
    CUSTOMER = "odbiorcy"
    ESTIMATED = "szacunkowy"


class SettlementBasis(StrEnum):
    """Podstawa rozliczenia."""

    ACTUAL_READING = "odczyt rzeczywisty"
    ESTIMATED_READING = "odczyt szacunkowy"
    FORECAST = "Prognoza"


class MeterDirection(StrEnum):
    IMPORT = "pobór"
    EXPORT = "oddanie"


class InvoiceSection(StrEnum):
    SALES = "Sprzedaż energii elektrycznej"
    DISTRIBUTION = "Dystrybucja energii elektrycznej"


class LineComponent(StrEnum):
    """Składnik Pozycji faktury (kategorie z ``GLOSSARY.md``)."""

    ACTIVE_ENERGY = "energia czynna"
    VARIABLE_NETWORK = "dystrybucja zmienna"
    QUALITY = "opłata jakościowa"
    OZE = "opłata OZE"
    COGENERATION = "opłata kogeneracyjna"
    FIXED_NETWORK = "dystrybucja stała"
    TRANSITIONAL = "opłata przejściowa"
    SUBSCRIPTION = "opłata abonamentowa"
    CAPACITY = "opłata mocowa"

    @property
    def is_variable(self) -> bool:
        """Składnik zmienny (od kWh); inaczej Składnik stały."""
        return self in _VARIABLE_COMPONENTS


_VARIABLE_COMPONENTS = frozenset(
    {
        LineComponent.ACTIVE_ENERGY,
        LineComponent.VARIABLE_NETWORK,
        LineComponent.QUALITY,
        LineComponent.OZE,
        LineComponent.COGENERATION,
    }
)


@dataclass(frozen=True)
class InvoiceHeader:
    number: str
    issue_date: date
    billing_period: DateRange
    """Okres rozliczeniowy."""
    ppe_number: str
    site_name: str
    """Nazwa obiektu na Fakturze (nie nazwa PPE nadana w aplikacji)."""
    address: str
    tariff_group: str
    contracted_power_kw: Decimal
    settlement_type: SettlementType
    billing_frequency_months: int | None
    source: Source
    """Strona „To jest Twoja faktura”: numer, daty, taryfa, moc."""
    site_source: Source
    """Strona podsumowania: numer PPE, nazwa obiektu, adres, częstotliwość rozliczenia."""


@dataclass(frozen=True)
class MeterReading:
    """Odczyt licznika; nowy układ dla net-meteringu podaje tylko ilość, bez stanów."""

    meter_number: str
    direction: MeterDirection
    zone: str
    reading_date: date
    reading_type: ReadingType
    previous: Decimal | None
    current: Decimal | None
    quantity_kwh: Decimal
    source: Source


@dataclass(frozen=True)
class EnergySettlement:
    """Rozliczenie OZE: ruch w Magazynie energii w Okresie rozliczeniowym."""

    imported_kwh: Decimal
    """Energia pobrana."""
    exported_kwh: Decimal
    """Energia oddana."""
    store_start_kwh: Decimal
    """Magazyn energii na początku okresu („Energia z magazynu”)."""
    discount_coefficient: Decimal
    """Współczynnik opustu."""
    exported_after_coefficient_kwh: Decimal
    """Przyrost Magazynu energii (Energia oddana × Współczynnik opustu)."""
    remaining_from_this_period_kwh: Decimal
    """„Z bieżącego rozliczenia pozostało X kWh przez 12 miesięcy”."""
    seller_share_kwh: Decimal
    """Udział Sprzedawcy."""
    store_end_kwh: Decimal
    """Magazyn energii na koniec okresu."""
    source: Source


@dataclass(frozen=True)
class InvoiceLine:
    """Pozycja faktury: składnik w jednym podokresie, z jedną ceną i stawką VAT."""

    section: InvoiceSection
    name: str
    """Nazwa jak na Fakturze."""
    component: LineComponent | None
    """``None``, gdy nazwy nie rozpoznano (import zgłasza ostrzeżenie)."""
    zone: str | None
    sub_period: int
    """Numer podokresu w kolejności z Faktury (od 1); nowy układ nie drukuje jego dat."""
    quantity: Decimal
    unit: str
    """``kWh`` albo ``mc`` (miesiące)."""
    unit_price_net: Decimal
    net: Decimal
    vat_rate: Decimal
    vat: Decimal
    gross: Decimal
    source: Source


@dataclass(frozen=True)
class Amount:
    net: Decimal | None
    vat: Decimal | None
    gross: Decimal


@dataclass(frozen=True)
class SettlementSummary:
    """Podsumowanie rozliczenia z Faktury; kwoty ze znakiem jak na Fakturze."""

    sales: Amount
    distribution: Amount
    result: Amount
    """Wynik rozliczenia (sprzedaż + dystrybucja)."""
    previous_forecast: Amount | None
    """Prognoza z poprzedniej Faktury (ujemna: już zapłacona)."""
    additional_payments: Decimal | None
    """Wpłaty dodatkowe (odejmowane od Wyniku rozliczenia)."""
    amount_due: Decimal
    """Do zapłaty; ujemna kwota = nadpłata do zwrotu."""
    account_balance: Decimal | None
    """Saldo po Fakturze: dodatnie = nadpłata, ujemne = niedopłata; ``None``, gdy nie podano."""
    excise_kwh: Decimal | None
    excise_amount: Decimal | None
    same_period_last_year_kwh: Decimal | None
    """Energia pobrana w analogicznym okresie poprzedniego roku według Taurona."""
    same_period_last_year_source: Source | None
    source: Source


@dataclass(frozen=True)
class Forecast:
    """Prognoza z harmonogramu płatności na kolejny okres."""

    number: str
    period: DateRange
    import_kwh: Decimal
    export_kwh: Decimal | None
    net: Decimal
    vat: Decimal
    gross: Decimal
    discount: Decimal
    balance_adjustment: Decimal
    """Nadpłata (ujemna) lub niedopłata (dodatnia) doliczona do tej Prognozy."""
    amount_due: Decimal
    due_date: date
    source: Source


@dataclass(frozen=True)
class Invoice:
    kind: DocumentKind
    layout: Layout
    header: InvoiceHeader
    readings: tuple[MeterReading, ...]
    energy_settlement: EnergySettlement | None
    """Tylko przy net-meteringu."""
    lines: tuple[InvoiceLine, ...]
    summary: SettlementSummary
    forecasts: tuple[Forecast, ...]

    @property
    def number(self) -> str:
        return self.header.number

    @property
    def period_cost(self) -> Decimal:
        """Koszt okresu: Wynik rozliczenia brutto (bez Not obciążeniowych, które dojdą później)."""
        return self.summary.result.gross

    @property
    def settlement_basis(self) -> SettlementBasis:
        if any(r.reading_type is ReadingType.ESTIMATED for r in self.readings):
            return SettlementBasis.ESTIMATED_READING
        return SettlementBasis.ACTUAL_READING

    @property
    def imported_kwh(self) -> Decimal:
        """Energia pobrana w Okresie rozliczeniowym."""
        if self.energy_settlement is not None:
            return self.energy_settlement.imported_kwh
        return sum(
            (r.quantity_kwh for r in self.readings if r.direction is MeterDirection.IMPORT),
            Decimal(0),
        )

    @property
    def exported_kwh(self) -> Decimal | None:
        """Energia oddana; ``None`` bez fotowoltaiki."""
        if self.energy_settlement is None:
            return None
        return self.energy_settlement.exported_kwh

    @property
    def billed_energy_kwh(self) -> Decimal:
        """kWh energii czynnej, za które Faktura liczy cenę (po Opuście)."""
        return sum(
            (x.quantity for x in self.lines if x.component is LineComponent.ACTIVE_ENERGY),
            Decimal(0),
        )

    @property
    def discount_kwh(self) -> Decimal:
        """Opust: kWh odebrane z Magazynu energii."""
        if self.energy_settlement is None:
            return Decimal(0)
        return self.imported_kwh - self.billed_energy_kwh
