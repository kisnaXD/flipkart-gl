/**
 * Gridlock — shared data layer + page binders for Stitch UI
 */
const SCENARIO_SHORT = ["Cricket Match", "ORR Metro", "Procession", "VIP Movement", "Flash Cluster"];

window.GRIDLOCK = window.GRIDLOCK || {};

const TIER_CLASS = {
  Critical: "text-[#d8b4fe] border-[#d8b4fe]/50 bg-[#d8b4fe]/20",
  High: "text-[#fca5a5] border-[#fca5a5]/50 bg-[#fca5a5]/20",
  Medium: "text-tertiary border-tertiary/50 bg-tertiary/20",
  Low: "text-secondary border-secondary/50 bg-secondary/20",
};

const TIER_DOT = {
  Critical: "bg-[#d8b4fe]",
  High: "bg-[#fca5a5]",
  Medium: "bg-tertiary",
  Low: "bg-secondary",
};

const CAUSE_LABEL = {
  public_event: "Public Event",
  construction: "Construction",
  procession: "Procession",
  protest: "Protest",
  vip_movement: "VIP Movement",
  congestion: "Congestion",
};

let scenarios = [];
let historicalEvents = [];
let activeIndex = 0;
let mapInstance = null;
let mapLayers = null;

function createMapLayers() {
  if (typeof L === "undefined") return null;
  return {
    historical: L.layerGroup(),
    scenario: L.layerGroup(),
    barricades: L.layerGroup(),
    routes: L.layerGroup(),
    zone: null,
  };
}

async function loadData() {
  const [sRes, mRes, metricsRes, learningRes] = await Promise.all([
    fetch("/api/scenarios/full"),
    fetch("/api/events/map-data"),
    fetch("/api/analytics/summary").catch(() => null),
    fetch("/api/learning/summary").catch(() => null),
  ]);
  if (!sRes.ok) throw new Error("Failed to load scenarios");
  scenarios = await sRes.json();
  historicalEvents = mRes.ok ? (await mRes.json()).events : [];
  window.GRIDLOCK.metrics = metricsRes?.ok ? await metricsRes.json() : null;
  window.GRIDLOCK.learning = learningRes?.ok ? await learningRes.json() : null;
  window.GRIDLOCK.scenarios = scenarios;
  window.GRIDLOCK.activeIndex = activeIndex;
}

function setActiveIndex(i) {
  activeIndex = i;
  window.GRIDLOCK.activeIndex = i;
  localStorage.setItem("gridlock_scenario_idx", String(i));
}

function getSavedIndex() {
  const v = localStorage.getItem("gridlock_scenario_idx");
  return v ? Math.min(parseInt(v, 10), scenarios.length - 1) : 0;
}

function fmtCause(c) {
  return CAUSE_LABEL[c] || c.replaceAll("_", " ");
}

function tierBadgeHtml(tier) {
  const cls = TIER_CLASS[tier] || TIER_CLASS.Medium;
  return `<span class="${cls} border px-3 py-1 rounded-full font-label-md text-label-md flex items-center gap-1.5"><span class="w-1.5 h-1.5 rounded-full ${TIER_DOT[tier] || TIER_DOT.Medium}"></span>${tier.toUpperCase()}</span>`;
}

function bindCommandPage() {
  const list = document.getElementById("gl-scenario-list");
  if (!list) return;

  list.innerHTML = "";
  scenarios.forEach((s, i) => {
    const tier = s.analysis.impact_tier;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = i === activeIndex
      ? "flex items-center justify-between p-3 rounded-lg bg-primary-container/20 border border-primary/50 text-primary transition-all glow-active w-full text-left"
      : "flex items-center justify-between p-3 rounded-lg hover:bg-white/5 transition-all group border border-transparent hover:border-white/10 w-full text-left";
    btn.innerHTML = `<div class="flex items-center gap-3"><span class="w-2 h-2 rounded-full ${TIER_DOT[tier] || "bg-secondary"}"></span><span class="font-label-md text-label-md ${i === activeIndex ? "" : "text-on-surface-variant group-hover:text-on-surface"}">${SCENARIO_SHORT[i] || s.name.split("—")[0].trim()}</span></div>${i === activeIndex ? '<span class="material-symbols-outlined text-sm">chevron_right</span>' : ""}`;
    btn.onclick = () => { setActiveIndex(i); bindCommandPage(); bindCommandSummary(); initCommandMiniMap(); };
    list.appendChild(btn);
  });
  bindCommandSummary();
  initCommandMiniMap();

  const openMap = document.getElementById("gl-open-map");
  if (openMap) openMap.href = "/map";
  const fullPlan = document.getElementById("gl-full-plan");
  if (fullPlan) fullPlan.onclick = () => { window.location.href = "/map"; };
}

function bindCommandSummary() {
  const s = scenarios[activeIndex];
  if (!s) return;
  const a = s.analysis;
  const d = a.diversion;
  const r = a.resources;

  const set = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };

  set("gl-title", s.name.split("—")[0].trim());
  set("gl-subtitle", `${fmtCause(s.request.event_cause)} · ${s.request.corridor}`);
  set("gl-score", Math.round(a.impact_score));
  set("gl-duration", `${a.predicted_duration_hours}h`);
  set("gl-delay", `+${Math.round(d.estimated_delay_minutes)}m`);
  set("gl-peak", a.peak_window);
  set("gl-constables", r.constables);
  set("gl-barricades", r.barricades);

  const tierEl = document.getElementById("gl-tier-badge");
  if (tierEl) {
    tierEl.textContent = a.impact_tier.toUpperCase();
    const tierStyles = {
      Critical: "bg-[#d8b4fe]/20 text-[#d8b4fe] border border-[#d8b4fe]/50",
      High: "bg-[#fca5a5]/20 text-[#fca5a5] border border-[#fca5a5]/50",
      Medium: "bg-tertiary/20 text-tertiary border border-tertiary/50",
      Low: "bg-secondary/20 text-secondary border border-secondary/50",
    };
    tierEl.className = `${tierStyles[a.impact_tier] || tierStyles.Medium} px-3 py-1 rounded-full font-label-md text-label-md flex items-center gap-1.5`;
  }

  const routes = document.getElementById("gl-routes");
  if (routes) {
    routes.innerHTML = (d.alternate_routes || []).slice(0, 2).map((rt) =>
      `<div class="bg-surface-container-low border-l-2 border-secondary p-2.5 rounded-r-lg font-body-sm text-body-sm text-on-surface-variant flex items-start gap-2"><span class="material-symbols-outlined text-sm text-secondary mt-0.5">alt_route</span><span>${rt.instruction}</span></div>`
    ).join("") || '<div class="text-on-surface-variant font-body-sm">No diversion routes computed</div>';
  }

  const chip = document.getElementById("gl-map-chip");
  if (chip) chip.textContent = s.name.split("—")[0].trim();
}

function initCommandMiniMap() {
  const el = document.getElementById("gl-mini-map");
  if (!el || typeof L === "undefined") return;
  const s = scenarios[activeIndex];
  if (!s) return;
  const lat = s.request.latitude;
  const lon = s.request.longitude;
  if (el._map) { el._map.remove(); el._map = null; }
  const m = L.map(el, { zoomControl: false, attributionControl: false }).setView([lat, lon], 14);
  L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png").addTo(m);
  L.circleMarker([lat, lon], { radius: 10, color: "#adc6ff", fillColor: "#adc6ff", fillOpacity: 0.9, weight: 2 }).addTo(m);
  el._map = m;
  setTimeout(() => m.invalidateSize(), 150);
}

function bindMapPage() {
  const el = document.getElementById("gl-leaflet-map");
  if (!el || typeof L === "undefined") return;

  if (mapInstance) {
    mapInstance.remove();
    mapInstance = null;
  }
  mapLayers = createMapLayers();

  mapInstance = L.map(el, { zoomControl: true }).setView([12.9716, 77.5946], 11);
  L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
    attribution: "© OSM © CARTO", maxZoom: 19,
  }).addTo(mapInstance);

  mapLayers.historical.addTo(mapInstance);
  mapLayers.scenario.addTo(mapInstance);
  mapLayers.barricades.addTo(mapInstance);
  mapLayers.routes.addTo(mapInstance);

  renderHistoricalLayer();
  renderMapScenario(activeIndex);
  bindMapScenarioChips();
  bindMapDrawer();
  bindMapToggles();

  const banner = document.getElementById("gl-map-banner");
  if (banner && scenarios[activeIndex]) {
    banner.textContent = `Live Simulation: ${scenarios[activeIndex].name}`;
  }

  setTimeout(() => {
    mapInstance.invalidateSize();
    fitMapToScenario(activeIndex);
  }, 250);
}

function renderHistoricalLayer() {
  if (!mapLayers || !mapInstance) return;
  mapLayers.historical.clearLayers();
  const colors = { Low: "#00C851", Medium: "#FFBB33", High: "#FF4444", Critical: "#d8b4fe" };
  historicalEvents.forEach((evt) => {
    if (evt.lat == null || evt.lon == null) return;
    L.circleMarker([evt.lat, evt.lon], {
      radius: 6,
      color: colors[evt.tier] || "#64748b",
      fillColor: colors[evt.tier] || "#64748b",
      fillOpacity: 0.85,
      weight: 1,
      interactive: true,
    })
      .bindPopup(`<strong>${fmtCause(evt.cause)}</strong><br>${evt.corridor}<br>${evt.tier}`)
      .addTo(mapLayers.historical);
  });
}

function fitMapToScenario(index) {
  const item = scenarios[index];
  if (!item || !mapInstance) return;
  const req = item.request;
  const div = item.analysis.diversion;
  const snapped = div.snapped_event;
  const lat = snapped?.latitude ?? req.latitude;
  const lon = snapped?.longitude ?? req.longitude;
  const bounds = L.latLngBounds([[lat, lon]]);
  (div.barricade_points || []).forEach((pt) => bounds.extend([pt.latitude, pt.longitude]));
  (div.alternate_routes || []).forEach((route) => {
    (route.geometry || []).forEach((c) => bounds.extend([c[0], c[1]]));
  });
  mapInstance.fitBounds(bounds.pad(0.25), { padding: [100, 100], maxZoom: 14 });
}

function renderMapScenario(index) {
  setActiveIndex(index);
  const item = scenarios[index];
  if (!item || !mapInstance || !mapLayers) return;
  const req = item.request;
  const a = item.analysis;
  const div = a.diversion;
  const snapped = div.snapped_event;
  const lat = snapped?.latitude ?? req.latitude;
  const lon = snapped?.longitude ?? req.longitude;

  mapLayers.scenario.clearLayers();
  mapLayers.barricades.clearLayers();
  mapLayers.routes.clearLayers();
  if (mapLayers.zone) {
    mapInstance.removeLayer(mapLayers.zone);
    mapLayers.zone = null;
  }

  L.circleMarker([lat, lon], {
    radius: 12,
    color: "#ffffff",
    fillColor: "#33B5E5",
    fillOpacity: 0.95,
    weight: 3,
    interactive: true,
  })
    .bindPopup(`<strong>${item.name}</strong><br>Impact ${Math.round(a.impact_score)}/100 · ${a.impact_tier}`)
    .addTo(mapLayers.scenario);

  mapLayers.zone = L.circle([lat, lon], {
    radius: div.affected_radius_m,
    color: "#33B5E5",
    fillColor: "#33B5E5",
    fillOpacity: 0.08,
    weight: 2,
    dashArray: "6 6",
    interactive: false,
  }).addTo(mapInstance);

  (div.barricade_points || []).forEach((pt) => {
    L.marker([pt.latitude, pt.longitude], {
      icon: L.divIcon({
        className: "gl-map-marker barricade",
        html: "B",
        iconSize: [30, 30],
        iconAnchor: [15, 15],
      }),
      interactive: true,
    })
      .bindPopup(`<strong>Barricade ${pt.id}</strong><br>${pt.street_name || "Road"}${pt.network_distance_m ? `<br>${Math.round(pt.network_distance_m)}m from epicenter` : ""}`)
      .addTo(mapLayers.barricades);
  });

  (div.alternate_routes || []).forEach((route) => {
    const coords = (route.geometry || [[route.start.latitude, route.start.longitude], [route.end.latitude, route.end.longitude]]).map((c) => [c[0], c[1]]);
    L.polyline(coords, { color: "#33B5E5", weight: 5, opacity: 0.9 })
      .bindPopup(route.instruction)
      .addTo(mapLayers.routes);
  });

  fitMapToScenario(index);
  bindMapDrawer();
  bindMapScenarioChips();

  const banner = document.getElementById("gl-map-banner");
  if (banner) banner.textContent = `Live Simulation: ${item.name}`;
}

function bindMapScenarioChips() {
  const bar = document.getElementById("gl-scenario-chips-inner") || document.getElementById("gl-scenario-chips");
  if (!bar) return;
  bar.innerHTML = "";
  scenarios.forEach((s, i) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = i === activeIndex
      ? "px-4 py-1.5 rounded-full bg-primary-container text-on-primary-container font-mono-data text-sm border border-primary/30 transition-all"
      : "px-4 py-1.5 rounded-full bg-transparent hover:bg-surface-variant text-on-surface-variant hover:text-on-surface font-mono-data text-sm transition-all border border-transparent";
    btn.textContent = SCENARIO_SHORT[i] + (i === activeIndex ? " (Active)" : "");
    btn.onclick = () => renderMapScenario(i);
    bar.appendChild(btn);
  });
}

function bindMapDrawer() {
  const s = scenarios[activeIndex];
  if (!s) return;
  const a = s.analysis;
  const set = (id, html) => { const el = document.getElementById(id); if (el) el.innerHTML = html; };

  set("gl-drawer-title", s.name.split("—")[0].trim());
  set("gl-drawer-detail", `<div class="flex justify-between items-center mb-2"><span class="font-mono-data text-mono-data text-on-surface">${fmtCause(s.request.event_cause)}</span><span class="px-2 py-0.5 rounded text-[10px] bg-ops-red/20 text-ops-red border border-ops-red/30">${a.impact_tier}</span></div><p class="font-body-sm text-body-sm text-on-surface-variant">${a.resources.notes}</p>`);

  set("gl-drawer-routes", (a.diversion.alternate_routes || []).map((rt) =>
    `<div class="flex items-start gap-3 p-2 rounded hover:bg-white/5 border-l-2 border-transparent hover:border-ops-blue"><span class="material-symbols-outlined text-ops-blue text-sm mt-0.5">alt_route</span><div><div class="font-mono-data text-mono-data text-on-surface">${rt.route_id}: ${rt.instruction}</div></div></div>`
  ).join("") || '<p class="text-on-surface-variant font-body-sm">No diversion routes</p>');

  set("gl-drawer-hotspots", (a.hotspots_next_hour || []).map((h) => {
    const color = h.risk_score > 70 ? "ops-red" : h.risk_score > 40 ? "ops-amber" : "ops-green";
    return `<li class="flex items-center justify-between p-2 rounded hover:bg-white/5 border-b border-white/5 last:border-0"><div class="flex items-center gap-2"><div class="w-1.5 h-1.5 rounded-full bg-${color}"></div><span class="font-mono-data text-sm text-on-surface">${h.corridor}</span></div><span class="font-mono-data text-[10px] text-${color} bg-${color}/10 px-1.5 py-0.5 rounded">${h.risk_score}%</span></li>`;
  }).join("") || '<li class="text-on-surface-variant font-body-sm p-2">No hotspot forecast</li>');
}

function toggleLayer(layer, btnId) {
  if (!mapInstance || !layer) return;
  const btn = document.getElementById(btnId);
  const visible = mapInstance.hasLayer(layer);
  if (visible) {
    mapInstance.removeLayer(layer);
    btn?.classList.add("opacity-50");
  } else {
    layer.addTo(mapInstance);
    btn?.classList.remove("opacity-50");
  }
}

function bindMapToggles() {
  document.getElementById("gl-toggle-past").onclick = () => toggleLayer(mapLayers?.historical, "gl-toggle-past");
  document.getElementById("gl-toggle-barricades").onclick = () => toggleLayer(mapLayers?.barricades, "gl-toggle-barricades");
  document.getElementById("gl-toggle-routes").onclick = () => toggleLayer(mapLayers?.routes, "gl-toggle-routes");
}

function bindScenariosPage() {
  const list = document.getElementById("gl-scenario-cards");
  const detail = document.getElementById("gl-scenario-detail");
  if (!list) return;

  list.innerHTML = scenarios.map((s, i) => {
    const tier = s.analysis.impact_tier;
    const active = i === activeIndex ? "border-primary/30 bg-surface-container-high" : "border-outline-variant/30";
    return `<div class="bg-surface-container p-4 rounded-lg border ${active} cursor-pointer hover:bg-surface-container-high transition-colors" data-idx="${i}">
      <div class="flex items-center gap-2 mb-1"><span class="w-2 h-2 rounded-full ${TIER_DOT[tier]}"></span><span class="font-label-md text-label-md uppercase tracking-wider">${tier}</span></div>
      <h3 class="font-title-md text-title-md text-on-surface">${s.name}</h3>
      <p class="font-body-sm text-on-surface-variant mt-2">${fmtCause(s.request.event_cause)} · ${s.request.corridor}</p>
    </div>`;
  }).join("");

  list.querySelectorAll("[data-idx]").forEach((el) => {
    el.onclick = () => { setActiveIndex(parseInt(el.dataset.idx, 10)); bindScenariosPage(); };
  });

  if (detail && scenarios[activeIndex]) {
    const s = scenarios[activeIndex];
    const a = s.analysis;
    detail.innerHTML = `
      <h2 class="font-headline-md text-headline-md text-on-surface mb-2">${s.name}</h2>
      ${tierBadgeHtml(a.impact_tier)}
      <div class="grid grid-cols-2 gap-3 mt-6">
        <div class="bg-surface-container-high rounded-lg p-4 border border-outline-variant/30"><div class="font-label-md text-label-md text-outline mb-1">Impact Score</div><div class="font-mono-data text-3xl text-primary">${Math.round(a.impact_score)}</div></div>
        <div class="bg-surface-container-high rounded-lg p-4 border border-outline-variant/30"><div class="font-label-md text-label-md text-outline mb-1">Duration</div><div class="font-mono-data text-3xl text-secondary">${a.predicted_duration_hours}h</div></div>
        <div class="bg-surface-container-high rounded-lg p-4 border border-outline-variant/30"><div class="font-label-md text-label-md text-outline mb-1">Constables</div><div class="font-mono-data text-3xl text-on-surface">${a.resources.constables}</div></div>
        <div class="bg-surface-container-high rounded-lg p-4 border border-outline-variant/30"><div class="font-label-md text-label-md text-outline mb-1">Barricades</div><div class="font-mono-data text-3xl text-on-surface">${a.resources.barricades}</div></div>
      </div>
      <p class="font-body-sm text-on-surface-variant mt-6">${a.diversion.notes}</p>
      <a href="/map" class="inline-flex mt-6 items-center gap-2 bg-secondary-container text-on-secondary-container px-4 py-2 rounded-lg font-label-md">View on map <span class="material-symbols-outlined text-sm">arrow_forward</span></a>`;
  }
}

let hotspotsBound = false;

function bindHotspotsPage() {
  const slider = document.getElementById("gl-hour-slider");
  const hour = parseInt(slider?.value || "18", 10);
  fetch(`/api/hotspots?hour=${hour}&top_n=8`).then((r) => r.json()).then((data) => {
    const list = document.getElementById("gl-hotspot-list");
    if (!list) return;
    list.innerHTML = (data.hotspots || []).map((h) => {
      const pct = h.risk_score;
      const color = pct > 70 ? "error" : pct > 40 ? "tertiary" : "secondary";
      return `<tr class="data-row border-b border-[rgba(255,255,255,0.04)]"><td class="p-3 font-body-sm text-body-sm text-on-surface flex items-center gap-3"><div class="w-2 h-2 rounded-full bg-${color}"></div>${h.corridor}</td><td class="p-3 text-right"><span class="font-mono-data text-${color} font-bold">${pct}%</span></td><td class="p-3"><div class="w-full bg-surface-variant h-1.5 rounded-full overflow-hidden"><div class="bg-${color} h-full" style="width:${pct}%"></div></div></td><td class="p-3 text-right font-mono-data text-on-surface-variant">~${h.expected_events} events</td></tr>`;
    }).join("") || '<tr><td colspan="4" class="p-4 text-on-surface-variant">No hotspots for this hour</td></tr>';
    document.querySelectorAll("#gl-hour-label").forEach((el) => { el.textContent = `${hour}:00`; });
  });
  if (slider && !hotspotsBound) {
    slider.addEventListener("input", bindHotspotsPage);
    hotspotsBound = true;
  }
}

function bindAnalyticsPage() {
  const m = window.GRIDLOCK.metrics;
  if (!m) return;
  const set = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
  set("gl-total-events", m.total_events?.toLocaleString());
  set("gl-event-driven", m.event_driven_events?.toLocaleString());
  if (m.tier_accuracy != null) {
    const acc = document.getElementById("gl-tier-accuracy");
    if (acc) acc.innerHTML = `${Math.round(m.tier_accuracy * 100)}<span class="text-[32px] text-on-surface-variant">%</span>`;
  }
  set("gl-duration-mae", m.duration_mae_hours != null ? `${m.duration_mae_hours}` : "—");
}

function bindLearningPage() {
  const l = window.GRIDLOCK.learning;
  if (!l) return;
  const set = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
  set("gl-learning-records", l.records ?? 0);
  set("gl-learning-mae", l.duration_mae_hours != null ? `${l.duration_mae_hours}h` : "—");
  bindAnalyticsPage();
}

async function boot() {
  try {
    await loadData();
    activeIndex = Math.min(getSavedIndex(), scenarios.length - 1);
    const page = window.GRIDLOCK_PAGE || "command";
    if (page === "command") bindCommandPage();
    if (page === "map") bindMapPage();
    if (page === "scenarios") bindScenariosPage();
    if (page === "hotspots") bindHotspotsPage();
    if (page === "analytics") bindAnalyticsPage();
    if (page === "learning") bindLearningPage();
  } catch (e) {
    console.error(e);
    document.body.insertAdjacentHTML("afterbegin", `<div class="fixed top-20 left-1/2 -translate-x-1/2 z-[9999] bg-error-container text-on-error-container px-4 py-2 rounded-lg">${e.message}</div>`);
  }
}

document.addEventListener("DOMContentLoaded", boot);
