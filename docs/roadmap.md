# Roadmapa

Statusy: **pomysł** → **do doprecyzowania** → **gotowe do implementacji** → **w trakcie** → **zrobione**.

## Ustalone fakty

- Fotowoltaika jest w PPE Dom (net-metering, 0,8). Mieszkanie nie ma fotowoltaiki.
- Oba PPE: grupa taryfowa G11. Moc umowna: Dom 13 kW, Mieszkanie 5 kW.
- Historia w `References/`: Dom od XII 2022, Mieszkanie od IX 2024.
- eLicznik jest dostępny tylko dla Domu; Mieszkanie ma wyłącznie Faktury.

## Pierwsza wersja (MVP)

**Status:** zrobione (spec #1, zamknięta po odbiorze XI 2026). Szkielet aplikacji (#2): start dwuklikiem, ekran powitalny, `Repository` (SQLite i w pamięci), testy w CI; pierwsza Faktura przez kreator (#3): import Faktury w nowym układzie z kontrolą sum, kreator „Dodaj punkt poboru”, lista Faktur w Koszty i Faktury; import paczki (#4): strona „Wgraj Faktury”, duplikaty po hashu pliku i numerze Faktury, pytanie o nowy PPE, archiwum plików; Faktury w starym układzie (#5); Faktury korygujące i Noty obciążeniowe (#6); Okres widoku i wykres miesiąc po miesiącu (#8): rozkład Faktur na miesiące, przełącznik Okresu widoku w adresie strony, zakładka Przegląd z wykresem oddane/pobrane i tabelą rok do roku. Magazyn energii (#9): model porcji `EnergyStore`, zakładka Magazyn energii, kafelek w Przeglądzie. Górna część Przeglądu (#10): status Faktur (aktualne / Brakująca Faktura z przyciskiem „Wgraj Fakturę” / odczyt szacunkowy), zdanie na start z ostatniej Faktury, pasek porcji Magazynu energii, kafelki Saldo, Najbliższa płatność i Ostatnia Faktura, wykres „Prognozy Taurona a rzeczywistość” dla PPE bez fotowoltaiki. Zakładka Koszty (#11): Koszt okresu i Cena średnia kWh w Okresie widoku z rokiem wcześniej, wykres „Koszt miesięcznie” (blok ze średnią miesięczną dla Faktury za kilka miesięcy, kontur roku wcześniej), 5 Grup kosztów z opisem i Bonifikatami, Akcyza informacyjnie, ceny jednostkowe w czasie, Cena średnia kWh przy każdej Fakturze, odznaka 🟡 tylko przy odczycie szacunkowym. Strona danych (#12): przycisk „Dane” w pasku bocznym, oś czasu Faktur (kolor Podstawy rozliczenia, Luki, Nakładanie się, Faktury zastąpione i korygujące, Noty obciążeniowe, przyszłe Prognozy; kliknięcie otwiera Fakturę), liczba miesięcy z ostatnich 12 na odczycie szacunkowym i bez Faktury, usunięcie Faktury po potwierdzeniu (razem z kopią w archiwum), przebudowa bazy z archiwum z podsumowaniem jak przy imporcie. Ustawienia PPE (#13): przycisk „Ustawienia” w pasku bocznym (nazwa, ikona, ładowanie auta, adres strony, widoczne zakładki z podpowiedzią o eLiczniku, usunięcie PPE z jego danymi i archiwum po wpisaniu nazwy), przełączanie PPE i „Dodaj punkt poboru” w pasku bocznym, reguły widoczności zakładek (także Dzień po dniu i Auto, zanim powstaną te zakładki). Odbiór MVP (XI 2026, prawdziwe Faktury obu PPE, porównanie z prototypem): kreator kończy się na stronie „Wgraj pliki” z prośbą o pozostałe Faktury, tabela rok do roku w Przeglądzie ma wiersz „Do Magazynu energii” (przyrost z Faktur).

F1 + F1a + F0 + F2 + F3 w osobnych widokach PPE. Ustalenia z grillowania (XI 2026):
- Import obu układów faktur (stary 2022–2025 i nowy), Faktur korygujących i Not obciążeniowych.
- Faktura trafia do bazy tylko, gdy sumy się zgadzają: pozycje = Wynik rozliczenia, Magazyn energii początek + przyrost − odbiór = koniec (tolerancja bilansowania). Spadek Magazynu energii między kolejnymi Fakturami zapisywany jako Wygaśnięcie.
- Upload wielu PDF-ów naraz; PPE rozpoznawany z faktury, nazwa nadawana raz; duplikaty pomijane; podsumowanie: zaimportowane / duplikaty / odrzucone z powodem.
- Rozkład na miesiące: kWh i Składniki zmienne proporcjonalnie do dni, Składniki stałe po równo na miesiące okresu; miesiące z rozkładu oznaczone na wykresach.
- Magazyn energii: porcja wygasa 12 miesięcy po końcu okresu, w którym ją oddano; odbiór zdejmowany od najstarszej porcji; stan łączny zawsze z Faktury, podział na porcje i daty Wygaśnięcia oznaczone jako szacunek.
- Osobny podgląd dla każdego PPE (własny adres, np. `?ppe=dom`), bez porównań i sum między PPE — Dom oglądają rodzice. Zakładki: Przegląd, Magazyn energii (tylko Dom), Koszty i Faktury, Dzień po dniu (eLicznik, tylko Dom), Auto (od 2027, tylko Dom).
- Przegląd: status Faktur (aktualne / brakuje Faktury za okres / odczyt szacunkowy); kafelki: Magazyn energii z przyrostem w ostatnim miesiącu i Wygaśnięciem w 3 mies. (Dom), Saldo, najbliższa płatność, ostatnia Faktura; wykres miesięczny Energii oddanej (w górę) i pobranej (w dół) z konturem tego samego miesiąca rok wcześniej; tabela „ten miesiąc a rok temu”.
- Składniki kosztów tylko w zakładce Koszty i Faktury, po kliknięciu Faktury, z opisem każdej grupy prostym językiem.
- Pojęcia na ekranie mają podpowiedź „?” z wyjaśnieniem dla osób nieznających rozliczeń.
- Prototyp: `data/prototype-dashboard/index.html`, wariant D (lokalnie, poza gitem).
- Saldo = ostatni stan konta z Faktury; dla starszych okresów tylko „do zapłaty / do zwrotu”; bez ręcznego wpisywania wpłat.
- Cena średnia kWh liczona według GLOSSARY, nie przepisywana z Faktury (Tauron pomija kWh pokryte Opustem).
- Każda liczba ma źródło (Faktura, strona, link do PDF z archiwum); liczby wyliczone mają opis sposobu wyliczenia.
- Koszty w 5 grupach: Energia; Dystrybucja zmienna (składnik zmienny + jakościowa); Opłaty od kWh (OZE + kogeneracyjna); Opłata mocowa; Opłaty stałe (składnik stały, przejściowa, abonamentowa). Akcyza tylko informacyjnie. Pełne Pozycje faktury w szczegółach.
- F2 zawiera historię cen jednostkowych w czasie.
- Rok do roku liczony z własnej historii; wartość „analogiczny okres” z Faktury jako zapas przy braku historii i jako kontrola przy różnicy > 5%.
- Strona danych: oś czasu Faktur na PPE (luki, nakładanie, korekty, odczyty szacunkowe), usunięcie Faktury, przebudowa bazy z archiwum.
- Podstawa rozliczenia widoczna przy każdej Fakturze i każdym okresie (tabela, oś czasu, podpowiedzi wykresów): 🟢 odczyt rzeczywisty, 🟡 odczyt szacunkowy, ⚪ Prognoza.
- Prognozy z harmonogramów na wykresach jako przerywana linia obok rzeczywistości; nigdy nie wchodzą do Kosztu okresu ani kWh.
- Okres rozliczony na odczycie szacunkowym zostaje oznaczony 🟡 także po wyrównaniu kolejną Fakturą i po zastąpieniu Fakturą korygującą na odczycie rzeczywistym (XI 2026); strona danych pokazuje, ile z ostatnich 12 miesięcy opierało się na szacunku.
- Na ekranie „oddane do sieci” i „pobrane z sieci”; słowa „produkcja” i „zużycie” tylko w znaczeniu z GLOSSARY, gdy będą dane z falownika.
- Rodzice korzystają z aplikacji u Ciebie albo z własnej kopii repozytorium na swoim komputerze; aplikacja działa po skopiowaniu folderu, bez serwera, start dwuklikiem w `Start.bat`. Każda kopia ma własne `data/` i sama decyduje, które PPE monitoruje; Faktury można wgrywać w każdej kopii.
- Punkty poboru dodaje się w aplikacji (pierwsze uruchomienie i później w ustawieniach), nie w kodzie — szczegóły w F8.
- „Faktura po ludzku” w wersji do druku (F7) wchodzi do MVP.
- Przełącznik Okresu widoku i pełny widok Faktury (F9) wchodzą do MVP.
- Kolejność pracy: `/prototype` (lokalnie, prawdziwe liczby, poza gitem) → `/to-spec` → `/to-tickets`.

## Otwarte pytania ogólne

- Jaka jest moc instalacji PV i od kiedy działa?

## F1. Import faktur Tauron (PDF)

**Status:** zrobione. Faktura rozliczeniowa w nowym układzie (#3; warianty i pułapki w `docs/invoice-structure.md`), import paczki z duplikatami i archiwum (#4), Faktura rozliczeniowa w starym układzie (#5; tabele czytane z komórek po położeniu na stronie), Faktury korygujące i Noty obciążeniowe korekty (#6). Ograniczenia paczki (#14): Faktury czekające na nowy PPE dołączają do kolejnej paczki, a wyjście ze strony przy czekających pyta o potwierdzenie; dokument i wpis jego pliku zapisują się w jednej transakcji; kreator dla PPE, który już jest w aplikacji, importuje do niego czekające Faktury.

Otwarte pytania:
- Nota obciążeniowa nie podaje okresu, którego dotyczy; przypisujemy ją do Faktury, w której Okresie rozliczeniowym leży data sprzedaży Noty. Czy to zgodne z tym, jak Tauron rozumie premię prądową (np. przyznaną za 2024)?
- Pierwotna Nota obciążeniowa (bez słowa KOREKTA) i Faktura korygująca w nowym układzie: brak przykładów w danych, parser ich nie rozpoznaje.

Upload PDF → Faktura z Pozycjami faktury, Okresem rozliczeniowym, odczytami, Rozliczeniem OZE (Energia pobrana i oddana, Magazyn energii na początku i końcu, Udział Sprzedawcy), Saldem i harmonogramem Prognoz. Dwa układy faktur (stary i nowy), Faktury korygujące, Noty obciążeniowe. Ostrzeżenie przy nierozpoznanej pozycji.

## F1a. Rozkład okresów na miesiące

**Status:** zrobione (#8). Rozkład: kWh i Składniki zmienne proporcjonalnie do dni, Składniki stałe po równo na miesiące okresu, reszta Kosztu okresu (zaokrąglenia, Bonifikaty) proporcjonalnie do dni. Na wykresach Faktura za kilka miesięcy to jeden płaski blok ze średnią miesięczną (suma / dni × 30,44), nie słupki z rozkładu; rozkład służy tabelom, Okresowi widoku i porównaniom. Dokładniejszy podział z Profilu godzinowego dojdzie z F4.

Okresy rozliczeniowe mają od 1 do 12 miesięcy. Każdy okres rozkładany na miesiące kalendarzowe proporcjonalnie do liczby dni (później dokładniej z Profilu godzinowego), żeby wykresy miesięczne i porównania rok do roku były uczciwe. W UI zawsze widać, które miesiące pochodzą z rozkładu, a które z miesięcznej Faktury.

## F0. Saldo z Tauronem

**Status:** w trakcie. Zrobione (#10): Saldo na koniec Okresu widoku (z Faktury, z Notami obciążeniowymi wystawionymi po niej; gdy Faktura nie podaje Salda, tylko jej „do zapłaty / do zwrotu”), najbliższa płatność z harmonogramu Prognoz, Prognozy przerywaną linią obok Faktur (PPE bez fotowoltaiki). Zostało: Saldo w czasie, sygnał rosnącej nadpłaty (#19).

Otwarte pytania:
- Czy Saldo na następnej Fakturze zawiera już Noty obciążeniowe wystawione przed nią? Model tak zakłada (Nota liczy się w Saldzie tylko do następnej Faktury).
- Termin płatności samej Faktury nie jest odczytywany; bez harmonogramu Prognoz kafelek pokazuje kwotę bez terminu.

Saldo każdego PPE w czasie, Prognozy zapłacone vs. rzeczywisty koszt, nadchodzące płatności z harmonogramu. Sygnał, gdy nadpłata rośnie bez potrzeby (w PPE Dom nadpłata narasta, bo Opusty pokrywają pobór, a Prognozy były płacone).

## F2. Przegląd kosztów

**Status:** w trakcie. Zrobione (#11): zakładka Koszty i Faktury z Kosztem okresu, Ceną średnią kWh, rokiem wcześniej, 5 Grupami kosztów (część dłuższej Faktury według rozkładu na miesiące: grupy Składników zmiennych po dniach, Opłata mocowa i Opłaty stałe po równo) i historią cen jednostkowych (netto, jak na Fakturze; Faktura z kilkoma podokresami dzieli kreskę na równe części, bo nie podaje ich dat). Zostało: Cena krańcowa kWh (potrzebna do Ładowań, F5).

Koszt miesięczny dla każdego PPE i łącznie, podział na Składniki zmienne i stałe, Cena średnia kWh i Cena krańcowa kWh, porównanie rok do roku.

## F3. Magazyn energii

**Status:** zrobione (#9). Model porcji (`domain/energy_store.py`): porcja = przyrost z Faktury, wygasa 12 miesięcy po końcu Okresu rozliczeniowego, Opust zdejmowany od najstarszej porcji, suma porcji zawsze dopasowana do stanu z Faktury. Opust jak w widoku Faktury: Energia pobrana − kWh energii czynnej na Fakturze (to decyduje o pieniądzach); różnicę do bilansu Magazynu (zwykle 1 kWh, bilansowanie godzinowe) tabela pokazuje jako „Zaokrąglenie Taurona”. Wygaśnięcie to spadek stanu na start poniżej stanu na koniec poprzedniej Faktury, tylko gdy Faktury przylegają (przy luce spadek może być Opustem) i spadek przekracza tolerancję bilansu z kontroli sum (2 kWh; mniejszy to zaokrąglenie Taurona); w tabeli ruchu to osobny wiersz, żeby każdy wiersz się domykał. Na ekranie Opust to „w tym z Magazynu energii” obok pobranych z sieci (zamiast „− zużyte” z issue: „zużycie” to w GLOSSARY inne pojęcie, a „Opust” jest dla rodziców niejasny). Zakładka: stan na koniec Okresu widoku, porcje i co wygaśnie w 3 miesiące (szacunek), Udział Sprzedawcy, wykres stanu w czasie, tabela ruchu na każdą Fakturę. Kafelek w Przeglądzie: stan, przyrost z Faktury, z której jest stan (podpisany jej okresem, przy Fakturze za kilka miesięcy to przyrost za cały okres), co wygaśnie w 3 miesiące.

Otwarte pytania:
- Tauron rozlicza Wygaśnięcie zapewne miesiącami oddania, a model traktuje Fakturę za kilka miesięcy jako jedną porcję; dokładniejszy podział da Profil godzinowy (F4).

Do triage: Wygaśnięcie w przeliczeniu na dni poboru, ⚠ tylko przy porcji, której pobór nie zużyje (#20).

Stan Magazynu energii w czasie, przyrosty i odbiory na okres, Udział Sprzedawcy, Wygaśnięcia wyliczone z różnicy stanu końcowego i początkowego kolejnych Faktur, porcje wygasające w najbliższych 12 miesiącach.

## F4. Import Profilu godzinowego

**Status:** zrobione (poza eksportem CSV). Zrobione (XI 2026): import Raportu wartości godzinowych (xlsx od Tauron Dystrybucji) na stronie „Wgraj pliki”, zapis Profilu godzinowego w bazie (nowszy raport nadpisuje te same godziny), raport nieznanego PPE odrzucany. Lokalny test na prawdziwych danych: sumy po Zbilansowaniu godzinowym zgadzają się z Fakturami (różnica poniżej 1%), sumy przed zbilansowaniem są o kilkadziesiąt procent wyższe. Porównanie sum z Fakturami na stronie „Dane” (#16): dla każdego niezastąpionego Okresu rozliczeniowego, który Profil pokrywa choć jednym dniem, Energia pobrana i oddana z obu źródeł i różnica; powyżej 2% „do sprawdzenia”, przy niepełnym pokryciu liczba brakujących dni (doba pełna przy 23, 24 albo 25 godzinach); okresy po końcu Profilu mają wiersz z brakującymi dniami (przypomnienie o nowym Raporcie), a okresy sprzed jego początku są tylko policzone. Zakładka Dzień po dniu (#15): słupek na każdy dzień Okresu widoku (oddane w górę, pobrane w dół; dzień bez pełnego Profilu kreskowany), godziny klikniętego dnia (na start ostatni dzień z Profilem; 23 albo 25 słupków przy zmianie czasu), Typowa doba z podpowiedzią, w których godzinach panele dają nadwyżkę; tylko ilości po Zbilansowaniu godzinowym, podpowiedź „?” z prostym wyjaśnieniem. Przełącznik Okresu widoku sięga do ostatniego dnia Profilu (`view_extent`), widok na start dalej z Faktur. Zostało: eksport CSV z eLicznika, jeśli kiedyś będzie potrzebny. Do triage: przypomnienie o nowym Raporcie w Przeglądzie i w Dniu po dniu, gdy Profil godzinowy jest zaległy (#18).

Ustalenia z triage #15 (XI 2026):
- Zakładka Dzień po dniu: dni w Okresie widoku (oddane w górę, pobrane w dół), godziny klikniętego dnia, Typowa doba; tylko ilości po Zbilansowaniu godzinowym.
- Przełącznik Okresu widoku sięga do końca Profilu godzinowego, więc dni po ostatniej Fakturze są widoczne; widok na start bez zmian.
- Przegląd i Koszty biorą kWh z Faktur, nie z Profilu godzinowego (dokładniejszy rozkład na miesiące z Profilu — ewentualnie później).
- Porównanie z Fakturami tylko na stronie „Dane”: narzędzie dla osoby wgrywającej pliki.

Upload xlsx → Profil godzinowy dla PPE Dom (Mieszkanie nie ma eLicznika). Porównanie sum z Fakturami (ADR 0003).

Otwarte pytania:
- Profil godzinowy zapisuje czas lokalny jak w raporcie (koniec godziny i flaga dodatkowej godziny); analizy dobowe muszą pamiętać o dniach z 23 i 25 godzinami (Dzień po dniu: dodatkowa godzina to jeszcze jedna próbka w Typowej dobie, brakująca jej nie zaniża).

## F5. Profil zużycia

**Status:** w trakcie. Zrobione: Typowa doba w zakładce Dzień po dniu (#15). Zostało: dzień tygodnia, sezonowość, godziny szczytu.

Rozkład Energii pobranej i oddanej w ciągu doby i tygodnia, sezonowość, godziny szczytu.

## F6. Ładowanie auta

**Status:** do doprecyzowania (auto od początku 2027)

Rejestr Ładowań wprowadzanych ręcznie. Wyniki: Koszt ładowania na sesję i miesiąc, koszt na 100 km, udział ładowania w Energii pobranej, zmiana względem Linii bazowej, wpływ na Magazyn energii.

Obserwacja z faktur: w PPE Dom, dopóki Magazyn energii pokrywa pobór, Cena krańcowa kWh to tylko opłata OZE i kogeneracyjna (≈ 0,013 zł brutto/kWh w 2026), a w Mieszkaniu ok. 1 zł/kWh. Koszt ładowania zależy więc głównie od tego, czy Magazyn energii wystarczy.

Otwarte pytania:
- Skąd będzie wiadomo, ile kWh trwało Ładowanie: licznik ładowarki lub gniazdka, aplikacja auta, czy tylko czas ładowania × moc?
- W którym PPE auto będzie ładowane: tylko Dom, czy oba?
- Czy notować przebieg, żeby liczyć koszt na 100 km?
- Czy uwzględniać ładowania publiczne (inna cena, poza Fakturami)?
- Gdy Ładowanie zjada Magazyn energii: liczyć je po Cenie krańcowej kWh, czy jako „darmowe” kWh z fotowoltaiki?

## F7. Zestawienie do druku

**Status:** w trakcie. Zrobione: „Faktura po ludzku” (#7): widok Faktury drukuje się na 1 stronie A4 bez nawigacji, rozwinięta pełna lista Pozycji faktury na 2. stronie. Zostało: Podsumowanie roku.

Wydruk dla jednego PPE do segregatora: A4, z przeglądarki (Ctrl+P → drukarka albo „Zapisz jako PDF”), osobny styl druku bez zakładek i przycisków, czytelny w czerni i bieli, prostym językiem.
- **Faktura po ludzku** (MVP): jedna strona na Fakturę — okres, Podstawa rozliczenia, pobrane i oddane, ruch w Magazynie energii, Koszt okresu z opisem grup kosztów, Saldo po Fakturze, ten sam miesiąc rok wcześniej.
- **Podsumowanie roku** (zaraz po MVP): 1–2 strony — wykres miesięczny oddane/pobrane, Magazyn energii w czasie, koszt miesięcznie, suma roku.

## F8. Punkty poboru w aplikacji

**Status:** zrobione. Kreator z pierwszej Faktury (#3), pytanie o nowy PPE przy imporcie (#4), kolejne PPE z paska bocznego, ustawienia i usunięcie PPE, reguły widoczności zakładek (#13). Adres strony PPE (`?ppe=dom`) nie zmienia się po zmianie nazwy. Pasek boczny pokazuje wszystkie PPE tej kopii, bez ukrywania: każda kopia sama decyduje, które PPE dodaje (XI 2026).

Kreator przy pierwszym uruchomieniu i dodawanie kolejnych PPE w ustawieniach. Dodany później PPE działa tak samo jak pierwszy.
- Kreator zaczyna od Faktury: „Dodaj punkt poboru” → wgraj dowolną Fakturę → aplikacja odczytuje i pokazuje do potwierdzenia numer PPE, adres, grupę taryfową, moc umowną i rodzaj rozliczenia (net-metering = fotowoltaika, Współczynnik opustu) → użytkownik podaje tylko nazwę, ikonę (dom / mieszkanie / inne) i czy ładuje tu auto → wgraj pozostałe Faktury → Przegląd.
- Zakładki wynikają z danych PPE: Magazyn energii gdy Faktura mówi „net-metering”; Dzień po dniu po wgraniu pierwszego eksportu eLicznika (wcześniej podpowiedź w ustawieniach PPE); Auto po włączeniu w ustawieniach PPE.
- Faktura z nieznanego PPE przy zwykłym imporcie: pytanie „To Faktura z nowego punktu poboru (adres…). Dodać go?” → kreator od kroku z nazwą. Usunięcie PPE w ustawieniach usuwa jego dane z tej kopii, po potwierdzeniu.

## F9. Okresy i widok Faktury

**Status:** zrobione (MVP). Przełącznik Okresu widoku w adresie strony, Przegląd i Koszty i Faktury filtrowane Okresem widoku, informacja, z której Faktury wyliczono Okres widoku (#8); widok Faktury (`&faktura=…`) otwierany z listy Faktur i z Przeglądu, strzałki poprzednia / następna, „pokaż ten okres w Przeglądzie” (najmniejszy miesiąc, kwartał albo rok obejmujący Okres rozliczeniowy), rok wcześniej z rozkładu na miesiące (≈ dla części dłuższej Faktury) obok wartości Taurona (#7). Kafelek Magazynu energii ze stanem na koniec Okresu widoku (#9). Kafelki Salda i Ostatniej Faktury ze stanem na koniec Okresu widoku (#10). Wejście z osi czasu na stronie „Dane” (#12). „Analogiczny okres” z Faktury używany tylko, gdy Faktury pokrywają Okres widoku dokładnie (np. miesiąc z własną Fakturą). Wybrana zakładka w adresie strony (`&zakladka=…`, stały identyfikator zakładki; ukryta albo nieznana otwiera Przegląd, przełączenie PPE i „pokaż ten okres w Przeglądzie” wracają do Przeglądu, „Wróć” z widoku Faktury do zakładki, z której ją otwarto) (#17).

- Przełącznik Okresu widoku pod nazwą PPE: Cały okres · Rok · Kwartał · Miesiąc, strzałki ◀ ▶ do sąsiednich okresów; działa we wszystkich zakładkach. Kafelki ze stanem (Magazyn energii, Saldo) pokazują stan na koniec Okresu widoku; rok do roku = ten sam Okres widoku rok wcześniej.
- Okres widoku wycięty z dłuższej Faktury oznaczony ≈ ze zdaniem, z której Faktury wyliczony; okresy pokryte miesięcznymi Fakturami są dokładne.
- Widok Faktury (z listy, osi czasu, strzałkami poprzednia / następna): nagłówek (numer, data wystawienia, okres, rodzaj dokumentu i co koryguje, Podstawa rozliczenia, taryfa, moc, rodzaj rozliczenia); liczniki (stany, data, Typ odczytu); Rozliczenie OZE (pobrane, oddane, Magazyn energii start, ×0,8, przybyło, Udział Sprzedawcy, koniec); 5 grup kosztów z opisem i rozwijana pełna lista Pozycji faktury jak w oryginale (z podokresami); rozliczenie (Wynik, Prognozy/wpłaty, do zapłaty/zwrotu, Saldo, akcyza, Cena średnia kWh); harmonogram Prognoz; ten sam okres rok wcześniej (także wartość Taurona); „Otwórz oryginał PDF”.
- Widok Faktury = strona „Faktura po ludzku” (F7); na wydruku pozycje zwinięte do 5 grup na 1 stronie A4, pełna lista Pozycji opcjonalnie na 2. stronie.
- Miesiąc i Faktura połączone linkami: widok miesiąca → „Faktura za ten okres” (lub „część Faktury rocznej …”), widok Faktury → „pokaż ten okres w Przeglądzie”.

## Pomysły

- Dane z falownika: Produkcja i autokonsumpcja w Domu.

- Symulacja zmiany taryfy (G11 ↔ G12) na Profilu godzinowym.
- Prognoza kosztu następnej Faktury.
