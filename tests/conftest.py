"""Wspólne fixture'y testów."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from pv_app.app.settings import DATA_DIR_ENV, TODAY_ENV

MAIN = str(Path(__file__).resolve().parent.parent / "src" / "pv_app" / "app" / "main.py")


@pytest.fixture
def empty_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv(DATA_DIR_ENV, str(tmp_path))
    return tmp_path


APP_TODAY = "2026-11-20"
"""„Dziś” aplikacji w testach AppTest: Faktura za październik 2026 z fixture'ów jest aktualna.
Test stanu zależnego od daty ustawia własną datę przez ``monkeypatch.setenv(TODAY_ENV, …)``."""


@pytest.fixture
def app(empty_data_dir: Path, monkeypatch: pytest.MonkeyPatch) -> AppTest:
    """Aplikacja na pustym katalogu danych i stałym „dziś” (``APP_TODAY``); zapisz dane do bazy,
    potem wywołaj ``.run()``.

    Timeout 30 s, bo pierwsze ``st.dataframe`` importuje pandas dłużej niż domyślne 3 s.
    """
    monkeypatch.setenv(TODAY_ENV, APP_TODAY)
    return AppTest.from_file(MAIN, default_timeout=30)
