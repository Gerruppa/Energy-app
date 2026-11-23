# Python + Streamlit + SQLite, aplikacja lokalna

Aplikacja ma jednego użytkownika, dane wchodzą raz na kilka tygodni, a najtrudniejszą częścią jest parsowanie tabel z PDF-ów. Python ma do tego najlepsze biblioteki (pdfplumber, pandas), Streamlit daje dashboard z uploadem plików bez osobnego frontendu, a SQLite trzyma dane w jednym pliku bez serwera. Środowisko i wersję Pythona zarządza `uv`.

## Considered Options

- **TypeScript (Next.js / Vite)**: pełna kontrola nad UI, ale osobny backend i słabsze biblioteki do tabel w PDF-ach.
- **Home Assistant + integracja Tauron AMIplus**: dane na żywo w kWh, bez kosztów z faktur i bez ładowań; wymaga utrzymywania HA.
- **Arkusz kalkulacyjny**: najszybszy start, ale każda faktura wymaga ręcznego przepisywania.
