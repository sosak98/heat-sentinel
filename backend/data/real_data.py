"""Intégration des DONNÉES RÉELLES de la Temperature API® de FortyGuard.

Le harvest (harvest.py) cache chaque requête API réussie dans
``artifacts/{city}/real/{node}_{date}.json`` et produit
``artifacts/{city}/fortyguard_real_daily.csv`` avec, par (point, jour) :
min / moyenne / max réels du maillage (filter_type=3, jour complet).

Ce module fait deux choses :
  1. ``calibrate_history`` — recalage affine de la courbe horaire simulée sur
     les min/moy/max RÉELS observés pour chaque (point, jour) couvert. Le
     modèle s'entraîne donc sur une série dont les extremums quotidiens sont
     des mesures réelles de la mesh TwentyGuard, la forme horaire restant la
     simulation (l'API ne fournit que des statistiques journalières).
  2. ``real_summary`` — résumé des lectures réelles pour le dashboard
     (badge « source : Temperature API® (réel) »).

Règle d'or : on ne fabrique jamais de donnée réelle. Les cellules absentes du
CSV restent sur la simulation, marquée comme telle.
"""

from __future__ import annotations

import os

import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def real_csv_path(city: str) -> str:
    return os.path.join(HERE, "artifacts", city, "fortyguard_real_daily.csv")


def load_real_daily(city: str) -> pd.DataFrame:
    """Lecture du CSV de récolte (vide si le harvest n'a pas encore tourné)."""
    p = real_csv_path(city)
    if not os.path.exists(p):
        return pd.DataFrame(columns=["node_id", "name", "date", "min_c", "avg_c", "max_c"])
    df = pd.read_csv(p)
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    return df


def calibrate_history(history: pd.DataFrame, city: str) -> tuple[pd.DataFrame, int]:
    """Recalage affine (min/max) de la simulation sur les jours réels disponibles.

    Pour chaque (node_id, date) présent dans le CSV réel :
        a = (max_r - min_r) / (max_m - min_m) ; b = min_r - a * min_m
        temp' = a * temp + b   sur les 24 h du jour
    La forme horaire (pic diurne, UHI, bruit) est conservée ; seuls les
    niveaux sont contraints aux mesures réelles.

    Retourne (histoire recalée, nb_de_jours_point_calibrés).
    """
    real = load_real_daily(city)
    if real.empty:
        return history, 0

    df = history.copy()
    df["date"] = pd.to_datetime(df["ts"]).dt.strftime("%Y-%m-%d")
    n_cal = 0
    for (nid, day), g in df.groupby(["node_id", "date"]):
        row = real[(real["node_id"] == nid) & (real["date"] == day)]
        if row.empty:
            continue
        r = row.iloc[0]
        t = g["temp_c"].to_numpy()
        lo_m, hi_m = t.min(), t.max()
        if hi_m - lo_m < 1e-3:
            continue
        a = (r["max_c"] - r["min_c"]) / (hi_m - lo_m)
        b = r["min_c"] - a * lo_m
        df.loc[g.index, "temp_c"] = a * t + b
        # RH légèrement ajustée en cohérence (chaud réel ⇒ moins humide) :
        # pas de mesure RH réelle pour l'instant → on ne touche pas à rh_pct.
        n_cal += 1

    # CONTINUATION DE TENDANCE : les jours simulés APRÈS le dernier jour réel
    # suivent la tendance observée sur les 2 derniers jours réels (amortie
    # ×0.7) — le pic projeté reste cohérent avec les mesures (pas de saut).
    last_day = real["date"].max()
    for nid, gnode in df.groupby("node_id"):
        rnode = real[real["node_id"] == nid].sort_values("date")
        if len(rnode) < 2:
            continue
        dmax = float(rnode["max_c"].iloc[-1] - rnode["max_c"].iloc[-2])
        dmin = float(rnode["min_c"].iloc[-1] - rnode["min_c"].iloc[-2])
        tmax = float(rnode["max_c"].iloc[-1]) + 0.7 * dmax
        tmin = float(rnode["min_c"].iloc[-1]) + 0.7 * dmin
        fut = gnode[gnode["date"] > last_day]
        for _, g in fut.groupby("date"):
            t = g["temp_c"].to_numpy()
            lo_m, hi_m = t.min(), t.max()
            if hi_m - lo_m < 1e-3:
                continue
            a = (tmax - tmin) / (hi_m - lo_m)
            b = tmin - a * lo_m
            df.loc[g.index, "temp_c"] = a * t + b

    df = df.drop(columns=["date"])
    return df, n_cal


def real_summary(city: str, max_rows: int = 40) -> dict:
    """Résumé des lectures réelles pour le dashboard (triées, limitées)."""
    real = load_real_daily(city)
    if real.empty:
        return {"covered": False, "source": "Temperature API®", "rows": []}
    n_days = int(real["date"].nunique())
    n_nodes = int(real["node_id"].nunique())
    real = real.sort_values(["date", "node_id"], ascending=[False, True]).head(max_rows)
    rows = [
        {
            "node_id": r.node_id, "name": r.name, "date": r.date,
            "min_c": round(float(r.min_c), 2), "avg_c": round(float(r.avg_c), 2),
            "max_c": round(float(r.max_c), 2),
            "source": "Temperature API® (réel)",
        }
        for r in real.itertuples()
    ]
    return {
        "covered": True,
        "source": "Temperature API®",
        "n_days": n_days,
        "n_nodes": n_nodes,
        "granularity_m": 100,
        "rows": rows,
    }
