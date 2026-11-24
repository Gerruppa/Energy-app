from functools import partial

import streamlit as st

from pv_app.domain.metering_point import MeteringPoint
from pv_app.features import formatting as fmt
from pv_app.features.base import FeatureContext
from pv_app.features.costs.analysis import (
    DebitNoteListRow,
    InvoiceListRow,
    debit_note_list,
    invoice_list,
)
from pv_app.features.navigation import open_invoice


class CostsFeature:
    id = "koszty"
    title = "Koszty i Faktury"
    order = 30

    def is_available(self, metering_point: MeteringPoint) -> bool:
        return True

    def render(self, context: FeatureContext) -> None:
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
                "się korekta. 🟢 odczyt rzeczywisty, 🟡 odczyt szacunkowy."
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
    entry: dict[str, object] = {
        "Okres": fmt.period(row.period),
        "Dni": row.period.days,
        "Dokument": document,
        "Podstawa rozliczenia": fmt.BASIS_BADGES[row.basis],
        "Pobrane z sieci": fmt.kwh(row.imported_kwh),
    }
    if point.net_metering:
        entry["Oddane do sieci"] = (
            fmt.kwh(row.exported_kwh) if row.exported_kwh is not None else "—"
        )
    entry["Koszt okresu"] = fmt.zl(row.period_cost)
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
