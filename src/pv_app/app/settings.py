"""Położenie danych aplikacji: zawsze obok folderu aplikacji, żeby działała po skopiowaniu."""

import os
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[3]
"""Folder aplikacji (ten, w którym leży ``Start.bat``)."""

DATA_DIR_ENV = "PV_APP_DATA_DIR"


def data_dir() -> Path:
    """Katalog danych (baza, archiwum plików); poza gitem (ADR 0004)."""
    override = os.environ.get(DATA_DIR_ENV)
    return Path(override) if override else APP_ROOT / "data"


def database_path() -> Path:
    return data_dir() / "pv_app.sqlite3"


def archive_dir() -> Path:
    """Kopie wgranych plików, z których da się odbudować bazę."""
    return data_dir() / "archive"
