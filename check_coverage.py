#!/usr/bin/env python3
"""TEST DE COUVERTURE — PRIORITÉ N°1 dès réception de la clé API.

1 requête (~1 crédit): est-ce que la ville est couverte par la Temperature API® ?

Usage:
  python check_coverage.py                 # Cotonou (point: Port Autonome)
  python check_coverage.py --city phoenix  # Phoenix (point: Downtown)

Si Cotonou n'est PAS couverte → plan B : démo sur Phoenix (ville couverte),
Cotonou reste la cible de déploiement dans le pitch.
  HS_CITY=phoenix python run_server.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd  # noqa: E402

from backend.envload import load_env  # noqa: E402
load_env()

from backend.data.cities import get_city  # noqa: E402
from backend.data.fortyguard import (  # noqa: E402
    create_heatmap, is_real, tile_temp_for_node, wait_for_result,
)

BASE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(BASE, "artifacts", "fortyguard_raw")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--city", default="cotonou", choices=["cotonou", "phoenix"])
    args = ap.parse_args()
    cfg = get_city(args.city)

    if not is_real():
        sys.exit("✗ FORTYGUARD_API_KEY absente — exécutez ce test dès réception de la clé trial.\n"
                 "  export FORTYGUARD_API_KEY=... && python check_coverage.py")

    node = cfg["nodes"][0]  # point de test
    yesterday = (pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    os.makedirs(RAW, exist_ok=True)

    print(f"Test de couverture {cfg['name']} ({node['name']}, {yesterday} 15:00 UTC)…")
    t0 = time.time()
    try:
        aid = create_heatmap(node, yesterday, "15:00", filter_type=1, granularity=100)
        print(f"  task soumis ({aid}) — en attente du résultat…")
        result = wait_for_result(aid, poll_s=5.0, timeout_s=240.0)
    except Exception as e:
        print(f"  ✗ {type(e).__name__}: {e}")
        print("\n→ La ville semble PAS couverte (ou erreur API).\n"
              "  PLAN B: HS_CITY=phoenix python run_server.py  (Cotonou reste la cible de déploiement)")
        return

    with open(os.path.join(RAW, f"coverage_{args.city}_{yesterday}.json"), "w") as f:
        json.dump(result, f, indent=1)

    try:
        t = tile_temp_for_node(node, result.get("map_data", {}))
        print(f"\n✅ {cfg['name']} EST COUVERTE — {node['name']}: {t:.1f} °C "
              f"({time.time() - t0:.0f} s, ~1 crédit consommé)")
        print("Réponse brute sauvegardée → artifacts/fortyguard_raw/ (vérifier le schéma,")
        print("puis ajuster tile_temp_for_node si le champ température a un autre nom.)")
        print("\nÉtape suivante: python harvest.py")
    except Exception as e:
        print(f"  ⚠ réponse reçue mais extraction de tuile: {e}")
        print("  (réponse brute sauvegardée — inspecter artifacts/fortyguard_raw/)")


if __name__ == "__main__":
    main()
