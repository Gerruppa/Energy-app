"""Górna część Przeglądu: status Faktur, Saldo, najbliższa płatność i ostatnia Faktura.

Czyste analizy na ``Repository``. Status i najbliższa płatność zależą od dnia „dziś”, który
podaje wywołujący; Saldo i ostatnia Faktura dotyczą końca Okresu widoku.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from itertools import pairwise

from pv_app.domain.invoice import DateRange, Forecast, Invoice, SettlementBasis, Source
from pv_app.domain.period_cost import PeriodCosts, superseded_invoices
from pv_app.domain.view_period import calendar_month, last_day, month_index
from pv_app.features.balance import balance_history, invoice_balance, notes_after
from pv_app.features.base import Filters
from pv_app.features.monthly import History
from pv_app.storage.repository import Repository

INVOICE_ISSUE_DAYS = 14
"""Zwykły czas wystawienia Faktury po końcu Okresu rozliczeniowego (Brakująca Faktura)."""


class StatusKind(StrEnum):
    CURRENT = "aktualne"
    MISSING = "Brakująca Faktura"
    ESTIMATED = "odczyt szacunkowy"


@dataclass(frozen=True)
class InvoiceStatus:
    kind: StatusKind
    last_invoice: str
    """Numer ostatniej Faktury (z najpóźniejszym Okresem rozliczeniowym)."""
    expected_period: DateRange
    """Następny Okres rozliczeniowy: miesiąc albo do końca harmonogramu Prognoz."""
    expected_by: date
    """Do kiedy zwykle przychodzi Faktura za ``expected_period``."""


def _settled(invoices: list[Invoice]) -> list[Invoice]:
    """Faktury do obliczeń (bez zastąpionych), od najwcześniej kończącego się okresu."""
    superseded = superseded_invoices(invoices)
    kept = [i for i in invoices if i.number not in superseded]
    return sorted(kept, key=lambda i: (i.header.billing_period.end, i.header.issue_date))


def _months(period: DateRange) -> int:
    return month_index(period.end) - month_index(period.start) + 1


def invoice_status(repository: Repository, ppe_number: str, today: date) -> InvoiceStatus | None:
    """Czy Faktury są aktualne na ``today``; ``None`` bez Faktur."""
    invoices = repository.list_invoices(ppe_number)
    settled = _settled(invoices)
    if not settled:
        return None
    last = settled[-1]
    period = last.header.billing_period
    next_start = period.end + timedelta(days=1)
    forecasts = _schedule(last, invoices)
    schedule_end = max((f.period.end for f in forecasts), default=None)
    if schedule_end is not None and schedule_end >= next_start:
        expected_end = schedule_end
    else:
        months = last.header.billing_frequency_months or _months(period)
        expected_end = last_day(month_index(next_start) + months - 1)
    expected_by = expected_end + timedelta(days=INVOICE_ISSUE_DAYS)
    if today > expected_by:
        kind = StatusKind.MISSING
    elif last.settlement_basis is SettlementBasis.ESTIMATED_READING:
        kind = StatusKind.ESTIMATED
    else:
        kind = StatusKind.CURRENT
    return InvoiceStatus(kind, last.number, DateRange(next_start, expected_end), expected_by)


def _schedule(invoice: Invoice, invoices: list[Invoice]) -> tuple[Forecast, ...]:
    """Harmonogram Prognoz Faktury; Faktura korygująca go nie powtarza, więc dla niej
    harmonogram korygowanej Faktury."""
    if invoice.forecasts or invoice.correction is None:
        return invoice.forecasts
    number = invoice.correction.corrected_invoice_number
    return next((i.forecasts for i in invoices if i.number == number), ())


def _last_ended_by(invoices: list[Invoice], day: date) -> Invoice | None:
    """Ostatnia Faktura do obliczeń, której Okres rozliczeniowy skończył się do ``day``."""
    ended = [i for i in _settled(invoices) if i.header.billing_period.end <= day]
    return ended[-1] if ended else None


def _view_end(filters: Filters) -> date:
    dates = filters.view_period.dates
    return dates.end if dates is not None else date.max


@dataclass(frozen=True)
class Balance:
    """Saldo PPE po ostatniej Fakturze zakończonej do końca Okresu widoku."""

    amount: Decimal
    """Dodatnie = nadpłata (Tauron winien), ujemne = niedopłata."""
    from_account: bool
    """Saldo z Faktury; ``False``: Faktura go nie podaje, więc to tylko jej „do zapłaty /
    do zwrotu” (ze znakiem odwróconym: do zwrotu = nadpłata)."""
    invoice_number: str
    source: Source
    debit_notes: tuple[str, ...] = ()
    """Noty obciążeniowe wystawione po tej Fakturze (a przed następną), doliczone do Salda."""
    forecast_follows: bool = False
    """Faktura ma harmonogram Prognoz, więc niedopłata trafia do najbliższej Prognozy."""

    @property
    def overpaid(self) -> bool:
        return self.amount >= 0


def balance(repository: Repository, filters: Filters) -> Balance | None:
    """Saldo na koniec Okresu widoku; ``None`` bez Faktury zakończonej do tego dnia.

    Nota obciążeniowa liczy się w Saldzie od daty wystawienia: Noty wystawione po Fakturze,
    a przed kolejną Fakturą, zmieniają Saldo z Faktury o swoje „do zapłaty”."""
    invoices = repository.list_invoices(filters.ppe_number)
    invoice = _last_ended_by(invoices, _view_end(filters))
    if invoice is None:
        return None
    point = invoice_balance(invoice)
    notes = (
        notes_after(invoice, invoices, repository.list_debit_notes(filters.ppe_number))
        if point.from_account
        else []
    )
    return Balance(
        point.amount - sum((n.amount_due for n in notes), Decimal(0)),
        from_account=point.from_account,
        invoice_number=invoice.number,
        source=point.source,
        debit_notes=tuple(n.number for n in notes),
        forecast_follows=bool(invoice.forecasts),
    )


RISING_OVERPAYMENT_INVOICES = 3
"""Na tylu ostatnich Fakturach z rzędu nadpłata musi rosnąć, żeby kafelek Salda dał sygnał."""
COST_AVERAGE_MONTHS = 12
"""Z ilu ostatnich miesięcy średni Koszt okresu mówi, na ile starczy nadpłata."""


@dataclass(frozen=True)
class OverpaymentSignal:
    """Nadpłata rośnie, a harmonogram Prognoz przewiduje dalsze wpłaty."""

    overpayment: Decimal
    """Nadpłata z kafelka Salda (z Notami obciążeniowymi po ostatniej Fakturze)."""
    invoices: tuple[str, ...]
    """Faktury, na których nadpłata była większa niż na poprzedniej, od najstarszej."""
    average_monthly_cost: Decimal
    """Średni Koszt okresu na miesiąc z miesięcy objętych Fakturami w całości."""
    cost_months: int
    """Z ilu miesięcy (z ostatnich ``COST_AVERAGE_MONTHS``) jest średnia."""
    months_covered: int | None
    """Na ile miesięcy (zaokrąglone) wystarczy nadpłata; ``None`` przy średniej zero lub
    mniej."""


def overpayment_signal(
    repository: Repository, filters: Filters, today: date
) -> OverpaymentSignal | None:
    """Sygnał rosnącej nadpłaty dla kafelka Salda; ``None``, gdy nadpłata nie rosła na
    ``RISING_OVERPAYMENT_INVOICES`` ostatnich Fakturach zakończonych do końca Okresu widoku
    (każda z Saldem, większym niż na poprzedniej) albo gdy żadna Prognoza z harmonogramu
    ostatniej Faktury nie ma od ``today`` nic do zapłaty."""
    ppe = filters.ppe_number
    view_end = _view_end(filters)
    points = [
        p
        for p in balance_history(repository, ppe)
        if p.period is not None and p.period.end <= view_end
    ]
    recent = points[-(RISING_OVERPAYMENT_INVOICES + 1) :]
    if len(recent) <= RISING_OVERPAYMENT_INVOICES or not all(p.from_account for p in recent):
        return None
    # Niedopłata przed pierwszą z Faktur to zero nadpłaty: każda nadpłata jest od niej większa.
    if not all(
        later.amount > max(earlier.amount, Decimal(0)) for earlier, later in pairwise(recent)
    ):
        return None
    invoices = repository.list_invoices(ppe)
    last = _last_ended_by(invoices, view_end)
    if last is None or last.number != recent[-1].document:
        return None
    if not any(f.due_date >= today and f.amount_due > 0 for f in _schedule(last, invoices)):
        return None
    current = balance(repository, filters)
    if current is None or current.amount <= 0:
        return None
    end = month_index(last.header.billing_period.end)
    comparison = History(repository, ppe).compare(
        range(end - COST_AVERAGE_MONTHS + 1, end + 1), with_year_earlier=False
    )
    if comparison is None:
        return None
    totals = comparison[0]
    average = (totals.period_cost / len(totals.months)).quantize(Decimal("0.01"))
    months = (
        int((current.amount / average).to_integral_value(ROUND_HALF_UP)) if average > 0 else None
    )
    return OverpaymentSignal(
        overpayment=current.amount,
        invoices=tuple(p.document for p in recent[1:]),
        average_monthly_cost=average,
        cost_months=len(totals.months),
        months_covered=months,
    )


@dataclass(frozen=True)
class NextPayment:
    """Najbliższa płatność według ostatniej Faktury i jej harmonogramu Prognoz."""

    amount: Decimal
    """Do zapłaty; zero albo mniej = nic do zapłaty."""
    due_date: date | None
    """Termin Prognozy; ``None`` dla kwoty z samej Faktury (termin nie jest odczytywany)."""
    forecast_number: str | None
    """Prognoza, której dotyczy płatność; ``None``: „do zapłaty” z Faktury."""
    overpayment_used: Decimal
    """Ile z Prognozy pokrywa nadpłata."""
    source: Source

    @property
    def nothing_to_pay(self) -> bool:
        return self.amount <= 0


def next_payment(repository: Repository, ppe_number: str, today: date) -> NextPayment | None:
    """Pierwsza Prognoza z terminem od ``today``; bez harmonogramu „do zapłaty” z ostatniej
    Faktury. ``None`` bez Faktur albo gdy harmonogram się skończył (kwotę poda następna
    Faktura)."""
    invoices = repository.list_invoices(ppe_number)
    settled = _settled(invoices)
    if not settled:
        return None
    last = settled[-1]
    if forecasts := _schedule(last, invoices):
        upcoming = sorted((f for f in forecasts if f.due_date >= today), key=lambda f: f.due_date)
        if not upcoming:
            return None
        forecast = upcoming[0]
        return NextPayment(
            amount=forecast.amount_due,
            due_date=forecast.due_date,
            forecast_number=forecast.number,
            overpayment_used=min(forecast.gross, max(Decimal(0), -forecast.balance_adjustment)),
            source=forecast.source,
        )
    return NextPayment(
        amount=last.amount_due,
        due_date=None,
        forecast_number=None,
        overpayment_used=Decimal(0),
        source=last.summary.source,
    )


@dataclass(frozen=True)
class LastInvoice:
    """Ostatnia Faktura zakończona do końca Okresu widoku: kafelek i zdanie na start."""

    number: str
    period: DateRange
    """Okres rozliczeniowy."""
    period_cost: Decimal
    """Koszt okresu: po Bonifikatach z Faktury i z Not obciążeniowych za ten okres."""
    basis: SettlementBasis
    imported_kwh: Decimal
    exported_kwh: Decimal | None
    amount_due: Decimal
    """Do zapłaty po tej Fakturze; zero albo mniej = pokryta z nadpłaty."""
    cost_source: Source
    """Strona z Wynikiem rozliczenia."""
    energy_source: Source

    @property
    def month(self) -> int | None:
        """``month_index`` okresu, gdy to dokładnie jeden miesiąc kalendarzowy."""
        return calendar_month(self.period)


def last_invoice(repository: Repository, filters: Filters) -> LastInvoice | None:
    """Ostatnia Faktura do obliczeń zakończona do końca Okresu widoku; ``None`` bez takiej."""
    costs = PeriodCosts(
        invoices=repository.list_invoices(filters.ppe_number),
        debit_notes=repository.list_debit_notes(filters.ppe_number),
    )
    invoice = _last_ended_by(list(costs.invoices), _view_end(filters))
    if invoice is None:
        return None
    return LastInvoice(
        number=invoice.number,
        period=invoice.header.billing_period,
        period_cost=costs.period_cost(invoice),
        basis=invoice.settlement_basis,
        imported_kwh=invoice.imported_kwh,
        exported_kwh=invoice.exported_kwh,
        amount_due=invoice.amount_due,
        cost_source=invoice.summary.source,
        energy_source=invoice.energy_source,
    )
