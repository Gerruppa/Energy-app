"""Folder „Builded app”: sama aplikacja do skopiowania na inny komputer.

    uv run python scripts/build_app.py [--target KATALOG]

Kopiuje tylko to, czego potrzebuje ``Start.bat``: skrypt startu, ``pyproject.toml``,
``uv.lock``, ``.python-version``, ``README.md`` i kod z ``src/`` (bez ``__pycache__``). Bez
testów, dokumentacji, skryptów i danych. Ponowne uruchomienie podmienia kod, a zostawia
``data/`` i ``.venv/`` używane w tym folderze. ``WERSJA.txt`` mówi, z którego commita jest
kopia. Domyślny katalog to ``Builded app/`` w repozytorium (poza gitem).
"""

import argparse
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TARGET = ROOT / "Builded app"
FILES = ("Start.bat", "pyproject.toml", "uv.lock", ".python-version", "README.md")
VERSION_FILE = "WERSJA.txt"
KEPT = {"data", ".venv"}
"""Zostają przy przebudowie: dane i środowisko tej kopii aplikacji."""


def _git(*args: str) -> str:
    result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else "?"


def _version() -> str:
    dirty = " (z niezacommitowanymi zmianami)" if _git("status", "--porcelain", "src") else ""
    return (
        f"Wersja: commit {_git('rev-parse', '--short', 'HEAD')}{dirty}, "
        f"{_git('log', '-1', '--format=%cs')}\n"
        f"Zbudowano: {datetime.now():%Y-%m-%d %H:%M}\n"
        "Start: dwuklik w Start.bat. Dane tej kopii są w folderze data/.\n"
    )


def build(target: Path) -> None:
    """Buduje kopię w ``target``; ``ValueError``, gdy to niepusty folder, którego ten skrypt
    nie zbudował (bez ``WERSJA.txt``), żeby pomyłka w ``--target`` nie skasowała plików."""
    if target.exists() and any(target.iterdir()) and not (target / VERSION_FILE).exists():
        raise ValueError(f"{target} nie jest pusty i nie jest zbudowaną kopią aplikacji")
    target.mkdir(parents=True, exist_ok=True)
    for entry in target.iterdir():
        if entry.name in KEPT:
            continue
        if entry.is_dir():
            shutil.rmtree(entry)
        else:
            entry.unlink()
    for name in FILES:
        shutil.copy2(ROOT / name, target / name)
    # cmd.exe bywa zawodny przy plikach .bat z końcami linii LF (jak w gicie).
    start = target / "Start.bat"
    start.write_bytes(start.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
    shutil.copytree(
        ROOT / "src", target / "src", ignore=shutil.ignore_patterns("__pycache__", "*.py[cod]")
    )
    (target / VERSION_FILE).write_text(_version(), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET)
    args = parser.parse_args()
    target = args.target.resolve()
    if target == ROOT or ROOT.is_relative_to(target):
        parser.error(f"{target} to repozytorium albo jego nadrzędny katalog")
    try:
        build(target)
    except ValueError as error:
        parser.error(str(error))
    print(f"Zbudowano: {target}")
    print(_version(), end="")


if __name__ == "__main__":
    main()
