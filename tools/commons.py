#!/usr/bin/env python3
"""Hilfswerkzeug zum Finden von Bildern auf Wikimedia Commons.

  python3 -I tools/commons.py suche "Schlacht bei Morgarten"     Volltextsuche nach Dateien
  python3 -I tools/commons.py kategorie "Karl Jauslin"            Dateien einer Kategorie
  python3 -I tools/commons.py info "Datei.jpg" ["Datei2.jpg" …]  Lizenz, Grösse, Urheber prüfen

Jede Zeile zeigt: Lizenz | Breite×Höhe | Dateiname | Urheber/Datum.
"""
import json
import sys
import urllib.parse

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from bilder import ERLAUBT, hole, text  # noqa: E402


def api(**p):
    p["format"] = "json"
    return json.loads(hole("https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(p)))


def zeige(seiten):
    for s in seiten:
        ii = (s.get("imageinfo") or [{}])[0]
        em = {k: v.get("value", "") for k, v in ii.get("extmetadata", {}).items()}
        lizenz = text(em.get("LicenseShortName")) or "?"
        frei = "  " if ERLAUBT.search(lizenz) else "✗ "
        titel = s["title"].removeprefix("File:")
        print(f"{frei}{lizenz[:18]:<18} | {ii.get('width', '?')}×{ii.get('height', '?')} | {titel} | "
              f"{text(em.get('Artist'), 50)} {text(em.get('DateTimeOriginal'), 25)}")


def mit_info(**gen):
    r = api(action="query", prop="imageinfo", iiprop="size|extmetadata", **gen)
    seiten = sorted(r.get("query", {}).get("pages", {}).values(), key=lambda s: s.get("index", 0))
    zeige(seiten)


def main(befehl, *args):
    if befehl == "suche":
        mit_info(generator="search", gsrnamespace=6, gsrsearch=" ".join(args), gsrlimit=30)
    elif befehl == "kategorie":
        mit_info(generator="categorymembers", gcmtitle="Category:" + " ".join(args),
                 gcmtype="file", gcmlimit=100)
    elif befehl == "info":
        mit_info(titles="|".join("File:" + a for a in args))
    else:
        print(__doc__)


if __name__ == "__main__":
    main(*(sys.argv[1:] or ["hilfe"]))
