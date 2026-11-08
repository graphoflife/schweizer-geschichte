# Druckfassung

Das ganze Buch als druckfertiges PDF. Erzeugen mit:

```bash
python3 -P tools/druck.py --umschlag
```

Das dauert drei bis vier Minuten. Es entstehen zwei Dateien in diesem Ordner (nicht im Repository, weil sie zu gross sind):

| Datei | Inhalt |
|---|---|
| `Die-Geschichte-der-Schweiz.pdf` | Buchblock: Titelei, Inhaltsverzeichnis mit Seitenzahlen, Vorwort, alle 63 Kapitel, Zeitleiste, «Über dieses Buch», Bildnachweis |
| `Umschlag-Vorderseite.pdf` | Vorderseite des Umschlags im selben Format |
| `satzbericht.json` | Protokoll des Seitenumbruchs: Seitenzahl jedes Kapitels, Warnungen, Spalten mit Leerraum |

Benötigt werden Google Chrome (mit einem Benutzerprofil, das die deutschen Trennmuster schon geladen hat – sonst
fehlt die Silbentrennung, das Skript warnt dann), poppler-utils (`pdfinfo`) sowie die Python-Pakete `websockets`,
`numpy` und `Pillow`.

## Angaben für die Druckerei

- **Endformat:** A4 hoch, 210 × 297 mm
- **Beschnitt:** 3 mm rundum, die PDF-Seiten messen also 216 × 303 mm; Papierton, Aquarelle und die Marken des
  Zahlenstrahls laufen bis in den Beschnitt. Schnittmarken sind keine gesetzt (die meisten Druckereien wünschen das so).
- **Satzspiegel:** 170 × 253 mm, innen und aussen 20 mm, oben 19 mm, unten 25 mm ab Endformat. Im Aussenrand der
  rechten Seiten steht der Zahlenstrahl (ab 8 mm vor der Schnittkante); seine Marke ragt als Registerstreifen bis in
  den Beschnitt.
- **Umfang:** 487 Seiten (genaue Zahl mit `pdfinfo`). Bei ungerader Seitenzahl fügt die Druckerei am Schluss eine
  leere Seite an.
- **Farbe:** RGB, alle Seiten farbig (cremefarbener Papierton als Fläche). Die Druckerei wandelt in ihr CMYK-Profil um;
  wer einen Proof will, sollte ihn bestellen, weil sich der Papierton je nach Papier und Profil etwas verschiebt.
  Alternativ auf Naturpapier mit leichtem Gelbton drucken – dann wirkt der Ton noch wärmer.
- **Schriften:** vollständig eingebettet (EB Garamond, IM Fell English, Cinzel Decorative; alle unter der SIL Open
  Font License).
- **Bildauflösung:** alle Abbildungen mindestens 150 ppi in Druckgrösse, der grösste Teil 200–300 ppi und mehr.
  Die blassen Aquarelle im Hintergrund sind weich hochgerechnet (rund 170 ppi über eine Doppelseite).
- **Umschlag:** Es liegt nur die Vorderseite bei. Rücken und Rückseite hängen von Papier, Bindung und Seitenzahl ab.
- **Dateigrösse:** rund 240 MB.

## Wie die Seiten gesetzt werden

`tools/druck.py` legt alle Inhalte, wie die Website sie baut, in ein einziges HTML-Dokument (`docs/druck/buch.html`).
Den Seitenumbruch macht nicht Chrome, sondern `satz.js`: Es setzt jede Seite selbst und lässt Chrome die fertigen
Seiten nur noch als PDF drucken. Die Gestaltung steht in `druck.css`.

- **Raster:** Jede Seite hat zwei Spalten (der Bildnachweis drei). Alle Textzeilen stehen auf einem festen
  Zeilenraster, links und rechts auf gleicher Höhe; Bilder, Kästen und Überschriften belegen ganze Rasterzeilen.
- **Umbruch:** Absätze werden zeilengenau geteilt, mit mindestens zwei Zeilen am Spaltenende und -anfang.
  Überschriften stehen nie allein am Spaltenfuss.
- **Bilder und Kästen** sind Gleitobjekte: Passt eines nicht mehr in die Spalte, steht es oben in der nächsten, und
  der Text läuft weiter. Ein Bild darf dafür bis auf 62 % verkleinert werden. Kästen, die höher als eine Spalte
  sind, gehen in der nächsten Spalte weiter («Fortsetzung»). Bleibt am Spaltenfuss Platz, verteilt er sich auf die
  Abstände um Bilder und Überschriften.
- **Breite Bilder und Karten** stehen oben über beiden Spalten, wenn möglich auf der Seite, auf der sie erwähnt werden.
- **Kapitel** beginnen immer oben auf einer neuen Seite mit einem Kopf über die ganze Breite. Am Ende folgen
  Zeittafel (als eigener Kasten) und Quellen; die letzte Seite wird in der Höhe ausgeglichen. Blieben dort nur ein
  paar Zeilen, wird die vorletzte Seite etwas enger gesetzt.
- **Aquarell:** eines pro Doppelseite, über den Bund hinweg (gehören die beiden Seiten zu verschiedenen Kapiteln,
  eines pro Seite). Die Bilder werden vorab aufgehellt und weich hochgerechnet (`docs/druck/aq/`), der Pinselrand
  ist eine PNG-Maske – Chrome würde CSS-Filter und die SVG-Maske der Website sonst als riesige Pixelbilder ablegen.
- **Zahlenstrahl:** am Aussenrand jeder rechten Seite, immer gleich: neun gleich lange Abschnitte, einer pro Teil
  des Buches (58 v. Chr., 1032, 1393, 1519, 1648, 1798, 1848, 1914, 1945, heute), jeder in der Farbe des Teils.
  Die Marke zeigt die Jahre des Kapitels, in der Zeitleiste die Jahre der Einträge auf der Seite.
- **Nebengeschichten und Legenden** stehen auf leicht getöntem Papier; ihr Band über dem Titel und der
  Kolumnentitel nennen die Art.
- **Verweise:** Inhaltsverzeichnis, Zeitleiste und Bildnachweis bekommen ihre Seitenzahlen direkt aus dem Umbruch.
