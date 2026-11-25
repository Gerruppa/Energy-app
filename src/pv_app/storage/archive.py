import re
from pathlib import Path

_HASH_PREFIX = 12

_UNSAFE = re.compile(r'[\\/:*?"<>|\x00-\x1f]+')


class FileArchive:
    """Kopie wgranych plików w katalogu danych, żeby bazę dało się odbudować z plików."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def store(self, file_name: str, content: bytes, sha256: str) -> str:
        """Zapisuje kopię pliku i zwraca jej nazwę w archiwum.

        Początek hasha w nazwie rozróżnia różne pliki o tej samej nazwie.
        """
        safe_name = _UNSAFE.sub("_", file_name).strip(" .") or "plik.pdf"
        archive_name = f"{sha256[:_HASH_PREFIX]}-{safe_name}"
        path = self.path(archive_name)
        if not path.exists():
            self.directory.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        return archive_name

    def path(self, archive_name: str) -> Path:
        return self.directory / archive_name

    def remove(self, archive_name: str) -> None:
        self.path(archive_name).unlink(missing_ok=True)

    def names(self) -> list[str]:
        """Nazwy kopii w archiwum, od najdawniej zapisanej."""
        if not self.directory.is_dir():
            return []
        files = [f for f in self.directory.iterdir() if f.is_file()]
        return [f.name for f in sorted(files, key=lambda f: (f.stat().st_mtime, f.name))]

    @staticmethod
    def file_name(archive_name: str) -> str:
        """Nazwa pliku przy wgraniu (bez początku hasha), gdy baza jej nie zna."""
        return archive_name[_HASH_PREFIX + 1 :]
