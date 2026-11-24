"""Wiersze PDF-a tak, jak widzi je parser (``read_pdf``), do rozpoznawania układu Faktur.

    uv run python scripts/dump_raw.py References/DOM/plik.pdf [--page 3] [--grep Licznik]
    uv run python scripts/dump_raw.py References/DOM/plik.pdf --json tests/fixtures/nowy.json
    uv run python scripts/dump_raw.py References/DOM/plik.pdf --cells [--json stary.json]

``--cells`` pokazuje wiersze podzielone na komórki tabel (``a | b``), z których czyta parser
starego układu; z ``--json`` zapisuje je jako listy komórek. ``--json`` zapisuje szkielet
fixture'a z prawdziwymi danymi: przed commitem zamień w nim numery, nazwy, adresy i kwoty
na wymyślone (CODING_STANDARDS.md, *Fixture'y i przykłady*).
"""

import argparse
import json
import re
import sys
from pathlib import Path

from pv_app.ingest.pdf_adapter import read_pdf


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--page", type=int, help="tylko ta strona (od 1)")
    parser.add_argument("--grep", help="tylko wiersze pasujące do wyrażenia regularnego")
    parser.add_argument("--json", type=Path, help="zapisz szkielet fixture'a do pliku")
    parser.add_argument("--cells", action="store_true", help="wiersze podzielone na komórki")
    args = parser.parse_args()

    document = read_pdf(args.pdf)
    if args.json:
        pages: list[list[str | list[str]]] = [
            [row[0] if len(row) == 1 else list(row) for row in page.rows]
            if args.cells
            else list(page.lines)
            for page in document.pages
        ]
        payload = {"_comment": "SZKIELET Z PRAWDZIWEJ FAKTURY: zanonimizuj przed commitem."}
        args.json.write_text(
            json.dumps({**payload, "pages": pages}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Zapisano {args.json} ({len(pages)} stron).")
        return

    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    pattern = re.compile(args.grep) if args.grep else None
    for page in document.pages:
        if args.page and page.number != args.page:
            continue
        print(f"##### strona {page.number}")
        lines = [" | ".join(row) for row in page.rows] if args.cells else page.lines
        for line in lines:
            if pattern is None or pattern.search(line):
                print(line)


if __name__ == "__main__":
    main()
