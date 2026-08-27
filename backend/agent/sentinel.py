"""SentinelAgent — la couche AGENTIQUE de HeatSentinel.

Boucle Monitor → Predict → Decide → Act, sans dépendance LLM (fiable
hors-ligne, latence < 5 s sur CPU). Le modèle (heat_risk.py) PRÉDIT;
l'agent DÉCIDE: il arbitre les alertes (déduplication, escalade uniquement),
rédige les messages **FR + fon**, déclenche les **notifications**
(Twilio SMS/WhatsApp, fallback journal local), et tient un registre
d'audit (JSONL).

Brouillons en fon: à faire valider par un locuteur natif avant usage public.
"""

from __future__ import annotations

import json
import os
from collections import deque
from datetime import datetime

from ..models.heat_risk import LEVEL_EN, LEVEL_FR

# ---------- brouillons fon (à faire valider par un natif) ----------
LEVEL_FON = {
    "green": "",
    "yellow": "Lɛ nyuɖu — tɔ nyǐ.",                       # surveille la chaleur — bois de l'eau
    "orange": "Nyuɖu nyu — tɔ nyǐ!",                        # la chaleur est là — bois de l'eau
    "red": "Nyuɖu gbã nyu — tɔ nyǐ, jɔ mɛ tɔn 14h–17h!",    # forte chaleur — bois de l'eau, reste au domicile 14h-17h
    "black": "Nyuɖu gbã gbã! Tɔ nyǐ, jɔ mɛ tɔn!",           # chaleur extrême ! bois de l'eau, rentre
}

ACTIONS_FR = {
    "black": [
        "Ouvrir un centre de rafraîchissement (délai 30 min)",
        "Alerte hôpital : vigilance coup de chaleur",
        "Suspendre le travail extérieur 14h–17h",
        "Activer les points d'eau : Port, Zongo, Cadjehoun",
    ],
    "red": [
        "Pré-positionner eau et glaces sur la zone",
        "Masures de travail extérieur — ombrage toutes les 45 min",
        "Visites prioritaires des personnes vulnérables",
    ],
    "orange": [
        "Ombrage et hydratation renforcés (travailleurs extérieurs)",
        "Suivi renforcé des zones denses",
    ],
    "yellow": [
        "Consigne publique : hydratation, éviter 14h–17h",
        "Surveillance continue",
    ],
    "green": [],
}

ACTIONS_EN = {
    "black": [
        "Open a cooling center (within 30 min)",
        "Hospital alert: heatstroke watch",
        "Suspend outdoor work 2–5 PM",
        "Activate water points: Port, Zongo, Cadjehoun",
    ],
    "red": [
        "Pre-position water & ice on the zone",
        "Outdoor work breaks — shade every 45 min",
        "Priority visits for vulnerable residents",
    ],
    "orange": [
        "Enhanced shade & hydration for outdoor workers",
        "Reinforced monitoring of dense districts",
    ],
    "yellow": [
        "Public advisory: hydrate, avoid 2–5 PM",
        "Continuous monitoring",
    ],
    "green": [],
}

DEDUP_WINDOW_S = 6 * 3600  # en mode démo 1h≈15s → 45 min simulées


def make_alert(state: dict, ts: datetime, node: dict, city: str = "cotonou") -> dict:
    level = state["level"]
    fr, en = LEVEL_FR[level], LEVEL_EN[level]
    action_fr = ACTIONS_FR[level][0] if ACTIONS_FR[level] else "Aucune action requise"
    action_en = ACTIONS_EN[level][0] if ACTIONS_EN[level] else "No action required"
    anomaly_fr = " · ⚠ anomalie détectée (z-score 48 h : vérifier pic local / capteur)" if state.get("anomaly") else ""
    return {
        "ts": ts.isoformat(),
        "node_id": state["node_id"],
        "node": node["name"],
        "level": level,
        "level_fr": fr,
        "level_en": en,
        "t_now": state["t_now"],
        "tmax6h": state["tmax6h"],
        "score": state["score"],
        "anomaly": bool(state.get("anomaly")),
        "message_fr": f"[{fr}] {node['name']}: pic {state['tmax6h']:.1f} °C prévu 6 heures à l'avance (risque {state['score']:.0f}/100). {action_fr}{anomaly_fr}",
        "message_en": f"[{en}] {node['name']}: peak {state['tmax6h']:.1f} °C in the next 6 h (risk {state['score']:.0f}/100). {action_en}",
        "message_fon": LEVEL_FON.get(level, "") if city == "cotonou" else "",
        "actions_fr": ACTIONS_FR[level],
        "actions_en": ACTIONS_EN[level],
    }


class SentinelAgent:
    def __init__(self, ledger_path: str, city: str = "cotonou"):
        self.ledger_path = ledger_path
        self.city = city
        self.alerts: deque = deque(maxlen=100)
        self.events: deque = deque(maxlen=120)
        self.notifications: deque = deque(maxlen=100)
        self._last: dict[str, tuple[int, float]] = {}
        os.makedirs(os.path.dirname(ledger_path), exist_ok=True)

    def reset(self):
        """Remise à zéro (boucle de simulation) : réautorise les alertes."""
        self._last.clear()

    def _log(self, ts: datetime, etype: str, node: str, text: str):
        ev = {"ts": ts.isoformat(), "type": etype, "node": node, "text": text}
        self.events.append(ev)
        return ev

    def cycle(self, ts: datetime, states: list[dict], nodes_by_id: dict) -> list[dict]:
        """Un cycle d'agent: surveille les points, émet les alertes nécessaires."""
        new_events: list[dict] = []

        # 1. MONITOR — scan de tous les points de mesure
        n_hot = sum(1 for s in states if s["score"] >= 50)
        e = self._log(ts, "monitor", "—",
                      f"scan de {len(states)} points · {n_hot} au-dessus de seuil · "
                      f"max {max(s['t_now'] for s in states):.1f} °C")
        new_events.append(e)

        # 2. DECIDE — top risques, dedup + escalade uniquement
        ranked = sorted(states, key=lambda s: (-s["score"], -s["tmax6h"]))
        for s in ranked[:6]:
            if s["score"] < 45 and not s.get("anomaly"):
                continue
            rank = {lv: i for i, lv in enumerate(LEVELS)}.get(s["level"], 0)
            prev = self._last.get(s["node_id"])
            now = ts.timestamp()
            if prev and prev[0] >= rank and (now - prev[1]) < DEDUP_WINDOW_S:
                continue
            node = nodes_by_id[s["node_id"]]
            alert = make_alert(s, ts, node, self.city)
            self._last[s["node_id"]] = (rank, now)
            self.alerts.appendleft(alert)
            with open(self.ledger_path, "a") as f:
                f.write(json.dumps(alert, ensure_ascii=False) + "\n")
            e = self._log(ts, "alert", node["name"], alert["message_fr"])
            new_events.append(e)

            # 3. ACT — notification (Twilio SMS/WhatsApp ou journal local)
            from .notifier import send_alert
            rec = send_alert(alert)
            self.notifications.appendleft(rec)
            ch = rec.get("channel", "local")
            e = self._log(ts, "act", node["name"],
                          f"→ notification {ch} envoyée · {alert['actions_fr'][0] if alert['actions_fr'] else 'veille'}")
            new_events.append(e)

        # INSIGHT — synthèse quotidienne (6h00 locale)
        if (ts.hour + (0 if self.city == "phoenix" else 1)) % 24 == 6:
            top = max(states, key=lambda s: s["tmax6h"])
            e = self._log(ts, "insight", "—",
                          f"briefing: pic prévu {top['tmax6h']:.1f} °C — {nodes_by_id[top['node_id']]['name']}")
            new_events.append(e)

        return new_events


# alias pour compatibilité
from ..models.heat_risk import LEVELS  # noqa: E402
