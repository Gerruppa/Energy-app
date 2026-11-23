# PV app

Koszty i zużycie energii elektrycznej w dwóch punktach poboru rozliczanych przez Tauron, z fotowoltaiką w net-meteringu i ładowaniem auta plug-in.

## Punkty i faktury

**PPE (punkt poboru energii)**:
Miejsce dostarczania energii z własnym licznikiem i numerem PPE. W projekcie są dwa: Dom i Mieszkanie.
_Avoid_: licznik, punkt, lokalizacja

**Faktura**:
Dokument Tauron rozliczający jeden PPE za jeden Okres rozliczeniowy.
_Avoid_: rachunek

**Faktura korygująca**:
Faktura zmieniająca kwoty lub ilości z wcześniejszej Faktury.
_Avoid_: korekta (bez słowa faktura)

**Nota obciążeniowa**:
Dokument Tauron bez kWh, doliczający lub zwracający kwotę dla PPE (np. bonifikata z rozporządzenia).
_Avoid_: faktura (to nie jest Faktura)

**Prognoza**:
Zaliczkowa płatność za przyszły okres, wyliczona przez Tauron z przewidywanego zużycia i rozliczana w następnej Fakturze.
_Avoid_: blankiet, rata

**Saldo**:
Stan rozrachunku z Tauronem dla PPE po Fakturze: nadpłata (Tauron winien) lub niedopłata (do dopłaty).
_Avoid_: nadpłata/niedopłata jako osobne pojęcia

**Typ odczytu**:
Sposób ustalenia stanu licznika na Fakturze: zdalny, fizyczny, odbiorcy albo szacunkowy.

**Okres rozliczeniowy**:
Zakres dat, za który Faktura rozlicza energię.
_Avoid_: miesiąc (gdy okres nie jest miesiącem kalendarzowym)

**Pozycja faktury**:
Jedna linia kosztu na Fakturze: ilość, cena jednostkowa, kwota netto i brutto.
_Avoid_: wiersz, opłata (jako ogólne słowo)

**Składnik zmienny**:
Pozycja faktury naliczana od kWh: energia czynna, dystrybucja zmienna, opłata OZE, opłata kogeneracyjna, opłata jakościowa.
_Avoid_: koszt energii (jako ogólne słowo)

**Składnik stały**:
Pozycja faktury naliczana niezależnie od kWh: dystrybucja stała, opłata przejściowa, opłata abonamentowa, opłata mocowa.

## Energia

**Energia pobrana**:
kWh pobrane z sieci w PPE, zmierzone licznikiem.
_Avoid_: import, zużycie

**Energia oddana**:
kWh wprowadzone do sieci z fotowoltaiki, zmierzone licznikiem.
_Avoid_: eksport, produkcja

**Zużycie**:
Cała energia zużyta w PPE: Energia pobrana plus autokonsumpcja z fotowoltaiki. Faktury pokazują tylko Energię pobraną.
_Avoid_: pobór

**Profil godzinowy**:
Energia pobrana i oddana w PPE godzina po godzinie, z eksportu eLicznika.

## Fotowoltaika

**Net-metering**:
System opustów dla prosumentów przyłączonych przed 1.04.2022: energia oddana, pomnożona przez Współczynnik opustu, pomniejsza energię pobraną.
_Avoid_: net-billing (inny system, rozliczany w PLN; nie dotyczy projektu)

**Współczynnik opustu**:
Ile kWh do odebrania daje 1 kWh Energii oddanej. W projekcie 0.8.

**Bank kWh**:
Pula kWh do odebrania (Energia oddana × Współczynnik opustu), z datą wygaśnięcia dla każdej porcji; Tauron nazywa ją na Fakturze „magazynem energii”.
_Avoid_: magazyn, depozyt (depozyt prosumencki to pojęcie z net-billingu)

**Wygaśnięcie**:
Utrata porcji Banku kWh, której nie odebrano w ciągu 12 miesięcy.
_Avoid_: przepadek

**Udział Sprzedawcy**:
Część Energii oddanej, która nie trafia do Banku kWh (1 − Współczynnik opustu, czyli 20%).
_Avoid_: strata, prowizja

**Opust**:
kWh z Banku kWh odliczone od Energii pobranej na Fakturze.
_Avoid_: rabat, zniżka

## Koszty

**Cena średnia kWh**:
Kwota brutto Faktury podzielona przez Energię pobraną w jej Okresie rozliczeniowym.

**Cena krańcowa kWh**:
Koszt brutto jednej dodatkowej kWh Energii pobranej w danym PPE i Okresie rozliczeniowym: suma Składników zmiennych na kWh, bez Składników stałych.
_Avoid_: cena prądu (bez doprecyzowania)

## Auto

**Ładowanie**:
Jedna sesja ładowania auta plug-in z gniazdka w PPE, z datą i Energią ładowania.
_Avoid_: tankowanie

**Energia ładowania**:
kWh pobrane z sieci PPE podczas Ładowania (po stronie gniazdka, przed stratami ładowania).
_Avoid_: kWh w baterii

**Koszt ładowania**:
Energia ładowania razy Cena krańcowa kWh w PPE i Okresie rozliczeniowym, w którym odbyło się Ładowanie.

**Linia bazowa**:
Energia pobrana w PPE w okresie przed pierwszym Ładowaniem, służąca do porównania zmian w zużyciu po rozpoczęciu ładowania.
_Avoid_: baseline
