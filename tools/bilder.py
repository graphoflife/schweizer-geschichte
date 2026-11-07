#!/usr/bin/env python3
"""Lädt die Bilder des Buchs von Wikimedia Commons und speichert den Bildnachweis.

Aufruf:  python3 -I tools/bilder.py [src/bilder/06.json ...]   (ohne Argument: alle Listen)

Eine Bildliste (src/bilder/NN.json) ist ein Array von Einträgen:
  {"id": "k06-bundesbrief", "datei": "Bundesbrief.jpg"}
optional: "breite": 1280 (Standard), "zuschnitt": [links, oben, rechts, unten] in Prozent.

Ergebnis: docs/img/<id>.jpg und der Nachweis in src/bilder/nachweis/NN.json
(eine Nachweisdatei pro Liste, damit mehrere Listen gleichzeitig geladen werden können).
Nur gemeinfreie oder frei lizenzierte Bilder (PD, CC0, CC BY, CC BY-SA) werden übernommen.
"""
import html
import io
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
LISTEN = ROOT / "src" / "bilder"
NACHWEIS = LISTEN / "nachweis"
ZIEL = ROOT / "docs" / "img"
UA = {"User-Agent": "SchweizerGeschichteBuch/1.0 (https://github.com/graphoflife/schweizer-geschichte)"}
ERLAUBT = re.compile(r"^(public domain|pd|cc0|cc[ -]by)", re.I)
MAX_KANTE = 1400


def hole(url, versuche=4):
    for i in range(versuche):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (429, 503) and i < versuche - 1:
                time.sleep(5 * (i + 1))
                continue
            raise


def text(wert, laenge=None):
    """HTML aus den Commons-Metadaten in schlichten Text verwandeln."""
    t = re.sub(r'<span style="display: none;">.*?</span>', "", wert or "", flags=re.S)
    t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r"\s+", " ", html.unescape(t)).strip()
    if laenge and len(t) > laenge:
        t = t[: laenge - 1].rsplit(" ", 1)[0] + " …"
    return t


def info(datei, breite):
    q = urllib.parse.urlencode({
        "action": "query", "format": "json", "titles": "File:" + datei, "prop": "imageinfo",
        "iiprop": "url|extmetadata|size|mime", "iiurlwidth": breite,
    })
    daten = json.loads(hole("https://commons.wikimedia.org/w/api.php?" + q))
    seite = next(iter(daten["query"]["pages"].values()))
    if "imageinfo" not in seite:
        raise LookupError(f"Datei nicht gefunden: {datei}")
    return seite["imageinfo"][0]


def verarbeite(eintrag, meta):
    bid, datei = eintrag["id"], eintrag["datei"]
    ziel = ZIEL / f"{bid}.jpg"
    if ziel.exists() and meta.get(bid, {}).get("datei") == datei and \
            meta[bid].get("zuschnitt") == eintrag.get("zuschnitt"):
        return "vorhanden"
    ii = info(datei, eintrag.get("breite", 1280))
    em = {k: v.get("value", "") for k, v in ii.get("extmetadata", {}).items()}
    lizenz = text(em.get("LicenseShortName")) or "unbekannt"
    if not ERLAUBT.search(lizenz):
        raise PermissionError(f"Lizenz nicht frei genug: {datei} ({lizenz})")

    bild = Image.open(io.BytesIO(hole(ii.get("thumburl") or ii["url"])))
    if bild.mode in ("RGBA", "LA", "P"):
        bild = bild.convert("RGBA")
        grund = Image.new("RGB", bild.size, "white")
        grund.paste(bild, mask=bild.split()[-1])
        bild = grund
    bild = bild.convert("RGB")
    if eintrag.get("zuschnitt"):
        l, o, r, u = eintrag["zuschnitt"]
        w, h = bild.size
        bild = bild.crop((round(w * l / 100), round(h * o / 100), round(w * r / 100), round(h * u / 100)))
    bild.thumbnail((MAX_KANTE, MAX_KANTE), Image.LANCZOS)
    ZIEL.mkdir(parents=True, exist_ok=True)
    bild.save(ziel, "JPEG", quality=78, optimize=True, progressive=True)

    meta[bid] = {
        "datei": datei,
        "seite": ii.get("descriptionurl"),
        "kuenstler": text(em.get("Artist"), 160) or "unbekannt",
        "datum": text(em.get("DateTimeOriginal"), 60),
        "lizenz": lizenz,
        "lizenz_url": em.get("LicenseUrl", ""),
        "beschreibung": text(em.get("ImageDescription"), 300),
        "breite": bild.size[0],
        "hoehe": bild.size[1],
        "zuschnitt": eintrag.get("zuschnitt"),
    }
    return f"geladen {bild.size[0]}×{bild.size[1]} · {lizenz} · {meta[bid]['kuenstler'][:50]}"


def main(listen):
    fehler = 0
    NACHWEIS.mkdir(parents=True, exist_ok=True)
    for liste in listen or sorted(LISTEN.glob("*.json")):
        liste = Path(liste)
        datei = NACHWEIS / liste.name
        meta = json.loads(datei.read_text()) if datei.exists() else {}
        eintraege = json.loads(liste.read_text())
        for alt in set(meta) - {e["id"] for e in eintraege}:
            del meta[alt]
        for eintrag in eintraege:
            try:
                status = verarbeite(eintrag, meta)
            except Exception as e:  # noqa: BLE001 – jede Störung melden, weitermachen
                status, fehler = f"FEHLER: {e}", fehler + 1
            print(f"{eintrag['id']:<32} {status}")
            datei.write_text(json.dumps(meta, ensure_ascii=False, indent=1, sort_keys=True))
            if not status == "vorhanden":
                time.sleep(0.4)
    sys.exit(1 if fehler else 0)


if __name__ == "__main__":
    main(sys.argv[1:])
