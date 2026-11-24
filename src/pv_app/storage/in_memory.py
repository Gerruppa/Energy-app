from pv_app.domain.invoice import Invoice
from pv_app.domain.metering_point import MeteringPoint


class InMemoryRepository:
    """Repository w pamięci, do testów funkcji."""

    def __init__(self) -> None:
        self._metering_points: list[MeteringPoint] = []
        self._invoices: list[Invoice] = []

    def add_metering_point(self, metering_point: MeteringPoint) -> None:
        self._metering_points.append(metering_point)

    def list_metering_points(self) -> list[MeteringPoint]:
        return list(self._metering_points)

    def add_invoice(self, invoice: Invoice) -> None:
        self._invoices.append(invoice)

    def list_invoices(self, ppe_number: str) -> list[Invoice]:
        return sorted(
            (i for i in self._invoices if i.header.ppe_number == ppe_number),
            key=lambda i: (i.header.billing_period.start, i.number),
        )
