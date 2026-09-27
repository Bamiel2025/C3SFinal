"""
Point d'entrée Vercel.

Le runtime Python de Vercel cherche un objet ASGI/WSGI nommé `app` dans un
fichier `app.py`, `index.py`, `main.py`… situé à la racine, dans `src/`,
`app/` ou `api/`. Ce module fait donc office de simple adaptateur : il place la
racine du projet sur `sys.path` puis reprend l'application définie dans
`c3s2.server`.

En local, c'est `run_local.py` (uvicorn) qui sert le même objet.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from c3s2.server import app  # noqa: E402,F401 - objet ASGI attendu par Vercel

__all__ = ["app"]
