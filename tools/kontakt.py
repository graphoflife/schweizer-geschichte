#!/usr/bin/env python3
"""Erstellt einen Kontaktbogen aller Bilder einer Liste, um sie mit einem Blick zu prüfen.

  python3 -I tools/kontakt.py src/bilder/07.json /pfad/zum/bogen.jpg
"""
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent


def main(liste, ziel, hoehe=330, breite=1500):
    bilder = []
    for e in json.loads(Path(liste).read_text()):
        datei = ROOT / "docs" / "img" / f"{e['id']}.jpg"
        if datei.exists():
            im = Image.open(datei).convert("RGB")
            im = im.resize((max(1, round(im.width * hoehe / im.height)), hoehe))
            bilder.append((e["id"], im))
    zeilen, zeile, x = [], [], 0
    for bid, im in bilder:
        if zeile and x + im.width > breite:
            zeilen.append(zeile)
            zeile, x = [], 0
        zeile.append((bid, im))
        x += im.width + 10
    if zeile:
        zeilen.append(zeile)
    bogen = Image.new("RGB", (breite, max(1, len(zeilen)) * (hoehe + 34)), "white")
    zeichnen = ImageDraw.Draw(bogen)
    for r, zeile in enumerate(zeilen):
        x = 0
        for bid, im in zeile:
            y = r * (hoehe + 34)
            bogen.paste(im, (x, y))
            zeichnen.text((x + 2, y + hoehe + 4), bid, fill="black")
            x += im.width + 10
    bogen.save(ziel, quality=78)
    print(f"{len(bilder)} Bilder → {ziel}")


if __name__ == "__main__":
    main(*sys.argv[1:3])
