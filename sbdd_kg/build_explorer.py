"""Generate a self-contained HTML explorer for the SBDD knowledge graph.

Reads graph.json (see build_graph.py), computes a fixed spring layout,
and writes explorer.html with the graph data embedded inline (no fetch,
no CDN - required for the artifact sandbox).
"""

import json
from pathlib import Path

import networkx as nx

HERE = Path(__file__).parent
graph_data = json.loads((HERE / "graph.json").read_text())
G = nx.node_link_graph(graph_data, edges="edges")

pos = nx.spring_layout(G, seed=11, k=1.6, iterations=500)
xs = [p[0] for p in pos.values()]
ys = [p[1] for p in pos.values()]
xmin, xmax = min(xs), max(xs)
ymin, ymax = min(ys), max(ys)

PAD = 130
W, H = 1900, 1250


def scale(v, vmin, vmax, lo, hi):
    if vmax - vmin < 1e-9:
        return (lo + hi) / 2
    return lo + (v - vmin) / (vmax - vmin) * (hi - lo)


nodes_out = []
for n, d in G.nodes(data=True):
    x, y = pos[n]
    degree = G.in_degree(n) + G.out_degree(n)
    nodes_out.append({
        "id": n,
        "type": d["type"],
        "label": d["label"],
        "summary": d["summary"],
        "url": d.get("url"),
        "year": d.get("year"),
        "source_url": d.get("source_url"),
        "source_note": d.get("source_note"),
        "x": round(scale(x, xmin, xmax, PAD, W - PAD), 1),
        "y": round(scale(y, ymin, ymax, PAD, H - PAD), 1),
        "degree": degree,
    })

edges_out = []
for u, v, d in G.edges(data=True):
    edges_out.append({
        "source": u,
        "target": v,
        "relation": d["relation"],
        "note": d.get("note", ""),
    })

payload = {"nodes": nodes_out, "edges": edges_out, "w": W, "h": H}
data_json = json.dumps(payload)

html = HTML_TEMPLATE = r"""<title>SBDD Concept Map</title>
<style>
@media (prefers-reduced-motion: reduce) {
  * { transition-duration: 0.001ms !important; animation-duration: 0.001ms !important; }
}

:root {
  --ground: #f4f2ec;
  --surface: #ffffff;
  --surface-2: #eae7dd;
  --border: #d9d4c6;
  --ink: #232019;
  --ink-dim: #6b6558;
  --accent: #c1642c;
  --accent-ink: #ffffff;
  --concept: #3f8f83;
  --method: #7d63c9;
  --paper: #b8862f;
  --link-line: #c7c1b1;
  --focus: #2f6ef2;
}

@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --ground: #191c22;
    --surface: #21252d;
    --surface-2: #2a2f39;
    --border: #383e4a;
    --ink: #eae7de;
    --ink-dim: #9a9d92;
    --accent: #e08947;
    --accent-ink: #191c22;
    --concept: #5bb3a6;
    --method: #a48ee0;
    --paper: #d4a548;
    --link-line: #3c414d;
    --focus: #6d9bff;
  }
}

:root[data-theme="dark"] {
  --ground: #191c22;
  --surface: #21252d;
  --surface-2: #2a2f39;
  --border: #383e4a;
  --ink: #eae7de;
  --ink-dim: #9a9d92;
  --accent: #e08947;
  --accent-ink: #191c22;
  --concept: #5bb3a6;
  --method: #a48ee0;
  --paper: #d4a548;
  --link-line: #3c414d;
  --focus: #6d9bff;
}

* { box-sizing: border-box; }

body {
  margin: 0;
  background: var(--ground);
  color: var(--ink);
  font-family: -apple-system, "Segoe UI", "Helvetica Neue", Arial, sans-serif;
  font-size: 15px;
  line-height: 1.5;
}

.app {
  display: grid;
  grid-template-columns: 280px 1fr 340px;
  grid-template-rows: auto 1fr;
  height: 100vh;
  min-height: 560px;
}

header {
  grid-column: 1 / 4;
  display: flex;
  align-items: baseline;
  gap: 14px;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
  background: var(--surface);
}

header h1 {
  font-family: ui-serif, Georgia, "Iowan Old Style", "Times New Roman", serif;
  font-size: 21px;
  font-weight: 600;
  margin: 0;
  letter-spacing: 0.2px;
}

header .sub {
  color: var(--ink-dim);
  font-size: 13px;
}

.legend {
  margin-left: auto;
  display: flex;
  gap: 16px;
  font-size: 12.5px;
  color: var(--ink-dim);
}

.legend span { display: inline-flex; align-items: center; gap: 6px; }

.dot { width: 9px; height: 9px; border-radius: 50%; display: inline-block; }
.dot.concept { background: var(--concept); }
.dot.method { background: var(--method); }
.dot.paper { background: var(--paper); }

nav.sidebar {
  border-right: 1px solid var(--border);
  background: var(--surface);
  overflow-y: auto;
  padding: 14px 12px 20px;
}

nav.sidebar input[type="search"] {
  width: 100%;
  padding: 9px 11px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--ground);
  color: var(--ink);
  font-size: 13.5px;
  margin-bottom: 14px;
}

nav.sidebar input[type="search"]:focus-visible {
  outline: 2px solid var(--focus);
  outline-offset: 1px;
}

.group-label {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  color: var(--ink-dim);
  margin: 16px 4px 6px;
}

.group-label:first-child { margin-top: 0; }

.node-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  text-align: left;
  padding: 7px 8px;
  border-radius: 7px;
  border: 1px solid transparent;
  background: transparent;
  color: var(--ink);
  font-size: 13.5px;
  cursor: pointer;
  font-family: inherit;
}

.node-btn:hover { background: var(--surface-2); }
.node-btn.active { background: var(--surface-2); border-color: var(--border); font-weight: 600; }
.node-btn:focus-visible { outline: 2px solid var(--focus); outline-offset: -1px; }
.node-btn.hidden { display: none; }

.node-btn .dot { flex: none; }
.node-btn .label { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

main {
  position: relative;
  overflow: hidden;
  background:
    radial-gradient(var(--border) 1px, transparent 1px);
  background-size: 22px 22px;
  background-position: -4px -4px;
}

main svg { width: 100%; height: 100%; display: block; cursor: grab; }
main svg.grabbing { cursor: grabbing; }

.edge {
  stroke: var(--link-line);
  stroke-width: 1.2;
  fill: none;
  transition: stroke 0.15s, stroke-width 0.15s, opacity 0.15s;
}

.edge.dim { opacity: 0.15; }
.edge.lit { stroke: var(--accent); stroke-width: 2; opacity: 1; }

.edge-label {
  font-size: 9.5px;
  fill: var(--ink-dim);
  font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace;
  pointer-events: none;
  opacity: 0;
  transition: opacity 0.15s;
}
.edge-label.lit { opacity: 1; fill: var(--accent); }

.node circle {
  stroke: var(--surface);
  stroke-width: 2;
  transition: stroke-width 0.15s, filter 0.15s, opacity 0.15s;
}

.node text {
  font-size: 11px;
  fill: var(--ink);
  pointer-events: none;
  paint-order: stroke;
  stroke: var(--ground);
  stroke-width: 3px;
  stroke-linejoin: round;
}

.node { cursor: pointer; }
.node.dim { opacity: 0.25; }
.node.selected circle { stroke: var(--accent); stroke-width: 3; }
.node:hover circle { filter: brightness(1.12); }
.node:focus-visible circle { outline: 2px solid var(--focus); outline-offset: 2px; }

.zoom-controls {
  position: absolute;
  right: 14px;
  bottom: 14px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.zoom-controls button {
  width: 30px;
  height: 30px;
  border-radius: 7px;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--ink);
  font-size: 16px;
  cursor: pointer;
  line-height: 1;
}
.zoom-controls button:hover { background: var(--surface-2); }
.zoom-controls button:focus-visible { outline: 2px solid var(--focus); }

aside.detail {
  border-left: 1px solid var(--border);
  background: var(--surface);
  padding: 22px 22px 24px;
  overflow-y: auto;
}

.empty-state {
  color: var(--ink-dim);
  font-size: 14px;
}

.empty-state p { margin: 0 0 10px; }

.type-pill {
  display: inline-block;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  padding: 3px 9px;
  border-radius: 999px;
  color: var(--accent-ink);
  margin-bottom: 12px;
}
.type-pill.concept { background: var(--concept); }
.type-pill.method { background: var(--method); }
.type-pill.paper { background: var(--paper); }

.detail h2 {
  font-family: ui-serif, Georgia, "Iowan Old Style", serif;
  font-size: 20px;
  margin: 0 0 4px;
  text-wrap: balance;
}

.detail .summary {
  margin: 12px 0 18px;
  color: var(--ink);
}

.detail .meta {
  font-size: 12.5px;
  color: var(--ink-dim);
  margin-bottom: 4px;
}

.detail a.paper-link {
  display: inline-block;
  margin-top: 4px;
  font-size: 13px;
  color: var(--accent);
  word-break: break-all;
}

.source-block {
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px solid var(--border);
}

.source-note {
  margin: 4px 0 0;
  font-size: 12.5px;
  color: var(--ink-dim);
  font-style: italic;
}

.rel-section h3 {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  color: var(--ink-dim);
  margin: 18px 0 8px;
}

.rel-item {
  display: flex;
  flex-direction: column;
  gap: 1px;
  width: 100%;
  text-align: left;
  padding: 8px 10px;
  border-radius: 7px;
  border: 1px solid var(--border);
  background: var(--ground);
  color: var(--ink);
  font-size: 13px;
  cursor: pointer;
  margin-bottom: 6px;
  font-family: inherit;
}
.rel-item:hover { border-color: var(--accent); }
.rel-item:focus-visible { outline: 2px solid var(--focus); }
.rel-item .rel-tag {
  font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace;
  font-size: 10.5px;
  color: var(--accent);
}

@media (max-width: 880px) {
  .app { grid-template-columns: 1fr; grid-template-rows: auto 44vh 1fr; }
  nav.sidebar { border-right: none; border-bottom: 1px solid var(--border); }
  aside.detail { border-left: none; border-top: 1px solid var(--border); }
}
</style>

<div class="app">
  <header>
    <h1>SBDD Concept Map</h1>
    <span class="sub">structure-based drug design &middot; concepts, methods &amp; papers</span>
    <div class="legend">
      <span><i class="dot concept"></i>Concept</span>
      <span><i class="dot method"></i>Method</span>
      <span><i class="dot paper"></i>Paper</span>
    </div>
  </header>

  <nav class="sidebar" id="sidebar" aria-label="Node index">
    <input type="search" id="search" placeholder="Filter nodes&hellip;" aria-label="Filter nodes" />
    <div id="node-list"></div>
  </nav>

  <main id="main">
    <svg id="graph" viewBox="0 0 __W__ __H__" aria-label="Concept graph">
      <g id="viewport">
        <g id="edges"></g>
        <g id="edge-labels"></g>
        <g id="nodes"></g>
      </g>
    </svg>
    <div class="zoom-controls">
      <button id="zoom-in" aria-label="Zoom in">+</button>
      <button id="zoom-out" aria-label="Zoom out">&minus;</button>
      <button id="zoom-reset" aria-label="Reset view">&#8634;</button>
    </div>
  </main>

  <aside class="detail" id="detail">
    <div class="empty-state">
      <p><strong>Click a node</strong> in the graph or the list on the left to read its summary.</p>
      <p>Drag the canvas to pan, scroll to zoom. Selecting a node highlights everything it connects to &mdash; click a connection to jump there.</p>
    </div>
  </aside>
</div>

<script>
const DATA = __DATA_JSON__;

const nodesById = Object.fromEntries(DATA.nodes.map(n => [n.id, n]));
const svg = document.getElementById("graph");
const viewport = document.getElementById("viewport");
const edgesG = document.getElementById("edges");
const edgeLabelsG = document.getElementById("edge-labels");
const nodesG = document.getElementById("nodes");
const detail = document.getElementById("detail");
const nodeListEl = document.getElementById("node-list");
const searchEl = document.getElementById("search");

const NS = "http://www.w3.org/2000/svg";
function el(tag, attrs) {
  const e = document.createElementNS(NS, tag);
  for (const k in attrs) e.setAttribute(k, attrs[k]);
  return e;
}

const typeColorVar = { Concept: "--concept", Method: "--method", Paper: "--paper" };
const radiusFor = n => 9 + Math.min(n.degree, 8) * 1.4;

// edges
const edgeEls = [];
DATA.edges.forEach(e => {
  const a = nodesById[e.source], b = nodesById[e.target];
  if (!a || !b) return;
  const line = el("line", {
    class: "edge", x1: a.x, y1: a.y, x2: b.x, y2: b.y,
    "data-source": e.source, "data-target": e.target
  });
  edgesG.appendChild(line);
  const label = el("text", {
    class: "edge-label", x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 - 3,
    "text-anchor": "middle", "data-source": e.source, "data-target": e.target
  });
  label.textContent = e.relation;
  edgeLabelsG.appendChild(label);
  edgeEls.push({ e, line, label });
});

// nodes
const nodeEls = {};
DATA.nodes.forEach(n => {
  const g = el("g", { class: "node", tabindex: "0", "data-id": n.id });
  const r = radiusFor(n);
  const circle = el("circle", { cx: n.x, cy: n.y, r: r, fill: `var(${typeColorVar[n.type]})` });
  const text = el("text", { x: n.x, y: n.y + r + 13, "text-anchor": "middle" });
  text.textContent = n.label.length > 26 ? n.label.slice(0, 24) + "…" : n.label;
  g.appendChild(circle);
  g.appendChild(text);
  g.addEventListener("click", () => selectNode(n.id));
  g.addEventListener("keydown", ev => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); selectNode(n.id); } });
  nodesG.appendChild(g);
  nodeEls[n.id] = g;
});

// sidebar list, grouped by type
const groupOrder = ["Concept", "Method", "Paper"];
const listItems = {};
groupOrder.forEach(type => {
  const items = DATA.nodes.filter(n => n.type === type).sort((a, b) => a.label.localeCompare(b.label));
  if (!items.length) return;
  const label = document.createElement("div");
  label.className = "group-label";
  label.textContent = type + "s";
  nodeListEl.appendChild(label);
  items.forEach(n => {
    const btn = document.createElement("button");
    btn.className = "node-btn";
    btn.setAttribute("data-id", n.id);
    btn.innerHTML = `<i class="dot ${type.toLowerCase()}"></i><span class="label"></span>`;
    btn.querySelector(".label").textContent = n.label;
    btn.addEventListener("click", () => selectNode(n.id));
    nodeListEl.appendChild(btn);
    listItems[n.id] = btn;
  });
});

let selected = null;

function neighborsOf(id) {
  const out = [], incoming = [];
  DATA.edges.forEach(e => {
    if (e.source === id) out.push(e);
    if (e.target === id) incoming.push(e);
  });
  return { out, incoming };
}

function selectNode(id) {
  selected = id;
  const n = nodesById[id];
  const { out, incoming } = neighborsOf(id);
  const connectedIds = new Set([id, ...out.map(e => e.target), ...incoming.map(e => e.source)]);

  Object.entries(nodeEls).forEach(([nid, g]) => {
    g.classList.toggle("dim", !connectedIds.has(nid));
    g.classList.toggle("selected", nid === id);
  });
  edgeEls.forEach(({ e, line, label }) => {
    const lit = e.source === id || e.target === id;
    line.classList.toggle("lit", lit);
    line.classList.toggle("dim", !lit);
    label.classList.toggle("lit", lit);
  });
  Object.entries(listItems).forEach(([nid, btn]) => btn.classList.toggle("active", nid === id));
  const activeBtn = listItems[id];
  if (activeBtn) activeBtn.scrollIntoView({ block: "nearest" });

  const pillClass = n.type.toLowerCase();
  let html = `<span class="type-pill ${pillClass}">${n.type}</span>`;
  html += `<h2>${n.label}</h2>`;
  html += `<p class="summary">${n.summary}</p>`;
  if (n.type === "Paper") {
    html += `<div class="meta">${n.year || ""}</div>`;
    if (n.url) html += `<a class="paper-link" href="${n.url}" target="_blank" rel="noopener">${n.url}</a>`;
  } else {
    html += `<div class="source-block">`;
    html += `<div class="meta">Source</div>`;
    if (n.source_url) {
      html += `<a class="paper-link" href="${n.source_url}" target="_blank" rel="noopener">${n.source_url}</a>`;
    }
    if (n.source_note) {
      html += `<p class="source-note">${n.source_note}</p>`;
    }
    html += `</div>`;
  }

  function relLabel(e, otherId, dir) {
    const other = nodesById[otherId];
    const arrow = dir === "out" ? "→" : "←";
    return `<button class="rel-item" data-id="${otherId}"><span class="rel-tag">${e.relation} ${arrow}</span>${other.label}</button>`;
  }

  if (out.length) {
    html += `<div class="rel-section"><h3>Connects to</h3>${out.map(e => relLabel(e, e.target, "out")).join("")}</div>`;
  }
  if (incoming.length) {
    html += `<div class="rel-section"><h3>Referenced by</h3>${incoming.map(e => relLabel(e, e.source, "in")).join("")}</div>`;
  }

  detail.innerHTML = html;
  detail.querySelectorAll(".rel-item").forEach(btn => {
    btn.addEventListener("click", () => selectNode(btn.getAttribute("data-id")));
  });
}

// filter
searchEl.addEventListener("input", () => {
  const q = searchEl.value.trim().toLowerCase();
  DATA.nodes.forEach(n => {
    const match = !q || n.label.toLowerCase().includes(q) || n.summary.toLowerCase().includes(q);
    listItems[n.id].classList.toggle("hidden", !match);
    nodeEls[n.id].classList.toggle("dim", !match && !selected);
  });
});

// pan & zoom
let scale = 1, tx = 0, ty = 0, dragging = false, lastX = 0, lastY = 0;
function applyTransform() {
  viewport.setAttribute("transform", `translate(${tx} ${ty}) scale(${scale})`);
}
svg.addEventListener("wheel", ev => {
  ev.preventDefault();
  const rect = svg.getBoundingClientRect();
  const mx = ev.clientX - rect.left, my = ev.clientY - rect.top;
  const factor = ev.deltaY < 0 ? 1.12 : 1 / 1.12;
  const newScale = Math.min(4, Math.max(0.35, scale * factor));
  tx = mx - (mx - tx) * (newScale / scale);
  ty = my - (my - ty) * (newScale / scale);
  scale = newScale;
  applyTransform();
}, { passive: false });

const DRAG_THRESHOLD = 4;
let downX = 0, downY = 0, downPointerId = null, movedPastThreshold = false;

svg.addEventListener("pointerdown", ev => {
  downX = lastX = ev.clientX;
  downY = lastY = ev.clientY;
  downPointerId = ev.pointerId;
  movedPastThreshold = false;
  dragging = false;
});
svg.addEventListener("pointermove", ev => {
  if (ev.pointerId !== downPointerId) return;
  if (!movedPastThreshold) {
    const dx = ev.clientX - downX, dy = ev.clientY - downY;
    if (Math.hypot(dx, dy) < DRAG_THRESHOLD) return;
    // real drag confirmed: capture pointer now so a click never fires on
    // the element under the cursor at pointerup (setPointerCapture would
    // otherwise retarget click on every mousedown, silently breaking node
    // clicks - only engage it once this is an actual pan, not a tap)
    movedPastThreshold = true;
    dragging = true;
    svg.classList.add("grabbing");
    svg.setPointerCapture(downPointerId);
  }
  if (!dragging) return;
  tx += ev.clientX - lastX; ty += ev.clientY - lastY;
  lastX = ev.clientX; lastY = ev.clientY;
  applyTransform();
});
["pointerup", "pointercancel"].forEach(evt =>
  svg.addEventListener(evt, () => {
    dragging = false; movedPastThreshold = false; downPointerId = null;
    svg.classList.remove("grabbing");
  })
);

document.getElementById("zoom-in").addEventListener("click", () => { scale = Math.min(4, scale * 1.25); applyTransform(); });
document.getElementById("zoom-out").addEventListener("click", () => { scale = Math.max(0.35, scale / 1.25); applyTransform(); });
document.getElementById("zoom-reset").addEventListener("click", () => { scale = 1; tx = 0; ty = 0; applyTransform(); });
</script>
"""

html = html.replace("__DATA_JSON__", data_json)
html = html.replace("__W__", str(W)).replace("__H__", str(H))

(HERE / "explorer.html").write_text(html)
print(f"wrote {HERE / 'explorer.html'}  ({len(html)} bytes)")
