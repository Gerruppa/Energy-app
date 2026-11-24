# Struktura faktur Tauron

Wyniki przeglądu 13 unikalnych dokumentów z `References/` (listopad 2026). Źródło wiedzy dla parsera (F1). Bez danych osobowych: numery PPE, klienta i adresy zostają w PDF-ach.

## Rodzaje dokumentów

| Rodzaj | Rozpoznanie (nagłówek) | Uwagi |
|---|---|---|
| Faktura rozliczeniowa, stary układ | `FAKTURA VAT ROZLICZENIOWA NR …` lub `FAKTURA VAT NR …` | do faktur wystawionych w 2025; tekst w kolumnach, wiersze z VAT 5% i 23% przeplatają się |
| Faktura rozliczeniowa, nowy układ | strona `To jest Twoja faktura` + strona `podsumowanie Twojej faktury` | od grudnia 2025; czyste tabele, jeden wiersz = jedna pozycja |
| Faktura korygująca | `FAKTURA VAT KOREKTA NR … DO FAKTURY VAT NR …` | stary układ także w 2026; sekcje `POLICZONO` i `NALEŻAŁO POLICZYĆ`, przyczyna korekty, kwota do zwrotu |
| Nota obciążeniowa korekta | `NOTA OBCIĄŻENIOWA KOREKTA NR …` | jedna strona, bonifikaty (np. obniżka z rozporządzenia MKiŚ); nie zawiera kWh |

Prefiks numeru wskazuje PPE: Dom ma inną serię niż Mieszkanie. Numer faktury jest unikalny i stabilny — klucz importu.

## Pola obecne we wszystkich fakturach rozliczeniowych

- **Nagłówek:** numer faktury, data wystawienia, Okres rozliczeniowy (od–do), numer PPE, nazwa obiektu, grupa taryfowa, moc umowna, rodzaj rozliczenia (`Net-metering` w nowym układzie).
- **Odczyty licznika:** licznik pobór / oddanie, strefa (`całodobowa` w G11), data i typ odczytu (Zdalny, Fizyczny, Odbiorcy, Szacunkowy), stan.
- **Rozliczenie OZE** (tylko PPE z fotowoltaiką): energia pobrana, energia wprowadzona, „Energia z magazynu” (stan Magazynu energii na początku okresu), współczynnik 0,8, energia po współczynniku; zdania `pozostało X kWh przez 12 miesięcy`, `do dyspozycji Sprzedawcy pozostaje Y kWh`, `pozostaje łączna ilość Z kWh`.
- **Sprzedaż energii:** energia czynna — ilość kWh, cena netto, wartość netto, VAT, brutto.
- **Dystrybucja:** zawsze ten sam zestaw siedmiu składników: składnik zmienny stawki sieciowej, stawka jakościowa, opłata OZE, opłata kogeneracyjna (od kWh); składnik stały stawki sieciowej, opłata przejściowa (do 2025), opłata abonamentowa, opłata mocowa (od miesięcy).
- **Podsumowanie:** sprzedaż, dystrybucja, wynik rozliczenia, prognoza z poprzedniej faktury lub wpłaty dodatkowe, do zapłaty / nadpłata / niedopłata, saldo nadpłaty na koncie (nowy układ).
- **Informacyjnie:** akcyza od kWh, „średnia cena za 1 kWh”, zużycie w analogicznym okresie poprzedniego roku.
- **Harmonogram prognoz** (gdy rozliczenie nie jest miesięczne): okresy, kWh, kwoty netto/VAT/brutto, terminy płatności.

## Zmienność, o którą parser musi zadbać

- **Długość okresu:** Dom — okresy roczne (do XI 2025), potem jeden 9-miesięczny (XII 2025–VIII 2026), od IX 2026 miesięczne. Mieszkanie — okresy ok. 6-miesięczne z miesięcznymi prognozami. Porównania wymagają przeliczenia na dzień lub rozłożenia na miesiące.
- **Pozycja w kilku wierszach:** gdy w trakcie okresu zmienia się cena (np. 1 stycznia) lub stawka VAT (5% → 23% w 2024), ten sam składnik pojawia się w kilku wierszach z innymi cenami i ilościami. Pozycja faktury = (składnik, podokres, cena, VAT).
- **Ilość 0 przy pokryciu z Magazynu energii:** energia czynna, składnik zmienny i stawka jakościowa mają ilość 0, gdy pobór pokrył Opust; opłata OZE i kogeneracyjna są naliczane od całej energii pobranej.
- **Liczby:** format polski (`1 234,56`, `0,50200`), kwoty ujemne przy zwrotach, akcyza potrafi mieć ujemne kWh w rozliczeniu prognoz.
- **Tekst warstwowy:** `pdftotext -layout` miesza kolumny w starym układzie; parser powinien czytać tabele po współrzędnych (pdfplumber), a nowy układ da się czytać wierszami.
- **Magazyn energii nie sumuje się wprost:** stan „Energia z magazynu” na początku okresu bywa niższy niż stan końcowy z poprzedniej faktury (spadek o kilkadziesiąt kWh między kolejnymi miesiącami): różnica to porcje, które wygasły po 12 miesiącach. Faktura nie podaje wygasania wprost.
- **Duplikaty plików:** te same PDF-y pod różnymi nazwami (`_1`, `-1`); import rozpoznaje je po hashu.

## Stary układ: warianty i pułapki (parser z #5)

Parser: `src/pv_app/ingest/old_layout.py`. Sprawdzony lokalnie na wszystkich Fakturach rozliczeniowych w starym układzie z `References/` (roczna z net-meteringiem, półroczna, półroczna z wymianą licznika); fixture'y z wymyślonymi liczbami w `tests/fixtures/old_layout_*.json`, wiersze tabel jako listy komórek.

- **Komórki zamiast tekstu:** w tekście odstęp tysięcy (`1 722`) wygląda jak granica kolumn, a kolumna współczynnika opłaty OZE i kogeneracyjnej (`1`) jak cyfra tysięcy (`1 722 1 0,00000`). Adapter dzieli wiersz na komórki tam, gdzie odstęp między znakami przekracza 5 pt (spacja i odstęp tysięcy mają 1–3 pt, kolumny tabel 10 pt i więcej); parser czyta tabele z komórek. Bywa, że dwie sąsiednie kolumny dają jedną komórkę (`839,95 13/10/2025` w harmonogramie); parser rozdziela tylko komórkę z datą, komórkę z samymi liczbami bierze w całości.
- **Rozpoznanie:** nagłówek `FAKTURA VAT ROZLICZENIOWA NR <numer> - …` albo `FAKTURA VAT NR <numer> - …`; Faktury korygujące (`FAKTURA VAT KOREKTA NR`) i Noty obciążeniowe nie pasują i są odrzucane jako nieobsługiwane (#6).
- **Dwa warianty:**
  - do III 2025: strona Faktury pierwsza, `Za okres od … do …`, załącznik w jednej kolumnie (`Nr punktu poboru:` bywa z dopiskiem `PPE`), nazwy składników zawinięte w dwa wiersze wokół wiersza liczb (`Składnik stały stawki` / `mc 1 …` / `sieciowej`);
  - od IX 2025: z przodu strony podsumowania (`Dzień dobry,` / `to jest podsumowanie Twojej faktury`, `Co 6 miesięcy`), Faktura na stronie 3 (`za okres od …`), załącznik w dwóch kolumnach (`Nr punktu poboru: | … | Nazwa obiektu: | …`), nazwy składników w jednej komórce. Częstotliwość (`Co 6 miesięcy`) stoi tylko na stronie podsumowania; nagłówek Faktury nie ma dla niej osobnego źródła, więc parser jej nie zapisuje.
- **Odczyty:** z kolumną `Mnożna` — stan bieżący, poprzedni, mnożna, ilość, straty, razem (bieżący przed poprzednim); przy net-meteringu tylko ilość. Typ odczytu literą w nawiasie po dacie (`30/11/2024 (Z)`). Wymiana licznika: dwa liczniki, każdy z własnym wierszem; Energia pobrana to ich suma.
- **Pozycje faktury:** nazwa składnika w komórce przed jednostką albo w wierszu nad wierszami stref (nagłówek grupy bywa w dwóch wierszach: `Składnik zmienny stawki` / `sieciowej`); wiersz liczb bez nazwy bierze nazwę z wierszy przed nim i jednego wiersza po nim. Po jednostce: ilość, [współczynnik], cena, netto, stawka VAT, VAT, brutto. Tabela dystrybucji przechodzi na kolejną stronę z powtórzonym nagłówkiem kolumn; kończy ją `Ogółem wartość`. Jak w nowym układzie podokres to kolejny wiersz tego samego składnika, bez dat. Wiersze z VAT 5% i 23% są osobnymi podokresami; w podsumowaniu stawka bywa wtedy `x` (w danych z `References/` wszystkie Faktury mają już 23%, wariant 5% jest tylko w fixture'ze).
- **Podsumowanie:** wiersze `N. | etykieta | netto | stawka | VAT | brutto [| kWh]` na stronie z numerem Faktury; `Do zapłaty ( 3 + 4 [- 5] )` ze znakiem (ujemna = zwrot); `Wpłaty dodatkowe` jedną kwotą. Saldo nie jest podawane. Akcyza: `Od [Ilości] X kWh … akcyzę w kwocie Y zł` na stronie Faktury (zdanie pod harmonogramem dotyczy Prognoz).
- **Harmonogram Prognoz:** jeden wiersz na Prognozę (numer blankietu, okres, kWh, kwoty). Kolejność kolumn kwot różni się: Faktura roczna z net-meteringiem ma netto, brutto, `x`, VAT, rabat, nadpłata/niedopłata, termin, do zapłaty; pozostałe netto, `x`, VAT, brutto, rabat, nadpłata/niedopłata, do zapłaty, termin. Parser ustawia kolumny po położeniu `x` i daty, a potwierdza je sumami netto + VAT = brutto i brutto + nadpłata/niedopłata = do zapłaty.

## Nowy układ: warianty i pułapki (parser z #3)

Parser: `src/pv_app/ingest/new_layout.py`. Sprawdzony lokalnie na wszystkich Fakturach w nowym układzie z `References/`; fixture'y z wymyślonymi liczbami w `tests/fixtures/new_layout_*.json`.

- **Tekst z PDF-a:** pogrubienia są drukowane trzykrotnie w tym samym miejscu (`SSSppprrr…`), więc adapter używa `dedupe_chars()`; kody QR i kreskowe dają ciągi `(cid:N)`, które adapter usuwa.
- **Rozpoznanie:** strona podsumowania `Dzień dobry, to jest podsumowanie Twojej faktury` (PPE, nazwa obiektu, adres, częstotliwość) i strona `To jest Twoja faktura` (tekst bywa sklejony: `Twojafaktura`) z numerem, datami, taryfą, mocą i podsumowaniem rozliczenia.
- **Dwa warianty w nowym układzie:**
  - Faktury wystawione w XII 2025 – III 2026: daty `dd/mm/rrrr`, etykiety `Sprzedaży energii elektrycznej`, `Świadczonych usług dystrybucji`, `Wartość prognozy z poprzedniej faktury`, `Do zapłaty ( 3 + 4 )`, tabela PPE `Numer Punktu Poboru Energii Grupa taryfowa Moc umowna`, kody Typu odczytu `(Z)`, `(O)`;
  - Faktury wystawione od IX 2026 (z IV–VIII 2026 nie ma Faktur w danych, więc dokładny moment zmiany jest nieznany): daty `dd.mm.rrrr`, etykiety `Sprzedaż …`, `Dystrybucja energii elektrycznej`, `Prognoza z poprzedniej faktury`, `Wpłaty dodatkowe`, `Razem (3-4)` / `NIEDOPŁATA (3+4)`, Typ odczytu słowem (`(Zdalny)` albo `Zdalny` w kolumnie).
- **Liczniki:** przy net-meteringu tabela podaje tylko ilość za okres (`całodobowa 31.10.2026 (Zdalny) 150,0000`), bez stanów. Bez fotowoltaiki są stany poprzedni / bieżący, ilość, straty i razem, czasem z kolumną `Mnożna`. Mnożna `1` przed ilością wygląda jak odstęp tysięcy (`520,0000 1 230,0000`), dlatego parser wybiera wzór wiersza po nagłówku `Mnożna`, nie po samych liczbach.
- **Podokresy Pozycji faktury:** nowy układ nie drukuje dat podokresów, tylko kolejne wiersze tego samego składnika (także `0 mc`). Pozycja faktury zapisuje więc numer podokresu (kolejność na Fakturze), nie zakres dat.
- **Składnik na dwóch stronach:** nagłówek składnika (np. `Opłata kogeneracyjna`) bywa na końcu strony, a jego wiersze na następnej, po powtórzonym nagłówku kolumn.
- **Harmonogram Prognoz:** trzy wiersze na Prognozę: numer blankietu (`<numer Faktury>/<n>`), kwoty z terminem, okres. Przy net-meteringu są dwie kolumny kWh (`Pobór Oddanie`).
- **Saldo:** tylko zdanie `Na Państwa koncie pozostała NADPŁATA|NIEDOPŁATA w kwocie …`; zdanie `Twoja NADPŁATA … została uwzględniona w płatnościach` dotyczy kwoty do zapłaty, nie Salda.
- **Akcyza:** pierwsze zdanie `Od X kWh sprzedawca odprowadzi akcyzę …` na stronie rozliczenia dotyczy Faktury; drugie (pod harmonogramem) dotyczy Prognoz.
- **Opust:** Faktura nie podaje go wprost. Liczony jako Energia pobrana minus kWh energii czynnej na Fakturze; bilans Magazynu energii: start + przyrost (po Współczynniku opustu) − Opust = koniec.
- **Kontrola sum:** suma brutto Pozycji = podsumowanie sprzedaży, dystrybucji i Wynik rozliczenia (tolerancja 0,02 zł); Do zapłaty = Wynik + Prognoza z poprzedniej Faktury − wpłaty dodatkowe; bilans Magazynu energii z tolerancją 2 kWh. Na prawdziwych Fakturach kwoty zgadzają się co do grosza, a Magazyn energii różni się najwyżej o 1 kWh (bilansowanie godzinowe).
- **Podstawa rozliczenia:** szacunkowy Typ odczytu na którymkolwiek liczniku (pobór lub oddanie) oznacza odczyt szacunkowy dla całej Faktury.
