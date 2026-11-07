#!/usr/bin/env python3
"""Bereitet Geodaten für die Buchkarten vor (einmalig auszuführen).

Eingaben (Verzeichnis als Argument):
  ch-combined.json                    swiss-maps 4.5.0, Stand 2024 (BFS/swisstopo, via interactivethings)
  ne_50m_admin_0_countries.geojson    Natural Earth (gemeinfrei)
  ne_10m_rivers_lake_centerlines.geojson, ne_10m_rivers_europe.geojson
  ne_10m_lakes.geojson, ne_10m_lakes_europe.geojson

Ausgabe: src/karten/geo.json – vereinfachte Linien in Längen-/Breitengraden.
"""
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGION = (2.5, 43.8, 13.5, 50.2)  # lon_min, lat_min, lon_max, lat_max

KANTONE = {
    1: "ZH", 2: "BE", 3: "LU", 4: "UR", 5: "SZ", 6: "OW", 7: "NW", 8: "GL", 9: "ZG",
    10: "FR", 11: "SO", 12: "BS", 13: "BL", 14: "SH", 15: "AR", 16: "AI", 17: "SG",
    18: "GR", 19: "AG", 20: "TG", 21: "TI", 22: "VD", 23: "VS", 24: "NE", 25: "GE", 26: "JU",
}

FLUESSE = {
    "Rhein": "Rhein", "Rhine": "Rhein", "Rhin": "Rhein", "Rhône": "Rhone", "Rhne": "Rhone",
    "Aare": "Aare", "Reuss": "Reuss", "Limmat": "Limmat", "Inn": "Inn", "Ticino": "Tessin",
    "Po": "Po", "Donau": "Donau", "Doubs": "Doubs", "Saône": "Saône", "Sane": "Saône",
    "Thielle": "Zihl", "Adda": "Adda", "Adige": "Etsch", "Mincio": "Mincio", "Ill": "Ill",
    "Neckar": "Neckar", "Mosel": "Mosel", "Dora Baltea": "Dora Baltea", "Isar": "Isar",
}


def perp_dist(p, a, b):
    (x, y), (x1, y1), (x2, y2) = p, a, b
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(x - x1, y - y1)
    t = max(0, min(1, ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)))
    return math.hypot(x - (x1 + t * dx), y - (y1 + t * dy))


def simplify(pts, tol):
    """Douglas-Peucker, iterativ; x wird mit cos(Breite) gestaucht."""
    if len(pts) < 3:
        return pts
    k = math.cos(math.radians(46.8))
    proj = [(p[0] * k, p[1]) for p in pts]
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        s, e = stack.pop()
        dmax, idx = 0, -1
        for i in range(s + 1, e):
            d = perp_dist(proj[i], proj[s], proj[e])
            if d > dmax:
                dmax, idx = d, i
        if dmax > tol and idx > 0:
            keep[idx] = True
            stack += [(s, idx), (idx, e)]
    return [p for p, kp in zip(pts, keep) if kp]


def rnd(pts, nd=4):
    return [[round(x, nd), round(y, nd)] for x, y in pts]


def topo_arcs(topo):
    sx, sy = topo["transform"]["scale"]
    tx, ty = topo["transform"]["translate"]
    arcs = []
    for arc in topo["arcs"]:
        x = y = 0
        pts = []
        for dx, dy in arc:
            x += dx
            y += dy
            pts.append((x * sx + tx, y * sy + ty))
        arcs.append(pts)
    return arcs


def ring_from_arcs(idxs, arcs):
    ring = []
    for i in idxs:
        a = arcs[i] if i >= 0 else list(reversed(arcs[~i]))
        ring.extend(a if not ring else a[1:])
    return ring


def topo_polys(geom, arcs):
    if geom["type"] == "Polygon":
        return [[ring_from_arcs(r, arcs) for r in geom["arcs"]]]
    if geom["type"] == "MultiPolygon":
        return [[ring_from_arcs(r, arcs) for r in poly] for poly in geom["arcs"]]
    return []


def rings(polys, tol):
    out = []
    for poly in polys:
        for r in poly:
            s = simplify(r, tol)
            if len(s) >= 4:
                out.append(rnd(s))
    return out


def in_region(pt, pad=0.0):
    return REGION[0] - pad <= pt[0] <= REGION[2] + pad and REGION[1] - pad <= pt[1] <= REGION[3] + pad


def geo_lines(g):
    t, c = g["type"], g["coordinates"]
    if t == "LineString":
        return [c]
    if t == "MultiLineString":
        return c
    if t == "Polygon":
        return c
    if t == "MultiPolygon":
        return [r for p in c for r in p]
    return []


def clip_line(line):
    """Teilt Linien an der Regionsgrenze (grob, genügt für Flüsse)."""
    segs, cur = [], []
    for p in line:
        if in_region(p, 0.3):
            cur.append(p)
        elif cur:
            segs.append(cur)
            cur = []
    if cur:
        segs.append(cur)
    return [s for s in segs if len(s) > 1]


def main(src):
    src = Path(src)
    out = {"quelle": {
        "schweiz": "Kantone, Landesgrenze, Seen: swiss-maps 4.5.0 (Stand 2024), Basis BFS/swisstopo",
        "region": "Länder, Flüsse, Seen: Natural Earth (gemeinfrei)",
    }}

    topo = json.loads((src / "ch-combined.json").read_text())
    arcs = topo_arcs(topo)
    out["kantone"] = {
        KANTONE[g["id"]]: rings(topo_polys(g, arcs), 0.0012)
        for g in topo["objects"]["cantons"]["geometries"]
    }
    out["land"] = rings(topo_polys(topo["objects"]["country"]["geometries"][0], arcs), 0.0008)
    out["seen_ch"] = [r for g in topo["objects"]["lakes"]["geometries"]
                      for r in rings(topo_polys(g, arcs), 0.0008)]

    countries = json.loads((src / "ne_50m_admin_0_countries.geojson").read_text())
    out["laender"] = {}
    for f in countries["features"]:
        g = f["geometry"]
        rs = [r for r in geo_lines(g) if any(in_region(p, 2) for p in r)]
        if rs:
            name = f["properties"].get("NAME_DE") or f["properties"]["NAME"]
            out["laender"][name] = [rnd(simplify(r, 0.01)) for r in rs if len(r) > 3]

    out["seen"] = []
    for fn in ("ne_10m_lakes.geojson", "ne_10m_lakes_europe.geojson"):
        for f in json.loads((src / fn).read_text())["features"]:
            if not f["geometry"]:
                continue
            for r in geo_lines(f["geometry"]):
                if any(in_region(p) for p in r):
                    s = simplify(r, 0.002)
                    if len(s) >= 4:
                        out["seen"].append(rnd(s))

    out["fluesse"] = []
    for fn in ("ne_10m_rivers_lake_centerlines.geojson", "ne_10m_rivers_europe.geojson"):
        for f in json.loads((src / fn).read_text())["features"]:
            name = FLUESSE.get(f["properties"].get("name"))
            if not name or not f["geometry"]:
                continue
            for line in geo_lines(f["geometry"]):
                for seg in clip_line(line):
                    s = simplify(seg, 0.003)
                    if len(s) > 1:
                        out["fluesse"].append({"name": name, "pts": rnd(s)})

    dest = ROOT / "src" / "karten" / "geo.json"
    dest.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    print(f"{dest} geschrieben ({dest.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main(sys.argv[1])
