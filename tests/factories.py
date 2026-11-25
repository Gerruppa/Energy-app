"""Syntetyczne Faktury z wymyślonymi liczbami, do testów rozkładu i analiz."""

from dataclasses import replace
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from pv_app.domain.hourly_profile import HourlyReading
from pv_app.domain.invoice import (
    Amount,
    Correction,
    DateRange,
    DocumentKind,
    Forecast,
    Invoice,
    InvoiceLine,
    LineComponent,
    MeterDirection,
    ReadingType,
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
                exported_after_coefficient_kwh=Decimal(exported)
                * base.energy_settlement.discount_coefficient,
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


def correcting(original: Invoice, number: str) -> Invoice:
    """Faktura korygująca ``original`` za ten sam Okres rozliczeniowy, na odczycie rzeczywistym."""
    return replace(
        original,
        kind=DocumentKind.CORRECTING_INVOICE,
        header=replace(original.header, number=number, issue_date=date(2026, 11, 10)),
        readings=tuple(replace(r, reading_type=ReadingType.REMOTE) for r in original.readings),
        correction=Correction(
            corrected_invoice_number=original.number,
            corrected_invoice_issue_date=original.header.issue_date,
            reason="błędny odczyt",
            charged_result=Amount(None, None, Decimal("0")),
            charged_amount_due=Decimal("0"),
            difference=Decimal("0"),
            source=Source(number, 1),
            difference_source=Source(number, 2),
        ),
    )


def reading(
    hour_end: datetime, imported: str = "0.5", exported: str = "0.25", *, extra: bool = False
) -> HourlyReading:
    return HourlyReading(
        ppe_number=HOME,
        hour_end=hour_end,
        extra_hour=extra,
        imported_kwh=Decimal(imported),
        exported_kwh=Decimal(exported),
        unbalanced_imported_kwh=Decimal(imported) * 2,
        unbalanced_exported_kwh=Decimal(exported) * 2,
    )


def days(
    first: date, last: date, imported: str = "0.5", exported: str = "0.25"
) -> list[HourlyReading]:
    """Pełne doby od ``first`` do ``last``: godziny „1:00” … „0:00” następnego dnia, w dniu
    zmiany czasu 23 albo 25 godzin."""
    readings: list[HourlyReading] = []
    day = first
    while day <= last:
        for hour in range(1, 25):
            hour_end = datetime(day.year, day.month, day.day) + timedelta(hours=hour)
            if day == date(2026, 3, 29) and hour == 2:
                continue
            readings.append(reading(hour_end, imported, exported))
            if day == date(2026, 10, 25) and hour == 3:
                readings.append(reading(hour_end, imported, exported, extra=True))
        day += timedelta(days=1)
    return readings
