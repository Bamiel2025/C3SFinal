"""
Lecture des séries pré-calculées (accès instantané en classe).

Télécharger ERA5 demande de 20 à 90 secondes par requête : devant une classe,
ce délai fait perdre l'attention. On lit donc d'abord les fichiers CSV versionnés
dans le dépôt, produits par `scripts/prepare_data.py`, et on n'interroge le CDS
que pour ce qu'ils ne couvrent pas.

⚠️ Unités des précipitations
----------------------------
Les moyennes mensuelles ERA5 livrent les précipitations en mètre **par jour** :
le cumul mensuel affiché à l'écran s'obtient en multipliant par le nombre de
jours du mois. Les fichiers versionnés dans ce dépôt sont déjà exprimés en
**cumuls mensuels (mm/mois)** — conversion effectuée une fois pour toutes par
`scripts/migrate_precip.py`. Toute donnée nouvelle écrite ici (CSV ou requête
CDS) doit donc être déjà convertie.
"""

from __future__ import annotations

import calendar
import threading
from functools import lru_cache
from pathlib import Path

import pandas as pd

from . import config, datasets

#: Fichier CSV associé à chaque variable exploitable.
PRECOMPUTED_FILES = {
    "2m_temperature": "villes_temperature.csv",
    "total_precipitation": "villes_precipitations.csv",
}

#: Marqueur posé par `scripts/migrate_precip.py` (cumuls mensuels).
PRECIP_MARKER = config.PRECOMPUTED_DIR / ".precip_monthly_total"

#: Libellé des fichiers, pour la page d'aide.
FILES_INVENTORY = {
    "villes_temperature.csv": (
        f"Température mensuelle à 2 m (°C), {config.FIRST_YEAR}-{config.LAST_DATA_YEAR}"
    ),
    "villes_precipitations.csv": (
        f"Précipitations mensuelles (mm), {config.FIRST_YEAR}-{config.LAST_DATA_YEAR}"
    ),
}

_lock = threading.Lock()


@lru_cache(maxsize=8)
def _raw_frame(variable: str) -> pd.DataFrame | None:
    """Charge (et met en cache) le fichier CSV d'une variable, tel quel."""
    filename = PRECOMPUTED_FILES.get(variable)
    if not filename:
        return None
    path = config.PRECOMPUTED_DIR / filename
    if not path.is_file() or path.stat().st_size < 200:
        return None
    try:
        frame = pd.read_csv(path, sep=";", index_col=0, parse_dates=True, encoding="utf-8-sig")
    except Exception:  # noqa: BLE001 - fichier illisible : on laissera le CDS répondre
        return None
    frame.index = pd.to_datetime(frame.index)
    return frame.sort_index()


def _frame(variable: str) -> pd.DataFrame | None:
    """
    Données d'une variable en unités d'affichage.

    Les fichiers produits par `scripts/prepare_data.py` sont déjà convertis ;
    seul un fichier hérité de la v1 (mm/jour) est corrigé à la lecture.
    """
    frame = _raw_frame(variable)
    if frame is None:
        return None
    if variable == "total_precipitation" and not PRECIP_MARKER.is_file():
        days = pd.Series(
            [calendar.monthrange(d.year, d.month)[1] for d in frame.index],
            index=frame.index,
            dtype="float64",
        )
        return frame.mul(days, axis=0)
    return frame


def clear_cache() -> None:
    """Vide le cache mémoire (utile après régénération des CSV)."""
    with _lock:
        _raw_frame.cache_clear()


def save_frame(variable: str, frame: pd.DataFrame) -> Path:
    """
    Écrit (ou complète) le fichier CSV d'une variable.

    Les colonnes déjà présentes sont conservées : régénérer les données ne
    recalcule que les villes qui manquent. `frame` doit être exprimé en unités
    d'affichage (mm/mois pour les précipitations).
    """
    filename = PRECOMPUTED_FILES.get(variable)
    if filename is None:
        raise KeyError(f"Aucun fichier pré-calculé pour la variable {variable!r}")

    existing = _raw_frame(variable)
    if existing is not None:
        merged = existing.copy()
        for column in frame.columns:
            merged[column] = frame[column]
        frame = merged

    return replace_frame(variable, frame)


def replace_frame(variable: str, frame: pd.DataFrame) -> Path:
    """Réécrit intégralement le fichier d'une variable (aucune fusion)."""
    filename = PRECOMPUTED_FILES.get(variable)
    if filename is None:
        raise KeyError(f"Aucun fichier pré-calculé pour la variable {variable!r}")

    frame = frame.sort_index()
    target = config.PRECOMPUTED_DIR / filename
    config.PRECOMPUTED_DIR.mkdir(parents=True, exist_ok=True)
    frame.to_csv(
        target,
        sep=";",
        float_format="%.2f",
        encoding="utf-8-sig",
        date_format="%Y-%m-%d",
    )
    clear_cache()
    return target


def save_daily(filename: str, frame: pd.DataFrame) -> Path:
    """
    Écrit (ou complète) un fichier journalier préparé (activité canicule).

    Même principe que `save_frame` : les colonnes déjà présentes sont gardées.
    """
    target = config.PRECOMPUTED_DIR / filename
    config.PRECOMPUTED_DIR.mkdir(parents=True, exist_ok=True)

    if target.is_file() and target.stat().st_size > 200:
        try:
            existing = pd.read_csv(target, sep=";", index_col=0, parse_dates=True, encoding="utf-8-sig")
            existing.index = pd.to_datetime(existing.index)
            merged = existing.sort_index()
            for column in frame.columns:
                merged[column] = frame[column]
            frame = merged.sort_index()
        except Exception:  # noqa: BLE001 - fichier illisible : on le réécrit
            pass

    frame.to_csv(
        target,
        sep=";",
        float_format="%.1f",
        encoding="utf-8-sig",
        date_format="%Y-%m-%d",
    )
    return target


def available_cities(variable: str) -> list[str]:
    """Villes présentes dans le fichier pré-calculé d'une variable."""
    frame = _frame(variable)
    if frame is None:
        return []
    return [str(c) for c in frame.columns]


def inventory() -> list[dict[str, str]]:
    """État des fichiers préparés, affiché dans la page d'aide."""
    rows = []
    for filename, description in FILES_INVENTORY.items():
        path = config.PRECOMPUTED_DIR / filename
        ready = path.is_file() and path.stat().st_size > 200
        rows.append(
            {
                "file": filename,
                "description": description,
                "status": "prêt" if ready else "absent",
                "size": f"{path.stat().st_size / 1e3:.0f} ko" if path.is_file() else "—",
            }
        )
    return rows


def _to_display(series: pd.Series, variable: str) -> pd.Series:
    """
    Renvoie la série dans son unité d'affichage.

    Historiquement, les précipitations étaient stockées en mm/jour et
    converties ici ; depuis `scripts/migrate_precip.py`, les fichiers sont
    déjà en mm/mois et cette fonction est une identité conservée pour garder
    un point d'entrée unique à la règle d'unités.
    """
    meta = datasets.VARIABLES.get(variable)
    if meta is None or not meta.monthly_rate:
        return series
    return series.astype("float64")


def precomputed_series(
    city: str,
    variable: str,
    start: int,
    end: int,
) -> tuple[pd.Series | None, tuple[int, int] | None]:
    """
    Série mensuelle déjà téléchargée pour une ville.

    Retourne `(série, couverture)` ; `(None, None)` si la ville n'existe pas
    dans le fichier, `(None, (début, fin))` si elle existe mais ne couvre pas
    la période demandée.
    """
    frame = _frame(variable)
    if frame is None or city not in frame.columns:
        return None, None

    column = frame[city].dropna()
    if column.empty:
        return None, None

    coverage = (int(column.index[0].year), int(column.index[-1].year))
    if coverage[0] > start or coverage[1] < end:
        return None, coverage

    window = column.loc[f"{start}-01-01": f"{end}-12-31"]
    if window.empty:
        return None, coverage
    return _to_display(window, variable), coverage


def precomputed_cities_summary() -> dict[str, list[str]]:
    """Couverture par variable, pour l'interface et l'aide."""
    return {
        variable: available_cities(variable)
        for variable in PRECOMPUTED_FILES
    }
