"""Liczby i daty w formacie z Faktur Tauron (``1 234,56``, ``31.10.2026`` lub ``31/10/2026``)."""

import re
from datetime import date
from decimal import Decimal

NUMBER = r"-?\d+(?: \d{3})*(?:,\d+)?"
"""Liczba z przecinkiem dziesiętnym i odstępem tysięcy albo bez, np. ``-1 234,56``, ``1500``."""

DATE = r"\d{2}[./]\d{2}[./]\d{4}"


def parse_number(text: str) -> Decimal:
    return Decimal(text.replace(" ", "").replace(",", "."))


def parse_date(text: str) -> date:
    day, month, year = re.split(r"[./]", text)
    return date(int(year), int(month), int(day))
