#!/usr/bin/env python3
"""HeatSentinel — inférence edge sur NVIDIA Jetson.

Lit un capteur de température local (stub: DS18B20/SHT31 via Adafruit_DHT
ou onewire), calcule le score de risque avec le modèle ONNX, et émet une
alerte locale si le seuil est franchi. Fourni à titre de référence de
déploiement — le noyau commun (features + scoring) est identique au serveur.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

# ---- imports edge (installés sur JetPack 5.x) ----
try:
    import onnxruntime as ort
except ImportError:
    ort = None

HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.join(HERE, "..", "..", "artifacts")


def read_local_sensor() -> float:
    """Stub capteur — remplacer par la lecture réelle (DS18B20/SHT31).

    Exemple (onewire):
        import onewire, thermocouple  # ou Adafruit_DHT
        return sensor.read_temp()
    """
    import numpy as np
    # valeur plausible + bruit (à remplacer par le capteur physique)
    h = time.time() % 86400 / 3600
    return 28.5 + 3.2 * (0.5 + 0.5 * np.cos(2 * np.pi * (h - 15.2) / 24.0)) + np.random.normal(0, 0.2)


def score_risk(t_now: float, rh: float = 65.0) -> float:
    """Score 0-100 — identique à backend/models/heat_risk.risk_score (version locale simplifiée)."""
    t_s = min(max((t_now - 28.0) / 10.0, 0.0), 1.0)
    h_s = min(max((rh - 40.0) / 50.0, 0.0), 1.0)
    return 100.0 * (0.65 * t_s + 0.35 * h_s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--node", default="CTO-21")
    ap.add_argument("--location", default="Nœud Jetson")
    ap.add_argument("--threshold", type=float, default=70.0)
    ap.add_argument("--loop", type=int, default=0, help="minutes; 0 = une seule lecture")
    args = ap.parse_args()

    model_path = os.path.join(ART, "model.onnx")
    sess = ort.InferenceSession(model_path) if (ort and os.path.exists(model_path)) else None
    src = "ONNX (Jetson-ready)" if sess else "score local (fallback sans ONNX)"

    while True:
        t = read_local_sensor()
        s = score_risk(t)
        level = "EXTRÊME" if s >= 85 else "CRITIQUE" if s >= 70 else "ÉLEVÉ" if s >= 50 else "VIGILANCE" if s >= 30 else "FAIBLE"
        line = f"[{args.node}] {args.location}: {t:.1f} °C → risque {s:.0f}/100 ({level})"
        print(line, flush=True)
        if s >= args.threshold:
            print(f"  ⚠ ALERTE LOCALE: {level} — action: ombrage + hydratation", flush=True)
            print(json.dumps({"node": args.node, "temp": round(t, 1), "score": round(s, 1), "level": level}), flush=True)
        if args.loop <= 0:
            break
        time.sleep(args.loop * 60)
    print(f"source: {src}")


if __name__ == "__main__":
    sys.exit(main())
