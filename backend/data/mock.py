"""Générateur de données hyperlocales physiquement plausibles (multi-villes).

Sert deux rôles:
  1. Entraîner/évaluer le modèle avant/après réception des crédits trial.
  2. Alimenter le serveur de démo en mode SIMULATED (1 h ≈ 15 s).

La donnée réelle provient du maillage de la Temperature API® de FortyGuard
(résolution 20 m², température modélisée à 2 m au-dessus du sol) — ce module
simule ce maillage (même schéma de sortie). Nous n'installons aucun matériel.

Physique simulée — Cotonou (climat côtier tropical humide, UTC+1),
**calibrée sur données réelles Open-Meteo** (2026-08-21→27 : moyenne 26,6 °C,
pic après-midi ~27,6 °C, nuit ~25,6 °C, RH ~83 % — voir validate.py) :
  - cycle diurne, pic ~15:20, plus chaud vers fin février (doy≈60),
  - îlots de chaleur urbains par zone (port/industriel > centre dense > plage),
  - vague de chaleur extrême (+5,5 °C) sur les 4 derniers jours de la série,
  - humidité très élevée (76 % après-midi, ~85 % la nuit), vent 10–20 m/s,
  - bruit AR(1), micro-pics de chaleur (que le détecteur d'anomalies repère).

Phoenix (plan B de démo) : climat désertique — 40–43 °C en août, RH 15–25 %,
forte amplitude diurne, parcs nettement plus frais que le cœur de ville.
**Calibré sur Open-Meteo réelles 2026-08-21→27** (vague de chaleur en cours :
moyenne 38,5 °C, min 29,0 / max 46,3 °C, pic 15–16 h, RH nuit 26–52 % / jour 10–13 %).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .cities import get_city


def _diurnal(local_h: np.ndarray, peak_h: float, phase: float = 0.0) -> np.ndarray:
    """1 au pic, -1 au creux."""
    return np.cos(2 * np.pi * ((local_h + phase) - peak_h) / 24.0)


def generate_history(days: int = 8, seed: int = 42, end: pd.Timestamp | None = None,
                     heatwave: bool = True, city: str | None = None) -> pd.DataFrame:
    """Série horaire (jours × 20 points) avec cible `future_max_6h`."""
    cfg = get_city(city)
    cl = cfg["climate"]
    tz = cfg["tz_hours"]
    rng = np.random.default_rng(seed)
    end = (end or pd.Timestamp.now(tz="UTC")).floor("h")
    n = days * 24 + 1
    ts = pd.date_range(end=end, periods=n, freq="h", tz="UTC")

    local_h = (ts.hour + ts.minute / 60.0 + tz).to_numpy(dtype=float) % 24.0
    doy = ts.dayofyear.to_numpy(dtype=float)
    # vague de chaleur: rampe linéaire sur les 4 derniers jours (0 → 1)
    if heatwave:
        hw = np.clip((np.arange(n) - (n - 4 * 24)) / (4 * 24.0), 0.0, 1.0)
    else:
        hw = np.zeros(n)

    # saisonnalité: pic à season_doy (mars pour Cotonou, juillet pour Phoenix)
    season = cl["season_amp"] * np.cos(2 * np.pi * (doy - cl["season_doy"]) / 365.0)

    frames = []
    for node in cfg["nodes"]:
        uhi = node["uhi"]
        mean = cl["base"] + cl["uhi_w"] * uhi + cl["hw_delta"] * hw + season
        amp = cl["amp"] + cl["amp_uhi"] * abs(uhi) + cl["hw_amp"] * hw
        temp = mean + amp * _diurnal(local_h, cl["peak_h"])

        # bruit AR(1) — l'API réelle renvoie un champ 20 m² lissé
        eps = rng.normal(0.0, cl["ar_sigma"], n)
        ar = np.empty(n)
        x = 0.0
        for i in range(n):
            x = 0.85 * x + eps[i]
            ar[i] = x
        temp = temp + ar

        # micro-pics de chaleur locaux (2–5 h, +0.8 à +1.6 °C)
        for _ in range(int(rng.integers(0, 3))):
            s = int(rng.integers(0, n - 32))
            ln = int(rng.integers(2, 6))
            temp[s : s + ln] += float(rng.uniform(0.8, 1.6))

        rh = cl["rh_base"] - cl["rh_amp"] * (0.5 + 0.5 * _diurnal(local_h, cl["peak_h"], phase=-0.3)) - cl["rh_hw"] * hw
        rh = np.clip(rh + rng.normal(0.0, cl["rh_noise"], n), cl["rh_min"], cl["rh_max"])

        wind = cl["wind_base"] + cl["wind_amp"] * (0.5 + 0.5 * _diurnal(local_h, cl["peak_h"], phase=-1.0))
        wind = np.clip(wind + rng.normal(0.0, cl["wind_noise"], n), cl["wind_min"], cl["wind_max"])

        f = pd.DataFrame(
            {"ts": ts, "temp_c": temp, "rh_pct": rh, "wind_ms": wind, "node_id": node["id"]}
        )
        f["future_max_6h"] = _future_max(temp, horizon=6)
        frames.append(f)

    out = pd.concat(frames, ignore_index=True)
    return out.sort_values(["node_id", "ts"]).reset_index(drop=True)


def _future_max(temp: np.ndarray, horizon: int = 6) -> np.ndarray:
    """target[i] = max(temp[i+1 .. i+horizon]) (NaN sur les horizon dernières lignes)."""
    out = np.full(len(temp), np.nan)
    for i in range(len(temp) - horizon):
        out[i] = temp[i + 1 : i + 1 + horizon].max()
    return out


def mock_reading(node: dict, cfg: dict | None = None) -> dict:
    """Lecture 'live' plausible pour le client API mock (schéma identique à l'API réelle)."""
    cfg = cfg or get_city()
    now = pd.Timestamp.now(tz="UTC")
    local_h = (now.hour + now.minute / 60.0 + cfg["tz_hours"]) % 24.0
    cl = cfg["climate"]
    d = _diurnal(np.array([local_h]), cl["peak_h"])[0]
    t = cl["base"] + cl["uhi_w"] * node["uhi"] + (cl["amp"] + cl["amp_uhi"] * abs(node["uhi"])) * d
    t += float(np.random.default_rng(0).normal(0, 0.4))
    rh = float(np.clip(cl["rh_base"] - cl["rh_amp"] * (0.5 + 0.5 * _diurnal(np.array([local_h]), cl["peak_h"], phase=-0.3))[0],
                       cl["rh_min"], cl["rh_max"]))
    return {
        "location": node["name"],
        "temperature_c": round(t, 1),
        "rh_pct": round(rh, 1),
        "wind_ms": round(cl["wind_base"], 1),
        "resolution": "20m²",
        "measured_at": "2m above ground",
        "source": "mock",
    }
