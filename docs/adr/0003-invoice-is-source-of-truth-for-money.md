# Faktura jest źródłem prawdy dla kwot, eLicznik dla profilu godzinowego

Faktury i eLicznik mogą podawać różne ilości kWh (odczyty szacunkowe, korekty, inne granice okresów). Kwoty, ceny i Opusty bierzemy wyłącznie z Faktur, bo to one są rozliczeniem; eksport eLicznika służy do Profilu godzinowego, Linii bazowej i rozkładu zużycia w czasie. Gdy sumy kWh z obu źródeł dla tego samego okresu się różnią, aplikacja pokazuje różnicę zamiast ją wyrównywać.
