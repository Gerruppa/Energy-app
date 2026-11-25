# Architektura

Aplikacja jednoosobowa, uruchamiana lokalnie: Python + Streamlit + SQLite (ADR 0001). Pliki trafiają do aplikacji przez upload, są parsowane do obiektów domeny i zapisywane w bazie; widoki dashboardu czytają z bazy i liczą statystyki czystymi funkcjami.

## Przepływ danych

```
PDF faktury ──────┐
                  ├─► ingest ──► domain (obiekty) ──► storage (SQLite)
xlsx godzinowy ───┘                                        │
Ładowania (formularz) ────────────────────────────────┤
                                                      ▼
                         app (Streamlit) ◄── features (analizy + widoki)
```

## Układ repozytorium

```
src/pv_app/
  domain/     obiekty i czyste obliczenia, bez I/O
  ingest/     pliki → obiekty domeny
  storage/    zapis i odczyt obiektów domeny
  features/   jedna funkcja dashboardu = jeden pakiet
  app/        powłoka Streamlit
tests/
  fixtures/   syntetyczne / zanonimizowane faktury i eksporty
References/   prawdziwe faktury użytkownika (poza gitem)
data/         baza SQLite i archiwum wgranych plików (poza gitem)
```

Zależności płyną w jedną stronę: `app → features → storage → domain` oraz `ingest → domain`. `domain` nie importuje niczego z projektu.

## Moduły

### domain

Słownik projektu w kodzie: `MeteringPoint`, `Invoice`, `InvoiceLine`, `DebitNote`, `BillingPeriod`, `HourlyReading` i `HourlyValuesReport` (`domain/hourly_profile.py`), `ChargingSession`. Obliczenia, które nie potrzebują I/O, mieszkają tutaj:

- `PeriodCosts` (`domain/period_cost.py`): które Faktury zastąpiły Faktury korygujące, której Fakturze Nota obciążeniowa pomniejsza Koszt okresu (data sprzedaży Noty w Okresie rozliczeniowym) i sam Koszt okresu.
- `ViewPeriod` (`domain/view_period.py`): Okres widoku, jego wartość w adresie strony (`caly`, `2026`, `2026-K4`, `2026-10`), sąsiednie okresy, ten sam okres rok wcześniej i widok na start (ostatni miesiąc objęty Fakturami w całości).
- Rozkład na miesiące (`domain/monthly_split.py`): `split_into_months(Faktura, Koszt okresu)` dzieli Fakturę na miesiące kalendarzowe; części sumują się dokładnie do wartości z Faktury.

- `EnergyStore` (`domain/energy_store.py`): księga Magazynu energii. Porcje Energii oddanej × Współczynnik opustu z datą Wygaśnięcia, Opusty zdejmowane od najstarszej porcji, suma porcji dopasowana do stanu z Faktury. Interfejs: `EnergyStore.from_invoices(Faktury)` (pomija Faktury zastąpione), `movements` (ruch na każdą Fakturę i Wygaśnięcia między przylegającymi Fakturami, gdy spadek przekracza tolerancję bilansu; Opust jak `Invoice.discount_kwh`, a różnica do stanu z Faktury to `rounding_kwh`), `state_on(dzień)` (stan z ostatniej Faktury zakończonej do tego dnia, porcje i co wygaśnie w 3 miesiące).
- Ceny: Cena średnia kWh i Cena krańcowa kWh dla Faktury.

Pozycje faktury są klasyfikowane do kategorii z `GLOSSARY.md` (Składnik zmienny / Składnik stały i ich rodzaje). Klasyfikacja jest częścią domeny, więc nowa nazwa pozycji na fakturze wymaga zmiany w jednym miejscu.

### ingest

Głęboki moduł z jednym wejściem: `import_file(path) -> ImportResult` (oraz `import_document(RawDocument)` i `import_sheet(wiersze arkusza)` dla surowych wierszy, używane w testach). `ImportResult` niesie Fakturę (rozliczeniową albo korygującą), Notę obciążeniową albo Raport wartości godzinowych. `import_file` niczego nie zapisuje; zapis robi wywołujący (kreator, strona importu). W środku:

1. rozpoznaje rodzaj pliku (faktura Tauron PDF, Raport wartości godzinowych xlsx),
2. wybiera parser (adapter) dla tego rodzaju,
3. zwraca obiekty domeny z odnośnikiem do źródła (plik, strona) oraz listę ostrzeżeń, gdy czegoś nie rozpoznał.

Seam leży między rozpoznaniem a parserem: gdy Tauron zmieni układ faktury, dochodzi nowy parser obok starego, a reszta aplikacji się nie zmienia.

Każdy parser faktur ma dwa etapy (ADR 0005): cienki adapter PDF → surowe wiersze i tabele (pdfplumber) oraz głęboki moduł surowe wiersze → Faktura. Adapter (`ingest/pdf_adapter.py`) daje dla każdej strony wiersze tekstu (`RawPage.lines`, czyta je parser nowego układu) i te same wiersze podzielone na komórki po odstępach między znakami (`RawPage.rows`, czyta je parser starego układu, `ingest/old_layout.py`). Faktura korygująca ma układ starej Faktury z częściami „policzono” i „należało policzyć”; parser starego układu czyta nagłówek z całego dokumentu, a resztę z części „należało policzyć”. Nota obciążeniowa ma własny parser (`ingest/debit_note.py`) i kontrolę kwot (`domain/debit_note.py`). Parsery zgłaszają nieczytelny dokument przez `ParseError` (`ingest/parse_error.py`). Głęboki moduł testowany jest na zanonimizowanych zrzutach w `tests/fixtures/` (JSON: `{"pages": [[wiersz, …], …]}`; wiersz to tekst albo lista komórek). Raport wartości godzinowych ma ten sam podział: `ingest/xlsx_adapter.py` (xlsx → wiersze komórek, bibliotekami standardowymi, daty jako liczby seryjne Excela) i `ingest/hourly_report.py` (wiersze → `HourlyValuesReport`, kolumny wybrane po oznaczeniach ECP/ECO/ECBP/ECBO w nagłówku). Po parsowaniu Faktura przechodzi kontrolę sum (`domain/invoice_checks.py`: pozycje = Wynik rozliczenia, Do zapłaty, bilans Magazynu energii); niezgodna jest odrzucana z opisem przyczyny. Każda część Faktury (nagłówek, odczyt, Pozycja, Rozliczenie OZE, podsumowanie, Prognoza) niesie `Source` (numer Faktury, strona PDF-a).

### storage

Interfejs `Repository`: zapis obiektów domeny i zapytania potrzebne funkcjom (Faktury i Noty obciążeniowe dla PPE, wgrany plik po hashu albo po numerze dokumentu, Profil godzinowy, Ładowania). Dwa adaptery: SQLite (aplikacja) i w pamięci (testy funkcji).

Adapter SQLite zapisuje Fakturę i Notę obciążeniową w całości jako JSON (`storage/codec.py`) z kolumnami do zapytań obok; pole dodane do obiektu domeny później ma wartość domyślną, więc starszy JSON dalej się odczytuje. Schemat ma wersje (`PRAGMA user_version`) i migruje się przy starcie. Import jest idempotentny: Faktura i Nota identyfikowane numerem, odczyt godzinowy trójką (PPE, koniec godziny, dodatkowa godzina) — nowszy raport nadpisuje wartości tej samej godziny, plik źródłowy hashem. Faktura korygująca zastępuje wartości korygowanej Faktury, a obie zostają w bazie. Wgrany plik jest kopiowany do `data/archive/`, żeby bazę dało się odbudować z plików.

### features

Każda funkcja dashboardu to pakiet `features/<nazwa>/` z dwiema częściami:

- `analysis.py`: czyste funkcje `(Repository, Filters) → wynik`, testowane bez Streamlita na adapterze w pamięci;
- `page.py`: obiekt `Feature` (id, tytuł, kolejność, `is_available(ppe)`, `render(context)`), który rysuje wynik analizy. `is_available` decyduje, czy zakładka pojawia się dla danego PPE (np. Magazyn energii tylko przy net-meteringu, Dzień po dniu tylko z danymi eLicznika).

`Filters` (`features/base.py`) to jeden PPE i Okres widoku (cały okres, rok, kwartał, miesiąc); `FeatureContext.filters` podaje go każdej zakładce. Analizy zwracają też stan na koniec Okresu widoku i ten sam okres rok wcześniej. Przegląd (`features/overview/`) liczy wykres miesiąc po miesiącu (`energy_chart`: słupek dla miesiąca z własną Fakturą, blok ze średnią miesięczną dla Faktury za kilka miesięcy, kontur roku wcześniej, luki) i porównanie rok do roku (`year_over_year`: z rozkładu na miesiące, „analogiczny okres” z Faktury jako zapas i kontrola); `chart.py` rysuje wykres w Plotly. Magazyn energii (`features/energy_store/`, tylko PPE z net-meteringiem) pokazuje `EnergyStore` w Okresie widoku; kafelek Magazynu energii w Przeglądzie bierze stan z `EnergyStore.state_on`, bez importu tej zakładki. Górną część Przeglądu liczy `overview/tiles.py`: `invoice_status(repository, ppe, dziś)` (aktualne / Brakująca Faktura: koniec oczekiwanego okresu — miesiąc albo koniec harmonogramu Prognoz — plus 14 dni / odczyt szacunkowy), `next_payment(repository, ppe, dziś)` (pierwsza Prognoza z terminem od dziś, bez harmonogramu „do zapłaty” z Faktury) oraz ze stanem na koniec Okresu widoku `balance` (Saldo z Faktury plus Noty wystawione po niej) i `last_invoice`; „dziś” podaje wywołujący, więc testy go ustalają. `overview/top.py` rysuje je w HTML (`st.html`, podpowiedzi „?” jako `<details>`, kolory dziedziczone z motywu). `forecast_chart` w `overview/analysis.py` daje Prognozy z najnowszego harmonogramu jako linie obok Faktur; Prognozy nie wchodzą do żadnych sum. Podpowiedzi wspólne dla kilku widoków (np. „Magazyn energii to nie bateria…”) są w `features/terms.py`. Widok Faktury (`features/invoice_view/`) nie jest zakładką: powłoka pokazuje go zamiast zakładek, gdy adres ma `&faktura=…`; `invoice_sheet(repository, ppe, numer)` zbiera „Fakturę po ludzku” (Grupy kosztów, Koszt okresu z Notami, sąsiednie Faktury, ten sam okres rok wcześniej, plik w archiwum), a `page.py` rysuje ją razem ze stylem druku. Zakładki otwierają Fakturę przez `features/navigation.py` (klucze adresu `okres` i `faktura`), bez importowania innej zakładki; stamtąd też otwierają stronę „Wgraj pliki” (`open_import`). Widok zawsze dotyczy jednego PPE, bez sum ani porównań między PPE. PPE, ich nazwy i ustawienia (np. ładowanie auta) są danymi w `storage`, dodawanymi przez kreator, nie stałymi w kodzie. Funkcje rejestrują się w `features/__init__.py`; dodanie funkcji to nowy pakiet plus jedna linia w rejestrze, bez zmian w `app` ani w innych funkcjach.

### app

Powłoka Streamlit: wybór PPE (adres `?ppe=…`), przełącznik Okresu widoku pod nazwą PPE (`app/view_period_switcher.py`, adres `&okres=…`, wspólny dla zakładek), kreator dodawania PPE, strona importu (upload → `ingest` → `storage`, pokazuje ostrzeżenia parsera i pyta o nowy PPE), zakładki z rejestru `features` dostępne dla wybranego PPE albo, z `&faktura=…` w adresie, widok Faktury. Uruchamiana dwuklikiem w `Start.bat`. Nie zawiera logiki obliczeń.

Logika importu bez Streamlita leży w `app/batch_import.py` i jest seamem testów strony importu i kreatora: `import_files(repository, archive, files) -> ImportSummary` (zaimportowane, duplikaty, odrzucone z powodem, Faktury nowych PPE czekające na kreator) oraz `add_new_metering_point(...)`, które dodaje PPE i kontynuuje import jego Faktur. Kolejność dla pliku: duplikat po hashu → `ingest` → duplikat po numerze Faktury (Noty) → PPE znany? Raport wartości godzinowych pomija sprawdzenie numeru: godziny znanego PPE dopisują się do Profilu godzinowego, raport nieznanego PPE jest odrzucany. Tylko dokument znanego PPE trafia do bazy, a jego plik do archiwum (`storage/archive.py`, `data/archive/`). Nota nieznanego PPE czeka razem z Fakturami tego PPE z tej samej paczki (Nota nie ma danych do kreatora); bez nich jest odrzucana. Odczyt pliku jest wstrzykiwany, więc testy podają zrzuty wierszy zamiast PDF-ów.
