"""HeatSentinel — serveur de démo (FastAPI).

Lance le dashboard (self-contained) + l'API temps réel:
  GET /                  → dashboard
  GET /api/overview      → état de la ville (points, risques, alertes, agent)
  GET /api/nodes/{id}    → détail d'un point (24 h + nowcast 6 heures à l'avance)
  GET /api/health        → santé + source de données

Ville active : HS_CITY=phoenix (défaut, ville 100 % données réelles) | cotonou
(cible de déploiement, non couverte par la mesh à ce jour). Le modèle de la
ville est auto-entraîné au premier lancement si absent.

Mode SIMULATED : le temps avance de 1 h toutes les 15 s pour la démo.
Avec FORTYGUARD_API_KEY, le flux est branché sur la Temperature API® réelle
(le maillage 20 m² est celui de FortyGuard — nous n'installons aucun capteur).
"""

from __future__ import annotations

import asyncio
import os

from fastapi import FastAPI
from fastapi.responses import FileResponse

from ..agent.sentinel import SentinelAgent
from ..data.cities import get_city
from ..data.fortyguard import is_real
from ..data.livesync import sync_city
from ..data.mock import generate_history
from ..data.real_data import calibrate_history, real_summary
from ..models.features import FEATURES, build_features
from ..models.heat_risk import BASE_ART, HeatSentinel, train

CITY_KEY = os.environ.get("HS_CITY", "phoenix")
CFG = get_city(CITY_KEY)
BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEMO_HTML = os.path.join(BASE, "demo", "dashboard.html")
SITE_DIR = os.path.join(BASE, "site")
SITE_PAGES = {
    "/": "index.html",
    "/how-it-works": "how-it-works.html",
    "/real-data": "real-data.html",
    "/team": "team.html",
}
LEDGER = os.path.join(BASE_ART, CITY_KEY, "alert_ledger.jsonl")

app = FastAPI(title=f"HeatSentinel — {CFG['name']} Urban Heat Intelligence")


class Engine:
    """Moteur temps réel : maillage (mock ou API) → features → modèle → agent."""

    def __init__(self):
        self.city = CITY_KEY
        self.nodes = CFG["nodes"]
        self.nodes_by_id = {n["id"]: n for n in self.nodes}
        art = os.path.join(BASE_ART, self.city)
        if not os.path.exists(os.path.join(art, "meta.json")):
            print(f"[HeatSentinel] modèle {self.city} absent → entraînement rapide…")
            train(generate_history(days=8, seed=42, city=self.city), city=self.city)
        self.hs = HeatSentinel(self.city)
        # LIVE SYNC : dernier rapport de sync (None tant qu'il n'a pas tourné)
        self.sync_info: dict | None = None
        self._rebuild()
        self.agent = SentinelAgent(LEDGER, city=self.city)
        self.step(run_agent=True)  # premier cycle: le dashboard démarre avec du contenu

    def _rebuild(self):
        """(Re)construit la série : flux simulé recalé sur les lectures
        RÉELLES du CSV + prédictions du modèle. À re-appeler après un
        live sync ayant apporté de nouvelles données."""
        self.hist, self.n_cal = calibrate_history(
            generate_history(days=8, seed=42, city=self.city), self.city)
        self.real = real_summary(self.city)
        d = build_features(self.hist, city=self.city).dropna(subset=FEATURES)
        d = self.hs.predict_matrix(d)
        self.data = d.sort_values(["ts", "node_id"]).reset_index(drop=True)
        self.by_ts = {ts: grp for ts, grp in self.data.groupby("ts", sort=True)}
        self.ts_list = list(self.by_ts.keys())
        self.piv = self.data.pivot(index="ts", columns="node_id", values="temp_c")
        self.ptr = max(0, len(self.ts_list) - 30)

    def step(self, run_agent: bool = True):
        if self.ptr >= len(self.ts_list) - 1:
            # boucle de démo: on revient 42 h en arrière (vague de chaleur en cours)
            self.ptr = len(self.ts_list) - 42
            self.agent.reset()
        else:
            self.ptr += 1
        ts = self.ts_list[self.ptr]
        if run_agent:
            self.agent.cycle(ts.to_pydatetime(), self.states(ts), self.nodes_by_id)
        return ts

    def states(self, ts) -> list[dict]:
        out = []
        for _, r in self.by_ts[ts].iterrows():
            nid = r["node_id"]
            n = self.nodes_by_id[nid]
            out.append({
                "node_id": nid, "name": n["name"], "lat": n["lat"], "lon": n["lon"],
                "zone": n["zone"], "uhi": n["uhi"],
                "t_now": round(float(r["temp_c"]), 1),
                "rh": round(float(r["rh_pct"]), 1),
                "wind": round(float(r["wind_ms"]), 1),
                "wb_gt": round(float(r["wb_gt"]), 1),
                "tmax6h": round(float(r["tmax6h"]), 1),
                "score": round(float(r["score"]), 1),
                "level": str(r["level"]),
                "anomaly": int(r["anomaly"]),
            })
        return out

    def overview(self) -> dict:
        ts = self.ts_list[self.ptr]
        states = self.states(ts)
        by_level: dict[str, int] = {}
        for s in states:
            by_level[s["level"]] = by_level.get(s["level"], 0) + 1
        top = max(states, key=lambda s: s["score"])
        series = {}
        window = self.piv.loc[:ts].tail(24)
        for n in self.nodes:
            series[n["id"]] = [
                [t.strftime("%d/%m %H:%M"), round(float(v), 1)] for t, v in window[n["id"]].items()
            ]
        m = self.hs.meta
        si = self.sync_info
        if si and si.get("ok") and si.get("latest"):
            mode = "live-sync"
            li = si["latest"]
            source = (f"Temperature API® mesh (20 m², 2 m above ground) — live sync "
                      f"on the server · last real day {li['date']} "
                      f"(measured max {li['max_c']} °C, {li['node']}) · feed re-anchored "
                      f"on {si.get('n_readings', '?')} real readings")
        elif self.n_cal:
            mode = "calibrated"
            source = (f"Temperature API® mesh (20 m², 2 m above ground) — simulation "
                      f"re-anchored on {self.n_cal} real readings (Temperature API®)")
        else:
            mode = "fortyguard" if is_real() else "simulated"
            source = ("FortyGuard Temperature API® (20 m², 2 m above ground)"
                      if is_real() else
                      "Simulated Temperature API® mesh feed (identical schema), calibrated on real Open-Meteo weather")
        return {
            "mode": mode,
            "speed": "1h ≈ 15s (démo)",
            "ts": ts.isoformat(),
            "clock_local": f"{(ts.hour + CFG['tz_hours']) % 24:02d}:{ts.minute:02d}",
            "city": {
                "name": CFG["name"], "country": CFG["country"],
                "population": CFG["population"], "heat_pitch": CFG["heat_pitch"],
                "map": CFG["map"],
                "source": source,
            },
            "live_sync": si,
            "nodes": states,
            "stats": {
                "nodes": len(states),
                "max_temp": max(s["t_now"] for s in states),
                "avg_score": round(float(sum(s["score"] for s in states) / len(states)), 1),
                "by_level": by_level,
                "hottest": top["name"],
                "hottest_score": top["score"],
            },
            "series": series,
            "model": {
                "name": f"Hybride Ridge+LightGBM nowcast {m['metrics']['horizon_h']} h + z-score 48 h",
                "mae": m["metrics"]["mae"],
                "rmse": m["metrics"]["rmse"],
                "r2": m["metrics"]["r2"],
                "size_kb": m["model_size_kb"],
                "edge": "ONNX-ready · NVIDIA Jetson",
            },
            "alerts": list(self.agent.alerts)[:12],
            "agent_events": list(self.agent.events)[-14:][::-1],
            "notifications": list(self.agent.notifications)[:5],
            "real": self.real,
        }

    def node_detail(self, nid: str) -> dict:
        ts = self.ts_list[self.ptr]
        st = next(s for s in self.states(ts) if s["node_id"] == nid)
        window = self.piv.loc[:ts].tail(24)[nid]
        st["series"] = [[t.strftime("%d/%m %H:%M"), round(float(v), 1)] for t, v in window.items()]
        st["alerts"] = [a for a in self.agent.alerts if a["node_id"] == nid][:6]
        return st


engine: Engine | None = None


@app.on_event("startup")
def _startup():
    global engine
    engine = Engine()
    asyncio.create_task(_loop())
    if is_real():
        asyncio.create_task(_sync_loop())


async def _loop():
    while True:
        await asyncio.sleep(15)
        engine.step()


async def _sync_loop():
    """LIVE SYNC : au démarrage puis toutes les SYNC_HOURS (défaut 24 h),
    le serveur appelle la Temperature API® pour les derniers jours réels
    terminés, puis recalibre le flux et recalcule les prédictions."""
    interval_h = int(os.environ.get("SYNC_HOURS", "24"))
    while True:
        if interval_h > 0:
            try:
                info = await asyncio.to_thread(
                    sync_city, CITY_KEY, int(os.environ.get("SYNC_MAX_DAYS", "3")))
                engine.sync_info = info
                if info.get("days_added"):
                    await asyncio.to_thread(engine._rebuild)
                    print(f"[HeatSentinel] live sync: +{info['days_added']} jour(s) réel(s) "
                          f"({info['requests']} req) → flux recalé, prédictions recalculées.")
                else:
                    print(f"[HeatSentinel] live sync: données à jour "
                          f"({info['requests']} req) — dernier jour réel: "
                          f"{(info.get('latest') or {}).get('date', '?')}")
            except Exception as e:
                print(f"[HeatSentinel] live sync error: {type(e).__name__}: {e}")
        await asyncio.sleep(max(1, interval_h) * 3600)


@app.get("/")
def index():
    return FileResponse(os.path.join(SITE_DIR, "index.html"))


@app.get("/demo")
@app.get("/demo.html")
def demo():
    return FileResponse(DEMO_HTML)


@app.get("/assets/{path:path}")
def assets(path: str):
    return FileResponse(os.path.join(SITE_DIR, "assets", path))


for _page in ("index", "how-it-works", "real-data", "team"):
    for _route in (f"/{_page}.html", f"/{_page}"):
        @app.get(_route)
        def _site(_f=_page + ".html"):
            return FileResponse(os.path.join(SITE_DIR, _f))


@app.get("/api/overview")
def overview():
    return engine.overview()


@app.get("/api/nodes/{nid}")
def node(nid: str):
    if nid not in engine.nodes_by_id:
        return {"error": "point introuvable"}
    return engine.node_detail(nid)


@app.get("/api/health")
@app.get("/health")
def health():
    return {
        "ok": True,
        "city": CITY_KEY,
        "data_source": ("calibrated" if (engine and engine.n_cal)
                        else ("fortyguard" if is_real() else "simulated")),
        "model_loaded": engine is not None,
    }
