"""
Catalogue des jeux de données Copernicus retenus en classe, et construction
des requêtes CDS associées.

Deux jeux suffisent au programme de cycle 4 :

* `monthly_means` — moyennes mensuelles ERA5 : courbes d'évolution, normales,
  climatogrammes, cartes de climat ;
* `daily_stats` — statistiques journalières : comptage des jours de canicule.

⚠️ Point pédagogique capital : dans les moyennes mensuelles ERA5, la
précipitation est livrée comme une **accumulation moyenne par jour** (m/j),
et non comme le cumul du mois. Multiplier par 1000 donne des mm/**jour** ;
il faut encore multiplier par le nombre de jours du mois pour obtenir le
cumul mensuel affiché sur un climatogramme. C'est `VARIABLES["…"].monthly_rate`
qui porte cette information, et c'est la correction qui rend les diagrammes
ombrothermiques justes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

VariableKind = Literal["temperature", "precipitation", "pressure", "wind"]


@dataclass(frozen=True)
class Variable:
    """Une variable météorologique exploitable en classe."""

    slug: str
    label: str
    unit: str
    long_name: str
    kind: VariableKind
    #: Vrai si les moyennes mensuelles expriment un débit moyen par jour.
    monthly_rate: bool = False
    daily_stats: tuple[str, ...] = ("daily_mean",)
    lesson: str = "climat"
    color: str = "#e07a5f"
    description: str = ""


TEMPERATURE = Variable(
    slug="2m_temperature",
    label="Température de l'air à 2 m",
    unit="°C",
    long_name="Temperature at 2 metres above ground surface",
    kind="temperature",
    daily_stats=("daily_mean", "daily_maximum", "daily_minimum"),
    lesson="saisons, effet de serre, réchauffement",
    color="#e07a5f",
    description="Grandeur la plus lisible pour parler de climat et de saisons.",
)

PRECIPITATION = Variable(
    slug="total_precipitation",
    label="Précipitations totales",
    unit="mm",
    long_name="Total precipitation (rain, snow and convective)",
    kind="precipitation",
    monthly_rate=True,
    daily_stats=("daily_sum",),
    lesson="cycle de l'eau, régimes pluviométriques",
    color="#4c7fd1",
    description="Cumul mensuel reconstruit à partir du débit moyen journalier.",
)

PRESSURE = Variable(
    slug="mean_sea_level_pressure",
    label="Pression au niveau de la mer",
    unit="hPa",
    long_name="Mean sea level pressure (MSLP)",
    kind="pressure",
    lesson="vents et circulation atmosphérique",
    color="#7a5cc2",
    description="Pression ramenée au niveau de la mer, en hectopascals.",
)

WIND_U = Variable(
    slug="10m_u_component_of_wind",
    label="Vent à 10 m — composante ouest (U)",
    unit="m/s",
    long_name="Eastward component of the 10 metre wind",
    kind="wind",
    lesson="vents",
    color="#2a9d8f",
)

WIND_V = Variable(
    slug="10m_v_component_of_wind",
    label="Vent à 10 m — composante nord (V)",
    unit="m/s",
    long_name="Northward component of the 10 metre wind",
    kind="wind",
    lesson="vents",
    color="#2a9d8f",
)

SST = Variable(
    slug="sea_surface_temperature",
    label="Température de la mer en surface",
    unit="°C",
    long_name="Sea surface temperature",
    kind="temperature",
    lesson="El Niño, courants océaniques",
    color="#2a9d8f",
    description="Température de la surface des océans, en degrés Celsius.",
)

VARIABLES: dict[str, Variable] = {
    v.slug: v for v in (TEMPERATURE, PRECIPITATION, PRESSURE, WIND_U, WIND_V, SST)
}

#: Variables réellement proposées dans l'interface.
EXPLORABLE_VARIABLES = ("2m_temperature", "total_precipitation", "mean_sea_level_pressure")


@dataclass(frozen=True)
class Dataset:
    """Un jeu de données du CDS et sa méthode d'appel."""

    id: str
    label: str
    summary: str
    frequency: str
    start_year: int
    resolution: str
    doc_url: str
    licence: str
    size_hint_mb: float = 5.0
    notes: str = ""
    difficulty: int = 1


DATASETS: dict[str, Dataset] = {
    "monthly_means": Dataset(
        id="reanalysis-era5-single-levels-monthly-means",
        label="ERA5 — moyennes mensuelles (surface)",
        summary=(
            "Température, précipitations et pression moyennées par mois sur toute la "
            "planète depuis 1940 : le jeu de référence pour construire des normales "
            "climatiques et des courbes d'évolution."
        ),
        frequency="mensuel",
        start_year=1940,
        resolution="0,25° × 0,25° (≈ 25 km)",
        doc_url="https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels-monthly-means",
        licence="CC BY 4.0",
        size_hint_mb=12.0,
        notes=(
            "La température est en kelvins dans le fichier : l'application la convertit. "
            "Les précipitations y sont exprimées en mètres par jour."
        ),
    ),
    "daily_stats": Dataset(
        id="derived-era5-single-levels-daily-statistics",
        label="ERA5 — statistiques journalières (surface)",
        summary=(
            "Moyenne, somme, maximum et minimum quotidiens, calculés par le CDS à "
            "partir des données horaires : indispensables pour compter les jours de "
            "canicule ou de gel."
        ),
        frequency="quotidien",
        start_year=1940,
        resolution="0,25° × 0,25° (≈ 25 km)",
        doc_url="https://cds.climate.copernicus.eu/datasets/derived-era5-single-levels-daily-statistics",
        licence="CC BY 4.0",
        size_hint_mb=25.0,
        difficulty=2,
        notes=(
            "`time_zone: utc+01:00` est essentiel : sans lui, une « journée » serait "
            "calée sur UTC et non sur le temps civil français."
        ),
    ),
}


def get_dataset(key: str) -> Dataset:
    if key not in DATASETS:
        raise KeyError(f"Jeu de données inconnu : {key!r}")
    return DATASETS[key]


# --------------------------------------------------------------------------- #
# Noms de variables
# --------------------------------------------------------------------------- #

#: Le CDS accepte le nom long dans la requête mais écrit le code court ECMWF
#: dans le fichier NetCDF. Sans cette table, toute requête échoue en `KeyError`.
SHORT_NAMES: dict[str, str] = {
    "2m_temperature": "t2m",
    "maximum_2m_temperature": "mx2t",
    "minimum_2m_temperature": "mn2t",
    "2m_dewpoint_temperature": "d2m",
    "total_precipitation": "tp",
    "sea_surface_temperature": "sst",
    "mean_sea_level_pressure": "msl",
    "surface_pressure": "sp",
    "total_cloud_cover": "tcc",
    "snow_depth": "sd",
    "10m_u_component_of_wind": "u10",
    "10m_v_component_of_wind": "v10",
}

KELVIN_OFFSET = 273.15

#: Conversion des unités trouvées dans le fichier vers l'unité d'affichage :
#: (facteur multiplicatif, unité cible, constante additive).
FILE_UNITS: dict[str, tuple[float, str, float]] = {
    "K": (1.0, "°C", -KELVIN_OFFSET),
    "kelvin": (1.0, "°C", -KELVIN_OFFSET),
    "degC": (1.0, "°C", 0.0),
    "m": (1000.0, "mm", 0.0),          # précipitations : m -> mm
    "kg m-2": (1.0, "mm", 0.0),
    "kg m**-2": (1.0, "mm", 0.0),
    "kg m-2 s-1": (1.0, "mm/j", 0.0),
    "Pa": (0.01, "hPa", 0.0),
    "hPa": (1.0, "hPa", 0.0),
    "m s**-1": (1.0, "m/s", 0.0),
    "m s-1": (1.0, "m/s", 0.0),
    "%": (1.0, "%", 0.0),
}


def name_candidates(variable: str) -> list[str]:
    """Noms possibles de la variable, du plus au moins probable."""
    candidates = [variable]
    short = SHORT_NAMES.get(variable)
    if short:
        candidates.append(short)
    candidates += [f"{variable}_mean", f"{variable}_daily_mean", f"var_{variable}"]
    if short:
        candidates += [f"{short}_mean", f"var_{short}"]
    return list(dict.fromkeys(candidates))


# --------------------------------------------------------------------------- #
# Construction des requêtes
# --------------------------------------------------------------------------- #


def build_monthly_request(
    variable: str | list[str],
    years: list[int],
    months: list[int],
    area: list[float],
    *,
    product_type: str = "monthly_averaged_reanalysis",
) -> dict[str, Any]:
    """
    Requête des moyennes mensuelles ERA5.

    `area` suit l'ordre CDS `[Nord, Ouest, Sud, Est]`, en degrés décimaux.
    Les années et les mois doivent être des chaînes. `variable` accepte une
    liste pour récupérer plusieurs composantes (U et V du vent, par exemple)
    en une seule requête.
    """
    variables = [variable] if isinstance(variable, str) else list(variable)
    return {
        "product_type": product_type,
        "variable": variables,
        "year": [str(y) for y in years],
        "month": [f"{m:02d}" for m in months],
        "time": "00:00",
        "area": list(area),
        "data_format": "netcdf",
        "download_format": "unarchived",
    }


def build_daily_request(
    variable: str,
    years: list[int],
    months: list[int],
    days: list[int],
    area: list[float],
    *,
    daily_statistic: str = "daily_mean",
) -> dict[str, Any]:
    """
    Requête des statistiques journalières ERA5.

    `time_zone=utc+01:00` calque la journée sur l'heure d'hiver française :
    sans lui, les totaux de précipitation et les maximums sont décalés.
    """
    return {
        "product_type": "reanalysis",
        "variable": [variable],
        "year": [str(y) for y in years],
        "month": [f"{m:02d}" for m in months],
        "day": [f"{d:02d}" for d in days],
        "daily_statistic": daily_statistic,
        "time_zone": "utc+01:00",
        "frequency": "1_hourly",
        "area": list(area),
        "data_format": "netcdf",
        "download_format": "unarchived",
    }
