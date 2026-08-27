"""LIVE SYNC — le backend appelle la Temperature API® à l'exécution.

Au démarrage du serveur (puis toutes les ``SYNC_HOURS``, défaut 24 h), ce
module récupère les derniers jours RÉELS « terminés » (hier et avant — la
journée en cours ne renvoie pas de données chez l'API) pour tous les points
de la ville :

  - **cache d'abord** : un (point, jour) déjà récolté = 0 requête ;
  - chaque nouveau (point, jour) = 1 requête → ~20 crédits par jour réel ;
  - arrêt propre si les crédits sont épuisés (HTTP 402/403) ;
  - si de nouvelles données arrivent → le flux horaire est recalé sur les
    min/moy/max réels (calibrate_history) et les prédictions du modèle sont
    recalculées (engine._rebuild) — la démo s'actualise seule, sans
    intervention.

Variables d'environnement :
  FORTYGUARD_API_KEY  — absente → live sync désactivé (mode « calibrated »,
                        la démo reste 100 % fonctionnelle sur les lectures
                        déjà récoltées) ;
  SYNC_HOURS          — période de sync (défaut 24, 0 = désactivé) ;
  SYNC_MAX_DAYS       — profondeur max de rattrapage (défaut 3 jours).
"""

from __future__ import annotations

import json
import os
import sys
import time

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import httpx  # noqa: E402

from backend.data.cities import get_city  # noqa: E402
from backend.data.fortyguard import fetch_day, is_real  # noqa: E402
from backend.data.real_data import load_real_daily, real_csv_path  # noqa: E402

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _out_dir(city: str) -> str:
    d = os.path.join(BASE, "artifacts", city, "real")
    os.makedirs(d, exist_ok=True)
    return d


def latest_real_date(city: str) -> str | None:
    df = load_real_daily(city)
    if df.empty:
        return None
    return str(df["date"].max())


def sync_city(city: str, max_days: int = 3, sleep_s: float = 1.0) -> dict:
    """Récupère les jours réels manquants (hier → avant-hier…).

    Retourne un dict d'information (sérialisable pour /api/overview) :
    {"ok", "disabled", "last_sync", "days_added", "requests",
     "credits_dead", "latest": {"date", "max_c", "node"}}
    """
    info: dict = {"ok": False, "last_sync": None, "days_added": [],
                  "requests": 0, "credits_dead": False, "latest": None}
    if not is_real():
        info["disabled"] = True
        return info

    cfg = get_city(city)
    nodes = cfg["nodes"]
    out_dir = _out_dir(city)
    csv_path = real_csv_path(city)
    today = pd.Timestamp.now(tz="UTC").normalize()
    yesterday = (today - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    latest = latest_real_date(city)
    oldest = (today - pd.Timedelta(days=max_days)).strftime("%Y-%m-%d")
    if latest:
        oldest = max(oldest, (pd.Timestamp(latest) - pd.Timedelta(days=1)).strftime("%Y-%m-%d"))
    # jours à traiter : hier → oldest (plus réels que tout ce qui est déjà au CSV)
    days = []
    d = pd.Timestamp(yesterday)
    while d.strftime("%Y-%m-%d") >= oldest:
        days.append(d.strftime("%Y-%m-%d"))
        d -= pd.Timedelta(days=1)
    if not days:
        info["ok"] = True
        info["last_sync"] = pd.Timestamp.now(tz="UTC").isoformat()
        return info

    rows, credits_dead = [], False
    for date in days:
        for n in nodes:
            if credits_dead:
                break
            tag = f"{n['id']}_{date}"
            cache = os.path.join(out_dir, tag + ".json")
            from_cache = False
            if os.path.exists(cache):
                try:
                    cached = json.load(open(cache))
                    if cached.get("date"):
                        from_cache = True
                except Exception:
                    from_cache = False
            if not from_cache:
                try:
                    parsed = fetch_day(n, date, granularity=100)
                    info["requests"] += 1
                    if parsed is not None:
                        with open(cache, "w") as f:
                            json.dump(parsed, f, indent=1)
                except httpx.HTTPStatusError as e:
                    if e.response.status_code in (402, 403):
                        info["credits_dead"] = True
                        credits_dead = True
                        print(f"[live-sync] CRÉDITS ÉPUISÉS (HTTP {e.response.status_code}) — arrêt propre.")
                    time.sleep(sleep_s)
                    continue
                except Exception as e:
                    print(f"[live-sync] erreur {n['id']} {date}: {type(e).__name__}: {e}")
                    time.sleep(sleep_s)
                    continue
                time.sleep(sleep_s)
                if parsed is not None:
                    rows.append({"node_id": n["id"], "name": n["name"], **parsed})

    if rows:
        existing = pd.read_csv(csv_path) if os.path.exists(csv_path) else pd.DataFrame()
        df = pd.concat([existing, pd.DataFrame(rows)], ignore_index=True)
        df = df.drop_duplicates(subset=["node_id", "date"]).sort_values(["date", "node_id"])
        df.to_csv(csv_path, index=False)
        info["days_added"] = sorted({r["date"] for r in rows})

    # « dernier jour réel » = max du CSV (même sans nouvelle donnée)
    latest_df = load_real_daily(city)
    if not latest_df.empty:
        top = latest_df.loc[latest_df["date"] == str(latest_df["date"].max())]
        row = top.loc[top["max_c"].idxmax()]
        info["latest"] = {"date": str(latest_df["date"].max()),
                          "max_c": round(float(row["max_c"]), 1),
                          "node": str(row["name"])}
        info["n_days"] = int(latest_df["date"].nunique())
        info["n_readings"] = int(len(latest_df))
    info["ok"] = not credits_dead
    info["last_sync"] = pd.Timestamp.now(tz="UTC").isoformat()
    return info
