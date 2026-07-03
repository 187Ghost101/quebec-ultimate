// OSIN CHAIN QUEBEC ULTIMATE — Footprint Frontend
// Leaflet map + animated timeline + movement polyline + heatmap
const API = '/api/v1';
const WS_URL = (location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host;

const STATE = {
  sessionId: null,
  ws: null,
  map: null,
  markerLayer: null,
  pathLayer: null,
  heatLayer: null,
  trail: [],
  segments: [],
  uniqueLocations: [],
  anomalies: [],
  snapshots: [],
  snapshotsCount: 0,
  layers: { markers: true, path: true, heatmap: true },
  timeline: { playing: false, idx: 0, interval: null, speed: 1800 },
  currentSnapshotId: null,
  initialCenter: [45.5017, -73.5673],
  initialZoom: 4,
};

const $ = (s) => document.querySelector(s);

const formatTs = (ts) => {
  if (!ts) return '';
  if (typeof ts === 'string') return ts;
  if (typeof ts === 'number') {
    const d = new Date(ts * 1000);
    return d.toISOString();
  }
  return String(ts);
};


const $$ = (s) => document.querySelectorAll(s);
const esc = (s) => String(s || '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

// ─── Map setup ───
function initMap() {
  STATE.map = L.map('map', {
    center: STATE.initialCenter,
    zoom: STATE.initialZoom,
    worldCopyJump: true,
    preferCanvas: true,
    zoomControl: true,
  });

  // Dark tile layer
  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    attribution: '© OSIN CHAIN QUEBEC ULTIMATE · © OpenStreetMap · © CARTO',
    subdomains: 'abcd',
    maxZoom: 19,
  }).addTo(STATE.map);

  STATE.markerLayer = L.layerGroup().addTo(STATE.map);
  STATE.pathLayer = L.layerGroup().addTo(STATE.map);
  STATE.heatLayer = L.layerGroup().addTo(STATE.map);
}

function clearLayers() {
  if (STATE.markerLayer) STATE.markerLayer.clearLayers();
  if (STATE.pathLayer) STATE.pathLayer.clearLayers();
  if (STATE.heatLayer) STATE.heatLayer.clearLayers();
}

// ─── Render full footprint ───
async function loadFootprint(sessionId) {
  STATE.sessionId = sessionId;
  $('#sess-id').textContent = sessionId;
  $('#status-text').textContent = 'Chargement du footprint...';

  try {
    const r = await fetch(`${API}/footprint/${sessionId}/geo`);
    const d = await r.json();
    STATE.trail = d.trail || [];
    STATE.segments = d.segments || [];
    STATE.uniqueLocations = d.unique_locations || [];

    const ar = await fetch(`${API}/footprint/${sessionId}/movement`);
    const ad = await ar.json();
    STATE.anomalies = ad.anomalies || [];

    const sr = await fetch(`${API}/footprint/${sessionId}/timeline`);
    const sd = await sr.json();
    STATE.snapshots = sd.snapshots || [];
    STATE.snapshotsCount = STATE.snapshots.length;

    renderAll();
    connectWS(sessionId);
    renderSidePanel();
  } catch (e) {
    console.error(e);
    $('#status-text').textContent = `Erreur: ${e.message}`;
  }
}

function renderAll() {
  clearLayers();
  renderMarkers();
  renderPath();
  renderHeatmap();
  fitBoundsToTrail();
  $('#status-text').textContent = `${STATE.trail.length} positions · ${STATE.segments.length} mouvements · ${STATE.uniqueLocations.length} lieux uniques`;
}

function renderMarkers() {
  if (!STATE.layers.markers || !STATE.trail.length) return;
  STATE.trail.forEach((p, i) => {
    const isLast = i === STATE.trail.length - 1;
    const color = isLast ? '#00ff88' :
                  p.confidence > 0.9 ? '#4ecdc4' :
                  p.confidence > 0.7 ? '#ffd60a' : '#ff6b6b';
    const icon = L.divIcon({
      html: `<div style="width:14px;height:14px;border-radius:50%;background:${color};border:3px solid #050810;box-shadow:0 0 10px ${color}88;"></div>`,
      iconSize: [14, 14],
      iconAnchor: [7, 7],
      className: '',
    });
    const marker = L.marker([p.lat, p.lon], { icon })
      .bindPopup(`
        <div style="font-family:'Inter',sans-serif;min-width:200px;">
          <div style="color:#4ecdc4;font-size:11px;text-transform:uppercase;letter-spacing:1px;">${esc(p.type || '?')}</div>
          <div style="font-size:14px;font-weight:600;margin-top:2px;color:#e8edf5;">${esc(p.value || '?')}</div>
          <div style="margin-top:6px;font-size:10px;color:#94a3b8;font-family:monospace;">${esc(formatTs(p.timestamp))}</div>
          <div style="margin-top:4px;font-size:10px;color:#94a3b8;">Source: ${esc(p.source || '?')}</div>
          <div style="margin-top:4px;font-size:10px;color:#94a3b8;">Confiance: ${Math.round((p.confidence || 0) * 100)}%</div>
          ${isLast ? '<div style="margin-top:6px;color:#00ff88;font-size:10px;font-weight:600;">● DERNIÈRE POSITION</div>' : ''}
        </div>
      `);
    STATE.markerLayer.addLayer(marker);
  });
}

function renderPath() {
  if (!STATE.layers.path || STATE.trail.length < 2) return;
  const coords = STATE.trail.map(p => [p.lat, p.lon]);

  // Full trajectory polyline
  L.polyline(coords, {
    color: '#4ecdc4',
    weight: 2,
    opacity: 0.4,
    dashArray: '5, 8',
  }).addTo(STATE.pathLayer);

  // Segment-by-segment with color based on speed category
  const colors = {
    stationary: '#94a3b8', walking: '#4ecdc4', city_drive: '#ffd60a',
    highway: '#ff8c00', air_travel: '#c77dff', impossible: '#ff003c',
  };
  STATE.segments.forEach((s, i) => {
    const c = colors[s.speed_category] || '#4ecdc4';
    const from = [s.from.lat, s.from.lon];
    const to = [s.to.lat, s.to.lon];
    L.polyline([from, to], {
      color: c,
      weight: 4,
      opacity: 0.85,
    }).bindPopup(`
      <div style="font-family:'Inter',sans-serif;min-width:220px;">
        <div style="color:#ffd60a;font-size:11px;font-weight:600;">${esc(s.from.value || s.from.type)} → ${esc(s.to.value || s.to.type)}</div>
        <div style="margin-top:6px;font-size:11px;">Distance: <b style="color:#ffd60a;">${s.distance_km} km</b></div>
        <div style="margin-top:2px;font-size:11px;">Direction: <b>${s.bearing_compass} (${s.bearing_deg}°)</b></div>
        <div style="margin-top:2px;font-size:11px;">Vitesse: <b>${s.speed_kmh ? s.speed_kmh + ' km/h' : 'N/A'}</b></div>
        <div style="margin-top:2px;font-size:10px;color:#94a3b8;">Catégorie: ${esc(s.speed_category)}</div>
        ${s.duration_seconds ? `<div style="margin-top:2px;font-size:10px;color:#94a3b8;">Durée: ${s.duration_seconds}s</div>` : ''}
      </div>
    `).addTo(STATE.pathLayer);

    // Animated arrow marker at midpoint
    const midLat = (s.from.lat + s.to.lat) / 2;
    const midLon = (s.from.lon + s.to.lon) / 2;
    const arrowIcon = L.divIcon({
      html: `<div style="transform:rotate(${s.bearing_deg}deg);color:${c};font-size:20px;text-shadow:0 0 4px #050810;">▲</div>`,
      iconSize: [20, 20],
      iconAnchor: [10, 10],
      className: '',
    });
    L.marker([midLat, midLon], { icon: arrowIcon, interactive: false })
      .addTo(STATE.pathLayer);
  });
}

function renderHeatmap() {
  if (!STATE.layers.heatmap || STATE.trail.length === 0) return;
  // Use Leaflet.heat plugin
  const heatPoints = STATE.trail.map(p => [p.lat, p.lon, p.confidence || 0.5]);
  if (typeof L.heatLayer === 'function') {
    const heat = L.heatLayer(heatPoints, {
      radius: 30, blur: 25, maxZoom: 12,
      gradient: { 0.2: '#4ecdc4', 0.5: '#ffd60a', 0.8: '#ff6b6b' },
    });
    STATE.heatLayer.addLayer(heat);
  }
}

function fitBoundsToTrail() {
  if (STATE.trail.length === 0) return;
  const bounds = L.latLngBounds(STATE.trail.map(p => [p.lat, p.lon]));
  STATE.map.fitBounds(bounds, { padding: [50, 50], maxZoom: 8 });
}

function renderSidePanel() {
  const body = $('#panel-body');
  if (STATE.trail.length === 0) {
    body.innerHTML = `
      <div class="empty-state">
        <div class="icon">📍</div>
        <p>Aucun point géo dans cette session</p>
        <p style="margin-top:8px;">Les entités géographiques apparaîtront ici une fois la cascade lancée.</p>
      </div>`;
    return;
  }

  const totalDist = STATE.segments.reduce((s, x) => s + (x.distance_km || 0), 0);
  const avgSpeed = STATE.segments.filter(s => s.speed_kmh).reduce((acc, s, _, arr) => acc + s.speed_kmh / arr.length, 0);

  body.innerHTML = `
    <div class="stat-grid">
      <div class="stat-card">
        <div class="stat-label">Snapshots</div>
        <div class="stat-value">${STATE.snapshotsCount}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Positions</div>
        <div class="stat-value">${STATE.trail.length}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Lieux uniques</div>
        <div class="stat-value">${STATE.uniqueLocations.length}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Distance totale</div>
        <div class="stat-value">${totalDist.toFixed(0)}<span class="stat-unit">km</span></div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Vitesse moy.</div>
        <div class="stat-value">${avgSpeed ? avgSpeed.toFixed(0) : '—'}<span class="stat-unit">km/h</span></div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Mouvements</div>
        <div class="stat-value">${STATE.segments.length}</div>
      </div>
    </div>

    ${STATE.anomalies.length ? `
      <div class="section-title">⚠ Anomalies (${STATE.anomalies.length})</div>
      ${STATE.anomalies.map(a => `
        <div class="anomaly ${a.severity}">
          <div class="anomaly-title">${esc(a.type.replace(/_/g, ' '))}</div>
          <div class="anomaly-desc">${esc(a.description)}</div>
          ${a.implication ? `<div style="margin-top:4px;font-size:10px;color:#64748b;">→ ${esc(a.implication)}</div>` : ''}
        </div>
      `).join('')}
    ` : ''}

    <div class="section-title">🛣 Segments de mouvement (${STATE.segments.length})</div>
    ${STATE.segments.length === 0 ? '<p style="font-size:11px;color:#64748b;">Aucun mouvement entre snapshots.</p>' : ''}
    ${STATE.segments.map((s, i) => `
      <div class="segment-item" data-seg-idx="${i}">
        <div class="seg-route">${esc((s.from.value || s.from.type || '?').toString().slice(0, 30))} → ${esc((s.to.value || s.to.type || '?').toString().slice(0, 30))}</div>
        <div class="seg-meta">
          <span class="seg-distance">${s.distance_km} km</span> ·
          bearing ${s.bearing_compass} (${s.bearing_deg}°) ·
          <span class="seg-speed ${s.speed_category}">${esc(s.speed_category)}</span>
          ${s.speed_kmh ? ` · ${s.speed_kmh} km/h` : ''}
        </div>
      </div>
    `).join('')}

    <div class="section-title">📍 Snapshots (${STATE.snapshotsCount})</div>
    ${STATE.snapshots.map((s, i) => `
      <div class="snap-item" data-snap-idx="${i}">
        <div class="snap-trigger">${esc(s.trigger || '?')}</div>
        <div class="snap-time">${esc(formatTs(s.timestamp).slice(11, 19))} · ${s.entity_count} entités · ${s.geo_count} geo</div>
      </div>
    `).join('')}
  `;

  // Bind click handlers
  body.querySelectorAll('.snap-item').forEach(el => {
    el.addEventListener('click', () => {
      const idx = parseInt(el.dataset.snapIdx, 10);
      pauseTimeline();
      STATE.timeline.idx = idx;
      STATE.currentSnapshotId = STATE.snapshots[idx].snapshot_id;
      $('#tl-scrubber').value = idx;
      renderSnapshotFocus(idx);
      body.querySelectorAll('.snap-item').forEach(x => x.classList.remove('active'));
      el.classList.add('active');
    });
  });
}

function renderSnapshotFocus(idx) {
  const snap = STATE.snapshots[idx];
  if (!snap) return;
  // Show entities with geo coords at this snapshot
  const pts = (snap.geo_points || []).map(p => [p.lat, p.lon]);
  if (pts.length === 0) return;
  const bounds = L.latLngBounds(pts);
  STATE.map.fitBounds(bounds, { padding: [60, 60], maxZoom: 10 });
  const elapsed = STATE.snapshots[0].timestamp_unix ? Math.round(snap.timestamp_unix - STATE.snapshots[0].timestamp_unix) : 0;
  $('#tl-time').textContent = `T+${elapsed}s · ${snap.trigger || ''}`;
}

// ─── Timeline animation ───
function playTimeline() {
  if (STATE.timeline.playing) return;
  if (STATE.snapshots.length === 0) {
    toast('Aucun snapshot à animer. Lance une recherche d\'abord.', 'warn');
    return;
  }
  STATE.timeline.playing = true;
  STATE.timeline.idx = 0;
  STATE.timeline.interval = setInterval(() => {
    if (STATE.timeline.idx >= STATE.snapshots.length) {
      pauseTimeline();
      return;
    }
    renderSnapshotFocus(STATE.timeline.idx);
    $('#tl-scrubber').value = STATE.timeline.idx;
    STATE.timeline.idx++;
  }, STATE.timeline.speed);
}

function pauseTimeline() {
  STATE.timeline.playing = false;
  if (STATE.timeline.interval) {
    clearInterval(STATE.timeline.interval);
    STATE.timeline.interval = null;
  }
}

function resetTimeline() {
  pauseTimeline();
  STATE.timeline.idx = 0;
  $('#tl-scrubber').value = 0;
  if (STATE.snapshots.length > 0) renderSnapshotFocus(0);
  renderAll();
}

// ─── Layer toggles ───
function bindLayerToggles() {
  $$('.layer-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const layer = btn.dataset.layer;
      STATE.layers[layer] = !STATE.layers[layer];
      btn.classList.toggle('active', STATE.layers[layer]);
      if (STATE.layers[layer]) {
        if (layer === 'markers' && STATE.markerLayer) STATE.map.addLayer(STATE.markerLayer);
        if (layer === 'path' && STATE.pathLayer) STATE.map.addLayer(STATE.pathLayer);
        if (layer === 'heatmap' && STATE.heatLayer) STATE.map.addLayer(STATE.heatLayer);
      } else {
        if (layer === 'markers' && STATE.markerLayer) STATE.map.removeLayer(STATE.markerLayer);
        if (layer === 'path' && STATE.pathLayer) STATE.map.removeLayer(STATE.pathLayer);
        if (layer === 'heatmap' && STATE.heatLayer) STATE.map.removeLayer(STATE.heatLayer);
      }
    });
  });
}

// ─── Scrubber ───
function bindScrubber() {
  $('#tl-scrubber').max = Math.max(0, STATE.snapshots.length - 1);
  $('#tl-scrubber').addEventListener('input', (e) => {
    pauseTimeline();
    const idx = parseInt(e.target.value, 10);
    if (STATE.snapshots[idx]) {
      STATE.timeline.idx = idx;
      renderSnapshotFocus(idx);
    }
  });
}

// ─── WebSocket (live updates) ───
function connectWS(sessionId) {
  if (STATE.ws) STATE.ws.close();
  try {
    STATE.ws = new WebSocket(`${WS_URL}/ws/${sessionId}`);
    STATE.ws.onopen = () => console.log('[WS] connected');
    STATE.ws.onclose = () => console.log('[WS] closed');
    STATE.ws.onmessage = (ev) => {
      try {
        const d = JSON.parse(ev.data);
        if (d.event === 'entity_discovered' && d.geo) {
          // New geo point discovered → refresh
          STATE.trail.push({
            lat: d.geo.lat, lon: d.geo.lon, type: d.entity.type,
            value: d.entity.value, source: d.geo.source || 'live',
            confidence: d.geo.confidence || 0.8,
            timestamp: d.timestamp || new Date().toISOString(),
          });
          renderAll();
          renderSidePanel();
          toast(`📍 Nouveau point: ${d.entity.value}`, 'success', 2000);
        } else if (d.event === 'pipeline_complete') {
          toast(`✓ Cascade complète · ${d.total_entities} entités`, 'success');
          // Reload full data
          setTimeout(() => loadFootprint(sessionId), 500);
        }
      } catch (e) { console.error(e); }
    };
  } catch (e) { console.error(e); }
}

// ─── Toast helper ───
function toast(msg, type = 'info', duration = 3000) {
  const t = document.createElement('div');
  t.className = `toast toast-${type}`;
  t.textContent = msg;
  t.style.cssText = 'position:fixed;bottom:80px;right:16px;background:#131a2e;border:1px solid #2a3550;border-left:3px solid #4ecdc4;padding:10px 14px;border-radius:6px;color:#e8edf5;font-size:12px;z-index:9999;max-width:300px;';
  document.body.appendChild(t);
  setTimeout(() => { t.style.opacity = '0'; t.style.transform = 'translateX(20px)'; }, duration - 200);
  setTimeout(() => t.remove(), duration);
}

// ─── Init ───
function getSessionFromUrl() {
  const params = new URLSearchParams(window.location.search);
  return params.get('session');
}

function init() {
  initMap();
  bindLayerToggles();

  $('#tl-play').addEventListener('click', playTimeline);
  $('#tl-pause').addEventListener('click', pauseTimeline);
  $('#tl-reset').addEventListener('click', resetTimeline);

  const sid = getSessionFromUrl() || localStorage.getItem('lastSessionId');
  if (sid) {
    localStorage.setItem('lastSessionId', sid);
    loadFootprint(sid);
  }
}

document.addEventListener('DOMContentLoaded', init);