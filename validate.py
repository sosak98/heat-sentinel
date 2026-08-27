#!/usr/bin/env python3
"""Calibration/validation du simulateur HeatSentinel sur données RÉELLES.

Source: Open-Meteo (gratuit, sans clé) — analyse météo horaire pour Cotonou
(6.36 N, 2.42 E). Compare le simulateur sur la même période réelle et
produit un tableau + artifacts/validation_openmeteo.json.

Usage:  python validate.py
"""

from __future__ import annotations

import json
import os
import statistics
import sys

import httpx
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.data.mock import generate_history  # noqa: E402
from backend.data.nodes import CITY  # noqa: E402

BASE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.join(BASE, "artifacts", "cotonou")


def fetch_openmeteo(lat: float = CITY["lat"], lon: float = CITY["lon"], past_days: int = 6) -> dict:
    r = httpx.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": lat, "longitude": lon,
            "hourly": "temperature_2m,relative_humidity_2m,wind_speed_10m",
            "past_days": past_days, "forecast_days": 0, "timezone": "UTC",
        },
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["hourly"]


def main():
    print("HeatSentinel — calibration du simulateur sur données réelles (Open-Meteo)")
    h = fetch_openmeteo()
    end = pd.Timestamp(h["time"][-1], tz="UTC")

    # --- données réelles (série ville) ---
    pairs = [(ts, v) for ts, v in zip(h["time"], h["temperature_2m"]) if v is not None]
    real = pd.Series(dict(pairs), dtype=float)
    real.index = pd.to_datetime(real.index, utc=True)
    rh = [v for v in h["relative_humidity_2m"] if v is not None]
    wind = [v for v in h["wind_speed_10m"] if v is not None]

    # --- simulateur sur la même période (moyenne des 20 nœuds, SANS vague de chaleur) ---
    mock = generate_history(days=6, seed=42, end=end, heatwave=False)
    sim = mock.groupby("ts")["temp_c"].mean()

    common = real.index.intersection(sim.index)
    daily_r = real.reindex(common).groupby(real.reindex(common).index.strftime("%Y-%m-%d")).agg(["min", "max", "mean"])
    daily_s = sim.reindex(common).groupby(sim.reindex(common).index.strftime("%Y-%m-%d")).agg(["min", "max", "mean"])

    print(f"\n{'Date':<12}{'Réel min':>9}{'Sim min':>9}{'Réel max':>9}{'Sim max':>9}{'Réel moy':>10}{'Sim moy':>10}")
    rows = []
    for day in daily_r.index:
        r_, s_ = daily_r.loc[day], daily_s.loc[day]
        print(f"{day:<12}{r_['min']:9.1f}{s_['min']:9.1f}{r_['max']:9.1f}{s_['max']:9.1f}{r_['mean']:10.1f}{s_['mean']:10.1f}")
        rows.append({
            "day": day,
            "real_c": [round(float(r_[k]), 1) for k in ("min", "max", "mean")],
            "sim_c": [round(float(s_[k]), 1) for k in ("min", "max", "mean")],
        })

    bias = float((real.reindex(common) - sim.reindex(common)).mean())
    out = {
        "source": "Open-Meteo (gratuit, sans clé)",
        "city": "Cotonou (6.36N, 2.42E)",
        "period": [str(daily_r.index[0]), str(daily_r.index[-1])],
        "real_rh_mean_pct": round(statistics.mean(rh), 0),
        "real_wind_mean_ms": round(statistics.mean(wind), 1),
        "hourly_bias_sim_vs_real_c": round(bias, 2),
        "daily": rows,
    }
    os.makedirs(ART, exist_ok=True)
    with open(os.path.join(ART, "validation_openmeteo.json"), "w") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    print(f"\nRH réelle (moy): {out['real_rh_mean_pct']:.0f} %  ·  vent réel (moy): {out['real_wind_mean_ms']} m/s")
    print(f"Bias horaire simulateur vs réel: {bias:+.2f} °C")
    print(f"Sauvegardé → {ART}/validation_openmeteo.json")


if __name__ == "__main__":
    main()
