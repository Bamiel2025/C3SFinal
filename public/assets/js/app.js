/* ==========================================================================
   C3S² — application (routeur, pages, accès aux données)
   Aucun framework : un routeur par hash, des gabarits littéraux et Plotly.
   ========================================================================== */

(function () {
  "use strict";

  const esc = Charts.esc;
  const fmt = Charts.fmt;

  /* ------------------------------------------------------------------ État */

  const state = {
    config: null,
    places: null,
    activities: null,
    unlocked: false,
    teacherCode: sessionStorage.getItem("c3s2_teacher_code") || "",
    explorer: {
      variable: "2m_temperature",
      cities: ["Brest", "Strasbourg"],
      start: 1991,
      end: 2020,
      source: "auto",
      view: "climato",
      periodA: [1941, 1970],
      periodB: [1991, 2020],
      payload: null,
      precip: null,
      loading: false
    },
    maps: {
      selected: null,
      payload: null,
      live: false,
      loading: false,
      form: { month: 1, domain: "Europe", variable: "2m_temperature" }
    },
    heat: { payload: null, loading: false, start: 2000, end: 2024, tmax: 35, tmin: 20 }
  };

  /* ------------------------------------------------------------------- API */

  async function api(path, options) {
    const opts = Object.assign({ headers: {} }, options || {});
    if (opts.body && typeof opts.body !== "string") {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(opts.body);
    }
    let res;
    try {
      res = await fetch(path, opts);
    } catch (err) {
      throw new Error("Serveur injoignable (" + err.message + ").");
    }
    let data = null;
    try { data = await res.json(); } catch (e) { data = null; }
    if (!res.ok) {
      const message = (data && (data.error || data.detail)) || ("Erreur HTTP " + res.status);
      throw new Error(typeof message === "string" ? message : JSON.stringify(message));
    }
    return data;
  }

  function queryString(params) {
    const q = new URLSearchParams();
    Object.keys(params).forEach((k) => {
      const v = params[k];
      if (v !== undefined && v !== null && v !== "") q.set(k, v);
    });
    const s = q.toString();
    return s ? "?" + s : "";
  }

  let toastTimer = null;
  function toast(message, kind) {
    const el = document.getElementById("toast");
    if (!el) return;
    el.textContent = message;
    el.className = "toast show" + (kind ? " " + kind : "");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { el.className = "toast"; }, kind === "err" ? 6000 : 3500);
  }

  /* -------------------------------------------------------------- Utilitaires */

  function el(id) { return document.getElementById(id); }

  function html(target, markup) {
    const node = typeof target === "string" ? el(target) : target;
    if (node) node.innerHTML = markup;
    return node;
  }

  function yearsOptions(from, to, selected) {
    let out = "";
    for (let y = from; y <= to; y += 1) {
      out += '<option value="' + y + '"' + (y === selected ? " selected" : "") + ">" + y + "</option>";
    }
    return out;
  }

  function coverage() {
    const c = state.config;
    return c && c.years ? c.years : [1940, 2024];
  }

  function badgeFor(payload) {
    if (!payload || !payload.meta) return "";
    const meta = payload.meta;
    if (meta.simulated) return '<span class="badge badge-sim">Données simulées</span>';
    if (meta.source === "cds") return '<span class="badge badge-cds">CDS en direct</span>';
    if (meta.source === "mixed") return '<span class="badge badge-warn">Sources mixtes</span>';
    if (meta.source === "precomputed") return '<span class="badge badge-ok">Pré-calculé</span>';
    return "";
  }

  /* --------------------------------------------------------------- Routeur */

  const routes = [
    { pattern: /^\/?$/, render: renderHome, route: "/" },
    { pattern: /^\/explorateur$/, render: renderExplorer, route: "/explorateur" },
    { pattern: /^\/activites$/, render: renderActivities, route: "/activites" },
    { pattern: /^\/activites\/([\w-]+)$/, render: renderActivity, route: "/activites" },
    { pattern: /^\/cartes$/, render: renderMaps, route: "/cartes" },
    { pattern: /^\/aide$/, render: renderAide, route: "/aide" }
  ];

  function currentPath() {
    const hash = window.location.hash.replace(/^#/, "");
    return hash || "/";
  }

  function navigate(path) {
    window.location.hash = "#" + path;
  }

  async function router() {
    const path = currentPath();
    let matched = null;
    let params = [];
    for (const r of routes) {
      const m = path.match(r.pattern);
      if (m) { matched = r; params = m.slice(1); break; }
    }
    document.querySelectorAll(".nav a").forEach((a) => {
      a.classList.toggle("active", matched && a.getAttribute("data-route") === matched.route);
    });
    document.getElementById("nav").classList.remove("open");
    document.getElementById("nav-toggle").setAttribute("aria-expanded", "false");

    const main = el("main");
    if (!matched) {
      html(main, notFound(path));
      return;
    }
    try {
      await ensureData();
      if (matched.route === "/aide" && !(await teacherVerified())) {
        renderAideLock(main);
        return;
      }
      await matched.render(main, params);
    } catch (err) {
      console.error(err);
      html(main, '<div class="card"><div class="callout callout-warn"><h4>Impossible de charger la page</h4><p>' +
        esc(err.message) + "</p></div></div>");
    }
    window.scrollTo({ top: 0, behavior: "instant" in window ? "instant" : "auto" });
  }

  function notFound(path) {
    return '<div class="card"><h2>Page introuvable</h2><p class="muted">Aucune route pour <code>' +
      esc(path) + '</code>.</p><p><a class="btn" href="#/">Retour à l\'accueil</a></p></div>';
  }

  async function teacherVerified() {
    const code = (state.teacherCode || "").trim();
    if (!code) return false;
    try {
      const out = await api("api/teacher/unlock", { method: "POST", body: { code } });
      return !!out.ok;
    } catch (e) { return false; }
  }

  function renderAideLock(main) {
    html(main, `
      <div class="section-head">
        <p class="eyebrow">Espace professeur</p>
        <h1>Aide &amp; CDS : accès réservé</h1>
        <p>Cette page (connexion au CDS, fichiers de données, dépannage) est
        destinée au professeur. Saisis le code enseignant pour l'ouvrir.</p>
      </div>
      ${teacherBoxMarkup()}
      <p style="margin-top:1rem"><a class="btn btn-ghost" href="#/">Retour à l'accueil</a></p>
    `);
    bindTeacherBox(main, () => router());
  }

  async function ensureData() {
    if (!state.config) state.config = await api("api/config");
    if (!state.places) state.places = await api("api/places");
    const v = document.getElementById("app-version");
    if (v) v.textContent = state.config && state.config.version ? " · version " + state.config.version : "";
  }

  /* ======================================================================== */
  /* Page d'accueil                                                           */
  /* ======================================================================== */

  async function renderHome(main) {
    if (!state.activities) {
      try { await fetchActivities(); } catch (e) { state.activities = { activities: [] }; }
    }
    const cfg = state.config;
    const places = state.places;
    const cards = (places.maps || []).length;

    const activities = state.activities || { activities: [] };
    const actList = activities.activities || [];

    main.innerHTML = `
      <section class="hero">
        <p class="eyebrow" style="color:#f2a541">Laboratoire de climatologie</p>
        <h1>Le climat se lit dans les données</h1>
        <p class="lead">
          Explore ${places.cities.length} villes et ${cards} cartes construites à partir de
          vraies mesures du climat (ERA5, Copernicus), ou suis une activité guidée :
          une question à la fois, avec des températures et des pluies réelles.
        </p>
        <div class="hero-actions">
          <a class="btn btn-warm" href="#/explorateur">Ouvrir l'explorateur</a>
          <a class="btn btn-ghost" style="color:#fff;border-color:rgba(255,255,255,.4)" href="#/activites">Voir les activités</a>
          <a class="btn btn-ghost" style="color:#fff;border-color:rgba(255,255,255,.4)" href="#/cartes">Explorer les cartes</a>
        </div>
        <div class="hero-meta">
          <span>Référence climatique ${cfg.reference_period[0]}–${cfg.reference_period[1]} (OMM)</span>
          <span>Couverture ${cfg.years[0]}–${cfg.years[1]}</span>
          <span>Résolution ERA5 : 0,25° (≈ 25 km)</span>
        </div>
      </section>

      <div class="stat-strip" style="margin-top:1.2rem">
        <div class="stat accent-temp">
          <dt>Villes</dt>
          <dd>${places.cities.length}<small>dont ${places.domains.length} domaines</small></dd>
        </div>
        <div class="stat accent-rain">
          <dt>Activités</dt>
          <dd>${actList.length}<small>1 question / étape</small></dd>
        </div>
        <div class="stat accent-press">
          <dt>Cartes</dt>
          <dd>${cards}<small>températures, pluies, vent</small></dd>
        </div>
      </div>

      <div class="card" style="margin-top:1.4rem">
        <p class="small">${esc(cfg.attribution)}</p>
        <p class="small muted">Licence des données : ${esc(cfg.licence)}</p>
      </div>
    `;

  }

  function reportMarkup(report) {
    const cls = report.ok ? "callout-ok" : "callout-warn";
    return '<div class="callout ' + cls + '"><h4>' + esc(report.title) + "</h4><p>" +
      esc(report.detail) + "</p>" +
      (report.hint ? '<p class="small muted">' + esc(report.hint) + "</p>" : "") +
      (report.latency_s !== null && report.latency_s !== undefined
        ? '<p class="small muted">Latence : ' + report.latency_s + " s</p>" : "") +
      "</div>";
  }

  /* ======================================================================== */
  /* Explorateur                                                               */
  /* ======================================================================== */

  const VIEWS = [
    { id: "climato", label: "Normale mensuelle" },
    { id: "line", label: "Séries mensuelles" },
    { id: "ombro", label: "Ombrothermie" },
    { id: "annual", label: "Moyennes annuelles" },
    { id: "anomalies", label: "Anomalies" },
    { id: "compare", label: "Avant / après" }
  ];

  async function renderExplorer(main) {
    const ex = state.explorer;
    const places = state.places;
    const cov = coverage();

    main.innerHTML = `
      <div class="section-head">
        <p class="eyebrow">Explorateur</p>
        <h1>Observer l'évolution du climat</h1>
        <p>Choisissez une variable, des villes et une période : les indicateurs,
        la narration climatique et les graphiques sont recalculés à chaque changement.</p>
      </div>

      <div class="layout-side">
        <aside class="card" id="explorer-controls">
          <div class="field">
            <span class="field-label">Variable</span>
            <div class="seg" id="var-seg">
              ${places.variables.map(v => `
                <button data-var="${v.slug}" class="${v.slug === ex.variable ? "active" : ""}">${esc(shortLabel(v))}</button>
              `).join("")}
            </div>
            <span class="hint" id="var-hint"></span>
          </div>

          <div class="field">
            <span class="field-label">Période</span>
            <div class="row">
              <div><select id="start-year">${yearsOptions(cov[0], cov[1], ex.start)}</select></div>
              <div><select id="end-year">${yearsOptions(cov[0], cov[1], ex.end)}</select></div>
            </div>
            <span class="hint">Couverture complète des fichiers : ${cov[0]}–${cov[1]}.</span>
          </div>

          <div class="field">
            <span class="field-label">Villes <span class="muted">(${ex.cities.length}/6)</span></span>
            <div class="chips" id="city-chips">${cityChips()}</div>
            <span class="hint">Maximum six villes par graphique.</span>
          </div>

          <div class="field">
            <span class="field-label">Source des données</span>
            <select id="source-select">
              <option value="auto"${ex.source === "auto" ? " selected" : ""}>Automatique (pré-calculé puis CDS)</option>
              <option value="precomputed"${ex.source === "precomputed" ? " selected" : ""}>Fichiers pré-calculés uniquement</option>
              <option value="cds"${ex.source === "cds" ? " selected" : ""}>Requête CDS en direct (20–90 s)</option>
              <option value="simulated"${ex.source === "simulated" ? " selected" : ""}>Simulation (sans clé)</option>
            </select>
            <span class="hint" id="source-hint"></span>
          </div>

          <div class="field">
            <span class="field-label">Affichage</span>
            <div class="seg" id="view-seg">
              ${VIEWS.map(v => `<button data-view="${v.id}" class="${v.id === ex.view ? "active" : ""}">${v.label}</button>`).join("")}
            </div>
          </div>

          <div id="compare-controls" style="display:${ex.view === "compare" ? "block" : "none"}">
            <div class="field">
              <span class="field-label">Période A</span>
              <div class="row">
                <div><select id="pa0">${yearsOptions(cov[0], cov[1], ex.periodA[0])}</select></div>
                <div><select id="pa1">${yearsOptions(cov[0], cov[1], ex.periodA[1])}</select></div>
              </div>
            </div>
            <div class="field">
              <span class="field-label">Période B</span>
              <div class="row">
                <div><select id="pb0">${yearsOptions(cov[0], cov[1], ex.periodB[0])}</select></div>
                <div><select id="pb1">${yearsOptions(cov[0], cov[1], ex.periodB[1])}</select></div>
              </div>
            </div>
            <span class="hint">Les deux périodes sont chargées automatiquement,
            au besoin sur toute la couverture ${cov[0]}–${cov[1]}.</span>
          </div>

          <div class="stack">
            <button class="btn btn-block" id="btn-refresh">Actualiser</button>
            <button class="btn btn-ghost btn-block" id="btn-cds">Requêter le CDS maintenant</button>
            <button class="btn btn-ghost btn-block" id="btn-full">Période complète ${cov[0]}–${cov[1]}</button>
          </div>
        </aside>

        <section>
          <div class="card">
            <div class="panel-title">
              <div>
                <span class="badge" id="src-badge">—</span>
                <span class="small muted" id="src-detail"></span>
              </div>
              <div class="small muted" id="elapsed"></div>
            </div>
            <h3 class="chart-heading" id="chart-heading"></h3>
            <div id="chart-explorer" class="chart chart-lg"><div class="chart-empty">Chargement…</div></div>
            <div class="chart-legend" id="explorer-legend"></div>
            <div class="narrative" id="narrative">Sélectionnez des villes pour afficher l'analyse.</div>
          </div>

          <div class="card">
            <div class="card-title"><h3>Indicateurs</h3><span class="small muted" id="period-label"></span></div>
            <div class="indices" id="indices"></div>
          </div>

          <div class="card">
            <div class="card-title"><h3>Valeurs mensuelles</h3><button class="btn btn-sm btn-ghost" id="btn-table">Afficher le tableau</button></div>
            <div id="table-host" style="display:none"></div>
          </div>
        </section>
      </div>
    `;

    bindExplorer();
    updateVarHint();
    await loadExplorerData({ silent: true });
  }

  function shortLabel(v) {
    return v.label.replace("Température de l'air à 2 m", "Température")
      .replace("Précipitations totales", "Précipitations")
      .replace("Pression au niveau de la mer", "Pression");
  }

  function cityChips() {
    const ex = state.explorer;
    const groups = [
      { name: "France", cities: state.places.cities.filter(c => c.country === "France") },
      { name: "Monde", cities: state.places.cities.filter(c => c.country !== "France") }
    ];
    return groups.map(g => `
      <div style="width:100%" class="small muted">${g.name}</div>
      ${g.cities.map(c => {
        const on = ex.cities.includes(c.name);
        return `<button type="button" class="chip ${on ? "on" : ""}" data-city="${esc(c.name)}"
          aria-pressed="${on}" title="${esc(c.region || "")} — ${c.lat.toFixed(2)}°${c.lat >= 0 ? "N" : "S"}">${esc(c.name)}</button>`;
      }).join("")}
    `).join("");
  }

  function updateVarHint() {
    const v = state.places.variables.find(x => x.slug === state.explorer.variable);
    const hint = el("var-hint");
    if (hint && v) hint.textContent = v.description || v.lesson;
    const src = el("source-hint");
    if (src) {
      src.textContent = state.explorer.source === "cds"
        ? "Chaque actualisation déclenche une vraie requête ERA5."
        : state.explorer.source === "simulated"
          ? "Valeurs synthétiques : aucun rapport avec les données réelles."
          : "Les villes déjà préparées s'affichent instantanément.";
    }
  }

  function bindExplorer() {
    const ex = state.explorer;

    el("var-seg").addEventListener("click", (e) => {
      const b = e.target.closest("button[data-var]");
      if (!b) return;
      ex.variable = b.getAttribute("data-var");
      if (ex.variable !== "2m_temperature" && ex.view === "ombro") ex.view = "climato";
      syncExplorerControls();
      loadExplorerData();
    });

    el("view-seg").addEventListener("click", (e) => {
      const b = e.target.closest("button[data-view]");
      if (!b) return;
      ex.view = b.getAttribute("data-view");
      syncExplorerControls();
      loadExplorerData();
    });

    el("city-chips").addEventListener("click", (e) => {
      const b = e.target.closest("button[data-city]");
      if (!b) return;
      const name = b.getAttribute("data-city");
      const i = ex.cities.indexOf(name);
      if (i >= 0) ex.cities.splice(i, 1);
      else {
        if (ex.cities.length >= 6) { toast("Six villes maximum.", "err"); return; }
        ex.cities.push(name);
      }
      html("city-chips", cityChips());
      loadExplorerData();
    });

    ["start-year", "end-year"].forEach(id => {
      el(id).addEventListener("change", () => {
        const s = Number(el("start-year").value);
        const e2 = Number(el("end-year").value);
        if (s > e2) { toast("La début est après la fin.", "err"); return; }
        ex.start = s; ex.end = e2;
        loadExplorerData();
      });
    });

    el("source-select").addEventListener("change", () => {
      ex.source = el("source-select").value;
      updateVarHint();
      loadExplorerData();
    });

    ["pa0", "pa1", "pb0", "pb1"].forEach(id => {
      el(id).addEventListener("change", () => {
        ex.periodA = [Number(el("pa0").value), Number(el("pa1").value)];
        ex.periodB = [Number(el("pb0").value), Number(el("pb1").value)];
        if (ex.periodA[0] > ex.periodA[1] || ex.periodB[0] > ex.periodB[1]) {
          toast("La borne de début est après la borne de fin.", "err");
          return;
        }
        loadExplorerData();
      });
    });

    el("btn-refresh").addEventListener("click", () => loadExplorerData());
    el("btn-full").addEventListener("click", () => {
      const cov = coverage();
      ex.start = cov[0]; ex.end = cov[1];
      el("start-year").value = cov[0]; el("end-year").value = cov[1];
      loadExplorerData();
    });
    el("btn-cds").addEventListener("click", async () => {
      ex.source = "cds";
      el("source-select").value = "cds";
      updateVarHint();
      toast("Requête CDS lancée : comptez 20 à 90 secondes…");
      await loadExplorerData();
    });

    el("btn-table").addEventListener("click", () => {
      const host = el("table-host");
      const shown = host.style.display !== "none";
      host.style.display = shown ? "none" : "block";
      el("btn-table").textContent = shown ? "Afficher le tableau" : "Masquer le tableau";
      if (!shown) renderTable();
    });
  }

  function syncExplorerControls() {
    document.querySelectorAll("#var-seg button").forEach(b =>
      b.classList.toggle("active", b.getAttribute("data-var") === state.explorer.variable));
    document.querySelectorAll("#view-seg button").forEach(b =>
      b.classList.toggle("active", b.getAttribute("data-view") === state.explorer.view));
    const cc = el("compare-controls");
    if (cc) cc.style.display = state.explorer.view === "compare" ? "block" : "none";
    updateVarHint();
  }

  async function loadExplorerData(opts) {
    const ex = state.explorer;
    if (!ex.cities.length) {
      Charts.emptyState("chart-explorer", "Aucune ville sélectionnée.", "Choisissez une ville dans la colonne de gauche.");
      html("chart-heading", "");
      html("narrative", "Aucune ville sélectionnée.");
      html("indices", "");
      html("explorer-legend", "");
      return;
    }
    ex.loading = true;
    const chart = el("chart-explorer");
    if (chart && !(opts && opts.silent)) {
      chart.classList.add("chart-empty");
      chart.innerHTML = '<div class="chart-empty">Téléchargement des données…</div>';
    }

    try {
      // Vue « avant / après » : on charge la période qui couvre les deux
      // comparaisons, sinon la colonne de gauche resterait vide.
      let start = ex.start;
      let end = ex.end;
      if (ex.view === "compare") {
        start = Math.min(start, ex.periodA[0], ex.periodB[0]);
        end = Math.max(end, ex.periodA[1], ex.periodB[1]);
      }
      start = Math.max(coverage()[0], start);
      end = Math.min(coverage()[1], end);

      const params = {
        cities: ex.cities.join(","),
        variable: ex.variable,
        start: start,
        end: end,
        source: ex.source
      };
      ex.payload = await api("api/series" + queryString(params));

      if (ex.view === "ombro") {
        const precipParams = Object.assign({}, params, { variable: "total_precipitation" });
        try {
          ex.precip = await api("api/series" + queryString(precipParams));
        } catch (e) {
          ex.precip = null;
          toast("Précipitations indisponibles : " + e.message, "err");
        }
      } else {
        ex.precip = null;
      }

      drawExplorerChart();
      renderIndices();
      if (el("table-host").style.display !== "none") renderTable();
      if (ex.payload.meta.simulated) toast(ex.payload.meta.warning, "err");
    } catch (err) {
      Charts.emptyState("chart-explorer", "Impossible de charger les données.", esc(err.message));
      html("chart-heading", "");
      html("narrative", '<span class="muted">' + esc(err.message) + "</span>");
      html("indices", "");
      toast(err.message, "err");
    } finally {
      ex.loading = false;
    }
  }

  function renderExplorerMeta() {
    const ex = state.explorer;
    const meta = ex.payload.meta;
    html("src-badge", badgeFor(ex.payload));
    html("src-detail", esc(meta.source_label) + " · " + esc(meta.variable_label) + " (" + esc(meta.unit) + ")");
    html("elapsed", meta.elapsed_s + " s");
    html("period-label", meta.start + " – " + meta.end);
    const narrative = ex.cities.map(c => (ex.payload.stats[c] || {}).narrative).filter(Boolean);
    html("narrative", narrative.length
      ? narrative.map(t => "<p>" + esc(t) + "</p>").join("")
      : "<p class='muted'>Pas de narration disponible.</p>");
    if (meta.monthly_rate_note) {
      html("narrative", el("narrative").innerHTML +
        '<p class="small muted" style="margin-bottom:0">' + esc(meta.monthly_rate_note) + "</p>");
    }
    const legend = el("explorer-legend");
    if (legend) {
      legend.innerHTML = ex.cities.map((c, i) =>
        '<span><i class="dot" style="background:' + Charts.colorFor(i) + '"></i>' + esc(c) + "</span>"
      ).join("") + extraNotes() +
        '<span class="muted">Source : ' + esc(meta.source_label) + "</span>";
    }
  }

  // Compléments de la bande de légende : cumuls de pluie, moyennes comparées,
  // normale des anomalies — lus à côté des villes plutôt que dans le graphique.
  function extraNotes() {
    const ex = state.explorer;
    if (!ex.payload) return "";
    try {
      if (ex.view === "ombro") return Charts.notes.ombro(ex.payload.stats, ex.precip);
      if (ex.view === "compare") {
        return Charts.notes.compare(ex.payload, [ex.periodA, ex.periodB], ex.cities[0]);
      }
      if (ex.view === "anomalies") return Charts.notes.anomalies(ex.payload, ex.cities[0]);
    } catch (e) { /* ignore */ }
    return "";
  }

  function explorerHeading() {
    const ex = state.explorer;
    const meta = (ex.payload && ex.payload.meta) || {};
    const city = ex.cities[0] || "";
    switch (ex.view) {
      case "line":
        return (meta.variable_label || "") + " — " + meta.start + " → " + meta.end;
      case "ombro":
        return "Diagramme ombrothermique — normale mensuelle";
      case "annual":
        return "Moyennes annuelles et tendance linéaire";
      case "anomalies": {
        const a = ex.payload.stats[city] && ex.payload.stats[city].anomalies;
        return "Anomalie annuelle par rapport à " + (a ? a.reference : "la moyenne") + " — " + city;
      }
      case "compare":
        return city + " — " + ex.periodA[0] + "-" + ex.periodA[1] +
          " comparé à " + ex.periodB[0] + "-" + ex.periodB[1];
      default: {
        const s = ex.payload.stats[city] && ex.payload.stats[city].climatology;
        return "Normale mensuelle (" + (s && s.reference ? s.reference : meta.start + "-" + meta.end) + ")";
      }
    }
  }

  function drawExplorerChart() {
    const ex = state.explorer;
    if (!ex.payload) return;
    html("chart-heading", explorerHeading());
    renderExplorerMeta();
    switch (ex.view) {
      case "line": Charts.line("#chart-explorer", ex.payload, { rangeslider: true }); break;
      case "ombro": renderOmbro(); break;
      case "annual": Charts.annual("#chart-explorer", ex.payload); break;
      case "anomalies": Charts.anomalies("#chart-explorer", ex.payload, { city: ex.cities[0] }); break;
      case "compare": Charts.compare("#chart-explorer", ex.payload, {
        periods: [ex.periodA, ex.periodB], city: ex.cities[0]
      }); break;
      default: Charts.climato("#chart-explorer", ex.payload);
    }
  }

  function renderOmbro() {
    const ex = state.explorer;
    if (!ex.precip || !ex.precip.stats) {
      Charts.emptyState("chart-explorer", "Diagramme ombrothermique indisponible.",
        "Choisissez une période couverte par les fichiers de précipitations.");
      return;
    }
    Charts.ombro("#chart-explorer", {
      meta: ex.payload.meta,
      stats: ex.payload.stats,
      precip: ex.precip
    });
  }

  function renderIndices() {
    const ex = state.explorer;
    const host = el("indices");
    if (!host) return;
    const first = ex.payload.stats[ex.cities[0]];
    if (!first || !first.indices) { html(host, '<p class="muted small">Aucun indicateur.</p>'); return; }
    html(host, first.indices.map(i => `
      <div class="index-row">
        <div class="label">${esc(i.label)}</div>
        <div class="value">${i.value === null || i.value === undefined ? "—" : esc(String(i.value))}
          <small>${esc(i.unit || "")}</small></div>
        ${i.definition ? `<div class="def">${esc(i.definition)}</div>` : ""}
        ${i.reading ? `<div class="reading">${esc(i.reading)}</div>` : ""}
      </div>
    `).join(""));
  }

  function renderTable() {
    const ex = state.explorer;
    const host = el("table-host");
    if (!host || !ex.payload) return;
    const dates = ex.payload.series[ex.cities[0]].dates;
    const head = ex.cities.map(c => `<th>${esc(c)}</th>`).join("");
    const rows = dates.map((d, i) => {
      const cells = ex.cities.map(c => {
        const v = (ex.payload.series[c] || {}).values;
        return '<td class="num">' + (v && v[i] !== null && v[i] !== undefined ? fmt(v[i], 1) : "—") + "</td>";
      }).join("");
      return "<tr><td>" + d + "</td>" + cells + "</tr>";
    }).join("");
    host.innerHTML = '<div class="table-wrap" style="max-height:340px;overflow:auto">' +
      '<table class="data"><thead><tr><th>Mois</th>' + head + "</tr></thead><tbody>" +
      rows + "</tbody></table></div>";
  }

  /* ======================================================================== */
  /* Activités                                                                 */
  /* ======================================================================== */

  async function fetchActivities() {
    state.activities = await api("api/activities" + queryString({ code: state.teacherCode || "" }));
    state.unlocked = !!state.activities.unlocked;
    return state.activities;
  }

  async function renderActivities(main) {
    const data = await fetchActivities();
    const list = data.activities;

    main.innerHTML = `
      <div class="section-head">
        <p class="eyebrow">Fiches pédagogiques</p>
        <h1>Activités prêtes à projeter</h1>
        <p>${list.length} séquences de 55 minutes : chaque étape pose <strong>une seule question</strong>,
        formulée sur des valeurs climatiques réelles. Les corrigés ne s'affichent qu'après
        saisie du code enseignant.</p>
      </div>

      ${state.unlocked ? forgetMarkup() : teacherBoxMarkup()}

      <div class="activity-list" style="margin-top:1.1rem">
        ${list.map(a => `
          <a class="activity-card" href="#/activites/${a.key}">
            <div class="meta">
              <span class="badge">${esc(a.levels)}</span>
              <span class="badge">${esc(a.duration)}</span>
              ${a.difficulty > 1 ? `<span class="badge badge-warn">difficulté ${a.difficulty}</span>` : ""}
            </div>
            <h3>${esc(a.title)}</h3>
            <p>${esc(a.objective)}</p>
            <div class="inline-list">${a.keywords.slice(0, 4).map(k => `<span class="badge">${esc(k)}</span>`).join("")}</div>
            <span class="go">${a.n_steps} étapes · ${esc(a.subject)} →</span>
          </a>
        `).join("")}
      </div>
    `;
    bindTeacherBox(main, () => renderActivities(main));
  }

  function teacherBoxMarkup() {
    return `
      <div class="teacher-box" id="teacher-box">
        <div class="row">
          <div>
            <label class="field-label" for="teacher-code">Code enseignant</label>
            <input type="password" id="teacher-code" placeholder="Code enseignant"
              autocomplete="off" style="max-width:220px">
            <span class="hint">Sans code, la fiche affichée aux élèves reste sans corrigé.</span>
          </div>
          <div style="flex:0 0 auto">
            <button class="btn" id="teacher-unlock">Afficher les corrigés</button>
          </div>
        </div>
        <div id="teacher-out" class="small" style="margin-top:.5rem"></div>
      </div>
    `;
  }

  function forgetMarkup() {
    return `
      <div class="teacher-box" id="teacher-box">
        <div class="row">
          <div>
            <span class="badge badge-ok">corrigés visibles</span>
            <span class="hint">Pense à reverrouiller avant de projeter aux élèves.</span>
          </div>
          <div style="flex:0 0 auto">
            <button class="btn" id="teacher-forget" style="background:#64748b;color:#fff">Verrouiller</button>
          </div>
        </div>
      </div>
    `;
  }

  function bindTeacherBox(root, rerender) {
    const doc = root.ownerDocument || document;
    const btn = doc.getElementById("teacher-unlock");
    if (btn) btn.addEventListener("click", async () => {
      const input = document.getElementById("teacher-code");
      const code = (input && input.value || "").trim();
      try {
        const out = await api("api/teacher/unlock", { method: "POST", body: { code } });
        if (out.ok) {
          state.teacherCode = code;
          sessionStorage.setItem("c3s2_teacher_code", code);
          state.unlocked = true;
          try { await fetchActivities(); } catch (e) { /* keep current list */ }
          toast("Corrigés déverrouillés.", "ok");
          await rerender();
        } else {
          html("teacher-out", '<span class="badge badge-warn">Code incorrect</span>');
        }
      } catch (err) {
        html("teacher-out", esc(err.message));
      }
    });
    const input = doc.getElementById("teacher-code");
    if (input && btn) input.addEventListener("keydown", (e) => { if (e.key === "Enter") btn.click(); });
    const forget = doc.getElementById("teacher-forget");
    if (forget) forget.addEventListener("click", async () => {
      state.teacherCode = "";
      state.unlocked = false;
      try { sessionStorage.removeItem("c3s2_teacher_code"); } catch (e) {}
      try { await fetchActivities(); } catch (e) { /* keep current list */ }
      toast("Corrigés verrouillés.", "ok");
      await rerender();
    });
  }

  async function renderActivity(main, params) {
    const key = params[0];
    const data = state.activities && state.activities.activities
      ? state.activities
      : await fetchActivities();
    const act = (data.activities || []).find(a => a.key === key);
    if (!act) {
      html(main, '<div class="card"><h2>Activité introuvable</h2><p><a class="btn" href="#/activites">Retour à la liste</a></p></div>');
      return;
    }

    const charts = [];
    act.steps.forEach(s => {
      [s.chart, s.chart2].forEach(c => { if (c && c !== "none") charts.push(c); });
    });
    const needMap = charts.includes("map");
    const needHeat = charts.includes("heat");
    let mapPayload = null;
    let heatPayload = null;
    const mapCache = {};

    if (needMap) {
      const fallback = act.key === "vent_pression" ? "mslp_janvier" : "t2m_janvier";
      const ids = [];
      act.steps.forEach(s => {
        if (s.chart === "map") ids.push(s.map_id || fallback);
        if (s.chart2 === "map" && s.map2_id) ids.push(s.map2_id);
      });
      for (const id of [...new Set(ids)]) {
        if (!id) continue;
        try { mapCache[id] = await api("api/maps/" + id); } catch (e) { /* carte absente */ }
      }
      const first = ids.find(id => mapCache[id]);
      mapPayload = first ? mapCache[first] : null;
    }
    if (needHeat) {
      try {
        heatPayload = await loadHeat();
      } catch (e) {
        heatPayload = null;
      }
    }

    main.innerHTML = `
      <p class="small"><a href="#/activites">← Toutes les activités</a></p>

      <div class="card">
        <div class="panel-title">
          <div>
            <p class="eyebrow">${esc(act.subject)}</p>
            <h1 style="margin-bottom:.3rem">${esc(act.title)}</h1>
            <div class="meta inline-list">
              <span class="badge">${esc(act.levels)}</span>
              <span class="badge">${esc(act.duration)}</span>
              <span class="badge">${act.n_steps} étapes</span>
              ${act.cities.length ? `<span class="badge">${esc(act.cities.join(" · "))}</span>` : ""}
            </div>
            <img src="assets/situation/${esc(act.key)}.png" alt="Situation des villes étudiées"
              class="situation" loading="lazy" onerror="this.remove()">
          </div>
          ${state.unlocked ? '<span class="badge badge-ok">corrigés visibles</span>' : ""}
        </div>
        <p>${esc(act.introduction)}</p>
        <h3>Objectif</h3>
        <p class="small">${esc(act.objective)}</p>
        <h3>Ce que tu vas apprendre à faire</h3>
        <ul class="small">${act.skills.map(s => "<li>" + esc(s) + "</li>").join("")}</ul>
      </div>

      ${act.exam ? examMarkup(act.exam) : ""}

      ${state.unlocked
        ? `<div style="margin-top:1.1rem">${forgetMarkup()}</div>`
        : `<div style="margin-top:1.1rem">${teacherBoxMarkup()}</div>`}

      <div class="progress-track" id="progress">
        ${act.steps.map((s, i) => `<div data-step="${i + 1}"></div>`).join("")}
      </div>

      <div class="layout-side" id="activity-body">
        <div id="steps-col">
          ${act.steps.map((s, i) => stepMarkup(act, s, i + 1)).join("")}
        </div>
        <div id="chart-col" style="position:sticky;top:calc(var(--nav-h) + 12px)">
          <div class="card">
            <div class="panel-title">
              <div><h3 id="chart-title">Graphique de l'étape</h3></div>
              <span class="badge" id="chart-step">étape 1</span>
            </div>
            <div id="activity-chart" class="chart"><div class="chart-empty">Chargement…</div></div>
            <div class="chart-legend" id="activity-legend"></div>
            <div id="activity-chart-note" class="small muted"></div>
            <div id="chart2-block" hidden style="border-top:1px solid rgba(148,163,184,.35);margin-top:.8rem;padding-top:.7rem">
              <div class="panel-title">
                <div><h3 id="chart2-title" style="font-size:1rem">Second document</h3></div>
                <span class="badge badge-cds">second document</span>
              </div>
              <div id="activity-chart2" class="chart"><div class="chart-empty">Chargement…</div></div>
              <div id="activity-chart2-note" class="small muted"></div>
            </div>
          </div>
        </div>
      </div>

      <div class="card">
        <h3>Données de l'activité</h3>
        <p class="small muted">Villes : ${esc(act.cities.join(", "))} — variables : ${esc(act.variables.join(", "))}
        — source : ${esc(act.source)}. Les valeurs affichées sont des moyennes de grille ERA5 (0,25°).</p>
        <div class="row">
          <button class="btn btn-sm" id="act-load">Recharger les données</button>
          <button class="btn btn-sm btn-ghost" id="act-print">Imprimer la fiche</button>
        </div>
      </div>
    `;

    bindTeacherBox(main, () => renderActivity(main, params));

    if (act.exam) {
      document.querySelectorAll("[data-exam-answer]").forEach(btn => {
        btn.addEventListener("click", () => {
          const n = btn.getAttribute("data-exam-answer");
          const target = document.querySelector('.exam-answer[data-exam="' + n + '"]');
          if (target) {
            target.hidden = !target.hidden;
            btn.textContent = target.hidden ? "Voir le corrigé" : "Masquer le corrigé";
          }
        });
      });
      drawExamFigures(act);
    }

    const ctx = { act, mapPayload, mapCache, heatPayload, current: 1 };
    window.__c3sActivity = ctx;

    document.querySelectorAll("#steps-col .step").forEach((node) => {
      node.addEventListener("click", (e) => {
        if (e.target.closest("button")) return;
        setActiveStep(Number(node.getAttribute("data-step")));
      });
    });
    document.querySelectorAll("[data-hint]").forEach(btn => {
      btn.addEventListener("click", () => {
        const n = btn.getAttribute("data-hint");
        const target = document.querySelector('.step[data-step="' + n + '"] .step-hint');
        if (target) {
          target.hidden = !target.hidden;
          btn.textContent = target.hidden ? "Afficher la piste" : "Masquer la piste";
        }
      });
    });
    document.querySelectorAll("[data-next]").forEach(btn => {
      btn.addEventListener("click", () => setActiveStep(Number(btn.getAttribute("data-next"))));
    });
    document.querySelectorAll("[data-prev]").forEach(btn => {
      btn.addEventListener("click", () => setActiveStep(Number(btn.getAttribute("data-prev"))));
    });
    document.querySelectorAll("[data-answer]").forEach(btn => {
      btn.addEventListener("click", () => {
        const n = btn.getAttribute("data-answer");
        const target = document.querySelector('.step[data-step="' + n + '"] .step-answer');
        if (target) {
          target.hidden = !target.hidden;
          btn.textContent = target.hidden ? "Voir le corrigé" : "Masquer le corrigé";
        }
      });
    });

    el("act-print") && el("act-print").addEventListener("click", () => window.print());
    el("act-load") && el("act-load").addEventListener("click", () => renderActivity(main, params));

    setActiveStep(1);
  }

  function examMarkup(exam) {
    return `
      <section class="card exam-card" id="exam-subject">
        <div class="panel-title">
          <div>
            <p class="eyebrow">Préparation au brevet</p>
            <h2>Sujet type brevet</h2>
            <div class="meta inline-list">
              <span class="badge">${exam.duration} min</span>
              <span class="badge badge-warn">${exam.points} points</span>
              <span class="badge">${exam.documents.length} documents</span>
              <span class="badge">${exam.questions.length} questions</span>
            </div>
          </div>
          ${state.unlocked ? '<span class="badge badge-ok">corrigés visibles</span>' : ""}
        </div>
        <p>${esc(exam.contexte)}</p>
        <div class="exam-rappel"><strong>Consigne :</strong> ${esc(exam.rappel)}</div>
        ${exam.documents.map(examDocMarkup).join("")}
        <h3>Questions <span class="small muted">(difficulté croissante)</span></h3>
        ${exam.questions.map(examQuestionMarkup).join("")}
        <p class="small muted">Thème : ${esc(exam.theme)}<br>
          Sources : ${exam.sources.map(esc).join(" · ")}</p>
      </section>
    `;
  }

  function examDocMarkup(d) {
    let visual = "";
    if (d.chart === "table") {
      const head = (d.table[0] || []).map(c => "<th>" + esc(c) + "</th>").join("");
      const rows = d.table.slice(1).map(row =>
        "<tr>" + row.map(c => "<td>" + esc(c) + "</td>").join("") + "</tr>").join("");
      visual = '<table class="data exam-table"><thead><tr>' + head + "</tr></thead><tbody>" +
        rows + "</tbody></table>";
    } else if (d.chart === "figure") {
      visual = '<div class="chart exam-fig" id="exam-fig-' + d.number + '">' +
        '<img src="assets/figures/' + esc(d.file) + '" alt="' + esc(d.title) + '" ' +
        'style="max-width:100%" onerror="this.remove()"></div>';
    } else if (d.chart === "annual" || d.chart === "anomalies") {
      visual = '<div class="chart exam-fig" id="exam-fig-' + d.number + '">' +
        '<div class="chart-empty">Chargement…</div></div>';
    }
    return `
      <figure class="exam-doc">
        <h4>Document ${d.number} — ${esc(d.title)}</h4>
        <p class="small">${esc(d.body)}</p>
        ${visual}
        ${d.caption ? `<figcaption class="small muted">${esc(d.caption)}</figcaption>` : ""}
      </figure>
    `;
  }

  function examQuestionMarkup(q) {
    const unlocked = state.unlocked && q.expected;
    return `
      <div class="exam-q">
        <div class="exam-q-head">
          <strong>Question ${esc(q.id)}</strong>
          <span class="badge">${q.points} pt${q.points > 1 ? "s" : ""}</span>
          <span class="badge badge-cds">${esc(q.skill)}</span>
        </div>
        <p class="step-question">${esc(q.text)}</p>
        ${unlocked
          ? `<button class="btn btn-sm btn-warm" data-exam-answer="${esc(q.id)}">Voir le corrigé</button>
             <div class="exam-answer" data-exam="${esc(q.id)}" hidden>
               <strong>Ce qui est attendu :</strong> ${esc(q.attendu)}<br>
               <strong>Corrigé :</strong> ${esc(q.expected)}
             </div>`
          : '<span class="small muted">Corrigé réservé au code enseignant</span>'}
      </div>
    `;
  }

  async function drawExamFigures(act) {
    const exam = act.exam;
    if (!exam) return;
    for (const d of exam.documents) {
      if (d.chart !== "annual" && d.chart !== "anomalies") continue;
      const target = "#exam-fig-" + d.number;
      const node = document.querySelector(target);
      if (!node) continue;
      try {
        const cities = (act.cities.length ? act.cities : ["Paris"]).slice(0, 1);
        const long = await api("api/series" + queryString({
          cities: cities.join(","),
          variable: "2m_temperature",
          start: 1940,
          end: 2024,
          source: "auto"
        }));
        if (d.chart === "annual") {
          Charts.annual(target, long);
        } else {
          Charts.anomalies(target, long, { city: cities[0] });
        }
      } catch (e) {
        node.innerHTML = '<div class="chart-empty">Graphique indisponible.</div>';
      }
    }
  }

  function stepMarkup(act, step, n) {
    return `
      <article class="step" data-step="${n}">
        <div class="step-head">
          <span class="step-num">${n}</span>
          <h3>${esc(step.title)}</h3>
          <span class="badge">${step.minutes} min</span>
          <span class="badge badge-cds">${esc(stepBadge(step))}</span>
        </div>
        <p class="step-question">${esc(step.instruction)}</p>
        <div class="step-tools">
          <button class="btn btn-sm btn-ghost" data-hint="${n}">Afficher la piste</button>
          ${state.unlocked
            ? `<button class="btn btn-sm btn-warm" data-answer="${n}">Voir le corrigé</button>`
            : '<span class="small muted">Corrigé réservé au code enseignant</span>'}
          ${n > 1 ? `<button class="btn btn-sm btn-quiet" data-prev="${n - 1}">← Étape ${n - 1}</button>` : ""}
          ${n < act.n_steps ? `<button class="btn btn-sm btn-quiet" data-next="${n + 1}">Étape ${n + 1} →</button>` : ""}
        </div>
        ${step.hint ? `<div class="step-hint" hidden><strong>Piste :</strong> ${esc(step.hint)}</div>` : ""}
        ${state.unlocked && step.expected
          ? `<div class="step-answer" hidden><strong>Corrigé :</strong> ${esc(step.expected)}</div>` : ""}
      </article>
    `;
  }

  function cap(text) {
    return text ? text.charAt(0).toUpperCase() + text.slice(1) : text;
  }

  function chartLabel(chart) {
    return {
      climato: "normale mensuelle",
      ombro: "ombrothermie",
      annual: "moyennes annuelles",
      anomalies: "anomalies",
      compare: "avant / après",
      map: "carte climatique",
      schema: "schéma des courants",
      figure: "figure de données",
      heat: "données journalières",
      line: "séries mensuelles",
      none: "aucun graphique"
    }[chart] || chart;
  }

  function stepBadge(step) {
    const main = chartLabel(step.chart);
    if (!step.chart2) return main;
    const second = step.chart2 === "schema" && (step.file2 || "").indexOf("rayons") >= 0
      ? "schéma des rayons"
      : chartLabel(step.chart2);
    return main + " + " + second;
  }

  async function setActiveStep(n) {
    const ctx = window.__c3sActivity;
    if (!ctx) return;
    ctx.current = n;
    document.querySelectorAll("#progress div").forEach(d => {
      const i = Number(d.getAttribute("data-step"));
      d.classList.toggle("current", i === n);
      d.classList.toggle("done", i < n);
    });
    document.querySelectorAll(".step").forEach(s => {
      s.style.borderColor = Number(s.getAttribute("data-step")) === n ? "var(--temp)" : "";
    });
    const step = ctx.act.steps[n - 1];
    html("chart-step", "étape " + n);
    html("chart-title", chartLabel(step.chart));
    await drawActivityChart(step);
    await drawSecondDoc(step);
  }

  async function drawActivityChart(step) {
    const ctx = window.__c3sActivity;
    const act = ctx.act;
    const target = "#activity-chart";
    const cities = act.cities.length ? act.cities : state.explorer.cities;

    if (step.chart === "none") {
      Charts.emptyState(target, "Étape sans graphique : travail au brouillon.");
      html("activity-legend", "");
      html("activity-chart-note", "");
      return;
    }

    if (step.chart === "map") {
      const payload = (step.map_id && ctx.mapCache && ctx.mapCache[step.map_id]) || ctx.mapPayload;
      if (!payload) {
        Charts.emptyState(target, "Carte indisponible.",
          "Lancez la préparation : <code>python scripts/prepare_maps.py</code>");
        return;
      }
      html("chart-title", payload.title || "Carte climatique");
      Charts.map(target, payload);
      html("activity-legend", Charts.notes.map(payload));
      html("activity-chart-note", payload.source || "");
      return;
    }

    if (step.chart === "heat") {
      if (!ctx.heatPayload) {
        Charts.emptyState(target, "Données journalières indisponibles.",
          "Cliquez sur « Recharger les données » : une requête CDS sera lancée.");
        return;
      }
      html("chart-title", "Températures journalières — " + cities[0]);
      Charts.heat(target, ctx.heatPayload, { city: cities[0] });
      html("activity-legend", "");
      html("activity-chart-note",
        "Jours avec maximum ≥ " + ctx.heatPayload.meta.tmax_threshold +
        " °C et minimum ≥ " + ctx.heatPayload.meta.tmin_threshold + " °C.");
      return;
    }

    if (step.chart === "schema") {
      html("chart-title", "Courants de surface de l'Atlantique Nord — schéma");
      html(target.replace("#", ""),
        '<img src="assets/schemas/courants_atlantique.png" ' +
        'alt="Schéma des courants de l\'Atlantique Nord" class="situation">');
      html("activity-legend", "");
      html("activity-chart-note", "Schéma pédagogique simplifié (pas une donnée CDS).");
      return;
    }

    if (step.chart === "figure") {
      const n = ((ctx.act && ctx.act.steps) || []).indexOf(step) + 1;
      html("chart-title", "Figure de données — étape " + n);
      html(target.replace("#", ""),
        '<img src="assets/figures/' + act.key + '_' + n + '.png" ' +
        'alt="Figure de données de l\'étape ' + n + '" class="situation" ' +
        'onerror="this.outerHTML=\'<p class=&quot;small muted&quot;>Figure indisponible.</p>\'">');
      html("activity-legend", "");
      html("activity-chart-note", "Figure construite sur des données ERA5 pré-calculées.");
      return;
    }

    html("chart-title", cap(chartLabel(step.chart)) + " — " + cities.slice(0, 4).join(", "));

    try {
      const variable = step.chart === "ombro" ? "2m_temperature" : (act.variables[0] || "2m_temperature");
      const payload = await api("api/series" + queryString({
        cities: cities.slice(0, 4).join(","),
        variable,
        start: 1991,
        end: 2020,
        source: "auto"
      }));

      let precip = null;
      let long = null;

      if (step.chart === "ombro") {
        precip = await api("api/series" + queryString({
          cities: cities.slice(0, 4).join(","),
          variable: "total_precipitation",
          start: 1991, end: 2020, source: "auto"
        }));
        Charts.ombro(target, { meta: payload.meta, stats: payload.stats, precip: precip });
        html("activity-chart-note", "Normale 1991-2020 · barres = cumul mensuel, courbe = température, pointillés = 2×T (aridité).");
      } else if (step.chart === "annual") {
        long = await api("api/series" + queryString({
          cities: cities.slice(0, 2).join(","), variable: "2m_temperature",
          start: 1940, end: 2024, source: "auto"
        }));
        Charts.annual(target, long);
        html("activity-chart-note", "Moyennes annuelles 1940-2024 et tendance (régression linéaire).");
      } else if (step.chart === "anomalies") {
        long = await api("api/series" + queryString({
          cities: cities.slice(0, 2).join(","), variable: "2m_temperature",
          start: 1940, end: 2024, source: "auto"
        }));
        Charts.anomalies(target, long, { city: cities[0] });
        html("activity-chart-note", "Écart de chaque année à la moyenne de la période affichée.");
      } else if (step.chart === "compare") {
        long = await api("api/series" + queryString({
          cities: cities.slice(0, 2).join(","), variable: "2m_temperature",
          start: 1940, end: 2024, source: "auto"
        }));
        Charts.compare(target, long, { periods: [state.explorer.periodA, state.explorer.periodB], city: cities[0] });
        html("activity-chart-note", "Deux périodes de trente ans comparées mois par mois.");
      } else {
        Charts.climato(target, payload);
        html("activity-chart-note", "Normale mensuelle calculée sur la période affichée (1991-2020).");
      }

      let extras = "";
      try {
        if (step.chart === "ombro") extras = Charts.notes.ombro(payload.stats, precip);
        else if (step.chart === "compare") {
          extras = Charts.notes.compare(long, [state.explorer.periodA, state.explorer.periodB], cities[0]);
        } else if (step.chart === "anomalies") extras = Charts.notes.anomalies(long, cities[0]);
      } catch (e) { /* ignore */ }
      html("activity-legend", cities.slice(0, 4).map((c, i) =>
        '<span><i class="dot" style="background:' + Charts.colorFor(i) + '"></i>' + esc(c) + "</span>"
      ).join("") + extras);
    } catch (err) {
      Charts.emptyState(target, "Graphique indisponible.", esc(err.message));
    }
  }

  async function drawSecondDoc(step) {
    const ctx = window.__c3sActivity;
    const block = document.getElementById("chart2-block");
    if (!block) return;
    if (!step.chart2) { block.hidden = true; return; }
    block.hidden = false;
    html("activity-chart2-note", "");
    const act = ctx.act;
    const cities = act.cities.length ? act.cities : state.explorer.cities;
    const target = "#activity-chart2";

    if (step.chart2 === "map") {
      const payload = ctx.mapCache && ctx.mapCache[step.map2_id];
      html("chart2-title", payload ? payload.title : "Carte climatique");
      if (!payload) { Charts.emptyState(target, "Carte indisponible."); return; }
      Charts.map(target, payload);
      html("activity-chart2-note", payload.source || "");
      return;
    }

    if (step.chart2 === "schema") {
      const file = step.file2 || "courants_atlantique.png";
      html("chart2-title", file.indexOf("rayons") >= 0
        ? "Réception du rayonnement selon la latitude — schéma"
        : "Schéma pédagogique");
      html("activity-chart2",
        '<img src="assets/schemas/' + esc(file) + '" alt="Schéma pédagogique" class="situation" ' +
        'onerror="this.outerHTML=\'<p class=&quot;small muted&quot;>Schéma indisponible.</p>\'">');
      html("activity-chart2-note", "Schéma pédagogique simplifié (pas une donnée CDS).");
      return;
    }

    if (step.chart2 === "annual") {
      html("chart2-title", cap(chartLabel("annual")) + " — " + cities[0]);
      try {
        const long = await api("api/series" + queryString({
          cities: cities.slice(0, 2).join(","), variable: "2m_temperature",
          start: 1940, end: 2024, source: "auto"
        }));
        Charts.annual(target, long);
        html("activity-chart2-note", "Moyennes annuelles 1940-2024 et tendance (régression linéaire).");
      } catch (err) {
        Charts.emptyState(target, "Graphique indisponible.", esc(err.message));
      }
      return;
    }

    if (step.chart2 === "ombro") {
      html("chart2-title", cap(chartLabel("ombro")) + " — " + cities.slice(0, 3).join(", "));
      try {
        const temp = await api("api/series" + queryString({
          cities: cities.slice(0, 3).join(","), variable: "2m_temperature",
          start: 1991, end: 2020, source: "auto"
        }));
        const precip = await api("api/series" + queryString({
          cities: cities.slice(0, 3).join(","), variable: "total_precipitation",
          start: 1991, end: 2020, source: "auto"
        }));
        Charts.ombro(target, { meta: temp.meta, stats: temp.stats, precip });
        html("activity-chart2-note", "Normale 1991-2020 · barres = cumul mensuel, courbe = température, pointillés = 2×T (aridité).");
      } catch (err) {
        Charts.emptyState(target, "Graphique indisponible.", esc(err.message));
      }
      return;
    }

    Charts.emptyState(target, "Second document indisponible.");
  }

  async function loadHeat(force) {
    const h = state.heat;
    if (h.payload && !force) return h.payload;
    h.loading = true;
    const payload = await api("api/heat" + queryString({
      cities: "Marseille,Paris",
      start: h.start, end: h.end, tmax: h.tmax, tmin: h.tmin
    }));
    h.payload = payload;
    h.loading = false;
    return payload;
  }

  /* ======================================================================== */
  /* Cartes                                                                    */
  /* ======================================================================== */

  async function renderMaps(main) {
    const maps = state.places.maps || [];
    const selected = state.maps.selected || (maps[0] && maps[0].id);

    main.innerHTML = `
      <div class="section-head">
        <p class="eyebrow">Cartes climatiques</p>
        <h1>Lire une carte du climat</h1>
        <p>Les cartes statiques sont pré-calculées (normale 1991-2020) et servies
        directement par le CDN : aucun délai en séance. Le bouton « CDS en direct »
        permet de télécharger un champ réel pour un mois et un domaine libres.</p>
      </div>

      ${maps.length ? `
        <div class="grid grid-3" style="margin-bottom:1.2rem">
          ${maps.map(m => `
            <button class="map-card" data-map="${esc(m.id)}" style="text-align:left;cursor:pointer;${m.id === selected ? "border-color:var(--temp);box-shadow:var(--shadow)" : ""}">
              <div class="map-card-body">
                <span class="eyebrow">${esc(m.unit)} · ${esc(m.period || "")}</span>
                <h3>${esc(m.title || m.variable_label)}</h3>
                <p>${esc(m.domain || "")}${m.month ? " · mois " + m.month : ""}</p>
              </div>
            </button>
          `).join("")}
        </div>
      ` : `
        <div class="empty">Aucune carte pré-calculée.
          <p class="small">Lancez <code>python scripts/prepare_maps.py</code> pour en créer.</p>
        </div>
      `}

      <div class="card">
        <div class="panel-title">
          <div>
            <span class="badge" id="map-badge">${state.maps.live ? "CDS en direct" : "statique"}</span>
            <span class="small muted" id="map-title">${esc(selected || "")}</span>
          </div>
          <div class="small muted" id="map-timing"></div>
        </div>

        <div class="map-toolbar">
          <div class="seg" id="map-quick">
            ${maps.map(m => `<button data-map="${esc(m.id)}" class="${m.id === selected ? "active" : ""}">${esc((m.title || m.id).split("—")[0])}</button>`).join("")}
          </div>
        </div>

        <div class="map-toolbar" style="border-top:1px solid var(--line);padding-top:.8rem">
          <div class="field" style="margin:0;min-width:170px">
            <label class="field-label" for="map-var">Variable</label>
            <select id="map-var">
              ${state.places.variables.map(v => `<option value="${v.slug}">${esc(v.label)}</option>`).join("")}
            </select>
          </div>
          <div class="field" style="margin:0;min-width:140px">
            <label class="field-label" for="map-month">Mois</label>
            <select id="map-month">
              ${Charts.MONTHS.map((m, i) => `<option value="${i + 1}"${i === 0 ? " selected" : ""}>${m}</option>`).join("")}
            </select>
          </div>
          <div class="field" style="margin:0;min-width:210px">
            <label class="field-label" for="map-domain">Domaine</label>
            <select id="map-domain">
              ${state.places.domains.map(d => `<option value="${esc(d.name)}"${d.name === "Europe" ? " selected" : ""}>${esc(d.name)}</option>`).join("")}
            </select>
          </div>
          <div style="align-self:flex-end">
            <button class="btn" id="map-live">Télécharger depuis le CDS</button>
          </div>
        </div>

        <div id="map-frame" class="map-frame chart chart-lg"><div class="chart-empty">Sélectionnez une carte…</div></div>
        <div class="map-meta" id="map-meta"></div>
      </div>

      <div class="card">
        <h3>Comment ces cartes sont produites</h3>
        <p class="small muted">Chaque carte est la moyenne des moyennes mensuelles ERA5 sur
        1991-2020, calculée sur l'Europe (0,25°) puis réduite à 0,5° pour rester légère.
        La pression est convertie en hPa, les précipitations en cumul mensuel (mm/mois),
        la vitesse du vent est calculée à partir des composantes U et V.</p>
        <p class="small muted">Les lignes fines sont les côtes (Natural Earth 110 m) ; les
        flèches de la carte de vent donnent la direction moyenne du vent à 10 m.</p>
      </div>
    `;

    document.querySelectorAll("[data-map]").forEach(node => {
      node.addEventListener("click", () => loadStaticMap(node.getAttribute("data-map")));
    });

    el("map-live").addEventListener("click", loadLiveMap);

    if (selected) await loadStaticMap(selected);
  }

  async function loadStaticMap(id) {
    state.maps.selected = id;
    state.maps.live = false;
    const frame = el("map-frame");
    if (!frame) return;
    frame.classList.add("chart-empty");
    frame.innerHTML = '<div class="chart-empty">Chargement de la carte…</div>';
    try {
      const payload = await api("api/maps/" + id);
      state.maps.payload = payload;
      Charts.map("#map-frame", payload);
      html("map-badge", '<span class="badge badge-ok">statique</span>');
      html("map-title", esc(payload.title));
      html("map-timing", payload.period + (payload.month ? " · mois " + payload.month : ""));
      html("map-meta", `
        <span>${esc(payload.variable_label)}</span>
        <span>unité : ${esc(payload.unit)}</span>
      ` + Charts.notes.map(payload));
      document.querySelectorAll("#map-quick button").forEach(b =>
        b.classList.toggle("active", b.getAttribute("data-map") === id));
      document.querySelectorAll(".map-card").forEach(c => {
        c.style.borderColor = c.getAttribute("data-map") === id ? "var(--temp)" : "";
        c.style.boxShadow = c.getAttribute("data-map") === id ? "var(--shadow)" : "";
      });
    } catch (err) {
      Charts.emptyState("#map-frame", "Carte indisponible.", esc(err.message));
      toast(err.message, "err");
    }
  }

  async function loadLiveMap() {
    const btn = el("map-live");
    const frame = el("map-frame");
    const form = {
      variable: el("map-var").value,
      month: Number(el("map-month").value),
      domain: el("map-domain").value
    };
    btn.disabled = true;
    btn.textContent = "Requête en cours (20-90 s)…";
    frame.classList.add("chart-empty");
    frame.innerHTML = '<div class="chart-empty"><div class="spinner"></div><p>Téléchargement ERA5 depuis le CDS…</p></div>';
    try {
      const payload = await api("api/field", { method: "POST", body: form });
      state.maps.payload = payload;
      state.maps.live = true;
      Charts.map("#map-frame", payload);
      html("map-badge", '<span class="badge badge-cds">CDS en direct</span>');
      html("map-title", esc(payload.title));
      html("map-timing", payload.elapsed_s + " s");
      html("map-meta", `
        <span>${esc(payload.variable_label)}</span>
        <span>unité : ${esc(payload.unit)}</span>
      ` + Charts.notes.map(payload));
      toast("Carte téléchargée en " + payload.elapsed_s + " s.", "ok");
    } catch (err) {
      Charts.emptyState("#map-frame", "Requête impossible.", esc(err.message));
      toast(err.message, "err");
    } finally {
      btn.disabled = false;
      btn.textContent = "Télécharger depuis le CDS";
    }
  }

  /* ======================================================================== */
  /* Aide & état du CDS                                                        */
  /* ======================================================================== */

  async function renderAide(main) {
    const cfg = state.config;
    const diag = cfg.key_diagnosis || {};
    const precomputed = cfg.precomputed || [];
    const heat = cfg.heat_coverage || { tmax: [], tmin: [] };

    main.innerHTML = `
      <div class="section-head">
        <p class="eyebrow">Aide</p>
        <h1>Fonctionnement, données et dépannage</h1>
        <p>C3S² fonctionne sans clé pour tout ce qui est pré-calculé. La clé du
        Climate Data Store n'est nécessaire que pour les requêtes en direct
        (périodes hors couverture, champs spatiaux, données journalières).</p>
        ${forgetMarkup()}
      </div>

      <div class="grid grid-2">
        <div class="card">
          <div class="card-title"><h3>Trois sources de données</h3></div>
          <div class="stack">
            <div class="callout callout-ok"><h4>1. Fichiers pré-calculés</h4>
              <p class="small">Séries mensuelles de ${cfg.years[0]} à ${cfg.years[1]}, lues depuis <code>data/precomputed/</code>.
              Instantané, gratuit, hors ligne.</p></div>
            <div class="callout"><h4>2. Requête CDS en direct</h4>
              <p class="small">L'application construit la requête ERA5, la soumet, lit le NetCDF
              et convertit les unités. Comptez 20 à 90 s ; le cache local évite de relancer
              une requête identique.</p></div>
            <div class="callout callout-warn"><h4>3. Simulation</h4>
              <p class="small">Uniquement si aucune clé n'est configurée : les courbes sont
              plausibles mais <strong>fausses</strong>, et l'écran l'annonce.</p></div>
          </div>
        </div>

        <div class="card">
          <div class="card-title"><h3>Connexion au Climate Data Store</h3>
            ${diag.ok ? '<span class="badge badge-ok">clé détectée</span>' : '<span class="badge badge-warn">clé absente</span>'}</div>
          <table class="data">
            <tbody>
              <tr><th>URL</th><td>${esc(cfg.cds.url || "—")}</td></tr>
              <tr><th>Clé</th><td>${esc(cfg.cds.masked_key || "—")}</td></tr>
              <tr><th>Source</th><td>${esc(cfg.cds.source || "—")}</td></tr>
              <tr><th>Statut</th><td>${esc(diag.message || "—")}</td></tr>
            </tbody>
          </table>
          <div class="row" style="margin-top:.8rem">
            <button class="btn btn-sm" id="cds-test">Tester (léger)</button>
            <button class="btn btn-sm btn-ghost" id="cds-deep">Test approfondi (requête réelle)</button>
          </div>
          <div id="cds-out" class="small" style="margin-top:.7rem"></div>

          <div class="callout" style="margin-top:1rem">
            <h4>Configurer la clé</h4>
            <p class="small">Soit le fichier <code>.env</code> à la racine :</p>
            <pre class="mono small" style="white-space:pre-wrap;background:#fff;padding:.6rem;border-radius:6px;border:1px solid var(--line)">CDSAPI_KEY=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
CDSAPI_URL=https://cds.climate.copernicus.eu/api</pre>
            <p class="small" style="margin-bottom:0">soit <code>~/.cdsapirc</code> :</p>
            <pre class="mono small" style="white-space:pre-wrap;background:#fff;padding:.6rem;border-radius:6px;border:1px solid var(--line)">url: https://cds.climate.copernicus.eu/api
key: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx</pre>
          </div>
        </div>
      </div>

      <div class="card">
        <div class="card-title"><h3>Fichiers de données présents</h3>
          <a class="btn btn-sm btn-ghost" href="#/">Retour</a></div>
        <div class="file-list">
          ${precomputed.map(f => `
            <div class="file-row">
              <span class="name">${esc(f.file)}</span>
              <span class="muted">${esc(f.description)}</span>
              <span class="status" style="color:${f.status === "prêt" ? "var(--ok)" : "var(--gold)"}">${esc(f.status)} · ${esc(f.size)}</span>
            </div>`).join("")}
          <div class="file-row">
            <span class="name">chaleur_tmax.csv / chaleur_tmin.csv</span>
            <span class="muted">données journalières (activité canicule)</span>
            <span class="status" style="color:${(heat.tmax || []).length ? "var(--ok)" : "var(--gold)"}">
              ${(heat.tmax || []).length ? "prêt · " + (heat.tmax || []).join(", ") : "absent"}
            </span>
          </div>
        </div>
        <p class="small muted" style="margin-top:.8rem">
          Compléter les fichiers : <code>python scripts/prepare_data.py cities</code> puis
          <code>python scripts/prepare_data.py heat</code>. Cartes :
          <code>python scripts/prepare_maps.py</code>.
        </p>
      </div>

      <div class="grid grid-2">
        <div class="card">
          <h3>Pourquoi les précipitations sont multipliées</h3>
          <p class="small">Les moyennes mensuelles ERA5 livrent les précipitations en
          <strong>mètre par jour</strong> : la valeur « 2 » de janvier n'est pas 2 mm de pluie
          sur le mois, mais 2 mm <em>par jour</em> en moyenne. Pour avoir le cumul mensuel
          affiché sur un climatogramme, l'application multiplie par 1000 puis par le nombre
          de jours du mois. C'est la correction qui rend les diagrammes ombrothermiques justes.</p>
          <p class="small muted">Les fichiers versionnés sont déjà convertis en mm/mois
          (migration effectuée par <code>scripts/migrate_precip.py</code>).</p>
        </div>
        <div class="card">
          <h3>Premiers pas en classe</h3>
          <ul class="small">
            <li>Ouvrez <strong>Activités</strong> puis une fiche : les étapes s'affichent une par une.</li>
            <li>Saisissez le code enseignant pour afficher les corrigés (et seulement à ce moment-là).</li>
            <li>Utilisez <strong>Imprimer la fiche</strong> pour la version papier sans corrigé.</li>
            <li>Dans l'<strong>Explorateur</strong>, le bouton « Requêter le CDS » déclenche une vraie
              requête : faites-la lancer par un élève pour montrer le trajet de la donnée.</li>
            <li>Sur les <strong>Cartes</strong>, les images statiques s'affichent instantanément ;
              le téléchargement en direct sert à comparer un mois libre.</li>
          </ul>
        </div>
      </div>

      <div class="card">
        <h3>Crédits</h3>
        <p class="small">${esc(cfg.attribution)}</p>
        <p class="small muted">${esc(cfg.citation)}</p>
        <p class="small muted">Licence : ${esc(cfg.licence)} — côtes Natural Earth (domaine public) — graphiques Plotly (MIT).</p>
      </div>
    `;

    el("cds-test") && el("cds-test").addEventListener("click", () => runTest(false));
    el("cds-deep") && el("cds-deep").addEventListener("click", () => runTest(true));
    bindTeacherBox(main, () => router());

    async function runTest(deep) {
      const out = el("cds-out");
      const btn = deep ? el("cds-deep") : el("cds-test");
      btn.disabled = true;
      html(out, '<div class="loading-bar"></div><p class="muted">Test en cours…</p>');
      try {
        const res = await api("api/cds/test", { method: "POST", body: { deep } });
        html(out, reportMarkup(res.report));
        state.config.cds = res.config;
      } catch (err) {
        html(out, '<div class="callout callout-warn">' + esc(err.message) + "</div>");
      } finally {
        btn.disabled = false;
      }
    }
  }

  /* ============================================================== Démarrage */

  async function boot() {
    window.addEventListener("hashchange", router);
    window.addEventListener("resize", () => Charts.resizeAll());

    const toggle = el("nav-toggle");
    toggle.addEventListener("click", () => {
      const nav = el("nav");
      const open = nav.classList.toggle("open");
      toggle.setAttribute("aria-expanded", String(open));
    });

    document.addEventListener("keydown", (e) => {
      if (e.target.matches("input, select, textarea")) return;
      if (e.key === "e" || e.key === "E") navigate("/explorateur");
      if (e.key === "a" || e.key === "A") navigate("/activites");
      if (e.key === "c" || e.key === "C") navigate("/cartes");
    });

    try {
      await ensureData();
      if (state.config.attribution) {
        const f = el("footer-attribution");
        if (f) f.textContent = state.config.attribution;
      }
    } catch (err) {
      console.error(err);
      html("main", '<div class="card"><div class="callout callout-warn"><h4>API indisponible</h4><p>' +
        esc(err.message) + '</p><p class="small">Lancez <code>python run_local.py</code> puis ouvrez ' +
        '<code>http://127.0.0.1:8000</code>.</p></div></div>');
      return;
    }
    await router();
  }

  document.addEventListener("DOMContentLoaded", boot);
})();
