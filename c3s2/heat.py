"""
Données journalières pour l'activité « jours de chaleur ».

Les statistiques journalières ERA5 sont lourdes à télécharger : on les range
dans un CSV préparé (`scripts/prepare_data.py heat`) et on ne repart vers le
CDS que si la ville ou la période demandées n'y figurent pas.

Les conversions sont les mêmes que partout ailleurs : kelvins -> °C, appliqué
aux maximums et minimums diurnes.
"""

from __future__ import annotations

import calendar
import time
from pathlib import Path
from typing import Any

import pandas as pd

from . import analysis, cds, config, datasets, places, store

#: Fichiers journaliers préparés.
TMAX_FILE = "chaleur_tmax.csv"
TMIN_FILE = "chaleur_tmin.csv"

#: Variables journalières réellement utiles.
DAILY_VARIABLES = {
    "tmax": ("maximum_2m_temperature", "daily_maximum"),
    "tmin": ("minimum_2m_temperature", "daily_minimum"),
}

#: Tranche d'années demandée au CDS pour une requête journalière.
#: Le CDS refuse au-delà d'un certain volume (« cost limits exceeded ») :
#: on démarre sur un bloc raisonnable et on divise automatiquement.
CHUNK_YEARS = 6

#: Sous-tranche minimale (année pleine avant de couper sur les mois).
MIN_CHUNK_YEARS = 1

#: Mois demandés lorsqu'une année entière reste trop volumineuse.
ALL_MONTHS = tuple(range(1, 13))

_cache: dict[str, pd.DataFrame] = {}


def clear_cache() -> None:
    """Oublie les fichiers journaliers déjà lus (après régénération)."""
    _cache.clear()


def _load(filename: str) -> pd.DataFrame | None:
    if filename in _cache:
        return _cache[filename]
    path = config.PRECOMPUTED_DIR / filename
    if not path.is_file() or path.stat().st_size < 200:
        return None
    try:
        frame = pd.read_csv(path, sep=";", index_col=0, parse_dates=True, encoding="utf-8-sig")
    except Exception:  # noqa: BLE001
        return None
    frame.index = pd.to_datetime(frame.index)
    _cache[filename] = frame
    return frame


def available() -> dict[str, list[str]]:
    """Villes couvertes par les fichiers journaliers, par grandeur."""
    out: dict[str, list[str]] = {}
    for key, filename in (("tmax", TMAX_FILE), ("tmin", TMIN_FILE)):
        frame = _load(filename)
        out[key] = [str(c) for c in frame.columns] if frame is not None else []
    return out


def _is_cost_error(exc: BaseException) -> bool:
    """Le CDS refuse une requête trop volumineuse (403 « too large »)."""
    text = str(exc).lower()
    return (
        "too large" in text
        or "cost limit" in text
        or "quota" in text
        or "trop volumineuse" in text  # message déjà traduit par cds._explain
        or "limite de coût" in text
    )


def _fetch_daily(place: places.Place, kind: str, start: int, end: int) -> pd.Series:
    """
    Télécharge (ou lit du cache) les données journalières d'une ville.

    La période est découpée en blocs de `CHUNK_YEARS` années. Si le CDS juge
    un bloc trop volumineux (« cost limits exceeded »), celui-ci est divisé
    par deux, puis par les mois si une année pleine reste trop lourde : on ne
    multiplie les appels que lorsque le serveur l'exige réellement.
    """
    variable, statistic = DAILY_VARIABLES[kind]
    cfg = config.resolve_cds_config()
    if not cfg.is_configured:
        raise RuntimeError(
            "Aucune clé CDS : les données journalières ne peuvent pas être "
            "téléchargées. Configurez CDSAPI_KEY puis réessayez."
        )

    dataset = datasets.get_dataset("daily_stats")
    y0 = max(int(start), dataset.start_year)
    y1 = min(int(end), config.LAST_DAILY_YEAR)
    if y0 > y1:
        raise ValueError(f"Période vide : {start}-{end}.")

    chunks: list[pd.Series] = []
    begin = y0
    while begin <= y1:
        stop = min(begin + CHUNK_YEARS - 1, y1)
        chunks.extend(
            _retrieve_block(cfg, dataset, variable, statistic, place, begin, stop, list(ALL_MONTHS))
        )
        begin = stop + 1

    merged = pd.concat(chunks).sort_index()
    return merged[~merged.index.duplicated(keep="first")]


def _retrieve_block(cfg, dataset, variable, statistic, place, y0: int, y1: int, months: list[int]) -> list[pd.Series]:
    """Un bloc d'années ; division binaire automatique si le CDS refuse."""
    try:
        return [_retrieve_chunk(cfg, dataset, variable, statistic, place, y0, y1, months)]
    except Exception as exc:  # noqa: BLE001
        if not _is_cost_error(exc):
            raise
        if y1 > y0:
            mid = (y0 + y1) // 2
            return _retrieve_block(cfg, dataset, variable, statistic, place, y0, mid, months) + (
                _retrieve_block(cfg, dataset, variable, statistic, place, mid + 1, y1, months)
            )
        if len(months) > 1:
            half = len(months) // 2
            return _retrieve_block(cfg, dataset, variable, statistic, place, y0, y0, months[:half]) + (
                _retrieve_block(cfg, dataset, variable, statistic, place, y0, y0, months[half:])
            )
        raise


def _retrieve_chunk(
    cfg,
    dataset,
    variable,
    statistic,
    place,
    year_from: int,
    year_to: int,
    months: list[int] | None = None,
) -> pd.Series:
    """Une requête journalière sur un bloc d'années, convertie en °C."""
    request = datasets.build_daily_request(
        variable,
        list(range(year_from, year_to + 1)),
        list(months) if months else list(range(1, 13)),
        list(range(1, 32)),
        list(place.area),
        daily_statistic=statistic,
    )
    path = cds.retrieve(cfg, dataset.id, request)
    with cds.open_dataset(path) as ds:
        da = cds.find_variable(ds, variable)
        da, _unit = cds.to_display_units(da, variable)
        box = cds.box_mean_series(da, place.lat, place.lon)
    box.index = pd.to_datetime(box.index)
    return box


def daily_series(city: str, kind: str, start: int, end: int) -> tuple[pd.Series, str]:
    """
    Série journalière d'une ville.

    Retourne `(série, source)` ; la source indique si la donnée vient du CSV
    préparé ou d'une requête CDS en direct.
    """
    place = places.get(city)
    if place is None:
        raise KeyError(f"Ville inconnue : {city!r}")
    if kind not in DAILY_VARIABLES:
        raise KeyError(f"Grandeur inconnue : {kind!r}")

    frame = _load(TMAX_FILE if kind == "tmax" else TMIN_FILE)
    if frame is not None and city in frame.columns:
        column = frame[city].dropna()
        if not column.empty:
            window = column.loc[f"{start}-01-01": f"{end}-12-31"]
            if not window.empty and window.index[0].year <= start and window.index[-1].year >= end:
                return window.astype("float64"), "precomputed"

    return _fetch_daily(place, kind, start, end), "cds"


def heat_payload(
    cities: list[str],
    start: int,
    end: int,
    *,
    tmax_threshold: float = 35.0,
    tmin_threshold: float = 20.0,
) -> dict[str, Any]:
    """
    Données de l'activité canicule : séries journalières + comptages.

    Le comptage combine deux seuils (maximum diurne **et** minimum nocturne),
    c'est exactement la comparaison demandée à l'élève à l'étape 3.
    """
    if not cities:
        raise ValueError("Aucune ville sélectionnée.")
    if len(cities) > 3:
        raise ValueError("Trois villes maximum pour les données journalières.")
    if end - start > 40:
        raise ValueError("40 ans au maximum par demande journalière.")

    t0 = time.perf_counter()
    payload: dict[str, Any] = {"cities": {}, "errors": []}

    for city in cities:
        try:
            tmax, src_max = daily_series(city, "tmax", start, end)
            tmin, src_min = daily_series(city, "tmin", start, end)
        except Exception as exc:  # noqa: BLE001
            payload["errors"].append({"city": city, "error": str(exc)})
            continue

        common = tmax.index.intersection(tmin.index)
        tmax = tmax.reindex(common)
        tmin = tmin.reindex(common)

        payload["cities"][city] = {
            "dates": [d.strftime("%Y-%m-%d") for d in common],
            "tmax": [None if pd.isna(v) else round(float(v), 1) for v in tmax.values],
            "tmin": [None if pd.isna(v) else round(float(v), 1) for v in tmin.values],
            "source": "precomputed" if src_max == "precomputed" and src_min == "precomputed" else "cds",
            "counts": {
                "tmax_above": analysis.day_counts(tmax, threshold=tmax_threshold, direction="above"),
                "tmin_above": analysis.day_counts(tmin, threshold=tmin_threshold, direction="above"),
                "both": _count_both(tmax, tmin, tmax_threshold, tmin_threshold),
            },
        }

    if not payload["cities"]:
        raise RuntimeError(payload["errors"][0]["error"] if payload["errors"] else "Aucune donnée.")

    payload["meta"] = {
        "start": start,
        "end": end,
        "tmax_threshold": tmax_threshold,
        "tmin_threshold": tmin_threshold,
        "elapsed_s": round(time.perf_counter() - t0, 2),
        "reference": list(config.REFERENCE_PERIOD),
        "attribution": config.ERA5_ATTRIBUTION,
    }
    return payload


def _count_both(
    tmax: pd.Series,
    tmin: pd.Series,
    tmax_threshold: float,
    tmin_threshold: float,
) -> dict[str, Any]:
    """Jours où les deux seuils sont franchis simultanément."""
    if tmax.empty:
        return {"years": [], "values": [], "total": 0}
    mask = (tmax >= tmax_threshold) & (tmin >= tmin_threshold)
    counts = mask.astype(float).groupby(mask.index.year).sum()
    counts = counts[counts.index <= config.LAST_DAILY_YEAR]
    return {
        "years": [int(y) for y in counts.index],
        "values": [int(v) for v in counts.values],
        "total": int(counts.sum()),
        "average": round(float(counts.mean()), 1) if len(counts) else 0.0,
        "max_year": int(counts.idxmax()) if len(counts) else None,
        "max_value": int(counts.max()) if len(counts) else None,
        "thresholds": {"tmax": tmax_threshold, "tmin": tmin_threshold},
    }
