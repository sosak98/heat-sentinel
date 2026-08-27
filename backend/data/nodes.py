"""Réseau de points de mesure — ré-export rétrocompatible (Cotonou par défaut).

La source de vérité est backend/data/cities.py (multi-villes, plan B Phoenix).
La donnée provient du maillage de la Temperature API® de FortyGuard
(résolution 20 m², température modélisée à 2 m au-dessus du sol) —
nous n'installons aucun capteur : le maillage est LEUR produit.
"""

from .cities import CITIES, DEFAULT_CITY, get_city

CITY = get_city(DEFAULT_CITY)
NODES = CITY["nodes"]
NODE_BY_ID = {n["id"]: n for n in NODES}
