"""Grupy kosztów: Pozycje faktury zebrane w pięć grup z ``GLOSSARY.md``."""

from decimal import Decimal
from enum import StrEnum

from pv_app.domain.invoice import Invoice, InvoiceLine, LineComponent


class CostGroup(StrEnum):
    """Grupa kosztów: Pozycje faktury zebrane tak, jak opisuje je „Faktura po ludzku”."""

    ENERGY = "Energia"
    VARIABLE_DISTRIBUTION = "Dystrybucja zmienna"
    PER_KWH_FEES = "Opłaty od kWh"
    CAPACITY = "Opłata mocowa"
    FIXED_FEES = "Opłaty stałe"
    UNRECOGNIZED = "Pozycje nierozpoznane"
    """Tylko gdy import nie rozpoznał nazwy którejś Pozycji faktury."""

    @property
    def is_variable(self) -> bool:
        """Grupa Składników zmiennych (od kWh); Pozycje nierozpoznane nie są żadnym składnikiem."""
        return self in _VARIABLE_GROUPS

    @property
    def split_by_days(self) -> bool:
        """W rozkładzie na miesiące dzielona po dniach (Składniki zmienne i Pozycje
        nierozpoznane); inaczej po równo na miesiące (Składniki stałe)."""
        return self.is_variable or self is CostGroup.UNRECOGNIZED


_VARIABLE_GROUPS = frozenset(
    {CostGroup.ENERGY, CostGroup.VARIABLE_DISTRIBUTION, CostGroup.PER_KWH_FEES}
)

_GROUP_OF_COMPONENT = {
    LineComponent.ACTIVE_ENERGY: CostGroup.ENERGY,
    LineComponent.VARIABLE_NETWORK: CostGroup.VARIABLE_DISTRIBUTION,
    LineComponent.QUALITY: CostGroup.VARIABLE_DISTRIBUTION,
    LineComponent.OZE: CostGroup.PER_KWH_FEES,
    LineComponent.COGENERATION: CostGroup.PER_KWH_FEES,
    LineComponent.CAPACITY: CostGroup.CAPACITY,
    LineComponent.FIXED_NETWORK: CostGroup.FIXED_FEES,
    LineComponent.TRANSITIONAL: CostGroup.FIXED_FEES,
    LineComponent.SUBSCRIPTION: CostGroup.FIXED_FEES,
}


def cost_group(line: InvoiceLine) -> CostGroup:
    if line.component is None:
        return CostGroup.UNRECOGNIZED
    return _GROUP_OF_COMPONENT[line.component]


def group_totals(invoice: Invoice) -> dict[CostGroup, Decimal]:
    """Suma brutto Pozycji faktury w każdej grupie: pięć grup w stałej kolejności (także
    puste), plus Pozycje nierozpoznane, gdy są."""
    totals: dict[CostGroup, Decimal] = {
        group: Decimal("0.00") for group in CostGroup if group is not CostGroup.UNRECOGNIZED
    }
    for line in invoice.lines:
        group = cost_group(line)
        totals[group] = totals.get(group, Decimal("0.00")) + line.gross
    return totals
