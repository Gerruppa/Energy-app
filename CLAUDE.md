# PV app

Lokalny dashboard kosztów i zużycia energii elektrycznej, zbudowany na fakturach Tauron. PPE dodaje się w aplikacji; dziś są dwa: **Dom** (fotowoltaika w net-meteringu, Współczynnik opustu 0.8; oglądają go rodzice użytkownika) i **Mieszkanie**. Od 2027 dochodzi ładowanie auta plug-in w Domu.

Dane wchodzą wsadowo, co 1–4 tygodnie: PDF-y faktur oraz eksport z eLicznika. Projekt działa bez danych na żywo (ADR 0002).

**Stan:** specyfikacja MVP to issue #1; zadania to jego sub-issues #2–#13 z zależnościami „blocked by” w GitHubie. Docelowy wygląd: prototyp `data/prototype-dashboard/index.html`, wariant D (lokalny, poza gitem, z prawdziwymi danymi — wzór wyglądu, nie kod do skopiowania).

## Mapa dokumentów

- `docs/architecture.md`: moduły, seamy, przepływ danych. Przeczytaj przed dodaniem, przeniesieniem lub zmianą interfejsu modułu.
- `GLOSSARY.md`: język domeny (PPE, Opust, Magazyn energii, Ładowanie, Cena krańcowa kWh…). Używaj tych terminów w kodzie, testach, UI i commitach; gdy użytkownik mówi inaczej, wskaż konflikt.
- `docs/adr/`: decyzje i ich powody. Przeczytaj przed zmianą stosu, przechowywania danych lub źródła danych.
- `docs/invoice-structure.md`: rodzaje dokumentów Tauron, pola i pułapki parsowania. Przeczytaj przed pracą nad importem faktur.
- `docs/roadmap.md`: funkcje ze statusem i otwartymi pytaniami. Każda nowa funkcja zaczyna się tutaj.
- `CODING_STANDARDS.md`: reguły oceniane przy przeglądzie kodu. Przekaż go recenzentowi standardów.

## Dane osobowe

`References/` i `data/` zawierają prawdziwe faktury i dane użytkownika (adres, numery PPE, numery klienta). Zostają lokalnie i są w `.gitignore` (ADR 0004). Testy korzystają wyłącznie z syntetycznych lub zanonimizowanych fixture'ów w `tests/fixtures/`; przy tworzeniu fixture'a z prawdziwej faktury podmieniaj dane identyfikujące na fikcyjne.

Repozytorium, issues i PR-y są publiczne. Hook `.githooks/pre-commit` uruchamia `tests/test_no_personal_data.py`, który szuka w plikach gita identyfikatorów, nazwisk, adresów i charakterystycznych kwot z `References/`. Drobnych liczb (ilości z liczników, pojedynczych opłat) test nie odróżni od wymyślonych, więc w przykładach i fixture'ach używaj tylko liczb wymyślonych. Komentarze w issue i opisy PR, których hook nie widzi, przejrzyj sam pod tym kątem.

## Praca nad jednym issue

Każde issue to osobna sesja zaczynana po `/clear`. Wszystko, czego sesja potrzebuje, jest w issue, w tym pliku i w dokumentach z mapy.

1. Przeczytaj issue (`gh issue view N --comments`) i sprawdź, że jego blokery są zamknięte (`gh api repos/Gerruppa/Energy-app/issues/N/dependencies/blocked_by`). Otwarty bloker = zatrzymaj się i powiedz użytkownikowi.
2. Pracuj na `main`: `git pull`, a stan roboczy musi być czysty, zanim zaczniesz.
3. Przeczytaj dokumenty z mapy dla obszaru, który dotykasz.
4. `/implement N`: `/tdd` na seamach importu i analiz (ADR 0005, `docs/architecture.md`), na koniec pełny zestaw testów (przy zmianach importu także `uv run pytest -m real_pdfs`) i `/mattpocock-skills:code-review`.
5. Przy zmianach ekranu uruchom podgląd „demo” (`.claude/launch.json`, dane z `scripts/seed_demo.py demo-data`) i porównaj z prototypem (wariant D). Zmieniony kod wczytuje rerun w otwartej karcie (klawisz R); nowa karta dostaje kod sprzed zmiany. Przy zmianach wydruku uruchom `scripts/print_check.py`.
6. Zaktualizuj dokumenty, które kod zmienił: status w `docs/roadmap.md`, nowe pojęcia w `GLOSSARY.md`, komendy w sekcji *Komendy* poniżej.
7. Commit na `main` (hook sprawdza prywatność) z „Closes #N” w treści, push (zamyka issue). Na koniec komentarz w issue: co zrobiono i które kryteria akceptacji są spełnione.

Gotowe, gdy testy są zielone, commit jest wypchnięty, a każde kryterium akceptacji z issue jest spełnione albo opisane w komentarzu jako niezrobione z powodem. Praca spoza zakresu issue trafia do nowego issue (`needs-triage`), nie do tego commita.

## Komendy

Python i biblioteki zarządza `uv` (ADR 0001). Gdy `uv` nie jest w PATH (sesja otwarta przed instalacją), uruchom go pełną ścieżką `%LOCALAPPDATA%\Microsoft\WinGet\Links\uv.exe`. Python 3.14 (`.python-version`).

- Start aplikacji: dwuklik w `Start.bat` (przy pierwszym starcie instaluje uv i zależności) albo `uv run python -m pv_app`; adres `http://localhost:8501`.
- Testy: `uv run pytest`; pojedynczy plik: `uv run pytest tests/test_repository.py`. Import na prawdziwych PDF-ach z `References/` (ok. 30 s, poza domyślnym zestawem): `uv run pytest -m real_pdfs`.
- Hook prywatności w nowej kopii repozytorium: `git config core.hooksPath .githooks`.
- Wiersze PDF-a tak, jak widzi je parser: `uv run python scripts/dump_raw.py PLIK.pdf [--page N] [--grep WZORZEC] [--json SZKIELET.json]`; `--cells` pokazuje i zapisuje komórki tabel (stary układ).
- Dane do oglądania ekranów bez ruszania `data/`: `uv run python scripts/seed_demo.py demo-data [--references]`, potem podgląd „demo” albo `uv run python -m pv_app --data-dir demo-data --port 8502 --no-browser`.
- Wydruk „Faktura po ludzku” (przy działającej aplikacji na tych danych): `uv run python scripts/print_check.py demo-data [--ppe SLUG] [--keep KATALOG_PDF]`; kod wyjścia 1, gdy Faktura nie mieści się na 1 stronie A4.
- Typy i styl: `uv run mypy`, `uv run ruff check .`, `uv run ruff format .`.
- CI: `.github/workflows/tests.yml` uruchamia ruff, mypy i pytest na Windows przy każdym pushu na `main`.
- Katalog danych: `data/` obok aplikacji; w testach podmieniany zmienną `PV_APP_DATA_DIR`.

## Dodawanie funkcji

1. Wpis w `docs/roadmap.md`: cel, dane wejściowe, otwarte pytania. Doprecyzuj go z użytkownikiem (`/grilling` lub `/grill-with-docs`); nowe pojęcia trafiają od razu do `GLOSSARY.md`.
2. Spec i tickety: `/to-spec`, `/to-tickets`.
3. Każdy ticket według *Praca nad jednym issue*. Nowa zakładka to pakiet w `src/pv_app/features/<nazwa>/` według sekcji *Features* w `docs/architecture.md`.

## Konwencje

- Kod, identyfikatory i commity po angielsku; dokumentacja i UI po polsku. Identyfikator to angielskie tłumaczenie terminu z `GLOSSARY.md` (PPE → `MeteringPoint`, Ładowanie → `ChargingSession`).
- Kwoty (PLN) i energię (kWh) przechowuj jako `Decimal`.
- Każda wartość odczytana z faktury niesie swoje źródło (numer faktury, strona), żeby użytkownik mógł ją sprawdzić w PDF-ie.
- Faktura jest źródłem prawdy dla kwot, eLicznik dla profilu godzinowego kWh (ADR 0003).

## Agent skills

### Issue tracker

Zadania i specyfikacje to GitHub Issues w repo Energy-app (gh CLI). See `docs/agents/issue-tracker.md`.

### Triage labels

Pięć domyślnych ról: needs-triage, needs-info, ready-for-agent, ready-for-human, wontfix. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `GLOSSARY.md` i `docs/adr/` w katalogu głównym. See `docs/agents/domain.md`.

## Skille

Skille o wyzwalaczach specyficznych dla projektu; resztę wybieraj po opisach.

| Kiedy | Skill |
|---|---|
| Zasady net-meteringu, struktura faktur Tauron | `mattpocock-skills:research` |
| Nowe lub zmienione pojęcie, decyzja do ADR | `mattpocock-skills:domain-modeling` |
| Wypróbowanie widoku dashboardu przed budową | `mattpocock-skills:prototype` |
| Błąd parsera, złe liczby | `mattpocock-skills:diagnosing-bugs` |
| Przegląd przed commitem / opis PR | `mattpocock-skills:code-review` (nie wbudowany `code-review`), `mattpocock-skills:pr` |
