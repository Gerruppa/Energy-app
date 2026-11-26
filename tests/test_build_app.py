"""Folder „Builded app” (``scripts/build_app.py``): sama aplikacja na inny komputer."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "build_app.py"


def _build(target: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--target", str(target)],
        capture_output=True,
        text=True,
    )


def test_built_folder_has_what_start_bat_needs_and_nothing_from_development(
    tmp_path: Path,
) -> None:
    target = tmp_path / "Builded app"

    _build(target)

    top = {p.name for p in target.iterdir()}
    assert {"Start.bat", "pyproject.toml", "uv.lock", ".python-version", "README.md"} <= top
    assert (target / "src" / "pv_app" / "__main__.py").is_file()
    assert (target / "src" / "pv_app" / "app" / "main.py").is_file()
    assert not top & {"tests", "docs", "scripts", "References", "data", "demo-data", ".git"}
    assert not list(target.rglob("__pycache__"))
    assert "Wersja" in (target / "WERSJA.txt").read_text(encoding="utf-8")


def test_rebuild_replaces_code_but_keeps_data_used_in_that_folder(tmp_path: Path) -> None:
    target = tmp_path / "Builded app"
    _build(target)
    (target / "data").mkdir()
    (target / "data" / "pv_app.sqlite3").write_bytes(b"baza")
    stale = target / "src" / "pv_app" / "removed_module.py"
    stale.write_text("", encoding="utf-8")

    _build(target)

    assert (target / "data" / "pv_app.sqlite3").read_bytes() == b"baza"
    assert not stale.exists()


def test_refuses_to_clear_a_folder_it_did_not_build(tmp_path: Path) -> None:
    someone_elses = tmp_path / "Dokumenty"
    someone_elses.mkdir()
    (someone_elses / "list.txt").write_text("ważne", encoding="utf-8")

    result = _build(someone_elses)

    assert result.returncode != 0
    assert (someone_elses / "list.txt").exists()
