from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

from pv_app.domain.debit_note import DebitNote
from pv_app.domain.hourly_profile import HourlyReading
from pv_app.domain.invoice import Invoice
from pv_app.domain.metering_point import MeteringPoint


@dataclass(frozen=True)
class SourceFile:
    """Wgrany plik, z którego pochodzi Faktura albo Nota obciążeniowa; rozpoznawany po hashu."""

    sha256: str
    file_name: str
    """Nazwa pliku przy wgraniu."""
    archive_name: str
    """Nazwa kopii w archiwum (``FileArchive``)."""
    invoice_number: str
    """Numer Faktury albo Noty obciążeniowej z tego pliku; dla Raportu wartości godzinowych
    jego zakres dni (``HourlyValuesReport.label``)."""
    ppe_number: str
    """PPE dokumentu z tego pliku (usunięcie PPE usuwa też jego pliki). Pusty tylko przy
    Raporcie wartości godzinowych zapisanym przed tą kolumną, gdy Profil godzinowy miało kilka
    PPE: usunięcie PPE go nie znajdzie (kopia zostaje w archiwum, a przebudowa odrzuca ją jako
    raport nieznanego PPE); każda przebudowa bazy uzupełnia to pole."""


class Repository(Protocol):
    """Zapis obiektów domeny i zapytania potrzebne funkcjom dashboardu."""

    def add_metering_point(self, metering_point: MeteringPoint) -> None: ...

    def list_metering_points(self) -> list[MeteringPoint]: ...

    def update_metering_point(self, metering_point: MeteringPoint) -> None:
        """Zapisuje nowe ustawienia (nazwa, ikona, ładowanie auta) PPE o tym numerze PPE."""
        ...

    def delete_metering_point(self, ppe_number: str) -> list[SourceFile]:
        """Usuwa PPE z jego Fakturami, Notami obciążeniowymi, Profilem godzinowym i wpisami
        wgranych plików; zwraca usunięte wpisy w kolejności wgrania (kopie w archiwum usuwa
        wywołujący)."""
        ...

    def add_invoice(self, invoice: Invoice, *, source_file: SourceFile | None = None) -> None:
        """Zapisuje Fakturę; z ``source_file`` razem z wpisem jej wgranego pliku, oba albo
        żadne (w SQLite jedna transakcja)."""
        ...

    def has_invoice(self, number: str) -> bool: ...

    def list_invoices(self, ppe_number: str) -> list[Invoice]:
        """Faktury PPE (także korygujące i zastąpione) od najstarszego Okresu rozliczeniowego."""
        ...

    def delete_invoice(self, number: str) -> SourceFile | None:
        """Usuwa Fakturę i wpis jej wgranego pliku; zwraca usunięty wpis (kopię w archiwum
        usuwa wywołujący) albo ``None``, gdy Faktura nie miała pliku."""
        ...

    def add_debit_note(self, note: DebitNote, *, source_file: SourceFile | None = None) -> None:
        """Zapisuje Notę obciążeniową; z ``source_file`` jak ``add_invoice``."""
        ...

    def has_debit_note(self, number: str) -> bool: ...

    def list_debit_notes(self, ppe_number: str) -> list[DebitNote]:
        """Noty obciążeniowe PPE od najstarszej daty wystawienia."""
        ...

    def add_source_file(self, source_file: SourceFile) -> None: ...

    def find_source_file(self, sha256: str) -> SourceFile | None: ...

    def list_source_files(self) -> list[SourceFile]:
        """Wgrane pliki w kolejności zapisu (przebudowa bazy wgrywa je w tej kolejności)."""
        ...

    def find_source_file_for(self, document_number: str) -> SourceFile | None:
        """Wgrany plik Faktury albo Noty obciążeniowej o tym numerze."""
        ...

    def add_hourly_readings(
        self, readings: Iterable[HourlyReading], *, source_file: SourceFile | None = None
    ) -> int:
        """Zapisuje godziny Profilu godzinowego; godzina już zapisana (ten sam PPE, koniec
        godziny i ``extra_hour``) dostaje nowe wartości. Zwraca liczbę nowych godzin.
        Z ``source_file`` (Raport wartości godzinowych) godziny i wpis pliku zapisują się
        razem albo wcale."""
        ...

    def list_hourly_readings(self, ppe_number: str) -> list[HourlyReading]:
        """Profil godzinowy PPE od najstarszej godziny."""
        ...

    def has_hourly_readings(self, ppe_number: str) -> bool:
        """Czy PPE ma choć jedną godzinę Profilu godzinowego (bez czytania całego Profilu)."""
        ...

    def clear_documents(self) -> None:
        """Usuwa Faktury, Noty obciążeniowe, wpisy wgranych plików i Profil godzinowy przed
        przebudową bazy z archiwum; PPE i ich ustawienia zostają."""
        ...
