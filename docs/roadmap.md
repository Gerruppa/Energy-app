# Roadmapa

Statusy: **pomysł** → **do doprecyzowania** → **gotowe do implementacji** → **w trakcie** → **zrobione**.

## Ustalone fakty

- Fotowoltaika jest w PPE Dom (net-metering, 0,8). Mieszkanie nie ma fotowoltaiki.
- Oba PPE: grupa taryfowa G11. Moc umowna: Dom 13 kW, Mieszkanie 5 kW.
- Historia w `References/`: Dom od XII 2022, Mieszkanie od IX 2024.
- eLicznik jest dostępny tylko dla Domu; Mieszkanie ma wyłącznie Faktury.

## Pierwsza wersja (MVP)

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
- Okres rozliczony na odczycie szacunkowym zostaje oznaczony 🟡 także po wyrównaniu kolejną Fakturą; strona danych pokazuje, ile z ostatnich 12 miesięcy opierało się na szacunku.
- Na ekranie „oddane do sieci” i „pobrane z sieci”; słowa „produkcja” i „zużycie” tylko w znaczeniu z GLOSSARY, gdy będą dane z falownika.
- Rodzice korzystają z aplikacji u Ciebie albo z własnej kopii repozytorium na swoim komputerze; aplikacja działa po skopiowaniu folderu, bez serwera, start dwuklikiem w `Start.bat`. Każda kopia ma własne `data/` i sama decyduje, które PPE monitoruje; Faktury można wgrywać w każdej kopii.
- Punkty poboru dodaje się w aplikacji (pierwsze uruchomienie i później w ustawieniach), nie w kodzie — szczegóły w F8.
- „Faktura po ludzku” w wersji do druku (F7) wchodzi do MVP.
- Kolejność pracy: `/prototype` (lokalnie, prawdziwe liczby, poza gitem) → `/to-spec` → `/to-tickets`.

## Otwarte pytania ogólne

- Jaka jest moc instalacji PV i od kiedy działa?

## F1. Import faktur Tauron (PDF)

**Status:** do doprecyzowania (struktura opisana w `docs/invoice-structure.md`)

Upload PDF → Faktura z Pozycjami faktury, Okresem rozliczeniowym, odczytami, Rozliczeniem OZE (Energia pobrana i oddana, Magazyn energii na początku i końcu, Udział Sprzedawcy), Saldem i harmonogramem Prognoz. Dwa układy faktur (stary i nowy), Faktury korygujące, Noty obciążeniowe. Ostrzeżenie przy nierozpoznanej pozycji.

## F1a. Rozkład okresów na miesiące

**Status:** pomysł (zależy od F1)

Okresy rozliczeniowe mają od 1 do 12 miesięcy. Każdy okres rozkładany na miesiące kalendarzowe proporcjonalnie do liczby dni (później dokładniej z Profilu godzinowego), żeby wykresy miesięczne i porównania rok do roku były uczciwe. W UI zawsze widać, które miesiące pochodzą z rozkładu, a które z miesięcznej Faktury.

## F0. Saldo z Tauronem

**Status:** pomysł (zależy od F1)

Saldo każdego PPE w czasie, Prognozy zapłacone vs. rzeczywisty koszt, nadchodzące płatności z harmonogramu. Sygnał, gdy nadpłata rośnie bez potrzeby (w PPE Dom nadpłata narasta, bo Opusty pokrywają pobór, a Prognozy były płacone).

## F2. Przegląd kosztów

**Status:** pomysł (zależy od F1)

Koszt miesięczny dla każdego PPE i łącznie, podział na Składniki zmienne i stałe, Cena średnia kWh i Cena krańcowa kWh, porównanie rok do roku.

## F3. Magazyn energii

**Status:** pomysł (zależy od F1)

Stan Magazynu energii w czasie, przyrosty i odbiory na okres, Udział Sprzedawcy, Wygaśnięcia wyliczone z różnicy stanu końcowego i początkowego kolejnych Faktur, porcje wygasające w najbliższych 12 miesiącach.

## F4. Import eksportu eLicznika

**Status:** pomysł (czeka na pierwszy eksport)

Upload CSV/XLSX → Profil godzinowy dla PPE Dom (Mieszkanie nie ma eLicznika). Porównanie sum z Fakturami (ADR 0003).

## F5. Profil zużycia

**Status:** pomysł (zależy od F4)

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

**Status:** gotowe do specyfikacji

Wydruk dla jednego PPE do segregatora: A4, z przeglądarki (Ctrl+P → drukarka albo „Zapisz jako PDF”), osobny styl druku bez zakładek i przycisków, czytelny w czerni i bieli, prostym językiem.
- **Faktura po ludzku** (MVP): jedna strona na Fakturę — okres, Podstawa rozliczenia, pobrane i oddane, ruch w Magazynie energii, Koszt okresu z opisem grup kosztów, Saldo po Fakturze, ten sam miesiąc rok wcześniej.
- **Podsumowanie roku** (zaraz po MVP): 1–2 strony — wykres miesięczny oddane/pobrane, Magazyn energii w czasie, koszt miesięcznie, suma roku.

## F8. Punkty poboru w aplikacji

**Status:** gotowe do specyfikacji (MVP)

Kreator przy pierwszym uruchomieniu i dodawanie kolejnych PPE w ustawieniach. Dodany później PPE działa tak samo jak pierwszy.
- Kreator zaczyna od Faktury: „Dodaj punkt poboru” → wgraj dowolną Fakturę → aplikacja odczytuje i pokazuje do potwierdzenia numer PPE, adres, grupę taryfową, moc umowną i rodzaj rozliczenia (net-metering = fotowoltaika, Współczynnik opustu) → użytkownik podaje tylko nazwę, ikonę (dom / mieszkanie / inne) i czy ładuje tu auto → wgraj pozostałe Faktury → Przegląd.
- Zakładki wynikają z danych PPE: Magazyn energii gdy Faktura mówi „net-metering”; Dzień po dniu po wgraniu pierwszego eksportu eLicznika (wcześniej podpowiedź w ustawieniach PPE); Auto po włączeniu w ustawieniach PPE.
- Faktura z nieznanego PPE przy zwykłym imporcie: pytanie „To Faktura z nowego punktu poboru (adres…). Dodać go?” → kreator od kroku z nazwą. Usunięcie PPE w ustawieniach usuwa jego dane z tej kopii, po potwierdzeniu.

## Pomysły

- Dane z falownika: Produkcja i autokonsumpcja w Domu.

- Symulacja zmiany taryfy (G11 ↔ G12) na Profilu godzinowym.
- Prognoza kosztu następnej Faktury.
