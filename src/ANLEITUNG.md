# Anleitung für Autorinnen und Autoren

Dieses Buch wird aus HTML-Fragmenten gebaut. Jedes Kapitel ist **eine Datei**
`src/kapitel/NN-slug.html` mit einer **Bildliste** `src/bilder/NN.json`.
Das Musterkapitel ist `src/kapitel/06-bundesbrief.html` – zuerst lesen, dann nachahmen.

## Arbeitsablauf

1. Recherche (siehe «Fakten») – Notizen mit Belegen sammeln.
2. Bilder suchen:
   ```bash
   python3 -I tools/commons.py suche "Schlacht bei Sempach"
   python3 -I tools/commons.py kategorie "Diebold Schilling chronicles"
   python3 -I tools/commons.py info "Datei.jpg"
   ```
   Zeilen mit ✗ haben keine freie Lizenz und werden nicht geladen.
3. Bildliste `src/bilder/NN.json` schreiben, laden, Kontaktbogen ansehen:
   ```bash
   python3 -I tools/bilder.py src/bilder/NN.json
   python3 -I tools/kontakt.py src/bilder/NN.json /tmp/…/bogen-NN.jpg   # dann mit Read ansehen
   ```
   Jedes Bild muss angesehen werden: Die Legende muss zeigen, was wirklich zu sehen ist.
   Farbkarten/Massstäbe von Scans wegschneiden (`"zuschnitt": [links, oben, rechts, unten]` in %).
4. Kapitel schreiben, dann bauen: `python3 -I tools/build.py` – Fehlermeldungen zum eigenen Kapitel beheben
   (Meldungen zu anderen Kapiteln ignorieren, dort arbeiten andere).

## Bildliste

```json
[
 {"id": "k07-morgarten-schilling", "datei": "Exakter Dateiname auf Commons.jpg", "kuenstler": "Diebold Schilling d. Ä., Spiezer Chronik (1485)"},
 {"id": "k07-karte", "datei": "…png", "zuschnitt": [0, 0, 100, 92]}
]
```
- `id` beginnt immer mit `kNN-` (Kapitelnummer), nur Kleinbuchstaben, Ziffern, Bindestriche.
- `kuenstler` (optional) überschreibt die oft unordentliche Commons-Angabe – sauber: «Name (Lebensdaten)» bzw. «Chronik, Jahr».
- Nur Bilder verwenden, die im Text auch vorkommen.

## Meta-Block (Anfang jeder Kapiteldatei)

```html
<!--meta
{
  "nr": 7, "slug": "morgarten", "teil": 2,
  "titel": "Morgarten und die acht alten Orte",
  "jahre": "1315 – 1353",
  "untertitel": "Ein Satz, der neugierig macht.",
  "held": "k07-…",               // Titelbild (Querformat ideal)
  "held_pos": "50% 30%",          // welcher Bildteil sichtbar bleibt (object-position)
  "held_titel": "Kurztitel des Titelbilds",
  "held_legende": "<b>Titel</b> – Legende mit Künstler und Jahr.",
  "kurz": "Ein Satz für das Inhaltsverzeichnis.",
  "ereignisse": [["1315", "Kurzer Satz für die grosse Zeitleiste."], …]   // 4–7 Einträge
}
-->
```
(JSON ohne Kommentare schreiben!)

## Bausteine

**Einleitung:** `<p class="lead">…</p>` – 3–5 Sätze, erzählerisch.

**Abschnitte:** `<section><h2>Überschrift</h2> … </section>` – erscheinen zweispaltig wie im Buch.

**Bild:**
```html
<bild id="k07-…" titel="Kurztitel" lage="spalte">Legende: was man sieht, wer es wann gemalt hat, warum es wichtig ist.</bild>
```
`lage`: `spalte` (Spaltenbreite, Standard), `breit` (über beide Spalten), `voll` (randabfallend, für Panoramen).

**Erklär-Punkte** (wie in Sachbüchern; Koordinaten in % von Bildbreite/-höhe, Bild vorher ansehen!):
```html
<bild id="…" lage="breit" titel="…">Legende
<punkt x="35" y="40">Die Halbarte – Hieb-, Stich- und Reisswaffe der Eidgenossen.</punkt>
</bild>
```

**Karte** (eigene Darstellung, Koordinaten in Dezimalgrad, aus Wikipedia/Geonames prüfen):
```html
<karte typ="schweiz" titel="…" kantone="UR SZ" kantone2="LU" legende="Waldstätte|Luzern" lage="spalte">
<ort name="Morgarten" lon="8.633" lat="47.104" typ="schlacht" jahr="1315" pos="e"/>
<route punkte="8.31,47.05 8.40,47.00" art="pfeil" name="Vormarsch"/>
Legende der Karte.
</karte>
```
- `typ="schweiz"`: Kantone, Seen, Flüsse. `ausschnitt="lon0,lat0,lon1,lat1"` zoomt hinein.
- `typ="region"`: Schweiz mit Nachbarländern (Standard 3.4,44.6 – 12.4,49.3; Daten reichen 2.5–13.5 / 43.8–50.2).
- `typ="beitritt"`: Kantone nach Beitrittsjahr eingefärbt; `bis="1513"` zeigt nur bis zu diesem Jahr.
- Kürzel: ZH BE LU UR SZ OW NW GL ZG FR SO BS BL SH AR AI SG GR AG TG TI VD VS NE GE JU. `kuerzel="ja"` beschriftet alle Kantone.
- Ortstypen: `stadt schlacht kloster pass roemisch burg ort`. `pos`: `e w n s ne nw se sw` (Lage der Beschriftung).
- `route art="pfeil"` (mit Pfeilspitze) oder `art="linie"`.
- Bei historischen Gebieten deutlich sagen, dass heutige Kantonsgrenzen nur der Orientierung dienen.

**Kästen** (`<aside class="kasten kasten--TYP"><h3>Titel</h3>…</aside>`, Kicker wird automatisch gesetzt):

| Typ | Kicker | Zweck |
|---|---|---|
| `fakten` | Auf einen Blick | `<dl><dt>…</dt><dd>…</dd></dl>` mit Eckdaten |
| `detail` | Im Detail | ein Aspekt genauer (Waffen, Recht, Technik …) |
| `vergessen` | Vergessene Geschichte | **Pflicht**: längst vergessene Ereignisse, Menschen, Orte |
| `mythos` | Mythos und Wirklichkeit | Legende vs. Quellenlage |
| `quelle` | Aus den Quellen | echtes Zitat aus einer zeitgenössischen Quelle (`<blockquote>`) mit Herkunft |
| `person` | Porträt | Kurzbiografie, gerne mit `<bild>` darin |
| `alltag` | So lebten die Menschen | Alltag, Ernährung, Arbeit, Kinder |
| `wissen` | Wusstest du? | überraschende, belegte Kleinigkeit |
| `erbe` | Was davon bleibt | **Pflicht**: was dieses Kapitel mit der heutigen Schweiz zu tun hat |

`kasten--breit` dazu, wenn ein Kasten über beide Spalten laufen soll.

**Zitat im Fliesstext:** `<blockquote class="zitat"><p>«…»</p><cite>Quelle, Jahr</cite></blockquote>`

**Kapitel-Zeitleiste** (nach dem letzten Abschnitt):
```html
<ol class="zeitleiste"><li><b>1315</b> Text</li> …</ol>
```

**Quellen** (ganz am Schluss): `<section class="quellen"><h2>Quellen und weiterführende Literatur</h2><ol><li>…</li></ol></section>`

## Fakten – die wichtigste Regel

- **Nichts erfinden.** Jede Jahreszahl, Zahl, jeder Name muss belegt sein. Im Zweifel weglassen oder als
  unsicher kennzeichnen («nach zeitgenössischen Chroniken», «wohl», «um»).
- Hauptquelle ist das **Historische Lexikon der Schweiz (HLS)**. Die Website blockiert automatische Abrufe –
  HLS-Artikel-URLs findet man über die Websuche (z. B. «hls-dhs-dss.ch Morgarten») oder in den Belegen
  der deutschsprachigen Wikipedia. Nur URLs angeben, die tatsächlich gefunden wurden.
  Bot-Sperren nie umgehen (keine gefälschten User-Agents o. Ä.).
- Wikipedia (de/fr/en) ist erlaubt, wenn die Angabe dort belegt ist; wichtige Zahlen möglichst doppelt prüfen.
- Schlachtenzahlen (Heeresgrössen, Tote) sind oft unsicher: Grössenordnungen nennen und Unsicherheit sagen.
- Legenden klar als Legenden kennzeichnen (Kasten `mythos`).
- Zitate nur, wenn sie echt sind; Übersetzungen als «eigene Übersetzung» oder «sinngemäss» kennzeichnen.
  Keine Passagen aus urheberrechtlich geschützten modernen Texten abschreiben.
- Auch dunkle Seiten erzählen (Untertanen, Verfolgungen, Gewalt, Ausgrenzung) – sachlich, ohne Moralpredigt.

## Sprache und Stil

- Schweizer Hochdeutsch: **kein ß** (immer «ss»), Anführungszeichen «…» und ‹…›.
- Zielgruppe: neugierige Erwachsene und Jugendliche ab etwa 14. Anschaulich, konkret, erzählend wie ein
  gutes Sachbuch (DK-Stil): Szenen, Details, Zahlen, Ursachen und Folgen. Fachbegriffe beim ersten Vorkommen erklären.
- Immer erklären, **warum** etwas geschah und **was es bewirkt** hat – der rote Faden ist: Wie wurde die Schweiz zu dem, was sie heute ist?
- Umfang pro Kapitel: etwa 2000–2800 Wörter, 6–10 Bilder, 1–2 Karten, Kästen gemischt.
- Bilder bevorzugt: Bilderchroniken (Tschachtlan, Schilling, Schodoler, Edlibach, Stumpf), Gemälde und Stiche
  (Jauslin, Hodler, Anker, Vogel, Stückelberg, Merian …), historische Fotografien (ETH-Bibliothek, Bundesarchiv),
  Karten (z. B. die historischen Karten von Marco Zanoli, CC BY-SA). Querformat für das Titelbild.
