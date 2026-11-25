# PV app

Koszty i zużycie energii elektrycznej w dwóch punktach poboru rozliczanych przez Tauron, z fotowoltaiką w net-meteringu i ładowaniem auta plug-in.

## Punkty i faktury

**PPE (punkt poboru energii)**:
Miejsce dostarczania energii z własnym licznikiem i numerem PPE, dodane w aplikacji pod nazwą nadaną przez użytkownika (dziś: Dom i Mieszkanie).
_Avoid_: licznik, punkt, lokalizacja

**Faktura**:
Dokument Tauron rozliczający jeden PPE za jeden Okres rozliczeniowy.
_Avoid_: rachunek

**Faktura korygująca**:
Faktura zmieniająca kwoty lub ilości z wcześniejszej Faktury; jej część „należało policzyć” zastępuje rozliczenie korygowanej Faktury, także gdy tej nie ma w danych.
_Avoid_: korekta (bez słowa faktura)

**Nota obciążeniowa**:
Dokument Tauron bez kWh, doliczający lub zwracający kwotę dla PPE (np. bonifikata z rozporządzenia). Dotyczy Okresu rozliczeniowego, w którym leży jej data sprzedaży; w Saldzie liczy się od daty wystawienia. Nota korygująca zastępuje korygowaną Notę.
_Avoid_: faktura (to nie jest Faktura)

**Bonifikata**:
Obniżka należności przyznana przez Tauron (np. premia prądowa z rozporządzenia MKiŚ), na Nocie obciążeniowej albo w części „należało policzyć” Faktury korygującej. Pomniejsza Koszt okresu, którego dotyczy.
_Avoid_: rabat, zniżka, premia (bez doprecyzowania)

**Faktura zastąpiona**:
Faktura, którą koryguje Faktura korygująca z danych. Zostaje w bazie i na liście Faktur, ale do obliczeń liczy się korekta.

**Prognoza**:
Zaliczkowa płatność za przyszły okres, wyliczona przez Tauron z przewidywanego zużycia i rozliczana w następnej Fakturze.
_Avoid_: blankiet, rata

**Saldo**:
Stan rozrachunku z Tauronem dla jednego PPE po Fakturze: nadpłata (Tauron winien) lub niedopłata (do dopłaty). Saldo jednego PPE nie przechodzi na inny.
_Avoid_: nadpłata/niedopłata jako osobne pojęcia

**Brakująca Faktura**:
Faktura za Okres rozliczeniowy, który już się skończył, a której po zwykłym czasie wystawienia (ok. 2 tygodnie) nie ma w danych.

**Luka**:
Dni między pierwszą a ostatnią Fakturą PPE, których nie rozlicza żadna Faktura (bez Faktur zastąpionych). Sumy Okresu widoku z Luką są niepełne.
_Avoid_: dziura, brak danych (gdy chodzi o brak Faktury)

**Nakładanie się**:
Dni rozliczone przez dwie Faktury naraz, z których żadna nie koryguje drugiej; liczą się w sumach dwa razy. Faktura korygująca za ten sam okres co Faktura zastąpiona to nie Nakładanie się.

**Typ odczytu**:
Sposób ustalenia stanu licznika na Fakturze: zdalny, fizyczny, odbiorcy albo szacunkowy.

**Podstawa rozliczenia**:
Na czym opierają się liczby danego okresu: odczyt rzeczywisty (Typ odczytu zdalny, fizyczny lub odbiorcy), odczyt szacunkowy albo Prognoza. Tylko dwie pierwsze wchodzą do Kosztu okresu i Energii pobranej.
_Avoid_: prognoza (jako określenie odczytu szacunkowego)

**Okres rozliczeniowy**:
Zakres dat, za który Faktura rozlicza energię.
_Avoid_: miesiąc (gdy okres nie jest miesiącem kalendarzowym)

**Okres widoku**:
Zakres dat wybrany do oglądania: cały okres, rok, kwartał albo miesiąc. Nie musi pokrywać się z Okresem rozliczeniowym żadnej Faktury.
_Avoid_: okres (bez doprecyzowania, gdy chodzi o wybór w widoku)

**Rozkład na miesiące**:
Podział Faktury na miesiące kalendarzowe: kWh i Składniki zmienne proporcjonalnie do dni, Składniki stałe po równo na miesiące okresu. Liczby Okresu widoku wycięte z dłuższej Faktury są oznaczone ≈; na wykresach taka Faktura to jeden blok ze średnią miesięczną.

**Pozycja faktury**:
Jedna linia kosztu na Fakturze: ilość, cena jednostkowa, kwota netto i brutto.
_Avoid_: wiersz, opłata (jako ogólne słowo)

**Składnik zmienny**:
Pozycja faktury naliczana od kWh: energia czynna, dystrybucja zmienna, opłata OZE, opłata kogeneracyjna, opłata jakościowa.
_Avoid_: koszt energii (jako ogólne słowo)

**Składnik stały**:
Pozycja faktury naliczana niezależnie od kWh: dystrybucja stała, opłata przejściowa, opłata abonamentowa, opłata mocowa.

**Grupa kosztów**:
Jedna z pięciu grup, w które „Faktura po ludzku” zbiera Pozycje faktury: Energia (energia czynna), Dystrybucja zmienna (składnik zmienny stawki sieciowej, stawka jakościowa), Opłaty od kWh (OZE, kogeneracyjna), Opłata mocowa, Opłaty stałe (dystrybucja stała, opłata przejściowa, opłata abonamentowa).
_Avoid_: kategoria (to Składnik zmienny / stały)

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

**Produkcja**:
Cała energia wytworzona przez fotowoltaikę: Energia oddana plus autokonsumpcja. Ani Faktury, ani eLicznik jej nie pokazują; znana tylko z danych falownika.
_Avoid_: produkcja jako nazwa Energii oddanej

**Profil godzinowy**:
Energia pobrana i oddana w PPE godzina po godzinie, z Raportu wartości godzinowych (albo eksportu eLicznika). Godzina jest oznaczona końcem: „1:00” to godzina od północy do pierwszej.

**Raport wartości godzinowych**:
Plik xlsx od Tauron Dystrybucji z Profilem godzinowym jednego PPE: dla każdej godziny Energia pobrana i oddana przed zbilansowaniem i po nim. Przy zmianie czasu na zimowy godzina „3:00” występuje dwa razy, druga z flagą „Godz dodat”.
_Avoid_: eksport, raport godzinowy

**Typowa doba**:
Średnia Energia pobrana i oddana w każdej godzinie doby, z Profilu godzinowego w Okresie widoku (po Zbilansowaniu godzinowym). Pokazuje, o której panele dają nadwyżkę, a kiedy dom pobiera z sieci.
_Avoid_: profil dobowy, średni dzień

**Zbilansowanie godzinowe**:
Tauron odejmuje w każdej godzinie mniejszą z Energii pobranej i oddanej od większej; Faktura rozlicza ilości po zbilansowaniu. Ilości przed zbilansowaniem (ECP, ECO) to surowe wskazania licznika, po zbilansowaniu (ECBP, ECBO) to Energia pobrana i oddana z Faktury.

## Fotowoltaika

**Net-metering**:
System opustów dla prosumentów przyłączonych przed 1.04.2022: energia oddana, pomnożona przez Współczynnik opustu, pomniejsza energię pobraną.
_Avoid_: net-billing (inny system, rozliczany w PLN; nie dotyczy projektu)

**Współczynnik opustu**:
Ile kWh do odebrania daje 1 kWh Energii oddanej. W projekcie 0.8.

**Magazyn energii**:
Pula kWh do odebrania (Energia oddana × Współczynnik opustu), z datą wygaśnięcia dla każdej porcji; nazwa taka jak na Fakturze. To rozliczenie w Tauronie, nie fizyczne urządzenie.
_Avoid_: Bank kWh, depozyt (depozyt prosumencki to pojęcie z net-billingu), bateria (zarezerwowane dla fizycznego magazynu, gdyby się pojawił)

**Wygaśnięcie**:
Utrata porcji Magazynu energii, której nie odebrano w ciągu 12 miesięcy.
_Avoid_: przepadek

**Udział Sprzedawcy**:
Część Energii oddanej, która nie trafia do Magazynu energii (1 − Współczynnik opustu, czyli 20%).
_Avoid_: strata, prowizja

**Opust**:
kWh z Magazynu energii odliczone od Energii pobranej na Fakturze. Na ekranie: „w tym z Magazynu energii” przy pobranych z sieci; słowo „Opust” tylko w podpowiedziach, jako nazwa z Faktury.
_Avoid_: rabat, zniżka, zużyte (z Magazynu energii)

## Koszty

**Koszt okresu**:
Wynik rozliczenia brutto Faktury (sprzedaż + dystrybucja) pomniejszony o Bonifikaty: z samej Faktury (Faktura korygująca) i z Not obciążeniowych dotyczących tego Okresu rozliczeniowego. Faktura zastąpiona nie ma własnego Kosztu okresu w obliczeniach. Kwoty w dashboardzie są brutto.
_Avoid_: do zapłaty, rachunek (to kwestie Salda, nie kosztu)

**Cena średnia kWh**:
Koszt okresu podzielony przez Energię pobraną w tym Okresie rozliczeniowym.

**Cena jednostkowa**:
Cena netto jednej jednostki Pozycji faktury (zł za kWh albo zł za miesiąc), tak jak na Fakturze. Faktura może mieć kilka podokresów z różnymi cenami tego samego składnika; nie podaje ich dat.

**Akcyza**:
Podatek od energii zawarty w cenach Pozycji faktury; Faktura podaje go tylko informacyjnie, więc nie dolicza się go do Kosztu okresu.

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
