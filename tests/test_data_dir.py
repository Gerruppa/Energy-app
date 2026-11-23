"""Katalog danych leży obok aplikacji, niezależnie od katalogu roboczego."""

from pathlib import Path

import pytest

from pv_app.app.settings import DATA_DIR_ENV, data_dir

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_data_dir_is_next_to_the_app_whatever_the_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(DATA_DIR_ENV, raising=False)
    monkeypatch.chdir(tmp_path)

    assert data_dir() == PROJECT_ROOT / "data"


def test_data_dir_can_be_overridden(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(DATA_DIR_ENV, str(tmp_path))

    assert data_dir() == tmp_path
