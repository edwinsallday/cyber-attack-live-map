"""One-off: build pipeline/countries.json (country name -> [lat, lon]) from the Natural Earth
borders the globe already uses. Each country is placed at the centre of its largest landmass.
Run again only if assets/countries-110m.json changes."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
topo = json.loads((ROOT / "assets" / "countries-110m.json").read_text(encoding="utf-8"))
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


def ring(idxs):
    out = []
    for i in idxs:
        pts = arcs[i] if i >= 0 else arcs[~i][::-1]
        out.extend(pts if not out else pts[1:])
    return out


def area_centroid(pts):
    a = cx = cy = 0.0
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        f = x0 * y1 - x1 * y0
        a += f
        cx += (x0 + x1) * f
        cy += (y0 + y1) * f
    if abs(a) < 1e-12:
        return 0.0, pts[0]
    return abs(a) / 2, (cx / (3 * a), cy / (3 * a))


out = {}
for g in topo["objects"]["countries"]["geometries"]:
    polys = g["arcs"] if g["type"] == "MultiPolygon" else [g["arcs"]]
    best = max((area_centroid(ring(p[0])) for p in polys), key=lambda t: t[0])
    lon, lat = best[1]
    out[g["properties"]["name"]] = [round(lat, 2), round(lon, 2)]

# Small states and territories that the 110m borders leave out.
out.update({
    "Russia": [60.0, 95.0], "Fiji": [-17.8, 178.0],   # their borders wrap past the date line
    "Singapore": [1.35, 103.82], "Hong Kong": [22.32, 114.17], "Macau": [22.2, 113.55], "Malta": [35.9, 14.45],
    "Bahrain": [26.07, 50.55], "Maldives": [4.18, 73.51], "Mauritius": [-20.25, 57.55], "Liechtenstein": [47.16, 9.55],
    "Monaco": [43.74, 7.42], "Andorra": [42.55, 1.6], "San Marino": [43.94, 12.46], "Barbados": [13.17, -59.55],
    "Seychelles": [-4.68, 55.48], "Bermuda": [32.31, -64.75], "Cayman Islands": [19.31, -81.25], "Guam": [13.44, 144.79],
    "Samoa": [-13.76, -172.1], "Tonga": [-21.18, -175.2], "Cape Verde": [15.1, -23.6], "Comoros": [-11.7, 43.3],
    "Saint Lucia": [13.9, -60.97], "Grenada": [12.1, -61.68], "Antigua and Barbuda": [17.07, -61.8],
    "Gibraltar": [36.14, -5.35], "Isle of Man": [54.24, -4.55], "Jersey": [49.21, -2.13], "Guernsey": [49.46, -2.59],
})
(ROOT / "pipeline" / "countries.json").write_text(json.dumps(dict(sorted(out.items())), ensure_ascii=False, indent=0), encoding="utf-8")
print(len(out), "countries")
for k in ["United States of America", "Russia", "France", "United Kingdom", "Japan", "Australia", "India", "Brazil"]:
    print(k, out.get(k))
