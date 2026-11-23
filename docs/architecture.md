# Architektura

Aplikacja jednoosobowa, uruchamiana lokalnie: Python + Streamlit + SQLite (ADR 0001). Pliki trafiają do aplikacji przez upload, są parsowane do obiektów domeny i zapisywane w bazie; widoki dashboardu czytają z bazy i liczą statystyki czystymi funkcjami.

## Przepływ danych

```
PDF faktury ─┐
             ├─► ingest ──► domain (obiekty) ──► storage (SQLite)
CSV eLicznik ┘                                        │
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

Słownik projektu w kodzie: `MeteringPoint`, `Invoice`, `InvoiceLine`, `BillingPeriod`, `HourlyReading`, `ChargingSession`. Obliczenia, które nie potrzebują I/O, mieszkają tutaj:

- `EnergyStore`: księga Magazynu energii. Porcje Energii oddanej × Współczynnik opustu z datą wygaśnięcia, Opusty zdejmowane od najstarszej porcji. Interfejs: zbuduj z historii Faktur, zapytaj o stan na dzień i porcje wygasające w zadanym oknie.
- Ceny: Cena średnia kWh i Cena krańcowa kWh dla Faktury.

Pozycje faktury są klasyfikowane do kategorii z `GLOSSARY.md` (Składnik zmienny / Składnik stały i ich rodzaje). Klasyfikacja jest częścią domeny, więc nowa nazwa pozycji na fakturze wymaga zmiany w jednym miejscu.

### ingest

Głęboki moduł z jednym wejściem: `import_file(path) -> ImportResult`. W środku:

1. rozpoznaje rodzaj pliku (faktura Tauron PDF, eksport eLicznika),
2. wybiera parser (adapter) dla tego rodzaju,
3. zwraca obiekty domeny z odnośnikiem do źródła (plik, strona) oraz listę ostrzeżeń, gdy czegoś nie rozpoznał.

Seam leży między rozpoznaniem a parserem: gdy Tauron zmieni układ faktury, dochodzi nowy parser obok starego, a reszta aplikacji się nie zmienia.

Każdy parser faktur ma dwa etapy (ADR 0005): cienki adapter PDF → surowe wiersze i tabele (pdfplumber) oraz głęboki moduł surowe wiersze → Faktura. Głęboki moduł testowany jest na zanonimizowanych zrzutach wierszy w `tests/fixtures/`. Po parsowaniu Faktura przechodzi kontrolę sum (pozycje = Wynik rozliczenia, bilans Magazynu energii); niezgodna jest odrzucana z opisem przyczyny.

### storage

Interfejs `Repository`: zapis obiektów domeny i zapytania potrzebne funkcjom (Faktury dla PPE w zakresie dat, Profil godzinowy, Ładowania). Dwa adaptery: SQLite (aplikacja) i w pamięci (testy funkcji).

Import jest idempotentny: Faktura identyfikowana numerem faktury, odczyt godzinowy parą (PPE, godzina), plik źródłowy hashem. Faktura korygująca zastępuje wartości korygowanej Faktury, a obie zostają w bazie. Wgrany plik jest kopiowany do `data/archive/`, żeby bazę dało się odbudować z plików.

### features

Każda funkcja dashboardu to pakiet `features/<nazwa>/` z dwiema częściami:

- `analysis.py`: czyste funkcje `(Repository, Filters) → wynik`, testowane bez Streamlita na adapterze w pamięci;
- `page.py`: obiekt `Feature` (id, tytuł, kolejność, `is_available(ppe)`, `render(context)`), który rysuje wynik analizy. `is_available` decyduje, czy zakładka pojawia się dla danego PPE (np. Magazyn energii tylko przy net-meteringu, Dzień po dniu tylko z danymi eLicznika).

`Filters` to jeden PPE i zakres dat; widok zawsze dotyczy jednego PPE, bez sum ani porównań między PPE. PPE, ich nazwy i ustawienia (np. ładowanie auta) są danymi w `storage`, dodawanymi przez kreator, nie stałymi w kodzie. Funkcje rejestrują się w `features/__init__.py`; dodanie funkcji to nowy pakiet plus jedna linia w rejestrze, bez zmian w `app` ani w innych funkcjach.

### app

Powłoka Streamlit: wybór PPE (adres `?ppe=…`), kreator dodawania PPE, strona importu (upload → `ingest` → `storage`, pokazuje ostrzeżenia parsera i pyta o nowy PPE), zakładki z rejestru `features` dostępne dla wybranego PPE, styl druku dla „Faktury po ludzku”. Uruchamiana dwuklikiem w `Start.bat`. Nie zawiera logiki obliczeń.
