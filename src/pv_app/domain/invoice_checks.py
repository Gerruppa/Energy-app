"""Kontrola sum Faktury: do bazy trafia tylko Faktura, której liczby się domykają."""

from decimal import Decimal

from pv_app.domain.formatting import kwh, zl
from pv_app.domain.invoice import Invoice, InvoiceSection

MONEY_TOLERANCE = Decimal("0.02")
"""Zaokrąglenia groszowe: Tauron liczy VAT od sumy, a brutto Pozycji od każdej osobno."""

ENERGY_BALANCE_TOLERANCE_KWH = Decimal("2")
"""Tolerancja bilansowania Magazynu energii: Tauron zaokrągla kWh po bilansowaniu godzinowym."""


def check_totals(invoice: Invoice) -> list[str]:
    """Opisy niezgodności po polsku; pusta lista = Faktura się zgadza."""
    problems: list[str] = []
    summary = invoice.summary

    for section, stated in (
        (InvoiceSection.SALES, summary.sales.gross),
        (InvoiceSection.DISTRIBUTION, summary.distribution.gross),
    ):
        lines = sum((x.gross for x in invoice.lines if x.section is section), Decimal(0))
        if abs(lines - stated) > MONEY_TOLERANCE:
            problems.append(
                f"Suma Pozycji faktury w sekcji „{section.value}” ({zl(lines)}) "
                f"nie zgadza się z podsumowaniem ({zl(stated)})."
            )

    all_lines = sum((x.gross for x in invoice.lines), Decimal(0))
    if abs(all_lines - summary.result.gross) > MONEY_TOLERANCE:
        problems.append(
            f"Suma Pozycji faktury ({zl(all_lines)}) nie zgadza się "
            f"z Wynikiem rozliczenia ({zl(summary.result.gross)})."
        )

    forecast = summary.previous_forecast.gross if summary.previous_forecast else Decimal(0)
    payments = summary.additional_payments or Decimal(0)
    expected_due = summary.result.gross + forecast - payments
    if abs(expected_due - summary.amount_due) > MONEY_TOLERANCE:
        problems.append(
            f"Do zapłaty ({zl(summary.amount_due)}) nie wynika z Wyniku rozliczenia, "
            f"Prognozy i wpłat ({zl(expected_due)})."
        )

    store = invoice.energy_settlement
    if store is not None:
        expected_end = store.store_start_kwh + store.exported_after_coefficient_kwh
        expected_end -= invoice.discount_kwh
        if abs(expected_end - store.store_end_kwh) > ENERGY_BALANCE_TOLERANCE_KWH:
            problems.append(
                "Bilans Magazynu energii się nie domyka: "
                f"{kwh(store.store_start_kwh)} na start"
                f" + {kwh(store.exported_after_coefficient_kwh)} przyrostu"
                f" − {kwh(invoice.discount_kwh)} Opustu = {kwh(expected_end)}, "
                f"a Faktura podaje {kwh(store.store_end_kwh)} na koniec."
            )
    return problems
