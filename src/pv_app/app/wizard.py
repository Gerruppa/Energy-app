"""Kreator „Dodaj punkt poboru”: logika bez Streamlita, żeby dało się ją testować."""

from pv_app.domain.invoice import Invoice, SettlementType
from pv_app.domain.metering_point import MeteringPoint, SiteIcon, make_slug
from pv_app.storage.repository import Repository


class MeteringPointAlreadyExists(Exception):
    pass


def add_metering_point_from_invoice(
    repository: Repository, invoice: Invoice, *, name: str, icon: SiteIcon, charges_car: bool
) -> MeteringPoint:
    """Tworzy PPE z danych pierwszej Faktury i odpowiedzi użytkownika, zapisuje oba."""
    existing = repository.list_metering_points()
    header = invoice.header
    if any(p.ppe_number == header.ppe_number for p in existing):
        raise MeteringPointAlreadyExists(header.ppe_number)
    point = MeteringPoint(
        ppe_number=header.ppe_number,
        name=name.strip(),
        slug=make_slug(name, {p.slug for p in existing}),
        icon=icon,
        charges_car=charges_car,
        address=header.address,
        net_metering=header.settlement_type is SettlementType.NET_METERING,
    )
    repository.add_metering_point(point)
    repository.add_invoice(invoice)
    return point
