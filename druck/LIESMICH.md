# Druckfassung

Das ganze Buch als druckfertiges PDF. Erzeugen mit:

```bash
python3 -P tools/druck.py --umschlag
```

Das dauert drei bis vier Minuten. Es entstehen diese Dateien in diesem Ordner (nicht im Repository):

| Datei | Inhalt |
|---|---|
| `Die-Geschichte-der-Schweiz.pdf` | Buchblock: Titelei, Inhaltsverzeichnis mit Seitenzahlen, Vorwort, alle 65 Kapitel, Zeitleiste, «Über dieses Buch», Bildnachweis |
| `Umschlag-Hardcover.pdf` | Ganzer Hardcover-Bezug in einem Stück: Rückseite, Rücken mit Titel, Vorderseite, rundum Einschlag (498 × 333 mm) |
| `Umschlag-Vorderseite.pdf` | Vorderseite allein im Seitenformat (für Softcover, Vorschau oder Druckereien, die die Teile einzeln wollen) |
| `Umschlag-Rueckseite.pdf` | Rückseite allein: ohne Text, im Papierton der Vorderseite |
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
- **Umfang:** 508 Seiten (genaue Zahl mit `pdfinfo`). Das Skript füllt am Schluss mit leeren Seiten auf, bis die
  Seitenzahl durch vier teilbar ist.
- **Farbe:** RGB, alle Seiten farbig (cremefarbener Papierton als Fläche). Die Druckerei wandelt in ihr CMYK-Profil um;
  wer einen Proof will, sollte ihn bestellen, weil sich der Papierton je nach Papier und Profil etwas verschiebt.
  Alternativ auf Naturpapier mit leichtem Gelbton drucken – dann wirkt der Ton noch wärmer.
- **Schriften:** vollständig eingebettet (EB Garamond, IM Fell English, Cinzel Decorative; alle unter der SIL Open
  Font License).
- **Bildauflösung:** alle Abbildungen mindestens 150 ppi in Druckgrösse, der grösste Teil 200–300 ppi und mehr.
  Die blassen Aquarelle im Hintergrund sind weich hochgerechnet (rund 170 ppi über eine Doppelseite).
- **Umschlag:** `Umschlag-Hardcover.pdf`. Die Masse stehen oben in `tools/druck.py` (`RUECKEN`, `DECKEL_B`, `GELENK`,
  `EINSCHLAG`); bei anderem Papier oder anderer Seitenzahl ändert sich die Rückenstärke – dann dort anpassen und neu
  erzeugen.
- **Dateigrösse:** rund 250 MB.

## Bestellen bei drucks.ch

Empfohlen: **Hardcover mit Fadenheftung** (drucks.ch → Bücher → Hardcover-Bücher → Fadenheftung). Fadenheftung hält
ein dickes Buch, das man oft aufschlägt, viel länger als Klebebindung, und es bleibt besser offen liegen.

| Einstellung | Wert |
|---|---|
| Format | DIN A4 hoch (210 × 297 mm) |
| Buchrücken | gerader Rücken – der Konfigurator nennt dann 26,24 mm Rückenstärke |
| Cellophanierung | glänzend oder matt (matt wirkt zum Papierton ruhiger) |
| Seitenanzahl Kern | 508 |
| Farbigkeit Kern | 4/4-farbig beidseitig CMYK |
| Material Kern | 100 g Kunstdruckpapier matt (die Rückenstärke im Umschlag ist dafür berechnet) |
| Lesebändchen, Kapitalband | nach Wunsch |
| Anzahl | ab 10 Stück |
| Datencheck | Premium Profidatencheck (manuelle Prüfung, ggf. Anpassungen, Korrekturabzug) |

Preis im November 2026 laut Konfigurator: 10 Stück rund CHF 400 inkl. MwSt. (Produktion «Relax», Versand gratis),
also rund CHF 40 pro Buch; ab 50 Stück knapp CHF 39.

Hochladen: `Die-Geschichte-der-Schweiz.pdf` (Inhalt) und `Umschlag-Hardcover.pdf` (Umschlag), am besten zusammen in
einer Zip-Datei, wie drucks.ch es für mehrere Dateien empfiehlt.

**Welche Seite ist Seite 1?** Seite 1 des Inhalts-PDFs ist die erste rechte Seite des Buchblocks – die Seite, die man
rechts sieht, wenn man den Deckel und das Vorsatzblatt umgeschlagen hat. Bei einem Hardcover ist die Innenseite des
Deckels mit dem unbedruckten Vorsatzpapier überklebt; sie gehört weder zum Inhalts- noch zum Umschlag-PDF. Ungerade
Seiten stehen rechts, gerade links. Hier ist Seite 1 der Schmutztitel, Seite 2 leer, Seite 3 die Titelseite, Seite 4
das Impressum; Seite 508 ist die letzte linke Seite.

**Noch zu prüfen:** Einschlag (15 mm) und Gelenk (8 mm) des Bezugs sind gängige Werte; die Vorgaben von drucks.ch
stehen in deren «Infoblätter» (Zip-Datei auf der Produktseite). Der Bezug ist so gestaltet, dass ein paar Millimeter
Abweichung nichts ausmachen: Hintergrund durchgehend, Text und Rahmen weit vom Rand. Mit dem Premium-Datencheck passt
drucks.ch die Datei bei Bedarf an und schickt vor dem Druck einen Korrekturabzug.

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
