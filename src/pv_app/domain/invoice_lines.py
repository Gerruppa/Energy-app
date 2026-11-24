"""Klasyfikacja Pozycji faktury: nazwa z Faktury → składnik. Nowa nazwa = zmiana tylko tutaj."""

from pv_app.domain.invoice import LineComponent

_COMPONENTS_BY_NAME = {
    "energia czynna": LineComponent.ACTIVE_ENERGY,
    "energia elektryczna czynna": LineComponent.ACTIVE_ENERGY,
    "składnik zmienny stawki sieciowej": LineComponent.VARIABLE_NETWORK,
    "stawka jakościowa": LineComponent.QUALITY,
    "opłata oze": LineComponent.OZE,
    "opłata kogeneracyjna": LineComponent.COGENERATION,
    "składnik stały stawki sieciowej": LineComponent.FIXED_NETWORK,
    "stawka opłaty przejściowej": LineComponent.TRANSITIONAL,
    "opłata przejściowa": LineComponent.TRANSITIONAL,
    "stawka opłaty abonamentowej": LineComponent.SUBSCRIPTION,
    "opłata abonamentowa": LineComponent.SUBSCRIPTION,
    "opłata mocowa": LineComponent.CAPACITY,
}


def classify_line(name: str) -> LineComponent | None:
    """Składnik dla nazwy Pozycji faktury; ``None``, gdy nazwa jest nieznana."""
    return _COMPONENTS_BY_NAME.get(" ".join(name.lower().split()))
