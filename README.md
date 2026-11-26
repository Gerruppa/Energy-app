# PV app

Lokalny dashboard kosztów i energii elektrycznej zbudowany na Fakturach Tauron. Pokazuje, ile prądu dom pobrał z sieci i oddał do niej, ile to kosztowało, co jest w Magazynie energii (net-metering) i kiedy jego porcje wygasną, jakie jest Saldo z Tauronem oraz — gdy wgrasz dane z eLicznika — jak wygląda zużycie godzina po godzinie.

Aplikacja działa na Twoim komputerze, bez serwera i bez konta. Nie łączy się z Tauronem: dane wchodzą z plików, które sam pobierasz (PDF-y Faktur i Raporty wartości godzinowych). Wszystko zostaje w folderze `data/` obok aplikacji.

Pojęcia pisane wielką literą (Faktura, Magazyn energii, Okres widoku…) są opisane w [GLOSSARY.md](GLOSSARY.md); w aplikacji każde ma podpowiedź „?”.

## Wymagania

- Windows 10 lub 11 (start dwuklikiem przez `Start.bat`). Na innych systemach aplikacja też działa, ale uruchamia się ją z terminala (niżej).
- Przy pierwszym starcie dostęp do internetu: `Start.bat` instaluje [uv](https://docs.astral.sh/uv/) (menedżer Pythona) przez `winget`, a uv pobiera Pythona i biblioteki. Potem aplikacja działa offline.
- Przeglądarka internetowa.

## Instalacja

Pobierz repozytorium jednym ze sposobów:

- `git clone https://github.com/Gerruppa/Energy-app.git`, albo
- na GitHubie **Code → Download ZIP** i rozpakuj w dowolnym folderze.

Folder można później skopiować albo przenieść w inne miejsce lub na inny komputer; `Start.bat` sam odtworzy środowisko. Każda kopia ma własne `data/`, więc własne punkty poboru i Faktury.

## Uruchomienie

**Windows:** kliknij dwukrotnie `Start.bat`.

1. Przy pierwszym starcie skrypt instaluje uv (jednorazowo) i zależności; może to potrwać minutę lub dwie.
2. Otwiera się okno konsoli z napisem „Uruchamiam PV app”, a po chwili przeglądarka pod adresem <http://localhost:8501>.
3. Aby zatrzymać aplikację, zamknij okno konsoli.

Jeśli aplikacja już działa, kolejne uruchomienie `Start.bat` tylko otworzy przeglądarkę.

**Z terminala (każdy system, z zainstalowanym uv):**

```powershell
uv run python -m pv_app
```

Opcje startu:

| Opcja | Działanie |
|---|---|
| `--data-dir KATALOG` | inny katalog danych niż `data/` (np. osobna kopia do testów) |
| `--port N` | inny port niż 8501, np. żeby uruchomić drugą kopię obok pierwszej |
| `--no-browser` | nie otwieraj przeglądarki |
| `--today RRRR-MM-DD` | udawaj inną dzisiejszą datę (do sprawdzania komunikatów o Brakującej Fakturze i Zaległym Profilu godzinowym; tak samo działa zmienna `PV_APP_TODAY`) |

## Pierwsze kroki: dodanie punktu poboru

Na pustej aplikacji zobaczysz ekran „Witaj!” z przyciskiem **Dodaj punkt poboru**.

1. Wgraj jedną dowolną Fakturę Tauron (PDF) z tego punktu poboru.
2. Aplikacja odczyta z niej i pokaże do potwierdzenia: numer PPE, adres, grupę taryfową, moc umowną i rodzaj rozliczenia (net-metering, czyli fotowoltaika, ze Współczynnikiem opustu).
3. Nadaj punktowi nazwę (np. „Dom”), wybierz ikonę i zaznacz, czy ładujesz tu auto.
4. Kreator kończy się na stronie **Wgraj pliki** z prośbą o pozostałe Faktury tego punktu.

Kolejny punkt poboru dodasz przyciskiem **Dodaj punkt poboru** w pasku bocznym albo po prostu wgrywając jego Fakturę: aplikacja zapyta „To Faktura z nowego punktu poboru (adres…). Dodać go?”.

## Import danych

Przycisk **Wgraj pliki** w pasku bocznym. Można wybrać wiele plików naraz, z różnych punktów poboru i w dowolnej kolejności.

### Co można wgrać

| Plik | Skąd | Co daje |
|---|---|---|
| Faktura rozliczeniowa Tauron (PDF) | e-mail od Tauronu albo eBOK Tauron | kwoty, kWh pobrane i oddane, Magazyn energii, Saldo, harmonogram Prognoz |
| Faktura korygująca (PDF) | jw. | zastępuje korygowaną Fakturę we wszystkich wyliczeniach |
| Nota obciążeniowa (PDF) | jw. | zmienia Koszt okresu i Saldo (np. Bonifikaty) |
| Raport wartości godzinowych (xlsx) | serwis eLicznik Tauron Dystrybucji, pobrany ręcznie | Profil godzinowy: pobrane i oddane w każdej godzinie |

Obsługiwane są oba układy Faktur Tauron: stary (2022–2025) i nowy. Okres rozliczeniowy może mieć od 1 do 12 miesięcy.

### Co się dzieje przy imporcie

- **Kontrola sum.** Faktura trafia do bazy tylko wtedy, gdy jej liczby się zgadzają: Pozycje faktury dają Wynik rozliczenia, a Magazyn energii na początku + przyrost − odbiór = stan na koniec. Faktura, która nie przejdzie kontroli, jest odrzucona z podanym powodem.
- **Duplikaty są pomijane:** ten sam plik (po zawartości) i ten sam dokument (po numerze Faktury) nie wejdą drugi raz. Wgrywanie całego folderu jeszcze raz jest więc bezpieczne.
- **Raport wartości godzinowych** dopisuje godziny do Profilu godzinowego; nowszy raport nadpisuje te same godziny. Raport punktu poboru, którego nie ma w aplikacji, jest odrzucany: najpierw dodaj punkt poboru z Faktury.
- **Podsumowanie** po imporcie: zaimportowane, duplikaty, odrzucone (każde z przyczyną) i ostrzeżenia parsera.
- **Archiwum.** Każdy przyjęty plik jest kopiowany do `data/archive/`. Z archiwum aplikacja potrafi odbudować całą bazę, a widok Faktury otwiera z niego oryginalny PDF.

### Jak często

Dane wchodzą wsadowo, np. co 1–4 tygodnie. Aplikacja przypomina sama:

- **Brakująca Faktura:** gdy minęło ok. 14 dni od końca okresu, za który powinna przyjść kolejna Faktura, Przegląd pokazuje ⚠ z przyciskiem **Wgraj Fakturę**.
- **Zaległy Profil godzinowy:** gdy dane z eLicznika są starsze niż 14 dni, Przegląd i zakładka Dzień po dniu proponują pobranie nowego Raportu (**Wgraj Raport**).

## Co pokazuje aplikacja

Każdy punkt poboru ma osobny widok i własny adres strony (np. `http://localhost:8501/?ppe=dom`), który można zapisać w zakładkach przeglądarki. Aplikacja nie sumuje ani nie porównuje różnych punktów poboru.

### Okres widoku

Pod nazwą punktu poboru jest przełącznik: **Cały okres · Rok · Kwartał · Miesiąc** i strzałki ◀ ▶. Wybrany okres filtruje wszystkie zakładki i jest zapisany w adresie strony. Na start pokazuje się ostatni miesiąc objęty Fakturami w całości.

Liczby za miesiąc, który jest częścią dłuższej Faktury (np. rocznej), są wyliczone z rozkładu na miesiące (kWh i Składniki zmienne proporcjonalnie do dni, Składniki stałe po równo) i oznaczone **≈**.

### Zakładki

Zakładki pojawiają się zależnie od danych punktu poboru.

- **Przegląd** (zawsze)
  - status Faktur: aktualne / Brakująca Faktura / ostatnia Faktura na odczycie szacunkowym;
  - zdanie na start z ostatniej Faktury;
  - kafelki: Magazyn energii, Saldo (nadpłata albo niedopłata, z sygnałem Rosnącej nadpłaty i informacją, na ile miesięcy wystarczy), Najbliższa płatność, Ostatnia Faktura;
  - wykres miesiąc po miesiącu: oddane do sieci w górę, pobrane z sieci w dół, z konturem tego samego okresu rok wcześniej;
  - tabela „ten okres a rok wcześniej” (z własnych Faktur, a gdy ich brak — z wartości „analogiczny okres” podanej przez Tauron);
  - dla punktu bez fotowoltaiki: Prognozy Taurona na tle rzeczywistości.
- **Magazyn energii** (punkt z net-meteringiem)
  - stan na koniec Okresu widoku i porcje z datami Wygaśnięcia (porcja wygasa 12 miesięcy po okresie, w którym ją oddano);
  - co wygaśnie w ciągu 3 miesięcy, przeliczone na dni poboru domu: ✓ „zdąży się wykorzystać” albo ⚠ ile przepadnie;
  - Udział Sprzedawcy, wykres stanu w czasie, tabela ruchu dla każdej Faktury (na start, przybyło ×0,8, pobrane, w tym z Magazynu, wygasło, na koniec).
- **Koszty i Faktury** (zawsze)
  - Koszt okresu i Cena średnia kWh z rokiem wcześniej;
  - wykres „Koszt miesięcznie”;
  - 5 Grup kosztów z opisem prostym językiem (Energia, Dystrybucja zmienna, Opłaty od kWh, Opłata mocowa, Opłaty stałe), Bonifikaty, Akcyza informacyjnie;
  - ceny jednostkowe w czasie;
  - Saldo w czasie: punkt na każdą Fakturę i Notę obciążeniową;
  - lista Faktur i Not z Podstawą rozliczenia: 🟢 odczyt rzeczywisty, 🟡 szacunkowy, ⚪ Prognoza.
- **Dzień po dniu** (po wgraniu pierwszego Raportu wartości godzinowych)
  - słupek na każdy dzień Okresu widoku (oddane w górę, pobrane w dół);
  - godziny klikniętego dnia;
  - Typowa doba: średnia każdej godziny i godziny, w których panele dają nadwyżkę.

  Ilości są po Zbilansowaniu godzinowym, tak jak rozlicza je Tauron.

### Widok Faktury („Faktura po ludzku”)

Otwiera się z listy Faktur, z Przeglądu i z osi czasu na stronie „Dane”. Pokazuje nagłówek, odczyty liczników, rozliczenie OZE (Magazyn energii), 5 Grup kosztów z rozwijaną pełną listą Pozycji faktury, rozliczenie (Saldo, do zapłaty / do zwrotu), harmonogram Prognoz, ten sam okres rok wcześniej i przycisk **Otwórz oryginał PDF**. Strzałki przechodzą do poprzedniej i następnej Faktury.

**Druk:** `Ctrl+P` w przeglądarce drukuje Fakturę na 1 stronie A4, bez przycisków i nawigacji (pełna lista Pozycji faktury, jeśli rozwinięta, na 2. stronie). „Zapisz jako PDF” daje plik do archiwum.

### Strona „Dane” (pasek boczny)

Narzędzia dla osoby, która wgrywa pliki:

- **oś czasu Faktur:** Okresy rozliczeniowe w kolorze Podstawy rozliczenia, Luki, Nakładanie się, korekty, Noty i przyszłe Prognozy; kliknięcie otwiera Fakturę. Pod osią: ile z ostatnich 12 miesięcy opiera się na odczycie szacunkowym, a ile nie ma Faktury;
- **lista Faktur z usuwaniem** (po potwierdzeniu; usuwa też kopię z archiwum);
- **Profil godzinowy a Faktury:** porównanie kWh z eLicznika i z Faktur dla każdego Okresu rozliczeniowego; różnica powyżej 2% jest oznaczona „do sprawdzenia”;
- **przebudowa bazy:** czyści dokumenty i importuje od nowa wszystkie pliki z archiwum (np. po aktualizacji aplikacji, która lepiej czyta Faktury).

### Ustawienia (pasek boczny)

Nazwa, ikona i ładowanie auta dla wybranego punktu poboru (adres strony się nie zmienia), lista widocznych zakładek z podpowiedzią, czego brakuje, oraz usunięcie punktu poboru razem z jego danymi i plikami w archiwum (po wpisaniu jego nazwy).

### Skąd są liczby

Faktura jest źródłem prawdy dla kwot, a eLicznik dla profilu godzinowego. Każda liczba odczytana z Faktury ma podane źródło (numer Faktury i stronę), żeby dało się ją sprawdzić w PDF-ie. Liczby wyliczone (rozkład na miesiące, porcje Magazynu energii, szacunek Wygaśnięcia) są oznaczone i mają opis sposobu wyliczenia w podpowiedzi „?”. Prognozy nigdy nie wchodzą do Kosztu okresu ani do kWh.

## Dane i prywatność

- Baza (`data/pv_app.sqlite3`) i archiwum plików (`data/archive/`) leżą w folderze `data/` obok aplikacji. Folder jest poza gitem i nigdzie nie jest wysyłany.
- **Kopia zapasowa:** skopiuj folder `data/`. Gdyby baza się zepsuła, strona „Dane” → przebudowa odtworzy ją z archiwum.
- Aplikacja nie ma logowania. Działa pod adresem `localhost`, więc jest dostępna tylko na tym komputerze.

## Ograniczenia

- Tylko Faktury Tauron (sprzedaż i dystrybucja na jednej Fakturze). Pierwotna Nota obciążeniowa (bez słowa KOREKTA) i Faktura korygująca w nowym układzie nie są jeszcze rozpoznawane, bo brakuje przykładów.
- Brak danych z falownika, więc aplikacja nie zna produkcji paneli ani autokonsumpcji; pokazuje tylko energię oddaną do sieci i pobraną z sieci.
- W planach (zob. [docs/roadmap.md](docs/roadmap.md)): rejestr Ładowań auta i ich koszt, Cena krańcowa kWh, Podsumowanie roku do druku, analizy profilu zużycia (dzień tygodnia, sezonowość).

## Dla programistów

- Stos: Python 3.14, Streamlit, SQLite, pdfplumber, Plotly; zależności przez uv ([ADR 0001](docs/adr/0001-python-streamlit-sqlite.md)).
- Architektura i moduły: [docs/architecture.md](docs/architecture.md); decyzje: [docs/adr/](docs/adr/); budowa Faktur Tauron i pułapki parsowania: [docs/invoice-structure.md](docs/invoice-structure.md); zasady kodu: [CODING_STANDARDS.md](CODING_STANDARDS.md).
- Testy: `uv run pytest`; typy i styl: `uv run mypy`, `uv run ruff check .`.
- Kopia aplikacji do przeniesienia na inny komputer (bez testów, dokumentacji i danych): `uv run python scripts/build_app.py` tworzy folder `Builded app/`; wystarczy go skopiować i uruchomić w nim `Start.bat`.
- Dane do oglądania bez ruszania `data/`: `uv run python scripts/seed_demo.py demo-data`, potem `uv run python -m pv_app --data-dir demo-data --port 8502`.
- Repozytorium jest publiczne: testy używają wyłącznie syntetycznych fixture'ów, a hook `.githooks/pre-commit` (`git config core.hooksPath .githooks`) blokuje commit z danymi osobowymi.
