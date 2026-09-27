"""
Serveur de développement local.

    python run_local.py            # http://127.0.0.1:8000
    python run_local.py --port 9000

L'application servie est exactement celle déployée sur Vercel : même code,
même API, mêmes fichiers statiques. La seule différence est le dossier de
cache (`data/cache` en local, `/tmp` sur Vercel).
"""

from __future__ import annotations

import argparse
import sys

import uvicorn


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="C3S² — serveur de développement")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true", help="redémarrage à chaque modification")
    args = parser.parse_args(argv)

    print(f"C3S² Climate Lab — http://{args.host}:{args.port}")
    uvicorn.run("c3s2.server:app", host=args.host, port=args.port, reload=args.reload)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
