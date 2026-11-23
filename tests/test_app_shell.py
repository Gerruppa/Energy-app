"""Powłoka Streamlit: co widzi użytkownik po starcie."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from pv_app.app.settings import DATA_DIR_ENV, database_path
from pv_app.domain.metering_point import MeteringPoint
from pv_app.storage.sqlite import SqliteRepository

MAIN = str(Path(__file__).resolve().parent.parent / "src" / "pv_app" / "app" / "main.py")


@pytest.fixture
def empty_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv(DATA_DIR_ENV, str(tmp_path))
    return tmp_path


def test_without_data_shows_welcome_screen_with_add_metering_point_button(
    empty_data_dir: Path,
) -> None:
    app = AppTest.from_file(MAIN).run()

    assert not app.exception
    assert [b.label for b in app.button] == ["Dodaj punkt poboru"]


def test_with_a_metering_point_does_not_show_welcome_screen(empty_data_dir: Path) -> None:
    repo = SqliteRepository(database_path())
    repo.add_metering_point(
        MeteringPoint(ppe_number="PL0000000000000000000001", name="Dom", slug="dom")
    )
    repo.close()

    app = AppTest.from_file(MAIN).run()

    assert not app.exception
    assert "Dodaj punkt poboru" not in [b.label for b in app.button]
    assert "Dom" in app.title[0].value
