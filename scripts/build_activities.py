"""
Fiches d'activités autonomes (HTML + PDF).

Génère, pour chaque activité de `c3s2.activities`, une page HTML **autonome**
(CSS, JavaScript et figures encodés dans le fichier : aucun serveur requis) :

    python scripts/build_activities.py

Sorties dans `public/activites/` :

* `<clé>.html` — fiche projetable et imprimable ;
* `index.html` — sommaire des 10 fiches ;
* `pdf/<clé>.pdf` et `pdf/<clé>-corrige.pdf` — voir `pw-export-pdf.js`
  (versions élève verrouillée / enseignant déverrouillée).

Figures (matplotlib) construites sur les **données réelles** :

* normales mensuelles 1991-2020 (CSV pré-calculés) pour `climato` / `ombro` ;
* séries annuelles 1940-2024 + tendance pour `annual` ;
* anomalies annuelles pour `anomalies` ;
* deux périodes de 30 ans pour `compare` ;
* champs ERA5 statiques pour `map` (température, pluie, pression, vent).

Les graphiques montrent les données brutes nécessaires à la mesure, sans les
résultats calculés (amplitudes, cumuls, écarts) : c'est à l'élève de les
produire. Seule la tendance linéaire (lue, non calculée, comme dans
l'application) est annotée.

Les corrigés sont embarqués **chiffrés** (XOR + base64, clé = code
enseignant) : ils n'apparaissent ni à l'écran ni dans le code source tant que
le code n'est pas saisi.
"""

from __future__ import annotations

import argparse
import base64
import html as htmlmod
import io
import json
import sys
from pathlib import Path
from urllib.parse import quote

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.patheffects as pe  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from matplotlib.patches import Polygon as MplPolygon  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from c3s2 import activities, config, datasets, fields, places, store  # noqa: E402

OUT_DIR = ROOT / "public" / "activites"
TEACHER_CODE = "2027"

MONTHS = [
    "janv.", "févr.", "mars", "avr.", "mai", "juin",
    "juil.", "août", "sept.", "oct.", "nov.", "déc.",
]
CITY_COLORS = ["#e07a5f", "#4c7fd1", "#2a9d8f", "#7a5cc2", "#f2a541", "#d64545"]

PALETTES = {
    "temperature": [(0, "#31688e"), (0.25, "#35b779"), (0.5, "#f9d34a"), (0.75, "#f2863c"), (1, "#c2312b")],
    "precipitation": [(0, "#f7fbff"), (0.2, "#c6dbef"), (0.45, "#6baed6"), (0.7, "#3182bd"), (1, "#08306b")],
    "pressure": [(0, "#440154"), (0.3, "#3b528b"), (0.5, "#21918c"), (0.7, "#5ec962"), (1, "#fde725")],
    "wind": [(0, "#f2f7fb"), (0.3, "#a8d8e8"), (0.55, "#4c9fc4"), (0.8, "#2a6f97"), (1, "#12345f")],
    "viridis": [(0, "#440154"), (0.5, "#21918c"), (1, "#fde725")],
}

plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 10,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.alpha": 0.25,
        "grid.linestyle": "--",
    }
)


# --------------------------------------------------------------------------- #
# Données
# --------------------------------------------------------------------------- #


def _normals(variable: str, city: str, start: int = 1991, end: int = 2020) -> pd.Series:
    frame = store._frame(variable)
    if frame is None or city not in frame.columns:
        raise KeyError(f"Série manquante : {variable} / {city}")
    sub = frame.loc[f"{start}":f"{end}", city].dropna()
    return sub.groupby(sub.index.month).mean()


def _annual(city: str) -> pd.Series:
    frame = store._frame("2m_temperature")
    if frame is None or city not in frame.columns:
        raise KeyError(f"Série manquante : 2m_temperature / {city}")
    annual = frame[city].dropna().resample("YE").mean()
    annual.index = annual.index.year
    return annual


def _coastlines() -> list[list[tuple[float, float]]]:
    path = ROOT / "data" / "maps" / "ne_110m_coastline.geojson"
    gj = json.loads(path.read_text(encoding="utf-8"))
    lines: list[list[tuple[float, float]]] = []
    for feat in gj.get("features", []):
        geom = feat.get("geometry") or {}
        if geom.get("type") == "LineString":
            lines.append([(float(x), float(y)) for x, y in geom.get("coordinates", [])])
    return lines


_COASTLINES: list[list[tuple[float, float]]] | None = None


def coastlines() -> list[list[tuple[float, float]]]:
    global _COASTLINES
    if _COASTLINES is None:
        _COASTLINES = _coastlines()
    return _COASTLINES


_LAND: list[list[tuple[float, float]]] | None = None


def land_polys() -> list[list[tuple[float, float]]]:
    """Anneaux des continents (fond de carte des situations et schémas)."""
    global _LAND
    if _LAND is None:
        path = ROOT / "data" / "maps" / "ne_110m_land.geojson"
        gj = json.loads(path.read_text(encoding="utf-8"))
        polys: list[list[tuple[float, float]]] = []
        for feat in gj.get("features", []):
            for ring in feat.get("geometry", {}).get("coordinates", []):
                polys.append([(float(x), float(y)) for x, y in ring])
        _LAND = polys
    return _LAND


def city_points(cities: list[str]) -> list[tuple[str, float, float]]:
    """(nom, longitude, latitude) pour les villes connues, dans l'ordre."""
    pts: list[tuple[str, float, float]] = []
    for city in cities:
        place = places.get(city)
        if place is not None:
            pts.append((city, float(place.lon), float(place.lat)))
    return pts


def draw_land(ax: plt.Axes) -> None:
    for ring in land_polys():
        ax.add_patch(MplPolygon(ring, closed=True, fc="#e3eaf2", ec="#94a3b8", lw=0.5, zorder=1))
    for line in coastlines():
        ax.plot(
            [p[0] for p in line], [p[1] for p in line],
            color="#64748b", lw=0.5, zorder=2,
        )


def draw_cities(ax: plt.Axes, pts: list[tuple[str, float, float]], fontsize: int = 10) -> None:
    for i, (name, x, y) in enumerate(pts):
        ax.scatter([x], [y], s=100, c=CITY_COLORS[i % len(CITY_COLORS)],
                   ec="white", lw=1.5, zorder=5)
        ax.text(
            x, y, "  " + name, fontsize=fontsize, fontweight="bold", color="#1f3a5f",
            va="center", ha="left", zorder=6,
            path_effects=[pe.withStroke(linewidth=3, foreground="white")],
        )


def fig_situation(cities: list[str]) -> tuple[str, str]:
    """Carte de situation des villes (emprise calculée automatiquement)."""
    pts = city_points(cities)
    if not pts:
        raise KeyError(f"Aucune ville connue parmi : {cities}")
    lons = [x for _, x, _ in pts]
    lats = [y for _, _, y in pts]
    dx = max(max(lons) - min(lons), 0.1)
    dy = max(max(lats) - min(lats), 0.1)
    x0, x1 = min(lons) - dx * 0.35 - 3, max(lons) + dx * 0.35 + 3
    y0, y1 = max(min(lats) - dy * 0.4 - 2.5, -60), min(max(lats) + dy * 0.4 + 2.5, 84)
    fig, ax = plt.subplots(figsize=(8.6, 4.1))
    draw_land(ax)
    draw_cities(ax, pts)
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_xlabel("Longitude (°E)")
    ax.set_ylabel("Latitude (°N)")
    ax.set_title("Situation — " + ", ".join(cities), pad=10)
    return "png", _as_png(fig)


def fig_courants() -> tuple[str, str]:
    """Schéma simplifié des courants de surface de l'Atlantique Nord.

    Le CDS ne fournit pas de courants : ce schéma pédagogique (flèches
    stylisées, pas des données) montre le Gulf Stream chaud vers l'Europe et
    le courant froid du Labrador vers le Canada, avec les vents d'ouest.
    """
    fig, ax = plt.subplots(figsize=(9.0, 5.6))
    draw_land(ax)
    draw_cities(ax, city_points(["Bordeaux", "Montréal"]))

    def arrow(path: list[tuple[float, float]], color: str, width: float = 2.6) -> None:
        for (x0, y0), (x1, y1) in zip(path[:-1], path[1:]):
            ax.annotate(
                "", xy=(x1, y1), xytext=(x0, y0),
                arrowprops={"arrowstyle": "->", "color": color, "lw": width,
                            "shrinkA": 0, "shrinkB": 3},
                zorder=4,
            )

    # Gulf Stream puis dérive nord-atlantique (chaud, vers l'Europe).
    arrow([(-80, 27), (-74, 34), (-66, 39), (-55, 42), (-42, 46)], "#c2312b")
    arrow([(-42, 46), (-30, 50), (-18, 54), (-8, 55)], "#e07a5f")
    # Courant du Labrador (froid, vers le sud le long du Canada).
    arrow([(-56, 61), (-55, 55), (-53, 49), (-50, 45)], "#31688e")
    # Vents d'ouest (gris, d'ouest en est).
    for y in (38, 46, 54):
        arrow([(-70, y), (-52, y), (-34, y)], "#64748b", width=1.4)
    ax.text(-66, 31, "Gulf Stream\n(chaud)", color="#c2312b", fontsize=9,
            fontweight="bold", ha="center",
            path_effects=[pe.withStroke(linewidth=3, foreground="white")], zorder=6)
    ax.text(-58, 56.5, "Labrador\n(froid)", color="#31688e", fontsize=9,
            fontweight="bold", ha="center",
            path_effects=[pe.withStroke(linewidth=3, foreground="white")], zorder=6)
    ax.text(-44, 34.5, "vents d'ouest", color="#475569", fontsize=9, ha="center",
            path_effects=[pe.withStroke(linewidth=3, foreground="white")], zorder=6)
    ax.set_xlim(-85, 5)
    ax.set_ylim(28, 64)
    ax.set_xlabel("Longitude (°E)")
    ax.set_ylabel("Latitude (°N)")
    ax.set_title("Courants de surface de l'Atlantique Nord — schéma simplifié", pad=10)
    return "png", _as_png(fig)


def _nino_series() -> pd.Series:
    path = ROOT / "data" / "precomputed" / "nino34_sst.csv"
    serie = pd.read_csv(path, sep=";", index_col=0, parse_dates=True).iloc[:, 0]
    serie.index = pd.to_datetime(serie.index)
    return serie.sort_index()


def _nino_baseline(serie: pd.Series) -> pd.Series:
    window = serie.loc["1991":"2020"]
    return window.groupby(window.index.month).mean()


def _save_figure_png(fig: plt.Figure, filename: str) -> str:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    payload = _as_png(fig)
    (FIGURES_DIR / filename).write_bytes(base64.b64decode(payload))
    return payload


FIGURES_DIR = ROOT / "public" / "assets" / "figures"


def fig_nino_series(filename: str) -> tuple[str, str, str]:
    """Températures mensuelles Niño 3.4 : 2025 contre 2026 (données réelles)."""
    serie = _nino_series()
    y25 = serie.loc["2025"]
    y26 = serie.loc["2026"]
    fig, ax = plt.subplots(figsize=(8.6, 4.6))
    ax.plot(range(1, 13), y25.values, marker="o", color="#64748b", lw=2, label="2025")
    x26 = list(y26.index.month)
    ax.plot(x26, y26.values, marker="o", color="#c2312b", lw=2.5, label="2026 (janv.–août)")
    ax.set_xticks(range(1, 13))
    ax.set_xticklabels(MONTHS)
    ax.set_ylabel("Température (°C)")
    ax.set_title("Température de la boîte Niño 3.4 — 2025 et 2026", pad=12)
    ax.legend(frameon=False, loc="best")
    payload = _save_figure_png(fig, filename)
    return "png", payload, "Température mensuelle de la boîte Niño 3.4 (ERA5, données réelles)."


def fig_nino_anom(filename: str) -> tuple[str, str, str]:
    """Anomalies mensuelles 2025-2026 par rapport à la normale 1991-2020."""
    serie = _nino_series()
    base = _nino_baseline(serie)
    sel = pd.concat([serie.loc["2025"], serie.loc["2026"]])
    anom = sel.values - base[sel.index.month].values
    colors = ["#c2312b" if v >= 0 else "#31688e" for v in anom]
    labels = [f"{MONTHS[d.month - 1]} {d.year}" for d in sel.index]
    fig, ax = plt.subplots(figsize=(8.6, 4.6))
    ax.bar(range(len(sel)), anom, color=colors)
    ax.axhline(0, color="black", lw=0.8)
    ax.set_xticks(range(len(sel)))
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("Anomalie (°C)")
    ax.set_title("Anomalie mensuelle — 2025 et 2026 (normale 1991-2020)", pad=12)
    payload = _save_figure_png(fig, filename)
    return "png", payload, "Écart de chaque mois à la normale 1991-2020 du même mois."


def fig_nino_timeline(filename: str) -> tuple[str, str, str]:
    """Anomalies mensuelles 2023-2026 : El Niño 2023-2024 puis 2026."""
    serie = _nino_series()
    base = _nino_baseline(serie)
    window = serie.loc["2023":]
    anom = window.values - base[window.index.month].values
    colors = ["#c2312b" if v >= 0 else "#31688e" for v in anom]
    fig, ax = plt.subplots(figsize=(8.6, 4.6))
    ax.bar(range(len(window)), anom, color=colors, width=0.9)
    ax.axhline(0, color="black", lw=0.8)
    ax.axhline(0.5, color="#c2312b", lw=1, ls="--", alpha=0.7)
    step = 6
    ax.set_xticks(range(0, len(window), step))
    ax.set_xticklabels(
        [f"{MONTHS[d.month - 1]} {d.year}" for d in window.index[::step]],
        rotation=45, ha="right", fontsize=8
    )
    ax.set_ylabel("Anomalie (°C)")
    ax.set_title("Anomalie mensuelle 2023-2026 — El Niño puis réchauffement 2026", pad=12)
    payload = _save_figure_png(fig, filename)
    return "png", payload, "Pointillés : +0,5 °C, seuil d'un hiver El Niño."


def fig_nino_box(filename: str) -> tuple[str, str, str]:
    """Situation de la boîte Niño 3.4 dans le Pacifique tropical."""
    from matplotlib.patches import Rectangle as MplRectangle

    fig, ax = plt.subplots(figsize=(8.6, 4.4))
    draw_land(ax)
    box = MplRectangle((-170, -5), 50, 10, fc="none",
                       ec="#c2312b", lw=2.5, zorder=5)
    ax.add_patch(box)
    ax.text(-145, 0, "Niño 3.4", color="#c2312b", fontsize=11, fontweight="bold",
            ha="center", va="center", zorder=6,
            path_effects=[pe.withStroke(linewidth=3, foreground="white")])
    ax.set_xlim(-180, -60)
    ax.set_ylim(-30, 30)
    ax.set_xlabel("Longitude (°E)")
    ax.set_ylabel("Latitude (°N)")
    ax.set_title("La boîte Niño 3.4 (5° N–5° S, 170° O–120° O)", pad=10)
    payload = _save_figure_png(fig, filename)
    return "png", payload, "Zone de surveillance d'El Niño : moyenne des températures de surface."


def data_figures(act_key: str, n: int) -> list[tuple[str, str, str]]:
    """Figures de données pré-calculées (PNG servis aussi à l'application).

    El Niño : étape 1 = séries 2025/2026 (+ situation de la boîte),
    étape 2 = anomalies mensuelles, étape 3 = chronologie 2023-2026,
    étape 4 = situation de la boîte étudiée.
    """
    if act_key == "elnino":
        if n == 1:
            return [fig_nino_series("elnino_1.png"), fig_nino_box("elnino_1b.png")]
        if n == 2:
            return [fig_nino_anom("elnino_2.png")]
        if n == 3:
            return [fig_nino_timeline("elnino_3.png")]
        return [fig_nino_box("elnino_4.png")]
    raise KeyError(f"Aucune figure de données pour : {act_key} (étape {n})")


# --------------------------------------------------------------------------- #
# Figures
# --------------------------------------------------------------------------- #


def _as_svg(fig: plt.Figure) -> str:
    buf = io.StringIO()
    fig.savefig(buf, format="svg", bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


def _as_png(fig: plt.Figure, dpi: int = 150) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def fig_climato(cities: list[str]) -> tuple[str, str]:
    fig, ax = plt.subplots(figsize=(8.6, 4.6))
    for i, city in enumerate(cities):
        m = _normals("2m_temperature", city)
        ax.plot(
            range(1, 13), [m.get(mo, np.nan) for mo in range(1, 13)],
            marker="o", ms=4.5, lw=2, color=CITY_COLORS[i % len(CITY_COLORS)], label=city,
        )
    ax.set_xticks(range(1, 13))
    ax.set_xticklabels(MONTHS)
    ax.set_ylabel("Température (°C)")
    ax.set_title(f"Normale mensuelle 1991-2020 — {', '.join(cities)}", pad=12)
    ax.legend(frameon=False, loc="best", fontsize=9)
    fig.text(0.01, -0.01, "Source : ERA5 pré-calculé (moyennes mensuelles 1991-2020).", fontsize=8, color="#64748b")
    return "svg", _as_svg(fig)


def fig_ombro(cities: list[str]) -> tuple[str, str]:
    fig, ax = plt.subplots(figsize=(8.6, 4.8))
    ax2 = ax.twinx()
    n = max(len(cities), 1)
    width = 0.78 / n
    x = np.arange(1, 13)
    for i, city in enumerate(cities):
        color = CITY_COLORS[i % len(CITY_COLORS)]
        p = _normals("total_precipitation", city)
        t = _normals("2m_temperature", city)
        pv = [p.get(mo, np.nan) for mo in range(1, 13)]
        tv = [t.get(mo, np.nan) for mo in range(1, 13)]
        off = (i - (n - 1) / 2) * width
        ax2.bar(x + off, pv, width=width * 0.92, color=color, alpha=0.5, label=f"{city} — pluie")
        ax.plot(x, tv, marker="o", ms=4, lw=2, color=color, label=f"{city} — température")
        ax.plot(x, [2 * v for v in tv], color=color, ls=":", lw=1.2, alpha=0.85)
    ax.set_xticks(range(1, 13))
    ax.set_xticklabels(MONTHS)
    ax.set_ylabel("Température (°C)")
    ax2.set_ylabel("Précipitations (mm/mois)")
    ax.set_title(f"Diagramme ombrothermique — normale 1991-2020 — {', '.join(cities)}", pad=12)
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, frameon=False, loc="upper left", fontsize=8, ncol=2)
    fig.text(
        0.01, -0.01,
        "Barres = pluie mensuelle (mm) · courbe = température (°C) · pointillés = 2×T (seuil d'aridité).",
        fontsize=8, color="#64748b",
    )
    return "svg", _as_svg(fig)


def fig_annual(city: str, start: int = 1940, end: int = 2024) -> tuple[str, str]:
    annual = _annual(city)
    annual = annual[(annual.index >= start) & (annual.index <= end)]
    x = annual.index.to_numpy(dtype=float)
    y = annual.to_numpy(dtype=float)
    coef = np.polyfit(x, y, 1)
    slope_decade = coef[0] * 10
    fig, ax = plt.subplots(figsize=(8.6, 4.6))
    ax.plot(x, y, color=CITY_COLORS[0], lw=1.4, label="Moyenne annuelle")
    ax.plot(x, coef[0] * x + coef[1], color="#1f3a5f", lw=2, ls="--", label="Tendance linéaire")
    ax.set_xlabel("Année")
    ax.set_ylabel("Température (°C)")
    ax.set_title(f"Moyennes annuelles {start}–{end} — {city}", pad=12)
    ax.text(
        0.02, 0.94,
        f"Tendance : {slope_decade:+.2f} °C par décennie".replace(".", ","),
        transform=ax.transAxes, fontsize=10, color="#1f3a5f",
        bbox={"facecolor": "white", "edgecolor": "#cbd5e1", "boxstyle": "round,pad=0.4"},
    )
    ax.legend(frameon=False, loc="lower right", fontsize=9)
    fig.text(0.01, -0.01, "Source : ERA5 pré-calculé (moyennes annuelles).", fontsize=8, color="#64748b")
    return "svg", _as_svg(fig)


def fig_anomalies(city: str, ref: tuple[int, int] = (1991, 2020)) -> tuple[str, str]:
    annual = _annual(city)
    baseline = annual[(annual.index >= ref[0]) & (annual.index <= ref[1])].mean()
    anom = annual - baseline
    colors = ["#c2312b" if v >= 0 else "#31688e" for v in anom.values]
    fig, ax = plt.subplots(figsize=(8.6, 4.6))
    ax.bar(anom.index, anom.values, color=colors, width=0.9)
    ax.axhline(0, color="black", lw=0.8)
    ax.set_xlabel("Année")
    ax.set_ylabel("Anomalie (°C)")
    ax.set_title(
        f"Anomalie annuelle par rapport à {ref[0]}–{ref[1]} ({baseline:.1f} °C) — {city}".replace(".", ","),
        pad=12,
    )
    fig.text(0.01, -0.01, "Écart de chaque année à la moyenne de la période de référence.", fontsize=8, color="#64748b")
    return "svg", _as_svg(fig)


def fig_compare(city: str, period_a: tuple[int, int] = (1941, 1970), period_b: tuple[int, int] = (1991, 2020)) -> tuple[str, str]:
    frame = store._frame("2m_temperature")
    if frame is None or city not in frame.columns:
        raise KeyError(f"Série manquante : 2m_temperature / {city}")
    col = frame[city].dropna()
    ma = col.loc[f"{period_a[0]}":f"{period_a[1]}"].groupby(col.loc[f"{period_a[0]}":f"{period_a[1]}"].index.month).mean()
    mb = col.loc[f"{period_b[0]}":f"{period_b[1]}"].groupby(col.loc[f"{period_b[0]}":f"{period_b[1]}"].index.month).mean()
    va = [ma.get(mo, np.nan) for mo in range(1, 13)]
    vb = [mb.get(mo, np.nan) for mo in range(1, 13)]
    mean_a, mean_b = float(np.nanmean(va)), float(np.nanmean(vb))
    delta = mean_b - mean_a
    x = np.arange(1, 13)
    fig, ax = plt.subplots(figsize=(8.6, 4.6))
    ax.bar(x - 0.2, va, width=0.38, color="#94a3b8", label=f"{period_a[0]}–{period_a[1]}")
    ax.bar(x + 0.2, vb, width=0.38, color=CITY_COLORS[0], label=f"{period_b[0]}–{period_b[1]}")
    ax.set_xticks(range(1, 13))
    ax.set_xticklabels(MONTHS)
    ax.set_ylabel("Température (°C)")
    ax.set_title(f"{city} — {period_a[0]}–{period_a[1]} comparé à {period_b[0]}–{period_b[1]}", pad=12)
    ax.text(
        0.02, 0.94,
        f"Moyennes : {mean_a:.1f} °C → {mean_b:.1f} °C, soit {delta:+.1f} °C".replace(".", ","),
        transform=ax.transAxes, fontsize=10, color="#1f3a5f",
        bbox={"facecolor": "white", "edgecolor": "#cbd5e1", "boxstyle": "round,pad=0.4"},
    )
    ax.legend(frameon=False, loc="lower right", fontsize=9)
    fig.text(0.01, -0.01, "Normales mensuelles sur deux périodes de trente ans.", fontsize=8, color="#64748b")
    return "svg", _as_svg(fig)


def _palette_cmap(name: str) -> LinearSegmentedColormap:
    stops = PALETTES.get(name, PALETTES["viridis"])
    return LinearSegmentedColormap.from_list(name, [(pos, col) for pos, col in stops])


def fig_map(map_id: str) -> tuple[str, str]:
    payload = fields.load_map(map_id)
    lat = np.array(payload["lat"], dtype=float)
    lon = np.array(payload["lon"], dtype=float)
    z = np.array(payload["z"], dtype=float)
    area = payload.get("area") or [lat.max(), lon.min(), lat.min(), lon.max()]
    north, west, south, east = area
    unit = payload.get("unit", "")
    title = payload.get("title", map_id)

    fig, ax = plt.subplots(figsize=(9.0, 5.6))
    cmap = _palette_cmap(payload.get("palette", "viridis"))
    mesh = ax.pcolormesh(lon, lat, z, cmap=cmap, shading="auto")
    for line in coastlines():
        xs = [p[0] for p in line]
        ys = [p[1] for p in line]
        ax.plot(xs, ys, color="#1f2937", lw=0.6)
    if "u" in payload and "v" in payload:
        u = np.array(payload["u"], dtype=float)
        v = np.array(payload["v"], dtype=float)
        step = max(1, int(round(max(z.shape) / 24)))
        ax.quiver(
            lon[::step], lat[::step], u[::step, ::step], v[::step, ::step],
            color="white", scale=60, width=0.004, headwidth=3.5, headlength=4,
        )
    ax.set_xlim(west, east)
    ax.set_ylim(south, north)
    ax.set_xlabel("Longitude (°E)")
    ax.set_ylabel("Latitude (°N)")
    ax.set_title(title, pad=12)
    cbar = fig.colorbar(mesh, ax=ax, shrink=0.85, pad=0.02)
    cbar.set_label(unit)
    fig.text(
        0.01, -0.01,
        f"{payload.get('source', 'ERA5')} · {payload.get('attribution', config.ERA5_ATTRIBUTION)}",
        fontsize=7, color="#64748b",
    )
    return "png", _as_png(fig)


# --------------------------------------------------------------------------- #
# Verrouillage des corrigés
# --------------------------------------------------------------------------- #


def lock_text(text: str, code: str = TEACHER_CODE) -> str:
    """Chiffre un corrigé (URL-encodé, XOR avec le code, base64)."""
    raw = quote(text, safe="").encode("ascii")
    key = code.encode("ascii")
    mixed = bytes(b ^ key[i % len(key)] for i, b in enumerate(raw))
    return base64.b64encode(mixed).decode("ascii")


# --------------------------------------------------------------------------- #
# Gabarit HTML
# --------------------------------------------------------------------------- #

CSS = """
:root{
  --ink:#1e293b; --muted:#64748b; --line:#e2e8f0; --card:#ffffff; --bg:#f1f5f9;
  --navy:#1f3a5f; --accent:#e07a5f; --ok:#15803d; --okbg:#dcfce7; --amberbg:#fef3c7;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font-family:"Segoe UI",Roboto,"Helvetica Neue",Arial,"DejaVu Sans",sans-serif;line-height:1.55}
.topbar{background:var(--navy);color:#fff;padding:.55rem 1rem;display:flex;gap:1rem;align-items:center}
.topbar a{color:#fff;text-decoration:none;font-weight:600}
.topbar .brand{display:flex;align-items:center;gap:.5rem}
.badge{display:inline-block;background:#eef2ff;border:1px solid var(--line);border-radius:999px;
  padding:.05rem .6rem;font-size:.8rem;color:var(--navy);margin:.1rem .15rem .1rem 0}
.wrap{max-width:1020px;margin:0 auto;padding:1.2rem 1rem 3rem}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:1.1rem 1.2rem;margin:1rem 0}
h1{font-size:1.7rem;margin:.2rem 0 .6rem;color:var(--navy)}
h2{font-size:1.15rem;color:var(--navy);margin:.2rem 0 .5rem}
.kicker{color:var(--accent);font-weight:700;letter-spacing:.06em;font-size:.8rem;text-transform:uppercase}
.question{border-left:4px solid var(--accent);background:#fff7ed;border-radius:0 10px 10px 0;
  padding:.7rem .9rem;font-weight:600;margin:.6rem 0}
.hint{background:#f8fafc;border:1px dashed #94a3b8;border-radius:10px;padding:.55rem .8rem;margin:.5rem 0;font-size:.95rem}
.hint b{color:var(--navy)}
figure{margin:.8rem 0}
figure svg, figure img{max-width:100%;height:auto;background:#fff;border:1px solid var(--line);border-radius:10px}
figcaption{font-size:.82rem;color:var(--muted);margin-top:.25rem}
.step-head{display:flex;align-items:center;gap:.6rem;flex-wrap:wrap}
.step-n{background:var(--navy);color:#fff;font-weight:700;border-radius:10px;min-width:2rem;height:2rem;
  display:inline-flex;align-items:center;justify-content:center}
.teacher{background:#fffbeb;border:1px solid #f59e0b;border-radius:12px;padding:.8rem 1rem}
input[type=password]{padding:.45rem .6rem;border:1px solid var(--line);border-radius:8px;max-width:220px}
.btn{background:var(--navy);color:#fff;border:none;border-radius:9px;padding:.5rem 1rem;font-weight:600;cursor:pointer}
.btn:hover{filter:brightness(1.12)}
.btn-warm{background:var(--accent)}
.answer{display:none;background:#f0fdf4;border:1px solid #86efac;border-radius:10px;padding:.7rem .9rem;margin:.5rem 0}
.answer.visible{display:block}
.badge-ok{background:var(--okbg);color:var(--ok);border:1px solid #86efac}
footer{color:var(--muted);font-size:.8rem;margin-top:2rem}
.tip{background:var(--amberbg);border-left:4px solid #f59e0b;border-radius:0 10px 10px 0;padding:.6rem .9rem}
.exam-rappel{background:#f6f9ff;border-left:4px solid var(--navy);border-radius:0 10px 10px 0;padding:.6rem .9rem;margin:.6rem 0}
.exam-doc{border:1px solid var(--line);border-radius:10px;padding:.7rem .9rem;margin:.7rem 0;background:#fbfcfe}
.exam-doc h4{margin:.1rem 0 .35rem;font-size:1rem;color:var(--navy)}
.exam-table{width:100%;border-collapse:collapse;font-size:.92rem;margin:.5rem 0}
.exam-table th,.exam-table td{border:1px solid var(--line);padding:.4rem .6rem;text-align:left}
.exam-table th{background:#eef2ff;color:var(--navy);font-size:.85rem}
.exam-q{border:1px solid var(--line);border-radius:10px;padding:.7rem .9rem;margin:.7rem 0}
.exam-q h3{margin:.1rem 0}
@media print{
  body{background:#fff}
  .topbar,.no-print{display:none !important}
  .wrap{max-width:none;padding:0}
  .card{break-inside:avoid;border-color:#cbd5e1}
  figure svg, figure img{-print-color-adjust:exact;print-color-adjust:exact}
  .step{break-inside:avoid}
  a{color:var(--ink);text-decoration:none}
}
"""

JS = """
(function(){
  var CODE = "2027";
  var KEY = "c3s_standalone_code";
  function lockedDecode(b64, code){
    var bin = atob(b64), pct = "";
    for (var i = 0; i < bin.length; i++){
      pct += String.fromCharCode(bin.charCodeAt(i) ^ code.charCodeAt(i % code.length));
    }
    return decodeURIComponent(pct);
  }
  function refresh(){
    var unlocked = false;
    try { unlocked = (localStorage.getItem(KEY) || "") === CODE; } catch(e){}
    document.querySelectorAll("[data-locked-step]").forEach(function(box){
      var btn = box.querySelector(".btn-answer");
      var ans = box.querySelector(".answer");
      if (unlocked){
        try {
          if (!ans.dataset.done){
            ans.innerHTML = "<b>Corrigé.</b> " + lockedDecode(ans.dataset.locked, CODE);
            ans.dataset.done = "1";
          }
        } catch(e){ ans.textContent = "Corrigé illisible."; }
        if (btn) btn.style.display = "none";
        ans.classList.add("visible");
      } else {
        if (btn) btn.style.display = "";
        ans.classList.remove("visible");
      }
    });
    var badge = document.getElementById("lock-badge");
    if (badge) badge.style.display = unlocked ? "" : "none";
    var form = document.getElementById("lock-form");
    if (form) form.style.display = unlocked ? "none" : "";
  }
  document.addEventListener("click", function(ev){
    if (ev.target && ev.target.id === "lock-btn"){
      var input = document.getElementById("lock-code");
      var code = (input && input.value || "").trim();
      var out = document.getElementById("lock-out");
      if (code === CODE){
        try { localStorage.setItem(KEY, code); } catch(e){}
        refresh();
      } else if (out){
        out.innerHTML = '<span class="badge">Code incorrect</span>';
      }
    }
    if (ev.target && ev.target.classList && ev.target.classList.contains("btn-forget")){
      try { localStorage.removeItem(KEY); } catch(e){}
      refresh();
    }
  });
  refresh();
})();
"""

CHART_LABELS = {
    "none": "travail au brouillon",
    "climato": "normale mensuelle",
    "ombro": "diagramme ombrothermique",
    "annual": "moyennes annuelles",
    "anomalies": "anomalies annuelles",
    "compare": "comparaison de périodes",
    "map": "carte climatique",
    "schema": "schéma des courants",
    "figure": "figure de données",
}


def esc(text: str) -> str:
    return htmlmod.escape(text or "", quote=True)


def figure_html(kind: str, payload: str, caption: str = "") -> str:
    if kind == "svg":
        inner = payload
    else:
        inner = f'<img src="data:image/png;base64,{payload}" alt="{esc(caption)}">'
    cap = f"<figcaption>{esc(caption)}</figcaption>" if caption else ""
    return f"<figure>{inner}{cap}</figure>"


def activity_maps(act: activities.Activity) -> list[str]:
    key = act.key
    if key == "cartes_climatiques":
        return ["t2m_janvier", "t2m_juillet", "t2m_juillet", "t2m_janvier"]
    if key == "vent_pression":
        return ["mslp_janvier", "mslp_janvier", "vent_janvier", "vent_janvier"]
    if key == "pluies_europe":
        return ["tp_janvier", "tp_juillet", "tp_juillet", "tp_janvier"]
    return []


def step_figures(act: activities.Activity) -> list[list[tuple[str, str, str]]]:
    """Figures (format, contenu, légende) pour chaque étape."""
    cities = list(act.default_cities) or ["Paris"]
    out: list[list[tuple[str, str, str]]] = []
    maps = activity_maps(act)
    map_cache: dict[str, tuple[str, str]] = {}
    for n, step in enumerate(act.steps, start=1):
        figs: list[tuple[str, str, str]] = []
        chart = step.chart
        if chart == "climato":
            kind, payload = fig_climato(cities[:4])
            figs.append((kind, payload, f"Normale mensuelle 1991-2020 — {', '.join(cities[:4])}."))
        elif chart == "ombro":
            kind, payload = fig_ombro(cities[:2])
            figs.append((kind, payload, f"Diagramme ombrothermique 1991-2020 — {', '.join(cities[:2])}."))
        elif chart == "annual":
            kind, payload = fig_annual(cities[0])
            figs.append((kind, payload, f"Moyennes annuelles 1940-2024 et tendance — {cities[0]}."))
        elif chart == "anomalies":
            kind, payload = fig_anomalies(cities[0])
            figs.append((kind, payload, f"Écart de chaque année à la moyenne 1991-2020 — {cities[0]}."))
        elif chart == "compare":
            kind, payload = fig_compare(cities[0])
            figs.append((kind, payload, f"Deux périodes de trente ans comparées mois par mois — {cities[0]}."))
        elif chart == "schema":
            kind, payload = fig_courants()
            figs.append((kind, payload, "Schéma simplifié des courants (pas une donnée CDS)."))
        elif chart == "figure":
            for kind, payload, caption in data_figures(act.key, n):
                figs.append((kind, payload, caption))
        elif chart == "map" and n - 1 < len(maps):
            mid = maps[n - 1]
            if mid not in map_cache:
                map_cache[mid] = fig_map(mid)
            kind, payload = map_cache[mid]
            meta = fields.load_map(mid)
            figs.append((kind, payload, f"{meta.get('title', mid)} · {meta.get('source', '')}"))
        out.append(figs)
    return out


def exam_doc_html(doc: activities.ExamDoc, act: activities.Activity) -> str:
    """Un document du sujet type brevet (figure, graphique ou tableau)."""
    visual = ""
    if doc.chart in ("annual", "anomalies"):
        city = (list(act.default_cities) or ["Paris"])[0]
        kind, payload = fig_annual(city) if doc.chart == "annual" else fig_anomalies(city)
        visual = figure_html(kind, payload, doc.caption)
    elif doc.chart == "figure":
        path = FIGURES_DIR / doc.file
        if path.exists():
            payload = base64.b64encode(path.read_bytes()).decode("ascii")
            visual = figure_html("png", payload, doc.caption)
        else:
            visual = (
                '<div class="hint"><b>Figure absente.</b> Relancez '
                "<code>python scripts/build_activities.py</code> pour la générer.</div>"
            )
    elif doc.chart == "table" and doc.table:
        head, *body = doc.table
        head_html = "".join(f"<th>{esc(c)}</th>" for c in head)
        body_html = "".join(
            "<tr>" + "".join(f"<td>{esc(c)}</td>" for c in row) + "</tr>" for row in body
        )
        cap = f"<figcaption>{esc(doc.caption)}</figcaption>" if doc.caption else ""
        visual = (
            f'<table class="exam-table"><thead><tr>{head_html}</tr></thead>'
            f"<tbody>{body_html}</tbody></table>{cap}"
        )
    return f"""
      <figure class="exam-doc">
        <h4>Document {doc.number} — {esc(doc.title)}</h4>
        <p class="small">{esc(doc.body)}</p>
        {visual}
      </figure>"""


def render_exam(act: activities.Activity) -> str:
    """Section « Sujet type brevet » d'une fiche (corrigés chiffrés)."""
    exam = act.exam
    if exam is None:
        return ""
    docs_html = "".join(exam_doc_html(d, act) for d in exam.documents)
    questions: list[str] = []
    for q in exam.questions:
        locked = lock_text(f"Attendu : {q.attendu}  Corrigé : {q.expected}")
        questions.append(
            f"""
      <div class="exam-q" data-locked-step="exam-{esc(q.id)}">
        <div class="step-head">
          <span class="step-n">{esc(q.id)}</span>
          <h3>Question {esc(q.id)}</h3>
          <span class="badge">{q.points} pt{'s' if q.points > 1 else ''}</span>
        </div>
        <p class="small kicker">{esc(q.skill)}</p>
        <div class="question">{esc(q.text)}</div>
        <div class="no-print" style="margin-top:.5rem">
          <button class="btn btn-warm btn-answer" type="button">Voir le corrigé</button>
        </div>
        <div class="answer" data-locked="{locked}"></div>
      </div>"""
        )
    sources = " · ".join(esc(s) for s in exam.sources)
    return f"""
  <section class="card">
    <p class="kicker">Préparation au brevet</p>
    <h2>Sujet type brevet</h2>
    <p>
      <span class="badge">{exam.duration} min</span>
      <span class="badge">{exam.points_total} points</span>
      <span class="badge">{len(exam.documents)} documents</span>
      <span class="badge">{len(exam.questions)} questions</span>
    </p>
    <p>{esc(exam.contexte)}</p>
    <div class="exam-rappel"><b>Consigne.</b> {esc(exam.rappel)}</div>
    {docs_html}
    <h3>Questions <span class="small">(difficulté croissante)</span></h3>
    {''.join(questions)}
    <p class="small"><i>Thème : {esc(exam.theme)}<br>Sources : {sources}</i></p>
  </section>"""


def render_activity(act: activities.Activity) -> str:
    figs = step_figures(act)
    exam_html = render_exam(act)
    city_list = list(act.default_cities)
    if city_list:
        kind, payload = fig_situation(city_list)
        situation_html = (
            '  <section class="card">\n    <h2>Où sont ces villes ?</h2>\n    '
            + figure_html(kind, payload, "Situation des villes étudiées.")
            + "\n  </section>"
        )
    else:
        situation_html = ""
    steps_html: list[str] = []
    for i, step in enumerate(act.steps, start=1):
        figs_html = "".join(figure_html(k, p, c) for k, p, c in figs[i - 1])
        if step.chart == "none" and not figs_html:
            figs_html = (
                '<div class="hint"><b>Étape sans graphique.</b> '
                "Travail au brouillon : écris ton classement avant de passer à l'étape 2.</div>"
            )
        steps_html.append(
            f"""
      <section class="card step" data-locked-step="{i}">
        <div class="step-head">
          <span class="step-n">{i}</span>
          <h2>{esc(step.title)}</h2>
          <span class="badge">{step.minutes} min</span>
          <span class="badge">{esc(CHART_LABELS.get(step.chart, step.chart))}</span>
        </div>
        <div class="question">{esc(step.instruction)}</div>
        <div class="hint"><b>Piste.</b> {esc(step.hint)}</div>
        {figs_html}
        <div class="no-print" style="margin-top:.5rem">
          <button class="btn btn-warm btn-answer" type="button">Voir le corrigé</button>
        </div>
        <div class="answer" data-locked="{lock_text(step.expected)}"></div>
      </section>"""
        )
    cities = ", ".join(act.default_cities)
    variables = ", ".join(
        datasets.VARIABLES[v].label if v in datasets.VARIABLES else v
        for v in act.variables
    )
    cities_badge = f'\n    <span class="badge">{esc(cities)}</span>' if cities else ""
    exam_badge = '\n    <span class="badge badge-ok">sujet type brevet</span>' if act.exam else ""
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(act.title)} — C3S² · fiche autonome</title>
<style>{CSS}</style>
</head>
<body>
<header class="topbar no-print">
  <span class="brand">C3S² · Climat en classe</span>
  <a href="index.html">← Toutes les fiches</a>
  <span style="margin-left:auto;font-size:.85rem">Fiche autonome — utilisable sans connexion après téléchargement</span>
</header>
<main class="wrap">
  <p class="kicker">Fiche pédagogique · {esc(act.subject)} · {esc(act.levels)} · {esc(act.duration)}</p>
  <h1>{esc(act.title)} <span class="badge badge-ok" id="lock-badge" style="display:none">corrigés visibles</span></h1>
  <p>
    <span class="badge">4 étapes</span>{cities_badge}
    <span class="badge">{esc(variables)}</span>
    {exam_badge}
  </p>
  <section class="card">
    <h2>Objectif</h2>
    <p>{esc(act.objective)}</p>
    <p>{esc(act.introduction)}</p>
    <h2>Ce que tu vas apprendre à faire</h2>
    <p>{" · ".join(esc(s) for s in act.skills)}</p>
  </section>
  {situation_html}
  <section class="card teacher no-print" id="lock-form">
    <b>Code enseignant</b>
    <div style="display:flex;gap:.5rem;align-items:center;margin-top:.4rem;flex-wrap:wrap">
      <input type="password" id="lock-code" placeholder="Code enseignant" autocomplete="off">
      <button class="btn" id="lock-btn" type="button">Afficher les corrigés</button>
      <button class="btn btn-forget" type="button" style="background:#64748b">Verrouiller</button>
    </div>
    <div id="lock-out" class="small" style="margin-top:.4rem"></div>
    <p class="small" style="color:var(--muted)">Sans code, la fiche imprimée ou projetée reste sans corrigé.</p>
  </section>
  {exam_html}
  {''.join(steps_html)}
  <section class="card">
    <h2>Données de l'activité</h2>
    <p>Villes : {esc(cities)} — variables : {esc(variables)} — source : ERA5 (moyennes 1991-2020 et série 1940-2024).
    Les valeurs affichées sont des moyennes de grille ERA5 (0,25°), pas des mesures de station.</p>
    <p class="no-print"><button class="btn" type="button" onclick="window.print()">Imprimer / exporter en PDF</button></p>
  </section>
  <footer>{esc(config.ERA5_ATTRIBUTION)}<br>Application pédagogique — fiche autonome générée à partir des données pré-calculées.</footer>
</main>
<script>{JS}</script>
</body>
</html>
"""


def render_index(acts: list[activities.Activity]) -> str:
    cards = []
    for act in acts:
        cards.append(
            f"""
      <section class="card">
        <p class="kicker">{esc(act.subject)} · {esc(act.levels)} · {esc(act.duration)}</p>
        <h2><a href="{act.key}.html">{esc(act.title)}</a></h2>
        <p>{esc(act.objective)}</p>
        <p><span class="badge">4 étapes</span> <span class="badge">{esc(', '.join(act.default_cities))}</span>{' <span class="badge badge-ok">sujet type brevet</span>' if act.exam else ''}</p>
      </section>"""
        )
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Fiches d'activités autonomes — C3S²</title>
<style>{CSS}</style>
</head>
<body>
<header class="topbar no-print">
  <span class="brand">C3S² · Climat en classe</span>
  <span style="margin-left:auto;font-size:.85rem">10 fiches autonomes + versions PDF</span>
</header>
<main class="wrap">
  <p class="kicker">Fiches pédagogiques autonomes</p>
  <h1>10 activités prêtes à projeter et à imprimer</h1>
  <p>Chaque fiche est un fichier unique (graphiques et cartes inclus) : elle fonctionne
  sans connexion une fois téléchargée. Les corrigés se déverrouillent avec le code enseignant.
  Les versions PDF (élève et corrigé) sont dans le dossier <code>pdf/</code>.</p>
  {''.join(cards)}
  <footer>{esc(config.ERA5_ATTRIBUTION)}</footer>
</main>
</body>
</html>
"""


def build(keys: list[str] | None = None) -> list[Path]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    situations = OUT_DIR.parent / "assets" / "situation"
    situations.mkdir(parents=True, exist_ok=True)
    acts = [a for a in activities.ACTIVITIES if not keys or a.key in keys]
    written: list[Path] = []
    for act in acts:
        print(f"  fiche {act.key} …", flush=True)
        path = OUT_DIR / f"{act.key}.html"
        path.write_text(render_activity(act), encoding="utf-8")
        written.append(path)
        # Carte de situation réutilisée par l'application web (sauf activités
        # sans villes, comme El Niño : l'image absente est masquée par l'app).
        try:
            _, png = fig_situation(list(act.default_cities))
            (situations / f"{act.key}.png").write_bytes(base64.b64decode(png))
        except KeyError:
            pass
    schemas = OUT_DIR.parent / "assets" / "schemas"
    if any(s.chart == "schema" for a in acts for s in a.steps):
        schemas.mkdir(parents=True, exist_ok=True)
        _, courant = fig_courants()
        (schemas / "courants_atlantique.png").write_bytes(base64.b64decode(courant))
    if not keys:
        index = OUT_DIR / "index.html"
        index.write_text(render_index(acts), encoding="utf-8")
        written.append(index)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Génère les fiches HTML autonomes.")
    parser.add_argument("--keys", default="", help="clés d'activités séparées par des virgules (défaut : tout)")
    args = parser.parse_args(argv)
    keys = [k.strip() for k in args.keys.split(",") if k.strip()]
    written = build(keys or None)
    total = sum(p.stat().st_size for p in written) / 1e6
    print(f"Terminé : {len(written)} fichier(s), {total:.1f} Mo dans {OUT_DIR}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
