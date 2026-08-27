#!/usr/bin/env python3
"""HeatSentinel — entraînement one-shot (tourne sur Colab T4 ou un laptop ordinaire).

Usage:
  python train.py                    # Phoenix (plan B — démo, ville couverte par l'API)
  python train.py --city cotonou     # Cotonou (cible de déploiement, flux simulé)

1. Génère 8 jours de données hyperlocales simulées (20 points, climat calibré
   sur Open-Meteo), recalées sur les lectures RÉELLES de la Temperature API®
   quand le harvest (harvest.py) en a produit (artifacts/{ville}/fortyguard_real_daily.csv).
2. Entraîne le nowcast 6 h (hybride Ridge + LightGBM) — anomalies = z-score 48 h.
3. Évalue sur 24 h de hold-out temporel, sauvegarde artifacts/{ville}/.
4. Génère le snapshot embarqué du dashboard (mode démo hors-ligne).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.agent.sentinel import make_alert  # noqa: E402
from backend.data.cities import get_city  # noqa: E402
from backend.data.mock import generate_history  # noqa: E402
from backend.data.real_data import calibrate_history, real_summary  # noqa: E402
from backend.models.features import build_features  # noqa: E402
from backend.models.heat_risk import HeatSentinel, train  # noqa: E402

BASE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(BASE, "demo", "dashboard.template.html")
DASHBOARD = os.path.join(BASE, "demo", "dashboard.html")


def build_snapshot(city: str) -> dict:
    """État de la ville au pic de la vague de chaleur (fallback hors-ligne)."""
    cfg = get_city(city)
    hs = HeatSentinel(city)
    real = real_summary(city)
    hist, n_cal = calibrate_history(generate_history(days=8, seed=42, city=city), city)
    d = build_features(hist, city=city)
    d = d.dropna(subset=hs.meta["features"])
    d = hs.predict_matrix(d).sort_values(["ts", "node_id"]).reset_index(drop=True)

    tail = d[d["ts"] <= d["ts"].max()]
    pivot = tail.pivot(index="ts", columns="node_id", values="temp_c")
    pivot["max"] = pivot.max(axis=1)
    peak_ts = pivot["max"].idxmax()
    grp = tail[tail["ts"] == peak_ts]

    states = []
    for _, r in grp.iterrows():
        nid = r["node_id"]
        n = next(x for x in cfg["nodes"] if x["id"] == nid)
        states.append({
            "node_id": nid, "name": n["name"], "lat": n["lat"], "lon": n["lon"],
            "zone": n["zone"], "uhi": n["uhi"],
            "t_now": round(float(r["temp_c"]), 1), "rh": round(float(r["rh_pct"]), 1),
            "wind": round(float(r["wind_ms"]), 1), "wb_gt": round(float(r["wb_gt"]), 1),
            "tmax6h": round(float(r["tmax6h"]), 1), "score": round(float(r["score"]), 1),
            "level": str(r["level"]), "anomaly": int(r["anomaly"]),
        })

    ranked = sorted(states, key=lambda s: (-s["score"], -s["tmax6h"]))
    alerts = [make_alert(s, peak_ts.to_pydatetime(), next(x for x in cfg["nodes"] if x["id"] == s["node_id"]), city)
              for s in ranked[:4]]

    series = {}
    window = pivot.loc[:peak_ts].tail(24)
    for n in cfg["nodes"]:
        series[n["id"]] = [[t.strftime("%d/%m %H:%M"), round(float(v), 1)]
                           for t, v in window[n["id"]].items()]

    by_level: dict[str, int] = {}
    for s in states:
        by_level[s["level"]] = by_level.get(s["level"], 0) + 1
    top = max(states, key=lambda s: s["score"])
    m = hs.meta
    return {
        "mode": "demo",
        "speed": "snapshot (hors-ligne)",
        "ts": peak_ts.isoformat(),
        "clock_local": f"{(peak_ts.hour + cfg['tz_hours']) % 24:02d}:{peak_ts.minute:02d}",
        "city": {
            "name": cfg["name"], "country": cfg["country"],
            "population": cfg["population"], "heat_pitch": cfg["heat_pitch"],
            "map": cfg["map"],
            "source": (f"Temperature API® mesh (20 m², 2 m above ground) — {len(real['rows'])} real readings, re-anchored daily"
                       if real["covered"]
                       else "Simulated Temperature API® mesh feed (identical schema), calibrated on real Open-Meteo weather"),
        },
        "nodes": states,
        "stats": {
            "nodes": len(states),
            "max_temp": max(s["t_now"] for s in states),
            "avg_score": round(sum(s["score"] for s in states) / len(states), 1),
            "by_level": by_level,
            "hottest": top["name"],
            "hottest_score": top["score"],
        },
        "series": series,
        "model": {
            "name": f"Hybride Ridge+LightGBM nowcast {m['metrics']['horizon_h']}h + z-score 48h",
            "mae": m["metrics"]["mae"], "rmse": m["metrics"]["rmse"], "r2": m["metrics"]["r2"],
            "size_kb": m["model_size_kb"], "edge": "ONNX-ready · NVIDIA Jetson",
        },
        "alerts": alerts,
        "agent_events": [
            {"ts": a["ts"], "type": "alert", "node": a["node"], "text": a["message_fr"]} for a in alerts
        ],
        "real": real,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--city", default="phoenix", choices=["cotonou", "phoenix"])
    args = ap.parse_args()
    city = args.city

    print("=" * 64)
    print(f"HEATSENTINEL — entraînement ({get_city(city)['name']}, 20 points hyperlocaux)")
    print("=" * 64)

    hist, n_cal = calibrate_history(generate_history(days=8, seed=42, city=city), city)
    meta = train(hist, city=city)
    m = meta["metrics"]
    if n_cal:
        rs = real_summary(city)
        print(f"  calibration: {n_cal} jours·point recalés sur {rs['n_nodes']} points réels "
              f"({rs['n_days']} jour(s) Temperature API®)")
    else:
        print("  calibration: aucune donnée réelle disponible (harvest.py à lancer)")
    print(f"  nowcast 6 h (hold-out 24 h): MAE {m['mae']} °C · RMSE {m['rmse']} °C · R² {m['r2']}")
    print(f"  MAE fenêtre opérationnelle 10h–16h: {m['mae_op_window_10h_16h']} °C")
    print(f"  modèle: {meta['model_size_kb']} Ko (edge-ready)")
    print(f"  top features: {', '.join(meta['top_features'])}")

    snap = build_snapshot(city)
    art = os.path.join(BASE, "artifacts", city)
    os.makedirs(art, exist_ok=True)
    with open(os.path.join(art, "snapshot.json"), "w") as f:
        json.dump(snap, f, ensure_ascii=False, indent=1)

    with open(TEMPLATE) as f:
        html = f.read()
    token = "/*__SNAPSHOT__*/null"
    if token not in html:
        raise SystemExit("template: token /*__SNAPSHOT__*/null introuvable")
    html = html.replace(token, "/*__SNAPSHOT__*/" + json.dumps(snap, ensure_ascii=False))
    # carte OpenStreetMap intégrée (hors-ligne) + bornes de projection des nœuds
    mb_obj = json.dumps({"bounds": {"lon_min": 0, "lon_max": 1, "lat_min": 0, "lat_max": 1},
                         "w": 1200, "h": 872})
    map_img = None
    try:
        with open(os.path.join(BASE, "site", "assets", "mapdata.js")) as f:
            md = f.read()
        m = re.search(rf'{city}: \{{ img: "(data:image/jpeg;base64,[^"]+)", bounds: (\{{[^}}]+\}}) \}},', md)
        if m:
            map_img = m.group(1)
            mb_obj = json.dumps({"bounds": json.loads(m.group(2)), "w": 1200,
                                 "h": 872 if city == "phoenix" else 1680})
        else:
            print(f"  attention: entrée {city} introuvable dans mapdata.js (site/build_maps.py)")
    except FileNotFoundError:
        print("  attention: site/assets/mapdata.js absent — carte de fond neutre (site/build_maps.py)")
    html = html.replace("/*__MAPBOUNDS__*/", mb_obj)
    if map_img:
        html = html.replace('src="/*__MAPIMG__*/"', f'src="{map_img}"')
    with open(DASHBOARD, "w") as f:
        f.write(html)
    print(f"  snapshot → {art}/snapshot.json")
    print(f"  dashboard → {DASHBOARD}")
    print(f"\nTerminé. Démo: HS_CITY={city} python run_server.py  (http://0.0.0.0:8000)")


if __name__ == "__main__":
    main()
