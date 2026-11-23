from typing import Protocol

from pv_app.domain.metering_point import MeteringPoint


class Repository(Protocol):
    """Zapis obiektów domeny i zapytania potrzebne funkcjom dashboardu."""

    def add_metering_point(self, metering_point: MeteringPoint) -> None: ...

    def list_metering_points(self) -> list[MeteringPoint]: ...
