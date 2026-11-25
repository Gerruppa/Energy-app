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
- Rozkład na miesiące (`domain/monthly_split.py`): `split_into_months(Faktura, Koszt okresu)` dzieli Fakturę na miesiące kalendarzowe, także każdą Grupę kosztów (`MonthShare.cost_groups`); części sumują się dokładnie do wartości z Faktury.
- Grupy kosztów (`domain/cost_groups.py`): `CostGroup`, `cost_group(Pozycja faktury)` i `group_totals(Faktura)`; pięć grup z `GLOSSARY.md` plus Pozycje nierozpoznane.

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

Interfejs `Repository`: zapis obiektów domeny i zapytania potrzebne funkcjom (Faktury i Noty obciążeniowe dla PPE, wgrany plik po hashu albo po numerze dokumentu, Profil godzinowy i czy PPE go ma, Ładowania), zmiana ustawień PPE (`update_metering_point`) i usunięcie PPE ze wszystkimi jego dokumentami (`delete_metering_point`, zwraca wpisy wgranych plików, których kopie usuwa wywołujący). Wpis wgranego pliku (`SourceFile`) zna PPE swojego dokumentu. `add_invoice`, `add_debit_note` i `add_hourly_readings` przyjmują `source_file=`: dokument (albo godziny Raportu wartości godzinowych) i wpis jego pliku zapisują się w jednej transakcji, razem albo wcale. Dwa adaptery: SQLite (aplikacja) i w pamięci (testy funkcji).

Adapter SQLite zapisuje Fakturę i Notę obciążeniową w całości jako JSON (`storage/codec.py`) z kolumnami do zapytań obok; pole dodane do obiektu domeny później ma wartość domyślną, więc starszy JSON dalej się odczytuje. Schemat ma wersje (`PRAGMA user_version`) i migruje się przy starcie. Import jest idempotentny: Faktura i Nota identyfikowane numerem, odczyt godzinowy trójką (PPE, koniec godziny, dodatkowa godzina) — nowszy raport nadpisuje wartości tej samej godziny, plik źródłowy hashem. Faktura korygująca zastępuje wartości korygowanej Faktury, a obie zostają w bazie. Wgrany plik jest kopiowany do `data/archive/`, żeby bazę dało się odbudować z plików.

### features

Każda funkcja dashboardu to pakiet `features/<nazwa>/` z dwiema częściami:

- `analysis.py`: czyste funkcje `(Repository, Filters) → wynik`, testowane bez Streamlita na adapterze w pamięci;
- `page.py`: obiekt `Feature` (id, tytuł, kolejność, `is_available(repository, ppe)`, `render(context)`), który rysuje wynik analizy. `is_available` decyduje, czy zakładka pojawia się dla danego PPE. Reguły leżą w `features/visibility.py`, wspólne dla zakładek i ustawień PPE: Magazyn energii przy net-meteringu, Dzień po dniu po wgraniu Profilu godzinowego tego PPE, Auto po włączeniu ładowania auta (zakładki Dzień po dniu i Auto jeszcze nie istnieją, reguły już tak).

`Filters` (`features/base.py`) to jeden PPE i Okres widoku (cały okres, rok, kwartał, miesiąc); `FeatureContext.filters` podaje go każdej zakładce. Analizy zwracają też stan na koniec Okresu widoku i ten sam okres rok wcześniej. Wspólna dla zakładek historia miesięczna leży w `features/monthly.py`: `History` (niezastąpione Faktury PPE rozłożone na miesiące; `totals` i `compare` dają sumy Okresu widoku — kWh, Koszt okresu, Grupy kosztów, Cena średnia kWh — i ten sam okres rok wcześniej), wykres miesiąc po miesiącu (`monthly_chart`: słupek dla miesiąca z własną Fakturą, blok ze średnią miesięczną dla Faktury za kilka miesięcy, z kWh i Kosztem okresu, kontur roku wcześniej, luki) i porównanie rok do roku (`year_over_year`: „analogiczny okres” z Faktury jako zapas i kontrola). `features/monthly_figure.py` rysuje ten wykres w Plotly jako energię (`energy_figure`) albo koszt (`cost_figure`). Przegląd (`features/overview/`) pokazuje wykres energii i rok do roku. Koszty i Faktury (`features/costs/`): `cost_summary` (Koszt okresu, Cena średnia kWh, Grupy kosztów, Bonifikaty i Akcyza w Okresie widoku, rok wcześniej), `unit_price_history` (ceny jednostkowe netto z Pozycji faktury, seria na składnik i strefę; `chart.py` rysuje je w czasie), lista Faktur i Not obciążeniowych. Magazyn energii (`features/energy_store/`, tylko PPE z net-meteringiem) pokazuje `EnergyStore` w Okresie widoku; kafelek Magazynu energii w Przeglądzie bierze stan z `EnergyStore.state_on`, bez importu tej zakładki. Górną część Przeglądu liczy `overview/tiles.py`: `invoice_status(repository, ppe, dziś)` (aktualne / Brakująca Faktura: koniec oczekiwanego okresu — miesiąc albo koniec harmonogramu Prognoz — plus 14 dni / odczyt szacunkowy), `next_payment(repository, ppe, dziś)` (pierwsza Prognoza z terminem od dziś, bez harmonogramu „do zapłaty” z Faktury) oraz ze stanem na koniec Okresu widoku `balance` (Saldo z Faktury plus Noty wystawione po niej) i `last_invoice`; „dziś” podaje wywołujący, więc testy go ustalają. `overview/top.py` rysuje je w HTML (`st.html`, podpowiedzi „?” jako `<details>`, kolory dziedziczone z motywu). `forecast_chart` w `overview/analysis.py` daje Prognozy z najnowszego harmonogramu jako linie obok Faktur; Prognozy nie wchodzą do żadnych sum. Podpowiedzi wspólne dla kilku widoków (np. „Magazyn energii to nie bateria…”, opisy Grup kosztów) są w `features/terms.py`. Widok Faktury (`features/invoice_view/`) nie jest zakładką: powłoka pokazuje go zamiast zakładek, gdy adres ma `&faktura=…`; `invoice_sheet(repository, ppe, numer)` zbiera „Fakturę po ludzku” (Grupy kosztów, Koszt okresu z Notami, sąsiednie Faktury, ten sam okres rok wcześniej, plik w archiwum), a `page.py` rysuje ją razem ze stylem druku. Oś czasu Faktur (`features/invoice_timeline/`) też nie jest zakładką, tylko częścią strony „Dane” w powłoce: `invoice_timeline(repository, ppe, dziś)` daje Okresy rozliczeniowe z Podstawą rozliczenia i korektami, Luki i Nakładanie się (z Faktur niezastąpionych), Noty obciążeniowe w dniu sprzedaży, Prognozy z aktualnych harmonogramów po ostatniej Fakturze (`current_forecasts` w `features/monthly.py`, wspólne z wykresem Prognoz w Przeglądzie) i miesiące z ostatnich 12 na odczycie szacunkowym (także z Faktur zastąpionych: korekta nie zdejmuje 🟡) oraz bez Faktury; `chart.py` rysuje ją w Plotly, a kliknięty Okres rozliczeniowy otwiera widok Faktury. Porównanie Profilu godzinowego z Fakturami (`features/profile_comparison/`) to także część strony „Dane”, bez zakładki: `profile_comparison(repository, ppe)` (`None` bez Profilu godzinowego) daje dla każdego niezastąpionego Okresu rozliczeniowego od pierwszego dnia Profilu (wcześniejsze tylko liczy), Energię pobraną i oddaną z Faktury i z Profilu (po Zbilansowaniu godzinowym), różnicę, „do sprawdzenia” powyżej 2% i liczbę dni bez pełnej doby (`hours_in_day` w `domain/hourly_profile.py`: 23 i 25 godzin w dniach zmiany czasu) zamiast różnicy. Zakładki otwierają Fakturę przez `features/navigation.py` (klucze adresu `okres` i `faktura`), bez importowania innej zakładki; stamtąd też otwierają stronę „Wgraj pliki” (`open_import`). Widok zawsze dotyczy jednego PPE, bez sum ani porównań między PPE. PPE, ich nazwy i ustawienia (np. ładowanie auta) są danymi w `storage`, dodawanymi przez kreator, nie stałymi w kodzie. Funkcje rejestrują się w `features/__init__.py`; dodanie funkcji to nowy pakiet plus jedna linia w rejestrze, bez zmian w `app` ani w innych funkcjach.

### app

Powłoka Streamlit: wybór PPE (adres `?ppe=…`, zawsze ustawiany na oglądany PPE, żeby dało się go zapisać w zakładkach przeglądarki; w pasku bocznym przyciski PPE i „Dodaj punkt poboru”; nieznany adres pokazuje pierwszy PPE z komunikatem), przełącznik Okresu widoku pod nazwą PPE (`app/view_period_switcher.py`, adres `&okres=…`, wspólny dla zakładek), kreator dodawania PPE, strona importu (upload → `ingest` → `storage`, pokazuje ostrzeżenia parsera i pyta o nowy PPE), zakładki z rejestru `features` dostępne dla wybranego PPE albo, z `&faktura=…` w adresie, widok Faktury. Uruchamiana dwuklikiem w `Start.bat`. Nie zawiera logiki obliczeń.

Strona „Ustawienia” (`app/settings_page.py`, przycisk w pasku bocznym) zmienia nazwę, ikonę i ładowanie auta wybranego PPE (adres strony zostaje), pokazuje adres strony i które zakładki są widoczne z podpowiedzią, czego brakuje, oraz usuwa PPE po wpisaniu jego nazwy: `delete_metering_point` w `app/data_maintenance.py` usuwa PPE z bazy razem z Fakturami, Notami obciążeniowymi i Profilem godzinowym oraz kopie jego plików z archiwum, więc przebudowa ich nie przywróci.

Strona „Dane” (`app/data_page.py`, przycisk w pasku bocznym, nie zakładka — narzędzia porządkowe są dla osoby wgrywającej pliki) pokazuje oś czasu Faktur wybranego PPE, listę Faktur z usuwaniem po potwierdzeniu, przy Profilu godzinowym sekcję „Profil godzinowy a Faktury” (`features/profile_comparison/`) i przebudowę bazy. Logika bez Streamlita jest w `app/data_maintenance.py`: `delete_invoice` usuwa Fakturę z bazy i jej kopię z archiwum (przebudowa jej nie przywróci, plik można wgrać ponownie), `rebuild` czyści dokumenty (`Repository.clear_documents`; PPE zostają) i importuje od nowa przez `import_files` pliki znane bazie w kolejności wgrania (`Repository.list_source_files`), a potem kopie z archiwum, których baza nie zna (np. odrzucone przy poprzedniej przebudowie); podsumowanie jak przy imporcie.

Logika importu bez Streamlita leży w `app/batch_import.py` i jest seamem testów strony importu i kreatora: `import_files(repository, archive, files, waiting=...) -> ImportSummary` (zaimportowane, duplikaty, odrzucone z powodem, Faktury nowych PPE czekające na kreator) oraz `add_new_metering_point(...) -> AddedMeteringPoint`, które dodaje PPE i kontynuuje import jego Faktur; PPE, który już jest w aplikacji (podwójne kliknięcie, dodany w międzyczasie), tylko dostaje czekające Faktury, bez zmiany ustawień (`already_existed`). `waiting` to czekające PPE z poprzedniej paczki: ich pliki przechodzą import przed nowymi, więc kolejna paczka dopisuje się do czekających, a duplikaty między paczkami są pomijane. Czekające pliki żyją tylko w sesji; strona „Wgraj pliki” pyta o potwierdzenie przed wyjściem, gdy jakieś czekają. Kolejność dla pliku: duplikat po hashu → `ingest` → duplikat po numerze Faktury (Noty) → PPE znany? Raport wartości godzinowych pomija sprawdzenie numeru: godziny znanego PPE dopisują się do Profilu godzinowego, raport nieznanego PPE jest odrzucany. Tylko dokument znanego PPE trafia do bazy, a jego plik do archiwum (`storage/archive.py`, `data/archive/`): najpierw kopia w archiwum, potem dokument z wpisem pliku w jednej transakcji (kopię bez wpisu wczyta przebudowa bazy). Nota nieznanego PPE czeka razem z Fakturami tego PPE z tej samej paczki (Nota nie ma danych do kreatora); bez nich jest odrzucana. Odczyt pliku jest wstrzykiwany, więc testy podają zrzuty wierszy zamiast PDF-ów.
