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
- **Rozliczenie OZE** (tylko PPE z fotowoltaiką): energia pobrana, energia wprowadzona, „Energia z magazynu” (stan Banku kWh na początku okresu), współczynnik 0,8, energia po współczynniku; zdania `pozostało X kWh przez 12 miesięcy`, `do dyspozycji Sprzedawcy pozostaje Y kWh`, `pozostaje łączna ilość Z kWh`.
- **Sprzedaż energii:** energia czynna — ilość kWh, cena netto, wartość netto, VAT, brutto.
- **Dystrybucja:** zawsze ten sam zestaw siedmiu składników: składnik zmienny stawki sieciowej, stawka jakościowa, opłata OZE, opłata kogeneracyjna (od kWh); składnik stały stawki sieciowej, opłata przejściowa (do 2025), opłata abonamentowa, opłata mocowa (od miesięcy).
- **Podsumowanie:** sprzedaż, dystrybucja, wynik rozliczenia, prognoza z poprzedniej faktury lub wpłaty dodatkowe, do zapłaty / nadpłata / niedopłata, saldo nadpłaty na koncie (nowy układ).
- **Informacyjnie:** akcyza od kWh, „średnia cena za 1 kWh”, zużycie w analogicznym okresie poprzedniego roku.
- **Harmonogram prognoz** (gdy rozliczenie nie jest miesięczne): okresy, kWh, kwoty netto/VAT/brutto, terminy płatności.

## Zmienność, o którą parser musi zadbać

- **Długość okresu:** Dom — okresy roczne (do XI 2025), potem jeden 9-miesięczny (XII 2025–VIII 2026), od IX 2026 miesięczne. Mieszkanie — okresy ok. 6-miesięczne z miesięcznymi prognozami. Porównania wymagają przeliczenia na dzień lub rozłożenia na miesiące.
- **Pozycja w kilku wierszach:** gdy w trakcie okresu zmienia się cena (np. 1 stycznia) lub stawka VAT (5% → 23% w 2024), ten sam składnik pojawia się w kilku wierszach z innymi cenami i ilościami. Pozycja faktury = (składnik, podokres, cena, VAT).
- **Ilość 0 przy pokryciu z Banku kWh:** energia czynna, składnik zmienny i stawka jakościowa mają ilość 0, gdy pobór pokrył Opust; opłata OZE i kogeneracyjna są naliczane od całej energii pobranej.
- **Liczby:** format polski (`3 308,35`, `0,50200`), kwoty ujemne przy zwrotach, akcyza potrafi mieć ujemne kWh w rozliczeniu prognoz.
- **Tekst warstwowy:** `pdftotext -layout` miesza kolumny w starym układzie; parser powinien czytać tabele po współrzędnych (pdfplumber), a nowy układ da się czytać wierszami.
- **Bank kWh nie sumuje się wprost:** stan „Energia z magazynu” na początku okresu bywa niższy niż stan końcowy z poprzedniej faktury (spadek o kilkadziesiąt kWh między kolejnymi miesiącami): różnica to porcje, które wygasły po 12 miesiącach. Faktura nie podaje wygasania wprost.
- **Duplikaty plików:** te same PDF-y pod różnymi nazwami (`_1`, `-1`); import rozpoznaje je po hashu.
