"""Widok jednej Faktury = „Faktura po ludzku” do druku (Ctrl+P w przeglądarce).

Strona nie jest zakładką: powłoka pokazuje ją zamiast zakładek, gdy adres ma
``&faktura=…`` (``features/navigation.py``). Styl druku chowa nawigację i przyciski;
pełna lista Pozycji faktury drukuje się na 2. stronie tylko wtedy, gdy jest rozwinięta.
"""

from decimal import Decimal

import streamlit as st

from pv_app.domain.invoice import Amount, DateRange, Invoice
from pv_app.features import formatting as fmt
from pv_app.features.base import FeatureContext
from pv_app.features.invoice_view.analysis import (
    CostGroup,
    CostGroupTotal,
    InvoiceSheet,
    YearEarlier,
    cost_group,
    invoice_sheet,
)
from pv_app.features.navigation import close_invoice, open_invoice
from pv_app.storage.archive import FileArchive

PRINT_STYLE = """
<style>
@media print {
  @page { size: A4; margin: 10mm 12mm; }
  html { font-size: 10px; }
  [data-testid="stSidebar"], [data-testid="stHeader"], [data-testid="stToolbar"],
  [data-testid="stDecoration"], [data-testid="stTooltipIcon"], .st-key-invoice-nav {
    display: none !important;
  }
  [data-testid="stMainBlockContainer"] { padding: 0 !important; max-width: none !important; }
  .stApp, .stApp * {
    color: #000 !important; background: transparent !important; box-shadow: none !important;
  }
  .stApp table { font-size: 9px; }
  .stApp th, .stApp td { padding: 1px 4px !important; border-color: #888 !important; }
  .stApp [data-testid="stMetricValue"] { font-size: 14px !important; }
  .stApp [data-testid="stCaptionContainer"] { font-size: 8px !important; }
  .stApp h1 { font-size: 18px !important; padding: 0 0 2px !important; }
  .stApp h3 { font-size: 12px !important; padding: 4px 0 0 !important; }
  .stApp [data-testid="stVerticalBlock"] { gap: 3px !important; }
  .stApp table, .stApp [data-testid="stMetric"] { break-inside: avoid; }
  .stApp h3 { break-after: avoid; }
  .st-key-invoice-lines { break-before: page; }
  .st-key-invoice-lines:not(:has(details[open])) { display: none !important; }
}
</style>
"""

TERMS = {
    "basis": (
        "Na czym opierają się liczby: odczyt rzeczywisty (zdalny, fizyczny albo odbiorcy) "
        "albo odczyt szacunkowy, gdy Tauron nie miał odczytu. Szacunek wyrówna kolejna Faktura."
    ),
    "reading_type": (
        "Jak ustalono stan licznika: zdalny (licznik sam wysłał odczyt), fizyczny (odczytał "
        "pracownik Taurona), odbiorcy (podaliście go sami) albo szacunkowy (Tauron go wyliczył)."
    ),
    "correcting": (
        "Faktura korygująca zmienia kwoty lub ilości z wcześniejszej Faktury. Jej część "
        "„należało policzyć” zastępuje rozliczenie korygowanej Faktury."
    ),
    "net_metering": (
        "Energia oddana do sieci, pomnożona przez Współczynnik opustu, trafia do Magazynu "
        "energii i pomniejsza energię pobraną."
    ),
    "store": (
        "Magazyn energii to nie bateria. To „konto” w Tauronie: za każdą kWh oddaną do sieci "
        "dostajecie {coefficient} kWh do odebrania później, przez 12 miesięcy."
    ),
    "store_added": "Energia oddana × Współczynnik opustu: tyle przybyło w Magazynie energii.",
    "discount_kwh": (
        "Opust: kWh z Magazynu energii odliczone od Energii pobranej. Za nie nie płacicie ceny "
        "energii ani dystrybucji zmiennej."
    ),
    "seller_share": (
        "Część Energii oddanej, która nie trafia do Magazynu energii "
        "(1 − Współczynnik opustu). Zostaje u Sprzedawcy."
    ),
    "imported": "Prąd wzięty z sieci, zmierzony licznikiem i rozliczony na Fakturze.",
    "exported": (
        "Prąd z paneli, którego dom w danej chwili nie zużył i który popłynął do sieci. "
        "To nie cała produkcja paneli, bo część zużywacie od razu."
    ),
    "period_cost": (
        "Wynik rozliczenia brutto (sprzedaż + dystrybucja) minus Bonifikaty z Faktury i z Not "
        "obciążeniowych za ten okres. Bez Prognoz i nadpłat."
    ),
    "average_price": "Koszt okresu podzielony przez Energię pobraną w tym okresie.",
    "result": "Suma wszystkich Pozycji faktury brutto: sprzedaż energii plus dystrybucja.",
    "forecast": (
        "Prognoza to zaliczka za przyszły okres, wyliczona przez Tauron z przewidywanej "
        "Energii pobranej i rozliczana w następnej Fakturze."
    ),
    "amount_due": (
        "Wynik rozliczenia minus Prognozy i wpłaty, które już poszły. Ujemna kwota to "
        "nadpłata do zwrotu albo do zaliczenia na kolejne Prognozy."
    ),
    "balance": (
        "Saldo to stan rozrachunku z Tauronem dla tego PPE po tej Fakturze: nadpłata "
        "(Tauron jest winien Wam) albo niedopłata (do dopłaty). Nie przechodzi na inny PPE."
    ),
    "tariff": (
        "Taryfa (grupa taryfowa) mówi, jak liczone są ceny, np. G11: jedna cena przez całą "
        "dobę. Moc umowna to największa moc, jaką PPE może pobierać naraz."
    ),
    "excise": "Akcyza to podatek od energii. Jest już w cenie; Faktura podaje ją dla informacji.",
    "cost_groups": (
        "Pozycje faktury zebrane w pięć grup. Pełna lista, tak jak na Fakturze, jest niżej."
    ),
    "year_earlier": (
        "Te same daty rok wcześniej, z Waszych Faktur. Tauron podaje na Fakturze własną "
        "wartość „analogicznego okresu”; obie powinny być podobne."
    ),
}

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


def render_invoice_page(context: FeatureContext, archive: FileArchive, number: str) -> None:
    st.html(PRINT_STYLE)
    point = context.metering_point
    sheet = invoice_sheet(context.repository, point.ppe_number, number)
    if sheet is None:
        st.warning(f"{point.name} nie ma Faktury {number}.")
        st.button("Wróć", on_click=close_invoice)
        return
    _render_navigation(sheet, archive)
    invoice = sheet.invoice
    _render_header(sheet, point.name)
    _render_key_figures(sheet)
    _render_readings(invoice)
    if invoice.energy_settlement is not None:
        _render_energy_settlement(invoice)
    _render_cost_groups(sheet)
    _render_settlement(sheet)
    _render_forecasts(invoice)
    _render_year_earlier(sheet)
    _render_lines(sheet)


def _render_navigation(sheet: InvoiceSheet, archive: FileArchive) -> None:
    with st.container(key="invoice-nav"):
        columns = st.columns([2, 1, 3, 2, 3], vertical_alignment="center")
        columns[0].button(
            "◀ Poprzednia Faktura",
            disabled=sheet.previous_number is None,
            on_click=open_invoice,
            args=(sheet.previous_number,),
        )
        columns[1].button("Wróć", on_click=close_invoice)
        columns[2].button(
            "Pokaż ten okres w Przeglądzie",
            on_click=close_invoice,
            args=(sheet.overview_period,),
        )
        columns[3].button(
            "Następna Faktura ▶",
            disabled=sheet.next_number is None,
            on_click=open_invoice,
            args=(sheet.next_number,),
        )
        source_file = sheet.source_file
        path = archive.path(source_file.archive_name) if source_file is not None else None
        if source_file is not None and path is not None and path.exists():
            columns[4].download_button(
                "Otwórz oryginał PDF",
                data=path.read_bytes(),
                file_name=source_file.file_name,
                mime="application/pdf" if path.suffix.lower() == ".pdf" else None,
            )
        else:
            columns[4].button(
                "Otwórz oryginał PDF",
                disabled=True,
                help="Tej Faktury nie ma w archiwum wgranych plików.",
            )
        st.caption("Wydruk „Faktura po ludzku”: Ctrl+P w przeglądarce (drukarka albo PDF).")


def _render_header(sheet: InvoiceSheet, point_name: str) -> None:
    invoice = sheet.invoice
    header = invoice.header
    period = header.billing_period
    st.title(f"{invoice.kind.value} {invoice.number}")
    st.markdown(f"**{point_name}** · {fmt.period(period)} ({period.days} dni)")
    if invoice.correction is not None:
        correction = invoice.correction
        st.markdown(
            f"Koryguje Fakturę **{correction.corrected_invoice_number}** z "
            f"{fmt.day(correction.corrected_invoice_issue_date)}. Przyczyna: {correction.reason}",
            help=TERMS["correcting"],
        )
    if sheet.superseded_by is not None:
        st.info(
            f"Tę Fakturę zastępuje Faktura korygująca {sheet.superseded_by}: "
            "do Kosztu okresu liczy się korekta."
        )
    left, right = st.columns(2)
    with left:
        st.markdown(f"**Data wystawienia:** {fmt.day(header.issue_date)}")
        st.markdown(
            f"**Podstawa rozliczenia:** {fmt.BASIS_BADGES[invoice.settlement_basis]}",
            help=TERMS["basis"],
        )
    with right:
        st.markdown(
            f"**Taryfa:** {header.tariff_group} · **Moc umowna:** "
            f"{fmt.decimal_pl(header.contracted_power_kw)} kW",
            help=TERMS["tariff"],
        )
        settlement = header.settlement_type.value
        settlement_help = None
        if invoice.energy_settlement is not None:
            coefficient = fmt.decimal_pl(invoice.energy_settlement.discount_coefficient)
            settlement += f", Współczynnik opustu {coefficient}"
            settlement_help = TERMS["net_metering"]
        st.markdown(f"**Rodzaj rozliczenia:** {settlement}", help=settlement_help)
    sources = [fmt.source(header.source)]
    if header.issue_date_source is not None and header.issue_date_source != header.source:
        sources.append(f"data wystawienia: str. {header.issue_date_source.page}")
    st.caption(f"Źródło: {', '.join(sources)}")


def _amount_due(invoice: Invoice) -> Decimal:
    """Do zapłaty (ujemne: do zwrotu); dla Faktury korygującej różnica po korekcie."""
    if invoice.correction is not None:
        return invoice.correction.difference
    return invoice.summary.amount_due


def _due_text(amount_due: Decimal) -> tuple[str, str]:
    if amount_due < 0:
        return "Do zwrotu", fmt.zl(-amount_due)
    return "Do zapłaty", fmt.zl(amount_due)


def _render_key_figures(sheet: InvoiceSheet) -> None:
    invoice = sheet.invoice
    figures: list[tuple[str, str, str | None]] = [
        ("Koszt okresu", fmt.zl(sheet.period_cost), TERMS["period_cost"]),
        ("Pobrane z sieci", fmt.kwh(invoice.imported_kwh), TERMS["imported"]),
    ]
    if invoice.exported_kwh is not None:
        figures.append(("Oddane do sieci", fmt.kwh(invoice.exported_kwh), TERMS["exported"]))
    price = sheet.average_price
    figures.append(
        (
            "Cena średnia kWh",
            _price(price),
            TERMS["average_price"],
        )
    )
    figures.append((*_due_text(_amount_due(invoice)), TERMS["amount_due"]))
    _metrics(figures)


def _price(price: Decimal | None) -> str:
    return f"{fmt.zl(price)}/kWh" if price is not None else "—"


def _metrics(figures: list[tuple[str, str, str | None]]) -> None:
    """Rząd liczb (etykieta, wartość, podpowiedź „?”)."""
    for column, (label, value, help) in zip(st.columns(len(figures)), figures, strict=True):
        column.metric(label, value, help=help)


def _render_readings(invoice: Invoice) -> None:
    st.subheader("Liczniki", help=TERMS["reading_type"])

    def state(value: Decimal | None) -> str:
        return fmt.decimal_pl(value) if value is not None else "—"

    st.table(
        [
            {
                "Licznik": r.meter_number,
                "Kierunek": r.direction.value,
                "Strefa": r.zone,
                "Data odczytu": fmt.day(r.reading_date),
                "Typ odczytu": r.reading_type.value,
                "Stan poprzedni": state(r.previous),
                "Stan obecny": state(r.current),
                "Ilość": fmt.kwh(r.quantity_kwh),
            }
            for r in invoice.readings
        ]
    )
    pages = sorted({r.source.page for r in invoice.readings})
    if pages:
        st.caption(f"Źródło: Faktura {invoice.number}, str. {', '.join(map(str, pages))}")


def _render_energy_settlement(invoice: Invoice) -> None:
    store = invoice.energy_settlement
    assert store is not None
    coefficient = fmt.decimal_pl(store.discount_coefficient)
    st.subheader("Rozliczenie OZE", help=TERMS["store"].format(coefficient=coefficient))
    figures: list[tuple[str, str, str | None]] = [
        ("Magazyn energii na początku", fmt.kwh(store.store_start_kwh), None),
        (
            f"Przybyło (oddane × {coefficient})",
            f"+{fmt.kwh(store.exported_after_coefficient_kwh)}",
            TERMS["store_added"],
        ),
        ("Opust (odebrane)", f"−{fmt.kwh(invoice.discount_kwh)}", TERMS["discount_kwh"]),
        ("Udział Sprzedawcy", fmt.kwh(store.seller_share_kwh), TERMS["seller_share"]),
        ("Magazyn energii na koniec", fmt.kwh(store.store_end_kwh), None),
    ]
    _metrics(figures)
    st.caption(
        f"Oddane do sieci {fmt.kwh(store.exported_kwh)}, pobrane z sieci "
        f"{fmt.kwh(store.imported_kwh)}, z tego za energię zapłacono od "
        f"{fmt.kwh(invoice.billed_energy_kwh)}. Z tego okresu w Magazynie energii zostaje "
        f"{fmt.kwh(store.remaining_from_this_period_kwh)} na 12 miesięcy. "
        f"Źródło: {fmt.source(store.source)}"
    )


def _group_text(group: CostGroupTotal, net_metering: bool) -> str:
    base, with_pv = GROUP_TEXTS[group.group]
    return base + (with_pv if net_metering else "")


def _render_cost_groups(sheet: InvoiceSheet) -> None:
    invoice = sheet.invoice
    net_metering = invoice.energy_settlement is not None
    st.subheader(f"Za co płacicie: {fmt.zl(sheet.period_cost)}", help=TERMS["cost_groups"])
    rows = [
        (group.group.value, fmt.zl(group.gross), _group_text(group, net_metering))
        for group in sheet.cost_groups
    ]
    discount = invoice.summary.discount
    if discount is not None:
        rows.append(
            (
                "Bonifikata na Fakturze",
                fmt.zl(discount.gross),
                "Obniżka należności przyznana przez Tauron w tej Fakturze.",
            )
        )
    for note in sheet.debit_notes:
        rows.append(
            (
                f"Bonifikata z Noty {note.number}",
                fmt.zl(-note.discount),
                "Obniżka z Noty obciążeniowej za ten okres (np. z rozporządzenia).",
            )
        )
    rows.append(("**Koszt okresu**", f"**{fmt.zl(sheet.period_cost)}**", ""))
    # Tabela Markdown, nie st.table: szerokości kolumn dopasowują się do treści, więc opisy
    # zajmują mniej wierszy i „Faktura po ludzku” mieści się na jednej stronie A4.
    table = ["| Grupa | Brutto | Co to jest |", "|---|--:|---|"]
    table += [f"| {name} | {_no_break(gross)} | {text} |" for name, gross, text in rows]
    st.markdown("\n".join(table))


def _no_break(text: str) -> str:
    """Kwota w jednym wierszu (twarda spacja w ``1 234,56 zł``)."""
    return text.replace(" ", "\u00a0")


def _amount(value: Amount | None) -> str:
    return fmt.zl(value.gross) if value is not None else "—"


SETTLEMENT_HELP = " ".join(
    TERMS[key] for key in ("result", "amount_due", "balance", "excise", "average_price")
)


def _render_settlement(sheet: InvoiceSheet) -> None:
    invoice = sheet.invoice
    summary = invoice.summary
    st.subheader("Rozliczenie", help=SETTLEMENT_HELP)
    rows = [("Wynik rozliczenia (sprzedaż + dystrybucja)", _amount(summary.result))]
    if summary.discount is not None:
        rows.append(("Bonifikata na Fakturze", _amount(summary.discount)))
    if summary.previous_forecast is not None:
        rows.append(
            ("Prognozy z poprzedniej Faktury (już zapłacone)", _amount(summary.previous_forecast))
        )
    if summary.additional_payments:
        rows.append(("Wpłaty", fmt.zl(-summary.additional_payments)))
    correction = invoice.correction
    if correction is None:
        rows.append(_due_text(summary.amount_due))
    else:
        label, value = _due_text(summary.amount_due)
        rows.append((f"{label} według „należało policzyć”", value))
        label, value = _due_text(correction.charged_amount_due)
        rows.append((f"{label} według korygowanej Faktury („policzono”)", value))
        label, value = _due_text(correction.difference)
        rows.append((f"{label} po korekcie", value))
    balance = summary.account_balance
    if balance is not None:
        state = "nadpłata" if balance >= 0 else "niedopłata"
        rows.append(("Saldo po Fakturze", f"{state} {fmt.zl(abs(balance))}"))
    if summary.excise_amount is not None:
        excise_kwh = f"{fmt.kwh(summary.excise_kwh)}, " if summary.excise_kwh is not None else ""
        rows.append(("Akcyza (w cenie)", f"{excise_kwh}{fmt.zl(summary.excise_amount)}"))
    price = sheet.average_price
    rows.append(("Cena średnia kWh", _price(price)))
    st.table([{"": name, "Kwota": value} for name, value in rows])
    note = f"Źródło: {fmt.source(summary.source)}"
    if correction is not None:
        note += (
            f"; korekta: str. {correction.source.page}, "
            f"kwota po korekcie: str. {correction.difference_source.page}"
        )
    st.caption(note)


def _render_forecasts(invoice: Invoice) -> None:
    if not invoice.forecasts:
        return
    st.subheader("Harmonogram Prognoz", help=TERMS["forecast"])
    st.table(
        [
            {
                "Prognoza": f.number,
                "Okres": fmt.period(f.period),
                "Pobrane (przewidywane)": fmt.kwh(f.import_kwh),
                "Brutto": fmt.zl(f.gross),
                "Doliczone Saldo": fmt.zl(f.balance_adjustment),
                "Do zapłaty": fmt.zl(f.amount_due),
                "Termin": fmt.day(f.due_date),
            }
            for f in invoice.forecasts
        ]
    )
    pages = sorted({f.source.page for f in invoice.forecasts})
    st.caption(f"Źródło: Faktura {invoice.number}, str. {', '.join(map(str, pages))}")


def _change(current: Decimal, earlier: Decimal | None) -> str:
    if earlier is None or earlier == 0:
        return "—"
    change = (current - earlier) / earlier * 100
    return f"{'+' if change > 0 else ''}{fmt.decimal_pl(change.quantize(Decimal(1)))}%"


def _render_year_earlier(sheet: InvoiceSheet) -> None:
    invoice = sheet.invoice
    earlier: YearEarlier = sheet.year_earlier
    st.subheader("Ten sam okres rok wcześniej", help=TERMS["year_earlier"])
    mark = "≈ " if earlier.approximate else ""
    this_period = f"Ten okres ({_short(invoice.header.billing_period)})"
    year_before = f"Rok wcześniej ({_short(earlier.period)})"
    if earlier.imported_kwh is None:
        st.markdown("Brak Waszych Faktur za cały ten okres rok wcześniej.")
    else:
        rows = [
            {
                "": "Pobrane z sieci",
                this_period: fmt.kwh(invoice.imported_kwh),
                year_before: mark + fmt.kwh(earlier.imported_kwh),
                "Zmiana": _change(invoice.imported_kwh, earlier.imported_kwh),
            }
        ]
        if invoice.exported_kwh is not None and earlier.exported_kwh is not None:
            rows.append(
                {
                    "": "Oddane do sieci",
                    this_period: fmt.kwh(invoice.exported_kwh),
                    year_before: mark + fmt.kwh(earlier.exported_kwh),
                    "Zmiana": _change(invoice.exported_kwh, earlier.exported_kwh),
                }
            )
        if earlier.period_cost is not None:
            rows.append(
                {
                    "": "Koszt okresu",
                    this_period: fmt.zl(sheet.period_cost),
                    year_before: mark + fmt.zl(earlier.period_cost),
                    "Zmiana": _change(sheet.period_cost, earlier.period_cost),
                }
            )
        st.table(rows)
        note = f"Z Faktur: {', '.join(earlier.invoice_numbers)}."
        if earlier.approximate:
            note += (
                " ≈ wycięte z Faktury za dłuższy okres: kWh i Składniki zmienne proporcjonalnie "
                "do dni, Składniki stałe po równo na miesiące."
            )
        st.caption(note)
    if earlier.tauron_imported_kwh is not None and earlier.tauron_source is not None:
        st.caption(
            f"Tauron na tej Fakturze podaje pobrane w analogicznym okresie rok wcześniej: "
            f"{fmt.kwh(earlier.tauron_imported_kwh)} ({fmt.source(earlier.tauron_source)})."
        )


def _short(period: DateRange) -> str:
    return f"{period.start:%d.%m.%y}–{period.end:%d.%m.%y}"


def _render_lines(sheet: InvoiceSheet) -> None:
    invoice = sheet.invoice
    with st.container(key="invoice-lines"):
        with st.expander(f"Pełna lista Pozycji faktury ({len(invoice.lines)})"):
            st.table(
                [
                    {
                        "Sekcja": x.section.value,
                        "Pozycja faktury": x.name,
                        "Strefa": x.zone or "",
                        "Podokres": x.sub_period,
                        "Ilość": f"{fmt.decimal_pl(x.quantity)} {x.unit}",
                        "Cena netto": fmt.decimal_pl(x.unit_price_net),
                        "Netto": fmt.zl(x.net),
                        "VAT": fmt.zl(x.vat),
                        "Brutto": fmt.zl(x.gross),
                        "Grupa": cost_group(x).value,
                    }
                    for x in invoice.lines
                ]
            )
            pages = sorted({x.source.page for x in invoice.lines})
            st.caption(
                "Kolejność i podokresy jak na Fakturze. "
                f"Źródło: Faktura {invoice.number}, str. {', '.join(map(str, pages))}. "
                "Rozwinięta lista drukuje się na 2. stronie."
            )
