"""Modèle HeatSentinel: nowcast 6 h du pic de chaleur + score de risque + anomalies.

Composants (légers, edge-first):
  - **Composante linéaire (Ridge)** sur les tendances 6/12/24/72 h:
    extrapolable — indispensable en fin de vague de chaleur où les arbres
    (LightGBM) ne peuvent pas extrapoler (sous-estimation nocturne, corrigée).
  - **LightGBM** sur le résidu: cycle diurne, UHI, interactions.
  - **z-score 48 h** (simple et transparent): anomalies — micro-pics locaux
    et dérives de capteur. |z_hod| ≥ 2,5 → anomalie.
  - Score de risque 0–100 (transparent), seuils adaptés par ville
    (Cotonou: chaleur humide 28→38 °C; Phoenix: 35→45 °C).

Artifacts par ville: artifacts/{ville}/ — model_lgbm.txt, lin_trend.joblib, meta.json.
"""

from __future__ import annotations

import json
import os

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, r2_score, root_mean_squared_error

from ..data.cities import DEFAULT_CITY, get_city
from .features import FEATURES, build_features

BASE_ART = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "artifacts")

# Composante linéaire (extrapolable) des tendances.
LIN_COLS = ["t_now", "trend_6h", "trend_12h", "trend_24h", "trend_72h", "uhi"]
Z_HOD_THRESHOLD = 2.5

LEVELS = ["green", "yellow", "orange", "red", "black"]
LEVEL_FR = {"green": "Faible", "yellow": "Vigilance", "orange": "Élevé", "red": "Critique", "black": "Extrême"}
LEVEL_EN = {"green": "Low", "yellow": "Watch", "orange": "Elevated", "red": "Critical", "black": "Extreme"}
LEVEL_RANK = {lv: i for i, lv in enumerate(LEVELS)}


def risk_score(tmax6: np.ndarray | float, rh: np.ndarray | float,
               t_lo: float = 28.0, t_hi: float = 38.0,
               rh_lo: float = 40.0, rh_hi: float = 90.0) -> np.ndarray | float:
    """Score 0–100. tmax6 = pic prévu 6 heures à l'avance (°C), rh = humidité (%).

    Seuils par ville (scoring dans cities.py):
      Cotonou (chaleur humide): 28 °C neutre → 38 °C extrême, RH 40→90 %
      Phoenix (désert):         35 °C neutre → 45 °C extrême, RH 10→40 %
    """
    t_s = np.clip((np.asarray(tmax6, dtype=float) - t_lo) / (t_hi - t_lo), 0.0, 1.0)
    h_s = np.clip((np.asarray(rh, dtype=float) - rh_lo) / (rh_hi - rh_lo), 0.0, 1.0)
    return np.clip(100.0 * (0.65 * t_s + 0.35 * h_s), 0.0, 100.0)


def levels_vector(score: np.ndarray) -> np.ndarray:
    return np.select(
        [score >= 85, score >= 70, score >= 50, score >= 30],
        ["black", "red", "orange", "yellow"],
        default="green",
    )


def level_of(score: float) -> str:
    return str(levels_vector(np.array([score]))[0])


def train(history: pd.DataFrame, city: str = DEFAULT_CITY) -> dict:
    """Entraîne et évalue (hold-out temporel 24 h). Sauvegarde artifacts/{city}/."""
    cfg = get_city(city)
    art = os.path.join(BASE_ART, city)
    os.makedirs(art, exist_ok=True)
    sc = cfg["scoring"]

    d = build_features(history, city=city)
    d = d.dropna(subset=["future_max_6h"] + FEATURES)

    cutoff = d["ts"].max() - pd.Timedelta(hours=24)
    train, test = d[d["ts"] < cutoff], d[d["ts"] >= cutoff]
    local_h = (test["ts"].dt.hour + test["ts"].dt.minute / 60 + cfg["tz_hours"]) % 24

    # 1. composante linéaire des tendances (extrapolation de la rampe)
    lin = Ridge(alpha=1.0)
    lin.fit(train[LIN_COLS], train["future_max_6h"])
    resid_train = train["future_max_6h"] - lin.predict(train[LIN_COLS])

    # 2. LightGBM sur le résidu
    model = lgb.LGBMRegressor(
        n_estimators=700, learning_rate=0.035, num_leaves=31,
        min_child_samples=20, subsample=0.9, colsample_bytree=0.9,
        random_state=42, n_jobs=2, verbose=-1,
    )
    model.fit(train[FEATURES], resid_train)
    pred = lin.predict(test[LIN_COLS]) + model.predict(test[FEATURES])

    # fenêtre opérationnelle (heure locale 10h–16h, quand l'agent alerte)
    op_mask = local_h.between(10, 16)
    metrics = {
        "mae": round(float(mean_absolute_error(test["future_max_6h"], pred)), 3),
        "rmse": round(float(root_mean_squared_error(test["future_max_6h"], pred)), 3),
        "r2": round(float(r2_score(test["future_max_6h"], pred)), 4),
        "mae_op_window_10h_16h": round(float(mean_absolute_error(
            test.loc[op_mask, "future_max_6h"], pred[op_mask.to_numpy()])), 3),
        "horizon_h": 6,
        "n_train_rows": int(len(train)),
        "n_test_rows": int(len(test)),
    }

    model.booster_.save_model(os.path.join(art, "model_lgbm.txt"))
    joblib.dump(lin, os.path.join(art, "lin_trend.joblib"))
    imp = sorted(zip(FEATURES, model.feature_importances_), key=lambda x: -x[1])
    meta = {
        "city": city,
        "features": FEATURES,
        "lin_cols": LIN_COLS,
        "scoring": sc,
        "z_hod_threshold": Z_HOD_THRESHOLD,
        "metrics": metrics,
        "top_features": [f for f, _ in imp[:8]],
        "model_size_kb": round(os.path.getsize(os.path.join(art, "model_lgbm.txt")) / 1024, 1),
    }
    with open(os.path.join(art, "meta.json"), "w") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    return meta


class HeatSentinel:
    """Wrapper d'inférence (CPU ou Jetson via ONNX Runtime). Un modèle par ville."""

    def __init__(self, city: str = DEFAULT_CITY):
        self.city = city
        self.art = os.path.join(BASE_ART, city)
        with open(os.path.join(self.art, "meta.json")) as f:
            self.meta = json.load(f)
        self.booster = lgb.Booster(model_file=os.path.join(self.art, "model_lgbm.txt"))
        lin_path = os.path.join(self.art, "lin_trend.joblib")
        self.lin = joblib.load(lin_path) if os.path.exists(lin_path) else None
        self.lin_cols = self.meta.get("lin_cols", LIN_COLS)
        sc = self.meta.get("scoring", get_city(city)["scoring"])
        self.scoring = sc

    def _hybrid(self, d: pd.DataFrame) -> np.ndarray:
        base = self.booster.predict(d[FEATURES].to_numpy(dtype=float))
        if self.lin is not None:
            base = base + self.lin.predict(d[self.lin_cols].to_numpy(dtype=float))
        return base

    def _score(self, tmax: np.ndarray, rh: np.ndarray) -> np.ndarray:
        sc = self.scoring
        return risk_score(tmax, rh, sc["t_lo"], sc["t_hi"], sc["rh_lo"], sc["rh_hi"])

    def predict_matrix(self, d: pd.DataFrame) -> pd.DataFrame:
        """Prédit sur toutes les lignes d'un frame déjà enrichi (build_features)."""
        tmax = self._hybrid(d)
        score = self._score(tmax, d["rh_pct"].to_numpy(dtype=float))
        dd = d.copy()
        dd["tmax6h"] = tmax
        dd["score"] = score
        dd["level"] = levels_vector(score)
        dd["anomaly"] = (d["z_hod"].abs() >= self.meta.get("z_hod_threshold", Z_HOD_THRESHOLD)).astype(int)
        return dd

    def predict_state(self, window: pd.DataFrame) -> dict:
        """État d'un point à partir des ~48 dernières heures (pour l'API/agent)."""
        d = build_features(window, city=self.city)
        tmax = float(self._hybrid(d)[0])
        score = float(self._score(np.array([tmax]), np.array([float(d["rh_pct"].iloc[-1])]))[0])
        anom = int(abs(float(d["z_hod"].iloc[-1] or 0.0)) >= self.meta.get("z_hod_threshold", Z_HOD_THRESHOLD))
        last = d.iloc[-1]
        return {
            "tmax6h": round(tmax, 2),
            "score": round(score, 1),
            "level": level_of(score),
            "anomaly": anom,
            "t_now": round(float(last["temp_c"]), 1),
            "rh": round(float(last["rh_pct"]), 1),
            "wind": round(float(last["wind_ms"]), 1),
            "wb_gt": round(float(last["wb_gt"]), 1),
        }
