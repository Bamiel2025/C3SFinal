"""
Point d'entrée unique des séries temporelles, avec choix automatique de la
source.

Trois sources, par ordre de priorité :

1. **Pré-calculé** — CSV versionnés dans le dépôt : instantané, disponible dès
   le premier affichage, même sans clé et même sur Vercel (lecture seule).
2. **CDS en direct** — requête ERA5 réelle, pour une période ou une ville non
   couverte par les fichiers préparés, ou quand l'enseignant veut montrer une
   requête vivante. Comptez 20 à 90 secondes.
3. **Simulation** — jeu de données synthétique, uniquement pour comprendre le
   fonctionnement de l'application sans clé.

La réponse expose toujours la source réellement utilisée : aucun écran ne
laisse croire qu'une simulation est une donnée réelle.
"""

from __future__ import annotations

import calendar
import time
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from . import analysis, cds, config, datasets, places, store

SOURCE_LABELS = {
    "precomputed": "Données ERA5 pré-calculées (lecture instantanée)",
    "cds": "Données ERA5 téléchargées depuis le CDS",
    "simulated": "Données simulées (aucune clé configurée)",
}

SIMULATED_WARNING = (
    "Ces valeurs sont simulées : l'application n'a trouvé aucune clé CDS. "
    "Elles illustrent le fonctionnement du graphique mais ne peuvent pas servir "
    "dans un travail scolaire."
)


@dataclass
class CityResult:
    """Série d'une ville, avec sa provenance."""

    name: str
    series: pd.Series
    source: str
    detail: str = ""
    request: dict[str, Any] | None = None


def _month_days(index: pd.DatetimeIndex, variable: str) -> pd.Series:
    """Nombre de jours de chaque mois (conversion des précipitations mensuelles)."""
    return pd.Series(
        [calendar.monthrange(d.year, d.month)[1] for d in index],
        index=index,
        dtype="float64",
    )


def monthly_totals(series: pd.Series, variable: str) -> pd.Series:
    """
    Passe d'un débit moyen journalier à un cumul mensuel (mm/mois).

    C'est la conversion qui manquait dans la première version de l'application :
    sans elle, un climatogramme affiche ~4 mm en janvier au lieu de ~120 mm.
    """
    meta = datasets.VARIABLES.get(variable)
    if meta is None or not meta.monthly_rate:
        return series
    return series.astype("float64") * _month_days(series.index, variable)


# --------------------------------------------------------------------------- #
# Sources
# --------------------------------------------------------------------------- #


def fetch_cds(place: places.Place, variable: str, start: int, end: int) -> CityResult:
    """Télécharge (ou lit du cache) la série mensuelle d'une ville auprès du CDS."""
    meta = datasets.VARIABLES.get(variable)
    dataset = datasets.get_dataset("monthly_means")
    y0 = max(start, dataset.start_year)
    y1 = min(end, config.LAST_DATA_YEAR)
    if y0 > y1:
        raise ValueError(f"Période vide : {start}-{end}.")

    months = list(range(1, 13))
    request = datasets.build_monthly_request(
        variable, list(range(y0, y1 + 1)), months, list(place.area)
    )
    cfg = config.resolve_cds_config()
    path = cds.retrieve(cfg, dataset.id, request)
    with cds.open_dataset(path) as ds:
        da = cds.find_variable(ds, variable)
        da, unit = cds.to_display_units(da, variable)
        raw = cds.box_mean_series(da, place.lat, place.lon)
    raw.index = pd.to_datetime(raw.index)

    converted = monthly_totals(raw, variable).rename(place.name)
    return CityResult(
        name=place.name,
        series=converted,
        source="cds",
        detail=f"Requête ERA5 {y0}-{y1} sur une cellule de 0,25° autour de {place.name}.",
        request={"dataset": dataset.id, "payload": request},
    )


def fetch_precomputed(place: places.Place, variable: str, start: int, end: int) -> CityResult | None:
    """Série déjà préparée, ou `None` si elle ne couvre pas la demande."""
    series, coverage = store.precomputed_series(place.name, variable, start, end)
    if series is None:
        return None
    return CityResult(
        name=place.name,
        series=series.rename(place.name),
        source="precomputed",
        detail=f"Couverture {coverage[0]}-{coverage[1]}.",
    )


def fetch_simulated(place: places.Place, variable: str, start: int, end: int) -> CityResult:
    """
    Série synthétique déterministe, utilisée uniquement sans clé.

    Le signal reproduit les ordres de grandeur réels (saison, latitude, tendance)
    pour que les activités restent jouables hors ligne — mais l'écran annonce
    explicitement la simulation.
    """
    import numpy as np

    meta = datasets.VARIABLES.get(variable)
    unit = meta.unit if meta else ""
    rng = np.random.default_rng(abs(hash(place.name)) % (2**32))
    dates = pd.date_range(f"{start}-01-01", f"{end}-12-01", freq="MS")
    months = dates.month.values.astype("float64")
    years = dates.year.values.astype("float64")

    if meta and meta.kind == "temperature":
        annual_mean = 16.0 - (abs(place.lat) - 45.0) * 0.45 - place.altitude * 0.006
        amplitude = 8.0 + max(0.0, abs(place.lat) - 45.0) * 0.7 + (5.0 if not place.coastal else 0.0)
        phase = np.cos((months - 7.5) / 12.0 * 2 * np.pi)
        values = annual_mean + amplitude / 2 * phase + 0.025 * (years - 1940)
        values = values + rng.normal(0, 0.6, len(dates))
    elif meta and meta.kind == "precipitation":
        base = 60.0 + (25.0 if place.coastal else 0.0)
        seasonal = np.cos((months - 1.0) / 12.0 * 2 * np.pi)
        values = base + base * 0.6 * seasonal + rng.normal(0, 12, len(dates))
        values = np.clip(values, 0.0, None)
        values = values * _month_days(dates, variable) / 30.0
    else:
        values = 1013.0 + rng.normal(0, 8, len(dates))

    series = pd.Series(values, index=dates, name=place.name)
    return CityResult(name=place.name, series=series, source="simulated", detail=SIMULATED_WARNING)


# --------------------------------------------------------------------------- #
# Entrée principale
# --------------------------------------------------------------------------- #


def get_city(
    city: str,
    variable: str,
    start: int,
    end: int,
    source: str = "auto",
) -> CityResult:
    """Récupère la série d'une ville selon la source demandée."""
    place = places.get(city)
    if place is None:
        raise KeyError(f"Ville inconnue : {city!r}")

    if source == "simulated":
        return fetch_simulated(place, variable, start, end)

    if source == "cds":
        return fetch_cds(place, variable, start, end)

    precomputed = fetch_precomputed(place, variable, start, end)
    if precomputed is not None:
        return precomputed

    if source == "precomputed":
        coverage = store.precomputed_series(place.name, variable, start, end)
        raise FileNotFoundError(
            f"Aucune donnée pré-calculée pour {place.name} "
            f"(couverture : {coverage[1]}). Utilisez la source « CDS »."
        )

    cfg = config.resolve_cds_config()
    if cfg.is_configured:
        try:
            return fetch_cds(place, variable, start, end)
        except Exception:
            if source == "cds":
                raise
            # Repli explicite plutôt qu'une page en erreur.
            return fetch_simulated(place, variable, start, end)

    return fetch_simulated(place, variable, start, end)


def get_series(
    cities: list[str],
    variable: str,
    start: int,
    end: int,
    source: str = "auto",
    *,
    include_stats: bool = True,
) -> dict[str, Any]:
    """
    Séries de plusieurs villes + statistiques + métadonnées, prêtes à envoyer
    au navigateur.
    """
    t0 = time.perf_counter()
    if variable not in datasets.VARIABLES:
        raise KeyError(f"Variable inconnue : {variable!r}")
    if not cities:
        raise ValueError("Aucune ville sélectionnée.")
    if len(cities) > 6:
        raise ValueError("Six villes au maximum par graphique.")

    start = max(int(start), datasets.get_dataset("monthly_means").start_year)
    end = min(int(end), config.LAST_DATA_YEAR)
    if start > end:
        raise ValueError(f"Période vide : {start}-{end}.")

    results: list[CityResult] = []
    errors: list[dict[str, str]] = []
    for city in cities:
        try:
            results.append(get_city(city, variable, start, end, source))
        except Exception as exc:  # noqa: BLE001 - une ville en échec n'annule pas les autres
            errors.append({"city": city, "error": str(exc)})

    if not results:
        raise RuntimeError(errors[0]["error"] if errors else "Aucune donnée disponible.")

    meta = datasets.VARIABLES[variable]
    used = {r.source for r in results}
    main_source = results[0].source
    mixed = len(used) > 1

    payload_series: dict[str, Any] = {}
    payload_stats: dict[str, Any] = {}
    requests: list[dict[str, Any]] = []

    for result in results:
        window = result.series.loc[f"{start}-01-01": f"{end}-12-31"].dropna()
        payload_series[result.name] = {
            "dates": [d.strftime("%Y-%m") for d in window.index],
            "values": [None if pd.isna(v) else round(float(v), 2) for v in window.values],
            "source": result.source,
            "detail": result.detail,
        }
        if include_stats:
            payload_stats[result.name] = analysis.describe_series(
                window, variable, meta.unit, city=result.name,
                # Normale calculée sur la période affichée : l'élève compare ce
                # qu'il voit, et la période est rappelée dans le graphique.
                reference=(start, end),
            )
        if result.request:
            requests.append({"city": result.name, **result.request})

    source_label = "Sources mixtes" if mixed else SOURCE_LABELS.get(main_source, main_source)
    elapsed = time.perf_counter() - t0

    return {
        "meta": {
            "variable": variable,
            "variable_label": meta.label,
            "unit": meta.unit,
            "kind": meta.kind,
            "start": start,
            "end": end,
            "reference": list(config.REFERENCE_PERIOD),
            "source": "mixed" if mixed else main_source,
            "source_label": source_label,
            "source_detail": {r.name: SOURCE_LABELS.get(r.source, r.source) for r in results},
            "simulated": all(r.source == "simulated" for r in results),
            "warning": SIMULATED_WARNING if all(r.source == "simulated" for r in results) else "",
            "elapsed_s": round(elapsed, 2),
            "cds": config.resolve_cds_config().as_dict(),
            "attribution": config.ERA5_ATTRIBUTION,
            "citation": config.ERA5_CITATION,
            "licence": config.ERA5_LICENCE,
            "monthly_rate_note": (
                "Les précipitations ERA5 mensuelles sont un débit moyen journalier : "
                "l'application les multiplie par le nombre de jours du mois pour "
                "reconstituer le cumul mensuel."
                if meta.monthly_rate else ""
            ),
            "errors": errors,
            "requests": requests,
        },
        "series": payload_series,
        "stats": payload_stats,
    }
