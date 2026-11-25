from decimal import Decimal
from functools import partial

import streamlit as st

from pv_app.domain.cost_groups import CostGroup
from pv_app.domain.invoice import SettlementBasis
from pv_app.domain.metering_point import MeteringPoint
from pv_app.domain.view_period import ViewPeriodKind, month_label
from pv_app.features import formatting as fmt
from pv_app.features.base import FeatureContext
from pv_app.features.costs.analysis import (
    CostSummary,
    DebitNoteListRow,
    InvoiceListRow,
    cost_summary,
    debit_note_list,
    invoice_list,
    unit_price_history,
)
from pv_app.features.costs.chart import unit_price_figure, units
from pv_app.features.monthly import PeriodTotals, monthly_chart
from pv_app.features.monthly_figure import COST_BLOCK_NOTE, cost_figure
from pv_app.features.navigation import open_invoice
from pv_app.features.terms import group_text

PERIOD_COST_HELP = (
    "Wynik rozliczenia brutto z Faktur (sprzedaż + dystrybucja) minus Bonifikaty z Faktur "
    "i z Not obciążeniowych. Bez Prognoz i nadpłat."
)
AVERAGE_PRICE_HELP = (
    "Koszt okresu podzielony przez prąd pobrany z sieci w tym okresie. To nie cena z Faktury: "
    "Tauron pomija w niej kWh pokryte z Magazynu energii, a tu liczy się wszystko, co "
    "zapłaciliście, także opłaty stałe."
)
APPROXIMATE_HELP = (
    "≈ liczby wyliczone z Faktury za dłuższy okres: kWh i Składniki zmienne proporcjonalnie "
    "do dni, Składniki stałe po równo na miesiące."
)
GROUPS_HELP = (
    "Pozycje faktury zebrane w pięć grup. Pełną listę Pozycji, tak jak na Fakturze, pokazuje "
    "Faktura po ludzku (kliknij Fakturę na liście niżej)."
)
EXCISE_HELP = (
    "Akcyza to podatek od energii. Jest już w cenach powyżej; Faktura podaje ją dla informacji."
)
UNIT_PRICES_HELP = (
    "Ceny jednostkowe netto z Pozycji faktury, Faktura po Fakturze, tak jak na Fakturze "
    "(bez VAT). Pokazują, kiedy Tauron zmieniał stawki."
)
UNIT_TITLES = {"kWh": "Ceny za kWh", "mc": "Opłaty za miesiąc"}


class CostsFeature:
    id = "koszty"
    title = "Koszty i Faktury"
    order = 30

    def is_available(self, metering_point: MeteringPoint) -> bool:
        return True

    def render(self, context: FeatureContext) -> None:
        summary = cost_summary(context.repository, context.filters)
        if summary is not None:
            _render_summary(context, summary)
        _render_cost_chart(context)
        if summary is not None:
            _render_groups(context, summary)
        _render_unit_prices(context)
        _render_invoices(context)


def _approx(totals: PeriodTotals) -> str:
    return "≈ " if totals.approximate else ""


def _price(value: Decimal | None) -> str:
    return fmt.zl(value) if value is not None else "—"


def _change(current: Decimal | None, earlier: Decimal | None) -> str | None:
    if current is None or earlier is None or earlier == 0:
        return None
    change = (current - earlier) / earlier * 100
    return f"{change:+.0f}% r/r"


def _months_text(months: tuple[int, ...]) -> str:
    return ", ".join(month_label(m) for m in months)


def _render_summary(context: FeatureContext, summary: CostSummary) -> None:
    period = context.view_period
    current, earlier = summary.current, summary.year_earlier
    st.subheader(f"Koszty: {period.label}")
    cost_column, price_column, earlier_column = st.columns(3)
    cost_column.metric(
        "Koszt okresu",
        _approx(current) + fmt.zl(current.period_cost),
        delta=_change(current.period_cost, earlier.period_cost if earlier else None),
        delta_color="inverse",
        help=PERIOD_COST_HELP,
    )
    price_column.metric(
        "Cena średnia kWh",
        _approx(current) + _price(current.average_price),
        delta=_change(current.average_price, earlier.average_price if earlier else None),
        delta_color="inverse",
        help=AVERAGE_PRICE_HELP,
    )
    if earlier is not None:
        earlier_column.metric(
            f"Rok wcześniej ({period.year_earlier().label})",
            _approx(earlier) + fmt.zl(earlier.period_cost),
            help=f"Ten sam okres rok wcześniej z Waszych Faktur. {APPROXIMATE_HELP}",
        )
        earlier_column.caption(
            f"Cena średnia kWh: {_approx(earlier)}{_price(earlier.average_price)}"
        )
    elif period.kind is not ViewPeriodKind.WHOLE:
        earlier_column.caption("Brak Faktur za ten sam okres rok wcześniej.")
    notes = [
        f"Pobrane z sieci: {_approx(current)}{fmt.kwh(current.imported_kwh)}.",
    ]
    if summary.missing_months:
        notes.append(
            "Sumy obejmują tylko miesiące objęte Fakturami w całości "
            f"({_months_text(current.months)})."
        )
    if current.approximate or (earlier is not None and earlier.approximate):
        notes.append(APPROXIMATE_HELP)
    st.caption(" ".join(notes))


def _render_cost_chart(context: FeatureContext) -> None:
    chart = monthly_chart(context.repository, context.filters)
    if chart is None:
        return
    heading, toggle = st.columns([3, 1], vertical_alignment="bottom")
    with heading:
        st.subheader(
            "Koszt miesięcznie",
            help="Miesiąc z własną Fakturą to słupek. Faktura za kilka miesięcy to jeden płaski "
            "blok na wysokości średniej miesięcznej (Koszt okresu / dni × 30,44). "
            + COST_BLOCK_NOTE,
        )
    with toggle:
        compare = st.checkbox("porównaj z rokiem wcześniej", value=True, key="costs_compare")
    st.plotly_chart(cost_figure(chart, compare), config={"displayModeBar": False}, key="cost_chart")
    st.caption(
        "Przerywany kontur: te same Faktury rok wcześniej. „?” — miesiąc bez Faktury. "
        "Wyróżniony fragment to wybrany Okres widoku."
    )


GROUP_COLORS = {
    CostGroup.ENERGY: "#e8a10c",
    CostGroup.VARIABLE_DISTRIBUTION: "#2f5d8a",
    CostGroup.PER_KWH_FEES: "#3c8a5a",
    CostGroup.CAPACITY: "#c96a2e",
    CostGroup.FIXED_FEES: "#7a8691",
    CostGroup.UNRECOGNIZED: "#c93c2e",
}


def _share_bar(groups: dict[CostGroup, Decimal]) -> str:
    """Pasek udziałów Grup kosztów (tylko grupy z kosztem dodatnim)."""
    positive = {g: v for g, v in groups.items() if v > 0}
    total = sum(positive.values(), Decimal(0))
    if not total:
        return ""
    parts = "".join(
        f'<div title="{g.value}: {fmt.zl(v)} ({v / total * 100:.0f}%)" '
        f'style="flex:{v};background:{GROUP_COLORS[g]}"></div>'
        for g, v in positive.items()
    )
    return (
        '<div style="display:flex;height:14px;border-radius:7px;overflow:hidden;gap:2px;'
        f'margin:4px 0 8px">{parts}</div>'
    )


def _render_groups(context: FeatureContext, summary: CostSummary) -> None:
    current = summary.current
    net_metering = context.metering_point.net_metering
    st.subheader(
        f"Za co płacicie: {_approx(current)}{fmt.zl(current.period_cost)}", help=GROUPS_HELP
    )
    bar = _share_bar(dict(current.cost_groups))
    if bar:
        st.html(bar)
    rows = [
        (
            f'<span style="color:{GROUP_COLORS[group]}">■</span> {group.value}',
            fmt.zl(value),
            group_text(group, net_metering),
        )
        for group, value in current.cost_groups.items()
    ]
    if current.discounts:
        rows.append(
            (
                "Bonifikaty",
                fmt.zl(current.discounts),
                "Obniżki z Faktur i Not obciążeniowych za ten okres (np. z rozporządzenia), "
                "z groszowymi zaokrągleniami VAT.",
            )
        )
    rows.append(("**Koszt okresu**", f"**{fmt.zl(current.period_cost)}**", ""))
    table = ["| Grupa | Brutto | Co to jest |", "|---|--:|---|"]
    table += [f"| {name} | {_no_break(gross)} | {text} |" for name, gross, text in rows]
    st.markdown("\n".join(table), unsafe_allow_html=True)
    notes = []
    if current.approximate:
        notes.append(APPROXIMATE_HELP)
    if summary.excise is not None:
        notes.append(
            f"W cenach jest akcyza: {_approx(current)}{fmt.zl(summary.excise)} "
            "(tylko informacyjnie, nie dolicza się jej osobno)."
        )
    if notes:
        st.caption(" ".join(notes), help=EXCISE_HELP if summary.excise is not None else None)


def _no_break(text: str) -> str:
    """Kwota w jednym wierszu (twarda spacja w ``1 234,56 zł``)."""
    return text.replace(" ", " ")


def _render_unit_prices(context: FeatureContext) -> None:
    history = unit_price_history(context.repository, context.filters)
    if not history:
        return
    st.subheader("Ceny jednostkowe w czasie", help=UNIT_PRICES_HELP)
    for unit in units(history):
        st.markdown(f"**{UNIT_TITLES.get(unit, f'Ceny za {unit}')}**")
        st.plotly_chart(
            unit_price_figure(history, unit, context.view_period.dates),
            config={"displayModeBar": False},
            key=f"unit_prices_{unit}",
        )
    st.caption(
        "Ceny netto z Pozycji faktury. Gdy cena zmieniła się w trakcie Okresu rozliczeniowego, "
        "kreska dzieli się na podokresy z Faktury."
    )


def _render_invoices(context: FeatureContext) -> None:
    point = context.metering_point
    rows = invoice_list(context.repository, context.filters)
    st.subheader("Faktury")
    if not rows:
        st.info(f"Brak Faktur za {context.view_period.label}.")
    else:
        st.dataframe(
            [_invoice_entry(row, point) for row in rows],
            hide_index=True,
            key=INVOICE_LIST_KEY,
            on_select=partial(_open_selected, [row.number for row in rows]),
            selection_mode="single-row",
        )
        st.caption(
            "Kliknij wiersz, żeby otworzyć Fakturę po ludzku (z wydrukiem). "
            "Koszt okresu to Wynik rozliczenia brutto z Faktury (sprzedaż + dystrybucja) "
            "minus bonifikaty z Faktury i z Not obciążeniowych za ten okres, bez Prognoz "
            "i nadpłat. Faktura zastąpiona Fakturą korygującą zostaje na liście, ale liczy "
            "się korekta. 🟡 odczyt szacunkowy: Tauron oszacował stan licznika, kolejna Faktura "
            "go wyrówna."
        )
    notes = debit_note_list(context.repository, context.filters)
    if notes:
        st.subheader("Noty obciążeniowe")
        st.dataframe([_note_entry(note) for note in notes], hide_index=True)
        st.caption(
            "Bonifikata z Noty pomniejsza Koszt okresu Faktury, w której Okresie "
            "rozliczeniowym leży data sprzedaży Noty."
        )


INVOICE_LIST_KEY = "invoice_list"


def _open_selected(numbers: list[str]) -> None:
    """Otwiera zaznaczoną Fakturę i czyści zaznaczenie, żeby po powrocie lista była zwykła."""
    selected = st.session_state[INVOICE_LIST_KEY].selection.rows
    del st.session_state[INVOICE_LIST_KEY]
    if selected:
        open_invoice(numbers[selected[0]])


def _invoice_entry(row: InvoiceListRow, point: MeteringPoint) -> dict[str, object]:
    document = f"{row.kind.value} {row.number}"
    if row.corrects:
        document += f" (koryguje {row.corrects})"
    if row.superseded_by:
        document += f" — zastąpiona przez {row.superseded_by}"
    period = fmt.period(row.period)
    if row.basis is not SettlementBasis.ACTUAL_READING:
        # Oznaczamy tylko wyjątki: odczyt rzeczywisty to zwykły przypadek.
        period += f" {fmt.BASIS_BADGES[row.basis]}"
    entry: dict[str, object] = {
        "Okres": period,
        "Dni": row.period.days,
        "Dokument": document,
        "Pobrane z sieci": fmt.kwh(row.imported_kwh),
    }
    if point.net_metering:
        entry["Oddane do sieci"] = (
            fmt.kwh(row.exported_kwh) if row.exported_kwh is not None else "—"
        )
    entry["Koszt okresu"] = fmt.zl(row.period_cost)
    entry["Cena średnia kWh"] = _price(row.average_price)
    entry["Noty obciążeniowe"] = ", ".join(row.debit_notes) or "—"
    entry["Źródło"] = fmt.source(row.source)
    return entry


def _note_entry(note: DebitNoteListRow) -> dict[str, object]:
    if note.superseded_by:
        applies_to = f"zastąpiona przez {note.superseded_by}"
    elif note.invoice_number:
        applies_to = f"Faktura {note.invoice_number}"
    else:
        applies_to = "brak Faktury za ten okres"
    return {
        "Nota": note.number,
        "Data wystawienia": fmt.day(note.issue_date),
        "Data sprzedaży": fmt.day(note.sale_date),
        "Bonifikata": fmt.zl(note.discount),
        "Do zapłaty": fmt.zl(note.amount_due),
        "Pomniejsza Koszt okresu": applies_to,
        "Źródło": f"Nota {note.number}, str. {note.source.page}",
    }
