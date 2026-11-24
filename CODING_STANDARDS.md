# Standardy kodu (dla recenzenta)

Reguły do oceny przy przeglądzie diffu. Rzeczy mechaniczne sprawdzają narzędzia: ruff, mypy, `tests/test_no_personal_data.py` (dane z prawdziwych Faktur) i `tests/test_ui_vocabulary.py` (słowa z `_Avoid_` na ekranie). Konwencje ogólne są w `CLAUDE.md` (*Konwencje*), a język domeny w `GLOSSARY.md`.

## Źródło każdej wartości

Wartość odczytana z Faktury niesie `Source` ze stroną, na której ją znaleziono. Gdy wartości jednej części Faktury leżą na różnych stronach, każda dostaje własne źródło albo wyszukiwanie zawężone do jednej strony; jedno `Source` dla wartości z kilku stron to błąd. Wartość wyliczona (np. Opust) nie ma `Source`, tylko opis sposobu wyliczenia.

## Nazwy z GLOSSARY.md

Identyfikator to angielskie tłumaczenie terminu z `GLOSSARY.md`, nie słowa z jego listy `_Avoid_` (Prognoza → `Forecast`, nie `Installment` od „raty”). Tekst na ekranie używa terminu; słowa z `_Avoid_` zależne od kontekstu (np. „do zapłaty” w miejscu Kosztu okresu, „zużycie” w miejscu Energii pobranej) ocenia recenzent.

## Fixture'y i przykłady

Liczby w fixture'ach, testach, dokumentacji i docstringach są wymyślone, także ceny i opłaty stałe, choć są publicznymi stawkami: wiersz przepisany z Faktury zdradza, ile ktoś zapłacił. Po zmianie liczby w fixture'ze sumy (Wynik rozliczenia, Do zapłaty, bilans Magazynu energii) muszą dalej się domykać; pilnuje tego kontrola sum przy imporcie fixture'a.

## Parsery

Wariant wiersza wybiera nagłówek lub znacznik w dokumencie (np. kolumna `Mnożna`, `Pobór Oddanie`), nie zgadywanie z odstępów między liczbami: odstęp tysięcy (`1 370,0000`) wygląda tak samo jak dwie kolumny (`1` i `370,0000`). Nowy wariant układu dostaje fixture z wymyślonymi liczbami i wpis w `docs/invoice-structure.md`.
