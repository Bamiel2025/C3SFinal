"""
Traitements climatologiques : normales, anomalies, tendances, indices.

Choix méthodologiques, expliqués aux élèves dans l'interface :

* **Normale** — moyenne calculée sur trente ans (1991-2020 pour l'OMM). Toute
  anomalie s'entend par rapport à cette période : sans elle, « +2 °C » ne veut
  rien dire.
* **Amplitude thermique** — écart entre le mois le plus chaud et le mois le plus
  froid de la normale : c'est l'indicateur qui distingue un climat océanique
  d'un climat continental.
* **Tendance** — régression linéaire des moindres carrés sur les moyennes
  annuelles, exprimée par décennie. Le R² mesure l'ajustement, pas la
  significativité : l'autocorrélation des séries interannuelles impose la
  prudence.
* **Lecture ponctuelle** — la valeur ERA5 en un point est la moyenne d'une
  cellule de 0,25° (≈ 25 km) : ce n'est pas une mesure de station.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

MONTH_LABELS_SHORT = [
    "janv.", "févr.", "mars", "avr.", "mai", "juin",
    "juil.", "août", "sept.", "oct.", "nov.", "déc.",
]
MONTH_LABELS_LONG = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]

REFERENCE_PERIOD = (1991, 2020)


def _fmt(value: float, digits: int = 1) -> str:
    """Nombre au format français (virgule décimale, espace fine millier)."""
    text = f"{value:,.{digits}f}".replace(",", " ").replace(".", ",")
    return text


# --------------------------------------------------------------------------- #
# Bases
# --------------------------------------------------------------------------- #


def monthly_climatology(series: pd.Series, reference: tuple[int, int] = REFERENCE_PERIOD) -> pd.Series:
    """
    Moyenne de chaque mois sur la période de référence (normale mensuelle).

    Renvoie une série de 12 valeurs rangées sur une année type, prête pour un
    diagramme ombrothermique.
    """
    ref = series.loc[f"{reference[0]}-01-01": f"{reference[1]}-12-31"]
    if ref.empty:
        ref = series
    if ref.empty:
        return pd.Series(dtype="float64")
    climat = ref.groupby(ref.index.month).mean()
    idx = pd.date_range("2001-01-01", periods=12, freq="MS")
    return pd.Series(climat.reindex(range(1, 13)).values, index=idx)


def annual_mean(series: pd.Series) -> pd.Series:
    """Moyenne annuelle ; les années incomplètes sont écartées."""
    if series.empty:
        return series
    groups = series.groupby(series.index.year)
    annual = groups.mean()
    counts = groups.count()
    return annual[counts >= 12]


def anomalies(series: pd.Series, reference: tuple[int, int] = REFERENCE_PERIOD) -> pd.Series:
    """Écart à la normale : `valeur − moyenne de la période de référence`."""
    ref = series.loc[f"{reference[0]}-01-01": f"{reference[1]}-12-31"]
    base = ref.mean() if not ref.empty else series.mean()
    return series - base


@dataclass
class Trend:
    """Résultat d'une régression linéaire des moindres carrés."""

    slope: float
    intercept: float
    r_squared: float
    n: int
    per_decade: float
    unit: str = ""

    @property
    def valid(self) -> bool:
        return self.n >= 3 and self.slope != 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "slope": round(self.slope, 6),
            "per_decade": round(self.per_decade, 3),
            "r_squared": round(self.r_squared, 3),
            "n": self.n,
            "valid": self.valid,
            "unit": self.unit,
            "label": (
                f"{_fmt(self.per_decade, 2)} {self.unit}/décennie (R² = {self.r_squared:.2f})"
                if self.valid else "—"
            ),
        }


def linear_trend(series: pd.Series, unit: str = "") -> Trend:
    """Tendance linéaire d'une série indexée sur des années ou des dates."""
    clean = series.dropna()
    if len(clean) < 3:
        return Trend(0.0, 0.0, 0.0, len(clean), 0.0, unit)
    if hasattr(clean.index, "year"):
        x = clean.index.year.values.astype("float64")
    else:
        x = np.asarray(clean.index, dtype="float64")
    y = clean.values.astype("float64")
    slope, intercept = np.polyfit(x, y, 1)
    pred = slope * x + intercept
    ss_res = float(np.sum((y - pred) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    return Trend(float(slope), float(intercept), r2, len(clean), float(slope * 10), unit)


# --------------------------------------------------------------------------- #
# Indices
# --------------------------------------------------------------------------- #


def thermal_amplitude(climatology: pd.Series) -> float:
    """Écart entre le mois le plus chaud et le mois le plus froid de la normale."""
    if climatology.empty:
        return float("nan")
    return float(climatology.max() - climatology.min())


def describe_series(
    series: pd.Series,
    variable: str,
    unit: str,
    *,
    city: str = "",
    reference: tuple[int, int] = REFERENCE_PERIOD,
) -> dict[str, Any]:
    """
    Calcule tous les indicateurs affichés autour du graphique.

    Le champ `narrative` est une phrase qui **décrit l'évolution du climat**
    (valeurs, dates, tendance) et non la forme de la courbe : c'est le support
    de la consigne pédagogique.
    """
    if series.empty:
        return {"narrative": "Aucune donnée sur la période demandée."}

    clim = monthly_climatology(series, reference)
    annual = annual_mean(series)
    trend = linear_trend(annual, unit)
    where = f"à {city} " if city else ""

    out: dict[str, Any] = {
        "n_points": int(series.size),
        "start": series.index[0].strftime("%Y-%m"),
        "end": series.index[-1].strftime("%Y-%m"),
        "climatology": {
            "months": MONTH_LABELS_LONG,
            "values": [None if pd.isna(v) else round(float(v), 2) for v in clim.values],
            "reference": f"{reference[0]}-{reference[1]}",
            "unit": unit,
        },
        "annual": {
            "years": [int(y) for y in annual.index],
            "values": [None if pd.isna(v) else round(float(v), 2) for v in annual.values],
        },
        "trend": trend.as_dict(),
    }

    if variable in ("2m_temperature", "maximum_2m_temperature", "minimum_2m_temperature"):
        out.update(_temperature_indices(series, clim, annual, trend, where, unit, reference))
    elif variable == "total_precipitation":
        out.update(_precipitation_indices(series, clim, annual, trend, where, unit, reference))
    else:
        out.update(_generic_indices(series, clim, annual, trend, where, unit, reference))

    out["anomalies"] = _anomaly_bars(annual, reference, unit)
    return out


def _temperature_indices(
    series: pd.Series,
    clim: pd.Series,
    annual: pd.Series,
    trend: Trend,
    where: str,
    unit: str,
    reference: tuple[int, int] = REFERENCE_PERIOD,
) -> dict[str, Any]:
    amplitude = thermal_amplitude(clim)
    hottest = int(clim.idxmax().month) if not clim.empty else None
    coldest = int(clim.idxmin().month) if not clim.empty else None
    period = f"{reference[0]}-{reference[1]}"

    latest = annual.iloc[-1] if len(annual) else float("nan")
    earliest = annual.iloc[0] if len(annual) else float("nan")

    indices = [
        {
            "label": "Température moyenne annuelle (normale)",
            "value": round(float(clim.mean()), 1) if not clim.empty else None,
            "unit": unit,
            "definition": f"Moyenne des douze moyennes mensuelles de {period}.",
        },
        {
            "label": "Mois le plus chaud",
            "value": round(float(clim.max()), 1) if not clim.empty else None,
            "unit": unit,
            "definition": f"Maximum de la normale, atteint en {MONTH_LABELS_LONG[hottest - 1]}." if hottest else "",
        },
        {
            "label": "Mois le plus froid",
            "value": round(float(clim.min()), 1) if not clim.empty else None,
            "unit": unit,
            "definition": f"Minimum de la normale, atteint en {MONTH_LABELS_LONG[coldest - 1]}." if coldest else "",
        },
        {
            "label": "Amplitude thermique annuelle",
            "value": round(amplitude, 1) if not np.isnan(amplitude) else None,
            "unit": unit,
            "definition": "Mois le plus chaud moins le mois le plus froid de la normale.",
            "reading": amplitude_reading(amplitude),
        },
        {
            "label": "Tendance sur la période",
            "value": round(trend.per_decade, 2) if trend.valid else None,
            "unit": f"{unit}/décennie",
            "definition": "Régression linéaire des moyennes annuelles.",
            "reading": trend_reading(trend, unit),
        },
    ]

    narrative = _temperature_narrative(clim, amplitude, trend, where, unit, earliest, latest)
    return {
        "indices": indices,
        "narrative": narrative,
        "amplitude": round(float(amplitude), 1) if not np.isnan(amplitude) else None,
        "summary": {
            "hottest_month": hottest,
            "coldest_month": coldest,
            "mean": round(float(clim.mean()), 1) if not clim.empty else None,
        },
    }


def amplitude_reading(amplitude: float) -> str:
    if np.isnan(amplitude):
        return ""
    if amplitude < 10:
        return "Amplitude faible : influence océanique marquée."
    if amplitude < 16:
        return "Amplitude modérée : influence marine encore sensible."
    if amplitude < 22:
        return "Amplitude forte : continentalité nette."
    return "Amplitude très forte : climat continental."


def trend_reading(trend: Trend, unit: str) -> str:
    if not trend.valid:
        return ""
    value = trend.per_decade
    if abs(value) < 0.05:
        return "Tendance quasiment nulle sur la période."
    direction = "hausse" if value > 0 else "baisse"
    strength = "marquée" if abs(value) >= 0.3 else "continue"
    return f"Tendance à la {direction} {strength} : {_fmt(value, 2)} {unit} par décennie."


def _temperature_narrative(
    clim: pd.Series,
    amplitude: float,
    trend: Trend,
    where: str,
    unit: str,
    earliest: float,
    latest: float,
) -> str:
    if clim.empty:
        return "Normale mensuelle indisponible sur la période."
    hottest = int(clim.idxmax().month)
    coldest = int(clim.idxmin().month)
    parts = [
        (
            f"Les températures {where}passent de {_fmt(float(clim.min()), 1)} {unit} "
            f"en {MONTH_LABELS_LONG[coldest - 1]} à {_fmt(float(clim.max()), 1)} {unit} "
            f"en {MONTH_LABELS_LONG[hottest - 1]} : l'amplitude annuelle atteint "
            f"{_fmt(amplitude, 1)} {unit}."
        )
    ]
    if trend.valid:
        direction = "augmente" if trend.per_decade > 0 else "diminue"
        parts.append(
            f"Sur la période étudiée, la moyenne annuelle {direction} de "
            f"{_fmt(abs(trend.per_decade), 2)} {unit} par décennie "
            f"(de {_fmt(earliest, 1)} à {_fmt(latest, 1)} {unit})."
        )
    return " ".join(parts)


def _precipitation_indices(
    series: pd.Series,
    clim: pd.Series,
    annual: pd.Series,
    trend: Trend,
    where: str,
    unit: str,
    reference: tuple[int, int] = REFERENCE_PERIOD,
) -> dict[str, Any]:
    annual_total = float(clim.sum()) if not clim.empty else float("nan")
    wettest = int(clim.idxmax().month) if not clim.empty else None
    driest = int(clim.idxmin().month) if not clim.empty else None
    mean_month = float(clim.mean()) if not clim.empty else 0.0
    dry_months = int((clim <= mean_month / 2).sum()) if not clim.empty else 0
    wet_months = int((clim >= 2 * mean_month).sum()) if not clim.empty else 0
    period = f"{reference[0]}-{reference[1]}"

    indices = [
        {
            "label": "Cumul annuel (normale)",
            "value": round(annual_total) if not np.isnan(annual_total) else None,
            "unit": unit,
            "definition": f"Somme des douze cumuls mensuels de {period}.",
        },
        {
            "label": "Mois le plus humide",
            "value": round(float(clim.max())) if not clim.empty else None,
            "unit": unit,
            "definition": f"Maximum mensuel en {MONTH_LABELS_LONG[wettest - 1]}." if wettest else "",
        },
        {
            "label": "Mois le plus sec",
            "value": round(float(clim.min())) if not clim.empty else None,
            "unit": unit,
            "definition": f"Minimum mensuel en {MONTH_LABELS_LONG[driest - 1]}." if driest else "",
        },
        {
            "label": "Mois secs (≤ moitié de la moyenne)",
            "value": dry_months,
            "unit": "mois",
            "definition": "Comptage indicatif de la sécheresse estivale.",
            "reading": "Un ou deux mois secs seulement : régime océanique. Quatre et plus : régime méditerranéen.",
        },
        {
            "label": "Tendance du cumul annuel",
            "value": round(trend.per_decade, 1) if trend.valid else None,
            "unit": f"{unit}/décennie",
            "definition": "Régression linéaire des cumuls annuels complets.",
        },
    ]

    narrative = ""
    if not clim.empty:
        narrative = (
            f"Les précipitations {where}culminent en {MONTH_LABELS_LONG[wettest - 1]} "
            f"({_fmt(float(clim.max()), 0)} {unit}) et diminuent jusqu'à leur minimum en "
            f"{MONTH_LABELS_LONG[driest - 1]} ({_fmt(float(clim.min()), 0)} {unit}) : "
            f"le cumul annuel atteint {_fmt(annual_total, 0)} {unit}."
        )
        if trend.valid and abs(trend.per_decade) >= 5:
            direction = "augmentent" if trend.per_decade > 0 else "diminuent"
            narrative += (
                f" Le total annuel {direction} de {_fmt(abs(trend.per_decade), 0)} {unit} "
                f"par décennie."
            )

    return {
        "indices": indices,
        "narrative": narrative,
        "amplitude": None,
        "summary": {
            "hottest_month": wettest,
            "coldest_month": driest,
            "annual_total": round(annual_total) if not np.isnan(annual_total) else None,
            "dry_months": dry_months,
            "wet_months": wet_months,
        },
    }


def _generic_indices(
    series: pd.Series,
    clim: pd.Series,
    annual: pd.Series,
    trend: Trend,
    where: str,
    unit: str,
    reference: tuple[int, int] = REFERENCE_PERIOD,
) -> dict[str, Any]:
    period = f"{reference[0]}-{reference[1]}"
    indices = [
        {
            "label": "Moyenne annuelle (normale)",
            "value": round(float(clim.mean()), 1) if not clim.empty else None,
            "unit": unit,
            "definition": f"Moyenne des douze moyennes mensuelles de {period}.",
        },
        {
            "label": "Valeur maximale observée",
            "value": round(float(series.max()), 1),
            "unit": unit,
            "definition": "Maximum mensuel de toute la série.",
        },
        {
            "label": "Valeur minimale observée",
            "value": round(float(series.min()), 1),
            "unit": unit,
            "definition": "Minimum mensuel de toute la série.",
        },
        {
            "label": "Tendance",
            "value": round(trend.per_decade, 2) if trend.valid else None,
            "unit": f"{unit}/décennie",
            "definition": "Régression linéaire des moyennes annuelles.",
            "reading": trend_reading(trend, unit),
        },
    ]
    narrative = ""
    if trend.valid:
        direction = "augmente" if trend.per_decade > 0 else "diminue"
        narrative = (
            f"La moyenne annuelle {where}{direction} de {_fmt(abs(trend.per_decade), 2)} "
            f"{unit} par décennie sur {trend.n} années."
        )
    return {"indices": indices, "narrative": narrative, "amplitude": None, "summary": {}}


def _anomaly_bars(
    annual: pd.Series,
    reference: tuple[int, int],
    unit: str,
) -> dict[str, Any]:
    """Anomalies annuelles par rapport à la normale, pour le graphique en barres."""
    ref = annual.loc[reference[0]: reference[1]]
    if ref.empty:
        return {"years": [], "values": [], "unit": unit, "reference": f"{reference[0]}-{reference[1]}"}
    base = float(ref.mean())
    values = annual - base
    return {
        "years": [int(y) for y in annual.index],
        "values": [None if pd.isna(v) else round(float(v), 2) for v in values],
        "unit": unit,
        "reference": f"{reference[0]}-{reference[1]}",
        "baseline": round(base, 2),
    }


# --------------------------------------------------------------------------- #
# Comparaison de périodes
# --------------------------------------------------------------------------- #


def compare_periods(
    series: pd.Series,
    period_a: tuple[int, int],
    period_b: tuple[int, int],
    *,
    monthly: bool = False,
) -> dict[str, Any]:
    """
    Compare deux périodes : moyennes mensuelles type ou moyennes annuelles.

    Sert à la page « Avant / Après » (20e vs 21e siècle, avant/après 1990…).
    """
    def window(period: tuple[int, int]) -> pd.Series:
        return series.loc[f"{period[0]}-01-01": f"{period[1]}-12-31"]

    a = window(period_a)
    b = window(period_b)

    if monthly:
        ca = a.groupby(a.index.month).mean() if not a.empty else pd.Series(dtype=float)
        cb = b.groupby(b.index.month).mean() if not b.empty else pd.Series(dtype=float)
        months = list(range(1, 13))
        return {
            "mode": "monthly",
            "labels": MONTH_LABELS_LONG,
            "series": [
                {"name": f"{period_a[0]}-{period_a[1]}", "values": [round(float(ca.get(m, np.nan)), 2) for m in months]},
                {"name": f"{period_b[0]}-{period_b[1]}", "values": [round(float(cb.get(m, np.nan)), 2) for m in months]},
            ],
            "delta": [round(float(cb.get(m, np.nan) - ca.get(m, np.nan)), 2) for m in months],
        }

    aa = annual_mean(a)
    bb = annual_mean(b)
    return {
        "mode": "annual",
        "labels": [str(y) for y in list(aa.index) + list(bb.index)],
        "series": [
            {"name": f"{period_a[0]}-{period_a[1]}", "values": [round(float(v), 2) for v in aa.values]},
            {"name": f"{period_b[0]}-{period_b[1]}", "values": [round(float(v), 2) for v in bb.values]},
        ],
        "mean_a": round(float(aa.mean()), 2) if not aa.empty else None,
        "mean_b": round(float(bb.mean()), 2) if not bb.empty else None,
        "delta_mean": round(float(bb.mean() - aa.mean()), 2) if not (aa.empty or bb.empty) else None,
    }


def day_counts(
    daily: pd.Series,
    *,
    threshold: float,
    direction: str = "above",
) -> dict[str, Any]:
    """Nombre de jours par an dépassant (ou non) un seuil — activité canicule."""
    if daily.empty:
        return {"years": [], "values": [], "threshold": threshold, "total": 0}
    mask = (daily >= threshold) if direction == "above" else (daily <= threshold)
    counts = mask.astype(float).groupby(daily.index.year).sum()
    return {
        "years": [int(y) for y in counts.index],
        "values": [int(v) for v in counts.values],
        "threshold": threshold,
        "direction": direction,
        "total": int(counts.sum()),
        "average": round(float(counts.mean()), 1),
        "max_year": int(counts.idxmax()) if not counts.empty else None,
        "max_value": int(counts.max()) if not counts.empty else None,
    }
