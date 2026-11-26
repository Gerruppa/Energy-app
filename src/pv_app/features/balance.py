"""Saldo w czasie: stan rozrachunku z Tauronem po każdej Fakturze i Nocie obciążeniowej.

Wspólne dla zakładek (wykres w Koszty i Faktury, sygnał rosnącej nadpłaty w Przeglądzie);
czyste analizy na ``Repository``.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from pv_app.domain.debit_note import DebitNote
from pv_app.domain.invoice import DateRange, Invoice, SettlementBasis, Source
from pv_app.domain.period_cost import superseded_invoices
from pv_app.storage.repository import Repository


@dataclass(frozen=True)
class BalancePoint:
    """Saldo po jednym dokumencie, w dniu jego wystawienia."""

    day: date
    """Data wystawienia Faktury albo Noty obciążeniowej."""
    amount: Decimal
    """Dodatnie = nadpłata (Tauron winien), ujemne = niedopłata."""
    from_account: bool
    """Saldo z Faktury (dla Noty: Saldo poprzedniej Faktury zmienione przez Noty);
    ``False``: Faktura go nie podaje, więc to tylko jej „do zapłaty / do zwrotu” (ze znakiem
    odwróconym: do zwrotu = nadpłata)."""
    document: str
    """Numer Faktury albo Noty obciążeniowej."""
    source: Source
    basis: SettlementBasis | None
    """Podstawa rozliczenia Faktury; ``None`` dla Noty obciążeniowej."""
    period: DateRange | None
    """Okres rozliczeniowy Faktury; ``None`` dla Noty obciążeniowej."""

    @property
    def is_debit_note(self) -> bool:
        return self.basis is None


def settled_invoices(invoices: list[Invoice]) -> list[Invoice]:
    """Faktury do obliczeń (bez zastąpionych) w kolejności wystawienia."""
    superseded = superseded_invoices(invoices)
    kept = [i for i in invoices if i.number not in superseded]
    return sorted(kept, key=lambda i: (i.header.issue_date, i.header.billing_period.end))


def notes_after(
    invoice: Invoice, invoices: list[Invoice], notes: list[DebitNote]
) -> list[DebitNote]:
    """Noty obciążeniowe wystawione po ``invoice``, a przed kolejną Fakturą PPE, od
    najwcześniejszej: zmieniają Saldo z ``invoice`` (Nota liczy się w Saldzie od daty
    wystawienia; Saldo następnej Faktury już je zawiera)."""
    issued = invoice.header.issue_date
    later = [i.header.issue_date for i in invoices if i.header.issue_date > issued]
    until = min(later, default=date.max)
    return sorted((n for n in notes if issued < n.issue_date < until), key=lambda n: n.issue_date)


def balance_history(repository: Repository, ppe_number: str) -> list[BalancePoint]:
    """Saldo po każdej niezastąpionej Fakturze PPE i po Notach obciążeniowych wystawionych po
    Fakturze z Saldem, od najwcześniej wystawionego dokumentu. Po Fakturze bez Salda Noty nie
    dostają punktu: stan konta nie jest znany."""
    invoices = repository.list_invoices(ppe_number)
    notes = repository.list_debit_notes(ppe_number)
    points = []
    for invoice in settled_invoices(invoices):
        point = invoice_balance(invoice)
        points.append(point)
        if not point.from_account:
            continue
        amount = point.amount
        for note in notes_after(invoice, invoices, notes):
            amount -= note.amount_due
            points.append(
                BalancePoint(
                    day=note.issue_date,
                    amount=amount,
                    from_account=True,
                    document=note.number,
                    source=note.source,
                    basis=None,
                    period=None,
                )
            )
    return points


def invoice_balance(invoice: Invoice) -> BalancePoint:
    """Saldo z Faktury; gdy Faktura go nie podaje, tylko jej „do zapłaty / do zwrotu” (dla
    Faktury korygującej ze strony z różnicą po korekcie)."""
    account = invoice.summary.account_balance
    if account is None and invoice.correction is not None:
        source = invoice.correction.difference_source
    else:
        source = invoice.summary.source
    return BalancePoint(
        day=invoice.header.issue_date,
        amount=account if account is not None else -invoice.amount_due,
        from_account=account is not None,
        document=invoice.number,
        source=source,
        basis=invoice.settlement_basis,
        period=invoice.header.billing_period,
    )
