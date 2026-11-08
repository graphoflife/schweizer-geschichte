# Die Geschichte der Schweiz

Ein illustriertes Geschichtsbuch über zweitausend Jahre Schweizer Geschichte – von den Helvetiern bis heute.
Seite für Seite, mit historischen Gemälden, Chronik-Illustrationen, eigenen Karten und Quellenangaben –
gestaltet wie ein Märchenbuch, mit Aquarell-Landschaften hinter den Texten.

38 Hauptkapitel erzählen die Geschichte der Reihe nach. Dazwischen stehen 25 Zwischenkapitel: Überblicke über
Machtstrukturen (Reich, Kirche, Bündnisse, Grossmächte), «Vor der Schweiz» (was die heutigen Kantone vor ihrem
Beitritt waren), Nebengeschichten (z. B. Thomas Platter, Einstein, der Bergsturz von Goldau) und Legenden.
Jedes Kapitel wurde unabhängig faktengeprüft; die Protokolle stehen in [`src/faktencheck/`](src/faktencheck).

**Lesen:** https://graphoflife.github.io/schweizer-geschichte/

## Aufbau

| Ordner | Inhalt |
|---|---|
| `src/kapitel/` | Kapiteltexte als HTML-Fragmente mit Meta-Block |
| `src/bilder/` | Bildlisten pro Kapitel (Dateinamen auf Wikimedia Commons), die Hintergrund-Aquarelle (`aquarelle.json`) und der automatisch erzeugte Bildnachweis |
| `src/aquarelle.json` | welche Aquarell-Landschaften hinter welchem Kapitel liegen |
| `src/faktencheck/` | Faktencheck-Protokolle pro Kapitel |
| `src/karten/geo.json` | vereinfachte Geodaten für die Karten |
| `src/seiten/` | Vorwort und «Über dieses Buch» |
| `tools/` | Build-Skript, Druck-Build (PDF), Bild-Download, Commons-Suche, Kontaktbogen, Geodaten-Aufbereitung |
| `druck/` | Seitensatz (`satz.js`), Gestaltung und Hinweise für die Druckfassung |
| `docs/` | fertige Website (wird von GitHub Pages ausgeliefert) |

Wie Kapitel geschrieben werden, steht in [`src/ANLEITUNG.md`](src/ANLEITUNG.md).

## Bauen

Benötigt Python 3 mit Pillow.

```bash
python3 -I tools/bilder.py      # fehlende Bilder von Wikimedia Commons laden
python3 -I tools/build.py       # Website nach docs/ bauen
python3 -m http.server -d docs  # lokal ansehen
```

## Druckfassung

`python3 -P tools/druck.py --umschlag` erzeugt das ganze Buch als druckfertiges PDF (A4 mit 3 mm Beschnitt)
und die Umschlag-Vorderseite. Jede Seite ist zweispaltig auf einem festen Zeilenraster gesetzt, mit einem Aquarell pro
Doppelseite und einem Zahlenstrahl am rechten Rand. Wie das funktioniert und die Angaben für die Druckerei:
[`druck/LIESMICH.md`](druck/LIESMICH.md).

## Quellen und Lizenzen

- Texte: [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/deed.de)
- Bilder: gemeinfrei oder frei lizenziert, einzeln nachgewiesen im Bildnachweis des Buchs
- Karten: eigene Darstellung; Geodaten BFS/swisstopo via [swiss-maps](https://github.com/interactivethings/swiss-maps) und [Natural Earth](https://www.naturalearthdata.com/) (gemeinfrei)
- Code (`tools/`, `docs/assets/`): MIT

Fehler gefunden? Bitte ein [Issue](https://github.com/graphoflife/schweizer-geschichte/issues) eröffnen.
