# Druckfassung

Das ganze Buch als druckfertiges PDF. Erzeugen mit:

```bash
python3 -P tools/druck.py --umschlag
```

Das dauert etwa vier Minuten. Es entstehen zwei Dateien in diesem Ordner (nicht im Repository, weil sie zu gross sind):

| Datei | Inhalt |
|---|---|
| `Die-Geschichte-der-Schweiz.pdf` | Buchblock: Titelei, Inhaltsverzeichnis mit Seitenzahlen, Vorwort, alle 63 Kapitel, Zeitleiste, «Über dieses Buch», Bildnachweis |
| `Umschlag-Vorderseite.pdf` | Vorderseite des Umschlags im selben Format |

Benötigt werden Google Chrome, poppler-utils (`pdftotext`, `pdfinfo`) sowie die Python-Pakete `websockets`, `numpy` und `Pillow`.

## Angaben für die Druckerei

- **Endformat:** A4 hoch, 210 × 297 mm
- **Beschnitt:** 3 mm rundum, die PDF-Seiten messen also 216 × 303 mm; Papierton und Hintergründe laufen bis in den Beschnitt. Schnittmarken sind keine gesetzt (die meisten Druckereien wünschen das so).
- **Satzspiegel:** innen (Bund) 22 mm, aussen 16 mm, oben 18 mm, unten 22 mm ab Endformat; linke und rechte Seiten gespiegelt. Für Klebebindung reicht der Bundsteg; bei sehr dicker Bindung die Druckerei fragen.
- **Umfang:** etwa 590 Seiten (genaue Zahl mit `pdfinfo`). Bei ungerader Seitenzahl fügt die Druckerei am Schluss eine leere Seite an.
- **Farbe:** RGB, alle Seiten farbig (cremefarbener Papierton als Fläche). Die Druckerei wandelt in ihr CMYK-Profil um; wer einen Proof will, sollte ihn bestellen, weil sich der Papierton je nach Papier und Profil etwas verschiebt. Alternativ auf Naturpapier mit leichtem Gelbton drucken – dann wirkt der Ton noch wärmer.
- **Schriften:** vollständig eingebettet (EB Garamond, IM Fell English, Cinzel Decorative; alle unter der SIL Open Font License).
- **Bildauflösung:** alle Abbildungen mindestens 150 ppi in Druckgrösse, der grösste Teil 200–300 ppi und mehr. Die blassen Aquarell-Hintergründe haben teils weniger; sie sind weich gemalt und nur zu etwa 40 % sichtbar.
- **Umschlag:** Es liegt nur die Vorderseite bei. Rücken und Rückseite hängen von Papier, Bindung und Seitenzahl ab – die Rückenbreite nennt die Druckerei; dann lässt sich der ganze Umschlag passend erzeugen.
- **Dateigrösse:** rund 240 MB.

## Wie der Druck-Build funktioniert

`tools/druck.py` setzt alle Kapitel wie die Website in ein einziges HTML-Dokument (`docs/druck/buch.html`) und lässt Chrome (headless) es mit `druck/druck.css` als PDF drucken. Ein zweiter Durchgang liest die Seitenzahlen aus dem ersten PDF und trägt sie ins Inhaltsverzeichnis ein.

Für den Druck gelten einige Abweichungen von der Website:

- Breite Bilder (ausser Panoramen) stehen in einer Spalte, sonst blieben halbleere Seiten, wenn ein grosses Bild nicht mehr auf die Seite passt.
- Karten sind höchstens 95 mm hoch.
- Die Aquarelle werden vorab aufgehellt (`docs/druck/aq/`), und der Pinselrand ist eine PNG-Maske. Chrome würde CSS-Filter und die SVG-Maske der Website sonst als riesige Pixelbilder ablegen.
