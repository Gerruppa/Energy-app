"""Teksty na ekranie używają terminów z ``GLOSSARY.md``, nie słów z jego list ``_Avoid_``.

Lista niżej to podzbiór ``_Avoid_``, który da się sprawdzić bez kontekstu; reszta
(np. „do zapłaty” zamiast Kosztu okresu) zostaje dla recenzenta (``CODING_STANDARDS.md``).
"""

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UI_PACKAGES = [ROOT / "src" / "pv_app" / "app", ROOT / "src" / "pv_app" / "features"]

AVOIDED = {
    r"\bpunkt\w*\b(?! [Pp]obor)": "PPE / punkt poboru",
    r"\brat(?:a|y|ę|ą|ami|ach)\b": "Prognoza",
    r"\bblankiet\w*": "Prognoza",
    r"\brachun(?:ek|ku|ki|kiem|kach)\b": "Faktura lub Koszt okresu",
    r"\bprzepad\w*": "Wygaśnięcie",
    r"\bbank kWh\b": "Magazyn energii",
    r"\bdepozyt\w*": "Magazyn energii",
    r"\bzniżk\w*": "Opust",
    r"\btankowa\w*": "Ładowanie",
    r"\bbaseline\b": "Linia bazowa",
    r"\bdan\w* godzinow\w*": "Profil godzinowy",
}


def _ui_strings() -> list[tuple[str, int, str]]:
    found = []
    for package in UI_PACKAGES:
        for path in sorted(package.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            docstrings = {
                id(node.body[0].value)
                for node in ast.walk(tree)
                if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef)
                and node.body
                and isinstance(node.body[0], ast.Expr)
            }
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Constant)
                    and isinstance(node.value, str)
                    and id(node) not in docstrings
                ):
                    found.append((path.relative_to(ROOT).as_posix(), node.lineno, node.value))
    return found


def test_ui_texts_avoid_words_the_glossary_replaces() -> None:
    problems = [
        f"{where}:{line}: „{match.group(0)}” → {term}"
        for where, line, text in _ui_strings()
        for pattern, term in AVOIDED.items()
        if (match := re.search(pattern, text, re.IGNORECASE))
    ]

    assert not problems, "Słowa z _Avoid_ w GLOSSARY.md:\n" + "\n".join(problems)


def test_check_catches_a_bare_punkt() -> None:
    pattern = next(iter(AVOIDED))

    assert re.search(pattern, "Nazwa punktu", re.IGNORECASE)
    assert not re.search(pattern, "Nazwa punktu poboru", re.IGNORECASE)
    assert not re.search(pattern, "Dodaj punkt poboru", re.IGNORECASE)


def test_check_catches_informal_name_of_the_hourly_profile() -> None:
    pattern = next(p for p, term in AVOIDED.items() if term == "Profil godzinowy")

    assert re.search(pattern, "Dane godzinowe z eLicznika kończą się", re.IGNORECASE)
    assert re.search(pattern, "brak danych godzinowych", re.IGNORECASE)
    assert not re.search(pattern, "Profil godzinowy z eLicznika", re.IGNORECASE)
