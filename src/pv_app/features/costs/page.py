import streamlit as st

from pv_app.domain.metering_point import MeteringPoint
from pv_app.features import formatting as fmt
from pv_app.features.base import FeatureContext
from pv_app.features.costs.analysis import invoice_list


class CostsFeature:
    id = "koszty"
    title = "Koszty i Faktury"
    order = 30

    def is_available(self, metering_point: MeteringPoint) -> bool:
        return True

    def render(self, context: FeatureContext) -> None:
        point = context.metering_point
        rows = invoice_list(context.repository, point.ppe_number)
        st.subheader("Faktury")
        if not rows:
            st.info("Brak Faktur dla tego punktu poboru.")
            return
        table = []
        for row in rows:
            entry = {
                "Okres": fmt.period(row.period),
                "Dni": row.period.days,
                "Dokument": f"{row.kind.value} {row.number}",
                "Podstawa rozliczenia": fmt.BASIS_BADGES[row.basis],
                "Pobrane z sieci": fmt.kwh(row.imported_kwh),
            }
            if point.net_metering:
                entry["Oddane do sieci"] = (
                    fmt.kwh(row.exported_kwh) if row.exported_kwh is not None else "—"
                )
            entry["Koszt okresu"] = fmt.zl(row.period_cost)
            entry["Źródło"] = fmt.source(row.source)
            table.append(entry)
        st.dataframe(table, hide_index=True)
        st.caption(
            "Koszt okresu to Wynik rozliczenia brutto z Faktury (sprzedaż + dystrybucja), "
            "bez Prognoz i nadpłat. 🟢 odczyt rzeczywisty, 🟡 odczyt szacunkowy."
        )
