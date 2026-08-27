"""Chargement minimal de .env (sans dépendance).

La clé API vit dans .env (gitignored) — à appeler AVANT tout import de
backend.data.fortyguard, qui lit l'environnement au moment de l'import.
"""

import os


def load_env(path: str | None = None) -> None:
    path = path or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
