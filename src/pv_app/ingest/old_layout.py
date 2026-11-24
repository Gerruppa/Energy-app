"""Głęboki moduł: komórki wierszy Faktury w starym układzie (do 2025) → ``Invoice``.

Ten sam układ mają Faktury korygujące (także w 2026): części „policzono” i „należało
policzyć” powtarzają podsumowanie i załącznik, a do obliczeń liczy się ta druga.

Tabele czytamy z komórek, które adapter wydziela po położeniu znaków na stronie: w samym
tekście odstęp tysięcy (``1 722``) wygląda jak granica kolumn (``1`` i ``722``). Opis układu
i jego wariantów: ``docs/invoice-structure.md``.
"""

import re
from collections.abc import Iterator
from dataclasses import dataclass
from decimal import Decimal

from pv_app.domain.invoice import (
    Amount,
    Correction,
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
from pv_app.ingest.parse_error import ParseError
from pv_app.ingest.polish_format import DATE, NUMBER, parse_date, parse_number
from pv_app.ingest.raw import RawDocument, Row

_TITLE = re.compile(r"^FAKTURA VAT (?:ROZLICZENIOWA )?NR (\S+) - ")
_CORRECTING_TITLE = re.compile(r"^FAKTURA VAT KOREKTA NR (\S+) - ")
_ATTACHMENT = r"^ZAŁĄCZNIK DO FAKTURY VAT (?:KOREKTA )?NR "
_CHARGED = "POLICZONO:"
_SHOULD_HAVE_CHARGED = "NALEŻAŁO POLICZYĆ:"
_NUMBER_CELL = re.compile(rf"^{NUMBER}$")
_ZONE = re.compile(r"^[a-ząćęłńóśźż]+$")

MONEY_TOLERANCE = Decimal("0.01")
"""Zaokrąglenie groszowe przy sprawdzaniu kolumn wiersza Prognozy."""


def is_old_layout(document: RawDocument) -> bool:
    return any(_TITLE.match(line) for page in document.pages for line in page.lines)


def is_correcting_invoice(document: RawDocument) -> bool:
    return any(_CORRECTING_TITLE.match(line) for page in document.pages for line in page.lines)


@dataclass(frozen=True)
class _PageRow:
    page: int
    cells: Row

    @property
    def text(self) -> str:
        return " ".join(self.cells)


class _PageRows:
    def __init__(self, rows: list[_PageRow]) -> None:
        self._rows = rows

    @classmethod
    def of(cls, document: RawDocument) -> "_PageRows":
        return cls([_PageRow(page.number, cells) for page in document.pages for cells in page.rows])

    def __iter__(self) -> Iterator[_PageRow]:
        return iter(self._rows)

    def on_page(self, page: int) -> "_PageRows":
        return _PageRows([row for row in self._rows if row.page == page])

    def find(self, pattern: str) -> tuple[re.Match[str], _PageRow] | None:
        regex = re.compile(pattern)
        for row in self._rows:
            if match := regex.search(row.text):
                return match, row
        return None

    def require(self, pattern: str, what: str) -> tuple[re.Match[str], _PageRow]:
        found = self.find(pattern)
        if found is None:
            raise ParseError(f"Nie znaleziono na Fakturze: {what}.")
        return found

    def labelled(self, label: str, what: str) -> tuple[str, ...]:
        """Komórki po komórce z etykietą (``Nazwa obiektu:``), także gdy wiersz ma dwie kolumny."""
        regex = re.compile(label)
        for row in self._rows:
            for index, cell in enumerate(row.cells):
                if regex.fullmatch(cell):
                    return row.cells[index + 1 :]
        raise ParseError(f"Nie znaleziono na Fakturze: {what}.")


def parse_old_layout(document: RawDocument) -> tuple[Invoice, list[str]]:
    """Faktura i ostrzeżenia o rzeczach nierozpoznanych; ``ParseError``, gdy brakuje sekcji."""
    rows = _cells(document)
    header = _header(rows, _TITLE)
    return _invoice(DocumentKind.SETTLEMENT_INVOICE, header, rows, None)


def parse_correcting_invoice(document: RawDocument) -> tuple[Invoice, list[str]]:
    """Faktura korygująca: nagłówek z całego dokumentu, wartości z części „należało policzyć”.

    Data wystawienia stoi pod kwotą do zwrotu (zapłaty) korekty, zwykle na drugiej stronie.
    """
    rows = _cells(document)
    charged, should_have_charged = _parts(rows)
    settled, settled_row = rows.require(
        rf"^Do (zwrotu|zapłaty):? ({NUMBER}) zł$", "kwota do zwrotu lub zapłaty korekty"
    )
    header = _header(rows, _CORRECTING_TITLE, issue_date_page=settled_row.page)
    title_page = rows.on_page(header.source.page)
    corrected, _ = title_page.require(
        rf"^DO FAKTURY VAT NR (\S+) z dnia ({DATE})$", "numer korygowanej Faktury"
    )
    difference = parse_number(settled.group(2))
    charged_page = charged.on_page(header.source.page)
    correction = Correction(
        corrected_invoice_number=corrected.group(1),
        corrected_invoice_issue_date=parse_date(corrected.group(2)),
        reason=_reason(title_page),
        charged_result=_summed_amount(charged_page, r"Wynik rozliczenia \(.*\)", "Wynik"),
        charged_amount_due=_amount_due(charged_page),
        difference=-difference if settled.group(1) == "zwrotu" else difference,
        source=header.source,
        difference_source=Source(header.number, settled_row.page),
    )
    return _invoice(DocumentKind.CORRECTING_INVOICE, header, should_have_charged, correction)


def _cells(document: RawDocument) -> _PageRows:
    if not any(page.rows for page in document.pages):
        raise ParseError("Brak komórek tabel: Fakturę w starym układzie trzeba wgrać jako PDF.")
    return _PageRows.of(document)


def _invoice(
    kind: DocumentKind, header: InvoiceHeader, rows: _PageRows, correction: Correction | None
) -> tuple[Invoice, list[str]]:
    """Faktura z wierszy wartości (dla Faktury korygującej: część „należało policzyć”)."""
    warnings: list[str] = []
    invoice = Invoice(
        kind=kind,
        layout=Layout.OLD,
        header=header,
        readings=_readings(rows, header.number),
        energy_settlement=_energy_settlement(rows, header.number),
        lines=_invoice_lines(rows, header.number, warnings),
        summary=_summary(rows, header.source),
        forecasts=_forecasts(rows, header.number),
        correction=correction,
    )
    return invoice, warnings


def _parts(rows: _PageRows) -> tuple[_PageRows, _PageRows]:
    """Wiersze części „policzono” i „należało policzyć”; wiersze przed pierwszą z nich
    (tytuł, okres, przyczyna) należą do obu."""
    charged: list[_PageRow] = []
    should_have_charged: list[_PageRow] = []
    current: list[_PageRow] | None = None
    for row in rows:
        if row.text == _CHARGED:
            current = charged
        elif row.text == _SHOULD_HAVE_CHARGED:
            current = should_have_charged
        elif current is None:
            charged.append(row)
            should_have_charged.append(row)
        else:
            current.append(row)
    if current is None:
        raise ParseError("Nie znaleziono na Fakturze korygującej części „należało policzyć”.")
    return _PageRows(charged), _PageRows(should_have_charged)


def _reason(title_page: _PageRows) -> str:
    """Przyczyna korekty: zdanie od ``Przyczyna korekty:`` do części „policzono”."""
    parts: list[str] = []
    for row in title_page:
        if parts and row.text == _CHARGED:
            break
        if parts:
            parts.append(row.text)
        elif match := re.match(r"^Przyczyna korekty: (.+)$", row.text):
            parts.append(match.group(1))
    if not parts:
        raise ParseError("Nie znaleziono na Fakturze: przyczyna korekty.")
    return " ".join(parts)


def _header(
    rows: _PageRows, title_pattern: re.Pattern[str], issue_date_page: int | None = None
) -> InvoiceHeader:
    title, title_row = rows.require(title_pattern.pattern, "numer Faktury")
    number = title.group(1)
    invoice_page = rows.on_page(title_row.page)
    period, _ = invoice_page.require(
        rf"^[Zz]a okres od ({DATE}) do ({DATE})$", "Okres rozliczeniowy"
    )
    issued_on = issue_date_page or title_row.page
    issued, _ = rows.on_page(issued_on).require(
        rf"^Data wystawienia:? ({DATE})$", "data wystawienia"
    )
    _, attachment_row = rows.require(_ATTACHMENT, "załącznik do Faktury")
    attachment = rows.on_page(attachment_row.page)
    ppe = [c for c in attachment.labelled(r"Nr punktu poboru:", "numer PPE") if c != "PPE"]
    power = re.match(r"(\d+(?:[.,]\d+)?) kW$", attachment.labelled(r"Moc umowna:", "moc umowna")[0])
    if not ppe or not re.fullmatch(r"\d+", ppe[0]) or power is None:
        raise ParseError(
            f"Nie udało się odczytać numeru PPE i mocy umownej (strona {attachment_row.page})."
        )
    return InvoiceHeader(
        number=number,
        issue_date=parse_date(issued.group(1)),
        billing_period=DateRange(parse_date(period.group(1)), parse_date(period.group(2))),
        ppe_number=ppe[0],
        site_name=attachment.labelled(r"Nazwa obiektu:", "nazwa obiektu")[0],
        address=attachment.labelled(r"Adres punktu poboru:", "adres PPE")[0],
        tariff_group=attachment.labelled(r"Grupa taryfowa:?", "grupa taryfowa")[0],
        contracted_power_kw=Decimal(power.group(1).replace(",", ".")).normalize(),
        settlement_type=(
            SettlementType.NET_METERING
            if rows.find(r"^Rozliczenie energii elektrycznej wprowadzonej") is not None
            else SettlementType.STANDARD
        ),
        # Częstotliwość („Co 6 miesięcy”) stoi tylko na stronie podsumowania z 2025, a nagłówek
        # nie ma dla niej własnego Source (CODING_STANDARDS.md, *Źródło każdej wartości*).
        billing_frequency_months=None,
        source=Source(number, title_row.page),
        site_source=Source(number, attachment_row.page),
        issue_date_source=(Source(number, issued_on) if issued_on != title_row.page else None),
    )


_METER = re.compile(r"^Licznik energii (?:elektrycznej \((pobór|oddanie)\)|czynnej)$")
_READING_DATE = re.compile(rf"^({DATE}) \(([A-Z])\)$")
_READING_TYPES = {
    "Z": ReadingType.REMOTE,
    "F": ReadingType.PHYSICAL,
    "O": ReadingType.CUSTOMER,
    "S": ReadingType.ESTIMATED,
}


def _readings(rows: _PageRows, invoice_number: str) -> tuple[MeterReading, ...]:
    """Odczyty licznika; z kolumną ``Mnożna`` stany bieżący i poprzedni, bez niej sama ilość."""
    with_states = rows.find(r"\bMnożna\b") is not None
    readings: list[MeterReading] = []
    meter, direction = "", MeterDirection.IMPORT
    for row in rows:
        if header := _METER.match(row.text):
            direction = MeterDirection.EXPORT if header[1] == "oddanie" else MeterDirection.IMPORT
            continue
        if number := re.match(r"^nr (\S+)$", row.text):
            meter = number[1]
            continue
        if len(row.cells) < 3 or not _ZONE.match(row.cells[0]):
            continue
        date_type = _READING_DATE.match(row.cells[1])
        if date_type is None:
            continue
        if date_type[2] not in _READING_TYPES:
            raise ParseError(f"Nieznany Typ odczytu „{date_type[2]}” (strona {row.page}).")
        values = row.cells[2:]
        # Mnożna: bieżący, poprzedni, mnożna, ilość, straty, razem.
        if len(values) != (6 if with_states else 1) or not all(map(_NUMBER_CELL.match, values)):
            raise ParseError(f"Nie udało się odczytać stanu licznika (strona {row.page}).")
        readings.append(
            MeterReading(
                meter_number=meter,
                direction=direction,
                zone=row.cells[0],
                reading_date=parse_date(date_type[1]),
                reading_type=_READING_TYPES[date_type[2]],
                previous=parse_number(values[1]) if with_states else None,
                current=parse_number(values[0]) if with_states else None,
                quantity_kwh=parse_number(values[-1]).normalize(),
                source=Source(invoice_number, row.page),
            )
        )
    if not readings:
        raise ParseError("Nie znaleziono na Fakturze: odczyty licznika.")
    return tuple(readings)


def _energy_settlement(rows: _PageRows, invoice_number: str) -> EnergySettlement | None:
    """Rozliczenie OZE: wiersze stref (pobrana, wprowadzona, magazyn, współczynnik, po
    współczynniku) i zdania pod tabelą, wszystko ze strony tabeli."""
    found = rows.find(r"^Rozliczenie energii elektrycznej wprowadzonej")
    if found is None:
        return None
    page = found[1].page
    table = rows.on_page(page)
    zones = [values for row in table if (values := _zone_values(row.cells)) is not None]
    if not zones:
        raise ParseError(f"Nie udało się odczytać tabeli Rozliczenie OZE (strona {page}).")

    def total(column: int) -> Decimal:
        return sum((parse_number(zone[column]) for zone in zones), Decimal(0))

    remaining, _ = table.require(
        rf"z bieżącego rozliczenia pozostało ({NUMBER}) kWh",
        "energia pozostała z bieżącego rozliczenia",
    )
    seller, _ = table.require(
        rf"(?:Sprzedawca ma do dyspozycji|do dyspozycji Sprzedawcy pozostaje) ({NUMBER}) kWh",
        "Udział Sprzedawcy",
    )
    end, _ = table.require(
        rf"pozostaje łączna ilość energii elektrycznej ({NUMBER}) kWh",
        "Magazyn energii na koniec okresu",
    )
    return EnergySettlement(
        imported_kwh=total(0),
        exported_kwh=total(1),
        # Energia z magazynu jest wspólna dla stref; bierzemy ją z pierwszego wiersza.
        store_start_kwh=parse_number(zones[0][2]),
        discount_coefficient=parse_number(zones[0][3]),
        exported_after_coefficient_kwh=total(4),
        remaining_from_this_period_kwh=parse_number(remaining.group(1)),
        seller_share_kwh=parse_number(seller.group(1)),
        store_end_kwh=parse_number(end.group(1)),
        source=Source(invoice_number, page),
    )


def _zone_values(cells: Row) -> Row | None:
    """Liczby wiersza strefy w tabeli Rozliczenie OZE: ``całodobowa | 5 liczb`` albo
    (Faktury za 2023) ``1. | Energia elektryczna całodobowa | 5 liczb``."""
    if len(cells) == 6 and _ZONE.match(cells[0]):
        values = cells[1:]
    elif (
        len(cells) == 7
        and re.fullmatch(r"\d+\.", cells[0])
        and re.fullmatch(r"Energia elektryczna [a-ząćęłńóśźż]+", cells[1])
    ):
        values = cells[2:]
    else:
        return None
    return values if all(_NUMBER_CELL.match(cell) for cell in values) else None


_SECTION_STARTS = (
    (
        re.compile(r"^Rozliczenie [Ss]przedaży [Ee]nergii [Ee]lektrycznej za okres"),
        InvoiceSection.SALES,
    ),
    (re.compile(r"^Rozliczenie opłat za usługi dystrybucji za okres"), InvoiceSection.DISTRIBUTION),
)
_SECTION_END = re.compile(r"^Ogółem wartość ?:")
_TABLE_HEADER = re.compile(
    r"^(?:Stawka|(?:Opis|Jednostka|[Ii]lość|Strefa|miary)\b.*|Jedn\. .*|(?:VAT )?\( ?% ?\)"
    r"|Strona \d+ z \d+|\d+ ?/ ?\d+(?: str\.)?)$"
)
_UNITS = {"kWh": "kWh", "mc": "mc", "zł/mc": "mc"}


@dataclass(frozen=True)
class _LineNumbers:
    """Liczby wiersza Pozycji faktury, od ilości do brutto (bez współczynnika OZE)."""

    unit: str
    quantity: str
    price: str
    net: str
    rate: str
    vat: str
    gross: str


def _item(cells: Row) -> tuple[Row, _LineNumbers] | None:
    """Komórki nazwy i liczby wiersza Pozycji faktury; ``None`` dla wiersza z samym tekstem.

    Po jednostce idą: ilość, [współczynnik — tylko opłata OZE i kogeneracyjna], cena, netto,
    stawka VAT, VAT, brutto. Komórki z położenia na stronie, więc liczba komórek mówi,
    czy jest współczynnik.
    """
    for index, cell in enumerate(cells):
        if cell in _UNITS:
            numbers = cells[index + 1 :]
            if len(numbers) not in (6, 7) or not all(map(_NUMBER_CELL.match, numbers)):
                return None
            if len(numbers) == 7:
                numbers = numbers[:1] + numbers[2:]
            return cells[:index], _LineNumbers(_UNITS[cell], *numbers)
    return None


def _invoice_lines(
    rows: _PageRows, invoice_number: str, warnings: list[str]
) -> tuple[InvoiceLine, ...]:
    """Pozycje faktury z tabel sprzedaży i dystrybucji.

    Nazwa składnika stoi w wierszu przed wierszami stref albo w komórce przed jednostką.
    Nazwa zawinięta w dwa wiersze otacza wiersz z liczbami (``Składnik stały stawki`` /
    liczby / ``sieciowej``); nagłówek grupy bywa zawinięty nad wierszami stref.
    """
    result: list[InvoiceLine] = []
    sub_periods: dict[tuple[InvoiceSection, str, str | None], int] = {}

    def add(
        section: InvoiceSection, name: str, zone: str | None, values: _LineNumbers, page: int
    ) -> None:
        component = classify_line(name)
        if component is None:
            warnings.append(f"Nierozpoznana Pozycja faktury „{name}” (strona {page}).")
        key = (section, name, zone)
        sub_periods[key] = sub_periods.get(key, 0) + 1
        result.append(
            InvoiceLine(
                section=section,
                name=name,
                component=component,
                zone=zone,
                sub_period=sub_periods[key],
                quantity=parse_number(values.quantity),
                unit=values.unit,
                unit_price_net=parse_number(values.price),
                net=parse_number(values.net),
                vat_rate=parse_number(values.rate),
                vat=parse_number(values.vat),
                gross=parse_number(values.gross),
                source=Source(invoice_number, page),
            )
        )

    section: InvoiceSection | None = None
    group: list[str] = []
    after_item = False
    unnamed: tuple[_LineNumbers, int] | None = None
    for row in rows:
        text = row.text
        if section is None:
            section = next((s for regex, s in _SECTION_STARTS if regex.match(text)), None)
            group, after_item = [], False
            continue
        if _SECTION_END.match(text):
            if unnamed is not None:
                raise ParseError(f"Pozycja faktury bez nazwy składnika (strona {unnamed[1]}).")
            section = None
            continue
        if _TABLE_HEADER.match(text):
            continue
        item = _item(row.cells)
        if item is None:
            if unnamed is not None:
                add(section, " ".join([*group, text]), None, unnamed[0], unnamed[1])
                unnamed, group, after_item = None, [], True
            elif after_item:
                group, after_item = [text], False
            else:
                group.append(text)
            continue
        if unnamed is not None:
            raise ParseError(f"Pozycja faktury bez nazwy składnika (strona {unnamed[1]}).")
        name_cells, values = item
        if not name_cells:
            unnamed = (values, row.page)
            continue
        if _ZONE.match(name_cells[0]):
            if not group:
                raise ParseError(f"Pozycja faktury bez nazwy składnika (strona {row.page}).")
            add(section, " ".join(group), name_cells[0], values, row.page)
        else:
            add(section, " ".join(name_cells), None, values, row.page)
        after_item = True
    if not result:
        raise ParseError("Nie znaleziono na Fakturze: Pozycje faktury.")
    return tuple(result)


def _summary_values(page: _PageRows, label: str) -> list[Row]:
    """Liczby wierszy podsumowania ``N. | etykieta | liczby`` o tej etykiecie."""
    return [
        row.cells[2:]
        for row in page
        if len(row.cells) > 2
        and re.fullmatch(r"\d\.", row.cells[0])
        and re.fullmatch(label, row.cells[1])
    ]


def _summed_amount(page: _PageRows, label: str, what: str) -> Amount:
    """Kwota z wierszy podsumowania; przy dwóch stawkach VAT (5% i 23%) każda ma swój
    wiersz z tą samą etykietą, więc wiersze się sumują."""
    found = _summary_values(page, label)
    if not found or any(len(values) < 4 for values in found):
        raise ParseError(f"Nie znaleziono na Fakturze: {what}.")

    # netto, stawka VAT (liczba albo x), VAT, brutto [, kWh]
    def total(column: int) -> Decimal:
        return sum((parse_number(values[column]) for values in found), Decimal(0))

    return Amount(net=total(0), vat=total(2), gross=total(3))


def _amount_due(page: _PageRows) -> Decimal:
    """``Do zapłaty ( 3 + 4 )`` ze znakiem; w części „policzono” Faktury korygującej
    etykieta bywa bez wzoru."""
    due = _summary_values(page, r"Do zapłaty(?: \(.*\))?")
    if len(due) != 1:
        raise ParseError("Nie znaleziono na Fakturze: kwota do zapłaty.")
    return parse_number(due[0][-1])


def _summary(rows: _PageRows, source: Source) -> SettlementSummary:
    """Podsumowanie ze strony z numerem Faktury: wiersze ``N. | etykieta | liczby``."""
    page = rows.on_page(source.page)

    def amount(label: str, what: str) -> Amount:
        return _summed_amount(page, label, what)

    forecast = _summary_values(page, r"Wartość prognozy z poprzedniej faktury")
    payments = _summary_values(page, r"Wpłaty dodatkowe")
    discount = _summary_values(page, r"Bonifikata")
    excise = page.find(
        rf"^Od (?:[Ii]lości )?({NUMBER}) kWh (?:energii elektrycznej naliczono|Sprzedawca "
        rf"odprowadził) akcyzę w kwocie ({NUMBER}) zł"
    )
    last_year = rows.find(rf"analogicznym okresie poprzedniego roku wyniosło ({NUMBER}) kWh")
    return SettlementSummary(
        sales=amount(r"Sprzedaży energii elektrycznej", "sprzedaż energii"),
        distribution=amount(r"Świadczonych usług dystrybucji", "dystrybucja energii"),
        result=amount(r"Wynik rozliczenia \(.*\)", "Wynik rozliczenia"),
        previous_forecast=(
            amount(r"Wartość prognozy z poprzedniej faktury", "Prognoza") if forecast else None
        ),
        additional_payments=parse_number(payments[0][0]) if payments else None,
        amount_due=_amount_due(page),
        account_balance=None,
        excise_kwh=parse_number(excise[0].group(1)) if excise else None,
        excise_amount=parse_number(excise[0].group(2)) if excise else None,
        same_period_last_year_kwh=parse_number(last_year[0].group(1)) if last_year else None,
        same_period_last_year_source=(
            Source(source.invoice_number, last_year[1].page) if last_year else None
        ),
        source=source,
        discount=amount(r"Bonifikata", "Bonifikata") if discount else None,
    )


_VALUE = rf"(?:{NUMBER}|x)"
_VALUE_WITH_DATE = re.compile(rf"^(?:({_VALUE}) ({DATE})|({DATE}) ({_VALUE}))$")


def _tokens(cells: Row) -> list[str]:
    """Wartości z komórek: liczba, ``x`` (kolumna stawki VAT) albo data.

    Komórka bywa sklejona z kwoty i terminu płatności (``839,95 13/10/2025``); rozdzielamy
    tylko taką, bo w komórce z samymi liczbami odstęp tysięcy (``1 100``) wygląda jak granica
    kolumn. Pusta lista, gdy któraś komórka nie pasuje.
    """
    tokens: list[str] = []
    for cell in cells:
        if re.fullmatch(rf"{_VALUE}|{DATE}", cell):
            tokens.append(cell)
        elif pair := _VALUE_WITH_DATE.match(cell):
            tokens.extend(group for group in pair.groups() if group is not None)
        else:
            return []
    return tokens


def _forecasts(rows: _PageRows, invoice_number: str) -> tuple[Forecast, ...]:
    """Harmonogram Prognoz: numer blankietu, okres, kWh (przy net-meteringu pobór i oddanie)
    i kwoty. Kolejność kolumn kwot różni się między Fakturami; wyznacza ją kolumna stawki VAT
    (``x``) i kolumna terminu (data), a sumy netto + VAT = brutto i brutto + nadpłata/niedopłata
    = do zapłaty to potwierdzają."""
    with_export = rows.find(r"^Pobór Oddanie\b") is not None
    kwh_columns = 2 if with_export else 1
    number = re.compile(rf"^{re.escape(invoice_number)}/\d+$")
    period = re.compile(rf"^({DATE}) - ({DATE})$")
    result = []
    for row in rows:
        if len(row.cells) < 3 or not number.match(row.cells[0]):
            continue
        dates = period.match(row.cells[1])
        tokens = _tokens(row.cells[2:])
        error = ParseError(f"Nie udało się odczytać Prognozy {row.cells[0]} (strona {row.page}).")
        if dates is None or len(tokens) != kwh_columns + 8:
            raise error
        kwh, money = tokens[:kwh_columns], tokens[kwh_columns:]
        due_dates = [t for t in money if re.fullmatch(DATE, t)]
        if len(due_dates) != 1 or "x" not in money[1:3]:
            raise error
        if money[1] == "x":  # netto, x, VAT, brutto
            net, vat, gross = money[0], money[2], money[3]
        else:  # netto, brutto, x, VAT
            net, gross, vat = money[0], money[1], money[3]
        discount, adjustment, due = [t for t in money[4:] if t != due_dates[0]]
        net_amount, vat_amount, gross_amount = map(parse_number, (net, vat, gross))
        adjustment_amount, due_amount = parse_number(adjustment), parse_number(due)
        # Rabat jest częścią brutto („W tym rabat”), więc nie wchodzi do sumy do zapłaty;
        # w danych z References/ rabat jest zawsze 0,00.
        if abs(net_amount + vat_amount - gross_amount) > MONEY_TOLERANCE or (
            abs(gross_amount + adjustment_amount - due_amount) > MONEY_TOLERANCE
        ):
            raise error
        result.append(
            Forecast(
                number=row.cells[0],
                period=DateRange(parse_date(dates.group(1)), parse_date(dates.group(2))),
                import_kwh=parse_number(kwh[0]),
                export_kwh=parse_number(kwh[1]) if with_export else None,
                net=net_amount,
                vat=vat_amount,
                gross=gross_amount,
                discount=parse_number(discount),
                balance_adjustment=adjustment_amount,
                amount_due=due_amount,
                due_date=parse_date(due_dates[0]),
                source=Source(invoice_number, row.page),
            )
        )
    return tuple(result)
