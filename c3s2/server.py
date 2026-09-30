"""
Serveur FastAPI de C3S².

L'application est un ASGI unique exporté sous le nom `app` : c'est la forme
attendue par le runtime Python de Vercel (voir `api/index.py`). Elle sert
l'API JSON sous `/api/*` ; les fichiers statiques (HTML, CSS, JS, cartes,
fonds de carte) sont délivrés directement par le CDN Vercel depuis `public/`.

Règles de conception :

* une route = un objet métier simple, réponse JSON stable ;
* les erreurs métier ressortent en 4xx avec un message exploitable en français ;
* aucune clé, aucun secret ne figure jamais dans une réponse.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse

from . import activities, analysis, config, datasets, fields, heat, places, series, store
from .cds import ConnectionReport, diagnose_key, test_connection

PUBLIC_DIR = config.PROJECT_ROOT / "public"
INDEX_HTML = PUBLIC_DIR / "index.html"
#: PDF de corrigés : volontairement **hors** de `public/` pour qu'aucun hébergeur
#: statique ne les serve ; accès exclusivement via `/api/corriges` + code.
CORRIGES_DIR = config.PROJECT_ROOT / "corriges"

app = FastAPI(
    title="C3S² Climate Lab — API",
    version=config.APP_VERSION,
    description="API pédagogique ERA5 / Copernicus pour l'enseignement du climat.",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------------- #
# Gestion des erreurs
# --------------------------------------------------------------------------- #


@app.exception_handler(KeyError)
async def _key_error(_request: Request, exc: KeyError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"error": str(exc).strip("'\"")})


@app.exception_handler(ValueError)
async def _value_error(_request: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"error": str(exc)})


@app.exception_handler(FileNotFoundError)
async def _not_found(_request: Request, exc: FileNotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"error": str(exc)})


@app.exception_handler(RuntimeError)
async def _runtime_error(_request: Request, exc: RuntimeError) -> JSONResponse:
    return JSONResponse(status_code=503, content={"error": str(exc)})


@app.exception_handler(Exception)
async def _generic_error(_request: Request, exc: Exception) -> JSONResponse:  # noqa: BLE001
    return JSONResponse(status_code=500, content={"error": f"{type(exc).__name__} : {exc}"})


# --------------------------------------------------------------------------- #
# Métadonnées
# --------------------------------------------------------------------------- #


@app.get("/api/health")
def health() -> dict[str, Any]:
    """Sonde de disponibilité (utilisée par les tests et par Vercel)."""
    return {"status": "ok", "app": config.APP_NAME, "version": config.APP_VERSION}


@app.get("/api/config")
def get_config() -> dict[str, Any]:
    """
    Configuration visible par le client : environnement, état de la clé CDS,
    code enseignant attendu (jamais sa valeur).
    """
    cfg = config.resolve_cds_config()
    info = config.app_info()
    info.update(
        {
            "cds": cfg.as_dict(),
            "key_diagnosis": diagnose_key(cfg.key).as_dict(),
            "teacher_code_required": True,
            "reference_period": list(config.REFERENCE_PERIOD),
            "years": [config.FIRST_YEAR, config.LAST_DATA_YEAR],
            "precomputed": store.inventory(),
            "heat_coverage": heat.available(),
            "attribution": config.ERA5_ATTRIBUTION,
            "citation": config.ERA5_CITATION,
            "licence": config.ERA5_LICENCE,
        }
    )
    return info


@app.get("/api/places")
def get_places() -> dict[str, Any]:
    """Villes, domaines, variables, jeux de données et cartes disponibles."""
    return {
        "cities": [p.as_dict() for p in places.all_places()],
        "domains": [
            {"name": d.name, "area": list(d.area), "description": d.description}
            for d in places.DOMAINS
        ],
        "variables": [
            {
                "slug": v.slug,
                "label": v.label,
                "unit": v.unit,
                "kind": v.kind,
                "color": v.color,
                "description": v.description,
                "lesson": v.lesson,
            }
            for v in datasets.VARIABLES.values()
            if v.slug in datasets.EXPLORABLE_VARIABLES
        ],
        "datasets": [
            {
                "key": key,
                "label": d.label,
                "summary": d.summary,
                "frequency": d.frequency,
                "start_year": d.start_year,
                "resolution": d.resolution,
                "doc_url": d.doc_url,
                "licence": d.licence,
                "notes": d.notes,
            }
            for key, d in datasets.DATASETS.items()
        ],
        "maps": fields.list_maps(),
        "precomputed_cities": store.precomputed_cities_summary(),
    }


# --------------------------------------------------------------------------- #
# Séries temporelles
# --------------------------------------------------------------------------- #


@app.get("/api/series")
def get_series(
    cities: str = Query(..., description="Villes séparées par des virgules"),
    variable: str = Query("2m_temperature"),
    start: int = Query(config.FIRST_YEAR, ge=1940, le=config.LAST_DATA_YEAR),
    end: int = Query(config.LAST_DATA_YEAR, ge=1940, le=config.LAST_DATA_YEAR),
    source: str = Query("auto", pattern="^(auto|precomputed|cds|simulated)$"),
) -> dict[str, Any]:
    """
    Séries mensuelles + statistiques + narration climatique.

    `source=auto` (défaut) lit d'abord les CSV pré-calculés, puis le CDS, puis
    bascule sur une simulation signalée comme telle. `source=cds` force une
    vraie requête ERA5 (20 à 90 s).
    """
    city_list = [c.strip() for c in cities.split(",") if c.strip()]
    return series.get_series(
        city_list, variable, start, end, source=source, include_stats=True
    )


# --------------------------------------------------------------------------- #
# Activités et corrigés
# --------------------------------------------------------------------------- #


@app.get("/api/activities")
def get_activities(code: str | None = Query(None)) -> dict[str, Any]:
    """
    Liste des activités. Les corrigés (`expected`) ne sont renvoyés que si le
    code enseignant est fourni : sur un vidéoprojecteur, la fiche affichée aux
    élèves reste vierge.
    """
    unlocked = config.check_teacher_code(code)
    return {
        "unlocked": unlocked,
        "activities": activities.list_activities(with_answers=unlocked),
        "reference": list(config.REFERENCE_PERIOD),
    }


@app.post("/api/teacher/unlock")
async def teacher_unlock(request: Request) -> dict[str, Any]:
    """Vérifie le code enseignant (aucune valeur n'est stockée côté serveur)."""
    payload = await _json_body(request)
    ok = config.check_teacher_code(str(payload.get("code", "")))
    return {"ok": ok}


async def _json_body(request: Request) -> dict[str, Any]:
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001 - corps vide ou invalide
        return {}
    return body if isinstance(body, dict) else {}


# --------------------------------------------------------------------------- #
# Données journalières (activité canicule)
# --------------------------------------------------------------------------- #


@app.get("/api/heat")
def get_heat(
    cities: str = Query(...),
    start: int = Query(2010, ge=1940, le=config.LAST_DAILY_YEAR),
    end: int = Query(config.LAST_DAILY_YEAR, ge=1940, le=config.LAST_DAILY_YEAR),
    tmax: float = Query(35.0),
    tmin: float = Query(20.0),
) -> dict[str, Any]:
    """Séries journalières (maximum / minimum) et comptages de jours de chaleur."""
    city_list = [c.strip() for c in cities.split(",") if c.strip()]
    return heat.heat_payload(city_list, start, end, tmax_threshold=tmax, tmin_threshold=tmin)


# --------------------------------------------------------------------------- #
# Cartes
# --------------------------------------------------------------------------- #


@app.get("/api/maps/{map_id}")
def get_map(map_id: str) -> dict[str, Any]:
    """Carte statique pré-calculée (servie normalement depuis le CDN)."""
    return fields.load_map(map_id)


@app.post("/api/field")
async def get_field(request: Request) -> dict[str, Any]:
    """
    Champ spatial téléchargé en direct auprès du CDS.

    Route longue (30 à 90 s) : `vercel.json` lui accorde les 300 secondes
    maximales du plan Hobby.
    """
    payload = await _json_body(request)
    variable = payload.get("variable", "2m_temperature")
    area = payload.get("area")
    return fields.field_from_cds(
        variable,
        domain=payload.get("domain"),
        area=tuple(area) if isinstance(area, list) and len(area) == 4 else None,
        month=payload.get("month"),
        years=tuple(payload.get("years") or config.REFERENCE_PERIOD),  # type: ignore[arg-type]
        dataset_key=payload.get("dataset", "monthly_means"),
    )


# --------------------------------------------------------------------------- #
# Diagnostic CDS
# --------------------------------------------------------------------------- #


@app.post("/api/cds/test")
async def cds_test(request: Request) -> dict[str, Any]:
    """Teste la clé CDS ; `{"deep": true}` lance une vraie petite requête."""
    payload = await _json_body(request)
    cfg = config.resolve_cds_config()
    report: ConnectionReport = test_connection(cfg, deep=bool(payload.get("deep")))
    return {"config": cfg.as_dict(), "report": report.as_dict()}


# --------------------------------------------------------------------------- #
# Frontend
# --------------------------------------------------------------------------- #


@app.get("/api/corriges/{name}")
def get_corrige(name: str, code: str | None = Query(None)) -> Any:
    """Télécharge un PDF de corrigé — réservé au code enseignant (2027)."""
    if not config.check_teacher_code(code):
        return JSONResponse(
            status_code=403,
            content={"error": "Corrigé verrouillé : code enseignant requis (?code=...)."},
        )
    if Path(name).name != name or not name.endswith(".pdf"):
        return JSONResponse(status_code=400, content={"error": "Nom de fichier invalide."})
    path = CORRIGES_DIR / name
    if not path.is_file():
        return JSONResponse(status_code=404, content={"error": f"Corrigé introuvable : {name}"})
    return FileResponse(path, media_type="application/pdf", filename=name)


@app.get("/")
def index() -> Any:
    """Page d'accueil : fichier statique si présent, sinon renvoi CDN."""
    if INDEX_HTML.is_file():
        return FileResponse(INDEX_HTML)
    return RedirectResponse("/index.html")


@app.get("/{path:path}")
def spa_fallback(path: str, request: Request) -> Any:
    """
    Routage SPA : toute route inconnue renvoie `index.html`, ce qui permet des
    URL propres (`/activites`) même sur un hébergeur sans règle de réécriture.
    Les fichiers réellement présents dans `public/` sont servis tels quels ;
    un éventuel `*-corrige.pdf` déposé ici par erreur reste verrouillé.
    """
    if path.startswith("api/"):
        return JSONResponse(status_code=404, content={"error": f"Route inconnue : /{path}"})

    candidate = (PUBLIC_DIR / path).resolve()
    try:
        candidate.relative_to(PUBLIC_DIR.resolve())
    except ValueError:  # tentative de traversée de dossier
        return JSONResponse(status_code=400, content={"error": "Chemin invalide."})

    if candidate.name.endswith("-corrige.pdf") and not config.check_teacher_code(
        request.query_params.get("code")
    ):
        return JSONResponse(
            status_code=403,
            content={"error": "Corrigé verrouillé : code enseignant requis (?code=...)."},
        )

    if candidate.is_file():
        return FileResponse(candidate)
    if INDEX_HTML.is_file():
        return FileResponse(INDEX_HTML)
    return RedirectResponse("/")
