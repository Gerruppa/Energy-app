from datetime import date
from decimal import Decimal

import streamlit as st

from pv_app.domain.metering_point import MeteringPoint
from pv_app.domain.view_period import ViewPeriodKind, month_label
from pv_app.features import formatting as fmt
from pv_app.features.base import FeatureContext
from pv_app.features.monthly import PeriodTotals, YearOverYear, monthly_chart, year_over_year
from pv_app.features.monthly_figure import BLOCK_NOTE, FORECAST_NOTE, energy_figure
from pv_app.features.navigation import open_invoice
from pv_app.features.overview.analysis import forecast_chart
from pv_app.features.overview.top import render_top
from pv_app.features.terms import FORECAST_HELP, STORED_HELP
from pv_app.storage.repository import Repository

EXPORTED_HELP = (
    "Prąd z paneli, którego dom w danej chwili nie zużył i który popłynął do sieci. "
    "To nie cała produkcja paneli, bo część zużywacie od razu."
)
IMPORTED_HELP = "Prąd wzięty z sieci, gdy panele dawały za mało (wieczorem, w nocy, zimą)."
IMPORTED_HELP_NO_PV = "Prąd wzięty z sieci, zmierzony licznikiem i rozliczony na Fakturze."
PERIOD_COST_HELP = (
    "Wynik rozliczenia brutto z Faktury (sprzedaż + dystrybucja) minus Bonifikaty. "
    "Bez Prognoz i nadpłat."
)
APPROXIMATE_HELP = (
    "≈ liczby wyliczone z Faktury za dłuższy okres: kWh i Składniki zmienne proporcjonalnie "
    "do dni, Składniki stałe po równo na miesiące."
)


class OverviewFeature:
    id = "przeglad"
    title = "Przegląd"
    order = 10

    def is_available(self, repository: Repository, metering_point: MeteringPoint) -> bool:
        return True

    def render(self, context: FeatureContext) -> None:
        point = context.metering_point
        chart = monthly_chart(context.repository, context.filters)
        if chart is None:
            st.info("Brak Faktur dla tego punktu poboru.")
            return
        render_top(context, today=date.today())
        title = (
            "Prąd miesiąc po miesiącu"
            if point.net_metering
            else "Pobrane z sieci miesiąc po miesiącu"
        )
        heading, toggle = st.columns([3, 1], vertical_alignment="bottom")
        with heading:
            st.subheader(
                title,
                help=(
                    f"**Oddane do sieci** (w górę): {EXPORTED_HELP}\n\n"
                    f"**Pobrane z sieci** (w dół): {IMPORTED_HELP}\n\n"
                    if point.net_metering
                    else f"**Pobrane z sieci**: {IMPORTED_HELP_NO_PV}\n\n"
                )
                + "Miesiąc z własną Fakturą to słupek. Faktura za kilka miesięcy to jeden "
                f"płaski blok na wysokości średniej miesięcznej. {BLOCK_NOTE}",
            )
        with toggle:
            compare = st.checkbox("porównaj z rokiem wcześniej", value=True, key="compare")
        st.plotly_chart(
            energy_figure(chart, point.net_metering, compare),
            config={"displayModeBar": False},
        )
        st.caption(
            "Przerywany kontur: te same Faktury rok wcześniej. "
            "„?” — miesiąc bez Faktury. Wyróżniony fragment to wybrany Okres widoku."
        )
        comparison = year_over_year(context.repository, context.filters)
        if comparison is not None:
            _render_comparison(context, comparison)
        elif context.view_period.kind is not ViewPeriodKind.WHOLE:
            st.info(f"Faktury nie obejmują w całości okresu: {context.view_period.label}.")
        if not point.net_metering:
            _render_forecasts(context)


def _render_forecasts(context: FeatureContext) -> None:
    """Prognozy Taurona a rzeczywistość (PPE bez fotowoltaiki): Prognozy przerywaną linią."""
    chart = forecast_chart(context.repository, context.filters)
    if chart is None:
        return
    st.subheader("Prognozy Taurona a rzeczywistość", help=FORECAST_HELP)
    st.plotly_chart(
        energy_figure(chart.energy, net_metering=False, compare=False, forecasts=chart.forecasts),
        config={"displayModeBar": False},
        key="forecast_chart",
    )
    st.caption(FORECAST_NOTE)


def _months_text(months: tuple[int, ...]) -> str:
    return ", ".join(month_label(m) for m in months)


def _change(current: Decimal | None, earlier: Decimal | None) -> str:
    if current is None or earlier is None or earlier == 0:
        return "—"
    change = (current - earlier) / earlier * 100
    arrow = "▲" if change > 0 else "▼" if change < 0 else "="
    return f"{arrow} {abs(change):.0f}%"


def _render_comparison(context: FeatureContext, comparison: YearOverYear) -> None:
    point = context.metering_point
    period = context.view_period
    current, earlier = comparison.current, comparison.year_earlier
    st.subheader(
        f"{period.label} a {period.year_earlier().label}",
        help="Rok do roku z Waszej własnej historii Faktur. " + APPROXIMATE_HELP,
    )
    this_column = period.label + (" ≈" if current.approximate else "")
    earlier_column = period.year_earlier().label + (
        " ≈" if earlier is not None and earlier.approximate else ""
    )

    imported_help = IMPORTED_HELP if point.net_metering else IMPORTED_HELP_NO_PV
    rows: list[dict[str, str]] = []

    def add(
        label: str,
        now: Decimal | None,
        before: Decimal | None,
        money: bool,
        from_tauron: bool = False,
    ) -> None:
        show = fmt.zl if money else fmt.kwh
        before_text = show(before) if before is not None else "—"
        if from_tauron:
            before_text += " (Tauron)"
        rows.append(
            {
                "": label,
                this_column: show(now) if now is not None else "—",
                earlier_column: before_text,
                "Zmiana": _change(now, before),
            }
        )

    from_tauron = earlier is None and comparison.tauron_last_year_kwh is not None
    before_imported = (
        comparison.tauron_last_year_kwh
        if from_tauron
        else earlier.imported_kwh
        if earlier
        else None
    )
    add(
        "Pobrane z sieci",
        current.imported_kwh,
        before_imported,
        money=False,
        from_tauron=from_tauron,
    )
    if point.net_metering:
        add(
            "Oddane do sieci",
            current.exported_kwh,
            earlier.exported_kwh if earlier is not None else None,
            money=False,
        )
        add(
            "Do Magazynu energii",
            current.stored_kwh,
            earlier.stored_kwh if earlier is not None else None,
            money=False,
        )
    add(
        "Koszt okresu",
        current.period_cost,
        earlier.period_cost if earlier is not None else None,
        money=True,
    )
    st.dataframe(
        rows,
        hide_index=True,
        column_config={
            "": st.column_config.TextColumn(
                "",
                help=f"Pobrane z sieci: {imported_help}"
                + (
                    f"\n\nOddane do sieci: {EXPORTED_HELP}\n\nDo Magazynu energii: {STORED_HELP}"
                    if point.net_metering
                    else ""
                )
                + f"\n\nKoszt okresu: {PERIOD_COST_HELP}",
            )
        },
    )
    notes = []
    if comparison.missing_months:
        notes.append(
            f"Bez Faktury: {_months_text(comparison.missing_months)}. Porównanie obejmuje "
            f"tylko miesiące z Fakturami ({_months_text(current.months)})."
        )
    if earlier is None:
        if comparison.tauron_last_year_kwh is not None:
            sources = ", ".join(fmt.source(s) for s in comparison.tauron_sources)
            notes.append(
                "Brak własnych Faktur sprzed roku. Pobrane z sieci rok wcześniej według "
                f"Taurona („analogiczny okres” na Fakturze; {sources})."
            )
        else:
            notes.append("Brak Faktur za ten sam okres rok wcześniej.")
    elif comparison.tauron_last_year_kwh is not None:
        tauron = fmt.kwh(comparison.tauron_last_year_kwh)
        if comparison.tauron_differs:
            notes.append(
                f"⚠ Tauron na Fakturze podaje dla tego okresu rok wcześniej {tauron} pobranych "
                f"z sieci, a z Waszych Faktur wychodzi {fmt.kwh(earlier.imported_kwh)} "
                "(różnica ponad 5%)."
            )
        else:
            notes.append(
                f"Tauron na Fakturze podaje rok wcześniej {tauron}, co zgadza się z wyliczeniem."
            )
    if current.approximate or (earlier is not None and earlier.approximate):
        notes.append(APPROXIMATE_HELP)
    for note in notes:
        st.caption(note)
    _render_invoices(current)


def _render_invoices(current: PeriodTotals) -> None:
    """Z której Faktury są liczby Okresu widoku, z przejściem do widoku Faktury."""
    for ref in current.invoices:
        sources = f"kWh: str. {ref.energy_source.page}, Koszt okresu: str. {ref.cost_source.page}"
        text_column, button_column = st.columns([5, 1], vertical_alignment="center")
        if ref.part_of_longer:
            text_column.markdown(
                f"≈ Liczby wyliczone z Faktury **{ref.number}** za okres "
                f"{fmt.period(ref.period)} ({sources})."
            )
        else:
            text_column.markdown(
                f"Faktura za ten okres: **{ref.number}**, {fmt.period(ref.period)} ({sources})."
            )
        button_column.button(
            "Pokaż Fakturę",
            key=f"overview_invoice_{ref.number}",
            on_click=open_invoice,
            args=(ref.number,),
        )
