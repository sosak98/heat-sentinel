"""Ingénierie des features pour le nowcast de chaleur (horizon 6 h).

Design edge-first: features simples et robustes (pas d'embeddings lourds)
pour que le modèle reste < 5 Mo et tourne sur un NVIDIA Jetson.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..data.cities import get_city


def _node_meta(node_id: str, city: str) -> dict:
    return next((n for n in get_city(city)["nodes"] if n["id"] == node_id),
                {"uhi": 0.0, "zone": "mixed"})


FEATURES = [
    "t_now", "t_3h", "t_6h", "t_12h", "t_24h", "t_72h",
    "t_24h_lag", "t_48h_lag",
    "slope_3h", "trend_6h", "trend_12h", "trend_24h", "trend_72h", "z_temp", "z_hod",
    "rh_pct", "wind_ms", "wb_gt",
    "hour_sin", "hour_cos", "dow_sin", "dow_cos",
    "uhi", "zone_ind", "zone_beach", "zone_dense",
]


def wet_bulb(t: np.ndarray, rh: np.ndarray) -> np.ndarray:
    """Température de bulbe humide (°C) — approximation de Stull (2011).

    Proxy du ressenti sans capteur supplémentaire: Tw est le paramètre
    standard des plans de gestion de la chaleur (OMS).
    """
    t = np.asarray(t, dtype=float)
    rh = np.clip(np.asarray(rh, dtype=float), 1.0, 100.0)
    return (
        t * np.arctan(0.151977 * np.sqrt(rh + 8.313659))
        + np.arctan(t + rh)
        - np.arctan(rh - 1.676331)
        + 0.00391837 * rh**1.5 * np.arctan(0.023101 * rh)
        - 4.686035
    )


def build_features(df: pd.DataFrame, city: str = "cotonou") -> pd.DataFrame:
    """Ajoute les features à un historique horaire (multi-nœuds ou un seul nœud).

    `df` doit contenir: ts, temp_c, rh_pct, wind_ms, node_id (+ future_max_6h si entraînement).
    """
    cfg = get_city(city)
    tz = cfg["tz_hours"]
    nodes = {n["id"]: n for n in cfg["nodes"]}
    d = df.sort_values(["node_id", "ts"]).copy()
    d["local_h"] = (d["ts"].dt.hour + d["ts"].dt.minute / 60.0 + tz) % 24.0
    d["dow"] = d["ts"].dt.dayofweek.to_numpy(dtype=float)

    g = d.groupby("node_id")
    d["t_now"] = d["temp_c"]
    d["t_3h"] = g["temp_c"].transform(lambda s: s.shift(1).rolling(3, min_periods=1).mean())
    d["t_6h"] = g["temp_c"].transform(lambda s: s.shift(1).rolling(6, min_periods=1).mean())
    d["t_12h"] = g["temp_c"].transform(lambda s: s.shift(1).rolling(12, min_periods=1).mean())
    d["t_24h"] = g["temp_c"].transform(lambda s: s.shift(1).rolling(24, min_periods=6).mean())
    d["t_72h"] = g["temp_c"].transform(lambda s: s.shift(1).rolling(72, min_periods=24).mean())
    d["t_24h_lag"] = g["temp_c"].transform(lambda s: s.shift(24))
    d["t_48h_lag"] = g["temp_c"].transform(lambda s: s.shift(48))
    d["slope_3h"] = d["temp_c"] - d["t_3h"]
    d["trend_6h"] = d["temp_c"] - d["t_6h"]
    d["trend_12h"] = d["temp_c"] - d["t_12h"]
    d["trend_24h"] = d["temp_c"] - d["t_24h"]
    d["trend_72h"] = d["temp_c"] - d["t_72h"]
    roll_mean = d["temp_c"].groupby(d["node_id"]).transform(lambda s: s.rolling(48, min_periods=12).mean())
    roll_std = d["temp_c"].groupby(d["node_id"]).transform(lambda s: s.rolling(48, min_periods=12).std()).replace(0.0, 1.0)
    d["z_temp"] = (d["temp_c"] - roll_mean) / roll_std
    d["z_hod"] = _z_same_hour(d, tz)

    d["wb_gt"] = wet_bulb(d["temp_c"].to_numpy(), d["rh_pct"].to_numpy())

    d["hour_sin"] = np.sin(2 * np.pi * d["local_h"] / 24.0)
    d["hour_cos"] = np.cos(2 * np.pi * d["local_h"] / 24.0)
    d["dow_sin"] = np.sin(2 * np.pi * d["dow"] / 7.0)
    d["dow_cos"] = np.cos(2 * np.pi * d["dow"] / 7.0)

    meta = d["node_id"].map(lambda nid: nodes.get(nid, {"uhi": 0.0, "zone": "mixed"}))
    d["uhi"] = meta.map(lambda m: m["uhi"])
    d["zone_ind"] = d["node_id"].map(lambda nid: nodes.get(nid, {}).get("zone")) == "industrial"
    d["zone_beach"] = d["node_id"].map(lambda nid: nodes.get(nid, {}).get("zone")) == "beach"
    d["zone_dense"] = d["node_id"].map(lambda nid: nodes.get(nid, {}).get("zone")) == "dense"

    return d


def _z_same_hour(d: pd.DataFrame, tz: int) -> np.ndarray:
    """z-score SIMPLE de détection d'anomalies (MVP): température actuelle vs
    sa valeur normale à la même heure (les 3 dernières occurrences, ~48 h).

    Transparent et interprétable: |z| ≥ 2,5 → pic local ou dérive capteur.
    """
    out = np.full(len(d), np.nan)
    vals = d["temp_c"].to_numpy(dtype=float)
    minutes = (d["ts"].dt.hour.to_numpy() * 60 + d["ts"].dt.minute.to_numpy()).astype(float)
    local_min = (minutes + tz * 3600.0) % 1440.0
    for _, idx in d.groupby("node_id", sort=False).groups.items():
        ix = np.array(sorted(idx))
        v = vals[ix]
        h = local_min[ix]
        for j in range(1, len(ix)):
            sel = v[1:j][h[1:j] == h[j]]
            sel = sel[-3:]  # les 3 dernières heures identiques (~48 h)
            if len(sel) >= 2:
                mu = sel.mean()
                sd = max(float(sel.std()), 0.08)
                out[ix[j]] = (v[j] - mu) / sd
    return out
