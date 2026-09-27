/* ==========================================================================
   C3S² — rendus graphiques (Plotly)
   Chaque fonction prend les données JSON de l'API et écrit dans un conteneur.
   Les palettes sont nommées côté serveur (`palette_for`) : c'est ici qu'elles
   sont traduites en couleurs.
   ========================================================================== */

const Charts = (function () {
  "use strict";

  const MONTHS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."];
  const MONTHS_LONG = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
    "septembre", "octobre", "novembre", "décembre"];
  const SHORT_BY_LONG = {};
  MONTHS_LONG.forEach((m, i) => { SHORT_BY_LONG[m] = MONTHS[i]; });
  const CITY_COLORS = ["#e07a5f", "#4c7fd1", "#2a9d8f", "#7a5cc2", "#f2a541", "#d64545"];

  const SCALES = {
    temperature: [
      [0, "#31688e"], [0.25, "#35b779"], [0.5, "#f9d34a"], [0.75, "#f2863c"], [1, "#c2312b"]
    ],
    precipitation: [
      [0, "#f7fbff"], [0.2, "#c6dbef"], [0.45, "#6baed6"], [0.7, "#3182bd"], [1, "#08306b"]
    ],
    pressure: [
      [0, "#440154"], [0.3, "#3b528b"], [0.5, "#21918c"], [0.7, "#5ec962"], [1, "#fde725"]
    ],
    wind: [
      [0, "#f2f7fb"], [0.3, "#a8d8e8"], [0.55, "#4c9fc4"], [0.8, "#2a6f97"], [1, "#12345f"]
    ],
    viridis: [
      [0, "#440154"], [0.5, "#21918c"], [1, "#fde725"]
    ]
  };

  const config = {
    displaylogo: false,
    responsive: true,
    scrollZoom: true,
    modeBarButtonsToRemove: ["lasso2d", "select2d", "autoScale2d"],
    toImageButtonOptions: { format: "png", scale: 2, filename: "c3s2-graphique" }
  };

  let plotCount = 0;

  /* ---------------------------------------------------------------- Outils */

  function hasPlotly() {
    return typeof window.Plotly !== "undefined";
  }

  function container(target) {
    const el = typeof target === "string" ? document.querySelector(target) : target;
    return el;
  }

  function emptyState(target, message, actionHtml) {
    const el = container(target);
    if (!el) return;
    el.classList.add("chart-empty");
    el.removeAttribute("data-parsed");
    el.innerHTML =
      '<div><strong>' + esc(message) + "</strong>" +
      (actionHtml ? '<div class="small muted" style="margin-top:.5rem">' + actionHtml + "</div>" : "") +
      "</div>";
  }

  function esc(text) {
    return String(text == null ? "" : text).replace(/[&<>"']/g, (c) => (
      { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
    ));
  }

  function fmt(value, digits) {
    if (value === null || value === undefined || Number.isNaN(value)) return "—";
    return Number(value).toLocaleString("fr-FR", {
      minimumFractionDigits: digits === undefined ? 1 : digits,
      maximumFractionDigits: digits === undefined ? 1 : digits
    });
  }

  function colorFor(index) {
    return CITY_COLORS[index % CITY_COLORS.length];
  }

  function shortMonths(list) {
    return (list || []).map((m) => SHORT_BY_LONG[m] || m);
  }

  function baseLayout(extra) {
    const font = getComputedStyle(document.body).fontFamily;
    return Object.assign(
      {
        font: { family: font, size: 13, color: "#38506e" },
        paper_bgcolor: "#ffffff",
        plot_bgcolor: "#ffffff",
        margin: { l: 62, r: 22, t: 44, b: 54 },
        legend: { orientation: "h", y: 1.04, yanchor: "bottom", x: 0, font: { size: 12 } },
        hovermode: "x unified",
        hoverlabel: { bgcolor: "#0b2545", font: { color: "#fff" } },
        xaxis: { gridcolor: "#eef2f8", zeroline: false },
        yaxis: { gridcolor: "#eef2f8", zeroline: false },
        showlegend: true,
        autosize: true
      },
      extra || {}
    );
  }

  function draw(target, traces, layout) {
    const el = container(target);
    if (!el) return;
    if (!hasPlotly()) {
      emptyState(el, "Plotly n'est pas chargé.", "Vérifiez la connexion au fichier assets/vendor/plotly.min.js.");
      return;
    }
    el.classList.remove("chart-empty");
    el.innerHTML = "";
    el.removeAttribute("data-parsed");
    // Plotly.react ne redessine plus une fois que le contenu du conteneur a été
    // remplacé : on purge l'état interne puis on construit une figure neuve.
    try { window.Plotly.purge(el); } catch (e) { /* ignore */ }
    const job = window.Plotly.newPlot(el, traces, layout, config);
    if (job && typeof job.catch === "function") {
      job.catch((err) => console.error("Plotly:", err));
    }
    plotCount += 1;
    if (el.id) {
      el.setAttribute("data-parsed", String(plotCount));
    }
  }

  function cityTraces(payload, opts) {
    const cities = Object.keys(payload.series || {});
    const traces = [];
    cities.forEach((city, i) => {
      const serie = payload.series[city];
      traces.push({
        type: "scatter",
        mode: "lines",
        name: city,
        x: serie.dates,
        y: serie.values,
        line: { color: colorFor(i), width: 2.2, shape: "spline", smoothing: 0.35 },
        hovertemplate: "%{x}<br>" + city + " : %{y} " + (opts && opts.unit ? opts.unit : "") + "<extra></extra>"
      });
    });
    return traces;
  }

  /* ------------------------------------------------------------ 1. Séries */

  function line(target, payload, opts) {
    opts = opts || {};
    const meta = payload.meta || {};
    const traces = cityTraces(payload, { unit: meta.unit });
    if (!traces.length) {
      emptyState(target, "Aucune donnée à afficher.");
      return;
    }
    draw(target, traces, baseLayout({
      yaxis: { title: meta.unit, gridcolor: "#eef2f8", zeroline: false },
      xaxis: { title: "", gridcolor: "#eef2f8", type: "date", rangeslider: { visible: !!opts.rangeslider, height: 26 } },
      hovermode: "x unified"
    }));
  }

  /* -------------------------------------------------- 2. Normale mensuelle */

  function climato(target, payload, opts) {
    opts = opts || {};
    const meta = payload.meta || {};
    const stats = payload.stats || {};
    const traces = [];
    Object.keys(stats).forEach((city, i) => {
      const clim = stats[city].climatology;
      if (!clim) return;
      traces.push({
        type: "scatter",
        mode: "lines+markers",
        name: city,
        x: shortMonths(clim.months),
        y: clim.values,
        line: { color: colorFor(i), width: 3 },
        marker: { size: 7, color: colorFor(i) },
        hovertemplate: "%{x} · " + city + " : %{y} " + (clim.unit || meta.unit || "") + "<extra></extra>"
      });
    });
    if (!traces.length) {
      emptyState(target, "Normale mensuelle indisponible.");
      return;
    }
    draw(target, traces, baseLayout({
      xaxis: { categoryorder: "array", categoryarray: MONTHS, gridcolor: "#eef2f8" },
      yaxis: { title: meta.unit || "°C", gridcolor: "#eef2f8", zeroline: true, zerolinecolor: "#c6d0de" },
      hovermode: "x unified"
    }));
  }

  /* ------------------------------------------------- 3. Diagramme ombrothermique */

  function ombro(target, payload, opts) {
    opts = opts || {};
    const stats = payload.stats || {};
    const meta = payload.meta || {};
    const cities = Object.keys(stats);
    const traces = [];
    let aridityShown = false;

    cities.forEach((city, i) => {
      const clim = stats[city].climatology;
      const precip = (payload.precip && payload.precip.stats && payload.precip.stats[city]) || null;
      if (precip && precip.climatology) {
        traces.push({
          type: "bar",
          name: city + " — pluie",
          x: shortMonths(precip.climatology.months),
          y: precip.climatology.values,
          marker: { color: "rgba(76,127,209,.55)", line: { color: "#4c7fd1", width: 1 } },
          yaxis: "y2",
          hovertemplate: "%{x} · pluie " + city + " : %{y} mm<extra></extra>"
        });
      }
      if (clim) {
        traces.push({
          type: "scatter",
          mode: "lines+markers",
          name: city + " — température",
          x: shortMonths(clim.months),
          y: clim.values,
          line: { color: colorFor(i), width: 3 },
          marker: { size: 7, color: colorFor(i) },
          yaxis: "y",
          hovertemplate: "%{x} · " + city + " : %{y} °C<extra></extra>"
        });
        // Droite d'aridité : cumul = 2 × température (diagramme de Gregory).
        const T = clim.values.map((v) => (v === null ? null : 2 * Number(v)));
        traces.push({
          type: "scatter",
          mode: "lines",
          name: "aridité (2×T)",
          x: shortMonths(clim.months),
          y: T,
          line: { color: "#96600a", width: 1.6, dash: "dot" },
          yaxis: "y2",
          hoverinfo: "skip",
          showlegend: !aridityShown
        });
        aridityShown = true;
      }
    });

    if (!traces.length) {
      emptyState(target, "Données de température ou de pluie manquantes.");
      return;
    }

    draw(target, traces, baseLayout({
      barmode: "group",
      xaxis: { categoryorder: "array", categoryarray: MONTHS, gridcolor: "#eef2f8" },
      yaxis: {
        title: "Température (°C)", side: "left", gridcolor: "#eef2f8",
        position: 0.08, zeroline: true, zerolinecolor: "#c6d0de"
      },
      yaxis2: {
        title: "Précipitations (mm/mois)", side: "right", overlaying: "y",
        gridcolor: "transparent", position: 0.94, rangemode: "tozero"
      }
    }));
  }

  /* --------------------------------------------------------- 4. Moyennes annuelles */

  function annual(target, payload, opts) {
    opts = opts || {};
    const stats = payload.stats || {};
    const meta = payload.meta || {};
    const traces = [];
    Object.keys(stats).forEach((city, i) => {
      const a = stats[city].annual;
      if (!a) return;
      traces.push({
        type: "bar",
        name: city,
        x: a.years,
        y: a.values,
        marker: { color: colorFor(i), opacity: 0.78 },
        hovertemplate: "%{x} · " + city + " : %{y} " + (meta.unit || "") + "<extra></extra>"
      });
      const trend = stats[city].trend;
      if (trend && trend.valid && a.years.length > 2) {
        const x0 = a.years[0];
        const x1 = a.years[a.years.length - 1];
        traces.push({
          type: "scatter",
          mode: "lines",
          name: city + " — tendance",
          x: [x0, x1],
          y: [trend.slope * x0 + trend.intercept, trend.slope * x1 + trend.intercept],
          line: { color: colorFor(i), width: 2.4, dash: "dash" },
          hoverinfo: "skip"
        });
      }
    });
    if (!traces.length) {
      emptyState(target, "Moyennes annuelles indisponibles.");
      return;
    }
    draw(target, traces, baseLayout({
      barmode: "group",
      xaxis: { type: "linear", tickformat: "d", dtick: 10, gridcolor: "#eef2f8" },
      yaxis: { title: meta.unit || "", gridcolor: "#eef2f8", zeroline: true, zerolinecolor: "#c6d0de" }
    }));
  }

  /* ------------------------------------------------------------ 5. Anomalies */

  function anomalies(target, payload, opts) {
    opts = opts || {};
    const stats = payload.stats || {};
    const meta = payload.meta || {};
    const city = opts.city && stats[opts.city] ? opts.city : Object.keys(stats)[0];
    const data = city ? stats[city].anomalies : null;
    if (!data || !data.years.length) {
      emptyState(target, "Anomalies indisponibles sur cette période.");
      return;
    }
    const colors = data.values.map((v) => (v >= 0 ? "#d64545" : "#4c7fd1"));
    draw(target, [{
      type: "bar",
      name: "anomalie",
      x: data.years,
      y: data.values,
      marker: { color: colors },
      hovertemplate: "%{x} · " + (city || "") + " : %{y:+.1f} " + (data.unit || meta.unit || "") + "<extra></extra>"
    }], baseLayout({
      xaxis: { type: "linear", tickformat: "d", dtick: 10, gridcolor: "#eef2f8" },
      yaxis: {
        title: "écart (" + (data.unit || meta.unit || "") + ")",
        gridcolor: "#eef2f8", zeroline: true, zerolinecolor: "#0b2545", zerolinewidth: 1.5
      },
      showlegend: false
    }));
  }

  /* ------------------------------------------------------- 6. Avant / après */

  function compareStats(payload, periods, city) {
    const serie = payload.series[city];
    const months = new Array(12).fill(null);
    const sumA = new Array(12).fill(0);
    const cntA = new Array(12).fill(0);
    const sumB = new Array(12).fill(0);
    const cntB = new Array(12).fill(0);

    serie.dates.forEach((date, i) => {
      const v = serie.values[i];
      if (v === null || v === undefined) return;
      const year = Number(date.slice(0, 4));
      const m = Number(date.slice(5, 7)) - 1;
      months[m] = m;
      if (year >= periods[0][0] && year <= periods[0][1]) { sumA[m] += v; cntA[m] += 1; }
      if (year >= periods[1][0] && year <= periods[1][1]) { sumB[m] += v; cntB[m] += 1; }
    });

    const mean = (sum, cnt) => cnt > 0 ? sum / cnt : null;
    const a = months.map((_, i) => mean(sumA[i], cntA[i]));
    const b = months.map((_, i) => mean(sumB[i], cntB[i]));
    const delta = months.map((_, i) => (a[i] === null || b[i] === null ? null : b[i] - a[i]));
    const meanOf = (arr) => {
      const vals = arr.filter((v) => v !== null);
      return vals.length ? vals.reduce((s, v) => s + v, 0) / vals.length : null;
    };
    return { a, b, delta, mA: meanOf(a), mB: meanOf(b) };
  }

  function compare(target, payload, opts) {
    opts = opts || {};
    const meta = payload.meta || {};
    const periods = opts.periods || [[1941, 1970], [1991, 2020]];
    const city = opts.city && payload.series[opts.city] ? opts.city : Object.keys(payload.series)[0];
    if (!city) {
      emptyState(target, "Aucune ville à comparer.");
      return;
    }
    const s = compareStats(payload, periods, city);

    draw(target, [
      {
        type: "bar", name: periods[0][0] + "-" + periods[0][1],
        x: MONTHS, y: s.a, marker: { color: "rgba(76,127,209,.75)" },
        hovertemplate: "%{x} · " + periods[0][0] + "-" + periods[0][1] + " : %{y} " + meta.unit + "<extra></extra>"
      },
      {
        type: "bar", name: periods[1][0] + "-" + periods[1][1],
        x: MONTHS, y: s.b, marker: { color: "rgba(224,122,95,.85)" },
        hovertemplate: "%{x} · " + periods[1][0] + "-" + periods[1][1] + " : %{y} " + meta.unit + "<extra></extra>"
      },
      {
        type: "scatter", mode: "lines+markers", name: "écart",
        x: MONTHS, y: s.delta, yaxis: "y2",
        line: { color: "#0b2545", width: 2.2, dash: "dot" },
        marker: { size: 7, color: "#0b2545" },
        hovertemplate: "%{x} · écart %{y:+.1f} " + meta.unit + "<extra></extra>"
      }
    ], baseLayout({
      barmode: "group",
      xaxis: { categoryorder: "array", categoryarray: MONTHS, gridcolor: "#eef2f8" },
      yaxis: { title: meta.unit || "", gridcolor: "#eef2f8", rangemode: "tozero" },
      yaxis2: { title: "écart", side: "right", overlaying: "y", gridcolor: "transparent" }
    }));
  }

  /* --------------------------------------------------------- 7. Jours de chaleur */

  function heat(target, payload, opts) {
    opts = opts || {};
    const cities = Object.keys(payload.cities || {});
    if (!cities.length) {
      emptyState(target, "Aucune donnée journalière.", "Lancez une requête vers le CDS depuis la page de l'activité.");
      return;
    }
    const city = opts.city && payload.cities[opts.city] ? opts.city : cities[0];
    const data = payload.cities[city];
    const meta = payload.meta || {};

    const traces = [
      {
        type: "scatter", mode: "lines", name: "maximum diurne",
        x: data.dates, y: data.tmax,
        line: { color: "#e07a5f", width: 1 },
        hovertemplate: "%{x}<br>max %{y} °C<extra></extra>"
      },
      {
        type: "scatter", mode: "lines", name: "minimum nocturne",
        x: data.dates, y: data.tmin,
        line: { color: "#4c7fd1", width: 1 },
        hovertemplate: "%{x}<br>min %{y} °C<extra></extra>"
      }
    ];

    const tmaxT = meta.tmax_threshold;
    const tminT = meta.tmin_threshold;
    const lastX = data.dates[data.dates.length - 1];
    const firstX = data.dates[0];
    if (tmaxT !== undefined) {
      traces.push({
        type: "scatter", mode: "lines", name: "seuil max " + tmaxT + " °C",
        x: [firstX, lastX], y: [tmaxT, tmaxT],
        line: { color: "#d64545", width: 2, dash: "dash" }, hoverinfo: "skip"
      });
    }
    if (tminT !== undefined) {
      traces.push({
        type: "scatter", mode: "lines", name: "seuil min " + tminT + " °C",
        x: [firstX, lastX], y: [tminT, tminT],
        line: { color: "#7a5cc2", width: 2, dash: "dash" }, hoverinfo: "skip"
      });
    }
    traces.push({
      type: "bar", name: "jours ≥ seuil (les deux)",
      x: (data.counts.both.years || []).map(String),
      y: data.counts.both.values,
      yaxis: "y2",
      marker: { color: "rgba(11,37,69,.55)" },
      hovertemplate: "%{x} : %{y} jours<extra></extra>"
    });

    draw(target, traces, baseLayout({
      xaxis: { type: "date", gridcolor: "#eef2f8", rangeslider: { visible: true, height: 26 } },
      yaxis: { title: "°C", gridcolor: "#eef2f8", side: "left", position: 0.07 },
      yaxis2: {
        title: "jours/an", side: "right", overlaying: "y",
        gridcolor: "transparent", position: 0.95, rangemode: "tozero", dtick: 5
      }
    }));
  }

  function heatCounts(target, payload, opts) {
    const cities = Object.keys(payload.cities || {});
    if (!cities.length) { emptyState(target, "Aucun comptage disponible."); return; }
    const city = opts.city && payload.cities[opts.city] ? opts.city : cities[0];
    const counts = payload.cities[city].counts;
    const meta = payload.meta || {};

    draw(target, [
      { type: "bar", name: "max ≥ " + meta.tmax_threshold + " °C", x: counts.tmax_above.years, y: counts.tmax_above.values, marker: { color: "#e07a5f" } },
      { type: "bar", name: "min ≥ " + meta.tmin_threshold + " °C", x: counts.tmin_above.years, y: counts.tmin_above.values, marker: { color: "#4c7fd1" } },
      { type: "bar", name: "les deux", x: counts.both.years, y: counts.both.values, marker: { color: "#0b2545" } }
    ], baseLayout({
      barmode: "group",
      xaxis: { type: "linear", tickformat: "d", dtick: 2, gridcolor: "#eef2f8" },
      yaxis: { title: "jours", gridcolor: "#eef2f8", rangemode: "tozero" }
    }));
  }

  /* ------------------------------------------------------------------ 8. Cartes */

  let geoCache = null;

  function loadGeo() {
    if (geoCache) return geoCache;
    geoCache = fetch("assets/geo/ne_110m_coastline.geojson")
      .then((r) => (r.ok ? r.json() : null))
      .then((json) => (json ? json : null))
      .catch(() => null);
    return geoCache;
  }

  function normalizeGrid(payload) {
    // ERA5 livre la latitude du nord au sud : on remonte pour un rendu standard.
    const lat = payload.lat.slice();
    const z = payload.z.slice();
    const u = payload.u ? payload.u.slice() : null;
    const v = payload.v ? payload.v.slice() : null;
    if (lat.length > 1 && lat[0] > lat[lat.length - 1]) {
      lat.reverse();
      z.reverse();
      if (u) u.reverse();
      if (v) v.reverse();
    }
    return { lat, z, u, v };
  }

  // Flèches de vent : segments dessinés comme des coordonnées de données
  // (les annotations Plotly mélangent unités pixels / papier / données).
  function arrowTraces(payload, grid) {
    if (!grid.u || !grid.v) return [];
    const nLat = grid.lat.length;
    const nLon = payload.lon.length;
    const cells = nLat * nLon;
    const step = Math.max(1, Math.ceil(Math.sqrt(cells / 320)));
    let maxSpeed = 0.0001;
    grid.z.forEach((row) => row.forEach((val) => { if (val > maxSpeed) maxSpeed = val; }));
    const cellLat = nLat > 1 ? Math.abs(grid.lat[1] - grid.lat[0]) : 0.5;
    const xs = [];
    const ys = [];

    const push = (x0, y0, x1, y1) => {
      xs.push(x0, x1, null);
      ys.push(y0, y1, null);
    };

    for (let i = 0; i < nLat; i += step) {
      for (let j = 0; j < nLon; j += step) {
        const u = grid.u[i][j];
        const v = grid.v[i][j];
        if (u === null || v === null || Number.isNaN(u)) continue;
        const speed = Math.hypot(u, v);
        if (speed < 0.5) continue;
        // Longueur en degrés, proportionnelle à l'intensité, calée sur la maille.
        const len = cellLat * (1.0 + 2.0 * Math.min(1, speed / maxSpeed));
        const ux = u / speed;
        const uy = v / speed;
        const cx = payload.lon[j];
        const cy = grid.lat[i];
        const hx = cx + ux * len * 0.5;
        const hy = cy + uy * len * 0.5;
        const tx = cx - ux * len * 0.5;
        const ty = cy - uy * len * 0.5;
        push(tx, ty, hx, hy);
        // Pointe en « V » derrière la tête de flèche.
        const barb = len * 0.32;
        const px = -uy;
        const py = ux;
        push(hx - ux * barb + px * barb * 0.55, hy - uy * barb + py * barb * 0.55, hx, hy);
        push(hx - ux * barb - px * barb * 0.55, hy - uy * barb - py * barb * 0.55, hx, hy);
      }
    }
    if (!xs.length) return [];
    return [{
      type: "scatter",
      mode: "lines",
      x: xs,
      y: ys,
      line: { color: "rgba(11,37,69,.85)", width: 1.2 },
      hoverinfo: "skip",
      showlegend: false
    }];
  }

  function map(target, payload, opts) {
    opts = opts || {};
    const grid = normalizeGrid(payload);
    const palette = SCALES[payload.palette] || SCALES.viridis;
    const traces = [{
      type: "heatmap",
      x: payload.lon,
      y: grid.lat,
      z: grid.z,
      colorscale: palette,
      zsmooth: false,
      colorbar: {
        title: { text: payload.unit, side: "right", font: { size: 12 } },
        thickness: 16, len: 0.72, outlinewidth: 0, ticksuffix: ""
      },
      hovertemplate: "%{y:.2f}° / %{x:.2f}°<br>" + (payload.variable_label || "") +
                     " : %{z} " + (payload.unit || "") + "<extra></extra>"
    }];

    const area = payload.area ||
      [grid.lat[grid.lat.length - 1], payload.lon[0], grid.lat[0], payload.lon[payload.lon.length - 1]];
    const [north, west, south, east] = area;

    loadGeo().then((geo) => {
      const all = traces
        .concat(geo ? coastlineTracesNow(payload, geo) : [])
        .concat(arrowTraces(payload, grid));
      const layout = baseLayout({
        xaxis: {
          title: "longitude", gridcolor: "transparent", zeroline: false,
          range: [west, east], constrain: "domain"
        },
        yaxis: {
          title: "latitude", gridcolor: "transparent", zeroline: false,
          range: [south, north], scaleanchor: "x", scaleratio: 1
        },
        showlegend: false,
        hovermode: "closest",
        margin: { l: 52, r: 74, t: 20, b: 44 }
      });
      draw(target, all, layout);
    });
  }

  function coastlineTracesNow(payload, geo) {
    const xs = [];
    const ys = [];
    const area = payload.area || [-90, -180, 90, 180];
    const [north, west, south, east] = area;
    geo.features.forEach((feature) => {
      const geom = feature.geometry;
      if (!geom) return;
      const lines = geom.type === "LineString" ? [geom.coordinates]
        : geom.type === "MultiLineString" ? geom.coordinates : [];
      lines.forEach((coords) => {
        let open = false;
        coords.forEach((pt) => {
          const inside = pt[0] >= west && pt[0] <= east && pt[1] >= south && pt[1] <= north;
          if (!inside) {
            open = false;
            return;
          }
          if (!open) {
            xs.push(null);
            ys.push(null);
            open = true;
          }
          xs.push(pt[0]);
          ys.push(pt[1]);
        });
      });
    });
    if (xs.length < 4) return [];
    return [{
      type: "scatter", mode: "lines",
      x: xs, y: ys,
      line: { color: "rgba(11,37,69,.6)", width: 0.9 },
      hoverinfo: "skip", showlegend: false
    }];
  }

  /* ------------------------------------------------------- Légendes HTML */

  const notes = {
    // Cumuls annuels de pluie (diagramme ombrothermique).
    ombro(stats, precip) {
      const cities = Object.keys(stats || {});
      return cities.map((city, i) => {
        const p = precip && precip.stats && precip.stats[city];
        const total = p && p.summary ? p.summary.annual_total : null;
        if (total === null || total === undefined) return "";
        return '<span style="color:' + colorFor(i) + '">' + esc(city) + " : " +
          fmt(total, 0) + " mm/an</span>";
      }).join("");
    },

    // Moyennes des deux périodes comparées (avant / après).
    compare(payload, periods, city) {
      if (!city || !payload.series || !payload.series[city]) return "";
      const s = compareStats(payload, periods, city);
      if (s.mA === null || s.mB === null) return "";
      return '<span><strong>' + esc(city) + "</strong> : " + fmt(s.mA, 1) + " → " +
        fmt(s.mB, 1) + " " + esc((payload.meta || {}).unit || "") + " (" + fmt(s.mB - s.mA, 1) + ")</span>";
    },

    // Normale de référence utilisée pour les anomalies.
    anomalies(payload, city) {
      const data = payload.stats && payload.stats[city] && payload.stats[city].anomalies;
      if (!data) return "";
      return "<span>normale " + esc(data.reference || "") + " : " + fmt(data.baseline, 1) + " " +
        esc(data.unit || "") + "</span>";
    },

    // Origine et domaine d'une carte (sous le graphique).
    map(payload) {
      return "<span>" + esc(payload.period || "") + "</span>" +
        "<span>domaine : " + esc(payload.domain || "") + "</span>" +
        "<span>source : " + esc(payload.source || "") + "</span>";
    }
  };

  /* ------------------------------------------------------------- Vignettes */

  function thumb(target, payload) {
    map(target, payload, { thumb: true });
  }

  /* ---------------------------------------------------------------- Export */

  function resizeAll() {
    if (!hasPlotly()) return;
    document.querySelectorAll(".chart, .map-frame").forEach((el) => {
      if (el.getAttribute("data-parsed")) {
        try { window.Plotly.Plots.resize(el); } catch (e) { /* ignore */ }
      }
    });
  }

  window.addEventListener("resize", debounce(resizeAll, 250));

  function debounce(fn, wait) {
    let t = null;
    return function () {
      clearTimeout(t);
      t = setTimeout(fn, wait);
    };
  }

  return {
    MONTHS,
    CITY_COLORS,
    SCALES,
    hasPlotly,
    emptyState,
    esc,
    fmt,
    colorFor,
    shortMonths,
    notes,
    draw,
    line,
    climato,
    ombro,
    annual,
    anomalies,
    compare,
    heat,
    heatCounts,
    map,
    thumb,
    resizeAll,
    loadGeo
  };
})();
