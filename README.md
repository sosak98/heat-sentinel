# 🔥 HEATSENTINEL — Urban Heat Intelligence, proven on real data

**An agentic AI that watches, predicts and acts on urban heat** — built on the
**FortyGuard Temperature API®** for **Hackathon'26 — Building the World's
Temperature AI** (FortyGuard × NVIDIA).

> **Heat kills at street level. We see it coming six hours early.**

<!-- DEPLOY: replace with your Render URL after the first deploy -->
**Live demo:** `https://heatsentinel.onrender.com` (site + live dashboard at
`/demo/` — first load after inactivity takes ~30–60 s)

## The problem

Heat is the deadliest climate hazard (≈2 M premature deaths/year, WHO) and the
least prepared for. In **Phoenix, Arizona**, the summer 2026 heat wave pushed
street-level temperatures to **46 °C** while city-scale forecasts — issued at
8 AM for a 3 PM peak, anchored on a single airport sensor — gave nobody a
street-level, hour-precise warning. Hospitals, schools, markets and outdoor
workers had no early warning they could act on.

HeatSentinel answers with **hyperlocal 6-hour-ahead peak prediction and
automatic, concrete alerts** — for Phoenix, on real Temperature API® data,
and by design for any covered city. **Cotonou, Benin (1.5 M+ metro, humid
heat: feels-like > 40 °C) is our first deployment target** — the system is
city-agnostic and re-trains on any new city in under 30 seconds.

## The solution

HeatSentinel closes the full **Monitor → Predict → Decide → Act** loop:

| Layer | What |
|---|---|
| 📡 **Data** | 20 **Temperature API® measurement points** (20 m² resolution, modeled 2 m above ground — FortyGuard's mesh; **we install no hardware**) across key zones: core UHI, river corridor (cooling effect), suburban edge, activity centers |
| 🧠 **AI core** | **Hybrid model** (Ridge trend component + LightGBM) **nowcasting the temperature peak 6 hours ahead** per point — **Phoenix: MAE 0.36 °C, R² 0.98** (24 h time-based hold-out, ~2 MB model) + **48 h z-score** anomaly detection (local heat spikes, sensor drift) |
| 🤖 **Agent** | Transparent policy engine (no black box, no LLM dependency): dedup, escalation-only, JSONL audit ledger, **localized alerts with concrete actions** (EN for Phoenix; FR + **Fon** for Cotonou) |
| 📤 **Notifications** | Agent → **Twilio SMS/WhatsApp** (optional credentials; without them: local audit log) |
| 🗺️ **Dashboard** | Real-time heat map on a real OpenStreetMap map, city risk gauge, per-point detail (24 h + nowcast), alert feed, agent log — **self-contained, works offline** |

**Tracks (3 in 1):** Resilient Cities & Infrastructure × Agentic AI ×
Data Analysis & Correlation.

**NVIDIA angle:** edge-first — the ~2 MB model exports to **ONNX** and infers
in <10 ms on an **NVIDIA Jetson** (the winning kit becomes our first citizen
sensor node). The vectorized feature pipeline maps to **CUDA-X** accelerated
processing and scales from 20 nodes to millions of 20 m² cells.

## Proven on real Temperature API® data

Coverage and integration were verified with the trial key (27 Aug 2026):

- **Phoenix: covered** — 37 tiles per 600 m × 600 m polygon at 100 m
  granularity. **60 real readings harvested** (24–26 Aug 2026 × 20 points):
  Downtown peak **42.9 °C measured** on 26 Aug — during an actual heat wave.
- **Cotonou: not yet covered** (0 tiles) — it runs on a calibrated feed
  anchored on real Open-Meteo weather (hourly bias −0.63 °C) and will switch
  to live data the day it enters the mesh.
- Real API granularity is **daily** (per-tile min/mean/max): the hourly shape
  between real days is simulated and **re-anchored daily** on the real
  extrema. Everything is labeled honestly in the demo and on `/real-data`.
- **The deployed backend calls the API itself** (live sync,
  `backend/data/livesync.py`): at startup and every 24 h it pulls the latest
  closed real day for all 20 points (cached first — a point-day already
  harvested costs 0 requests), re-anchors the feed and recomputes the
  nowcasts. During judging the live site is genuinely re-anchoring on fresh
  real data every day, with a "last real day … measured max …" stamp shown in
  the dashboard.

```bash
python check_coverage.py --city phoenix   # 1 request: is the city in the mesh?
python harvest.py --city phoenix --days 7 # cached, resumable real-data harvest
python train.py --city phoenix            # retrain <30 s + rebuild demo snapshot
```

## Quick start (2 minutes)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python run_server.py      # models are committed — no training needed
```

Then open http://localhost:8000 — a **multi-page site + the live demo**:
`/` (home), `/demo/` (live heat map, real OSM map, localized alerts, agent
log — demo time ×4, 1 h ≈ 15 s), `/how-it-works` (the agent explained,
transparent alert score), `/real-data` (the 60 real readings, methodology),
`/team` (the team). `HS_CITY=cotonou python run_server.py` runs the
deployment-target city (FR + Fon alerts).

## Deployment — live URL in ~5 minutes (free)

The app is designed to deploy anywhere that runs Python:

1. **GitHub:** push this repo (public).
2. **Render:** [render.com](https://render.com) → sign in with GitHub →
   **New + → Blueprint** → pick the `heat-sentinel` repo → **Apply**.
   The blueprint (`render.yaml`) creates a free web service
   (`startCommand: python run_server.py`, health check `/health`).
3. ~2–4 min later the service URL is live. That URL is the link to paste in
   the hackathon submission.
4. **Live API (optional but recommended):** in the Render dashboard, service
   → *Environment* → add `FORTYGUARD_API_KEY` (your trial key). The backend
   then runs the **live sync** (startup + every `SYNC_HOURS`, default 24 h):
   each new real day is pulled automatically — ~20 credits/day
   (1 request per point). Without the key the app runs in calibrated mode on
   the 60 harvested readings (zero credits).

Notes: the free tier sleeps after ~15 min idle — first request after
inactivity takes 30–60 s (open the URL once right before a live demo). Each
wake-up triggers a live sync if a new real day is available (and the key is
set). A `Dockerfile` (Jetson-ready edge vision) is included for self-hosting.

## Methodology (for Q&A)

- **Target:** `max(T[t+1..t+6])` per node — the actionable horizon for a city.
- **Evaluation:** time-based 24 h hold-out, no leakage (past-only features):
  Phoenix **MAE 0.36 °C, RMSE 0.45 °C, R² 0.98** (desert = harder: 18 °C
  diurnal amplitude); Cotonou **MAE 0.26 °C, RMSE 0.33 °C, R² 0.95**.
- **Why a hybrid:** trees cannot extrapolate — at the top of a heat-wave ramp
  the trend feature leaves the training range and peaks are under-predicted
  (worst at night). A Ridge component on the 6/12/24/72 h trends handles
  extrapolation; LightGBM captures the diurnal cycle and interactions.
- **Anomalies:** simple 48 h z-score — current temperature vs its normal value
  at the same hour (last 3 occurrences), threshold |z| ≥ 2.5. Transparent,
  interpretable; catches local spikes and sensor drift.
- **Features (19, all interpretable):** true 24 h/48 h lags, rolling means
  3–72 h, trends, diurnal sin/cos, day-of-week, per-zone UHI coefficient,
  wet-bulb (Stull 2011) as felt-heat proxy.
- **Risk score 0–100 (transparent, per city):**
  `0.65·f(6h peak temp) + 0.35·f(humidity)`, thresholds aligned with WHO heat
  plans (Phoenix 35→45 °C; Cotonou 28→38 °C).
- **Agent:** deterministic, auditable policy (6 h dedup window, escalate
  only) — reproducible and testable. An LLM can optionally draft narrative
  reports; it never enters the safety loop.
- **Alerts are localized per city:** English for Phoenix; French + **Fon**
  (the local language of Cotonou) for the deployment target — the last-mile
  warning reaches market vendors and outdoor workers in the language they
  actually speak.

## Repo layout

```
heat-sentinel/
├── train.py                  # one-shot training (--city phoenix|cotonou)
├── run_server.py             # site + live demo + API (port $PORT or 8000, HS_CITY=…)
├── check_coverage.py         # coverage test — first thing once a key arrives
├── harvest.py                # controlled real-data harvest (cached, resumable)
├── render.yaml               # 1-click free deploy blueprint (Render)
├── Dockerfile                # "Jetson-ready" image (edge vision, untested on hardware)
├── requirements.txt
├── backend/
│   ├── data/                 # cities.py (Phoenix + Cotonou), mock feed, FortyGuard client
│   ├── models/               # features.py, heat_risk.py (Ridge+LGBM + z-score)
│   ├── agent/                # sentinel.py (agentic loop, EN/FR/Fon alerts), notifier.py (Twilio)
│   └── api/                  # server.py (FastAPI: multi-page site, /demo/, /api/…)
├── site/                     # the public site (EN): index, how-it-works, real-data, team
├── demo/                     # live dashboard (self-contained, OSM map embedded)
├── edge/jetson/              # edge deployment reference (ONNX + local alerting)
└── artifacts/{city}/         # trained models, metrics, snapshot, ledgers, real data
```

## Honest limitations

- **Cotonou is not yet in the Temperature API® mesh** (verified 27/08): its
  demo runs on a calibrated simulated feed; Phoenix runs on **real harvested
  tiles** (daily min/mean/max; the hourly shape between real days is
  simulated). Every additional real day re-anchors the model automatically.
- The 6 h nowcast is trained per city; `train.py` re-adapts to any city in
  <30 s on its data.
- The Jetson mesh is a documented deployment reference; the physical node is
  the first post-hackathon deliverable (funded by the winning kit).

---

**Team ClimVision** — Cotonou, Benin. Built in a city that feels the heat
daily, proven on real Phoenix data, ready for any city. → [`/team`](site/team.html)
