"""Import paczki plików: logika strony importu i kreatora bez Streamlita.

Plik przechodzi kolejno: duplikat po hashu → odczyt (``ingest``) → duplikat po numerze
Faktury (Noty obciążeniowej) → PPE znany? Faktura znanego PPE trafia do bazy, a plik do
archiwum. Raport wartości godzinowych znanego PPE dopisuje godziny do Profilu godzinowego
(godziny z wcześniejszych raportów dostają nowsze wartości); nieznanego PPE jest odrzucany,
bo PPE dodaje się z Faktury. Faktury nieznanego PPE czekają w ``NewMeteringPoint``, aż
użytkownik doda PPE w kreatorze (``add_new_metering_point``). Nota obciążeniowa nie ma danych
do kreatora, więc Nota nieznanego PPE czeka tylko razem z jego Fakturami z tej samej paczki
(w dowolnej kolejności plików); inaczej jest odrzucana.
"""

import hashlib
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from functools import cached_property
from io import BytesIO

from pv_app.app.wizard import create_metering_point_from_invoice
from pv_app.domain.debit_note import DebitNote
from pv_app.domain.hourly_profile import HourlyValuesReport
from pv_app.domain.invoice import DocumentKind, Invoice
from pv_app.domain.metering_point import MeteringPoint, SiteIcon
from pv_app.ingest import ImportResult, import_file
from pv_app.storage.archive import FileArchive
from pv_app.storage.repository import Repository, SourceFile


@dataclass(frozen=True)
class UploadedFile:
    name: str
    content: bytes

    @cached_property
    def sha256(self) -> str:
        return hashlib.sha256(self.content).hexdigest()


def read_file(file: UploadedFile) -> ImportResult:
    return import_file(BytesIO(file.content), file.name)


Reader = Callable[[UploadedFile], ImportResult]


@dataclass(frozen=True)
class ImportedFile:
    file_name: str
    invoice_number: str
    """Numer Faktury albo Noty obciążeniowej; dla Raportu wartości godzinowych zakres dni."""
    archive_name: str
    warnings: tuple[str, ...] = ()
    kind: DocumentKind = DocumentKind.SETTLEMENT_INVOICE
    new_hours: int | None = None
    """Raport wartości godzinowych: ile godzin Profilu godzinowego przybyło."""


@dataclass(frozen=True)
class SkippedFile:
    file_name: str
    reason: str
    """Po polsku, do pokazania użytkownikowi."""


@dataclass(frozen=True)
class WaitingFile:
    """Odczytany plik, którego Faktura albo Nota obciążeniowa czeka na dodanie PPE."""

    file: UploadedFile
    result: ImportResult

    @property
    def document(self) -> Invoice | DebitNote:
        document = self.result.invoice or self.result.debit_note
        assert document is not None
        return document

    @property
    def ppe_number(self) -> str:
        document = self.document
        return document.header.ppe_number if isinstance(document, Invoice) else document.ppe_number


@dataclass
class NewMeteringPoint:
    """PPE, którego nie ma w aplikacji, z Fakturami czekającymi na jego dodanie."""

    files: list[WaitingFile]

    @property
    def first_invoice(self) -> Invoice:
        """Pierwsza Faktura PPE; Noty dołączają tylko do PPE, który ma już Fakturę."""
        return next(w.result.invoice for w in self.files if w.result.invoice is not None)

    @property
    def ppe_number(self) -> str:
        return self.first_invoice.header.ppe_number

    @property
    def address(self) -> str:
        return self.first_invoice.header.address

    @property
    def file_names(self) -> tuple[str, ...]:
        return tuple(w.file.name for w in self.files)


@dataclass
class ImportSummary:
    imported: list[ImportedFile] = field(default_factory=list)
    duplicates: list[SkippedFile] = field(default_factory=list)
    rejected: list[SkippedFile] = field(default_factory=list)
    new_metering_points: list[NewMeteringPoint] = field(default_factory=list)

    def after_adding(
        self, new_point: NewMeteringPoint, continuation: "ImportSummary"
    ) -> "ImportSummary":
        """Podsumowanie paczki po dodaniu PPE i imporcie jego czekających Faktur."""
        return ImportSummary(
            imported=self.imported + continuation.imported,
            duplicates=self.duplicates + continuation.duplicates,
            rejected=self.rejected + continuation.rejected,
            new_metering_points=[
                p for p in self.new_metering_points if p.ppe_number != new_point.ppe_number
            ],
        )


class _ImportRun:
    def __init__(self, repository: Repository, archive: FileArchive) -> None:
        self._repository = repository
        self._archive = archive
        self._known_points = {p.ppe_number for p in repository.list_metering_points()}
        self._unsaved_by_hash: dict[str, str] = {}
        """Pliki tej paczki, których nie ma w bazie (odrzucone, czekające): hash → nazwa."""
        self._waiting_numbers: set[str] = set()
        self._notes_of_unknown_points: list[WaitingFile] = []
        self.summary = ImportSummary()

    def add(self, file: UploadedFile, read: Reader) -> None:
        duplicate_of = self._file_name_by_hash(file.sha256)
        if duplicate_of is not None:
            self._skip_duplicate(file, f"Ten sam plik został już wgrany jako {duplicate_of}.")
            return
        result = read(file)
        if result.hourly_report is not None:
            self._add_hourly_report(file, result.hourly_report, result.warnings)
            return
        if result.invoice is None and result.debit_note is None:
            self._reject(file, result.rejection or "Nie udało się odczytać Faktury.")
            return
        waiting = WaitingFile(file, result)
        document = waiting.document
        if isinstance(document, Invoice):
            already_saved = self._repository.has_invoice(document.number)
            label = "Faktura"
        else:
            already_saved = self._repository.has_debit_note(document.number)
            label = "Nota obciążeniowa"
        if document.number in self._waiting_numbers or already_saved:
            self._skip_duplicate(file, f"{label} {document.number} jest już w aplikacji.")
            return
        if waiting.ppe_number in self._known_points:
            self._save(file, document, result.warnings)
        elif isinstance(document, Invoice):
            self._wait(waiting)
        else:
            self._unsaved_by_hash[file.sha256] = file.name
            self._waiting_numbers.add(document.number)
            self._notes_of_unknown_points.append(waiting)

    def finish(self) -> None:
        """Noty nieznanych PPE dołączają do Faktur tego PPE z paczki albo są odrzucane."""
        for waiting in self._notes_of_unknown_points:
            point = self._new_point(waiting.ppe_number)
            if point is not None:
                point.files.append(waiting)
            else:
                self._reject(
                    waiting.file,
                    f"Nota obciążeniowa {waiting.document.number} dotyczy punktu poboru, "
                    "którego nie ma w aplikacji. Wgraj ją razem z Fakturą tego punktu poboru "
                    "albo po jego dodaniu.",
                )
        self._notes_of_unknown_points = []

    def _reject(self, file: UploadedFile, reason: str) -> None:
        self.summary.rejected.append(SkippedFile(file.name, reason))
        self._unsaved_by_hash[file.sha256] = file.name

    def _new_point(self, ppe_number: str) -> NewMeteringPoint | None:
        return next(
            (p for p in self.summary.new_metering_points if p.ppe_number == ppe_number), None
        )

    def _file_name_by_hash(self, sha256: str) -> str | None:
        known = self._repository.find_source_file(sha256)
        return known.file_name if known else self._unsaved_by_hash.get(sha256)

    def _skip_duplicate(self, file: UploadedFile, reason: str) -> None:
        self.summary.duplicates.append(SkippedFile(file.name, reason))

    def _save(
        self, file: UploadedFile, document: Invoice | DebitNote, warnings: tuple[str, ...]
    ) -> None:
        archive_name = self._archive.store(file.name, file.content, file.sha256)
        if isinstance(document, Invoice):
            self._repository.add_invoice(document)
            ppe_number = document.header.ppe_number
        else:
            self._repository.add_debit_note(document)
            ppe_number = document.ppe_number
        self._repository.add_source_file(
            SourceFile(file.sha256, file.name, archive_name, document.number, ppe_number)
        )
        self.summary.imported.append(
            ImportedFile(
                file.name,
                document.number,
                archive_name,
                warnings,
                document.kind if isinstance(document, Invoice) else DocumentKind.DEBIT_NOTE,
            )
        )

    def _add_hourly_report(
        self, file: UploadedFile, report: HourlyValuesReport, warnings: tuple[str, ...]
    ) -> None:
        if report.ppe_number not in self._known_points:
            self._reject(
                file,
                "Raport wartości godzinowych dotyczy punktu poboru, którego nie ma w aplikacji. "
                "Dodaj go najpierw, wgrywając jego Fakturę, a potem wgraj raport ponownie.",
            )
            return
        archive_name = self._archive.store(file.name, file.content, file.sha256)
        new_hours = self._repository.add_hourly_readings(report.readings)
        self._repository.add_source_file(
            SourceFile(file.sha256, file.name, archive_name, report.label, report.ppe_number)
        )
        self.summary.imported.append(
            ImportedFile(
                file.name,
                report.label,
                archive_name,
                warnings,
                DocumentKind.HOURLY_VALUES_REPORT,
                new_hours,
            )
        )

    def _wait(self, waiting: WaitingFile) -> None:
        self._unsaved_by_hash[waiting.file.sha256] = waiting.file.name
        self._waiting_numbers.add(waiting.document.number)
        point = self._new_point(waiting.ppe_number)
        if point is not None:
            point.files.append(waiting)
        else:
            self.summary.new_metering_points.append(NewMeteringPoint([waiting]))


def import_files(
    repository: Repository,
    archive: FileArchive,
    files: Iterable[UploadedFile],
    *,
    read: Reader = read_file,
) -> ImportSummary:
    """Importuje pliki po kolei; duplikaty i odrzucone Faktury nie zmieniają bazy."""
    run = _ImportRun(repository, archive)
    for file in files:
        run.add(file, read)
    run.finish()
    return run.summary


def add_new_metering_point(
    repository: Repository,
    archive: FileArchive,
    new_point: NewMeteringPoint,
    *,
    name: str,
    icon: SiteIcon,
    charges_car: bool,
) -> tuple[MeteringPoint, ImportSummary]:
    """Dodaje PPE z kreatora i importuje czekające na nie Faktury."""
    point = create_metering_point_from_invoice(
        repository, new_point.first_invoice, name=name, icon=icon, charges_car=charges_car
    )
    already_read = {w.file.sha256: w.result for w in new_point.files}
    run = _ImportRun(repository, archive)
    for waiting in new_point.files:
        run.add(waiting.file, lambda file: already_read[file.sha256])
    run.finish()
    return point, run.summary
