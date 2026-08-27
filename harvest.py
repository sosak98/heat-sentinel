#!/usr/bin/env python3
"""Récolte de données RÉELLES FortyGuard (Temperature API®) — MODE JOURNALIER.

Schéma réel (confirmé 27/08/2026) : filter_type=3 (jour complet) → 1 requête
par point × jour → tuiles GeoJSON avec min/average/max_temperature par tuile.
(Le mode heure unique, filter_type=1, renvoie 0 cellules — à éviter.)

Stratégie crédits : 1 requête = 1 point × 1 jour. Cache local : chaque
réponse brute est sauvegardée et JAMAIS re-demandée. Arrêt propre si les
crédits sont épuisés (402/403) — les données déjà récoltées sont gardées.

Exemples:
  python harvest.py --city phoenix --days 7
  python harvest.py --city phoenix --days 3 --nodes PHX-01,PHX-02,PHX-15

Sorties:
  artifacts/{city}/real/{node}_{date}.json    (réponses brutes — à garder)
  artifacts/{city}/fortyguard_real_daily.csv  (série journalière)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import httpx  # noqa: E402
import pandas as pd  # noqa: E402

from backend.envload import load_env  # noqa: E402
load_env()

from backend.data.cities import get_city  # noqa: E402
from backend.data.fortyguard import fetch_day, is_real  # noqa: E402

BASE = os.path.dirname(os.path.abspath(__file__))


def main():
    ap = argparse.ArgumentParser(description="Récolte journalière de données FortyGuard")
    ap.add_argument("--city", default="phoenix", choices=["cotonou", "phoenix"])
    ap.add_argument("--days", type=int, default=7, help="jours de récolte (hier → avant-hier…)")
    ap.add_argument("--nodes", default="", help="ids séparés par des virgules (défaut: tous)")
    ap.add_argument("--granularity", type=int, default=100, choices=[60, 80, 100])
    ap.add_argument("--sleep", type=float, default=1.0, help="attente entre requêtes (s)")
    args = ap.parse_args()

    if not is_real():
        sys.exit("✗ FORTYGUARD_API_KEY absente (.env) — impossible de récolter.")

    cfg = get_city(args.city)
    out_dir = os.path.join(BASE, "artifacts", args.city, "real")
    os.makedirs(out_dir, exist_ok=True)
    csv_path = os.path.join(BASE, "artifacts", args.city, "fortyguard_real_daily.csv")

    nodes = cfg["nodes"]
    if args.nodes:
        wanted = [x.strip() for x in args.nodes.split(",") if x.strip()]
        nodes = [n for n in cfg["nodes"] if n["id"] in wanted]
    if not nodes:
        sys.exit("✗ aucun point valide")

    today = pd.Timestamp.now(tz="UTC")
    rows, n_req, n_uncovered = [], 0, 0
    credits_dead = False

    for day in range(1, args.days + 1):
        d = (today - pd.Timedelta(days=day)).strftime("%Y-%m-%d")
        for n in nodes:
            if credits_dead:
                break
            tag = f"{n['id']}_{d}"
            cache = os.path.join(out_dir, tag + ".json")
            parsed = None
            if os.path.exists(cache):
                cached = json.load(open(cache))
                if cached.get("date"):
                    parsed = cached
                    print(f"= {tag}: cache")
            else:
                print(f"→ {tag} ({n['name']})…", end=" ", flush=True)
                try:
                    parsed = fetch_day(n, d, granularity=args.granularity)
                except httpx.HTTPStatusError as e:
                    code = e.response.status_code
                    if code in (402, 403):
                        print(f"CRÉDITS ÉPUISÉS (HTTP {code}) — arrêt propre.")
                        credits_dead = True
                        break
                    print(f"HTTP {code}: {e.response.text[:120]}")
                except Exception as e:
                    print(f"erreur: {type(e).__name__}: {e}")
                if parsed is not None:
                    with open(cache, "w") as f:
                        json.dump(parsed, f, indent=1)
                    n_req += 1
                time.sleep(args.sleep)

            if parsed is not None:
                rows.append({"node_id": n["id"], "name": n["name"], **parsed})
                print(f"✓ {parsed['avg_c']} °C (min {parsed['min_c']} / max {parsed['max_c']}) [req {n_req}]")

    if rows:
        existing = pd.read_csv(csv_path) if os.path.exists(csv_path) else pd.DataFrame()
        df = pd.concat([existing, pd.DataFrame(rows)], ignore_index=True)
        df = df.drop_duplicates(subset=["node_id", "date"]).sort_values(["date", "node_id"])
        df.to_csv(csv_path, index=False)
        print(f"\n✓ {len(rows)} lectures → {csv_path}")
        print(f"  total: {df['date'].nunique()} jours × {df['node_id'].nunique()} points")
    print(f"requêtes API: {n_req} | non couverts: {n_uncovered} | crédits épuisés: {credits_dead}")


if __name__ == "__main__":
    main()
