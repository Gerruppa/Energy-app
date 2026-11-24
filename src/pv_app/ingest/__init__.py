"""Pliki (Faktury PDF, eksporty eLicznika) → obiekty domeny.

Jedno wejście: ``import_file`` (plik PDF) albo ``import_document`` (surowe wiersze, ADR 0005).
"""

from pv_app.ingest.importer import import_document, import_file
from pv_app.ingest.result import ImportResult

__all__ = ["ImportResult", "import_document", "import_file"]
