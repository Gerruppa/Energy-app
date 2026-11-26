"""Opcje startu ``python -m pv_app``, które ustawiają otoczenie aplikacji."""

from datetime import date

import pytest

from pv_app.__main__ import configure
from pv_app.app.settings import TODAY_ENV, today


@pytest.fixture(autouse=True)
def restored_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """``configure`` zapisuje do ``os.environ``; ``setenv`` przed ``delenv`` sprawia, że
    monkeypatch przywraca zmienną po teście, także gdy jej wcześniej nie było."""
    monkeypatch.setenv(TODAY_ENV, "")
    monkeypatch.delenv(TODAY_ENV)


def test_today_option_sets_today_for_the_whole_app() -> None:
    configure(["--today", "2027-01-15", "--no-browser"])

    assert today() == date(2027, 1, 15)


def test_without_today_option_the_app_keeps_the_real_date() -> None:
    configure([])

    assert today() == date.today()


def test_invalid_today_option_stops_the_start_with_a_readable_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit):
        configure(["--today", "2027-02-30"])

    assert "RRRR-MM-DD" in capsys.readouterr().err


def test_invalid_today_in_environment_stops_the_start_with_a_readable_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv(TODAY_ENV, "jutro")

    with pytest.raises(SystemExit):
        configure([])

    assert TODAY_ENV in capsys.readouterr().err
