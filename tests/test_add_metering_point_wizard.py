"""Kreator „Dodaj punkt poboru”: z pierwszej Faktury i odpowiedzi użytkownika powstaje PPE."""

from pathlib import Path

import pytest

from pv_app.app.wizard import MeteringPointAlreadyExists, add_metering_point_from_invoice
from pv_app.domain.invoice import Invoice
from pv_app.domain.metering_point import MeteringPoint, SiteIcon
from pv_app.ingest import import_document
from pv_app.ingest.raw import RawDocument
from pv_app.storage.in_memory import InMemoryRepository

FIXTURES = Path(__file__).parent / "fixtures"


def fixture_invoice(name: str) -> Invoice:
    invoice = import_document(RawDocument.from_json(FIXTURES / f"{name}.json")).invoice
    assert invoice is not None
    return invoice


def test_creates_metering_point_from_invoice_and_saves_the_invoice() -> None:
    repository = InMemoryRepository()
    invoice = fixture_invoice("new_layout_net_metering_monthly")

    point = add_metering_point_from_invoice(
        repository, invoice, name="Dom rodziców", icon=SiteIcon.HOUSE, charges_car=True
    )

    assert point == MeteringPoint(
        ppe_number="590000000000000001",
        name="Dom rodziców",
        slug="dom-rodzicow",
        icon=SiteIcon.HOUSE,
        charges_car=True,
        address="UL. PRZYKŁADOWA 1, 00-001 TESTOWO",
        net_metering=True,
    )
    assert repository.list_metering_points() == [point]
    assert repository.list_invoices(point.ppe_number) == [invoice]


def test_metering_point_without_photovoltaics_is_not_net_metering() -> None:
    repository = InMemoryRepository()

    point = add_metering_point_from_invoice(
        repository,
        fixture_invoice("new_layout_standard_half_year"),
        name="Mieszkanie",
        icon=SiteIcon.FLAT,
        charges_car=False,
    )

    assert point.net_metering is False
    assert point.slug == "mieszkanie"


def test_second_point_with_the_same_name_gets_a_distinct_address() -> None:
    repository = InMemoryRepository()
    add_metering_point_from_invoice(
        repository,
        fixture_invoice("new_layout_net_metering_monthly"),
        name="Dom",
        icon=SiteIcon.HOUSE,
        charges_car=False,
    )

    second = add_metering_point_from_invoice(
        repository,
        fixture_invoice("new_layout_standard_half_year"),
        name="Dom",
        icon=SiteIcon.OTHER,
        charges_car=False,
    )

    assert second.slug == "dom-2"


def test_refuses_to_add_the_same_metering_point_twice() -> None:
    repository = InMemoryRepository()
    invoice = fixture_invoice("new_layout_net_metering_monthly")
    add_metering_point_from_invoice(
        repository, invoice, name="Dom", icon=SiteIcon.HOUSE, charges_car=False
    )

    with pytest.raises(MeteringPointAlreadyExists):
        add_metering_point_from_invoice(
            repository, invoice, name="Dom", icon=SiteIcon.HOUSE, charges_car=False
        )
