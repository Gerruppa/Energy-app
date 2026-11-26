"""Ustawienia z otoczenia: położenie danych (zawsze obok folderu aplikacji, żeby działała po
skopiowaniu) i „dziś” aplikacji."""

import os
import re
from datetime import date
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[3]
"""Folder aplikacji (ten, w którym leży ``Start.bat``)."""

DATA_DIR_ENV = "PV_APP_DATA_DIR"
TODAY_ENV = "PV_APP_TODAY"


def data_dir() -> Path:
    """Katalog danych (baza, archiwum plików); poza gitem (ADR 0004)."""
    override = os.environ.get(DATA_DIR_ENV)
    return Path(override) if override else APP_ROOT / "data"


def database_path() -> Path:
    return data_dir() / "pv_app.sqlite3"


def archive_dir() -> Path:
    """Kopie wgranych plików, z których da się odbudować bazę."""
    return data_dir() / "archive"


def parse_today(text: str) -> date:
    """Data „dziś” w zapisie RRRR-MM-DD; inny zapis albo nieistniejący dzień to ``ValueError``
    z czytelnym komunikatem."""
    try:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
            raise ValueError
        return date.fromisoformat(text)
    except ValueError:
        raise ValueError(
            f"nieprawidłowa data „{text}”: podaj ją jako RRRR-MM-DD, np. 2027-01-15"
        ) from None


def today() -> date:
    """„Dziś” aplikacji: jedyne źródło dzisiejszej daty dla stron i zakładek.

    ``PV_APP_TODAY`` (RRRR-MM-DD) albo prawdziwa data; nadpisanie pokazuje stany zależne od
    daty (Brakująca Faktura, Zaległy Profil godzinowy) i ustala datę w testach."""
    override = os.environ.get(TODAY_ENV)
    if not override:
        return date.today()
    try:
        return parse_today(override)
    except ValueError as error:
        raise ValueError(f"{TODAY_ENV}: {error}") from None
