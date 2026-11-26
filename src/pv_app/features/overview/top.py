"""Górna część Przeglądu: status Faktur, zdanie na start, pasek Magazynu energii i kafelki.

Rysowane w HTML (``st.html``), żeby mieć tekst 15 px, podpisy 13 px z kontrastem ≥ 4,5:1,
kafelki w dwóch kolumnach na telefonie i podpowiedzi „?”, które działają po stuknięciu
i z klawiatury (``<details>``). Liczby liczą analizy z ``tiles.py`` i ``EnergyStore``.
"""

from datetime import date
from decimal import Decimal
from html import escape

import streamlit as st

from pv_app.domain.energy_store import EXPIRING_SOON_MONTHS, Portion
from pv_app.domain.invoice import SettlementBasis
from pv_app.features import formatting as fmt
from pv_app.features.base import FeatureContext
from pv_app.features.navigation import invoice_href, open_import
from pv_app.features.overview.analysis import StoreTile, store_tile
from pv_app.features.overview.tiles import (
    COST_AVERAGE_MONTHS,
    Balance,
    InvoiceStatus,
    LastInvoice,
    NextPayment,
    OverpaymentSignal,
    StatusKind,
    balance,
    invoice_status,
    last_invoice,
    next_payment,
    overpayment_signal,
)
from pv_app.features.store_expiry import (
    ExpiryOutlook,
    lost_portions,
    outlook_help,
    outlook_line,
)
from pv_app.features.terms import ESTIMATE_HELP, FORECAST_HELP, store_help

# Tekst dziedziczy kolor z motywu Streamlita (jasny albo ciemny), tła są półprzezroczyste.
# Bursztyn = Magazyn energii, czerwień tylko dla wygasania i braków.
STYLE = """
<style>
.pv-top { font-size: 15px; line-height: 1.45; }
.pv-top b { font-weight: 600; }
.pv-lede { font-size: 20px; line-height: 1.45; max-width: 60ch; margin: 0; }
.pv-lede b { white-space: nowrap; }
.pv-card { background: rgba(128,128,128,.07); border: 1px solid rgba(128,128,128,.35);
  border-radius: 10px; padding: 12px 14px; }
.pv-hero { padding: 18px 20px 14px; }
.pv-hero-top { display: flex; justify-content: space-between; align-items: flex-end;
  gap: 8px 16px; flex-wrap: wrap; }
.pv-hero-v { font-size: 46px; font-weight: 600; line-height: 1.05; letter-spacing: -.02em;
  font-variant-numeric: tabular-nums; }
.pv-hero-v .u { font-size: .42em; font-weight: 500; margin-left: 6px; letter-spacing: 0; }
.pv-hero-delta { text-align: right; font-variant-numeric: tabular-nums; }
.pv-hero-delta .plus { font-weight: 600; }
.pv-tank { display: flex; gap: 3px; height: 34px; margin: 14px 0 10px; border-radius: 8px;
  overflow: hidden; background: rgba(128,128,128,.2); }
.pv-tank .seg { background: #e8a10c; min-width: 8px; }
.pv-tank .seg.urgent { background: repeating-linear-gradient(45deg, #c93c2e 0 4px,
  #e49a92 4px 8px); }
.pv-tank-legend { list-style: none; display: flex; flex-wrap: wrap; gap: 6px 20px;
  padding: 0; margin: 0; font-size: 13px; }
.pv-tank-legend li { display: flex; align-items: center; gap: 6px; margin: 0; }
.pv-tank-legend i { width: 12px; height: 12px; border-radius: 3px; background: #e8a10c;
  flex: none; }
.pv-tank-legend b { font-variant-numeric: tabular-nums; }
.pv-tank-legend li.urgent i { background: #c93c2e; }
.pv-expiry { list-style: none; padding: 10px 0 0; margin: 10px 0 0; font-size: 13px;
  border-top: 1px solid rgba(128,128,128,.35); }
.pv-expiry li { margin: 0 0 4px; }
.pv-expiry .pv-help { display: inline-block; vertical-align: top; }
.pv-what { margin-top: 12px; font-size: 14px; }
.pv-what summary { cursor: pointer; font-weight: 500; }
.pv-what p { margin: 6px 0 0; max-width: 70ch; }
.pv-facts { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.pv-fv { font-size: 22px; font-weight: 600; font-variant-numeric: tabular-nums;
  margin: 2px 0; }
.pv-fn, .pv-note { font-size: 13px; }
.pv-fn a { color: inherit; font-weight: 600; text-decoration: underline; }
.pv-signal { margin-top: 8px; padding-top: 8px; border-top: 1px solid rgba(128,128,128,.35);
  font-size: 13px; }
.pv-signal p { margin: 0 0 4px; }
.pv-help summary { list-style: none; cursor: pointer; font-size: 13px;
  display: inline-flex; align-items: center; gap: 6px; }
.pv-help summary::-webkit-details-marker { display: none; }
.pv-help summary:focus-visible { outline: 2px solid currentColor; outline-offset: 2px;
  border-radius: 4px; }
.pv-help .q { display: inline-block; width: 18px; height: 18px; line-height: 16px;
  text-align: center; border-radius: 50%; border: 1px solid currentColor; font-size: 13px; }
.pv-help[open] .q { border-width: 2px; line-height: 14px; font-weight: 700; }
.pv-help p { margin: 4px 0 6px; font-size: 13px; max-width: 60ch; }
@media (max-width: 640px) {
  .pv-facts { grid-template-columns: 1fr 1fr; gap: 8px; }
  .pv-fv { font-size: 18px; }
  .pv-hero-v { font-size: 38px; }
  .pv-hero-delta { text-align: left; }
  .pv-lede { font-size: 17px; }
}
[class*="st-key-pv_status_"] { border-left: 4px solid; border-radius: 8px;
  padding: 8px 10px 8px 14px; font-size: 15px; }
.st-key-pv_status_current { border-color: #1e8a4c; background: rgba(30,138,76,.12); }
.st-key-pv_status_missing { border-color: #c93c2e; background: rgba(201,60,46,.12); }
.st-key-pv_status_estimated { border-color: #e0a200; background: rgba(224,162,0,.16); }
</style>
"""

FADING_SUN = ("#e8a10c", "#d9a448", "#c6a773", "#b3a690")
"""Kolor „słońca” z malejącym nasyceniem dla kolejnych porcji Magazynu energii (bez
przezroczystości, żeby kontrast nie zależał od tła motywu)."""

BALANCE_HELP = (
    "Saldo to stan rozrachunku z Tauronem dla tego punktu poboru po ostatniej Fakturze. "
    "Nadpłata to pieniądze, które leżą na koncie w Tauronie i pokrywają kolejne płatności; "
    "nie przechodzą na inny punkt poboru. Niedopłata to kwota do dopłaty."
)
PAYMENT_HELP = "Z ostatniej Faktury i jej harmonogramu Prognoz. " + FORECAST_HELP
PERIOD_COST_HELP = (
    "Koszt okresu: Wynik rozliczenia brutto z Faktury (sprzedaż + dystrybucja) minus "
    "Bonifikaty. Bez Prognoz i nadpłat."
)


def render_top(context: FeatureContext, today: date) -> None:
    """Status Faktur, zdanie na start, (PPE z net-meteringiem) Magazyn energii i kafelki."""
    repository, filters = context.repository, context.filters
    st.html(STYLE)
    status = invoice_status(repository, filters.ppe_number, today)
    if status is not None:
        _render_status(status)
    last = last_invoice(repository, filters)
    if last is not None:
        st.html(f'<div class="pv-top"><p class="pv-lede">{lede(last, context)}</p></div>')
    if context.metering_point.net_metering:
        tile = store_tile(repository, filters)
        if tile is not None:
            st.html(f'<div class="pv-top">{_store_hero(tile)}</div>')
    if last is None:
        return
    facts = [
        _balance_fact(balance(repository, filters), overpayment_signal(repository, filters, today)),
        _payment_fact(next_payment(repository, filters.ppe_number, today)),
        _invoice_fact(last),
    ]
    st.html(f'<div class="pv-top"><div class="pv-facts">{"".join(facts)}</div></div>')


def _render_status(status: InvoiceStatus) -> None:
    expected = fmt.for_period(status.expected_period)
    with st.container(key=f"pv_status_{status.kind.name.lower()}"):
        match status.kind:
            case StatusKind.MISSING:
                text, button = st.columns([3, 1], vertical_alignment="center")
                text.html(
                    f"<span>⚠ <b>Brakuje Faktury {escape(expected)}.</b> Okres skończył się "
                    f"{fmt.day(status.expected_period.end)}, Faktura zwykle przychodzi do "
                    f"ok. {fmt.day(status.expected_by)}.</span>"
                )
                button.button("Wgraj Fakturę", on_click=open_import, key="status_import")
            case StatusKind.ESTIMATED:
                st.html(
                    "<span>◐ Ostatnia Faktura opiera się na <b>odczycie szacunkowym</b>. "
                    "Liczby mogą się zmienić przy następnym rozliczeniu.</span>"
                )
            case StatusKind.CURRENT:
                st.html(
                    f"<span>✓ Faktury są aktualne. Następna: Faktura {escape(expected)}, "
                    f"spodziewana ok. {fmt.day(status.expected_by)}.</span>"
                )


def _when(last: LastInvoice) -> str:
    month = last.month
    if month is not None:
        return fmt.in_month(month).capitalize()
    return f"Od {fmt.day(last.period.start)} do {fmt.day(last.period.end)}"


def lede(last: LastInvoice, context: FeatureContext) -> str:
    """Ostatni okres prostym językiem, z liczbami z ostatniej Faktury (HTML)."""
    when = _when(last)
    cost = f"<b>{fmt.zl(last.period_cost)}</b>"
    imported = f"<b>{fmt.kwh(last.imported_kwh)}</b>"
    if context.metering_point.net_metering and last.exported_kwh is not None:
        which = "ten miesiąc" if last.month is not None else "ten okres"
        covered = ", pokryta z nadpłaty" if last.amount_due <= 0 < last.period_cost else ""
        return (
            f"{when} panele oddały do sieci <b>{fmt.kwh(last.exported_kwh)}</b>, a z sieci "
            f"pobraliście {imported}. Faktura za {which}: {cost}{covered}."
        )
    text = f"{when} pobraliście z sieci {imported} za {cost}"
    if last.imported_kwh > 0:
        average = last.period_cost / last.imported_kwh
        text += f", czyli średnio <b>{fmt.zl(average)}</b> za kWh"
    return text + "."


def _help(label: str, text: str) -> str:
    return (
        f'<details class="pv-help"><summary>{escape(label)} '
        f'<span class="q" aria-label="wyjaśnienie">?</span></summary>'
        f"<p>{escape(text)}</p></details>"
    )


def _fact(label: str, help_text: str, value: str, note: str) -> str:
    return (
        f'<div class="pv-card">{_help(label, help_text)}'
        f'<div class="pv-fv">{value}</div><div class="pv-fn">{note}</div></div>'
    )


def signal_text(signal: OverpaymentSignal) -> str:
    """Zdanie o rosnącej nadpłacie pod kafelkiem Salda, z podpowiedzią „?” o wyliczeniu
    (HTML)."""
    why = (
        f"Nadpłata rosła na {len(signal.invoices)} ostatnich Fakturach "
        f"({', '.join(signal.invoices)}), a harmonogram Prognoz przewiduje dalsze wpłaty. "
    )
    average = (
        f"średni Koszt okresu {fmt.zl(signal.average_monthly_cost)} na miesiąc (z "
        f"{signal.cost_months} mies. z ostatnich {COST_AVERAGE_MONTHS} objętych Fakturami "
        "w całości)"
    )
    if signal.months_covered is None:
        label = "Nadpłata nie topnieje"
        how = f"Koszt okresu nie był większy od zera: {average}."
    else:
        months = signal.months_covered
        label = (
            "Wystarczy na niecały miesiąc" if months == 0 else f"Wystarczy na ok. {months} mies."
        )
        how = f"Nadpłata {fmt.zl(signal.overpayment)} podzielona przez {average}, zaokrąglone."
    return (
        '<div class="pv-signal"><p>↗ <b>Nadpłata rośnie.</b> Możecie poprosić Tauron '
        "o zwrot nadpłaty albo o obniżenie Prognoz.</p>"
        f"{_help(label, why + how)}</div>"
    )


def _balance_fact(result: Balance | None, signal: OverpaymentSignal | None = None) -> str:
    if result is None:
        return _fact("Saldo", BALANCE_HELP, "—", "brak Faktury do końca okresu")
    source = escape(fmt.source(result.source))
    notes = (
        f"; z Notą obciążeniową {escape(', '.join(result.debit_notes))}"
        if result.debit_notes
        else ""
    )
    if not result.from_account:
        label = "Do zwrotu według Faktury" if result.overpaid else "Do zapłaty według Faktury"
        return _fact(
            label,
            BALANCE_HELP,
            fmt.zl(abs(result.amount)),
            f"Faktura nie podaje Salda, tylko tę kwotę. {source}",
        )
    if result.amount == 0:
        return _fact("Saldo", BALANCE_HELP, fmt.zl(Decimal(0)), f"rozliczone na zero. {source}")
    if result.overpaid:
        extra = signal_text(signal) if signal is not None else ""
        return _fact(
            "Nadpłata w Tauronie",
            BALANCE_HELP,
            fmt.zl(result.amount),
            f"zostaje na koncie tego punktu poboru{notes}. {source}{extra}",
        )
    where = "doliczona do najbliższej Prognozy" if result.forecast_follows else "do dopłaty"
    return _fact("Niedopłata", BALANCE_HELP, fmt.zl(-result.amount), f"{where}{notes}. {source}")


def _payment_fact(payment: NextPayment | None) -> str:
    label = "Najbliższa płatność"
    if payment is None:
        return _fact(
            label,
            PAYMENT_HELP,
            "—",
            "harmonogram Prognoz się skończył; kwotę poda następna Faktura",
        )
    source = escape(fmt.source(payment.source))
    if payment.nothing_to_pay:
        note = (
            f"Prognoza z terminem {fmt.day(payment.due_date)} pokryta z nadpłaty"
            if payment.due_date is not None
            else "ostatnia Faktura pokryta z nadpłaty"
        )
        return _fact(label, PAYMENT_HELP, "Nic do zapłaty", f"{note}. {source}")
    if payment.due_date is not None:
        note = f"do {fmt.day(payment.due_date)}, według Prognozy"
        if payment.overpayment_used > 0:
            note += f"; {fmt.zl(payment.overpayment_used)} pokrywa nadpłata"
    else:
        note = "według ostatniej Faktury"
    return _fact(label, PAYMENT_HELP, fmt.zl(payment.amount), f"{note}. {source}")


def _invoice_link(number: str) -> str:
    return f'<a href="{escape(invoice_href(number))}" target="_self">Pokaż Fakturę</a>'


def _invoice_fact(last: LastInvoice) -> str:
    note = escape(fmt.period(last.period))
    if last.basis is not SettlementBasis.ACTUAL_READING:
        note += f" · {escape(fmt.BASIS_BADGES[last.basis])}"
    note += f" · {_invoice_link(last.number)}"
    return _fact("Ostatnia Faktura", PERIOD_COST_HELP, fmt.zl(last.period_cost), note)


def _number(kwh: Decimal) -> str:
    return fmt.kwh(kwh).removesuffix(" kWh")


def _portion_label(portion: Portion, urgent: bool) -> str:
    amount = f"<b>{fmt.kwh(portion.remaining_kwh)}</b>"
    if portion.expires_on is None:
        return f"{amount} sprzed pierwszej Faktury w aplikacji"
    word = "⚠ wygaśnie" if urgent else "ważne do"
    return f"{amount}&nbsp;{word} {fmt.day(portion.expires_on)}"


def _expiry_list(outlook: tuple[ExpiryOutlook, ...]) -> str:
    """Porcje wygasające wkrótce: zdanie o każdej z podpowiedzią „?” o wyliczeniu (HTML)."""
    items = [
        f"<li>{escape(outlook_line(item))} {_help('szacunek', outlook_help(item))}</li>"
        for item in outlook
    ]
    return f'<ul class="pv-expiry">{"".join(items)}</ul>' if items else ""


def _store_hero(tile: StoreTile) -> str:
    """Magazyn energii: stan z Faktury, pasek porcji od najwcześniej wygasającej i zdanie
    o każdej porcji wygasającej wkrótce."""
    state = tile.state
    lost = lost_portions(tile.outlook)
    movement = state.movement
    when = fmt.during(movement.period)
    portions = [p for p in state.portions if p.remaining_kwh > 0]
    segments, legend = [], []
    fade = 0
    for portion in portions:
        urgent = portion in lost
        if urgent:
            style = ""
        else:
            style = f"background:{FADING_SUN[min(len(FADING_SUN) - 1, fade)]}"
            fade += 1
        css = "seg urgent" if urgent else "seg"
        segments.append(f'<div class="{css}" style="flex:{portion.remaining_kwh};{style}"></div>')
        legend.append(
            f'<li class="{"urgent" if urgent else ""}"><i style="{style}"></i>'
            f"{_portion_label(portion, urgent)}</li>"
        )
    aria = ", ".join(
        f"{fmt.kwh(p.remaining_kwh)} ważne do {fmt.day(p.expires_on)}"
        for p in portions
        if p.expires_on is not None
    )
    bar = (
        f'<div class="pv-tank" role="img" aria-label="Magazyn energii: {escape(aria)}">'
        f'{"".join(segments)}</div><ul class="pv-tank-legend">{"".join(legend)}</ul>'
        if portions
        else ""
    )
    return f"""
<section class="pv-card pv-hero">
  <div class="pv-hero-top">
    <div>
      {_help("Magazyn energii", store_help(movement.discount_coefficient))}
      <div class="pv-hero-v">{_number(state.balance_kwh)}<span class="u">kWh</span></div>
      <div class="pv-note">stan na {fmt.day(state.as_of)}; {escape(fmt.source(state.source))}</div>
    </div>
    <div class="pv-hero-delta">
      <span class="plus">+{fmt.kwh(movement.credited_kwh)}</span> przybyło {when}<br>
      −{fmt.kwh(movement.discount_kwh)} pokryło prąd pobrany z sieci
    </div>
  </div>
  {bar}
  {_expiry_list(tile.outlook)}
  <details class="pv-what"><summary>Co to jest Magazyn energii?</summary>
    <p>{escape(store_help(movement.discount_coefficient))} Najpierw odbierana jest najstarsza
    porcja. Czerwone, kreskowane: porcje, które wygasną w {EXPIRING_SOON_MONTHS} miesiące, zanim
    zdążycie je odebrać (szacunek).
    {escape(ESTIMATE_HELP)}</p>
  </details>
</section>"""
