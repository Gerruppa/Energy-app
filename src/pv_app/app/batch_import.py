"""Import paczki plików: logika strony importu i kreatora bez Streamlita.

Plik przechodzi kolejno: duplikat po hashu → odczyt (``ingest``) → duplikat po numerze
Faktury → PPE znany? Faktura znanego PPE trafia do bazy, a plik do archiwum. Faktury
nieznanego PPE czekają w ``NewMeteringPoint``, aż użytkownik doda PPE w kreatorze
(``add_new_metering_point``).
"""

import hashlib
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from functools import cached_property
from io import BytesIO

from pv_app.app.wizard import create_metering_point_from_invoice
from pv_app.domain.invoice import Invoice
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


def read_pdf(file: UploadedFile) -> ImportResult:
    return import_file(BytesIO(file.content), file.name)


Reader = Callable[[UploadedFile], ImportResult]


@dataclass(frozen=True)
class ImportedFile:
    file_name: str
    invoice_number: str
    archive_name: str
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class SkippedFile:
    file_name: str
    reason: str
    """Po polsku, do pokazania użytkownikowi."""


@dataclass(frozen=True)
class WaitingFile:
    """Odczytany plik, którego Faktura czeka na dodanie PPE."""

    file: UploadedFile
    result: ImportResult

    @property
    def invoice(self) -> Invoice:
        assert self.result.invoice is not None
        return self.result.invoice


@dataclass
class NewMeteringPoint:
    """PPE, którego nie ma w aplikacji, z Fakturami czekającymi na jego dodanie."""

    files: list[WaitingFile]

    @property
    def first_invoice(self) -> Invoice:
        return self.files[0].invoice

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
        self.summary = ImportSummary()

    def add(self, file: UploadedFile, read: Reader) -> None:
        duplicate_of = self._file_name_by_hash(file.sha256)
        if duplicate_of is not None:
            self._skip_duplicate(file, f"Ten sam plik został już wgrany jako {duplicate_of}.")
            return
        result = read(file)
        invoice = result.invoice
        if invoice is None:
            reason = result.rejection or "Nie udało się odczytać Faktury."
            self.summary.rejected.append(SkippedFile(file.name, reason))
            self._unsaved_by_hash[file.sha256] = file.name
            return
        if invoice.number in self._waiting_numbers or self._repository.has_invoice(invoice.number):
            self._skip_duplicate(file, f"Faktura {invoice.number} jest już w aplikacji.")
            return
        if invoice.header.ppe_number in self._known_points:
            self._save(file, invoice, result.warnings)
        else:
            self._wait(WaitingFile(file, result))

    def _file_name_by_hash(self, sha256: str) -> str | None:
        known = self._repository.find_source_file(sha256)
        return known.file_name if known else self._unsaved_by_hash.get(sha256)

    def _skip_duplicate(self, file: UploadedFile, reason: str) -> None:
        self.summary.duplicates.append(SkippedFile(file.name, reason))

    def _save(self, file: UploadedFile, invoice: Invoice, warnings: tuple[str, ...]) -> None:
        archive_name = self._archive.store(file.name, file.content, file.sha256)
        self._repository.add_invoice(invoice)
        self._repository.add_source_file(
            SourceFile(file.sha256, file.name, archive_name, invoice.number)
        )
        self.summary.imported.append(
            ImportedFile(file.name, invoice.number, archive_name, warnings)
        )

    def _wait(self, waiting: WaitingFile) -> None:
        self._unsaved_by_hash[waiting.file.sha256] = waiting.file.name
        self._waiting_numbers.add(waiting.invoice.number)
        ppe_number = waiting.invoice.header.ppe_number
        for point in self.summary.new_metering_points:
            if point.ppe_number == ppe_number:
                point.files.append(waiting)
                return
        self.summary.new_metering_points.append(NewMeteringPoint([waiting]))


def import_files(
    repository: Repository,
    archive: FileArchive,
    files: Iterable[UploadedFile],
    *,
    read: Reader = read_pdf,
) -> ImportSummary:
    """Importuje pliki po kolei; duplikaty i odrzucone Faktury nie zmieniają bazy."""
    run = _ImportRun(repository, archive)
    for file in files:
        run.add(file, read)
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
    return point, run.summary
