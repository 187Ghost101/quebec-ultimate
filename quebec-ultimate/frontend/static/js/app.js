/* OSIN CHAIN QUEBEC ULTIMATE - Unified View JS - Ghost1o1 */

const TYPE_COLORS = {
  phone:'#10b981', email:'#4ecdc4', username:'#a78bfa', domain:'#ffd60a',
  subdomain:'#f59e0b', ip:'#ef4444', url:'#06b6d4', social_profile:'#ec4899',
  github_profile:'#a78bfa', image:'#f97316', name:'#84cc16', alias:'#6366f1',
  city:'#22d3ee', country:'#0ea5e9', carrier:'#14b8a6', isp:'#dc2626',
  asn:'#9333ea', txt_record:'#a16207', mx_record:'#ca8a04', ns_record:'#854d0e',
  spf_record:'#65a30d', rdap_handle:'#d97706', gps:'#22c55e', timezone:'#0891b2',
  phone_type:'#0d9488', company:'#7c3aed', file:'#71717a', hash:'#737373',
  breach:'#dc2626', credential:'#fb7185', leak:'#e11d48', paste:'#be123c',
  document:'#a8a29e', ocr_text:'#d6d3d1', metadata:'#a1a1aa',
  bitcoin_address:'#f7931a', ethereum_address:'#627eea', darkweb_url:'#000000',
  forum_post:'#831843', market:'#9d174d', tor_relay:'#155e75',
  face:'#f472b6', avatar:'#fb923c', exif:'#facc15', reverse_image:'#fde047',
  face_cluster:'#ec4899', camera:'#7c3aed'
};
const TYPE_SIZES = {
  phone:32, email:30, username:28, domain:24, ip:28, url:20,
  social_profile:26, github_profile:28, image:22, name:22, city:18,
  country:20, carrier:18, isp:18, asn:18, gps:18, file:18,
  breach:24, credential:22, document:20, darkweb_url:20,
  face:22, avatar:18, face_cluster:26, gps:20, camera:18
};

let cy = null;
let map = null;
let mapMarkers = [];
let seenNodes = new Set();
let seenEdges = new Set();
let currentSession = null;
let allEntities = [];
let allRelationships = [];
let currentLayout = 'cose';
let modulesData = [];
let logEntries = [];

document.addEventListener('DOMContentLoaded', async () => {
  initGraph();
  initMap();
  setupUI();
  setupUpload();
  await loadModules();
  pollActivity();
  buildLegend();
});

function initGraph() {
  cy = cytoscape({
    container: document.getElementById('cy-graph'),
    elements: [],
    style: [
      { selector: 'node', style: {
          'background-color': (ele) => TYPE_COLORS[ele.data('type')] || '#64748b',
          'background-opacity': 0.92,
          'label': (ele) => {
            const v = String(ele.data('value') || '');
            return v.length > 28 ? v.slice(0, 26) + '…' : v;
          },
          'color': '#fff',
          'font-size': 9,
          'font-weight': 600,
          'text-valign': 'center',
          'text-halign': 'center',
          'text-wrap': 'wrap',
          'text-max-width': '120px',
          'width': (ele) => TYPE_SIZES[ele.data('type')] || 18,
          'height': (ele) => TYPE_SIZES[ele.data('type')] || 18,
          'border-width': 2,
          'border-color': '#04060d',
          'text-outline-color': '#04060d',
          'text-outline-width': 2,
      }},
      { selector: 'node.root', style: {
          'border-width': 5,
          'border-color': '#ffd60a',
          'background-blacken': -0.3,
          'text-outline-color': '#000',
      }},
      { selector: 'node.highlight', style: {
          'border-width': 6,
          'border-color': '#ff6b6b',
          'background-blacken': -0.4,
      }},
      { selector: 'node.flash', style: {
          'border-color': '#ffd60a',
          'border-width': 6,
          'background-blacken': -0.5,
      }},
      { selector: 'edge', style: {
          'curve-style': 'bezier',
          'target-arrow-shape': 'triangle',
          'line-color': (ele) => {
            const w = ele.data('weight') || 1;
            return w > 0.9 ? '#ff6b6b' : w > 0.7 ? '#ffd60a' : '#4ecdc4';
          },
          'target-arrow-color': (ele) => {
            const w = ele.data('weight') || 1;
            return w > 0.9 ? '#ff6b6b' : w > 0.7 ? '#ffd60a' : '#4ecdc4';
          },
          'width': (ele) => 1 + (ele.data('weight') || 1) * 2,
          'opacity': 0.75,
          'label': (ele) => ele.data('type') || '',
          'font-size': 8,
          'color': '#94a3b8',
          'text-rotation': 'autorotate',
          'text-background-color': '#04060d',
          'text-background-opacity': 0.8,
          'text-background-padding': 2,
      }},
      { selector: 'edge.highlight', style: {
          'line-color': '#ff6b6b',
          'target-arrow-color': '#ff6b6b',
          'width': 4,
          'opacity': 1,
          'z-index': 100,
      }},
    ],
    layout: { name: 'cose', animate: true, idealEdgeLength: 110,
              nodeRepulsion: 60000, edgeElasticity: 0.45, gravity: 0.25,
              numIter: 2500, fit: true, padding: 30,
              randomize: true, componentSpacing: 60 },
    wheelSensitivity: 0.15,
    minZoom: 0.1, maxZoom: 4,
  });

  cy.on('tap', 'node', (evt) => {
    highlightNode(evt.target);
    showEntityDetails(evt.target.data());
    showEntityOnMap(evt.target.data());
  });

  cy.on('tap', (evt) => {
    if (evt.target === cy) {
      cy.elements().removeClass('highlight');
    }
  });
}

function initMap() {
  map = L.map('mini-map', {
    zoomControl: false, attributionControl: false,
    worldCopyJump: true, preferCanvas: true,
  }).setView([20, 0], 2);
  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png', {
    subdomains: 'abcd', maxZoom: 19,
  }).addTo(map);
}

function setupUI() {
  const input = document.getElementById('search-input');
  document.getElementById('btn-run').onclick = () => runSearch(input.value.trim(), false);
  document.getElementById('btn-upload').onclick = openUploadZone;
  document.getElementById('btn-facesearch').onclick = openFaceSearch;
  document.getElementById('btn-faceindex').onclick = openPersons;
  document.getElementById('btn-heatmap').onclick = openHeatmap;
  document.getElementById('btn-demo').onclick = runDemo;
  document.getElementById('btn-cascade').onclick = () => runSearch(input.value.trim(), true);
  document.getElementById('btn-clear').onclick = clearAll;
  document.getElementById('btn-export').onclick = () => exportData(exportFormat);
  document.getElementById('btn-export-arrow').onclick = toggleExportMenu;
  document.querySelectorAll('.export-menu-item').forEach(item => {
    item.onclick = () => {
      const fmt = item.getAttribute('data-format');
      setExportFormat(fmt);
      exportData(fmt);
    };
  });
  document.addEventListener('click', (e) => {
    if (!e.target.closest('.export-split')) closeExportMenu();
  });
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') runSearch(input.value.trim(), false);
  });

  document.querySelectorAll('.gc-btn').forEach(b => {
    b.onclick = () => {
      document.querySelectorAll('.gc-btn').forEach(x => x.classList.remove('active'));
      b.classList.add('active');
      currentLayout = b.dataset.layout;
      applyLayout();
    };
  });
}

async function loadModules() {
  try {
    const r = await fetch('/api/v1/modules');
    const d = await r.json();
    modulesData = d.modules || [];
    renderModuleTracker('idle');
  } catch (e) {
    console.error('loadModules failed', e);
  }
}

function renderModuleTracker(state) {
  const el = document.getElementById('modules-list');
  if (state === 'idle') {
    el.innerHTML = modulesData.map(m => `
      <div class="mod-card" data-mid="${m.id}">
        <div class="icon">${m.icon || '🔍'}</div>
        <div>
          <div class="name">${m.name}</div>
          <div class="sub">${(m.description || '').slice(0, 40)}</div>
        </div>
        <div class="badge">IDLE</div>
      </div>
    `).join('');
  }
}

function markModule(mid, state, count) {
  const el = document.querySelector(`.mod-card[data-mid="${mid}"]`);
  if (!el) return;
  el.classList.remove('queued', 'running', 'done', 'failed');
  el.classList.add(state);
  const badge = el.querySelector('.badge');
  badge.textContent = state === 'running' ? '⚡ ACTIF'
    : state === 'done' ? `✓ ${count || 0}`
    : state === 'failed' ? '✗ FAIL'
    : 'QUEUED';
}

function addLog(ts, ev, detail, isErr) {
  const log = document.getElementById('activity-log');
  const entry = document.createElement('div');
  entry.className = 'log-entry' + (isErr ? ' err' : '');
  entry.innerHTML = `<span class="ts">${ts}</span> <span class="ev">${ev}</span> ${detail || ''}`;
  log.appendChild(entry);
  log.scrollTop = log.scrollHeight;
  while (log.children.length > 200) log.removeChild(log.firstChild);
}

function buildLegend() {
  const types = Object.keys(TYPE_COLORS).slice(0, 12);
  const legend = document.getElementById('legend');
  legend.innerHTML = types.map(t => `
    <div class="legend-item">
      <span class="legend-dot" style="background:${TYPE_COLORS[t]}"></span>${t}
    </div>
  `).join('');
}

async function runSearch(value, cascade) {
  if (!value) {
    const inp = document.getElementById('search-input');
    if (inp) inp.focus();
    return;
  }
  try { resetForNewSearch(); } catch (e) { console.warn('reset failed', e); }
  try { addLog(ts(), '🎯 INPUT', value); } catch(e) {}

  try {
    const r = await fetch('/api/v1/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        input_value: value, max_depth: cascade ? 3 : 1,
        auto_cascade: true, snapshot_pacing_seconds: cascade ? 0.5 : 0,
      }),
    });
    const d = await r.json();
    currentSession = d.session_id;
    document.getElementById('qs-session').textContent = currentSession;

    if (d.root_entity) {
      addNode({
        ...d.root_entity,
        metadata: { ...d.root_entity.metadata, root: true, session: currentSession },
      });
    }
    if (d.pipeline) {
      d.pipeline.forEach(p => markModule(p.module_id, 'queued', 0));
    }
    addLog(ts(), '📡 PIPELINE', `${(d.pipeline || []).length} modules queued`, false);
    document.getElementById('graph-stats').textContent = 'Pipeline en cours...';

    // Start active polling immediately
    startPolling(currentSession);
    document.getElementById('polling-indicator').textContent = '🟢 POLLING...';
    setTimeout(() => loadSessionGraph(currentSession), 1000);
  } catch (e) {
    addLog(ts(), '✗ ERR', e.message, true);
  }
}

async function runDemo() {
  resetForNewSearch();
  addLog(ts(), '🎲 DEMO', 'Lancement séquence démo multi-cibles', false);

  const demoInputs = [
    { value: '+15145550199', type: 'phone', label: 'phone' },
    { value: 'octocat', type: 'username', label: 'username' },
    { value: 'github.com', type: 'domain', label: 'domain' },
  ];

  for (const inp of demoInputs) {
    addLog(ts(), '🎯 INPUT', `${inp.label}: ${inp.value}`);
    try {
      const r = await fetch('/api/v1/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          input_value: inp.value, max_depth: 2, auto_cascade: true,
          snapshot_pacing_seconds: 0.3,
        }),
      });
      const d = await r.json();
      currentSession = d.session_id;
      document.getElementById('qs-session').textContent = currentSession;
      if (d.root_entity) {
        addNode({ ...d.root_entity, metadata: { ...d.root_entity.metadata, root: true } });
      }
      if (d.pipeline) d.pipeline.forEach(p => markModule(p.module_id, 'queued', 0));
      await new Promise(r => setTimeout(r, 1500));
      await loadSessionGraph(currentSession);
    } catch (e) {
      addLog(ts(), '✗ ERR', `${inp.label}: ${e.message}`, true);
    }
  }
  addLog(ts(), '✓ DEMO', 'Séquence complète', false);
}

async function loadSessionGraph(sid) {
  try {
    const r = await fetch(`/api/v1/footprint/${sid}/graph`);
    const d = await r.json();
    if (d.nodes) {
      d.nodes.forEach(n => addNode(n));
      d.edges?.forEach(e => addEdge(e));
    }
    if (d.relationships) d.relationships.forEach(e => addEdge(e));
    updateStats();
    document.getElementById('mod-done').textContent =
      document.querySelectorAll('.mod-card.done').length;
  } catch (e) {
    console.error('loadSessionGraph failed', e);
  }
}

function resetForNewSearch() {
  try {
    if (cy && typeof cy.elements === 'function') {
      cy.elements().remove();
    }
  } catch (e) { console.warn('cy.reset failed', e); }
  seenNodes.clear();
  seenEdges.clear();
  allEntities = [];
  allRelationships = [];
  try {
    if (map && mapMarkers && mapMarkers.length) {
      mapMarkers.forEach(m => { try { map.removeLayer(m); } catch(_){} });
      mapMarkers = [];
    }
  } catch(e) { /* map not ready */ }
  currentSession = null;
  renderModuleTracker('idle');
  const set0 = (id, v) => { const x = document.getElementById(id); if (x) x.textContent = v; };
  set0('tl-count', 0);
  set0('qs-nodes', 0);
  set0('qs-edges', 0);
  set0('graph-stats', 'Reset.');
  set0('map-stats', 'Reset.');
  const tt = document.getElementById('timeline-track');
  if (tt) tt.remove();
}

function clearAll() {
  resetForNewSearch();
  document.getElementById('entity-details').innerHTML =
    '<div class="no-data">👆 Clique un nœud pour voir ses corrélations.</div>';
  document.getElementById('corr-ribbon').style.display = 'none';
  addLog(ts(), '⟲ CLEAR', 'Reset complet', false);
}

function addNode(entity) {
  if (!entity || !entity.id || seenNodes.has(entity.id)) return;
  seenNodes.add(entity.id);
  allEntities.push(entity);

  const isRoot = entity.metadata?.root === true;
  if (cy && typeof cy.add === 'function') {
    cy.add({
      group: 'nodes',
      data: {
        id: entity.id, type: entity.type, value: entity.value,
        source: entity.source, confidence: entity.confidence,
        metadata: entity.metadata, status: entity.status,
      },
      classes: isRoot ? 'root' : '',
    });
  }

  // Update map if geo
  if (entity.metadata?.lat && entity.metadata?.lon) {
    addMapMarker(entity);
  }
  // Update timeline
  addTimelineEntry(entity);
  updateStats();
}

function addEdge(rel) {
  if (!rel || !rel.source || !rel.target) return;
  const eid = `${rel.source}→${rel.target}`;
  if (seenEdges.has(eid)) return;
  if (!seenNodes.has(rel.source) || !seenNodes.has(rel.target)) return;
  seenEdges.add(eid);
  allRelationships.push(rel);

  if (cy && typeof cy.add === 'function') {
    cy.add({
      group: 'edges',
      data: {
        id: eid, source: rel.source, target: rel.target,
        type: rel.type, weight: rel.weight || 1.0, evidence: rel.evidence,
      },
    });
  }
  updateStats();
}

function addMapMarker(entity) {
  const lat = parseFloat(entity.metadata.lat);
  const lon = parseFloat(entity.metadata.lon);
  if (isNaN(lat) || isNaN(lon)) return;
  const color = TYPE_COLORS[entity.type] || '#4ecdc4';
  const marker = L.circleMarker([lat, lon], {
    radius: 5, color: '#000', fillColor: color, fillOpacity: 0.85,
    weight: 1, opacity: 0.8,
  }).addTo(map).bindPopup(`<b>${entity.type}</b><br>${entity.value}<br><small>${entity.source || ''}</small>`);
  mapMarkers.push(marker);
  updateMapStats();
}

function updateMapStats() {
  const pts = mapMarkers.map(m => m.getLatLng());
  if (!pts.length) {
    document.getElementById('map-stats').textContent = 'Aucune coordonnée.';
    return;
  }
  if (pts.length === 1) {
    map.setView(pts[0], 4);
  } else {
    const bounds = L.latLngBounds(pts);
    map.fitBounds(bounds, { padding: [20, 20] });
  }
  document.getElementById('map-stats').textContent =
    `${pts.length} points géolocalisés`;
}

function addTimelineEntry(entity) {
  let track = document.getElementById('timeline-track');
  if (!track) {
    const section = document.querySelector('.timeline-section');
    section.innerHTML = '<div class="timeline-track" id="timeline-track"></div>';
    track = document.getElementById('timeline-track');
  }
  const ev = document.createElement('div');
  ev.className = 'tl-event';
  const ts = entity.metadata?.ts || new Date().toLocaleTimeString();
  const mod = entity.source || 'unknown';
  ev.innerHTML = `<span class="tl-mod">${mod}</span> → <span class="tl-val">${entity.value}</span>
                  <div class="tl-time">${ts}</div>`;
  track.prepend(ev);
  document.getElementById('tl-count').textContent = track.children.length;
}

function highlightNode(node) {
  cy.elements().removeClass('highlight');
  const neighborhood = node.closedNeighborhood();
  neighborhood.addClass('highlight');
  node.flashClass('flash', 800);
  // Center
  cy.animate({ center: { eles: node }, duration: 400 });
}

function showEntityDetails(entity) {
  const el = document.getElementById('entity-details');
  const meta = entity.metadata || {};
  const conf = entity.confidence != null
    ? `${Math.round(entity.confidence * 100)}%` : '—';
  const conn = allRelationships.filter(r => r.source === entity.id || r.target === entity.id);

  el.innerHTML = `
    <div class="ed-type">${entity.type || 'unknown'}</div>
    <div class="ed-value">${entity.value || '—'}</div>
    <div class="ed-meta">
      <div><div class="k">Source</div><div class="v">${entity.source || '—'}</div></div>
      <div><div class="k">Confiance</div><div class="v">${conf}</div></div>
      <div><div class="k">Status</div><div class="v">${entity.status || '—'}</div></div>
      <div><div class="k">Connexions</div><div class="v">${conn.length}</div></div>
    </div>
    ${meta.lat ? `<div class="ed-meta">
      <div><div class="k">Lat</div><div class="v">${meta.lat}</div></div>
      <div><div class="k">Lon</div><div class="v">${meta.lon}</div></div>
    </div>` : ''}
    <div style="margin-top:12px;font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:1px;">
      Corrélations directes:
    </div>
    <div style="margin-top:6px;font-family:monospace;font-size:10px;color:var(--dim);max-height:180px;overflow-y:auto;">
      ${conn.slice(0, 30).map(c => {
        const other = c.source === entity.id ? c.target : c.source;
        const e = allEntities.find(x => x.id === other);
        return `<div style="padding:3px 0;border-bottom:1px dashed var(--bg-2);">
          <span style="color:var(--acc)">${c.type}</span> →
          <span style="color:var(--text)">${e ? e.value : other}</span>
        </div>`;
      }).join('') || '<em style="color:var(--muted)">Aucune corrélation directe.</em>'}
    </div>
  `;

  // Update correlation ribbon
  const ribbon = document.getElementById('corr-ribbon');
  if (conn.length >= 3) {
    ribbon.style.display = 'block';
    ribbon.textContent = `🎯 ${conn.length} corrélations actives`;
  } else if (conn.length === 0) {
    ribbon.style.display = 'none';
  } else {
    ribbon.style.display = 'block';
    ribbon.textContent = `🎯 ${conn.length} corrélations`;
  }
}

function showEntityOnMap(entity) {
  const lat = parseFloat(entity.metadata?.lat);
  const lon = parseFloat(entity.metadata?.lon);
  if (!isNaN(lat) && !isNaN(lon)) {
    map.setView([lat, lon], 6);
  }
}

function applyLayout() {
  const layouts = {
    'cose': { name: 'cose', animate: true, idealEdgeLength: 110,
              nodeRepulsion: 60000, edgeElasticity: 0.45, gravity: 0.25,
              numIter: 1500, fit: true, padding: 30, randomize: true,
              componentSpacing: 60 },
    'concentric': { name: 'concentric', animate: true, minNodeSpacing: 30,
                     concentric: (n) => n.degree(), levelWidth: () => 2,
                     fit: true, padding: 30 },
    'breadthfirst': { name: 'breadthfirst', animate: true, directed: true,
                     padding: 30, spacingFactor: 1.5, fit: true },
    'grid': { name: 'grid', animate: true, fit: true, padding: 30 },
  };
  const layout = layouts[currentLayout] || layouts['cose'];
  cy.layout(layout).run();
}

function updateStats() {
  const nn = cy ? cy.nodes().length : 0;
  const ne = cy ? cy.edges().length : 0;
  const setText = (id, v) => { const x = document.getElementById(id); if (x) x.textContent = v; };
  setText('qs-nodes', nn);
  setText('qs-edges', ne);
  setText('graph-stats', `${nn} nœuds · ${ne} corrélations`);
  // Count correlation clusters
  const corrCount = allRelationships.filter(r => (r.weight || 1) >= 0.7).length;
  document.getElementById('qs-corr').textContent = corrCount;
}

let eventSource = null;
let pollInterval = null;

function startPolling(sid) {
  if (pollInterval) clearInterval(pollInterval);
  pollInterval = setInterval(async () => {
    try {
      const r = await fetch(`/api/v1/footprint/${sid}/graph`);
      const d = await r.json();
      if (d.nodes) d.nodes.forEach(n => addNode(n));
      if (d.edges) d.edges.forEach(e => addEdge(e));
      updateStats();
      const ind = document.getElementById('polling-indicator');
      if (ind) {
        const n = cy ? cy.nodes().length : allEntities.length;
        ind.textContent = `🟢 POLLING · ${n} nodes`;
        ind.style.color = 'var(--ok)';
      }
    } catch (e) {
      const ind = document.getElementById('polling-indicator');
      if (ind) ind.style.color = 'var(--acc3)';
    }
  }, 10000);
}

function startEventSource() {
  if (eventSource) eventSource.close();
  try {
    eventSource = new EventSource('/api/v1/activity/stream');
    eventSource.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data);
        handleActivity(data);
        if (data.stats && currentSession) {
          loadSessionGraph(currentSession);
        }
      } catch (e) {}
    };
    eventSource.onerror = () => {
      // SSE failed, HTTP polling still works as fallback
    };
  } catch (e) {}
}

async function pollActivity() {
  startEventSource();
}

function handleActivity(data) {
  if (data.event === 'module_completed') {
    markModule(data.module_id, 'done', data.entities_found || 0);
    addLog(ts(), '✓ MODULE', `${data.module_name || data.module_id}: ${data.entities_found} entités`, false);
    (data.new_entities || []).forEach(e => addNode(e));
  } else if (data.event === 'module_started') {
    markModule(data.module_id, 'running', 0);
    addLog(ts(), '⚡ MOD', `${data.module_id} démarré`, false);
  } else if (data.event === 'module_error') {
    markModule(data.module_id, 'failed', 0);
    addLog(ts(), '✗ ERR', `Module ${data.module_id}: ${data.error || 'fail'}`, true);
  } else if (data.event === 'pipeline_complete') {
    addLog(ts(), '✓ DONE', `Pipeline: ${data.total_modules || '?'} modules, ${data.total_entities || '?'} entités`, false);
  } else if (data.event === 'entity_discovered') {
    addNode(data.entity);
  } else if (data.event === 'relationship_added') {
    addEdge(data.relationship);
  } else if (data.stats) {
    updateStats();
  }
}

let _uploadedFile = null;
let _uploadedFileURL = null;

function openUploadZone() {
  const z = document.getElementById('upload-zone');
  if (z) z.classList.add('open');
  const res = document.getElementById('upload-result');
  if (res) res.style.display = 'none';
}
function closeUploadZone() {
  const z = document.getElementById('upload-zone');
  if (z) z.classList.remove('open');
  _uploadedFile = null;
  _uploadedFileURL = null;
}

function setupUpload() {
  const pick = document.getElementById('upload-pick');
  const file = document.getElementById('upload-file');
  const preview = document.getElementById('upload-preview');
  const analyze = document.getElementById('upload-analyze');
  const close = document.getElementById('upload-close');
  if (!pick) return;
  pick.onclick = () => file.click();
  file.onchange = (e) => {
    _uploadedFile = e.target.files[0];
    if (_uploadedFile) {
      if (_uploadedFileURL) URL.revokeObjectURL(_uploadedFileURL);
      _uploadedFileURL = URL.createObjectURL(_uploadedFile);
      preview.src = _uploadedFileURL;
      preview.style.display = 'block';
      analyze.disabled = false;
    }
  };
  analyze.onclick = async () => {
    if (!_uploadedFile) return;
    analyze.disabled = true;
    analyze.textContent = '⏳ Analyse...';
    const fd = new FormData();
    fd.append('file', _uploadedFile);
    try {
      const r = await fetch('/api/v1/image/upload', { method: 'POST', body: fd });
      const d = await r.json();
      const res = document.getElementById('upload-result');
      res.style.display = 'block';
      const det = d.entities ? d.entities.filter(e => e.type === 'face').length : 0;
      const gps = d.entities ? d.entities.filter(e => e.type === 'gps') : [];
      const cam = d.entities ? d.entities.filter(e => e.type === 'camera') : [];
      res.innerHTML = `
        <div><span class="lbl">Backend:</span> <span class="ok">${d.backend || '?'}</span></div>
        <div><span class="lbl">Status:</span> ${d.status}</div>
        <div><span class="lbl">Faces d\u00e9tect\u00e9es:</span> <span class="ok">${det}</span></div>
        ${cam.length ? `<div><span class="lbl">Camera EXIF:</span> ${cam[0].value}</div>` : ''}
        ${gps.length ? `<div><span class="lbl">GPS EXIF:</span> ${gps[0].value}</div>` : ''}
        <div><span class="lbl">Entit\u00e9s:</span> ${(d.entities||[]).length}</div>
        <div><span class="lbl">Relations:</span> ${(d.relationships||[]).length}</div>
        <div><span class="lbl">Temps:</span> ${d.execution_time_ms}ms</div>
        ${d.warnings && d.warnings.length ? `<div style="color:#facc15;margin-top:6px;">⚠ ${d.warnings.join(', ')}</div>` : ''}
      `;
      if (window.cy && d.entities) {
        d.entities.forEach(e => addNode({
          id: e.id, type: e.type, value: String(e.value).slice(0, 80),
          confidence: e.confidence || 0.8, metadata: e.metadata || {}
        }));
        (d.relationships || []).forEach(r => addEdge(r));
        updateStats();
      }
      addLog(ts(), '📷 UPLOAD', `FaceMatch: ${det} face(s), ${(d.entities||[]).length} entit\u00e9s`, false);
    } catch (e) {
      const res = document.getElementById('upload-result');
      res.style.display = 'block';
      res.innerHTML = `<div style="color:#ef4444;">✗ ${e.message}</div>`;
    } finally {
      analyze.disabled = false;
      analyze.textContent = '⚡ ANALYSER';
    }
  };
  close.onclick = closeUploadZone;
}

let exportFormat = 'json';

function setExportFormat(fmt) {
  exportFormat = fmt;
  const labels = { json: '📥 JSON', pdf: '📄 PDF', png: '🖼️ PNG' };
  const btn = document.getElementById('btn-export');
  if (btn) btn.innerHTML = labels[fmt] || '📥 JSON';
}

function toggleExportMenu(e) {
  if (e) { e.stopPropagation(); e.preventDefault(); }
  const menu = document.getElementById('export-menu');
  if (menu) menu.classList.toggle('open');
}

function closeExportMenu() {
  const menu = document.getElementById('export-menu');
  if (menu) menu.classList.remove('open');
}

async function exportData(fmt) {
  const format = fmt || exportFormat || 'json';
  const btn = document.getElementById('btn-export');
  const original = btn ? btn.innerHTML : null;
  const labels = { json: '📥 JSON', pdf: '📄 PDF', png: '🖼️ PNG' };
  closeExportMenu();
  try {
    if (btn) { btn.innerHTML = '⏳ ...'; btn.disabled = true; }

    // PNG: génération côté client via Cytoscape
    if (format === 'png') {
      if (!cy) throw new Error('Graphe non initialisé');
      const png = cy.png({ full: true, scale: 2, bg: '#04060d' });
      const tsSlug = new Date().toISOString().replace(/[-:T]/g, '').slice(0, 14);
      const a = document.createElement('a');
      a.href = png;
      a.download = `osin_graph_${currentSession || 'graph'}_${tsSlug}.png`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      addLog(ts(), '🖼️ PNG', 'Capture du graphe téléchargée', false);
      return;
    }

    const r = await fetch('/api/v1/export', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ format, include_footprint: true }),
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const blob = await r.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    const tsSlug = new Date().toISOString().replace(/[-:T]/g, '').slice(0, 14);
    const ext = format === 'pdf' ? 'pdf' : 'json';
    a.download = `osin_export_${currentSession || 'graph'}_${tsSlug}.${ext}`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    const sizeKb = Math.round(blob.size / 1024);
    const fmtLabel = labels[format] || format.toUpperCase();
    addLog(ts(), fmtLabel, `Export ${format.toUpperCase()} téléchargé (${sizeKb} KB)`, false);
  } catch (e) {
    const fmtLabel = labels[format] || format.toUpperCase();
    addLog(ts(), `✗ ${fmtLabel}`, e.message, true);
  } finally {
    if (btn) { btn.innerHTML = original; btn.disabled = false; }
  }
}

function ts() {
  return new Date().toLocaleTimeString('fr-FR', { hour12: false });
}

// ════════════════════════════════════════════════════════════
// MODULE 14 FACEMATCH — FRONTEND HANDLERS
// ════════════════════════════════════════════════════════════

// ─── Face Search modal ───
let _fsFile = null;
let _fsFileURL = null;
let _fsThreshold = 0.50;

function openFaceSearch() {
  document.getElementById('face-search-modal').classList.add('open');
  document.getElementById('fs-result').style.display = 'none';
  document.getElementById('fs-preview').style.display = 'none';
  document.getElementById('fs-go').disabled = true;
  _fsFile = null;
}
function closeFaceSearch() {
  document.getElementById('face-search-modal').classList.remove('open');
  if (_fsFileURL) URL.revokeObjectURL(_fsFileURL);
}
function _setupFaceSearch() {
  const drop = document.getElementById('fs-drop');
  const file = document.getElementById('fs-file');
  const go = document.getElementById('fs-go');
  const preview = document.getElementById('fs-preview');
  const tdown = document.getElementById('fs-threshold-down');
  const tup = document.getElementById('fs-threshold-up');

  drop.onclick = () => file.click();
  file.onchange = (e) => {
    _fsFile = e.target.files[0];
    if (_fsFile) {
      if (_fsFileURL) URL.revokeObjectURL(_fsFileURL);
      _fsFileURL = URL.createObjectURL(_fsFile);
      preview.src = _fsFileURL;
      preview.style.display = 'block';
      go.disabled = false;
    }
  };
  drop.ondragover = (e) => { e.preventDefault(); drop.classList.add('dragover'); };
  drop.ondragleave = () => drop.classList.remove('dragover');
  drop.ondrop = (e) => {
    e.preventDefault();
    drop.classList.remove('dragover');
    if (e.dataTransfer.files.length) {
      _fsFile = e.dataTransfer.files[0];
      if (_fsFileURL) URL.revokeObjectURL(_fsFileURL);
      _fsFileURL = URL.createObjectURL(_fsFile);
      preview.src = _fsFileURL;
      preview.style.display = 'block';
      go.disabled = false;
    }
  };
  tdown.onclick = () => {
    _fsThreshold = Math.max(0.10, _fsThreshold - 0.05);
    document.getElementById('fs-thresh').textContent = _fsThreshold.toFixed(2);
  };
  tup.onclick = () => {
    _fsThreshold = Math.min(0.95, _fsThreshold + 0.05);
    document.getElementById('fs-thresh').textContent = _fsThreshold.toFixed(2);
  };
  go.onclick = async () => {
    if (!_fsFile) return;
    go.disabled = true; go.textContent = '⏳ Recherche...';
    const fd = new FormData();
    fd.append('file', _fsFile);
    try {
      const r = await fetch(`/api/v1/face/search?top_k=20&threshold=${_fsThreshold}`, { method: 'POST', body: fd });
      const d = await r.json();
      renderFaceSearchResult(d);
    } catch (e) {
      const res = document.getElementById('fs-result');
      res.style.display = 'block';
      res.innerHTML = `<div class="err">✗ ${e.message}</div>`;
    } finally {
      go.disabled = false; go.textContent = '⚡ CHERCHER MATCHS';
    }
  };
}
function renderFaceSearchResult(d) {
  const res = document.getElementById('fs-result');
  res.style.display = 'block';
  if (d.error) {
    res.innerHTML = `<div class="err">✗ ${d.error}</div>`;
    return;
  }
  let html = `<div><span class="lbl">Visages query:</span> <span class="ok">${(d.query_faces||[]).length}</span></div>`;
  html += `<div><span class="lbl">Index total:</span> ${d.total_indexed || 0} visages</div>`;
  html += `<div><span class="lbl">Seuil:</span> θ=${_fsThreshold.toFixed(2)}</div>`;
  (d.matches || []).forEach((m, i) => {
    html += `<h3>👤 Query Face #${i+1} (${m.backend}, ${m.gender || '?'}, ${m.age || '?'} ans)</h3>`;
    html += `<div><span class="lbl">bbox:</span> [${m.bbox.map(x => x.toFixed(0)).join(', ')}]</div>`;
    html += `<div><span class="lbl">matches:</span> <span class="ok">${m.match_count}</span></div>`;
    if (m.matches && m.matches.length) {
      html += `<div style="margin-top:6px;">`;
      m.matches.slice(0, 5).forEach(mt => {
        const color = mt.similarity >= 0.65 ? 'ok' : mt.similarity >= 0.50 ? 'warn' : '';
        html += `<div class="stat-pill" style="display:block; margin:2px 0; padding:4px 8px;">
          <strong>${(mt.similarity*100).toFixed(1)}%</strong>
          · <span class="${color}">${mt.face_id.slice(0,18)}</span>
          · ${(mt.source || '').slice(0,40)}
        </div>`;
      });
      html += `</div>`;
    }
  });
  if (!d.matches || !d.matches.length) {
    html += `<div class="warn" style="margin-top:10px;">⚠ Aucun match dans l'index (ou aucun visage détecté dans la query)</div>`;
  }
  res.innerHTML = html;
  addLog(ts(), '🔍 FACE-SEARCH', `${(d.matches||[]).length} visage(s) query, ${d.total_indexed || 0} indexés`, false);
}

// ─── Persons panel ───
let _perSelected = new Set();

function openPersons() {
  document.getElementById('persons-modal').classList.add('open');
  refreshPersons();
}
function closePersons() {
  document.getElementById('persons-modal').classList.remove('open');
}
function _setupPersons() {
  document.getElementById('per-refresh').onclick = refreshPersons;
  document.getElementById('per-compare').onclick = doCompareSelected;
  document.getElementById('per-clear').onclick = async () => {
    if (!confirm('Vraiment effacer TOUT l\'index de visages ? (RGPD)')) return;
    const r = await fetch('/api/v1/face/index/clear', { method: 'DELETE' });
    const d = await r.json();
    addLog(ts(), '🗑️ CLEAR', `${d.cleared} visages effacés`, false);
    refreshPersons();
  };
  document.getElementById('per-cancel-compare').onclick = () => {
    _perSelected.clear();
    document.querySelectorAll('.face-thumb').forEach(t => t.classList.remove('selected'));
    updateCompareUI();
  };
}
async function refreshPersons() {
  try {
    const [statsR, clustersR, idxR] = await Promise.all([
      fetch('/api/v1/face/stats').then(r => r.json()),
      fetch('/api/v1/face/clusters').then(r => r.json()),
      fetch('/api/v1/face/index?limit=60').then(r => r.json()),
    ]);
    renderStats(statsR);
    renderClusters(clustersR.clusters || []);
    renderFaceIndex(idxR.items || []);
  } catch (e) {
    addLog(ts(), '✗ PERSONS', e.message, true);
  }
}
function renderStats(s) {
  const el = document.getElementById('per-stats');
  el.innerHTML = `<span class="stat-pill">visages <strong>${s.total_faces||0}</strong></span>
    <span class="stat-pill">personnes <strong>${s.total_persons||0}</strong></span>
    ${s.demographics && s.demographics.avg_age ? `<span class="stat-pill">âge moy <strong>${s.demographics.avg_age}</strong></span>` : ''}
    ${s.with_embedding ? `<span class="stat-pill">emb <strong>${s.with_embedding}</strong></span>` : ''}`;
}
function renderClusters(clusters) {
  const c = document.getElementById('per-clusters');
  if (!clusters.length) {
    c.innerHTML = `<div class="no-data">Aucun cluster (besoin de 2+ visages avec embedding ou 4+ avec pHash)</div>`;
    return;
  }
  c.innerHTML = `<h3 style="color:var(--acc4); font-size:13px; letter-spacing:1px; margin:0 0 8px 0;">👥 PERSON CLUSTERS (DBSCAN)</h3>` +
    clusters.map(p => {
      const ageG = (p.avg_age ? `${p.avg_age}ans` : '?') + ' / ' + (p.dominant_gender || '?');
      return `<div class="person-card">
        <div class="pavatar">${(p.face_count || 1)}</div>
        <div class="pinfo">
          <div class="pname">Person #${p.cluster_id} — ${p.face_count} face(s)</div>
          <div class="pmeta">${ageG} · first: ${p.first_seen ? new Date(p.first_seen*1000).toLocaleString() : '?'} · last: ${p.last_seen ? new Date(p.last_seen*1000).toLocaleString() : '?'}</div>
        </div>
        <button class="pbtn" onclick="viewPerson(${p.cluster_id})">VOIR</button>
      </div>`;
    }).join('');
}
function renderFaceIndex(items) {
  const g = document.getElementById('per-grid');
  if (!items.length) {
    g.innerHTML = `<div class="no-data" style="grid-column: 1/-1;">Index vide. Upload des photos pour le remplir.</div>`;
    return;
  }
  g.innerHTML = items.map(f => {
    const ts = f.created_at ? new Date(f.created_at*1000).toLocaleTimeString() : '';
    const backend = (f.metadata && f.metadata.backend) || '?';
    return `<div class="face-thumb" data-fid="${f.face_id}" onclick="toggleFaceSelect('${f.face_id}', this)">
      <div style="font-size:24px;">👤</div>
      <div class="ftid">${f.face_id.slice(0,16)}</div>
      <div class="ftmeta">${ts}</div>
      <div class="ftbadge">${backend}</div>
    </div>`;
  }).join('');
}
function toggleFaceSelect(fid, el) {
  if (_perSelected.has(fid)) {
    _perSelected.delete(fid);
    el.classList.remove('selected');
  } else if (_perSelected.size < 2) {
    _perSelected.add(fid);
    el.classList.add('selected');
  } else {
    addLog(ts(), '⚠ SELECT', 'Max 2 faces pour compare', true);
  }
  updateCompareUI();
}
function updateCompareUI() {
  const cb = document.getElementById('per-comparebar');
  const btn = document.getElementById('per-compare');
  if (_perSelected.size === 2) {
    cb.style.display = 'flex';
    btn.disabled = false;
    document.getElementById('per-cktext').textContent = '2/2 sélectionnés — COMPARE prêt';
  } else {
    btn.disabled = _perSelected.size !== 2;
    if (_perSelected.size > 0) {
      cb.style.display = 'flex';
      document.getElementById('per-cktext').textContent = `${_perSelected.size}/2 sélectionnés`;
    } else {
      cb.style.display = 'none';
    }
  }
}
async function doCompareSelected() {
  if (_perSelected.size !== 2) return;
  const [a, b] = [..._perSelected];
  try {
    const r = await fetch(`/api/v1/face/compare?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`);
    const d = await r.json();
    const verdict = d.verdict || '?';
    const color = d.similarity >= 0.65 ? '#10b981' : d.similarity >= 0.50 ? '#f59e0b' : '#ef4444';
    const res = document.getElementById('per-grid');
    res.insertAdjacentHTML('beforeend', `<div class="face-result" style="grid-column: 1/-1; border-color:${color};">
      <h3>⚖️ COMPARE RESULT</h3>
      <div><span class="lbl">Verdict:</span> <strong style="color:${color};">${verdict.toUpperCase().replace(/_/g, ' ')}</strong></div>
      <div><span class="lbl">Similarité:</span> <strong style="color:${color};">${(d.similarity*100).toFixed(2)}%</strong></div>
      <div><span class="lbl">Méthode:</span> ${d.method}</div>
      <div><span class="lbl">Face A:</span> ${(d.face_a.value || '').slice(0,40)}</div>
      <div><span class="lbl">Face B:</span> ${(d.face_b.value || '').slice(0,40)}</div>
    </div>`);
    addLog(ts(), '⚖️ COMPARE', `${verdict} · ${(d.similarity*100).toFixed(1)}%`, false);
  } catch (e) {
    addLog(ts(), '✗ COMPARE', e.message, true);
  }
}
async function viewPerson(clusterId) {
  try {
    const r = await fetch(`/api/v1/face/person/${clusterId}`);
    const p = await r.json();
    addLog(ts(), '👤 PERSON', `Cluster #${clusterId}: ${p.face_count} faces · ${p.dominant_gender||'?'} · ${p.avg_age||'?'}ans`, false);
  } catch (e) {
    addLog(ts(), '✗ PERSON', e.message, true);
  }
}

// ─── Batch upload ───
let _batchFiles = [];

function openBatch() { document.getElementById('batch-modal').classList.add('open'); }
function closeBatch() { document.getElementById('batch-modal').classList.remove('open'); }
function _setupBatch() {
  const drop = document.getElementById('batch-drop');
  const file = document.getElementById('batch-file');
  const go = document.getElementById('batch-go');
  drop.onclick = () => file.click();
  file.onchange = (e) => {
    _batchFiles = Array.from(e.target.files);
    renderBatchList();
    go.disabled = !_batchFiles.length;
  };
  drop.ondragover = (e) => { e.preventDefault(); drop.style.background = 'rgba(78,205,196,0.12)'; };
  drop.ondragleave = () => drop.style.background = '';
  drop.ondrop = (e) => {
    e.preventDefault();
    drop.style.background = '';
    _batchFiles = Array.from(e.dataTransfer.files).filter(f => f.type.startsWith('image/'));
    renderBatchList();
    go.disabled = !_batchFiles.length;
  };
  go.onclick = async () => {
    if (!_batchFiles.length) return;
    go.disabled = true; go.textContent = `⏳ Analyse ${_batchFiles.length} photos...`;
    const fd = new FormData();
    _batchFiles.forEach(f => fd.append('files', f));
    try {
      const r = await fetch('/api/v1/image/batch', { method: 'POST', body: fd });
      const d = await r.json();
      renderBatchResult(d);
      addLog(ts(), '📦 BATCH', `${d.count} photos analysées`, false);
      setTimeout(refreshPersons, 500);
    } catch (e) {
      addLog(ts(), '✗ BATCH', e.message, true);
    } finally {
      go.disabled = false; go.textContent = '⚡ ANALYSER TOUT';
    }
  };
}
function renderBatchList() {
  const el = document.getElementById('batch-list');
  el.innerHTML = _batchFiles.map((f, i) =>
    `<div class="batch-item">📷 ${f.name} (${(f.size/1024).toFixed(1)} KB)</div>`
  ).join('');
}
function renderBatchResult(d) {
  const el = document.getElementById('batch-list');
  el.innerHTML = '<h3 style="color:var(--acc4);">RÉSULTATS</h3>' +
    d.results.map(r => {
      if (r.error) return `<div class="batch-item error">✗ ${r.filename}: ${r.error}</div>`;
      return `<div class="batch-item">✓ ${r.filename} · ${r.backend} · ${r.entities} entité(s) · ${r.execution_time_ms}ms</div>`;
    }).join('');
}

// ─── EXIF GPS auto-pin on map ───
function autoPinGPS(lat, lon, label) {
  if (typeof map === 'undefined' || !map) return;
  L.marker([lat, lon]).addTo(map)
    .bindPopup(`<b>📷 ${label || 'Photo'}</b><br>${lat.toFixed(4)}, ${lon.toFixed(4)}`)
    .openPopup();
  map.setView([lat, lon], 8);
  addLog(ts(), '🗺️ GPS', `Pin auto: ${lat.toFixed(4)}, ${lon.toFixed(4)}`, false);
}

// ─── Hook into upload result to auto-pin EXIF GPS ───
const _origAn = window.analyzeUploadedPhoto;
window.analyzeUploadedPhoto = function() {
  // Called by upload modal after fetch
  if (arguments.length === 0 && window._lastUploadResult) {
    const d = window._lastUploadResult;
    const gps = (d.entities || []).filter(e => e.type === 'gps');
    if (gps.length) {
      const m = gps[0].metadata || {};
      const lat = parseFloat(m.lat || m.value);
      const lon = parseFloat(m.lon);
      if (!isNaN(lat) && !isNaN(lon)) {
        autoPinGPS(lat, lon, d.filename || 'Photo uploadée');
      }
    }
  }
};

// ─── Heatmap modal ───
let _heatCellSize = 1.0;

function openHeatmap() {
  document.getElementById('heatmap-modal').classList.add('open');
  refreshHeatmap();
}
function closeHeatmap() { document.getElementById('heatmap-modal').classList.remove('open'); }
async function refreshHeatmap() {
  try {
    const r = await fetch(`/api/v1/face/density?cell_size=${_heatCellSize}`);
    const d = await r.json();
    renderHeatmap(d);
  } catch (e) { addLog(ts(), '✗ HEATMAP', e.message, true); }
}
function renderHeatmap(d) {
  const canvas = document.getElementById('heat-canvas');
  canvas.innerHTML = '';
  const total = d.total || 0;
  document.getElementById('heat-total').innerHTML =
    `<span class="stat-pill"><strong>${total}</strong> sightings GPS</span>` +
    `<span class="stat-pill">cells <strong>${(d.cells||[]).length}</strong></span>`;
  if (!d.cells || !d.cells.length) {
    canvas.innerHTML = '<div class="no-data" style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);">No GPS data yet. Upload photos with EXIF GPS coords.</div>';
    return;
  }
  // Show top hotspots
  const max_count = Math.max(...d.cells.map(c => c.count));
  const hotspots = document.getElementById('heat-clusters');
  hotspots.innerHTML = '<h3 style="color:var(--acc4);font-size:12px;letter-spacing:1px;margin:8px 0 4px 0;">🔥 TOP HOTSPOTS</h3>' +
    d.cells.slice(0, 5).map(c => {
      const intensity = (c.count / max_count * 100).toFixed(0);
      return `<div class="stat-pill" style="display:block;margin:2px 0;padding:4px 8px;">
        📍 ${c.lat.toFixed(2)}°, ${c.lon.toFixed(2)}° — <strong>${c.count}</strong> sightings (${intensity}%)
      </div>`;
    }).join('');
  // Render cells as simple dots on a basic world map projection
  d.cells.slice(0, 30).forEach(c => {
    const dot = document.createElement('div');
    dot.className = 'heatmap-cell';
    const x = ((c.lon + 180) / 360) * 100;
    const y = ((90 - c.lat) / 180) * 100;
    const sz = Math.max(8, Math.min(40, c.count / max_count * 40));
    dot.style.left = `calc(${x}% - ${sz/2}px)`;
    dot.style.top = `calc(${y}% - ${sz/2}px)`;
    dot.style.width = `${sz}px`;
    dot.style.height = `${sz}px`;
    dot.title = `${c.lat}, ${c.lon} — ${c.count} sightings`;
    canvas.appendChild(dot);
  });
}
function _setupHeatmap() {
  document.getElementById('heat-refresh').onclick = refreshHeatmap;
  document.getElementById('heat-cell-down').onclick = () => {
    _heatCellSize = Math.max(0.1, _heatCellSize - 0.5);
    document.getElementById('heat-cell').textContent = _heatCellSize.toFixed(1) + '°';
    refreshHeatmap();
  };
  document.getElementById('heat-cell-up').onclick = () => {
    _heatCellSize = Math.min(10.0, _heatCellSize + 0.5);
    document.getElementById('heat-cell').textContent = _heatCellSize.toFixed(1) + '°';
    refreshHeatmap();
  };
}

// ─── Person rename (inline) ───
async function renamePerson(clusterId, currentName) {
  const name = prompt(`Renommer Person #${clusterId} (actuellement: ${currentName || 'Aucun'})`, currentName || '');
  if (!name) return;
  try {
    await fetch(`/api/v1/face/cluster/${clusterId}/name`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({name}),
    });
    addLog(ts(), '✏️ RENAME', `Person #${clusterId} → "${name}"`, false);
    refreshPersons();
  } catch (e) { addLog(ts(), '✗ RENAME', e.message, true); }
}

// ─── Face timeline ───
async function showFaceTimeline(faceId) {
  try {
    const r = await fetch(`/api/v1/face/timeline/${encodeURIComponent(faceId)}`);
    const d = await r.json();
    const res = document.getElementById('per-grid');
    const evs = (d.sightings || []).map(s => {
      const ts = new Date(s.timestamp*1000).toLocaleString();
      const gps = (s.lat != null && s.lon != null) ? `📍 ${s.lat.toFixed(2)}, ${s.lon.toFixed(2)}` : '';
      return `<div class="timeline-event">
        ⏱ ${ts} · ${(s.source||'').slice(0,40)} ${gps} · <em>${s.backend||'?'}</em>
      </div>`;
    }).join('');
    res.insertAdjacentHTML('beforeend', `<div class="face-result" style="grid-column: 1/-1;">
      <h3>⏱ TIMELINE: ${faceId.slice(0,18)} (${d.count} sightings)</h3>
      ${evs || '<div class="warn">No sightings yet</div>'}
    </div>`);
  } catch (e) { addLog(ts(), '✗ TIMELINE', e.message, true); }
}

// ─── Boot modals ───
document.addEventListener('DOMContentLoaded', () => {
  _setupFaceSearch();
  _setupPersons();
  _setupBatch();
  _setupHeatmap();
});

