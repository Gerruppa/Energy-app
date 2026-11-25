"""Strona „Dane” wybranego PPE: oś czasu Faktur (kompletność i wiarygodność danych), usunięcie
Faktury i przebudowa bazy z archiwum plików.

Otwierana z paska bocznego, nie jest zakładką: narzędzia porządkowe są dla osoby, która wgrywa
pliki, a nie dla oglądających dashboard.
"""

from datetime import date
from functools import partial

import streamlit as st

from pv_app.app.data_maintenance import delete_invoice, rebuild
from pv_app.app.import_page import render_summary
from pv_app.domain.view_period import month_index, month_label
from pv_app.features import formatting as fmt
from pv_app.features.base import FeatureContext
from pv_app.features.invoice_timeline.analysis import (
    InvoiceTimeline,
    TimelinePeriod,
    invoice_timeline,
)
from pv_app.features.invoice_timeline.chart import timeline_figure
from pv_app.features.navigation import open_invoice
from pv_app.storage.archive import FileArchive

DATA_PAGE = "data_page"
"""Klucz ``st.session_state``: strona „Dane” jest otwarta."""
_TIMELINE_KEY = "data_timeline"
_INVOICE_LIST_KEY = "data_invoice_list"
_PENDING_DELETE = "data_pending_delete"
_CONFIRM_REBUILD = "data_confirm_rebuild"
_REBUILD_SUMMARY = "data_rebuild_summary"
_DELETED = "data_deleted"


def close_data_page() -> None:
    for key in (DATA_PAGE, _PENDING_DELETE, _CONFIRM_REBUILD, _REBUILD_SUMMARY, _DELETED):
        st.session_state.pop(key, None)


def _open(number: str) -> None:
    close_data_page()
    open_invoice(number)


def _open_from_timeline() -> None:
    points = st.session_state[_TIMELINE_KEY].selection.points
    del st.session_state[_TIMELINE_KEY]
    number = next((p.get("customdata") for p in points if p.get("customdata")), None)
    if number:
        _open(str(number))


def _open_from_list(numbers: list[str]) -> None:
    rows = st.session_state[_INVOICE_LIST_KEY].selection.rows
    del st.session_state[_INVOICE_LIST_KEY]
    if rows:
        _open(numbers[rows[0]])


def render_data_page(context: FeatureContext, archive: FileArchive, today: date) -> None:
    point = context.metering_point
    st.title(f"Dane: {point.icon.emoji} {point.name}")
    st.caption(
        "Skąd biorą się liczby na dashboardzie: które okresy mają Fakturę, na jakim odczycie, "
        "i narzędzia do porządkowania danych."
    )
    if st.button("Wróć do dashboardu"):
        close_data_page()
        st.rerun()
    if (deleted := st.session_state.pop(_DELETED, None)) is not None:
        st.success(f"Usunięto Fakturę {deleted}.")

    timeline = invoice_timeline(context.repository, point.ppe_number, today)
    if timeline is None:
        st.info("Ten punkt poboru nie ma jeszcze Faktur.")
    else:
        _render_timeline(timeline, today)
        _render_invoices(context, archive, timeline)
    _render_rebuild(context, archive)


def _render_timeline(timeline: InvoiceTimeline, today: date) -> None:
    st.subheader("Oś czasu Faktur")
    st.plotly_chart(
        timeline_figure(timeline, today),
        config={"displayModeBar": False},
        key=_TIMELINE_KEY,
        on_select=_open_from_timeline,
        selection_mode="points",
    )
    estimate = timeline.estimated_months
    window = (
        f"{month_label(month_index(estimate.window.start))} – "
        f"{month_label(month_index(estimate.window.end))}"
    )
    count = len(estimate.months)
    missing = (
        f" {len(estimate.without_invoice)} z 12 miesięcy nie ma Faktury, więc o nich nie wiadomo."
        if estimate.without_invoice
        else ""
    )
    if count:
        months = ", ".join(month_label(m) for m in estimate.months)
        st.warning(
            f"🟡 Ostatnie 12 miesięcy ({window}): {count} z 12 na odczycie szacunkowym "
            f"({months}). Tauron oszacował stan licznika; kolejna Faktura albo korekta go "
            f"wyrównuje, ale okres zostaje oznaczony.{missing}"
        )
    elif missing:
        st.info(f"Ostatnie 12 miesięcy ({window}): żaden na odczycie szacunkowym.{missing}")
    else:
        st.success(f"🟢 Ostatnie 12 miesięcy ({window}): żaden miesiąc na odczycie szacunkowym.")
    for gap in timeline.gaps:
        st.error(
            f"Luka: brak Faktury {fmt.for_period(gap)} ({gap.days} dni). "
            "Wgraj brakującą Fakturę, żeby sumy obejmowały cały okres."
        )
    for overlap in timeline.overlaps:
        first, second = overlap.invoice_numbers
        st.warning(
            f"Nakładanie się: Faktury {first} i {second} rozliczają te same dni "
            f"({fmt.period(overlap.period)}), więc liczą się w sumach dwa razy. "
            "Jeśli jedna z nich jest błędna, usuń ją niżej."
        )
    st.caption(
        "Kliknij okres, żeby otworzyć Fakturę po ludzku. Kolor to Podstawa rozliczenia: "
        "🟢 odczyt rzeczywisty, 🟡 odczyt szacunkowy; ⚪ Prognozy (przerywany kontur) to "
        "zaliczki z harmonogramu, nie wchodzą do sum. Pas „Zastąpione”: Faktury, które "
        "zastąpiła Faktura korygująca (liczy się korekta). ◆ Nota obciążeniowa w dniu sprzedaży."
    )


def _entry(period: TimelinePeriod) -> dict[str, object]:
    document = f"{period.kind.value} {period.number}"
    if period.corrects:
        document += f" (koryguje {period.corrects})"
    if period.superseded_by:
        document += f" — zastąpiona przez {period.superseded_by}"
    return {
        "Okres": fmt.period(period.period),
        "Dokument": document,
        "Podstawa rozliczenia": fmt.BASIS_BADGES[period.basis],
        "Koszt okresu": fmt.zl(period.period_cost),
    }


def _render_invoices(
    context: FeatureContext, archive: FileArchive, timeline: InvoiceTimeline
) -> None:
    st.subheader("Faktury")
    periods = list(reversed(timeline.periods))
    numbers = [p.number for p in periods]
    st.dataframe(
        [_entry(p) for p in periods],
        hide_index=True,
        key=_INVOICE_LIST_KEY,
        on_select=partial(_open_from_list, numbers),
        selection_mode="single-row",
    )
    st.caption("Kliknij wiersz, żeby otworzyć Fakturę po ludzku.")

    with st.expander("Usuń Fakturę"):
        st.write(
            "Usuń Fakturę wgraną omyłkowo albo odczytaną błędnie. Znika z bazy i z archiwum "
            "plików, więc przebudowa jej nie przywróci; jej plik można wgrać ponownie."
        )
        number = st.selectbox(
            "Faktura",
            numbers,
            index=None,
            placeholder="Wybierz Fakturę",
            format_func=lambda n: next(
                f"{fmt.period(p.period)} · {p.kind.value} {p.number}"
                for p in periods
                if p.number == n
            ),
        )
        if st.button("Usuń Fakturę…", disabled=number is None):
            st.session_state[_PENDING_DELETE] = number
        pending = st.session_state.get(_PENDING_DELETE)
        if pending is not None:
            chosen = next(p for p in periods if p.number == pending)
            if _confirmed(_PENDING_DELETE, _delete_question(chosen), "Tak, usuń"):
                delete_invoice(context.repository, archive, pending)
                st.session_state[_DELETED] = pending
                st.rerun()


def _delete_question(period: TimelinePeriod) -> str:
    question = f"Na pewno usunąć Fakturę {period.number}? Tego nie da się cofnąć."
    if period.corrects:
        question += (
            f" To Faktura korygująca: po jej usunięciu w sumach znów liczy się "
            f"Faktura {period.corrects}."
        )
    if period.superseded_by:
        question += f" Koryguje ją Faktura {period.superseded_by}, która zostaje w aplikacji."
    return question


def _confirmed(key: str, question: str, yes: str) -> bool:
    """Pytanie z przyciskami „tak” i „Anuluj” pod kluczem ``key`` w ``st.session_state``;
    ``True`` po potwierdzeniu (klucz jest już usunięty)."""
    st.warning(question)
    confirm, cancel = st.columns(2)
    if confirm.button(yes, type="primary", key=f"{key}_yes"):
        st.session_state.pop(key, None)
        return True
    if cancel.button("Anuluj", key=f"{key}_cancel"):
        st.session_state.pop(key, None)
        st.rerun()
    return False


def _render_rebuild(context: FeatureContext, archive: FileArchive) -> None:
    st.subheader("Przebudowa bazy")
    st.write(
        "Odczytuje od nowa wszystkie pliki z archiwum (Faktury, Noty obciążeniowe, Raporty "
        "wartości godzinowych) wszystkich punktów poboru, np. po poprawce odczytu Faktur. "
        "Punkty poboru i ich ustawienia zostają. Plik, którego nie uda się odczytać, zostaje "
        "w archiwum i wraca przy kolejnej przebudowie."
    )
    if st.button("Przebuduj bazę z archiwum…"):
        st.session_state[_CONFIRM_REBUILD] = True
    if st.session_state.get(_CONFIRM_REBUILD) and _confirmed(
        _CONFIRM_REBUILD,
        "Przebudować bazę? To może potrwać kilkadziesiąt sekund. Dokumenty z plików, których "
        "nie uda się odczytać, znikną z aplikacji do kolejnej udanej przebudowy.",
        "Tak, przebuduj",
    ):
        with st.spinner("Odczytuję pliki z archiwum…"):
            st.session_state[_REBUILD_SUMMARY] = rebuild(context.repository, archive)
        st.rerun()
    summary = st.session_state.get(_REBUILD_SUMMARY)
    if summary is not None:
        render_summary(summary)
