"""Kontrakt Repository: każdy adapter zachowuje się tak samo."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from pv_app.domain.metering_point import MeteringPoint
from pv_app.storage.in_memory import InMemoryRepository
from pv_app.storage.repository import Repository
from pv_app.storage.sqlite import SqliteRepository


@pytest.fixture(params=["in_memory", "sqlite"])
def repository(request: pytest.FixtureRequest, tmp_path: Path) -> Iterator[Repository]:
    if request.param == "in_memory":
        yield InMemoryRepository()
    else:
        repo = SqliteRepository(tmp_path / "pv.sqlite3")
        yield repo
        repo.close()


HOME = MeteringPoint(ppe_number="PL0000000000000000000001", name="Dom", slug="dom")


def test_new_repository_has_no_metering_points(repository: Repository) -> None:
    assert repository.list_metering_points() == []


def test_added_metering_point_can_be_listed(repository: Repository) -> None:
    repository.add_metering_point(HOME)

    assert repository.list_metering_points() == [HOME]
