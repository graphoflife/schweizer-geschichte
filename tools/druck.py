#!/usr/bin/env python3
"""Druckfassung: das ganze Buch als PDF für die Druckerei.

  python3 -P tools/druck.py              Buchblock  → druck/Die-Geschichte-der-Schweiz.pdf
  python3 -P tools/druck.py --umschlag   zusätzlich Hardcover-Bezug, Vorder- und Rückseite → druck/Umschlag-*.pdf
  python3 -P tools/druck.py --kapitel=16,22a   Probedruck nur mit diesen Kapiteln

Format A4 (210 × 297 mm) mit 3 mm Beschnitt rundum, also 216 × 303 mm pro Seite. Zuerst entsteht
docs/druck/buch.html: alle Inhalte (wie auf der Website gebaut) in einem unsichtbaren Vorrat. Darin setzt
druck/satz.js in Chrome (headless, über das DevTools-Protokoll) jede Seite selbst – zwei Spalten auf einem
festen Zeilenraster, Bilder und Kästen als Gleitobjekte, Aquarell und Zahlenstrahl pro Doppelseite –, und
Chrome druckt die fertigen Seiten als PDF. Die Gestaltung steht in druck/druck.css.

Benötigt Google Chrome, poppler-utils (pdfinfo) und das Python-Paket websockets
(daher -P statt -I: das Paket liegt meist in den Benutzer-Paketen, die -I ausblendet).
"""
import asyncio
import base64
import datetime
import itertools
import json
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build  # noqa: E402
from build import (ARTEN, BUCH, DOCS, ROOT, SRC, TEILE, UNTERTITEL, esc, expandiere,  # noqa: E402
                   kuenstler, nachweis_zeile)

import numpy as np  # noqa: E402
from PIL import Image, ImageEnhance, ImageFilter  # noqa: E402
from websockets.asyncio.client import connect  # noqa: E402

HTML = DOCS / "druck" / "buch.html"           # Zwischenstufe (nicht im Repository)
UMSCHLAG_HTML = DOCS / "druck" / "umschlag.html"
AUSGABE = ROOT / "druck"
PDF = AUSGABE / "Die-Geschichte-der-Schweiz.pdf"
UMSCHLAG_PDF = AUSGABE / "Umschlag-Vorderseite.pdf"
RUECKSEITE_PDF = AUSGABE / "Umschlag-Rueckseite.pdf"
BEZUG_PDF = AUSGABE / "Umschlag-Hardcover.pdf"
BEZUG_HTML = DOCS / "druck" / "bezug.html"
RUECKSEITE_HTML = DOCS / "druck" / "rueckseite.html"
# Hardcover-Bezug (Masse in mm): Rückenstärke laut Konfigurator von drucks.ch für die gewählte Bestellung (508 Seiten,
# A4). Deckel = Buchblock 210 x 297 plus Kantenüberstand; Gelenk und Einschlag sind übliche Werte –
# vor dem Bestellen mit der Vorlage der Druckerei vergleichen (siehe druck/LIESMICH.md).
RUECKEN = 31.8
DECKEL_B, DECKEL_H = 213, 303
GELENK = 8
EINSCHLAG = 15
SCHRIFTEN = build.SCHRIFTEN
AQ_DRUCK = DOCS / "druck" / "aq"
PINSEL = DOCS / "druck" / "pinsel.png"
HEUTE = datetime.date.today().year
# Zahlenstrahl am Seitenrand: neun gleich lange Abschnitte, einer pro Teil des Buches (Anfangsjahre)
GRENZEN = [-58, 1032, 1393, 1519, 1648, 1798, 1848, 1914, 1945]
# Chrome trennt nur mit seinen Trennmustern, die es sich ins Benutzerprofil lädt; das frische Druckprofil hat
# keine. Deshalb werden sie aus einem vorhandenen Chrome-Profil übernommen.
TRENNMUSTER = [Path.home() / ".config" / p / "hyphen-data" for p in ("google-chrome", "chromium")]


# ------------------------------------------------------------ Aquarelle ---
# Auf der Website hellt ein CSS-Filter die Aquarelle auf, und eine SVG-Maske mit Turbulenz-Filter franst
# die Ränder aus. Chrome würde beides im PDF als riesige Pixelbilder ablegen (hundertfache Dateigrösse).
# Für den Druck wird die Farbanpassung deshalb vorab in die Bilder gerechnet und die Maske als PNG erzeugt.

AQ_BREITE = 2600   # Ein Aquarell läuft über eine ganze Doppelseite (392 mm): weich hochgerechnet, damit im Druck
                   # keine Pixel und JPEG-Kästchen der Web-Bilder sichtbar werden


def bereite_aquarelle():
    AQ_DRUCK.mkdir(parents=True, exist_ok=True)
    for bid in sorted({b for ids in build.AQUARELLE.values() for b in ids}):
        quelle, ziel = DOCS / "img" / f"{bid}.jpg", AQ_DRUCK / f"{bid}.jpg"
        if ziel.exists() and ziel.stat().st_mtime > quelle.stat().st_mtime and Image.open(ziel).width >= AQ_BREITE:
            continue
        im = Image.open(quelle).convert("RGB")
        if im.width < AQ_BREITE:
            im = im.resize((AQ_BREITE, round(im.height * AQ_BREITE / im.width)), Image.LANCZOS)
            im = im.filter(ImageFilter.GaussianBlur(AQ_BREITE / 1400))
        im = ImageEnhance.Brightness(ImageEnhance.Color(im).enhance(1.25)).enhance(1.14)   # wie filter: saturate(1.25)
        im.point(lambda v: round((v - 127.5) * .88 + 127.5)).save(ziel, quality=84)      # brightness(1.14) contrast(.88)


def pinselmaske(n=1000):
    """Rechteck mit wie gemalt ausgefransten, weichen Rändern (Alphakanal), über die Ebene gestreckt."""
    rng = np.random.default_rng(11)
    rauschen = np.zeros((n, n))
    for radius, gewicht in ((40, 1.0), (14, .45), (5, .2)):
        feld = Image.fromarray(rng.integers(0, 256, (n, n), dtype=np.uint8)).filter(ImageFilter.GaussianBlur(radius))
        feld = np.asarray(feld, dtype=float)
        rauschen += gewicht * (feld - feld.mean()) / (feld.std() or 1)
    rauschen /= np.abs(rauschen).max()
    y, x = np.mgrid[0:n, 0:n] / (n - 1)
    rand = np.minimum.reduce([x, 1 - x, y, 1 - y])            # 0 am Rand, 0.5 in der Mitte
    alpha = np.clip((rand - .075 + .05 * rauschen) / .07, 0, 1)
    maske = Image.fromarray((alpha * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(4))
    bild = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    bild.putalpha(maske)
    bild.save(PINSEL, optimize=True)


# ------------------------------------------------------------- Vorrat ---
# Jeder Fluss (<section class="q-fluss">) wird von satz.js auf eigene Seiten gesetzt: zuerst der Kopf
# (.q-oben) über beide Spalten, dann der Inhalt Element für Element in die Spalten. Die data-Attribute
# steuern Kolumnentitel, Aquarelle und den Zahlenstrahl.

def kopf_html(titel, koerperklasse, inhalt, skript=True):
    js = '\n<script src="../../druck/satz.js"></script>' if skript else ""
    return f"""<!doctype html>
<html lang="de-CH">
<head>
<meta charset="utf-8">
<title>{esc(titel)}</title>
<link rel="stylesheet" href="{SCHRIFTEN}">
<link rel="stylesheet" href="../assets/buch.css">
<link rel="stylesheet" href="../../druck/druck.css">
</head>
<body class="druck {koerperklasse}">
{inhalt}{js}
</body>
</html>
"""


def ziel_id(k):
    return f"k-{k['schluessel']}"


def jahresspanne(jahre):
    """«1348 – 1394» → (1348, 1394); «58 v. Chr. – 260» → (-58, 260); «1291 bis heute» → (1291, HEUTE)."""
    def jahr(s):
        if "heute" in s:
            return HEUTE
        j = int(re.search(r"\d+", s).group())
        return -j if "v. Chr" in s else j
    teile = re.split(r"\s+(?:–|bis)\s+", jahre.strip())
    return jahr(teile[0]), jahr(teile[-1])


def ereignisjahr(s):
    """Jahr eines Zeitleisten-Eintrags: «16. Jan. 1349» → 1349, «um 15 v. Chr.» → -15."""
    if m := re.search(r"(\d+)\s*v\. Chr", s):
        return -int(m.group(1))
    m = re.search(r"\d{3,4}", s) or re.search(r"\d+", s)
    return int(m.group()) if m else None


def fluss(fid, inhalt, kopf_links, kopf_rechts, aq="anhang", spalten=2, art="", strahl=None, teil=None, klasse=""):
    """strahl: (von, bis) für die Marke auf dem Zahlenstrahl, «seite» = Jahre der Einträge auf jeder Seite."""
    farbe = TEILE[teil][3] if teil else "#8a6d45"
    aq = (build.AQUARELLE.get(aq) or build.AQUARELLE.get("anhang") or []) if aq else []
    daten = {"id": fid, "aq": " ".join(aq),
             "kopf-links": kopf_links, "kopf-rechts": kopf_rechts, "spalten": spalten, "art": art}
    if teil:
        daten["teil"] = teil
    if strahl == "seite":
        daten["strahl"] = "seite"
    elif strahl:
        daten["von"], daten["bis"] = strahl
    attribute = " ".join(f'data-{k}="{esc(str(v))}"' for k, v in daten.items())
    return f'<section class="q-fluss {klasse}" {attribute} style="--teil:{farbe}">{inhalt}</section>\n'


def eroeffnung(k, bilder, v):
    """Kapitelkopf über beide Spalten: Teil, Nummer bzw. Band, Titel, Jahre, Untertitel und Titelbild."""
    rom, teilname = TEILE[k["teil"]][:2]
    if "nr" in k:
        nummer, hinweis = f'<p class="kopf__nr"><span>Kapitel</span> {k["nr"]}</p>', ""
    else:
        nummer = f'<p class="kopf__nr kopf__nr--art"><span>{esc(k["label"])}</span></p>'
        hinweis = f'<p class="kopf__art">{esc(ARTEN[k["art"]][1])}</p>'
    bild = ""
    if k.get("held") in bilder:
        m = bilder[k["held"]]
        v.setdefault(k["held"], k.get("held_titel", k["titel"]))
        bild = (f'<figure class="eroeffnung__bild" id="bild-{k["held"]}"><div class="eroeffnung__rahmen">'
                f'<img src="../img/{k["held"]}.jpg" width="{m["breite"]}" height="{m["hoehe"]}" '
                f'style="object-position:{esc(k.get("held_pos", "50% 35%"))}" alt="{esc(k.get("held_titel", ""))}">'
                f'</div><figcaption>{k.get("held_legende", "")} '
                f'<span class="fig__nachweis">{nachweis_zeile(m)}</span></figcaption></figure>')
    return f"""<div class="q-oben eroeffnung">
<div class="eroeffnung__text">
<p class="kopf__teil">Teil {rom} · {esc(teilname)}</p>
{nummer}
<h1>{esc(k['titel'])}</h1>
<p class="kopf__jahre">{esc(k.get('jahre', ''))}</p>
<p class="kopf__unter">{esc(k.get('untertitel', ''))}</p>
{hinweis}
</div>
{bild}
</div>"""


def titelblock(titel, vor="", lead=""):
    vor = f'<p class="kopf__teil">{esc(vor)}</p>' if vor else ""
    lead = f'<p class="titelblock__lead">{lead}</p>' if lead else ""
    return f'<div class="q-oben titelblock">{vor}<h1>{esc(titel)}</h1>{lead}</div>'


def titelei(bilder, kapitel):
    """Schmutztitel, Leerseite, Titel und Impressum – je eine feste Seite (.q-seite)."""
    m = bilder[build.TITELBILD]
    bild = (f'<img src="../img/{build.TITELBILD}.jpg" width="{m["breite"]}" height="{m["hoehe"]}" '
            f'alt="Das Rütli am Urnersee">')
    haupt = len(build.hauptkapitel(kapitel))
    stand = datetime.date.today()
    monat = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober",
             "November", "Dezember"][stand.month - 1]
    return f"""<section class="q-titelei">
<div class="q-seite d-schmutztitel"><p>{esc(BUCH)}</p></div>
<div class="q-seite d-leer"></div>
<div class="q-seite d-titel">
<p class="cover__vor">Ein illustriertes Geschichtsbuch</p>
<h1>{esc(BUCH)}</h1>
<p class="cover__unter">{esc(UNTERTITEL)}</p>
<div class="cover__bild">{bild}</div>
<p class="cover__info">{haupt} Kapitel · {len(kapitel) - haupt} Zwischenkapitel</p>
</div>
<div class="q-seite d-impressum">
<p><b>{esc(BUCH)}</b><br>{esc(UNTERTITEL)}</p>
<p>Druckfassung, Stand {monat} {stand.year}. Die Online-Fassung mit allen Bildern in Farbe und vergrösserbar:
<br>graphoflife.github.io/schweizer-geschichte</p>
<p>Texte: Creative Commons Namensnennung – Weitergabe unter gleichen Bedingungen 4.0 (CC BY-SA 4.0),
creativecommons.org/licenses/by-sa/4.0/deed.de</p>
<p>Bilder: gemeinfrei oder unter freien Lizenzen; Urheber, Lizenz und Herkunft jedes Bildes stehen in der Bildlegende
und im Bildnachweis am Ende des Buches. Die meisten Bilder stammen von Wikimedia Commons.</p>
<p>Karten: eigene Darstellung auf Grundlage der generalisierten Grenzen des Bundesamts für Statistik
(über das Projekt swiss-maps) und der gemeinfreien Daten von Natural Earth.</p>
<p>Titelbild: {esc(kuenstler(m))}, Rütli am Urnersee.</p>
<p>Quellen und Faktencheck-Protokolle: github.com/graphoflife/schweizer-geschichte</p>
</div>
</section>
"""


def inhaltsverzeichnis(kapitel, anhang):
    """Klassisches Inhaltsverzeichnis; die Seitenzahlen (000) trägt satz.js nach dem Umbruch ein."""
    def zeile(ziel, nummer, titel, zusatz="", klasse=""):
        return (f'<div class="d-toc {klasse}"><span class="d-toc__nr">{nummer}</span>'
                f'<span class="d-toc__titel">{titel}{zusatz}</span><span class="d-toc__punkte"></span>'
                f'<span class="d-toc__seite" data-ziel="{ziel}">000</span></div>')
    teile = [zeile("vorwort", "", "Vorwort", klasse="d-toc--anhang")]
    for t, (rom, name, jahre, farbe) in TEILE.items():
        teile.append(f'<h2 class="d-toc-teil" style="--teil:{farbe}"><span>Teil {rom}</span> {esc(name)} '
                     f'<small>{esc(jahre)}</small></h2>')
        for k in (k for k in kapitel if k["teil"] == t):
            if "nr" in k:
                teile.append(zeile(ziel_id(k), k["nr"], esc(k["titel"])))
            else:
                teile.append(zeile(ziel_id(k), "❦", esc(k["titel"]), f' <em class="d-toc__art">{esc(k["label"])}</em>',
                                   f"d-toc--{k['art']}"))
    teile.append('<h2 class="d-toc-teil"><span>Anhang</span></h2>')
    teile += [zeile(z, "", esc(t), klasse="d-toc--anhang") for z, t in anhang]
    return fluss("inhalt", titelblock("Inhalt") + "".join(teile), "Inhalt", "Inhalt", aq="start")


def lizenz_adresse(name):
    """«CC BY-SA 2.0 de» → creativecommons.org/licenses/by-sa/2.0/de/, «CC0» → …/publicdomain/zero/1.0/"""
    if name == "CC0":
        return "creativecommons.org/publicdomain/zero/1.0/"
    _, art, version, *land = name.split()
    return f"creativecommons.org/licenses/{art.lower()}/{version}/" + (f"{land[0]}/" if land else "")


def bildnachweis(kapitel, bilder, verwendet):
    """Kompakter Bildnachweis: ohne Vorschaubilder, mit Dateinamen statt Links; die Seitenzahlen setzt satz.js."""
    def eintrag(bid, titel, zusatz=""):
        m = bilder[bid]
        datum = f", {esc(m['datum'])}" if m.get("datum") else ""
        return (f'<p class="nw"><b>{esc(titel or m["datei"])}</b> <span class="nw__seite" data-bild="{bid}"></span>'
                f'– {esc(kuenstler(m))}{datum} · {esc(m["lizenz"])} · Wikimedia Commons, Datei «{esc(m["datei"])}»'
                f'{zusatz}</p>')
    teile = []
    for k in kapitel:
        zeilen = [eintrag(bid, titel) for bid, titel in verwendet.get(k["html"], {}).items()]
        if zeilen:
            name = k["titel"] if "nr" not in k else f"Kapitel {k['nr']} · {k['titel']}"
            teile.append(f'<h3 class="nw-titel">{esc(name)}</h3>{"".join(zeilen)}')
    # Welche Aquarelle wirklich im Hintergrund stehen, weiss erst satz.js; es behält nur die verwendeten.
    aq = sorted({b for ids in build.AQUARELLE.values() for b in ids} | {build.TITELBILD})
    teile.append('<h3 class="nw-titel">Aquarelle im Hintergrund und Titelbild</h3>'
                 + "".join(eintrag(bid, bilder[bid]["beschreibung"][:90]).replace('class="nw"', f'class="nw" data-aq="{bid}"')
                           for bid in aq))
    lead = ("Alle Gemälde, Chronik-Illustrationen und Fotografien sind gemeinfrei oder frei lizenziert. Unter dem "
            "Dateinamen sind sie auf Wikimedia Commons (commons.wikimedia.org) mit allen Angaben zu finden. Lizenzen: "
            "CC BY = Namensnennung, CC BY-SA = Namensnennung – Weitergabe unter gleichen Bedingungen, CC0 und Public "
            "Domain = gemeinfrei. Viele Bilder sind für den Druck zugeschnitten, die Aquarelle zudem aufgehellt. "
            "Die Zahl nach dem Titel ist die Seite.")
    # Die CC-Lizenzen verlangen einen Hinweis, wo ihr Text steht – im Druck als Adresse statt als Link.
    benutzt = {b for v in verwendet.values() for b in v} | set(aq)
    lizenzen = {}
    for bid in benutzt:
        name = bilder[bid]["lizenz"]
        if name.startswith("CC"):
            lizenzen[name] = lizenz_adresse(name)
    liste = "".join(f'<p class="nw"><b>{esc(n)}</b><br><span class="nw__url">{esc(a)}</span></p>' for n, a in sorted(lizenzen.items()))
    teile.insert(0, f'<h3 class="nw-titel">Lizenztexte</h3>{liste}')
    return fluss("bildnachweis", titelblock("Bildnachweis", "Anhang", lead) + "".join(teile),
                 "Anhang", "Bildnachweis", aq=None, spalten=3, klasse="d-nachweis")


def zeitleiste(kapitel):
    """Grosse Zeitleiste: alle Ereignisse der Reihe nach, gegliedert nach den Epochen des Zahlenstrahls; jeder
    Eintrag nennt Kapitel und Seite (die Seite trägt satz.js ein), der Zahlenstrahl zeigt die Jahre der Seite."""
    eintraege = []
    for k in kapitel:
        for jahr, text in k.get("ereignisse", []):
            j = ereignisjahr(jahr)
            eintraege.append((j if j is not None else jahresspanne(k["jahre"])[0], len(eintraege), jahr, text, k))
    eintraege.sort(key=lambda e: e[:2])
    teile, offen = [], None
    for j, _, jahr, text, k in eintraege:
        t = max(n for n, g in enumerate(GRENZEN, 1) if j >= g or n == 1)
        rom, name, _, farbe = TEILE[t]
        if t != offen:
            von, bis = GRENZEN[t - 1], (GRENZEN + [HEUTE])[t]
            spanne = f"{jahr_text(von)} – {jahr_text(bis)}"
            teile.append(f'<h2 class="zt-teil" style="--teil:{farbe}"><span>{esc(spanne)}</span> {esc(name)}</h2>')
            offen = t
        verweis = f"Kap. {k['nr']}" if "nr" in k else k["label"]
        teile.append(f'<div class="zt" data-jahr="{j}" style="--teil:{farbe}"><time>{esc(jahr)}</time>'
                     f'<p>{esc(text)} <span class="zt__kap" data-ziel="{ziel_id(k)}">{esc(verweis)}</span></p></div>')
    lead = ("Die wichtigsten Ereignisse aus zweitausend Jahren Schweizer Geschichte der Reihe nach, gegliedert wie der "
            "Zahlenstrahl am Seitenrand. Jeder Eintrag nennt das Kapitel und die Seite, wo er ausführlich erzählt wird.")
    return fluss("zeitleiste", titelblock("Zeitleiste", "Anhang", lead) + "".join(teile), "Anhang", "Zeitleiste",
                 strahl="seite", klasse="d-zeitleiste")


def jahr_text(j):
    return "heute" if j >= HEUTE else f"{-j} v. Chr." if j < 0 else str(j)


def baue_html(bilder, kapitel):
    verwendet = {}
    fluesse = []
    for k in kapitel:
        v = {}
        koerper = expandiere(k["inhalt"], "../", bilder, v, k["html"])
        rom, teilname = TEILE[k["teil"]][:2]
        art = k.get("art", "")
        rechts = f"Kapitel {k['nr']} · {k['titel']}" if "nr" in k else f"{k['label']} · {k['titel']}"
        fluesse.append(fluss(ziel_id(k), eroeffnung(k, bilder, v) + koerper, f"Teil {rom} · {teilname}", rechts,
                             aq=k["schluessel"], art=art, strahl=jahresspanne(k["jahre"]), teil=k["teil"],
                             klasse=f"art-{art}" if art else ""))
        verwendet[k["html"]] = v

    vorwort = expandiere((SRC / "seiten" / "vorwort.html").read_text(), "../", bilder, {}, "vorwort")
    vorwort = vorwort.replace("Mit den Pfeiltasten ← und → lässt sich wie in einem Buch blättern. Ein Klick auf ein Bild "
                              "vergrössert es. ", "")
    vorwort = re.sub(r"<h2>Vorwort</h2>", "", vorwort)
    vorwort = fluss("vorwort", titelblock("Vorwort") + f"<section>{vorwort}</section>", "Vorwort", "Vorwort", aq="start",
                    klasse="d-vorwort")

    ueber = expandiere((SRC / "seiten" / "ueber.html").read_text(), "../", bilder, {}, "ueber")
    lead = re.search(r'<p class="lead">(.*?)</p>', ueber, re.S).group(1)
    ueber = re.sub(r'<header class="anhang__kopf">.*?</header>', "", ueber, flags=re.S)
    ueber = fluss("ueber", titelblock("Über dieses Buch", "Anhang", lead) + ueber, "Anhang", "Über dieses Buch")

    anhang = [("zeitleiste", "Zeitleiste"), ("ueber", "Über dieses Buch"), ("bildnachweis", "Bildnachweis")]
    vorrat = (titelei(bilder, kapitel) + inhaltsverzeichnis(kapitel, anhang) + vorwort + "".join(fluesse)
              + zeitleiste(kapitel) + ueber + bildnachweis(kapitel, bilder, verwendet))
    # Im Druck müssen alle Bilder sofort geladen werden.
    vorrat = vorrat.replace(' loading="lazy"', "").replace(' decoding="async"', "")
    teile = {t: {"rom": rom, "name": name, "farbe": farbe} for t, (rom, name, _, farbe) in TEILE.items()}
    daten = json.dumps({"heute": HEUTE, "grenzen": GRENZEN, "teile": teile, "titelbild": build.TITELBILD},
                       ensure_ascii=False)
    return kopf_html(BUCH, "", f'<div id="vorrat">\n{vorrat}</div>\n<div id="buch"></div>\n'
                               f'<script type="application/json" id="satz-daten">{daten}</script>')


def umschlag_html(bilder):
    m = bilder[build.TITELBILD]
    return kopf_html(f"{BUCH} – Umschlag", "d-umschlag", f"""<section class="cover">
<div class="cover__bild"><img src="../img/{build.TITELBILD}.jpg" width="{m["breite"]}" height="{m["hoehe"]}" alt=""></div>
<div class="cover__text">
<p class="cover__vor">Ein illustriertes Geschichtsbuch</p>
<h1>{esc(BUCH)}</h1>
<p class="cover__unter">{esc(UNTERTITEL)}</p>
</div>
</section>""", skript=False)


def rueckseite_html():
    """Rückseite ohne Text: nur der Papierton der Vorderseite."""
    return kopf_html(f"{BUCH} – Rückseite", "d-umschlag", '<section class="cover cover--leer"></section>', skript=False)


def bezug_html(bilder):
    """Ganzer Hardcover-Bezug in einem Stück: Einschlag | Rückseite | Gelenk | Rücken | Gelenk | Vorderseite | Einschlag."""
    m = bilder[build.TITELBILD]
    halb = EINSCHLAG + DECKEL_B + GELENK
    breite, hoehe = 2 * halb + RUECKEN, DECKEL_H + 2 * EINSCHLAG
    return kopf_html(f"{BUCH} – Umschlag (Hardcover)", "d-umschlag d-bezug", f"""<style>
@page {{ size: {breite:.2f}mm {hoehe}mm; margin: 0; }}
.d-bezug {{ --halb: {halb}mm; --ruecken: {RUECKEN}mm; --einschlag: {EINSCHLAG}mm; --gelenk: {GELENK}mm;
  --breite: {breite:.2f}mm; --hoehe: {hoehe}mm; --deckel-b: {DECKEL_B}mm; --deckel-h: {DECKEL_H}mm; }}
</style>
<div class="bezug">
<div class="bezug__deckel bezug__deckel--hinten"></div>
<div class="bezug__ruecken"><p>{esc(BUCH)}</p></div>
<div class="bezug__deckel bezug__deckel--vorne">
<section class="cover">
<div class="cover__bild"><img src="../img/{build.TITELBILD}.jpg" width="{m["breite"]}" height="{m["hoehe"]}" alt=""></div>
<div class="cover__text">
<p class="cover__vor">Ein illustriertes Geschichtsbuch</p>
<h1>{esc(BUCH)}</h1>
<p class="cover__unter">{esc(UNTERTITEL)}</p>
</div>
</section>
</div>
</div>""", skript=False)


# ------------------------------------------------------------- Chrome ---

class Chrome:
    """Minimaler DevTools-Client: Seite laden, auf Schriften und Bilder warten, setzen, als PDF drucken."""

    async def __aenter__(self):
        self.profil = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        muster = next((p for p in TRENNMUSTER if p.is_dir()), None)
        if muster:
            shutil.copytree(muster, Path(self.profil.name) / "hyphen-data")
        else:
            print("Warnung: keine Trennmuster von Chrome gefunden – der Blocksatz wird ohne Silbentrennung gesetzt.")
        programm = shutil.which("google-chrome") or shutil.which("chromium") or "google-chrome"
        self.proc = subprocess.Popen(
            [programm, "--headless=new", "--remote-debugging-port=0", f"--user-data-dir={self.profil.name}",
             "--no-first-run", "--no-default-browser-check", "--allow-file-access-from-files",
             "--disable-gpu", "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        for zeile in self.proc.stderr:
            if "DevTools listening on" in zeile:
                url = zeile.split(" on ", 1)[1].strip()
                break
        else:
            raise SystemExit("Chrome liess sich nicht starten")
        threading.Thread(target=lambda: [None for _ in self.proc.stderr], daemon=True).start()
        self.ws = await connect(url, max_size=None, ping_interval=None)
        self.ids = itertools.count(1)
        self.antworten, self.ereignisse = {}, asyncio.Queue()
        self.leser = asyncio.create_task(self._lies())
        ziel = await self.befehl("Target.createTarget", url="about:blank")
        self.sitzung = (await self.befehl("Target.attachToTarget", targetId=ziel["targetId"], flatten=True))["sessionId"]
        await self.befehl("Page.enable", sitzung=self.sitzung)
        # Gesetzt wird mit den Druck-Stilen und einem Fenster von Seitengrösse, damit Bildschirm und PDF gleich umbrechen.
        await self.befehl("Emulation.setEmulatedMedia", sitzung=self.sitzung, media="print")
        await self.befehl("Emulation.setDeviceMetricsOverride", sitzung=self.sitzung, width=816, height=1145,
                          deviceScaleFactor=1, mobile=False)
        return self

    async def __aexit__(self, *_):
        self.leser.cancel()
        await self.ws.close()
        self.proc.terminate()
        self.proc.wait()
        self.profil.cleanup()

    async def _lies(self):
        async for roh in self.ws:
            nachricht = json.loads(roh)
            if "id" in nachricht:
                self.antworten.pop(nachricht["id"]).set_result(nachricht)
            else:
                await self.ereignisse.put(nachricht)

    async def befehl(self, methode, sitzung=None, **params):
        nr = next(self.ids)
        self.antworten[nr] = asyncio.get_running_loop().create_future()
        nachricht = {"id": nr, "method": methode, "params": params}
        if sitzung:
            nachricht["sessionId"] = sitzung
        await self.ws.send(json.dumps(nachricht))
        antwort = await self.antworten[nr]
        if "error" in antwort:
            raise SystemExit(f"{methode}: {antwort['error']}")
        return antwort["result"]

    async def werte_aus(self, ausdruck):
        antwort = await self.befehl("Runtime.evaluate", sitzung=self.sitzung, awaitPromise=True, returnByValue=True,
                                    expression=ausdruck)
        if "exceptionDetails" in antwort:
            fehler = antwort["exceptionDetails"]
            raise SystemExit(f"Fehler in Chrome: {fehler.get('exception', {}).get('description') or fehler['text']}")
        return antwort["result"].get("value")

    async def drucke(self, quelle, ziel, setzen=False):
        while not self.ereignisse.empty():
            self.ereignisse.get_nowait()
        await self.befehl("Page.navigate", sitzung=self.sitzung, url=quelle.as_uri())
        while (await self.ereignisse.get()).get("method") != "Page.loadEventFired":
            pass
        fehlend = await self.werte_aus("""(async () => {
              await document.fonts.ready;
              await Promise.all([...document.images].map(i => i.complete ? 0 :
                  new Promise(r => { i.onload = i.onerror = r; })));
              return [...document.images].filter(i => !i.naturalWidth).map(i => i.src);
            })()""")
        if fehlend:
            raise SystemExit(f"Bilder nicht geladen: {fehlend[:5]}")
        bericht = await self.werte_aus("satz()") if setzen else None
        await self.werte_aus("""(async () => {
              await Promise.all([...document.images].map(i => i.complete ? 0 :
                  new Promise(r => { i.onload = i.onerror = r; })));
              await new Promise(r => setTimeout(r, 1500));
            })()""")
        pdf = await self.befehl("Page.printToPDF", sitzung=self.sitzung, printBackground=True,
                                preferCSSPageSize=True, generateDocumentOutline=True,
                                transferMode="ReturnAsStream")
        with open(ziel, "wb") as f:
            while True:
                stueck = await self.befehl("IO.read", sitzung=self.sitzung, handle=pdf["stream"], size=8 << 20)
                f.write(base64.b64decode(stueck["data"]) if stueck.get("base64Encoded") else stueck["data"].encode())
                if stueck.get("eof"):
                    break
        await self.befehl("IO.close", sitzung=self.sitzung, handle=pdf["stream"])
        return bericht


def seitenzahl(pdf):
    info = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True, check=True).stdout
    return int(re.search(r"Pages:\s+(\d+)", info).group(1))


async def main(umschlag, auswahl):
    bilder = build.lade_bilder()
    build.lade_aquarelle(bilder)
    kapitel = build.lade_kapitel()
    if auswahl:
        kapitel = [k for k in kapitel if k["schluessel"] in auswahl]
    if build.FEHLER:
        raise SystemExit("Fehler im Buch – zuerst tools/build.py ausführen:\n  " + "\n  ".join(build.FEHLER))
    HTML.parent.mkdir(parents=True, exist_ok=True)
    AUSGABE.mkdir(exist_ok=True)
    bereite_aquarelle()
    pinselmaske()
    HTML.write_text(baue_html(bilder, kapitel))
    async with Chrome() as chrome:
        if umschlag:
            UMSCHLAG_HTML.write_text(umschlag_html(bilder))
            await chrome.drucke(UMSCHLAG_HTML, UMSCHLAG_PDF)
            RUECKSEITE_HTML.write_text(rueckseite_html())
            await chrome.drucke(RUECKSEITE_HTML, RUECKSEITE_PDF)
            BEZUG_HTML.write_text(bezug_html(bilder))
            await chrome.drucke(BEZUG_HTML, BEZUG_PDF)
            print(f"Umschlag → {UMSCHLAG_PDF}, {RUECKSEITE_PDF.name}, {BEZUG_PDF.name}")
        bericht = await chrome.drucke(HTML, PDF, setzen=True)
    for warnung in bericht["warnungen"]:
        print("Warnung:", warnung)
    if seitenzahl(PDF) != bericht["seiten"]:
        raise SystemExit(f"Seitenzahl stimmt nicht: gesetzt {bericht['seiten']}, im PDF {seitenzahl(PDF)}")
    (AUSGABE / "satzbericht.json").write_text(json.dumps(bericht, ensure_ascii=False, indent=1))
    print(f"Buchblock → {PDF} ({bericht['seiten']} Seiten, {PDF.stat().st_size / 2**20:.0f} MB)")


if __name__ == "__main__":
    auswahl = next((a.split("=", 1)[1].split(",") for a in sys.argv if a.startswith("--kapitel=")), None)
    asyncio.run(main("--umschlag" in sys.argv, auswahl))
