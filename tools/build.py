#!/usr/bin/env python3
"""Baut das Buch aus src/ nach docs/ (GitHub Pages).

  python3 -I tools/build.py          baut alles und meldet Fehler (fehlende Bilder usw.)

Kapitel liegen als HTML-Fragmente in src/kapitel/NN-slug.html. Ausser gewöhnlichem HTML
verstehen sie drei eigene Elemente, die hier in fertiges Markup verwandelt werden:
  <bild id="…" lage="spalte|breit|voll" titel="…">Legende <punkt x="40" y="30">…</punkt></bild>
  <karte typ="schweiz|region|beitritt" titel="…" …>Legende <ort …/> <route …/></karte>
Die vollständige Beschreibung steht in src/ANLEITUNG.md.
"""
import html
import itertools
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
DOCS = ROOT / "docs"

BUCH = "Die Geschichte der Schweiz"
UNTERTITEL = "Zweitausend Jahre – von den Helvetiern bis heute"
REPO = "https://github.com/graphoflife/schweizer-geschichte"

TEILE = {
    1: ("I", "Kelten, Römer und Klöster", "58 v. Chr. – 1032", "#a0612b"),
    2: ("II", "Die Entstehung der Eidgenossenschaft", "1032 – 1393", "#b0282e"),
    3: ("III", "Die Eidgenossen als Kriegsmacht", "1400 – 1527", "#8a2f5c"),
    4: ("IV", "Glaube und Spaltung", "1519 – 1712", "#2f5d8a"),
    5: ("V", "Gnädige Herren und Aufklärer", "1648 – 1797", "#3d7a5a"),
    6: ("VI", "Revolution und Neuordnung", "1798 – 1847", "#b8741a"),
    7: ("VII", "Der junge Bundesstaat", "1848 – 1914", "#1f6f78"),
    8: ("VIII", "Im Zeitalter der Weltkriege", "1914 – 1945", "#59606b"),
    9: ("IX", "Die moderne Schweiz", "1945 bis heute", "#a8336a"),
}

# Zwischenkapitel (Meta "art"): Bezeichnung, Hinweis unter dem Titel
ARTEN = {
    "ueberblick": ("Überblick", "Ein Überblickskapitel: Es erzählt nicht Ereignis um Ereignis, sondern erklärt, "
                   "wer die Macht hatte und wie Herrschaft aufgebaut war."),
    "kanton": ("Vor der Schweiz", "Vor der Schweiz: Was dieses Gebiet war und tat, bevor es ein Schweizer Kanton wurde."),
    "neben": ("Nebengeschichte", "Eine Nebengeschichte: Sie hat die Schweiz nicht geformt – aber sie ist wahr, "
              "belegt und erzählenswert."),
    "legende": ("Legende", "Eine Legende: So wird es seit Jahrhunderten erzählt. Was davon belegt ist und was nicht, "
                "steht in den Kästen «Mythos und Wirklichkeit»."),
}

FEHLER = []


def esc(s):
    return html.escape(str(s), quote=True)


def attrs(s):
    return {k: html.unescape(v) for k, v in re.findall(r'([\w-]+)="([^"]*)"', s)}


# ---------------------------------------------------------------- Bilder ---

def lade_bilder():
    """Nachweis aus src/bilder/nachweis/*.json, ergänzt um Angaben aus den Bildlisten."""
    bilder = {}
    for liste in sorted((SRC / "bilder").glob("*.json")):
        nachweis = SRC / "bilder" / "nachweis" / liste.name
        meta = json.loads(nachweis.read_text()) if nachweis.exists() else {}
        for e in json.loads(liste.read_text()):
            if e["id"] in bilder:
                FEHLER.append(f"Bild-ID doppelt vergeben: {e['id']}")
            if e["id"] not in meta or not (DOCS / "img" / f"{e['id']}.jpg").exists():
                FEHLER.append(f"Bild nicht geladen (tools/bilder.py ausführen): {e['id']}")
                continue
            m = dict(meta[e["id"]])
            for k in ("kuenstler", "datum"):
                if e.get(k):
                    m[k] = e[k]
            m["liste"] = liste.stem
            bilder[e["id"]] = m
    return bilder


def kuenstler(m):
    k = m["kuenstler"]
    k = re.sub(r"^(Unknown author|Unknown|Anonymous|unbekannt|Unbekannter? .*)$", "Unbekannt", k, flags=re.I)
    k = re.sub(r"\b(de|en|fr):", "", k)
    return k


def nachweis_zeile(m):
    lizenz = esc(m["lizenz"])
    if m.get("lizenz_url"):
        lizenz = f'<a href="{esc(m["lizenz_url"])}" rel="license">{lizenz}</a>'
    return (f'{esc(kuenstler(m))} · {lizenz} · '
            f'<a href="{esc(m["seite"])}">Wikimedia Commons</a>')


def render_bild(a, innen, root, bilder, verwendet, kapitel):
    bid = a.get("id", "")
    m = bilder.get(bid)
    if not m:
        FEHLER.append(f"{kapitel}: unbekanntes Bild «{bid}»")
        return f'<p class="fehlt">[Bild {esc(bid)} fehlt]</p>'
    verwendet.setdefault(bid, a.get("titel", ""))
    lage = a.get("lage", "spalte")
    punkte = re.findall(r'<punkt\s+([^>]*)>(.*?)</punkt>', innen, re.S)
    legende = re.sub(r'<punkt\s+[^>]*>.*?</punkt>', "", innen, flags=re.S).strip()
    pins = "".join(
        f'<span class="pin" style="left:{esc(p["x"])}%;top:{esc(p["y"])}%" data-n="{i}">{i}</span>'
        for i, (p, _) in enumerate(((attrs(pa), t) for pa, t in punkte), 1))
    liste = ""
    if punkte:
        liste = '<ol class="fig__punkte">' + "".join(
            f'<li data-n="{i}">{t.strip()}</li>' for i, (_, t) in enumerate(punkte, 1)) + "</ol>"
    src = f"{root}img/{bid}.jpg"
    alt = a.get("alt") or a.get("titel", "")
    titel = f'<span class="fig__titel">{esc(a["titel"])}</span> ' if a.get("titel") else ""
    return (
        f'<figure class="fig fig--{esc(lage)}" id="bild-{esc(bid)}">'
        f'<div class="fig__rahmen" style="--b:{m["breite"]};--h:{m["hoehe"]}"><a class="fig__link" href="{src}">'
        f'<img src="{src}" width="{m["breite"]}" height="{m["hoehe"]}" alt="{esc(alt)}" '
        f'loading="lazy" decoding="async"></a>{pins}</div>'
        f'<figcaption>{liste}<p>{titel}{legende}</p>'
        f'<p class="fig__nachweis">{nachweis_zeile(m)}</p></figcaption></figure>'
    )


# ---------------------------------------------------------------- Karten ---

GEO = None
SCHWEIZ = (5.88, 45.76, 10.56, 47.87)
REGION = (3.4, 44.6, 12.4, 49.3)
BEITRITT = {
    "UR": 1291, "SZ": 1291, "OW": 1291, "NW": 1291, "LU": 1332, "ZH": 1351, "GL": 1352, "ZG": 1352,
    "BE": 1353, "FR": 1481, "SO": 1481, "BS": 1501, "BL": 1501, "SH": 1501, "AR": 1513, "AI": 1513,
    "SG": 1803, "GR": 1803, "AG": 1803, "TG": 1803, "TI": 1803, "VD": 1803,
    "VS": 1815, "NE": 1815, "GE": 1815, "JU": 1979,
}
EPOCHEN = [  # (bis Jahr, Farbe, Legende)
    (1291, "#6e1414", "1291 Uri, Schwyz, Unterwalden"),
    (1353, "#a8262b", "1332–1353 Luzern, Zürich, Glarus, Zug, Bern"),
    (1513, "#d4553f", "1481–1513 Freiburg, Solothurn, Basel, Schaffhausen, Appenzell"),
    (1803, "#e8935c", "1803 St. Gallen, Graubünden, Aargau, Thurgau, Tessin, Waadt"),
    (1815, "#f2c27f", "1815 Wallis, Neuenburg, Genf"),
    (1979, "#f7e2a8", "1979 Jura"),
]
KANTON_LABEL = {  # Lagekorrekturen für Kantonskürzel (lon, lat)
    "BE": (7.62, 46.72), "SO": (7.58, 47.27), "SG": (9.18, 47.17), "BL": (7.73, 47.45),
    "VD": (6.62, 46.6), "FR": (7.08, 46.7), "SZ": (8.73, 47.04), "OW": (8.2, 46.86),
    "NW": (8.42, 46.93), "AI": (9.43, 47.31), "AR": (9.32, 47.39), "LU": (8.1, 47.06),
}
FARBEN = ["var(--teil)", "#d9a441", "#5b7fa6", "#6f8f4e"]
LAENDER_LABEL = {
    "Frankreich": (4.6, 47.6), "Deutschland": (9.6, 48.55), "Italien": (9.4, 45.0),
    "Österreich": (11.0, 47.25), "Liechtenstein": (9.55, 47.14),
}
SYMBOLE = {"stadt": "Stadt", "schlacht": "Schlacht", "kloster": "Kloster/Kirche",
           "pass": "Pass", "roemisch": "Römischer Ort", "burg": "Burg", "ort": "Ort"}


class Projektion:
    def __init__(self, box, breite=1000):
        self.lon0, self.lat0, self.lon1, self.lat1 = box
        self.k = math.cos(math.radians((self.lat0 + self.lat1) / 2))
        self.s = breite / ((self.lon1 - self.lon0) * self.k)
        self.w, self.h = breite, round((self.lat1 - self.lat0) * self.s)

    def __call__(self, lon, lat):
        return (lon - self.lon0) * self.k * self.s, (self.lat1 - lat) * self.s

    def pfad(self, ringe, zu=True):
        teile = []
        for r in ringe:
            pts = [self(*p) for p in r]
            teile.append("M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in pts) + ("Z" if zu else ""))
        return "".join(teile)


def schwerpunkt(ringe):
    r = max(ringe, key=len)
    a = cx = cy = 0
    for (x1, y1), (x2, y2) in zip(r, r[1:] + r[:1]):
        f = x1 * y2 - x2 * y1
        a += f
        cx += (x1 + x2) * f
        cy += (y1 + y2) * f
    return (cx / (3 * a), cy / (3 * a)) if a else tuple(r[0])


def symbol(typ, x=0, y=0, f=1.0):
    """Kartensymbol um (0,0) gezeichnet, verschoben und skaliert."""
    form = {
        "schlacht": '<circle r="9"/><path d="M-5,-5L5,5M5,-5L-5,5"/>',
        "kloster": '<path d="M0,-8V8M-6,-2H6"/>',
        "pass": '<path d="M-7,5L0,-7L7,5Z"/>',
        "roemisch": '<rect x="-6" y="-6" width="12" height="12"/>',
        "burg": '<path d="M0,-8L8,0L0,8L-8,0Z"/>',
        "stadt": '<circle r="6.5"/>',
    }.get(typ, '<circle r="5"/>')
    t = typ if typ in SYMBOLE else "ort"
    return f'<g class="sym sym--{t}" transform="translate({x:.1f},{y:.1f}) scale({f})">{form}</g>'


def beschriftung(text, x, y, pos, klasse="karte__ort", f=1.0):
    d = 13 * f
    dx, dy, anker = {
        "e": (d, 5 * f, "start"), "w": (-d, 5 * f, "end"), "n": (0, -d, "middle"),
        "s": (0, d + 12 * f, "middle"), "ne": (d * .8, -d * .8, "start"), "nw": (-d * .8, -d * .8, "end"),
        "se": (d * .8, d + 8 * f, "start"), "sw": (-d * .8, d + 8 * f, "end"),
    }.get(pos, (d, 5 * f, "start"))
    return f'<text class="{klasse}" x="{x + dx:.1f}" y="{y + dy:.1f}" text-anchor="{anker}">{esc(text)}</text>'


def render_karte(a, innen, kapitel):
    global GEO
    if GEO is None:
        GEO = json.loads((SRC / "karten" / "geo.json").read_text())
    typ = a.get("typ", "schweiz")
    box = SCHWEIZ if typ in ("schweiz", "beitritt") else REGION
    if a.get("ausschnitt"):
        try:
            box = tuple(float(v) for v in a["ausschnitt"].split(","))
        except ValueError:
            FEHLER.append(f"{kapitel}: ungültiger Kartenausschnitt {a['ausschnitt']}")
    P = Projektion(box)
    lage = a.get("lage", "spalte")
    f = 1.8 if lage == "spalte" else 1.0
    teile = [f'<rect class="karte__grund" width="{P.w}" height="{P.h}"/>']
    legende = []

    gruppen = []  # (Kantone, Farbe, Legende)
    namen = a.get("legende", "").split("|")
    for i, key in enumerate(("kantone", "kantone2", "kantone3", "kantone4")):
        if a.get(key):
            gruppen.append((a[key].split(), FARBEN[i], namen[i] if i < len(namen) else ""))
    for kt, _, _ in gruppen:
        for k in kt:
            if k not in GEO["kantone"]:
                FEHLER.append(f"{kapitel}: unbekanntes Kantonskürzel {k}")

    if typ == "region":
        for name, ringe in GEO["laender"].items():
            cls = "karte__ch" if name == "Schweiz" else "karte__land"
            teile.append(f'<path class="{cls}" d="{P.pfad(ringe)}"/>')
        for kt, farbe, _ in gruppen:
            for k in kt:
                teile.append(f'<path class="karte__hervor" style="fill:{farbe};fill-opacity:.5" d="{P.pfad(GEO["kantone"].get(k, []))}"/>')
        teile.append(f'<path class="karte__seen" d="{P.pfad(GEO["seen"])}"/>')
    else:
        bis = int(a.get("bis", "9999"))
        for k, ringe in GEO["kantone"].items():
            stil = ""
            if typ == "beitritt":
                jahr = BEITRITT[k]
                if jahr <= bis:
                    stil = next(f for j, f, _ in EPOCHEN if jahr <= j)
            for kt, farbe, _ in gruppen:
                if k in kt:
                    stil = f"{farbe};fill-opacity:.45"
            style = f' style="fill:{stil}"' if stil else ""
            teile.append(f'<path class="karte__kanton{" karte__hervor" if stil else ""}"{style} d="{P.pfad(ringe)}"/>')
        teile.append(f'<path class="karte__seen" d="{P.pfad(GEO["seen_ch"])}"/>')
    for fluss in GEO["fluesse"]:
        teile.append(f'<path class="karte__fluss" d="{P.pfad([fluss["pts"]], zu=False)}"/>')
    if typ == "region":
        for name, (lon, lat) in LAENDER_LABEL.items():
            x, y = P(lon, lat)
            if 0 < x < P.w and 0 < y < P.h and name != "Liechtenstein":
                teile.append(f'<text class="karte__landname" x="{x:.0f}" y="{y:.0f}" text-anchor="middle">{esc(name.upper())}</text>')
    else:
        teile.append(f'<path class="karte__grenze" d="{P.pfad(GEO["land"])}"/>')

    if typ == "beitritt" or a.get("kuerzel") == "ja":
        bis = int(a.get("bis", "9999"))
        for k, ringe in GEO["kantone"].items():
            lon, lat = KANTON_LABEL.get(k) or schwerpunkt(ringe)
            x, y = P(lon, lat)
            dunkel = typ == "beitritt" and BEITRITT[k] <= min(bis, 1353)
            teile.append(f'<text class="karte__kuerzel{" karte__kuerzel--hell" if dunkel else ""}" '
                         f'x="{x:.0f}" y="{y + 5:.0f}" text-anchor="middle">{k}</text>')

    for r in re.findall(r"<route\s+([^>]*?)/?>", innen):
        ra = attrs(r)
        try:
            pts = [tuple(float(v) for v in p.split(",")) for p in ra.get("punkte", "").split()]
        except ValueError:
            FEHLER.append(f"{kapitel}: ungültige Route {ra}")
            continue
        d = P.pfad([pts], zu=False)
        pfeil = ' marker-end="url(#pfeil)"' if ra.get("art", "pfeil") == "pfeil" else ""
        teile.append(f'<path class="karte__routengrund" d="{d}"/><path class="karte__route"{pfeil} d="{d}"/>')
        if ra.get("name"):
            x, y = P(*pts[len(pts) // 2])
            teile.append(beschriftung(ra["name"], x, y, ra.get("pos", "e"), "karte__routenname", f))

    typen = []
    for o in re.findall(r"<ort\s+([^>]*?)/?>", innen):
        oa = attrs(o)
        try:
            x, y = P(float(oa["lon"]), float(oa["lat"]))
        except (KeyError, ValueError):
            FEHLER.append(f"{kapitel}: Ort ohne gültige Koordinaten {oa}")
            continue
        t = oa.get("typ", "ort")
        if t not in SYMBOLE:
            FEHLER.append(f"{kapitel}: unbekannter Ortstyp {t}")
        typen.append(t)
        name = oa.get("name", "") + (f" {oa['jahr']}" if oa.get("jahr") else "")
        teile.append(symbol(t, x, y, f))
        teile.append(beschriftung(name, x, y, oa.get("pos", "e"), f=f))

    text = re.sub(r"<(ort|route)\s+[^>]*?/?>", "", innen).strip()
    if typ == "beitritt":
        bis = int(a.get("bis", "9999"))
        legende += [(f, t) for j, f, t in EPOCHEN if j <= bis]
    legende += [(f"{f};opacity:.5", n) for _, f, n in gruppen if n]
    swatches = "".join(f'<li><span class="swatch" style="background:{f}"></span>{esc(t)}</li>' for f, t in legende)
    swatches += "".join(f'<li><svg viewBox="-12 -12 24 24" class="sym-legende">{symbol(t)}</svg>{SYMBOLE[t]}</li>'
                        for t in dict.fromkeys(typen) if t in SYMBOLE)
    titel = f'<span class="fig__titel">{esc(a["titel"])}</span> ' if a.get("titel") else ""
    quelle = GEO["quelle"]["region" if typ == "region" else "schweiz"]
    return (
        f'<figure class="fig karte fig--{esc(lage)}">'
        f'<svg class="karte__svg{" karte--klein" if lage == "spalte" else ""}" viewBox="0 0 {P.w} {P.h}" '
        f'role="img" aria-label="{esc(a.get("titel", "Karte"))}">'
        '<defs><marker id="pfeil" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="5" markerHeight="5" '
        'orient="auto-start-reverse"><path d="M0,0L10,5L0,10Z" class="karte__pfeilspitze"/></marker></defs>'
        + "".join(teile) +
        '</svg><figcaption>'
        + (f'<ul class="karte__legende">{swatches}</ul>' if swatches else "")
        + f'<p>{titel}{text}</p><p class="fig__nachweis">Karte: eigene Darstellung · {esc(quelle)}</p>'
        '</figcaption></figure>'
    )


# --------------------------------------------------------------- Kapitel ---

def lade_kapitel():
    kapitel = []
    for datei in sorted((SRC / "kapitel").glob("[0-9][0-9]*-*.html")):
        roh = datei.read_text()
        m = re.search(r"<!--meta\s*(\{.*?\})\s*-->", roh, re.S)
        if not m:
            FEHLER.append(f"{datei.name}: Meta-Block fehlt")
            continue
        try:
            meta = json.loads(m.group(1))
        except json.JSONDecodeError as e:
            FEHLER.append(f"{datei.name}: Meta-Block ist kein gültiges JSON ({e})")
            continue
        meta["datei"] = datei
        meta["inhalt"] = roh[m.end():]
        if "code" in meta:
            code, art, nach = meta["code"], meta.get("art"), meta.get("nach")
            if art not in ARTEN or not isinstance(nach, int) or not re.fullmatch(f"{nach:02d}[a-z]", code):
                FEHLER.append(f"{datei.name}: Zwischenkapitel braucht art ({'/'.join(ARTEN)}), nach (Zahl) "
                              f"und code wie «{nach}a»")
                continue
            meta["html"] = f"{code}-{meta['slug']}.html"
            meta["schluessel"] = code
            meta["label"] = ARTEN[art][0]
            meta["ordnung"] = (nach, code[-1])
        else:
            meta["html"] = f"{meta['nr']:02d}-{meta['slug']}.html"
            meta["schluessel"] = str(meta["nr"])
            meta["label"] = f"Kapitel {meta['nr']}"
            meta["ordnung"] = (meta["nr"], "")
        kapitel.append(meta)
    kapitel.sort(key=lambda k: k["ordnung"])
    return kapitel


def hauptkapitel(kapitel):
    return [k for k in kapitel if "nr" in k]


def seitenname(k):
    return k["label"] if "nr" in k else k["titel"]


def kurzname(k):
    """«12 · Titel» für Hauptkapitel, «Nebengeschichte · Titel» für Zwischenkapitel."""
    return f"{k['nr'] if 'nr' in k else k['label']} · {k['titel']}"


def expandiere(text, root, bilder, verwendet, name):
    text = re.sub(r"<bild\s+([^>]*)>(.*?)</bild>",
                  lambda m: render_bild(attrs(m.group(1)), m.group(2), root, bilder, verwendet, name), text, flags=re.S)
    text = re.sub(r"<karte\s+([^>]*)>(.*?)</karte>",
                  lambda m: render_karte(attrs(m.group(1)), m.group(2), name), text, flags=re.S)
    return text


SCHRIFTEN = ("https://fonts.googleapis.com/css2?family=Cinzel+Decorative:wght@700&"
             "family=EB+Garamond:ital,wght@0,400..700;1,400..600&"
             "family=IM+Fell+English:ital@0;1&family=IM+Fell+English+SC&display=swap")

# ------------------------------------------------------------ Aquarelle ---

AQUARELLE = {}   # "6" / "start" / "anhang" → Bild-IDs aus src/aquarelle.json
AQ_VERWENDET = {}  # Bild-ID → Liste der Seiten, auf denen es als Hintergrund dient


def lade_aquarelle(bilder):
    datei = SRC / "aquarelle.json"
    zuordnung = json.loads(datei.read_text()) if datei.exists() else {}
    zuordnung.pop("_info", None)
    for schluessel, ids in zuordnung.items():
        for bid in ids:
            if bid not in bilder:
                FEHLER.append(f"aquarelle.json ({schluessel}): unbekanntes Aquarell «{bid}»")
    AQUARELLE.update({k: [b for b in v if b in bilder] for k, v in zuordnung.items()})


def aquarell_url(schluessel, nr, root, seite_name):
    """URL des nr-ten Aquarells (zyklisch) für diesen Schlüssel; merkt sich die Verwendung."""
    ids = AQUARELLE.get(schluessel) or AQUARELLE.get("anhang") or []
    if not ids:
        return ""
    bid = ids[nr % len(ids)]
    AQ_VERWENDET.setdefault(bid, [])
    if seite_name not in AQ_VERWENDET[bid]:
        AQ_VERWENDET[bid].append(seite_name)
    return f"url({root}img/{bid}.jpg)"


def aquarell(schluessel, nr, root, seite_name):
    """style-Attribut mit einem einzelnen Aquarell (Kapitelkopf, Titelseite)."""
    url = aquarell_url(schluessel, nr, root, seite_name)
    return f' style="--aquarell:{url}"' if url else ""


def ebenen(schluessel, zaehler, n, root, seite_name):
    """n Aquarell-Ebenen, die einen Textblock von oben nach unten überlappend ausfüllen."""
    return "".join(f'<div class="aq" aria-hidden="true" style="--i:{i};--n:{n};'
                   f'--aquarell:{aquarell_url(schluessel, next(zaehler), root, seite_name)}"></div>'
                   for i in range(n)) if AQUARELLE else ""


def anzahl_ebenen(html):
    """Etwa eine Landschaft pro Bildschirmhöhe: geschätzt aus Text, Bildern und Kästen."""
    woerter = len(re.sub(r"<[^>]+>", " ", html).split())
    return max(1, min(8, round(woerter / 260 + html.count("<figure") * 0.6)))


def hinterlege(html, schluessel, root, seite_name, start=1):
    """Hinterlegt Einleitung und jeden schlichten <section> mit farbigen Aquarell-Landschaften."""
    zaehler = itertools.count(start)
    html = re.sub(r'<p class="lead">.*?</p>', lambda m: f'<div class="einleitung mit-aq">'
                  f'{ebenen(schluessel, zaehler, 1, root, seite_name)}{m.group(0)}</div>', html, count=1, flags=re.S)
    return re.sub(r"<section>(.*?)</section>", lambda m: f'<section class="mit-aq">'
                  f'{ebenen(schluessel, zaehler, anzahl_ebenen(m.group(1)), root, seite_name)}{m.group(1)}</section>',
                  html, flags=re.S)


def seite(titel, inhalt, root, teil=None, prev=None, next=None, beschreibung="", fortschritt=None, klasse=""):
    farbe = TEILE[teil][3] if teil else "#b0282e"
    teil_txt = f'<span class="leiste__teil">Teil {TEILE[teil][0]} · {esc(TEILE[teil][1])}</span>' if teil else ""
    links = ""
    if prev:
        links += f'<link rel="prev" href="{prev[0]}">'
    if next:
        links += f'<link rel="next" href="{next[0]}">'
    balken = f'<div class="leiste__fortschritt"><span style="width:{fortschritt:.1f}%"></span></div>' if fortschritt is not None else ""
    blaettern = ""
    if prev or next:
        blaettern = '<nav class="blaettern" aria-label="Blättern">'
        blaettern += (f'<a class="blaettern__zurueck" href="{prev[0]}"><span>← Zurück</span>{esc(prev[1])}</a>'
                      if prev else "<span></span>")
        blaettern += (f'<a class="blaettern__weiter" href="{next[0]}"><span>Weiter →</span>{esc(next[1])}</a>'
                      if next else "<span></span>")
        blaettern += "</nav>"
    return f"""<!doctype html>
<html lang="de-CH">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(titel)}{' – ' + BUCH if titel != BUCH else ''}</title>
<meta name="description" content="{esc(beschreibung or UNTERTITEL)}">
<meta property="og:title" content="{esc(titel)}">
<meta property="og:description" content="{esc(beschreibung or UNTERTITEL)}">
<meta name="theme-color" content="{farbe}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="{SCHRIFTEN}">
<link rel="stylesheet" href="{root}assets/buch.css">
<link rel="icon" href="{root}assets/icon.svg" type="image/svg+xml">
{links}
</head>
<body class="{klasse}" style="--teil:{farbe}">
<a class="sprung" href="#inhalt">Zum Inhalt</a>
<header class="leiste">
<a class="leiste__buch" href="{root}index.html">{BUCH}</a>
{teil_txt}
<nav class="leiste__nav"><a href="{root}index.html#inhaltsverzeichnis">Inhalt</a><a href="{root}zeitleiste.html">Zeitleiste</a><a href="{root}ueber.html">Über das Buch</a></nav>
{balken}
</header>
<main id="inhalt">
{inhalt}
</main>
{blaettern}
<footer class="fuss">
<p>{BUCH} · Texte CC BY-SA 4.0 · Bilder gemäss <a href="{root}bildnachweis.html">Bildnachweis</a> · <a href="{REPO}">Quelltext auf GitHub</a></p>
</footer>
<script src="{root}assets/buch.js" defer></script>
</body>
</html>
"""


def kopf(k, bilder, verwendet):
    rom, teilname, _, _ = TEILE[k["teil"]]
    bild = ""
    if k.get("held") in bilder:
        m = bilder[k["held"]]
        verwendet.setdefault(k["held"], k.get("held_titel", k["titel"]))
        unter = f'<figcaption>{k.get("held_legende", "")} <span class="fig__nachweis">{nachweis_zeile(m)}</span></figcaption>'
        bild = (f'<figure class="kopf__bild"><a class="fig__link" href="../img/{k["held"]}.jpg">'
                f'<img src="../img/{k["held"]}.jpg" width="{m["breite"]}" height="{m["hoehe"]}" '
                f'style="object-position:{esc(k.get("held_pos", "50% 35%"))}" '
                f'alt="{esc(k.get("held_titel", k["titel"]))}" fetchpriority="high"></a>{unter}</figure>')
    elif k.get("held"):
        FEHLER.append(f"{k['html']}: Titelbild «{k['held']}» fehlt")
    stil = aquarell(k["schluessel"], 0, "../", seitenname(k))
    if "nr" in k:
        nummer = f'<p class="kopf__nr"><span>Kapitel</span> {k["nr"]}</p>'
        hinweis = ""
    else:
        nummer = f'<p class="kopf__nr kopf__nr--art"><span>{esc(k["label"])}</span>❦</p>'
        hinweis = f'<p class="kopf__art">{esc(ARTEN[k["art"]][1])}</p>'
    return f"""<header class="kopf aquarell"{stil}>
<div class="kopf__text">
<p class="kopf__teil">Teil {rom} · {esc(teilname)}</p>
{nummer}
<h1>{esc(k['titel'])}</h1>
<p class="kopf__jahre">{esc(k.get('jahre', ''))}</p>
<p class="kopf__unter">{esc(k.get('untertitel', ''))}</p>
{hinweis}
</div>
{bild}
</header>"""


def baue_kapitel(kapitel, bilder):
    verwendet_alle = {}
    for i, k in enumerate(kapitel):
        verwendet = {}
        prev = (kapitel[i - 1]["html"], kurzname(kapitel[i - 1])) if i else ("../index.html", "Inhalt")
        nxt = (kapitel[i + 1]["html"], kurzname(kapitel[i + 1])) if i + 1 < len(kapitel) else ("../zeitleiste.html", "Zeitleiste")
        koerper = expandiere(k["inhalt"], "../", bilder, verwendet, k["html"])
        koerper = hinterlege(koerper, k["schluessel"], "../", seitenname(k))
        inhalt = f'<article class="kapitel">\n{kopf(k, bilder, verwendet)}\n{koerper}\n</article>'
        (DOCS / "kapitel" / k["html"]).write_text(seite(
            k["titel"], inhalt, "../", teil=k["teil"], prev=prev, next=nxt,
            beschreibung=k.get("kurz", ""), fortschritt=100 * (i + 1) / len(kapitel),
            klasse=f"art-{k['art']}" if "art" in k else ""))
        verwendet_alle[k["html"]] = verwendet
        k["woerter"] = len(re.sub(r"<[^>]+>", " ", koerper).split())
        k["bilder"] = len(verwendet)
        k["karten"] = koerper.count('class="fig karte')
    return verwendet_alle


def baue_startseite(kapitel, bilder):
    vorwort = expandiere((SRC / "seiten" / "vorwort.html").read_text(), "", bilder, {}, "vorwort")
    toc = []
    for t, (rom, name, jahre, farbe) in TEILE.items():
        ks = [k for k in kapitel if k["teil"] == t]
        if not ks:
            continue
        items = []
        for k in ks:
            thumb = (f'<img src="img/{k["held"]}.jpg" alt="" loading="lazy" '
                     f'width="{bilder[k["held"]]["breite"]}" height="{bilder[k["held"]]["hoehe"]}">'
                     if k.get("held") in bilder else "")
            if "nr" in k:
                nummer, zeit, art = k["nr"], esc(k.get("jahre", "")), ""
            else:
                nummer, art = "❦", f' class="toc--art toc--{k["art"]}"'
                zeit = f'<em>{esc(k["label"])}</em> · {esc(k.get("jahre", ""))}'
            items.append(f'<li{art}><a href="kapitel/{k["html"]}"><span class="toc__bild">{thumb}</span>'
                         f'<span class="toc__nr">{nummer}</span><span class="toc__titel">{esc(k["titel"])}</span>'
                         f'<span class="toc__jahre">{zeit}</span>'
                         f'<span class="toc__kurz">{esc(k.get("kurz", ""))}</span></a></li>')
        toc.append(f'<section class="toc__teil" style="--teil:{farbe}"><h3><span>Teil {rom}</span> {esc(name)}'
                   f' <small>{esc(jahre)}</small></h3><ol>{"".join(items)}</ol></section>')
    titelbild = next((k["held"] for k in kapitel if k.get("nr") == 6 and k.get("held") in bilder), None)
    cover_bild = ""
    if titelbild:
        m = bilder[titelbild]
        cover_bild = f'<img src="img/{titelbild}.jpg" width="{m["breite"]}" height="{m["hoehe"]}" alt="">'
    zaehler = itertools.count(1)
    inhalt = f"""<section class="cover"{aquarell("start", 0, "", "Startseite")}>
<div class="cover__bild">{cover_bild}</div>
<div class="cover__text">
<p class="cover__vor">Ein illustriertes Geschichtsbuch</p>
<h1>{BUCH}</h1>
<p class="cover__unter">{UNTERTITEL}</p>
<p class="cover__info">{len(hauptkapitel(kapitel))} Kapitel · {len(kapitel) - len(hauptkapitel(kapitel))} Zwischenkapitel · {sum(k['bilder'] for k in kapitel)} Bilder · {sum(k['karten'] for k in kapitel)} Karten</p>
<a class="knopf" href="kapitel/{kapitel[0]['html'] if kapitel else ''}">Mit dem Lesen beginnen →</a>
</div>
</section>
<section class="vorwort mit-aq">{ebenen("start", zaehler, 2, "", "Startseite")}{vorwort}</section>
<section class="toc mit-aq" id="inhaltsverzeichnis">{ebenen("start", zaehler, max(2, len(kapitel) // 4), "", "Startseite")}<h2>Inhalt</h2>{''.join(toc)}
<ul class="toc__anhang"><li><a href="zeitleiste.html">Zeitleiste: 2000 Jahre auf einen Blick</a></li>
<li><a href="ueber.html">Über dieses Buch: Methode und Quellen</a></li>
<li><a href="bildnachweis.html">Bildnachweis</a></li></ul></section>"""
    nxt = (f"kapitel/{kapitel[0]['html']}", kurzname(kapitel[0])) if kapitel else None
    (DOCS / "index.html").write_text(seite(BUCH, inhalt, "", next=nxt, klasse="startseite"))


def baue_zeitleiste(kapitel):
    zeilen = []
    for k in kapitel:
        farbe = TEILE[k["teil"]][3]
        for jahr, text in k.get("ereignisse", []):
            zeilen.append(f'<li style="--teil:{farbe}"><time>{esc(jahr)}</time>'
                          f'<p>{esc(text)} <a href="kapitel/{k["html"]}">{esc(k["label"])}</a></p></li>')
    inhalt = f"""<article class="kapitel anhang">
<header class="anhang__kopf aquarell"{aquarell("anhang", 0, "", "Zeitleiste")}><p class="kopf__teil">Anhang</p><h1>Zeitleiste</h1>
<p class="lead">Die wichtigsten Ereignisse aus zweitausend Jahren Schweizer Geschichte – jeder Eintrag führt zum Kapitel, in dem er ausführlich erzählt wird.</p></header>
<div class="mit-aq">{ebenen("anhang", itertools.count(1), max(1, len(zeilen) // 14), "", "Zeitleiste")}
<ol class="grosse-zeitleiste">{''.join(zeilen)}</ol></div></article>"""
    prev = (f"kapitel/{kapitel[-1]['html']}", kapitel[-1]["titel"]) if kapitel else None
    (DOCS / "zeitleiste.html").write_text(seite("Zeitleiste", inhalt, "", prev=prev, next=("ueber.html", "Über dieses Buch")))


def baue_ueber(bilder):
    roh = (SRC / "seiten" / "ueber.html").read_text()
    roh = roh.replace('<header class="anhang__kopf">',
                      f'<header class="anhang__kopf aquarell"{aquarell("anhang", 0, "", "Über dieses Buch")}>')
    roh = hinterlege(expandiere(roh, "", bilder, {}, "ueber"), "anhang", "", "Über dieses Buch")
    inhalt = f'<article class="kapitel anhang">{roh}</article>'
    (DOCS / "ueber.html").write_text(seite("Über dieses Buch", inhalt, "", prev=("zeitleiste.html", "Zeitleiste"),
                                           next=("bildnachweis.html", "Bildnachweis")))


def baue_bildnachweis(kapitel, bilder, verwendet):
    abschnitte = []
    for k in kapitel:
        zeilen = []
        for bid, titel in verwendet.get(k["html"], {}).items():
            m = bilder[bid]
            datum = f", {esc(m['datum'])}" if m.get("datum") else ""
            zeilen.append(f'<li><a class="nachweis__bild" href="img/{bid}.jpg"><img src="img/{bid}.jpg" alt="" loading="lazy"></a>'
                          f'<div><b>{esc(titel or m["datei"])}</b><br>{esc(kuenstler(m))}{datum}<br>'
                          f'<span class="nachweis__lizenz">{nachweis_zeile(m)}</span><br>'
                          f'<small>Datei: {esc(m["datei"])}</small></div></li>')
        if zeilen:
            abschnitte.append(f'<section><h2>{esc(kurzname(k) if "nr" not in k else "Kapitel " + kurzname(k))}</h2>'
                              f'<ul class="nachweis">{"".join(zeilen)}</ul></section>')
    zeilen = []
    for bid, seiten in sorted(AQ_VERWENDET.items()):
        m = bilder[bid]
        zeilen.append(f'<li><a class="nachweis__bild" href="img/{bid}.jpg"><img src="img/{bid}.jpg" alt="" loading="lazy"></a>'
                      f'<div><b>{esc(m["beschreibung"][:90] or m["datei"])}</b><br>{esc(kuenstler(m))}<br>'
                      f'<span class="nachweis__lizenz">{nachweis_zeile(m)}</span><br>'
                      f'<small>Hintergrund in: {esc(", ".join(seiten))}</small></div></li>')
    if zeilen:
        abschnitte.append('<section><h2>Aquarelle im Hintergrund</h2><p>Die zart eingeblendeten Landschaften hinter den '
                          'Texten sind Aquarelle und kolorierte Ansichten von William Turner, John Ruskin und Schweizer '
                          f'«Kleinmeistern» des 18. und 19. Jahrhunderts.</p><ul class="nachweis">{"".join(zeilen)}</ul></section>')
    inhalt = f"""<article class="kapitel anhang">
<header class="anhang__kopf aquarell"{aquarell("anhang", 0, "", "Bildnachweis")}><p class="kopf__teil">Anhang</p><h1>Bildnachweis</h1>
<p class="lead">Alle Gemälde, Chronik-Illustrationen und Fotografien stammen von Wikimedia Commons und sind gemeinfrei
oder unter freien Lizenzen veröffentlicht. Ein Klick auf «Wikimedia Commons» führt jeweils zur Originaldatei mit allen Angaben.
Die Karten sind eigene Darstellungen auf Grundlage offener Geodaten (Bundesamt für Statistik/swisstopo über
<a href="https://github.com/interactivethings/swiss-maps">swiss-maps</a>; <a href="https://www.naturalearthdata.com/">Natural Earth</a>).</p></header>
{hinterlege(''.join(abschnitte), "anhang", "", "Bildnachweis")}</article>"""
    (DOCS / "bildnachweis.html").write_text(seite("Bildnachweis", inhalt, "", prev=("ueber.html", "Über dieses Buch")))


def main():
    for d in ("kapitel", "img", "assets"):
        (DOCS / d).mkdir(parents=True, exist_ok=True)
    bilder = lade_bilder()
    lade_aquarelle(bilder)
    kapitel = lade_kapitel()
    nummern = [k["schluessel"] for k in kapitel]
    if len(set(nummern)) != len(nummern):
        FEHLER.append(f"Kapitelnummern doppelt: {nummern}")
    for alt in (DOCS / "kapitel").glob("*.html"):
        if alt.name not in {k["html"] for k in kapitel}:
            alt.unlink()
    verwendet = baue_kapitel(kapitel, bilder)
    baue_startseite(kapitel, bilder)
    baue_zeitleiste(kapitel)
    baue_ueber(bilder)
    baue_bildnachweis(kapitel, bilder, verwendet)
    (DOCS / ".nojekyll").write_text("")

    print(f"{'Kapitel':<44} {'Wörter':>7} {'Bilder':>6} {'Karten':>6}")
    for k in kapitel:
        print(f"{k['schluessel']:>3} {k['titel'][:40]:<41} {k['woerter']:>6} {k['bilder']:>6} {k['karten']:>6}")
    print(f"{'Total':<44} {sum(k['woerter'] for k in kapitel):>7} {sum(k['bilder'] for k in kapitel):>6} "
          f"{sum(k['karten'] for k in kapitel):>6}")
    ungenutzt = set(bilder) - {b for v in verwendet.values() for b in v} - set(AQ_VERWENDET)
    if ungenutzt:
        print("Geladen, aber nicht verwendet:", ", ".join(sorted(ungenutzt)))
    if FEHLER:
        print("\nFEHLER:")
        for f in FEHLER:
            print("  –", f)
        sys.exit(1)


if __name__ == "__main__":
    main()
