from pv_app.domain.metering_point import MeteringPoint


class InMemoryRepository:
    """Repository w pamięci, do testów funkcji."""

    def __init__(self) -> None:
        self._metering_points: list[MeteringPoint] = []

    def add_metering_point(self, metering_point: MeteringPoint) -> None:
        self._metering_points.append(metering_point)

    def list_metering_points(self) -> list[MeteringPoint]:
        return list(self._metering_points)
