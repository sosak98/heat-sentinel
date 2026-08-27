#!/usr/bin/env python3
"""Génère les cartes OpenStreetMap intégrées au site (fonctionnent hors-ligne).

Pour chaque ville : télécharge un grille de tuiles OSM (zoom 12), les assemble
en une seule image, calcule les bornes géographiques exactes et sort
  site/assets/maps_phoenix.png, maps_cotonou.png  +  site/assets/mapdata.js
(les 20 points du maillage sont projetés précisément sur l'image dans le JS).

Attribution obligatoire : © OpenStreetMap contributors
"""
from __future__ import annotations

import base64
import io
import math
import os
import sys

import httpx
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.data.cities import CITIES  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "assets")
Z = 12
UA = "HeatSentinel-Hackathon26 (contact: climvision-team; one-off static capture)"


def tile_xy(lon: float, lat: float, z: int) -> tuple[float, float]:
    n = 2.0 ** z
    x = (lon + 180.0) / 360.0 * n
    lat_r = math.radians(lat)
    y = (1.0 - math.asinh(math.tan(lat_r)) / math.pi) / 2.0 * n
    return x, y


def lon_lat_of_tile(x: int, y: int, z: int) -> tuple[float, float]:
    """coin haut-gauche de la tuile (lon, lat)."""
    n = 2.0 ** z
    lon = x / n * 360.0 - 180.0
    lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
    return lon, lat


def build_city(city: str) -> tuple[str, dict]:
    nodes = CITIES[city]["nodes"]
    lats = [n["lat"] for n in nodes]
    lons = [n["lon"] for n in nodes]
    c_lat, c_lon = sum(lats) / len(lats), sum(lons) / len(lons)
    # grille minimale qui englobe tous les nœuds, + 1 tuile de marge
    x0f, y0f = tile_xy(min(lons), max(lats), Z)   # haut-gauche
    x1f, y1f = tile_xy(max(lons), min(lats), Z)   # bas-droite
    x0, x1 = int(math.floor(x0f)) - 1, int(math.ceil(x1f)) + 1
    y0, y1 = int(math.floor(y0f)) - 1, int(math.ceil(y1f)) + 1
    w, h = (x1 - x0 + 1) * 256, (y1 - y0 + 1) * 256
    print(f"  {city}: grille {x1 - x0 + 1}×{y1 - y0 + 1} tuiles z{Z} ({w}×{h} px)…")

    img = Image.new("RGB", (w, h))
    r = httpx.Client(headers={"User-Agent": UA}, timeout=30)
    for tx in range(x0, x1 + 1):
        for ty in range(y0, y1 + 1):
            u = f"https://tile.openstreetmap.org/{Z}/{tx}/{ty}.png"
            resp = r.get(u)
            resp.raise_for_status()
            tile = Image.open(io.BytesIO(resp.content)).convert("RGB")
            img.paste(tile, ((tx - x0) * 256, (ty - y0) * 256))
    r.close()

    lon_t, lat_t = lon_lat_of_tile(x0, y0, Z)      # coin haut-gauche
    lon_b, lat_b = lon_lat_of_tile(x1 + 1, y1 + 1, Z)  # coin bas-droite
    bounds = {"lon_min": lon_t, "lon_max": lon_b, "lat_min": lat_b, "lat_max": lat_t}
    # on n'affiche la carte qu'à ~800 px de large → on redimensionne + JPEG q85
    max_w = 1200
    if img.width > max_w:
        ratio = max_w / img.width
        img = img.resize((max_w, int(img.height * ratio)), Image.LANCZOS)
    jpg = os.path.join(OUT, f"maps_{city}.jpg")
    img.convert("RGB").save(jpg, quality=85, optimize=True)
    b64 = base64.b64encode(open(jpg, "rb").read()).decode()
    print(f"  {city}: {os.path.getsize(jpg) // 1024} Ko ({img.size[0]}×{img.size[1]}) · bounds {bounds}")
    return b64, bounds


def main():
    os.makedirs(OUT, exist_ok=True)
    parts = []
    for city in ("phoenix", "cotonou"):
        b64, bounds = build_city(city)
        parts.append(f'  {city}: {{ img: "data:image/png;base64,{b64}", bounds: {bounds!r} }},')
    js = "/* Cartes OpenStreetMap intégrées (hors-ligne). © OpenStreetMap contributors */\n"
    js += "const MAPS = {\n" + "\n".join(parts) + "\n};\n"
    with open(os.path.join(OUT, "mapdata.js"), "w") as f:
        f.write(js)
    print("OK → site/assets/mapdata.js")


if __name__ == "__main__":
    main()
