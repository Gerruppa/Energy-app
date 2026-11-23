# Roadmapa

Statusy: **pomysł** → **do doprecyzowania** → **gotowe do implementacji** → **w trakcie** → **zrobione**.

## Ustalone fakty

- Fotowoltaika jest w PPE Dom (net-metering, 0,8). Mieszkanie nie ma fotowoltaiki.
- Oba PPE: grupa taryfowa G11. Moc umowna: Dom 13 kW, Mieszkanie 5 kW.
- Historia w `References/`: Dom od XII 2022, Mieszkanie od IX 2024.

## Pierwsza wersja (MVP)

F1 + F1a + F0 + F2 + F3 z paskiem KPI. Ustalenia z grillowania (XI 2026):
- Import obu układów faktur (stary 2022–2025 i nowy), Faktur korygujących i Not obciążeniowych.
- Faktura trafia do bazy tylko, gdy sumy się zgadzają: pozycje = Wynik rozliczenia, Bank kWh początek + przyrost − odbiór = koniec (tolerancja bilansowania). Spadek Banku kWh między kolejnymi Fakturami zapisywany jako Wygaśnięcie.
- Upload wielu PDF-ów naraz; PPE rozpoznawany z faktury, nazwa nadawana raz; duplikaty pomijane; podsumowanie: zaimportowane / duplikaty / odrzucone z powodem.
- Rozkład na miesiące: kWh i Składniki zmienne proporcjonalnie do dni, Składniki stałe po równo na miesiące okresu; miesiące z rozkładu oznaczone na wykresach.
- Bank kWh: porcja wygasa 12 miesięcy po końcu okresu, w którym ją oddano; odbiór zdejmowany od najstarszej porcji; stan łączny zawsze z Faktury, podział na porcje i daty Wygaśnięcia oznaczone jako szacunek.
- Pasek KPI (Dom / Mieszkanie / suma): Saldo, Bank kWh i Wygaśnięcia w 3 mies., Koszt okresu ostatniej Faktury, koszt 12 mies., Cena średnia kWh 12 mies., następna Prognoza; zmiana rok do roku.
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
- Kolejność pracy: `/prototype` (lokalnie, prawdziwe liczby, poza gitem) → `/to-spec` → `/to-tickets`.

## Otwarte pytania ogólne

- Jaka jest moc instalacji PV i od kiedy działa?

## F1. Import faktur Tauron (PDF)

**Status:** do doprecyzowania (struktura opisana w `docs/invoice-structure.md`)

Upload PDF → Faktura z Pozycjami faktury, Okresem rozliczeniowym, odczytami, Rozliczeniem OZE (Energia pobrana i oddana, Bank kWh na początku i końcu, Udział Sprzedawcy), Saldem i harmonogramem Prognoz. Dwa układy faktur (stary i nowy), Faktury korygujące, Noty obciążeniowe. Ostrzeżenie przy nierozpoznanej pozycji.

## F1a. Rozkład okresów na miesiące

**Status:** pomysł (zależy od F1)

Okresy rozliczeniowe mają od 1 do 12 miesięcy. Każdy okres rozkładany na miesiące kalendarzowe proporcjonalnie do liczby dni (później dokładniej z Profilu godzinowego), żeby wykresy miesięczne i porównania rok do roku były uczciwe. W UI zawsze widać, które miesiące pochodzą z rozkładu, a które z miesięcznej Faktury.

## F0. Saldo z Tauronem

**Status:** pomysł (zależy od F1)

Saldo każdego PPE w czasie, Prognozy zapłacone vs. rzeczywisty koszt, nadchodzące płatności z harmonogramu. Sygnał, gdy nadpłata rośnie bez potrzeby (w PPE Dom nadpłata narasta, bo Opusty pokrywają pobór, a Prognozy były płacone).

## F2. Przegląd kosztów

**Status:** pomysł (zależy od F1)

Koszt miesięczny dla każdego PPE i łącznie, podział na Składniki zmienne i stałe, Cena średnia kWh i Cena krańcowa kWh, porównanie rok do roku.

## F3. Bank kWh

**Status:** pomysł (zależy od F1)

Stan Banku kWh w czasie, przyrosty i odbiory na okres, Udział Sprzedawcy, Wygaśnięcia wyliczone z różnicy stanu końcowego i początkowego kolejnych Faktur, porcje wygasające w najbliższych 12 miesiącach.

## F4. Import eksportu eLicznika

**Status:** pomysł (czeka na pierwszy eksport)

Upload CSV/XLSX → Profil godzinowy dla PPE. Porównanie sum z Fakturami (ADR 0003).

## F5. Profil zużycia

**Status:** pomysł (zależy od F4)

Rozkład Energii pobranej i oddanej w ciągu doby i tygodnia, sezonowość, godziny szczytu.

## F6. Ładowanie auta

**Status:** do doprecyzowania (auto od początku 2027)

Rejestr Ładowań wprowadzanych ręcznie. Wyniki: Koszt ładowania na sesję i miesiąc, koszt na 100 km, udział ładowania w Energii pobranej, zmiana względem Linii bazowej, wpływ na Bank kWh.

Obserwacja z faktur: w PPE Dom, dopóki Bank kWh pokrywa pobór, Cena krańcowa kWh to tylko opłata OZE i kogeneracyjna (≈ 0,013 zł brutto/kWh w 2026), a w Mieszkaniu ok. 1 zł/kWh. Koszt ładowania zależy więc głównie od tego, czy Bank kWh wystarczy.

Otwarte pytania:
- Skąd będzie wiadomo, ile kWh trwało Ładowanie: licznik ładowarki lub gniazdka, aplikacja auta, czy tylko czas ładowania × moc?
- W którym PPE auto będzie ładowane: tylko Dom, czy oba?
- Czy notować przebieg, żeby liczyć koszt na 100 km?
- Czy uwzględniać ładowania publiczne (inna cena, poza Fakturami)?
- Gdy Ładowanie zjada Bank kWh: liczyć je po Cenie krańcowej kWh, czy jako „darmowe” kWh z fotowoltaiki?

## Pomysły

- Symulacja zmiany taryfy (G11 ↔ G12) na Profilu godzinowym.
- Prognoza kosztu następnej Faktury.
