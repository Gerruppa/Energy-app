# Parser dwuetapowy, testy na zanonimizowanych wierszach

Repozytorium jest publiczne, więc prawdziwe PDF-y faktur nie mogą być fixture'ami. Parser dzielimy na cienki adapter PDF → surowe wiersze i tabele (pdfplumber) oraz głęboki moduł surowe wiersze → Faktura. Głęboki moduł testujemy na zanonimizowanych zrzutach wierszy (JSON w `tests/fixtures/`, zmienione numery i kwoty); adapter sprawdza lokalny test na PDF-ach z `References/`, pomijany, gdy folderu nie ma.

## Considered Options

- **Syntetyczne PDF-y odtwarzające układ Taurona**: testują całą ścieżkę, ale wierne odtworzenie dwóch układów to więcej pracy niż sam parser, a różnice w generowaniu PDF-a dawałyby fałszywe wyniki.
- **Testy tylko lokalne na prawdziwych PDF-ach**: najprostsze, ale nic nie chroni parsera poza komputerem użytkownika.
