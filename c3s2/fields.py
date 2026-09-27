"""
Champs spatiaux (cartes climatiques).

Deux régimes coexistent :

* **statique** — `scripts/prepare_maps.py` télécharge les champs une fois et
  écrit des JSON dans `public/assets/maps/`. Le navigateur les récupère
  directement depuis le CDN Vercel : aucune fonction, aucun délai, aucune
  consommation de quota CDS.
* **en direct** — `field_from_cds()` interroge le CDS à la demande pour une
  variable, un mois et un domaine arbitraires (comptez 30 à 90 secondes).

Les deux produisent exactement la même structure JSON, si bien que le rendu
côté navigateur est identique.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import numpy as np

from . import analysis, cds, config, datasets, places

#: Dossier public des cartes statiques (servi par le CDN).
PUBLIC_MAPS_DIR = config.PROJECT_ROOT / "public" / "assets" / "maps"

#: Pas de sous-échelonnement cible, en degrés (0,25° ERA5 -> 0,5° affiché).
TARGET_STEP = 0.5
#: Nombre maximal de cellules conservées dans un JSON de carte.
MAX_CELLS = 14_000


# --------------------------------------------------------------------------- #
# Cartes statiques
# --------------------------------------------------------------------------- #


def list_maps() -> list[dict[str, Any]]:
    """Inventaire des cartes statiques disponibles."""
    index = PUBLIC_MAPS_DIR / "index.json"
    if not index.is_file():
        return []
    try:
        return json.loads(index.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):  # pragma: no cover
        return []


def load_map(map_id: str) -> dict[str, Any]:
    """Charge une carte statique par son identifiant."""
    if not map_id.replace("_", "").replace("-", "").isalnum():
        raise KeyError(f"Identifiant de carte invalide : {map_id!r}")
    path = PUBLIC_MAPS_DIR / f"{map_id}.json"
    if not path.is_file():
        raise KeyError(
            f"Carte inconnue : {map_id!r}. Disponibles : "
            f"{[m['id'] for m in list_maps()]}"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def save_static_map(map_id: str, payload: dict[str, Any]) -> Path:
    """
    Écrit une carte statique et met à jour l'inventaire `index.json`.

    L'inventaire ne contient pas les valeurs : il reste léger et peut être
    lu avant de charger la carte elle-même.
    """
    PUBLIC_MAPS_DIR.mkdir(parents=True, exist_ok=True)
    payload = {**payload, "id": map_id, "live": False, "url": f"/assets/maps/{map_id}.json"}
    (PUBLIC_MAPS_DIR / f"{map_id}.json").write_text(
        json.dumps(payload, separators=(",", ":")), encoding="utf-8"
    )

    index_path = PUBLIC_MAPS_DIR / "index.json"
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        index = []
    index = [m for m in index if m.get("id") != map_id]
    index.append(
        {k: v for k, v in payload.items() if k not in ("z", "u", "v", "request")}
    )
    index_path.write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
    return PUBLIC_MAPS_DIR / f"{map_id}.json"


def wind_map_from_cds(
    area: tuple[float, float, float, float],
    *,
    month: int,
    years: tuple[int, int] = config.REFERENCE_PERIOD,
) -> dict[str, Any]:
    """
    Carte de vent : vitesse (m/s) calculée à partir des composantes U et V,
    plus les deux composantes pour dessiner les flèches de circulation.
    """
    from .analysis import MONTH_LABELS_LONG

    dataset = datasets.get_dataset("monthly_means")
    y0 = max(int(years[0]), dataset.start_year)
    y1 = min(int(years[1]), config.LAST_COMPLETE_YEAR)
    request = datasets.build_monthly_request(
        ["10m_u_component_of_wind", "10m_v_component_of_wind"],
        list(range(y0, y1 + 1)),
        [month],
        list(area),
    )
    cfg = config.resolve_cds_config()
    if not cfg.is_configured:
        raise RuntimeError("Aucune clé CDS configurée : la carte de vent est indisponible.")

    t0 = time.perf_counter()
    path = cds.retrieve(cfg, dataset.id, request)
    with cds.open_dataset(path) as ds:
        u_da, _ = cds.to_display_units(cds.find_variable(ds, "10m_u_component_of_wind"), "10m_u_component_of_wind")
        v_da, _ = cds.to_display_units(cds.find_variable(ds, "10m_v_component_of_wind"), "10m_v_component_of_wind")
        u_field = cds.field2d(u_da, month=month)
        v_field = cds.field2d(v_da, month=month)

    lat = np.asarray(u_field["latitude"].values, dtype="float64")
    lon = np.asarray(u_field["longitude"].values, dtype="float64")
    u = np.asarray(u_field.values, dtype="float64").reshape(u_field.shape[-2], u_field.shape[-1])
    v = np.asarray(v_field.values, dtype="float64").reshape(v_field.shape[-2], v_field.shape[-1])
    speed = np.hypot(u, v)

    lat_out, lon_out, z_out = _downsample(lat, lon, speed)
    _, _, u_out = _downsample(lat, lon, u)
    _, _, v_out = _downsample(lat, lon, v)

    period = f"{y0}-{y1}"
    return {
        "title": f"Vent à 10 m — {MONTH_LABELS_LONG[month - 1]} ({period})",
        "variable": "10m_wind_speed",
        "variable_label": "Vitesse du vent à 10 m",
        "unit": "m/s",
        "area": list(area),
        "domain": places.area_label(tuple(area)),
        "lat": lat_out,
        "lon": lon_out,
        "z": z_out,
        "u": u_out,
        "v": v_out,
        "period": period,
        "month": month,
        "palette": "wind",
        "source": f"CDS (ERA5) — vitesse calculée à partir de U et V, moyenne {period}",
        "live": False,
        "elapsed_s": round(time.perf_counter() - t0, 1),
        "request": {"dataset": dataset.id, "payload": request},
        "attribution": config.ERA5_ATTRIBUTION,
    }


# --------------------------------------------------------------------------- #
# Champ en direct
# --------------------------------------------------------------------------- #


def _downsample(lat: np.ndarray, lon: np.ndarray, z: np.ndarray) -> tuple[list, list, list]:
    """
    Réduit le champ à une taille raisonnable pour le navigateur.

    ERA5 fait 0,25° : sur l'Europe cela représente plus de 43 000 cellules, ce
    qui alourdit inutilement la réponse. On cible `TARGET_STEP` degrés, avec un
    plafond de cellules pour les domaines très vastes.
    """
    step = TARGET_STEP
    est_cells = (abs(lat.max() - lat.min()) / step) * (abs(lon.max() - lon.min()) / step)
    while est_cells > MAX_CELLS:
        step *= 1.5
        est_cells = (abs(lat.max() - lat.min()) / step) * (abs(lon.max() - lon.min()) / step)

    lat_step = max(1, int(round(step / abs(float(lat[1]) - float(lat[0])))))
    lon_step = max(1, int(round(step / abs(float(lon[1]) - float(lon[0])))))

    lat_out = np.asarray(lat)[::lat_step]
    lon_out = np.asarray(lon)[::lon_step]
    z_out = np.asarray(z)[::lat_step, ::lon_step]

    return (
        [round(float(v), 3) for v in lat_out],
        [round(float(v), 3) for v in lon_out],
        [[None if not np.isfinite(v) else round(float(v), 2) for v in row] for row in z_out],
    )


def field_from_cds(
    variable: str,
    *,
    domain: str | None = None,
    area: tuple[float, float, float, float] | None = None,
    month: int | None = None,
    years: tuple[int, int] = config.REFERENCE_PERIOD,
    dataset_key: str = "monthly_means",
) -> dict[str, Any]:
    """
    Télécharge un champ auprès du CDS et le retourne au format carte.

    `month=None` moyenne sur toute la période (carte annuelle) ; sinon la
    carte porte sur le seul mois demandé, moyenné sur `years`.
    """
    meta = datasets.VARIABLES.get(variable)
    if meta is None:
        raise KeyError(f"Variable inconnue : {variable!r}")
    if month is not None and not 1 <= int(month) <= 12:
        raise ValueError("Le mois doit être compris entre 1 et 12.")

    if area is None:
        match = next((d for d in places.DOMAINS if d.name == domain), None)
        if match is None:
            raise KeyError(f"Domaine inconnu : {domain!r}. Voir /api/places.")
        area = match.area

    dataset = datasets.get_dataset(dataset_key)
    y0 = max(int(years[0]), dataset.start_year)
    y1 = min(int(years[1]), config.LAST_COMPLETE_YEAR)
    if y0 > y1:
        raise ValueError(f"Période vide : {years[0]}-{years[1]}.")

    months = [int(month)] if month else list(range(1, 13))
    request = datasets.build_monthly_request(variable, list(range(y0, y1 + 1)), months, list(area))

    cfg = config.resolve_cds_config()
    if not cfg.is_configured:
        raise RuntimeError("Aucune clé CDS configurée : la carte en direct est indisponible.")

    t0 = time.perf_counter()
    path = cds.retrieve(cfg, dataset.id, request)
    with cds.open_dataset(path) as ds:
        da = cds.find_variable(ds, variable)
        da, unit = cds.to_display_units(da, variable)
        field = cds.field2d(da, month=month)

    lat = np.asarray(field["latitude"].values, dtype="float64")
    lon = np.asarray(field["longitude"].values, dtype="float64")
    values = np.asarray(field.values, dtype="float64")
    if values.ndim > 2:
        values = values.reshape(values.shape[-2], values.shape[-1])

    # Précipitations : le fichier est un débit moyen par jour.
    if meta.monthly_rate and unit == "mm":
        days = 30.4 if month is None else float(analysis_month_days(month))
        values = values * days
        unit = "mm/mois"

    lat_out, lon_out, z_out = _downsample(lat, lon, values)

    period = f"{y0}-{y1}"
    return {
        "id": "live",
        "title": _map_title(meta, month, period),
        "variable": variable,
        "variable_label": meta.label,
        "unit": unit,
        "area": list(area),
        "domain": places.area_label(tuple(area)),
        "lat": lat_out,
        "lon": lon_out,
        "z": z_out,
        "period": period,
        "month": month,
        "palette": palette_for(variable),
        "source": f"CDS (ERA5) — moyennes mensuelles {period}",
        "live": True,
        "elapsed_s": round(time.perf_counter() - t0, 1),
        "request": {"dataset": dataset.id, "payload": request},
        "attribution": config.ERA5_ATTRIBUTION,
    }


def analysis_month_days(month: int) -> int:
    import calendar

    return calendar.monthrange(2001, int(month))[1]


def _map_title(meta: datasets.Variable, month: int | None, period: str) -> str:
    from .analysis import MONTH_LABELS_LONG

    when = f"{MONTH_LABELS_LONG[month - 1]} ({period})" if month else f"moyenne annuelle ({period})"
    return f"{meta.label} — {when}"


def palette_for(variable: str) -> str:
    """Nom de palette renvoyé au navigateur (les palettes sont définies en JS)."""
    meta = datasets.VARIABLES.get(variable)
    if meta is None:
        return "viridis"
    return {
        "temperature": "temperature",
        "precipitation": "precipitation",
        "pressure": "pressure",
        "wind": "wind",
    }.get(meta.kind, "viridis")
