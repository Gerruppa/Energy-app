# PV app

Lokalny dashboard kosztów i zużycia energii elektrycznej, zbudowany na fakturach Tauron dla dwóch PPE: **Dom** i **Mieszkanie**. Jeden PPE ma fotowoltaikę rozliczaną w net-meteringu (Współczynnik opustu 0.8). Od 2027 dochodzi koszt ładowania auta plug-in z gniazdka.

Dane wchodzą wsadowo, co 1–4 tygodnie: PDF-y faktur oraz eksport z eLicznika. Projekt działa bez danych na żywo (ADR 0002).

**Stan:** faza projektowa: architektura i model domeny są opisane, kodu jeszcze nie ma.

## Mapa dokumentów

- `docs/architecture.md`: moduły, seamy, przepływ danych. Przeczytaj przed dodaniem, przeniesieniem lub zmianą interfejsu modułu.
- `GLOSSARY.md`: język domeny (PPE, Opust, Magazyn energii, Ładowanie, Cena krańcowa kWh…). Używaj tych terminów w kodzie, testach, UI i commitach; gdy użytkownik mówi inaczej, wskaż konflikt.
- `docs/adr/`: decyzje i ich powody. Przeczytaj przed zmianą stosu, przechowywania danych lub źródła danych.
- `docs/invoice-structure.md`: rodzaje dokumentów Tauron, pola i pułapki parsowania. Przeczytaj przed pracą nad importem faktur.
- `docs/roadmap.md`: funkcje ze statusem i otwartymi pytaniami. Każda nowa funkcja zaczyna się tutaj.

## Dane osobowe

`References/` i `data/` zawierają prawdziwe faktury i dane użytkownika (adres, numery PPE, numery klienta). Zostają lokalnie i są w `.gitignore` (ADR 0004). Testy korzystają wyłącznie z syntetycznych lub zanonimizowanych fixture'ów w `tests/fixtures/`; przy tworzeniu fixture'a z prawdziwej faktury podmieniaj dane identyfikujące na fikcyjne.

## Dodawanie funkcji

1. Wpis w `docs/roadmap.md`: cel, dane wejściowe, otwarte pytania. Doprecyzuj go z użytkownikiem (`/grilling` lub `/grill-with-docs`); nowe pojęcia trafiają od razu do `GLOSSARY.md`.
2. Spec i tickety: `/to-spec`, `/to-tickets`.
3. Implementacja: nowy pakiet w `src/pv_app/features/<nazwa>/` według sekcji *Features* w `docs/architecture.md`, prowadzona `/tdd` przez interfejs funkcji. Gotowe, gdy testy są zielone, a status w roadmapie zaktualizowany.
4. `/code-review` przed commitem.

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

| Kiedy | Skill |
|---|---|
| Doprecyzowanie pomysłu, stress-test planu | `mattpocock-skills:grilling`, `/grill-with-docs` |
| Nowe lub zmienione pojęcie, decyzja do ADR | `mattpocock-skills:domain-modeling` |
| Projekt interfejsu modułu, położenie seamu | `mattpocock-skills:codebase-design` |
| Zasady net-meteringu, struktura faktur Tauron | `mattpocock-skills:research` |
| Wypróbowanie widoku dashboardu przed budową | `mattpocock-skills:prototype` |
| Od pomysłu do kodu | `/to-spec` → `/to-tickets` → `/implement` |
| Implementacja test-first (parser na fixture'ach) | `mattpocock-skills:tdd` |
| Błąd parsera, złe liczby | `mattpocock-skills:diagnosing-bugs` |
| Przegląd przed commitem / opis PR | `mattpocock-skills:code-review`, `mattpocock-skills:pr` |
| Struktura i tekst PDF-ów faktur | `anthropic-skills:pdf` |
| Eksporty CSV/XLSX z eLicznika | `anthropic-skills:xlsx` |
| Wykresy, kafelki KPI, kolory | `dataviz` |
| Wygląd i układ dashboardu | `frontend-design` |
| Dokumentacja bibliotek (pdfplumber, Streamlit, Plotly) | `find-docs` |
