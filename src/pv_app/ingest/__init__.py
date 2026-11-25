"""Pliki (Faktury PDF, Raporty wartości godzinowych xlsx) → obiekty domeny.

Jedno wejście: ``import_file`` (plik PDF albo xlsx), a dla surowych wierszy (ADR 0005)
``import_document`` (PDF) i ``import_sheet`` (arkusz xlsx).
"""

from pv_app.ingest.importer import import_document, import_file, import_sheet
from pv_app.ingest.result import ImportResult

__all__ = ["ImportResult", "import_document", "import_file", "import_sheet"]
