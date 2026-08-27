"""Villes supportées par HeatSentinel : nœuds, climat simulé, seuils de score.

Cotonou = ville de démo principale (angle local, Hackathon'26).
Phoenix  = PLAN B de démo si Cotonou n'est pas couverte par la Temperature API®
(fortyguard couvre surtout les US + quelques pays — à vérifier avec
check_coverage.py dès réception de la clé). Cotonou reste alors la cible
de déploiement dans le pitch.

Changer de ville :  HS_CITY=phoenix python run_server.py
(le modèle est auto-entraîné pour la ville au premier lancement)
"""

COTONOU_NODES = [
    {"id": "CTO-01", "name": "Port Autonome", "lat": 6.346, "lon": 2.422, "uhi": 2.8, "zone": "industrial"},
    {"id": "CTO-02", "name": "Godomey",       "lat": 6.308, "lon": 2.384, "uhi": 1.8, "zone": "industrial"},
    {"id": "CTO-03", "name": "Akpakpa",       "lat": 6.387, "lon": 2.408, "uhi": -0.4, "zone": "beach"},
    {"id": "CTO-04", "name": "Zongo",         "lat": 6.357, "lon": 2.405, "uhi": 1.4, "zone": "dense"},
    {"id": "CTO-05", "name": "Mèto",          "lat": 6.375, "lon": 2.413, "uhi": 1.1, "zone": "dense"},
    {"id": "CTO-06", "name": "Cadjehoun",     "lat": 6.392, "lon": 2.429, "uhi": 1.3, "zone": "dense"},
    {"id": "CTO-07", "name": "Gbégamey",      "lat": 6.383, "lon": 2.399, "uhi": 0.9, "zone": "dense"},
    {"id": "CTO-08", "name": "Sègbéya",       "lat": 6.399, "lon": 2.446, "uhi": 1.0, "zone": "mixed"},
    {"id": "CTO-09", "name": "Fidjrossè",     "lat": 6.390, "lon": 2.463, "uhi": 1.2, "zone": "mixed"},
    {"id": "CTO-10", "name": "Agla",          "lat": 6.338, "lon": 2.469, "uhi": 1.5, "zone": "mixed"},
    {"id": "CTO-11", "name": "Kèrékougou",    "lat": 6.330, "lon": 2.446, "uhi": 1.1, "zone": "mixed"},
    {"id": "CTO-12", "name": "Hègo",          "lat": 6.425, "lon": 2.462, "uhi": 0.8, "zone": "mixed"},
    {"id": "CTO-13", "name": "Avotrou",       "lat": 6.445, "lon": 2.471, "uhi": 0.7, "zone": "mixed"},
    {"id": "CTO-14", "name": "Dèguè",         "lat": 6.475, "lon": 2.501, "uhi": 0.9, "zone": "mixed"},
    {"id": "CTO-15", "name": "Toffo",         "lat": 6.492, "lon": 2.521, "uhi": 1.6, "zone": "industrial"},
    {"id": "CTO-16", "name": "Zè",            "lat": 6.361, "lon": 2.476, "uhi": 1.0, "zone": "mixed"},
    {"id": "CTO-17", "name": "Cinkassé",      "lat": 6.411, "lon": 2.502, "uhi": 1.4, "zone": "mixed"},
    {"id": "CTO-18", "name": "Bèkoko",        "lat": 6.322, "lon": 2.456, "uhi": 0.9, "zone": "mixed"},
    {"id": "CTO-19", "name": "Minoukpa",      "lat": 6.353, "lon": 2.481, "uhi": 1.2, "zone": "mixed"},
    {"id": "CTO-20", "name": "Aïssè",         "lat": 6.349, "lon": 2.516, "uhi": 0.8, "zone": "mixed"},
]

PHOENIX_NODES = [
    {"id": "PHX-01", "name": "Downtown",        "lat": 33.448, "lon": -112.074, "uhi": 2.4, "zone": "dense"},
    {"id": "PHX-02", "name": "Sky Harbor",      "lat": 33.437, "lon": -112.008, "uhi": 2.8, "zone": "industrial"},
    {"id": "PHX-03", "name": "Tempe",           "lat": 33.429, "lon": -111.939, "uhi": 1.8, "zone": "dense"},
    {"id": "PHX-04", "name": "Mesa",            "lat": 33.415, "lon": -111.834, "uhi": 1.5, "zone": "mixed"},
    {"id": "PHX-05", "name": "Chandler",        "lat": 33.306, "lon": -111.841, "uhi": 1.4, "zone": "mixed"},
    {"id": "PHX-06", "name": "Gilbert",         "lat": 33.354, "lon": -111.789, "uhi": 1.3, "zone": "mixed"},
    {"id": "PHX-07", "name": "Scottsdale",      "lat": 33.516, "lon": -111.924, "uhi": 1.2, "zone": "mixed"},
    {"id": "PHX-08", "name": "Glendale",        "lat": 33.538, "lon": -112.186, "uhi": 1.6, "zone": "dense"},
    {"id": "PHX-09", "name": "Avondale",        "lat": 33.435, "lon": -112.348, "uhi": 1.2, "zone": "mixed"},
    {"id": "PHX-10", "name": "Goodyear",        "lat": 33.439, "lon": -112.353, "uhi": 1.9, "zone": "industrial"},
    {"id": "PHX-11", "name": "Queen Creek",     "lat": 33.339, "lon": -111.763, "uhi": 1.1, "zone": "mixed"},
    {"id": "PHX-12", "name": "Deer Valley",     "lat": 33.592, "lon": -111.978, "uhi": 1.0, "zone": "mixed"},
    {"id": "PHX-13", "name": "Encanto",         "lat": 33.476, "lon": -112.130, "uhi": 1.3, "zone": "mixed"},
    {"id": "PHX-14", "name": "Biltmore",        "lat": 33.510, "lon": -112.005, "uhi": 1.5, "zone": "dense"},
    {"id": "PHX-15", "name": "Papago Park",     "lat": 33.555, "lon": -111.973, "uhi": -1.2, "zone": "park"},
    {"id": "PHX-16", "name": "South Mountain",  "lat": 33.338, "lon": -112.060, "uhi": -1.5, "zone": "park"},
    {"id": "PHX-17", "name": "Saguaro NP",      "lat": 33.328, "lon": -111.780, "uhi": -1.8, "zone": "park"},
    {"id": "PHX-18", "name": "Roosevelt Row",   "lat": 33.455, "lon": -112.071, "uhi": 2.2, "zone": "dense"},
    {"id": "PHX-19", "name": "Garfield Ctr",    "lat": 33.460, "lon": -112.074, "uhi": 2.0, "zone": "dense"},
    {"id": "PHX-20", "name": "Camelback",       "lat": 33.515, "lon": -111.960, "uhi": -0.8, "zone": "park"},
]

CITIES = {
    "cotonou": {
        "name": "Cotonou", "country": "Bénin", "tz_hours": 1, "lat": 6.36, "lon": 2.42,
        "population": "≈ 700 000 (commune) · 1,5 M+ (agglomération)",
        "heat_pitch": "chaleur humide tropicale — ressenti > 40 °C avec l'humidité (max moyens 31–32 °C, dépassés en vague de chaleur)",
        "map": {"label": "GOLFE DE GUINÉE", "coast": True, "x0": 2.365, "x1": 2.545, "y0": 6.28, "y1": 6.52},
        "scoring": {"t_lo": 28.0, "t_hi": 38.0, "rh_lo": 40.0, "rh_hi": 90.0},
        "climate": {
            "base": 28.4, "uhi_w": 0.45, "hw_delta": 5.5,
            "amp": 1.0, "amp_uhi": 0.25, "hw_amp": 1.2,
            "season_amp": 1.8, "season_doy": 60.0,
            "rh_base": 78.0, "rh_amp": 8.0, "rh_hw": 2.0, "rh_noise": 3.0, "rh_min": 55.0, "rh_max": 97.0,
            "wind_base": 12.0, "wind_amp": 3.5, "wind_noise": 1.5, "wind_min": 5.0, "wind_max": 22.0,
            "peak_h": 15.2, "ar_sigma": 0.15,
        },
        "nodes": COTONOU_NODES,
    },
    "phoenix": {
        "name": "Phoenix", "country": "USA — Arizona", "tz_hours": -7, "lat": 33.45, "lon": -112.07,
        "population": "≈ 1,6 M (ville) · 4,9 M (métropole)",
        "heat_pitch": "chaleur désertique — 40–43 °C réguliers en août, ~43–44 °C en vague de chaleur",
        "map": {"label": "SONORAN DESERT", "coast": False, "x0": -112.45, "x1": -111.65, "y0": 33.25, "y1": 33.65},
        "scoring": {"t_lo": 35.0, "t_hi": 45.0, "rh_lo": 10.0, "rh_hi": 40.0},
        "climate": {
            # Calibré sur Open-Meteo réelles 2026-08-21→27 (vague de chaleur en cours :
            # moy 38,5 °C · min 29 / max 46,3 · pic local 15–16 h · RH nuit 26–52 % / jour 10–13 %)
            "base": 35.7, "uhi_w": 0.9, "hw_delta": 0.5,
            "amp": 6.5, "amp_uhi": 0.3, "hw_amp": 0.4,
            "season_amp": 2.0, "season_doy": 190.0,
            "rh_base": 35.0, "rh_amp": 23.0, "rh_hw": 8.0, "rh_noise": 3.0, "rh_min": 5.0, "rh_max": 55.0,
            "wind_base": 2.0, "wind_amp": 1.0, "wind_noise": 0.8, "wind_min": 0.5, "wind_max": 9.0,
            "peak_h": 15.5, "ar_sigma": 0.25,
        },
        "nodes": PHOENIX_NODES,
    },
}

# Plan B : Cotonou n'est PAS couvert par la Temperature API® (vérifié 2026-08-27,
# 0 tuiles). La démo tourne donc sur Phoenix (couvert, données réelles). Cotonou
# reste la cible de déploiement — l'afficher avec HS_CITY=cotonou / --city cotonou.
DEFAULT_CITY = "phoenix"


def get_city(name: str | None = None) -> dict:
    name = (name or DEFAULT_CITY).lower()
    if name not in CITIES:
        raise ValueError(f"ville inconnue: {name} (disponibles: {list(CITIES)})")
    return CITIES[name]
