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
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from c3s2 import activities, config, fields, store  # noqa: E402

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
        elif chart == "map" and n - 1 < len(maps):
            mid = maps[n - 1]
            if mid not in map_cache:
                map_cache[mid] = fig_map(mid)
            kind, payload = map_cache[mid]
            meta = fields.load_map(mid)
            figs.append((kind, payload, f"{meta.get('title', mid)} · {meta.get('source', '')}"))
        out.append(figs)
    return out


def render_activity(act: activities.Activity) -> str:
    figs = step_figures(act)
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
    variables = ", ".join(act.variables)
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
    <span class="badge">4 étapes</span>
    <span class="badge">{esc(cities)}</span>
    <span class="badge">{esc(variables)}</span>
  </p>
  <section class="card">
    <h2>Objectif</h2>
    <p>{esc(act.objective)}</p>
    <p>{esc(act.introduction)}</p>
    <h2>Ce que tu vas apprendre à faire</h2>
    <p>{" · ".join(esc(s) for s in act.skills)}</p>
  </section>
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
        <p><span class="badge">4 étapes</span> <span class="badge">{esc(', '.join(act.default_cities))}</span></p>
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
    acts = [a for a in activities.ACTIVITIES if not keys or a.key in keys]
    written: list[Path] = []
    for act in acts:
        print(f"  fiche {act.key} …", flush=True)
        path = OUT_DIR / f"{act.key}.html"
        path.write_text(render_activity(act), encoding="utf-8")
        written.append(path)
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
