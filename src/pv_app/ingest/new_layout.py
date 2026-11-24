"""Głęboki moduł: surowe wiersze Faktury w nowym układzie (od XII 2025) → ``Invoice``.

Opis układu i jego wariantów: ``docs/invoice-structure.md``.
"""

import re
from collections.abc import Iterator
from dataclasses import dataclass
from decimal import Decimal

from pv_app.domain.invoice import (
    Amount,
    DateRange,
    DocumentKind,
    EnergySettlement,
    Forecast,
    Invoice,
    InvoiceHeader,
    InvoiceLine,
    InvoiceSection,
    Layout,
    MeterDirection,
    MeterReading,
    ReadingType,
    SettlementSummary,
    SettlementType,
    Source,
)
from pv_app.domain.invoice_lines import classify_line
from pv_app.ingest.polish_format import DATE, NUMBER, parse_date, parse_number
from pv_app.ingest.raw import RawDocument

_NUM = NUMBER

_SUMMARY_PAGE = re.compile(r"To jest Twoja\s*faktura")
_GREETING = re.compile(r"^Dzień dobry, to jest podsumowanie Twojej faktury")


class ParseError(Exception):
    """Faktury nie da się odczytać; komunikat po polsku trafia do użytkownika."""


def is_new_layout(document: RawDocument) -> bool:
    lines = [line for page in document.pages for line in page.lines]
    return any(_GREETING.match(line) for line in lines) and any(
        _SUMMARY_PAGE.search(line) for line in lines
    )


@dataclass(frozen=True)
class _Line:
    page: int
    text: str


class _Lines:
    def __init__(self, document: RawDocument, pages: set[int] | None = None) -> None:
        self._lines = [
            _Line(page.number, line.strip())
            for page in document.pages
            if pages is None or page.number in pages
            for line in page.lines
        ]

    def __iter__(self) -> Iterator[_Line]:
        return iter(self._lines)

    def find(self, pattern: str) -> tuple[re.Match[str], int] | None:
        regex = re.compile(pattern)
        for line in self._lines:
            match = regex.search(line.text)
            if match:
                return match, line.page
        return None

    def require(self, pattern: str, what: str) -> tuple[re.Match[str], int]:
        found = self.find(pattern)
        if found is None:
            raise ParseError(f"Nie znaleziono na Fakturze: {what}.")
        return found

    def after(self, pattern: str) -> str | None:
        """Wiersz następujący po pierwszym wierszu pasującym do wzorca."""
        regex = re.compile(pattern)
        for current, following in zip(self._lines, self._lines[1:], strict=False):
            if regex.search(current.text):
                return following.text
        return None


def parse_new_layout(document: RawDocument) -> tuple[Invoice, list[str]]:
    """Faktura i ostrzeżenia o rzeczach nierozpoznanych; ``ParseError``, gdy brakuje sekcji."""
    summary_page = _page_number(document, _SUMMARY_PAGE, "„To jest Twoja faktura”")
    greeting_page = _page_number(document, _GREETING, "„Dzień dobry, to jest podsumowanie”")
    all_lines = _Lines(document)
    summary_lines = _Lines(document, {summary_page})
    header = _header(all_lines, summary_lines, _Lines(document, {greeting_page}))
    warnings: list[str] = []
    invoice = Invoice(
        kind=DocumentKind.SETTLEMENT_INVOICE,
        layout=Layout.NEW,
        header=header,
        readings=_readings(all_lines, header.number),
        energy_settlement=_energy_settlement(document, all_lines, header.number),
        lines=_invoice_lines(all_lines, header.number, warnings),
        summary=_summary(all_lines, summary_lines, header.source),
        forecasts=_forecasts(all_lines, header.number),
    )
    return invoice, warnings


_METER = re.compile(
    r"^Licznik energii (?:elektrycznej \((?P<direction>pobór|oddanie)\)|czynnej)"
    r"(?:-(?P<number>\S+))?$"
)
_METER_NUMBER = re.compile(r"^nr (\S+)$")
_READING = re.compile(
    rf"^(?P<zone>[a-ząćęłńóśźż]+) (?P<date>{DATE}) "
    r"(?:\((?P<code>\w+)\)|(?P<word>Zdalny|Fizyczny|Odbiorcy|Szacunkowy)) (?P<rest>.+)$"
)
_M4 = r"\d{1,3}(?: \d{3})*,\d{4}"
_STATES_WITH_MULTIPLIER = re.compile(
    rf"^(?P<prev>{_M4}) (?P<curr>{_M4}) \d+ {_M4} {_M4} (?P<total>{_M4})$"
)
_STATES = re.compile(rf"^(?P<prev>{_M4}) (?P<curr>{_M4}) {_M4} {_M4} (?P<total>{_M4})$")
_QUANTITY_ONLY = re.compile(rf"^(?P<total>{_M4})$")
_READING_TYPES = {
    "z": ReadingType.REMOTE,
    "zdalny": ReadingType.REMOTE,
    "f": ReadingType.PHYSICAL,
    "fizyczny": ReadingType.PHYSICAL,
    "o": ReadingType.CUSTOMER,
    "odbiorcy": ReadingType.CUSTOMER,
    "s": ReadingType.ESTIMATED,
    "szacunkowy": ReadingType.ESTIMATED,
}


def _readings(all_lines: _Lines, invoice_number: str) -> tuple[MeterReading, ...]:
    with_multiplier = all_lines.find(r"\bMnożna\b") is not None
    states = _STATES_WITH_MULTIPLIER if with_multiplier else _STATES
    readings: list[MeterReading] = []
    meter: str | None = None
    direction = MeterDirection.IMPORT
    for line in all_lines:
        if header := _METER.match(line.text):
            direction = (
                MeterDirection.EXPORT if header["direction"] == "oddanie" else MeterDirection.IMPORT
            )
            meter = header["number"]
            continue
        if number := _METER_NUMBER.match(line.text):
            meter = number.group(1)
            continue
        row = _READING.match(line.text)
        if row is None:
            continue
        code = (row["code"] or row["word"]).lower()
        if code not in _READING_TYPES:
            raise ParseError(f"Nieznany Typ odczytu „{code}” (strona {line.page}).")
        values = states.match(row["rest"]) or _QUANTITY_ONLY.match(row["rest"])
        if values is None:
            raise ParseError(f"Nie udało się odczytać stanu licznika (strona {line.page}).")
        groups = values.groupdict()
        readings.append(
            MeterReading(
                meter_number=meter or "",
                direction=direction,
                zone=row["zone"],
                reading_date=parse_date(row["date"]),
                reading_type=_READING_TYPES[code],
                previous=parse_number(groups["prev"]) if groups.get("prev") else None,
                current=parse_number(groups["curr"]) if groups.get("curr") else None,
                quantity_kwh=parse_number(groups["total"]).normalize(),
                source=Source(invoice_number, line.page),
            )
        )
    if not readings:
        raise ParseError("Nie znaleziono na Fakturze: odczyty licznika.")
    return tuple(readings)


_MONEY = r"-?\d+(?: \d{3})*,\d{2}"
_LINE = re.compile(
    rf"^(?P<name>.+?) (?P<qty>{_NUM}) (?P<unit>kWh|mc|zł/mc) (?P<price>-?\d+,\d+) "
    rf"(?P<net>{_MONEY}) (?P<rate>\d+) (?P<vat>{_MONEY}) (?P<gross>{_MONEY})$"
)
_ZONE = re.compile(r"^[a-ząćęłńóśźż]+$")
_SECTIONS = {section.value: section for section in InvoiceSection}
_SECTION_END = re.compile(r"^Razem za (?:sprzedaż|dystrybucję) energii\b")
_SKIPPED_IN_SECTION = re.compile(r"^(?:Szczegóły rozliczenia|Nazwa Ilość Jednostka|\d+ ?/ ?\d+)")


def _invoice_lines(
    all_lines: _Lines, invoice_number: str, warnings: list[str]
) -> tuple[InvoiceLine, ...]:
    """Pozycje faktury z sekcji sprzedaży i dystrybucji; składnik może przejść na kolejną stronę."""
    result: list[InvoiceLine] = []
    section: InvoiceSection | None = None
    group: str | None = None
    sub_periods: dict[tuple[InvoiceSection, str, str | None], int] = {}
    for line in all_lines:
        text = line.text
        if text in _SECTIONS:
            section, group = _SECTIONS[text], None
            continue
        if section is None:
            continue
        if _SECTION_END.match(text):
            section = None
            continue
        if _SKIPPED_IN_SECTION.match(text):
            continue
        row = _LINE.match(text)
        if row is None:
            group = text
            continue
        if _ZONE.match(row["name"]):
            if group is None:
                raise ParseError(f"Pozycja faktury bez nazwy składnika (strona {line.page}).")
            name, zone = group, row["name"]
        else:
            name, zone = row["name"], None
        component = classify_line(name)
        if component is None:
            warnings.append(f"Nierozpoznana Pozycja faktury „{name}” (strona {line.page}).")
        key = (section, name, zone)
        sub_periods[key] = sub_periods.get(key, 0) + 1
        result.append(
            InvoiceLine(
                section=section,
                name=name,
                component=component,
                zone=zone,
                sub_period=sub_periods[key],
                quantity=parse_number(row["qty"]),
                unit="mc" if row["unit"] == "zł/mc" else row["unit"],
                unit_price_net=parse_number(row["price"]),
                net=parse_number(row["net"]),
                vat_rate=parse_number(row["rate"]),
                vat=parse_number(row["vat"]),
                gross=parse_number(row["gross"]),
                source=Source(invoice_number, line.page),
            )
        )
    if not result:
        raise ParseError("Nie znaleziono na Fakturze: Pozycje faktury.")
    return tuple(result)


def _forecasts(all_lines: _Lines, invoice_number: str) -> tuple[Forecast, ...]:
    """Harmonogram Prognoz: wiersz z numerem blankietu, wiersz kwot, wiersz okresu."""
    with_export = all_lines.find(r"^Pobór Oddanie$") is not None
    kwh = r"(?P<kwh>-?\d+) (?P<export>-?\d+)" if with_export else r"(?P<kwh>-?\d+(?: \d{3})*)"
    values = re.compile(
        rf"^{kwh} (?P<net>{_MONEY}) (?P<vat>{_MONEY}) (?P<gross>{_MONEY}) "
        rf"(?P<discount>{_MONEY}) (?P<adj>{_MONEY}) (?P<due>{_MONEY}) (?P<date>{DATE})$"
    )
    number = re.compile(rf"^{re.escape(invoice_number)}/\d+$")
    period = re.compile(rf"^({DATE}) - ({DATE})$")
    lines = list(all_lines)
    result = []
    for first, second, third in zip(lines, lines[1:], lines[2:], strict=False):
        if not number.match(first.text):
            continue
        row, dates = values.match(second.text), period.match(third.text)
        if row is None or dates is None:
            raise ParseError(f"Nie udało się odczytać Prognozy {first.text} (strona {first.page}).")
        result.append(
            Forecast(
                number=first.text,
                period=DateRange(parse_date(dates.group(1)), parse_date(dates.group(2))),
                import_kwh=parse_number(row["kwh"]),
                export_kwh=parse_number(row["export"]) if with_export else None,
                net=parse_number(row["net"]),
                vat=parse_number(row["vat"]),
                gross=parse_number(row["gross"]),
                discount=parse_number(row["discount"]),
                balance_adjustment=parse_number(row["adj"]),
                amount_due=parse_number(row["due"]),
                due_date=parse_date(row["date"]),
                source=Source(invoice_number, first.page),
            )
        )
    return tuple(result)


def _energy_settlement(
    document: RawDocument, all_lines: _Lines, invoice_number: str
) -> EnergySettlement | None:
    """Rozliczenie OZE: tabela (wiersze ``N. Energia …`` sumowane po strefach) i zdania pod nią.

    Wszystkie wartości muszą leżeć na stronie tabeli, żeby jej numer był ich źródłem.
    """
    if all_lines.find(r"^Rozliczenie OZE$") is None:
        return None
    rows = [
        (match, line.page)
        for line in all_lines
        if (
            match := re.match(
                r"^\d+\. Energia(?: elektryczna)? (\d+) (\d+) (\d+) (\d+,\d+) (\d+)$", line.text
            )
        )
    ]
    if not rows:
        raise ParseError("Nie udało się odczytać tabeli Rozliczenie OZE.")
    page = rows[0][1]
    table_page = _Lines(document, {page})

    def total(column: int) -> Decimal:
        return sum((parse_number(m.group(column)) for m, _ in rows), Decimal(0))

    remaining, _ = table_page.require(
        rf"z bieżącego rozliczenia pozostało ({_NUM}) kWh",
        "energia pozostała z bieżącego rozliczenia",
    )
    seller, _ = table_page.require(
        rf"do dyspozycji Sprzedawcy pozostaje ({_NUM}) kWh", "Udział Sprzedawcy"
    )
    end, _ = table_page.require(
        rf"do wykorzystania pozostaje łączna ilość energii elektrycznej ({_NUM}) kWh",
        "Magazyn energii na koniec okresu",
    )
    return EnergySettlement(
        imported_kwh=total(1),
        exported_kwh=total(2),
        # Energia z magazynu jest wspólna dla stref; bierzemy ją z pierwszego wiersza.
        store_start_kwh=parse_number(rows[0][0].group(3)),
        discount_coefficient=parse_number(rows[0][0].group(4)),
        exported_after_coefficient_kwh=total(5),
        remaining_from_this_period_kwh=parse_number(remaining.group(1)),
        seller_share_kwh=parse_number(seller.group(1)),
        store_end_kwh=parse_number(end.group(1)),
        source=Source(invoice_number, page),
    )


def _page_number(document: RawDocument, marker: re.Pattern[str], name: str) -> int:
    for page in document.pages:
        if any(marker.search(line) for line in page.lines):
            return page.number
    raise ParseError(f"Nie znaleziono strony {name}.")


def _header(all_lines: _Lines, summary: _Lines, greeting: _Lines) -> InvoiceHeader:
    match, summary_page = summary.require(
        rf"^({DATE}) (\S+/\S+) ({DATE}) - ({DATE})$", "numer, data wystawienia i okres"
    )
    number = match.group(2)
    ppe, greeting_page = greeting.require(r"^Punkt Poboru Energii: (\d+) \| (.+)$", "numer PPE")
    address = greeting.after(r"^Punkt Poboru Energii: ")
    if address is None:
        raise ParseError("Nie znaleziono na Fakturze: adres PPE.")
    tariff, _ = summary.require(
        r"(?:^|\s)([GCB]\d{2}\w?) (\d+(?:[.,]\d+)?) kW\b", "grupa taryfowa i moc umowna"
    )
    net_metering = all_lines.find(r"\bNet[- ]?met+ering\b") is not None or (
        all_lines.find(r"^Rozliczenie OZE$") is not None
    )
    frequency = greeting.find(r"^Co (\d+) miesi")
    return InvoiceHeader(
        number=number,
        issue_date=parse_date(match.group(1)),
        billing_period=DateRange(parse_date(match.group(3)), parse_date(match.group(4))),
        ppe_number=ppe.group(1),
        site_name=ppe.group(2).strip(),
        address=address,
        tariff_group=tariff.group(1),
        contracted_power_kw=Decimal(tariff.group(2).replace(",", ".")).normalize(),
        settlement_type=SettlementType.NET_METERING if net_metering else SettlementType.STANDARD,
        billing_frequency_months=int(frequency[0].group(1)) if frequency else None,
        source=Source(number, summary_page),
        site_source=Source(number, greeting_page),
    )


def _amount(match: re.Match[str]) -> Amount:
    return Amount(
        net=parse_number(match["net"]),
        vat=parse_number(match["vat"]),
        gross=parse_number(match["gross"]),
    )


_AMOUNT = rf"(?P<net>{_NUM}) (?:\d+|x) (?P<vat>{_NUM}) (?P<gross>{_NUM})$"


def _summary(all_lines: _Lines, summary: _Lines, source: Source) -> SettlementSummary:
    sales, _ = summary.require(
        rf"^1\. Sprzedaży? energii elektrycznej {_NUM} {_AMOUNT}", "sprzedaż energii"
    )
    distribution, _ = summary.require(
        r"^2\. (?:Dystrybucja energii elektrycznej|Świadczonych usług dystrybucji)"
        rf" {_NUM} {_AMOUNT}",
        "dystrybucja energii",
    )
    result, _ = summary.require(rf"^3\. Wynik rozliczenia \([^)]*\) {_AMOUNT}", "Wynik rozliczenia")
    forecast = summary.find(
        rf"^\d\. (?:Wartość prognozy|Prognoza) z poprzedniej faktury (?:{_NUM} )?{_AMOUNT}"
    )
    payments = summary.find(rf"^\d\. Wpłaty dodatkowe ({_NUM})$")
    due, _ = summary.require(
        r"^(Do zapłaty|Razem|NIEDOPŁATA|NADPŁATA) \([^)]*\) (.+)$", "kwota do zapłaty"
    )
    due_amount = parse_number(re.findall(_NUM, due.group(2))[-1])
    if due.group(1) == "NADPŁATA":
        due_amount = -abs(due_amount)
    balance = summary.find(
        rf"Na Państwa koncie pozostała (NADPŁATA|NIEDOPŁATA) w kwocie ({_NUM}) zł"
    )
    excise = summary.find(rf"^Od ({_NUM}) kWh sprzedawca odprowadzi akcyzę w wysokości ({_NUM}) zł")
    last_year = all_lines.find(
        r"(?:analogicznym okresie poprzedniego roku wyniosło|rok temu w analogicznym okresie)"
        rf" ({_NUM}) kWh"
    )
    account_balance = None
    if balance:
        value = parse_number(balance[0].group(2))
        account_balance = value if balance[0].group(1) == "NADPŁATA" else -value
    return SettlementSummary(
        sales=_amount(sales),
        distribution=_amount(distribution),
        result=_amount(result),
        previous_forecast=_amount(forecast[0]) if forecast else None,
        additional_payments=parse_number(payments[0].group(1)) if payments else None,
        amount_due=due_amount,
        account_balance=account_balance,
        excise_kwh=parse_number(excise[0].group(1)) if excise else None,
        excise_amount=parse_number(excise[0].group(2)) if excise else None,
        same_period_last_year_kwh=parse_number(last_year[0].group(1)) if last_year else None,
        same_period_last_year_source=(
            Source(source.invoice_number, last_year[1]) if last_year else None
        ),
        source=source,
    )
