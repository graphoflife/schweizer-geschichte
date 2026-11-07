# Die Geschichte der Schweiz

Ein illustriertes Geschichtsbuch über zweitausend Jahre Schweizer Geschichte – von den Helvetiern bis heute.
Seite für Seite, mit historischen Gemälden, Chronik-Illustrationen, eigenen Karten und Quellenangaben.

**Lesen:** https://graphoflife.github.io/schweizer-geschichte/

## Aufbau

| Ordner | Inhalt |
|---|---|
| `src/kapitel/` | Kapiteltexte als HTML-Fragmente mit Meta-Block |
| `src/bilder/` | Bildlisten pro Kapitel (Dateinamen auf Wikimedia Commons) und der automatisch erzeugte Bildnachweis |
| `src/karten/geo.json` | vereinfachte Geodaten für die Karten |
| `src/seiten/` | Vorwort und «Über dieses Buch» |
| `tools/` | Build-Skript, Bild-Download, Commons-Suche, Kontaktbogen, Geodaten-Aufbereitung |
| `docs/` | fertige Website (wird von GitHub Pages ausgeliefert) |

Wie Kapitel geschrieben werden, steht in [`src/ANLEITUNG.md`](src/ANLEITUNG.md).

## Bauen

Benötigt Python 3 mit Pillow.

```bash
python3 -I tools/bilder.py      # fehlende Bilder von Wikimedia Commons laden
python3 -I tools/build.py       # Website nach docs/ bauen
python3 -m http.server -d docs  # lokal ansehen
```

## Quellen und Lizenzen

- Texte: [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/deed.de)
- Bilder: gemeinfrei oder frei lizenziert, einzeln nachgewiesen im Bildnachweis des Buchs
- Karten: eigene Darstellung; Geodaten BFS/swisstopo via [swiss-maps](https://github.com/interactivethings/swiss-maps) und [Natural Earth](https://www.naturalearthdata.com/) (gemeinfrei)
- Code (`tools/`, `docs/assets/`): MIT

Fehler gefunden? Bitte ein [Issue](https://github.com/graphoflife/schweizer-geschichte/issues) eröffnen.
