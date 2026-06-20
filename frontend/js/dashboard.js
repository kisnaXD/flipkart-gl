const TIER_COLORS = {
  Low: "#22c55e",
  Medium: "#f59e0b",
  High: "#ef4444",
  Critical: "#a855f7",
};

let map;
let layers = {
  historical: null,
  scenario: L.layerGroup(),
  zone: null,
  barricades: L.layerGroup(),
  routes: L.layerGroup(),
};
let scenarios = [];
let historicalEvents = [];
let activeIndex = 0;

const causeLabels = {
  public_event: "Public Event",
  construction: "Construction",
  procession: "Procession",
  protest: "Protest",
  vip_movement: "VIP Movement",
  congestion: "Congestion",
};

function tierClass(tier) {
  return `tier-badge tier-${tier}`;
}

function formatCause(cause) {
  return causeLabels[cause] || cause.replaceAll("_", " ");
}

function initMap() {
  map = L.map("map", { zoomControl: true }).setView([12.9716, 77.5946], 11);
  L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
    attribution: "&copy; OpenStreetMap &copy; CARTO",
    maxZoom: 19,
  }).addTo(map);

  layers.scenario.addTo(map);
  layers.barricades.addTo(map);
  layers.routes.addTo(map);
}

function renderHistorical() {
  if (layers.historical) {
    map.removeLayer(layers.historical);
  }
  layers.historical = L.layerGroup();
  historicalEvents.forEach((evt) => {
    const color = TIER_COLORS[evt.tier] || "#64748b";
    const marker = L.circleMarker([evt.lat, evt.lon], {
      radius: 5,
      color,
      fillColor: color,
      fillOpacity: 0.75,
      weight: 1,
      opacity: 0.9,
    });
    marker.bindPopup(`
      <div class="popup-title">Historical Event</div>
      <div class="popup-meta">
        <strong>Type:</strong> ${formatCause(evt.cause)}<br/>
        <strong>Corridor:</strong> ${evt.corridor}<br/>
        <strong>Impact tier:</strong> ${evt.tier}<br/>
        <strong>When:</strong> ${evt.when}<br/>
        <em>Past incident from Astram dataset — context for hotspot patterns.</em>
      </div>
    `);
    marker.addTo(layers.historical);
  });
  layers.historical.addTo(map);
}

function clearScenarioLayers() {
  layers.scenario.clearLayers();
  layers.barricades.clearLayers();
  layers.routes.clearLayers();
  if (layers.zone) {
    map.removeLayer(layers.zone);
    layers.zone = null;
  }
}

function renderScenario(index) {
  activeIndex = index;
  const item = scenarios[index];
  const req = item.request;
  const analysis = item.analysis;
  const div = analysis.diversion;
  const snapped = div.snapped_event;
  const eventLat = snapped ? snapped.latitude : req.latitude;
  const eventLon = snapped ? snapped.longitude : req.longitude;

  clearScenarioLayers();

  document.querySelectorAll(".scenario-card").forEach((el, i) => {
    el.classList.toggle("active", i === index);
  });

  document.getElementById("map-banner-text").textContent =
    `Viewing: ${item.name}. Star = event epicenter. Shaded circle = affected zone. Red markers = barricades. Blue lines = suggested diversions.`;

  document.getElementById("scenario-title").textContent = item.name;
  document.getElementById("scenario-subtitle").textContent =
    `${formatCause(req.event_cause)} on ${req.corridor} · ${req.event_type} event`;

  document.getElementById("impact-score").textContent = analysis.impact_score;
  document.getElementById("impact-tier").textContent = analysis.impact_tier;
  document.getElementById("impact-tier").className = tierClass(analysis.impact_tier);
  document.getElementById("duration").textContent = `${analysis.predicted_duration_hours}h`;
  document.getElementById("delay").textContent = `${div.estimated_delay_minutes} min`;
  document.getElementById("constables").textContent = analysis.resources.constables;
  document.getElementById("barricades").textContent = analysis.resources.barricades;
  document.getElementById("peak-window").textContent = analysis.peak_window;
  document.getElementById("resource-notes").textContent = analysis.resources.notes;
  document.getElementById("diversion-notes").textContent =
    (div.planner_mode === "osm"
      ? "✓ OpenStreetMap road network · "
      : div.planner_mode === "historical_proxy"
      ? "✓ Historical road locations · "
      : "⚠ ") + div.notes;

  const routeList = document.getElementById("route-list");
  routeList.innerHTML = "";
  div.alternate_routes.forEach((route) => {
    const el = document.createElement("div");
    el.className = "route-item";
    const len = route.length_m ? ` · ${Math.round(route.length_m)}m` : "";
    el.innerHTML = `<strong>${route.route_id}</strong> — ${route.instruction}${len}`;
    routeList.appendChild(el);
  });

  const hotspotList = document.getElementById("hotspot-list");
  hotspotList.innerHTML = "";
  analysis.hotspots_next_hour.forEach((h) => {
    const el = document.createElement("div");
    el.className = "hotspot-item";
    el.innerHTML = `<strong>${h.corridor}</strong> · risk ${h.risk_score}% · ~${h.expected_events} past incidents around ${h.hour_of_day}:00`;
    hotspotList.appendChild(el);
  });

  const star = L.marker([eventLat, eventLon], {
    icon: L.divIcon({
      className: "",
      html: `<div style="background:#38bdf8;width:18px;height:18px;border-radius:50%;border:3px solid white;box-shadow:0 0 0 4px rgba(56,189,248,.35)"></div>`,
      iconSize: [18, 18],
      iconAnchor: [9, 9],
    }),
  });
  const snapInfo = snapped
    ? `<br/>Snapped to road: <strong>${snapped.street_name}</strong>`
    : "";
  star.bindPopup(`
    <div class="popup-title">${item.name}</div>
    <div class="popup-meta">
      <strong>Event epicenter</strong> — congestion origin (snapped to nearest driveable road).${snapInfo}<br/>
      Impact: ${analysis.impact_score}/100 (${analysis.impact_tier})<br/>
      Deploy resources around this point.
    </div>
  `);
  star.addTo(layers.scenario);

  layers.zone = L.circle([eventLat, eventLon], {
    radius: div.affected_radius_m,
    color: "#38bdf8",
    fillColor: "#38bdf8",
    fillOpacity: 0.08,
    weight: 2,
    dashArray: "6 6",
  }).bindPopup(`
    <div class="popup-title">Affected Zone</div>
    <div class="popup-meta">
      Approximate ${Math.round(div.affected_radius_m)}m radius where traffic slows or stops.<br/>
      Size varies by event type and road closure status.
    </div>
  `);
  layers.zone.addTo(map);

  div.barricade_points.forEach((pt) => {
    const roadLabel = div.planner_mode === "historical_proxy"
      ? "Known road location from past Astram incidents"
      : "OpenStreetMap drive network";
    const marker = L.marker([pt.latitude, pt.longitude], {
      icon: L.divIcon({
        className: "",
        html: `<div style="background:#fb7185;color:white;font-size:10px;font-weight:700;width:22px;height:22px;border-radius:6px;display:grid;place-items:center;border:2px solid white;">B</div>`,
        iconSize: [22, 22],
        iconAnchor: [11, 11],
      }),
    });
    marker.bindPopup(`
      <div class="popup-title">Barricade ${pt.id}</div>
      <div class="popup-meta">
        <strong>Road:</strong> ${pt.street_name || "Unknown"}<br/>
        <strong>Distance:</strong> ${pt.network_distance_m ? Math.round(pt.network_distance_m) + "m along road" : "—"}<br/>
        Role: ${(pt.role || "control").replaceAll("_", " ")}<br/>
        Place personnel here — ${roadLabel}.
      </div>
    `);
    marker.addTo(layers.barricades);
  });

  div.alternate_routes.forEach((route) => {
    const coords = (route.geometry || [
      [route.start.latitude, route.start.longitude],
      [route.end.latitude, route.end.longitude],
    ]).map((c) => [c[0], c[1]]);

    const line = L.polyline(coords, {
      color: "#60a5fa",
      weight: 5,
      opacity: 0.9,
    });
    line.bindPopup(`
      <div class="popup-title">${route.route_id}</div>
      <div class="popup-meta">${route.instruction}<br/><em>Route follows actual road geometry from OpenStreetMap.</em></div>
    `);
    line.addTo(layers.routes);
  });

  map.flyTo([eventLat, eventLon], 14, { duration: 0.8 });
}

function bindLayerToggles() {
  document.getElementById("toggle-historical").addEventListener("click", (e) => {
    const btn = e.currentTarget;
    if (layers.historical && map.hasLayer(layers.historical)) {
      map.removeLayer(layers.historical);
      btn.classList.remove("active");
    } else if (layers.historical) {
      layers.historical.addTo(map);
      btn.classList.add("active");
    }
  });

  document.getElementById("toggle-scenario").addEventListener("click", (e) => {
    const btn = e.currentTarget;
    const group = [layers.scenario, layers.barricades, layers.routes, layers.zone];
    const visible = layers.scenario && map.hasLayer(layers.scenario);
    group.forEach((layer) => {
      if (!layer) return;
      if (visible) map.removeLayer(layer);
      else layer.addTo(map);
    });
    btn.classList.toggle("active", !visible);
  });
}

function renderScenarioCards() {
  const list = document.getElementById("scenario-list");
  list.innerHTML = "";
  scenarios.forEach((item, index) => {
    const btn = document.createElement("button");
    btn.className = "scenario-card" + (index === 0 ? " active" : "");
    btn.innerHTML = `
      <div class="title">${item.name}</div>
      <div class="meta">${formatCause(item.request.event_cause)} · ${item.analysis.impact_tier} impact · ${item.request.corridor}</div>
    `;
    btn.addEventListener("click", () => renderScenario(index));
    list.appendChild(btn);
  });
}

async function boot() {
  try {
    initMap();
    document.getElementById("map-banner-text").textContent = "Loading scenarios and map data…";
    const [scenarioRes, mapRes] = await Promise.all([
      fetch("/api/scenarios/full"),
      fetch("/api/events/map-data"),
    ]);
    if (!scenarioRes.ok) throw new Error(`Scenarios API failed (${scenarioRes.status})`);
    if (!mapRes.ok) throw new Error(`Map data API failed (${mapRes.status})`);
    scenarios = await scenarioRes.json();
    const mapData = await mapRes.json();
    historicalEvents = mapData.events || [];
    if (!scenarios.length) throw new Error("No scenarios returned from server");

    renderScenarioCards();
    renderHistorical();
    renderScenario(0);
    bindLayerToggles();
  } catch (err) {
    console.error(err);
    document.getElementById("map-banner-text").textContent =
      `Failed to load dashboard: ${err.message}. Run: python -m src.pipeline then restart the server.`;
  }
}

document.addEventListener("DOMContentLoaded", boot);
