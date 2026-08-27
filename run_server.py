#!/usr/bin/env python3
"""Démo HeatSentinel — dashboard + API temps réel.

Port : variable d'environnement PORT (défaut 8000) — rendu compatible
Render/Railway/Fly qui injectent PORT.
Ville active : HS_CITY=phoenix (défaut, ville 100 % données réelles) | cotonou
(cible de déploiement, non couverte par la mesh à ce jour).
Source de données : .env (FORTYGUARD_API_KEY) si présente, sinon flux
calibré sur les lectures réelles déjà récoltées (artifacts/).
"""

import os

import uvicorn

from backend.envload import load_env

load_env()

if __name__ == "__main__":
    uvicorn.run("backend.api.server:app", host="0.0.0.0",
                port=int(os.environ.get("PORT", 8000)), log_level="info")
