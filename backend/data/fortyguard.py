"""Client FortyGuard Temperature API® — conforme à la doc officielle
(docs-api.fortyguard.com, lue le 27/08/2026).

Authentification : header `api-key: YOUR_API_KEY` sur chaque requête.
Base URL        : https://api.fortyguard.com (overridable via FORTYGUARD_BASE_URL)

Endpoints utilisés (disponibles sur le plan Basic) :
  POST /v1/heatmap           → soumet un task heatmap (async) → activity_id
  GET  /v1/status/{id}       → poll du task (Processing → Completed + result)

Capacités exploitées par HeatSentinel :
  - analytic_type 'tcm'            → température (°C) par tuile (mesure)
  - analytic_type 'time_of_measure'→ heure du pic de température (valide notre nowcast)
  - analytic_type 'exceedance'     → heures au-dessus d'un seuil (métrique de risque)
  - prévisions jusqu'à +12 h       → benchmark de notre modèle sur les 6 h
  - historique depuis 2019-01-01   → dataset réel pour ré-entraîner

Endpoints Premium (non utilisés) : heat-intelligence, segmentation satellite/
street view.

Mode mock (sans clé) : flux simulé au même schéma de sortie → la démo reste
100 % fonctionnelle avant réception des crédits trial.
"""

from __future__ import annotations

import math
import os
import time

import httpx

BASE = os.environ.get("FORTYGUARD_BASE_URL", "https://api.fortyguard.com")
KEY = os.environ.get("FORTYGUARD_API_KEY", "")

__all__ = ["is_real", "create_heatmap", "check_status", "wait_for_result",
           "tile_temp_for_node", "get_heat", "node_polygon", "BASE", "KEY"]


def is_real() -> bool:
    """True si une clé API est configurée (mode réel), sinon mock."""
    return bool(KEY)


def _headers() -> dict:
    return {"api-key": KEY, "Content-Type": "application/json"}


def node_polygon(node: dict, half_size_m: float = 300.0) -> dict:
    """Petit polygone GeoJSON centré sur le nœud (~600 m de côté, 20 m² résolu)."""
    lat, lon = float(node["lat"]), float(node["lon"])
    dlat = half_size_m / 111_320.0
    dlon = half_size_m / (111_320.0 * math.cos(math.radians(lat)))
    coords = [
        [lon - dlon, lat - dlat], [lon + dlon, lat - dlat],
        [lon + dlon, lat + dlat], [lon - dlon, lat + dlat],
        [lon - dlon, lat - dlat],  # boucle fermée
    ]
    return {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature", "properties": {},
            "geometry": {"type": "Polygon", "coordinates": [coords]},
        }],
    }


def create_heatmap(node: dict,
                   start_date: str,
                   start_time: str | None = None,
                   filter_type: int = 1,
                   end_time: str | None = None,
                   end_date: str | None = None,
                   analytic_type: str = "tcm",
                   granularity: int = 100,
                   threshold: float | None = None,
                   direction: str | None = None) -> str:
    """Soumet un task de génération de heatmap. Retourne l'activity_id.

    Args:
        start_date: YYYY-MM-DD (2019-01-01 → maintenant + 12 h)
        filter_type: 1 = heure unique, 2 = plage d'heures (même jour),
                     3 = jour complet, 4 = plage de jours (≤ 1 mois)
        analytic_type: 'tcm' (°C/tuile) | 'time_of_measure' (heure du pic)
                       | 'exceedance' | 'persistence' (heures au-delà du seuil)
        granularity: 60 | 80 | 100 (mètres)
        threshold/direction: pour exceedance/persistence (défaut 30 °C, 'above')
    """
    dt: dict = {"start_date": start_date, "filter_type": filter_type}
    if start_time:
        dt["start_time"] = start_time
    if end_time:
        dt["end_time"] = end_time
    if end_date:
        dt["end_date"] = end_date
    payload: dict = {
        "polygon_aoi": node_polygon(node),
        "date_time": dt,
        "granularity": granularity,
        "analytic_type": analytic_type,
    }
    if threshold is not None:
        payload["threshold"] = threshold
    if direction:
        payload["direction"] = direction

    r = httpx.post(f"{BASE}/v1/heatmap", headers=_headers(), json=payload, timeout=30)
    r.raise_for_status()
    body = r.json()
    if body.get("error"):
        raise RuntimeError(f"FortyGuard API error {body.get('status_code')}: {body.get('message')}")
    return body["data"]["activity_id"]


def check_status(activity_id: str) -> dict:
    r = httpx.get(f"{BASE}/v1/status/{activity_id}", headers=_headers(), timeout=30)
    r.raise_for_status()
    return r.json()


def wait_for_result(activity_id: str, poll_s: float = 5.0, timeout_s: float = 300.0) -> dict:
    """Polle le task jusqu'à 'Completed'. Retourne le bloc `result`
    (map_data: GeoJSON de tuiles + stats_data)."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        body = check_status(activity_id)
        data = body.get("data") or {}
        status = str(data.get("status", ""))
        if status == "Completed":
            return data.get("result", body)
        if status.lower() in ("failed", "error"):
            raise RuntimeError(f"task {activity_id} échoué: {body.get('message')}")
        time.sleep(poll_s)
    raise TimeoutError(f"task {activity_id} pas terminé après {timeout_s:.0f} s")


def nearest_tile(node: dict, map_data: dict) -> dict:
    """Propriétés de la tuile la plus proche du point depuis le GeoJSON.

    Schéma réel (confirmé sur vraies réponses, 27/08/2026) :
    properties = {tile_id, average_temperature, min_temperature, max_temperature}
    """
    best, best_d = None, None
    for f in (map_data or {}).get("features", []):
        geom = f.get("geometry", {})
        if geom.get("type") == "Polygon" and geom.get("coordinates"):
            ring = geom["coordinates"][0]
            cx = sum(c[0] for c in ring) / len(ring)
            cy = sum(c[1] for c in ring) / len(ring)
        elif geom.get("type") == "Point" and geom.get("coordinates"):
            cx, cy = geom["coordinates"][:2]
        else:
            continue
        d = (cx - float(node["lon"])) ** 2 + (cy - float(node["lat"])) ** 2
        if best_d is None or d < best_d:
            best, best_d = f.get("properties", {}), d
    if not best:
        raise ValueError("aucune tuile exploitable dans map_data")
    return best


def tile_temp_for_node(node: dict, map_data: dict) -> float:
    """Température (moyenne) de la tuile la plus proche du point."""
    best = nearest_tile(node, map_data)
    for k in ("average_temperature", "temperature", "temperature_c", "temp", "value", "tcm"):
        if k in best:
            return float(best[k])
    for v in best.values():
        if isinstance(v, (int, float)):
            return float(v)
    raise ValueError(f"aucun champ température trouvé dans les propriétés: {list(best)[:10]}")


def fetch_day(node: dict, date: str, granularity: int = 100, half_size_m: float = 300.0) -> dict | None:
    """Données RÉELLES d'un jour (filter_type=3) pour le point le plus proche.

    Retourne {"date", "min_c", "avg_c", "max_c"} ou None si le polygone
    n'est pas couvert (n_cells=0 — ex. Cotonou).
    """
    dt = {"start_date": date, "filter_type": 3}
    payload = {
        "polygon_aoi": node_polygon(node, half_size_m),
        "date_time": dt,
        "granularity": granularity,
    }
    r = httpx.post(f"{BASE}/v1/heatmap", headers=_headers(), json=payload, timeout=30)
    r.raise_for_status()
    body = r.json()
    if body.get("error"):
        raise RuntimeError(f"FortyGuard API error {body.get('status_code')}: {body.get('message')}")
    aid = body["data"]["activity_id"]
    result = wait_for_result(aid, poll_s=5.0, timeout_s=240.0)
    feats = (result.get("map_data") or {}).get("features", [])
    if not feats:
        return None  # non couvert
    props = nearest_tile(node, result.get("map_data"))
    out = {"date": date, "node_id": node["id"]}
    for src, dst in (("min_temperature", "min_c"), ("average_temperature", "avg_c"),
                     ("max_temperature", "max_c")):
        if src in props:
            out[dst] = round(float(props[src]), 2)
    return out


def get_heat(node: dict) -> dict:
    """Une lecture hyperlocale pour un nœud (schéma commun réel/mock).

    Mode réel: heatmap single-hour (filter_type 1) sur le polygone du nœud,
    température de la tuile la plus proche.
    """
    if KEY:
        import pandas as pd
        now = pd.Timestamp.now(tz="UTC")
        aid = create_heatmap(node, now.strftime("%Y-%m-%d"),
                             now.strftime("%H:00"), filter_type=1)
        result = wait_for_result(aid)
        t = tile_temp_for_node(node, result.get("map_data", {}))
        return {
            "location": node["name"], "temperature_c": round(t, 1),
            "rh_pct": None, "wind_ms": None,
            "resolution": "100m", "measured_at": "2m above ground",
            "source": "fortyguard",
        }
    from .mock import mock_reading
    from .cities import get_city
    return mock_reading(node, get_city(os.environ.get("HS_CITY", "cotonou")))


def get_history(node: dict, hours: int = 48) -> list[dict]:
    """Historique horaire d'un nœud.

    Mode réel: à construire via harvest.py (24 requêtes/jour/nœud = coûteux en
    crédits — c'est le rôle du script de récolte de le faire de façon contrôlée
    et en cache). Sans clé: générateur mock au même schéma.
    """
    if KEY:
        csv_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "artifacts", "fortyguard_real.csv")
        import pandas as pd
        if os.path.exists(csv_path):
            df = pd.read_csv(csv_path)
            rows = df[df["node_id"] == node["id"]].to_dict("records")
            if rows:
                return rows
    from .mock import generate_history
    import pandas as pd
    h = generate_history(days=max(2, hours // 24))
    return h[h["node_id"] == node["id"]].tail(hours).to_dict("records")
