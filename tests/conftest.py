"""Wspólne fixture'y testów."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from pv_app.app.settings import DATA_DIR_ENV

MAIN = str(Path(__file__).resolve().parent.parent / "src" / "pv_app" / "app" / "main.py")


@pytest.fixture
def empty_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv(DATA_DIR_ENV, str(tmp_path))
    return tmp_path


@pytest.fixture
def app(empty_data_dir: Path) -> AppTest:
    """Aplikacja na pustym katalogu danych; zapisz dane do bazy, potem wywołaj ``.run()``.

    Timeout 30 s, bo pierwsze ``st.dataframe`` importuje pandas dłużej niż domyślne 3 s.
    """
    return AppTest.from_file(MAIN, default_timeout=30)
