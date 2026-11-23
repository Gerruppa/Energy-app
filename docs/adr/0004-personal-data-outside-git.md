# Dane osobowe poza repozytorium

Faktury zawierają adres, numery PPE i numer klienta, a repozytorium jest publiczne na GitHubie. Dokumentacja opisuje strukturę faktur i wnioski ogólnie, bez kwot, stanów Magazynu energii i numerów z prawdziwych faktur. `References/` (prawdziwe faktury) i `data/` (baza i archiwum plików) są w `.gitignore`; testy korzystają z syntetycznych lub zanonimizowanych fixture'ów w `tests/fixtures/`. Kosztem jest to, że bazy i faktur nie odtworzy się z gita: kopię zapasową `data/` użytkownik robi sam.
