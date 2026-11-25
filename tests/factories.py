"""Syntetyczne Faktury z wymyślonymi liczbami, do testów rozkładu i analiz."""

from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path

from pv_app.domain.invoice import (
    DateRange,
    Forecast,
    Invoice,
    InvoiceLine,
    LineComponent,
    MeterDirection,
    Source,
)
from pv_app.ingest import import_document
from pv_app.ingest.raw import RawDocument

FIXTURES = Path(__file__).parent / "fixtures"
HOME = "590000000000000001"


def invoice_for(
    period: DateRange,
    imported: str,
    exported: str | None = None,
    *,
    number: str | None = None,
    variable_gross: str = "0",
    fixed_gross: str = "0",
    same_period_last_year: str | None = None,
) -> Invoice:
    """Faktura PPE ``HOME`` za ``period`` z jedną Pozycją faktury zmienną i jedną stałą;
    kWh na stronie 4, Wynik rozliczenia na stronie 3.

    Bez ``exported`` Faktura nie ma Rozliczenia OZE (PPE bez fotowoltaiki); Koszt okresu
    to suma obu Pozycji.
    """
    base = import_document(
        RawDocument.from_json(FIXTURES / "new_layout_net_metering_monthly.json")
    ).invoice
    assert base is not None and base.energy_settlement is not None
    number = number or f"T/{period.start:%Y%m%d}"
    template = base.lines[0]

    def line(component: LineComponent, gross: str) -> InvoiceLine:
        return replace(template, component=component, gross=Decimal(gross))

    import_reading = next(r for r in base.readings if r.direction is MeterDirection.IMPORT)
    total = Decimal(variable_gross) + Decimal(fixed_gross)
    last_year = Decimal(same_period_last_year) if same_period_last_year is not None else None
    return replace(
        base,
        header=replace(base.header, number=number, billing_period=period),
        readings=(
            replace(import_reading, quantity_kwh=Decimal(imported), source=Source(number, 4)),
        ),
        energy_settlement=(
            replace(
                base.energy_settlement,
                imported_kwh=Decimal(imported),
                exported_kwh=Decimal(exported),
                source=Source(number, 4),
            )
            if exported is not None
            else None
        ),
        lines=(
            line(LineComponent.VARIABLE_NETWORK, variable_gross),
            line(LineComponent.CAPACITY, fixed_gross),
        ),
        summary=replace(
            base.summary,
            result=replace(base.summary.result, gross=total),
            source=Source(number, 3),
            same_period_last_year_kwh=last_year,
            same_period_last_year_source=Source(number, 2) if last_year is not None else None,
        ),
    )


def store_invoice(
    period: DateRange,
    start: str,
    credited: str,
    end: str,
    *,
    number: str | None = None,
    exported: str | None = None,
    discount: str | None = None,
) -> Invoice:
    """Faktura PPE ``HOME`` z ruchem w Magazynie energii: na start, przyrost (Energia oddana
    × 0,8), na koniec; Rozliczenie OZE na stronie 4. Energia pobrana 100 kWh, z tego
    ``discount`` kWh pokrył Magazyn energii (Opust; domyślnie na start + przyrost − na koniec),
    a reszta to energia czynna na Fakturze."""
    exported = exported or str(Decimal(credited) / Decimal("0.8"))
    invoice = invoice_for(period, "100", exported, number=number)
    assert invoice.energy_settlement is not None
    opust = (
        Decimal(discount)
        if discount is not None
        else Decimal(start) + Decimal(credited) - Decimal(end)
    )
    active_energy = replace(
        invoice.lines[0],
        component=LineComponent.ACTIVE_ENERGY,
        quantity=invoice.imported_kwh - opust,
        gross=Decimal(0),
    )
    return replace(
        invoice,
        lines=(*invoice.lines, active_energy),
        energy_settlement=replace(
            invoice.energy_settlement,
            store_start_kwh=Decimal(start),
            discount_coefficient=Decimal("0.8"),
            exported_after_coefficient_kwh=Decimal(credited),
            seller_share_kwh=Decimal(exported) - Decimal(credited),
            store_end_kwh=Decimal(end),
        ),
    )


def forecast(
    number: str,
    period: DateRange,
    due: date,
    gross: str = "100.00",
    import_kwh: str = "100",
    balance_adjustment: str = "0.00",
) -> Forecast:
    """Prognoza z wymyślonymi kwotami; do zapłaty = brutto + doliczone Saldo."""
    return Forecast(
        number=number,
        period=period,
        import_kwh=Decimal(import_kwh),
        export_kwh=None,
        net=Decimal(gross),
        vat=Decimal(0),
        gross=Decimal(gross),
        discount=Decimal(0),
        balance_adjustment=Decimal(balance_adjustment),
        amount_due=max(Decimal(0), Decimal(gross) + Decimal(balance_adjustment)),
        due_date=due,
        source=Source(number.rsplit("/", 1)[0], 2),
    )
