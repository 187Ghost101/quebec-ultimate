/* OSIN CHAIN QUEBEC ULTIMATE — Footprint Visualizer
 * Ghost1o1 — Leaflet map + timeline animation + movement segments
 *
 * Reads session_id from URL (?session=xxx) or localStorage.
 * Fetches geo trail, timeline snapshots, and movement analysis.
 * Animates entity discoveries and movement over time.
 */
(function () {
  "use strict";

  // ─── State ───
  const state = {
    sessionId: null,
    geoData: null,
    timelineData: null,
    movementData: null,
    map: null,
    markersLayer: null,
    pathLayer: null,
    heatLayer: null,
    snapshots: [],
    currentIdx: 0,
    playInterval: null,
    layers: { markers: true, path: true, heatmap: true },
  };

  // ─── Init ───
  function init() {
    const params = new URLSearchParams(window.location.search);
    state.sessionId = params.get("session") || localStorage.getItem("osin_last_session");

    if (!state.sessionId) {
      renderEmpty();
      return;
    }

    document.getElementById("sess-id").textContent = state.sessionId;
    setupMap();
    setupControls();
    loadAll().then(() => {
      if (state.snapshots.length === 0) {
        renderEmpty("Aucune donnée pour cette session.");
      }
    });
  }

  // ─── Map setup (Leaflet, dark tiles) ───
  function setupMap() {
    state.map = L.map("map", {
      center: [45.5017, -73.5673],
      zoom: 3,
      zoomControl: true,
      preferCanvas: true,
    });

    L.tileLayer(
      "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
      {
        attribution: "© CARTO © OSM",
        maxZoom: 18,
        subdomains: "abcd",
      }
    ).addTo(state.map);

    state.markersLayer = L.layerGroup().addTo(state.map);
    state.pathLayer = L.layerGroup().addTo(state.map);
    state.heatLayer = L.layerGroup().addTo(state.map);
  }

  // ─── Load all data ───
  async function loadAll() {
    setStatus("Chargement des données footprint…");
    try {
      const [geo, timeline, movement] = await Promise.all([
        fetchJson(`/api/v1/footprint/${state.sessionId}/geo`),
        fetchJson(`/api/v1/footprint/${state.sessionId}/timeline`),
        fetchJson(`/api/v1/footprint/${state.sessionId}/movement`),
      ]);
      state.geoData = geo;
      state.timelineData = timeline;
      state.movementData = movement;
      state.snapshots = (timeline && timeline.snapshots) || [];

      if (state.snapshots.length > 0) {
        setupScrubber();
        renderGeoTrail();
        renderMovementPanel();
        renderHeatmap();
        fitToTrail();
        setStatus(`✅ ${state.snapshots.length} snapshots chargés — ${geo.unique_locations ? geo.unique_locations.length : 0} lieux uniques`);
      } else {
        setStatus("⚠ Pas de snapshots — lance une cascade depuis la page d'accueil.");
      }
    } catch (err) {
      console.error(err);
      setStatus("❌ Erreur chargement: " + err.message);
    }
  }

  async function fetchJson(url) {
    const r = await fetch(url);
    if (!r.ok) throw new Error(url + " → " + r.status);
    return await r.json();
  }

  // ─── Render: trail ───
  function renderGeoTrail() {
    state.markersLayer.clearLayers();
    state.pathLayer.clearLayers();

    const trail = (state.geoData && state.geoData.trail) || [];
    if (trail.length === 0) return;

    const latlngs = [];
    trail.forEach((p, idx) => {
      const m = L.circleMarker([p.lat, p.lon], {
        radius: 7,
        fillColor: colorForType(p.type),
        color: "#050810",
        weight: 2,
        fillOpacity: 0.9,
      }).bindPopup(
        `<b>${escapeHtml(p.type || "?")}</b><br>` +
        `<code>${escapeHtml(String(p.value).slice(0, 60))}</code><br>` +
        `<small>Source: ${escapeHtml(p.source || "?")}<br>` +
        `Conf: ${(p.confidence * 100).toFixed(0)}%<br>` +
        `Step ${p.step} — ${escapeHtml(fmtTs(p.timestamp))}</small>`
      );
      m.addTo(state.markersLayer);
      latlngs.push([p.lat, p.lon]);
    });

    // Path
    if (latlngs.length > 1) {
      const poly = L.polyline(latlngs, {
        color: "#4ecdc4",
        weight: 3,
        opacity: 0.85,
        dashArray: "6 4",
      }).addTo(state.pathLayer);

      // Direction arrows
      for (let i = 1; i < latlngs.length; i++) {
        const mid = [
          (latlngs[i - 1][0] + latlngs[i][0]) / 2,
          (latlngs[i - 1][1] + latlngs[i][1]) / 2,
        ];
        const angle = Math.atan2(
          latlngs[i][1] - latlngs[i - 1][1],
          latlngs[i][0] - latlngs[i - 1][0]
        ) * (180 / Math.PI);
        const arrow = L.divIcon({
          html: `<div style="transform:rotate(${angle}deg);font-size:18px;color:#ffd60a;">➤</div>`,
          className: "arrow-icon",
          iconSize: [20, 20],
        });
        L.marker(mid, { icon: arrow }).addTo(state.pathLayer);
      }
    }
  }

  // ─── Heatmap ───
  function renderHeatmap() {
    state.heatLayer.clearLayers();
    const trail = (state.geoData && state.geoData.trail) || [];
    if (trail.length === 0) return;
    if (typeof L.heatLayer === "function") {
      const points = trail.map((p) => [p.lat, p.lon, p.confidence || 0.5]);
      L.heatLayer(points, {
        radius: 35,
        blur: 25,
        maxZoom: 12,
        gradient: { 0.0: "#1a2335", 0.4: "#4ecdc4", 0.7: "#ffd60a", 1.0: "#ff003c" },
      }).addTo(state.heatLayer);
    }
  }

  // ─── Fit map to trail ───
  function fitToTrail() {
    const trail = (state.geoData && state.geoData.trail) || [];
    if (trail.length === 0) return;
    const bounds = L.latLngBounds(trail.map((p) => [p.lat, p.lon]));
    state.map.fitBounds(bounds, { padding: [40, 40] });
  }

  // ─── Scrubber / playback ───
  function setupScrubber() {
    const scrubber = document.getElementById("tl-scrubber");
    const total = Math.max(1, state.snapshots.length - 1);
    scrubber.max = total;
    scrubber.value = state.currentIdx;

    scrubber.addEventListener("input", (e) => {
      const idx = parseInt(e.target.value, 10);
      jumpToSnapshot(idx);
    });

    document.getElementById("tl-play").addEventListener("click", play);
    document.getElementById("tl-pause").addEventListener("click", pause);
    document.getElementById("tl-reset").addEventListener("click", reset);
  }

  function jumpToSnapshot(idx) {
    state.currentIdx = idx;
    const snap = state.snapshots[idx];
    if (!snap) return;
    const ts = snap.timestamp_unix || 0;
    const start = state.snapshots[0].timestamp_unix || ts;
    const dt = Math.max(0, ts - start);
    document.getElementById("tl-time").textContent = `T+${dt.toFixed(1)}s`;
    document.getElementById("tl-scrubber").value = idx;

    // Highlight markers visible at this snapshot
    const visible = new Set((snap.entities || []).map((e) => e.id));
    state.markersLayer.eachLayer((m) => {
      const lat = m.getLatLng().lat;
      const lon = m.getLatLng().lng;
      const p = (state.geoData.trail || []).find(
        (g) => Math.abs(g.lat - lat) < 0.0001 && Math.abs(g.lon - lon) < 0.0001
      );
      if (!p) return;
      const visibleAt = p.timestamp_unix <= ts + 0.1;
      m.setStyle({
        radius: visibleAt ? 10 : 6,
        fillOpacity: visibleAt ? 1.0 : 0.3,
      });
    });

    renderSnapshotPanel(snap);
  }

  function play() {
    pause();
    state.playInterval = setInterval(() => {
      if (state.currentIdx >= state.snapshots.length - 1) {
        pause();
        return;
      }
      jumpToSnapshot(state.currentIdx + 1);
    }, 1200);
  }

  function pause() {
    if (state.playInterval) clearInterval(state.playInterval);
    state.playInterval = null;
  }

  function reset() {
    pause();
    jumpToSnapshot(0);
  }

  // ─── Right-side panel ───
  function renderMovementPanel() {
    const body = document.getElementById("panel-body");
    if (!body) return;
    const geo = state.geoData || {};
    const movement = state.movementData || {};

    const stats = `
      <div class="section-title">📈 STATISTIQUES</div>
      <div class="stat-grid">
        <div class="stat-card">
          <div class="stat-label">Snapshots</div>
          <div class="stat-value">${state.snapshots.length}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Distance totale</div>
          <div class="stat-value">${(geo.total_distance_km || 0).toFixed(1)}<span class="stat-unit">km</span></div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Lieux uniques</div>
          <div class="stat-value">${(geo.unique_locations || []).length}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Segments</div>
          <div class="stat-value">${(geo.segments || []).length}</div>
        </div>
      </div>
    `;

    let segments = "";
    if (geo.segments && geo.segments.length > 0) {
      segments = `<div class="section-title">🛣 SEGMENTS DE MOUVEMENT</div>`;
      geo.segments.forEach((s) => {
        const speedClass = s.speed_category || "stationary";
        segments += `
          <div class="segment-item">
            <div class="seg-route">
              ${escapeHtml(String(s.from.value || "?").slice(0, 30))} → ${escapeHtml(String(s.to.value || "?").slice(0, 30))}
            </div>
            <div class="seg-meta">
              <span class="seg-distance">${(s.distance_km || 0).toFixed(1)} km</span>
              · ${(s.bearing_compass || "?").slice(0, 3)}
              ${s.duration_seconds != null ? `· ${(s.duration_seconds / 60).toFixed(1)} min` : ""}
            </div>
            <div class="seg-meta">
              <span class="seg-speed ${speedClass}">${speedClass}</span>
              ${s.speed_kmh ? `· ${s.speed_kmh.toFixed(0)} km/h` : ""}
            </div>
          </div>
        `;
      });
    }

    let anomalies = "";
    if (movement.anomalies && movement.anomalies.length > 0) {
      anomalies = `<div class="section-title">⚠ ANOMALIES</div>`;
      movement.anomalies.forEach((a) => {
        anomalies += `
          <div class="anomaly ${a.severity || "low"}">
            <div class="anomaly-title">${escapeHtml(a.type || "?")}</div>
            <div class="anomaly-desc">${escapeHtml(a.description || "")}<br>
            <em>${escapeHtml(a.implication || "")}</em></div>
          </div>
        `;
      });
    }

    let trajectory = "";
    if (movement.geo_trajectory && movement.geo_trajectory.length > 0) {
      trajectory = `<div class="section-title">🛰 TRAJECTOIRE GÉO</div>`;
      movement.geo_trajectory.forEach((t) => {
        const changes = Object.entries(t.changes || {})
          .map(([k, v]) => `<code>${escapeHtml(k)}: ${escapeHtml(String(v.from))} → ${escapeHtml(String(v.to))}</code>`)
          .join("<br>");
        trajectory += `
          <div class="segment-item">
            <div class="seg-route">Step ${t.step} — ${escapeHtml(t.trigger || "")}</div>
            <div class="seg-meta">${changes}</div>
          </div>
        `;
      });
    }

    let snapshotsList = "";
    if (state.snapshots.length > 0) {
      snapshotsList = `<div class="section-title">📸 SNAPSHOTS</div>`;
      state.snapshots.forEach((s, idx) => {
        snapshotsList += `
          <div class="snap-item" data-idx="${idx}">
            <div class="snap-trigger">${escapeHtml(s.trigger || "?")}</div>
            <div class="snap-time">${escapeHtml(fmtTs(s.timestamp).slice(11, 19))} UTC</div>
            <div class="snap-stats">
              ${s.entity_count || 0} entités · ${s.relationship_count || 0} relations · ${s.geo_count || 0} géo
            </div>
          </div>
        `;
      });
    }

    body.innerHTML = stats + segments + anomalies + trajectory + snapshotsList;

    // Wire snapshot clicks
    body.querySelectorAll(".snap-item").forEach((el) => {
      el.addEventListener("click", () => {
        const idx = parseInt(el.dataset.idx, 10);
        jumpToSnapshot(idx);
      });
    });
  }

  function renderSnapshotPanel(snap) {
    document.querySelectorAll(".snap-item").forEach((el) => {
      el.classList.toggle("active", parseInt(el.dataset.idx, 10) === state.currentIdx);
    });
  }

  // ─── Controls ───
  function setupControls() {
    document.querySelectorAll(".layer-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        const layer = btn.dataset.layer;
        btn.classList.toggle("active");
        state.layers[layer] = btn.classList.contains("active");
        if (layer === "markers" && state.markersLayer) {
          if (state.layers.markers) state.markersLayer.addTo(state.map);
          else state.map.removeLayer(state.markersLayer);
        }
        if (layer === "path" && state.pathLayer) {
          if (state.layers.path) state.pathLayer.addTo(state.map);
          else state.map.removeLayer(state.pathLayer);
        }
        if (layer === "heatmap" && state.heatLayer) {
          if (state.layers.heatmap) state.heatLayer.addTo(state.map);
          else state.map.removeLayer(state.heatLayer);
        }
      });
    });
  }

  // ─── Empty state ───
  function renderEmpty(msg) {
    const body = document.getElementById("panel-body");
    if (body) {
      body.innerHTML = `
        <div class="empty-state">
          <div class="icon">🏴‍☠️</div>
          <p>${escapeHtml(msg || "Aucune session active")}</p>
          <p style="margin-top:8px;font-size:11px;">Lancement une cascade depuis <a href="/" style="color:#4ecdc4;">la page d'accueil</a>, puis revenez ici pour visualiser le footprint + mouvement.</p>
        </div>
      `;
    }
    setStatus("En attente de session — ?session=xxx dans l'URL");
  }

  function setStatus(text) {
    const el = document.getElementById("status-text");
    if (el) el.textContent = text;
  }

  // ─── Utils ───
  function fmtTs(ts) {
    if (ts == null) return "";
    if (typeof ts === "string") return ts;
    if (typeof ts === "number") {
      try { return new Date(ts * 1000).toISOString(); } catch (e) { return String(ts); }
    }
    return String(ts);
  }
  function colorForType(t) {
    const map = {
      ip: "#4ecdc4", city: "#ffd60a", country: "#c77dff",
      gps: "#ff8c00", asn: "#9d4edd", carrier: "#ff003c",
      timezone: "#94a3b8", address: "#00ff88", postal_code: "#6ee0d8",
    };
    return map[t] || "#4ecdc4";
  }

  function escapeHtml(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  // ─── Boot ───
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();