#!/usr/bin/env python3
"""Druckfassung: das ganze Buch als PDF für die Druckerei.

  python3 -P tools/druck.py              Buchblock  → druck/Die-Geschichte-der-Schweiz.pdf
  python3 -P tools/druck.py --umschlag   zusätzlich die Umschlag-Vorderseite → druck/Umschlag-Vorderseite.pdf
  python3 -P tools/druck.py --kapitel=16,22a   Probedruck nur mit diesen Kapiteln

Format A4 (210 × 297 mm) mit 3 mm Beschnitt rundum, also 216 × 303 mm pro Seite; die Gestaltung steht in
druck/druck.css. Zuerst entsteht docs/druck/buch.html (alle Kapitel hintereinander, wie die Website gebaut),
dann rendert Chrome (headless, über das DevTools-Protokoll) daraus das PDF. Ein zweiter Durchgang trägt die
Seitenzahlen ins Inhaltsverzeichnis ein; sie werden aus dem Text des ersten PDFs gelesen (pdftotext).

Benötigt Google Chrome, poppler-utils (pdftotext, pdfinfo) und das Python-Paket websockets
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
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build  # noqa: E402
from build import (ARTEN, BUCH, DOCS, ROOT, SRC, TEILE, UNTERTITEL, esc, expandiere,  # noqa: E402
                   hinterlege, kopf, kuenstler)

import numpy as np  # noqa: E402
from PIL import Image, ImageEnhance, ImageFilter  # noqa: E402
from websockets.asyncio.client import connect  # noqa: E402

HTML = DOCS / "druck" / "buch.html"           # Zwischenstufe (nicht im Repository)
UMSCHLAG_HTML = DOCS / "druck" / "umschlag.html"
AUSGABE = ROOT / "druck"
PDF = AUSGABE / "Die-Geschichte-der-Schweiz.pdf"
UMSCHLAG_PDF = AUSGABE / "Umschlag-Vorderseite.pdf"
SCHRIFTEN = build.SCHRIFTEN
AQ_DRUCK = DOCS / "druck" / "aq"
PINSEL = DOCS / "druck" / "pinsel.png"


# ------------------------------------------------------------ Aquarelle ---
# Auf der Website hellt ein CSS-Filter die Aquarelle auf, und eine SVG-Maske mit Turbulenz-Filter franst
# die Ränder aus. Chrome würde beides im PDF als riesige Pixelbilder ablegen (hundertfache Dateigrösse).
# Für den Druck wird die Farbanpassung deshalb vorab in die Bilder gerechnet und die Maske als PNG erzeugt.

def bereite_aquarelle():
    AQ_DRUCK.mkdir(parents=True, exist_ok=True)
    for bid in sorted({b for ids in build.AQUARELLE.values() for b in ids}):
        quelle, ziel = DOCS / "img" / f"{bid}.jpg", AQ_DRUCK / f"{bid}.jpg"
        if ziel.exists() and ziel.stat().st_mtime > quelle.stat().st_mtime:
            continue
        im = Image.open(quelle).convert("RGB")       # wie filter: saturate(1.25) brightness(1.14) contrast(.88)
        im = ImageEnhance.Brightness(ImageEnhance.Color(im).enhance(1.25)).enhance(1.14)
        im.point(lambda v: round((v - 127.5) * .88 + 127.5)).save(ziel, quality=86)


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


# ------------------------------------------------------------- Dokument ---

def kopf_html(titel, koerperklasse, inhalt):
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
{inhalt}
</body>
</html>
"""


def ziel_id(k):
    return f"k-{k['schluessel']}"


def inhaltsverzeichnis(kapitel, anhang):
    """Klassisches Inhaltsverzeichnis; die Seitenzahlen (000) ersetzt der zweite Durchgang."""
    def zeile(ziel, nummer, titel, zusatz="", klasse=""):
        return (f'<li class="d-toc {klasse}"><a href="#{ziel}"><span class="d-toc__nr">{nummer}</span>'
                f'<span class="d-toc__titel">{titel}{zusatz}</span><span class="d-toc__punkte"></span>'
                f'<span class="d-toc__seite" data-ziel="{ziel}">000</span></a></li>')
    teile = [f'<ol class="d-toc__liste">{zeile("vorwort", "", "Vorwort", klasse="d-toc--anhang")}</ol>']
    for t, (rom, name, jahre, farbe) in TEILE.items():
        zeilen = []
        for k in (k for k in kapitel if k["teil"] == t):
            if "nr" in k:
                zeilen.append(zeile(ziel_id(k), k["nr"], esc(k["titel"])))
            else:
                zeilen.append(zeile(ziel_id(k), "❦", esc(k["titel"]),
                                    f' <em class="d-toc__art">{esc(k["label"])}</em>', f"d-toc--{k['art']}"))
        teile.append(f'<h3 style="--teil:{farbe}"><span>Teil {rom}</span> {esc(name)} <small>{esc(jahre)}</small></h3>'
                     f'<ol class="d-toc__liste">{"".join(zeilen)}</ol>')
    teile.append('<h3><span>Anhang</span></h3><ol class="d-toc__liste">'
                 + "".join(zeile(z, "", esc(t), klasse="d-toc--anhang") for z, t in anhang) + "</ol>")
    return f'<section class="d-inhalt" id="inhalt"><h2>Inhalt</h2>{"".join(teile)}</section>'


def titelei(bilder, kapitel):
    m = bilder[build.TITELBILD]
    bild = (f'<img src="../img/{build.TITELBILD}.jpg" width="{m["breite"]}" height="{m["hoehe"]}" '
            f'alt="Das Rütli am Urnersee">')
    haupt = len(build.hauptkapitel(kapitel))
    stand = datetime.date.today()
    monat = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober",
             "November", "Dezember"][stand.month - 1]
    return f"""<section class="d-titelei d-schmutztitel"><p>{esc(BUCH)}</p></section>
<section class="d-titelei d-leer"></section>
<section class="d-titelei d-titel">
<p class="cover__vor">Ein illustriertes Geschichtsbuch</p>
<h1>{esc(BUCH)}</h1>
<p class="cover__unter">{esc(UNTERTITEL)}</p>
<div class="cover__bild">{bild}</div>
<p class="cover__info">{haupt} Kapitel · {len(kapitel) - haupt} Zwischenkapitel</p>
</section>
<section class="d-titelei d-impressum">
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
</section>"""


def bildnachweis(kapitel, bilder, verwendet):
    """Kompakter Bildnachweis für den Druck: ohne Vorschaubilder, mit Dateinamen statt Links."""
    def eintrag(bid, titel, zusatz=""):
        m = bilder[bid]
        datum = f", {esc(m['datum'])}" if m.get("datum") else ""
        return (f'<li><b>{esc(titel or m["datei"])}</b> – {esc(kuenstler(m))}{datum} · {esc(m["lizenz"])} · '
                f'Wikimedia Commons, Datei «{esc(m["datei"])}»{zusatz}</li>')
    teile = []
    for k in kapitel:
        zeilen = [eintrag(bid, titel) for bid, titel in verwendet.get(k["html"], {}).items()]
        if zeilen:
            name = k["titel"] if "nr" not in k else f"Kapitel {k['nr']} · {k['titel']}"
            teile.append(f'<h3>{esc(name)}</h3><ul>{"".join(zeilen)}</ul>')
    aq = [eintrag(bid, bilder[bid]["beschreibung"][:90], f' · Hintergrund in: {esc(", ".join(seiten))}')
          for bid, seiten in sorted(build.AQ_VERWENDET.items())]
    teile.append('<h3>Aquarelle im Hintergrund und Titelbild</h3><ul>' + "".join(aq) + "</ul>")
    return f"""<article class="kapitel anhang d-bildnachweis" id="bildnachweis">
<header class="anhang__kopf"><p class="kopf__teil">Anhang</p><h1>Bildnachweis</h1>
<p class="lead">Alle Gemälde, Chronik-Illustrationen und Fotografien sind gemeinfrei oder frei lizenziert. Unter
dem Dateinamen sind sie auf Wikimedia Commons (commons.wikimedia.org) mit allen Angaben zu finden. Lizenzen:
CC BY = Namensnennung, CC BY-SA = Namensnennung – Weitergabe unter gleichen Bedingungen
(creativecommons.org/licenses), CC0 und Public Domain = gemeinfrei.</p></header>
<section class="d-nachweis">{"".join(teile)}</section></article>"""


def spalten(html):
    """Im Druck steht die Abschnittsüberschrift ausserhalb des zweispaltigen Satzes – nur so hält Chrome sie
    beim Seitenumbruch mit dem folgenden Text zusammen (über die Spalten laufende Elemente trennt es sonst ab)."""
    return re.sub(r'(<section class="mit-aq">(?:<div class="aq"[^>]*></div>)*)(\s*<h2>.*?</h2>)?(.*?)</section>',
                  lambda m: f'{m.group(1)}{m.group(2) or ""}<div class="d-spalten">{m.group(3)}</div></section>',
                  html, flags=re.S)


def spaltenbilder(html, bilder):
    """Breite Bilder (ausser Panoramen ab 2:1) im Druck in eine Spalte setzen. Über beide Spalten laufende Bilder,
    die nicht mehr auf die Seite passen, rutschen sonst auf die nächste und hinterlassen eine halbleere Seite."""
    def ersetze(m):
        b = bilder[m.group(2)]
        return m.group(0) if b["breite"] / b["hoehe"] >= 2 else f'<figure class="fig fig--spalte" id="bild-{m.group(2)}"'
    return re.sub(r'<figure class="fig fig--(breit|voll)" id="bild-([^"]+)"', ersetze, html)


def baue_html(bilder, kapitel):
    verwendet = {}
    teile = []
    for k in kapitel:
        v = {}
        koerper = expandiere(k["inhalt"], "../", bilder, v, k["html"])
        koerper = spalten(spaltenbilder(hinterlege(koerper, k["schluessel"], "../", build.seitenname(k)), bilder))
        art = f" art-{k['art']}" if "art" in k else ""
        teile.append(f'<article class="kapitel{art}" id="{ziel_id(k)}" style="--teil:{TEILE[k["teil"]][3]}">'
                     f'{kopf(k, bilder, v)}{koerper}</article>')
        verwendet[k["html"]] = v

    vorwort = expandiere((SRC / "seiten" / "vorwort.html").read_text(), "../", bilder, {}, "vorwort")
    vorwort = vorwort.replace("Mit den Pfeiltasten ← und → lässt sich wie in einem Buch blättern. Ein Klick auf ein Bild "
                              "vergrössert es. ", "")
    vorwort = f'<article class="kapitel anhang d-vorwort" id="vorwort"><section class="vorwort">{vorwort}</section></article>'

    zeilen = []
    for k in kapitel:
        for jahr, text in k.get("ereignisse", []):
            zeilen.append(f'<li style="--teil:{TEILE[k["teil"]][3]}"><time>{esc(jahr)}</time>'
                          f'<p>{esc(text)} <a href="#{ziel_id(k)}">{esc(k["label"])}</a></p></li>')
    zeitleiste = f"""<article class="kapitel anhang" id="zeitleiste">
<header class="anhang__kopf"><p class="kopf__teil">Anhang</p><h1>Zeitleiste</h1>
<p class="lead">Die wichtigsten Ereignisse aus zweitausend Jahren Schweizer Geschichte – jeder Eintrag nennt das Kapitel,
in dem er ausführlich erzählt wird.</p></header>
<ol class="grosse-zeitleiste">{"".join(zeilen)}</ol></article>"""

    ueber = (SRC / "seiten" / "ueber.html").read_text()
    ueber = f'<article class="kapitel anhang" id="ueber">{expandiere(ueber, "../", bilder, {}, "ueber")}</article>'

    build.AQ_VERWENDET.setdefault(build.TITELBILD, []).append("Titelbild")
    anhang = [("zeitleiste", "Zeitleiste"), ("ueber", "Über dieses Buch"), ("bildnachweis", "Bildnachweis")]
    inhalt = (titelei(bilder, kapitel) + inhaltsverzeichnis(kapitel, anhang) + vorwort + "".join(teile)
              + zeitleiste + ueber + bildnachweis(kapitel, bilder, verwendet))
    # Im Druck müssen alle Bilder sofort geladen werden.
    inhalt = inhalt.replace(' loading="lazy"', "").replace(' decoding="async"', "")
    inhalt = inhalt.replace("url(../img/aq-", "url(../druck/aq/aq-")    # aufgehellte Druck-Aquarelle (relativ zu assets/)
    return kopf_html(BUCH, "", inhalt)


def umschlag_html(bilder):
    m = bilder[build.TITELBILD]
    return kopf_html(f"{BUCH} – Umschlag", "d-umschlag", f"""<section class="cover">
<div class="cover__bild"><img src="../img/{build.TITELBILD}.jpg" width="{m["breite"]}" height="{m["hoehe"]}" alt=""></div>
<div class="cover__text">
<p class="cover__vor">Ein illustriertes Geschichtsbuch</p>
<h1>{esc(BUCH)}</h1>
<p class="cover__unter">{esc(UNTERTITEL)}</p>
</div>
</section>""")


# ------------------------------------------------------------ Seitenzahlen ---

def normal(s):
    s = unicodedata.normalize("NFKC", s).replace("\u00ad", "")
    return re.sub(r"[\s\-\u2010]+", "", s)      # pdftotext verschluckt Trennstriche am Zeilenende


def seiten_text(pdf):
    text = subprocess.run(["pdftotext", "-enc", "UTF-8", str(pdf), "-"], capture_output=True, text=True,
                          check=True).stdout
    return [normal(s) for s in text.split("\f")]


def finde_seiten(pdf, marken):
    """Seitenzahl (1-basiert) jedes Ziels; marken: Liste (ziel, [Textstücke]) in Buchreihenfolge."""
    seiten = seiten_text(pdf)
    gefunden, start = {}, 0
    for ziel, stuecke in marken:
        stuecke = [normal(s) for s in stuecke]
        for i in range(start, len(seiten)):
            if all(s in seiten[i] for s in stuecke):
                gefunden[ziel] = i + 1
                start = i
                break
        else:
            raise SystemExit(f"Seite für «{ziel}» nicht gefunden ({stuecke})")
    return gefunden


def marken(kapitel):
    m = [("inhalt", ["Inhalt", "Vorwort"]), ("vorwort", ["Vorwort", "Warum spricht man"])]
    for k in kapitel:
        rom, name = TEILE[k["teil"]][:2]
        m.append((ziel_id(k), [f"Teil {rom} · {name}", k["titel"]]))
    m += [("zeitleiste", ["Anhang", "Zeitleiste", "Die wichtigsten Ereignisse"]),
          ("ueber", ["Anhang", "Über dieses Buch"]),
          ("bildnachweis", ["Anhang", "Bildnachweis", "Alle Gemälde"])]
    return m


def setze_seitenzahlen(html, seiten):
    return re.sub(r'<span class="d-toc__seite" data-ziel="([^"]+)">\d+</span>',
                  lambda m: f'<span class="d-toc__seite" data-ziel="{m.group(1)}">{seiten[m.group(1)]}</span>', html)


# ------------------------------------------------------------- Chrome ---

class Chrome:
    """Minimaler DevTools-Client: Seite laden, auf Schriften und Bilder warten, als PDF drucken."""

    async def __aenter__(self):
        self.profil = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
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

    async def drucke(self, quelle, ziel):
        while not self.ereignisse.empty():
            self.ereignisse.get_nowait()
        await self.befehl("Page.navigate", sitzung=self.sitzung, url=quelle.as_uri())
        while (await self.ereignisse.get()).get("method") != "Page.loadEventFired":
            pass
        fehlend = await self.befehl("Runtime.evaluate", sitzung=self.sitzung, awaitPromise=True, returnByValue=True,
                                    expression="""(async () => {
              await document.fonts.ready;
              await Promise.all([...document.images].map(i => i.complete ? 0 :
                  new Promise(r => { i.onload = i.onerror = r; })));
              await new Promise(r => setTimeout(r, 1500));
              return [...document.images].filter(i => !i.naturalWidth).map(i => i.src);
            })()""")
        if fehlend["result"]["value"]:
            raise SystemExit(f"Bilder nicht geladen: {fehlend['result']['value'][:5]}")
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
    html = baue_html(bilder, kapitel)
    async with Chrome() as chrome:
        if umschlag:
            UMSCHLAG_HTML.write_text(umschlag_html(bilder))
            await chrome.drucke(UMSCHLAG_HTML, UMSCHLAG_PDF)
            print(f"Umschlag → {UMSCHLAG_PDF}")
        seiten = None
        for durchgang in range(1, 4):
            HTML.write_text(setze_seitenzahlen(html, seiten) if seiten else html)
            await chrome.drucke(HTML, PDF)
            neu = finde_seiten(PDF, marken(kapitel))
            print(f"Durchgang {durchgang}: {seitenzahl(PDF)} Seiten")
            if neu == seiten:
                break
            seiten = neu
    print(f"Buchblock → {PDF} ({PDF.stat().st_size / 2**20:.0f} MB)")


if __name__ == "__main__":
    auswahl = next((a.split("=", 1)[1].split(",") for a in sys.argv if a.startswith("--kapitel=")), None)
    asyncio.run(main("--umschlag" in sys.argv, auswahl))
