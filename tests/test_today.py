"""„Dziś” aplikacji: prawdziwa data albo ustawiona z zewnątrz (``--today``, ``PV_APP_TODAY``)."""

from datetime import date

import pytest

from pv_app.app.settings import TODAY_ENV, today


def test_today_is_the_real_date_without_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(TODAY_ENV, raising=False)

    assert today() == date.today()


def test_today_can_be_overridden(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(TODAY_ENV, "2027-01-15")

    assert today() == date(2027, 1, 15)


@pytest.mark.parametrize(
    "text", ["2027-13-01", "2027-02-30", "15.01.2027", "20270115", "2027-1-5", "jutro"]
)
def test_invalid_override_is_a_readable_error(monkeypatch: pytest.MonkeyPatch, text: str) -> None:
    monkeypatch.setenv(TODAY_ENV, text)

    with pytest.raises(ValueError, match=f"{TODAY_ENV}.*RRRR-MM-DD"):
        today()
