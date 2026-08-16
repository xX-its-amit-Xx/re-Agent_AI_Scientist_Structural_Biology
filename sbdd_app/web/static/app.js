const state = {
  slug: null,
  data: null,
  es: null,
  selectedNode: null,
  viewer3d: null,
  lastViewerCmdCount: -1,
};

const NODE_COLORS = {
  Concept: "#46c2b9",
  Method: "#e0a339",
  Paper: "#7d9ce8",
  Protein: "#d9604f",
  Compound: "#b07de8",
};

async function api(path, opts) {
  const res = await fetch(path, opts);
  if (!res.ok) throw new Error(`${path}: ${res.status}`);
  return res.json();
}

async function refreshProjectList(selectSlug) {
  const projects = await api("/api/projects");
  const sel = document.getElementById("project-select");
  sel.innerHTML = "";
  if (projects.length === 0) {
    const opt = document.createElement("option");
    opt.textContent = "(no projects)";
    opt.value = "";
    sel.appendChild(opt);
    state.slug = null;
    renderEmpty();
    return;
  }
  for (const p of projects) {
    const opt = document.createElement("option");
    opt.value = p.slug;
    opt.textContent = p.name;
    sel.appendChild(opt);
  }
  const target = selectSlug && projects.some(p => p.slug === selectSlug)
    ? selectSlug
    : projects[0].slug;
  sel.value = target;
  await switchProject(target);
}

async function switchProject(slug) {
  if (state.es) { state.es.close(); state.es = null; }
  state.slug = slug;
  state.selectedNode = null;
  state.viewer3d = null;
  state.lastViewerCmdCount = -1;
  await loadState();
  connectEvents();
}

async function loadState() {
  if (!state.slug) return;
  state.data = await api(`/api/projects/${state.slug}/state`);
  renderAll();
}

function connectEvents() {
  if (!state.slug) return;
  const dot = document.getElementById("conn-status");
  const es = new EventSource(`/api/projects/${state.slug}/events`);
  es.onopen = () => { dot.classList.remove("dot-off"); dot.classList.add("dot-on"); };
  es.onerror = () => { dot.classList.remove("dot-on"); dot.classList.add("dot-off"); };
  es.onmessage = () => { loadState(); };
  es.addEventListener("capture", ev => {
    const { request_id } = JSON.parse(ev.data);
    capturePreviewNow(request_id);
  });
  state.es = es;
}

// ephemeral: grab whatever the live viewer shows RIGHT NOW and ship it to
// the staging endpoint - unlike replayViewerCommands' "snapshot" op, this is
// never written into viewer.commands, so it can't accumulate/replay
function capturePreviewNow(requestId) {
  if (!state.viewer3d) return;
  state.viewer3d.render();
  const dataUri = state.viewer3d.pngURI();
  fetch(`/api/projects/${state.slug}/viewer/capture_preview/${requestId}/upload`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ data_uri: dataUri }),
  });
}

function renderEmpty() {
  const tpl = document.getElementById("tpl-empty-project");
  for (const id of ["panel-literature", "panel-playground", "panel-reports"]) {
    const el = document.getElementById(id);
    el.innerHTML = "";
    el.appendChild(tpl.content.cloneNode(true));
  }
}

function renderAll() {
  if (!state.data) return;
  renderLiterature();
  renderPlayground();
  renderReports();
  renderStructure();
}

/* ---------------- Literature tab ---------------- */

function renderLiterature() {
  const svg = document.getElementById("lit-graph");
  svg.innerHTML = "";
  const detail = document.getElementById("lit-detail");
  const { nodes, edges } = state.data.literature;

  if (nodes.length === 0) {
    detail.innerHTML = '<p class="muted">No knowledge graph nodes yet. Ask Claude to add some via kg_add_node.</p>';
    return;
  }

  const W = 1200, H = 900, PAD = 60;
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);

  const byId = {};
  for (const n of nodes) byId[n.id] = n;
  const px = n => PAD + (n.x ?? 0.5) * (W - 2 * PAD);
  const py = n => PAD + (n.y ?? 0.5) * (H - 2 * PAD);

  const gEdges = document.createElementNS("http://www.w3.org/2000/svg", "g");
  const gNodes = document.createElementNS("http://www.w3.org/2000/svg", "g");

  for (const e of edges) {
    const s = byId[e.source], t = byId[e.target];
    if (!s || !t) continue;
    const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
    line.setAttribute("class", "lg-edge");
    line.setAttribute("x1", px(s)); line.setAttribute("y1", py(s));
    line.setAttribute("x2", px(t)); line.setAttribute("y2", py(t));
    line.dataset.source = e.source; line.dataset.target = e.target;
    gEdges.appendChild(line);
  }

  for (const n of nodes) {
    const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
    g.setAttribute("class", "lg-node");
    g.setAttribute("transform", `translate(${px(n)},${py(n)})`);
    g.dataset.id = n.id;
    const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    circle.setAttribute("r", 9);
    circle.setAttribute("fill", NODE_COLORS[n.type] || "#888");
    g.appendChild(circle);
    const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
    text.setAttribute("x", 13);
    text.setAttribute("y", 4);
    text.textContent = n.label;
    g.appendChild(text);
    g.addEventListener("click", () => selectNode(n.id));
    gNodes.appendChild(g);
  }

  svg.appendChild(gEdges);
  svg.appendChild(gNodes);
  setupPanZoom(svg, gEdges, gNodes);

  if (state.selectedNode) selectNode(state.selectedNode, true);
  else detail.innerHTML = '<p class="muted">Select a node to see its summary and source.</p>';
}

function selectNode(id, skipRerender) {
  state.selectedNode = id;
  const { nodes, edges } = state.data.literature;
  const n = nodes.find(x => x.id === id);
  if (!n) return;

  document.querySelectorAll(".lg-node").forEach(el => {
    el.classList.toggle("selected", el.dataset.id === id);
  });

  const detail = document.getElementById("lit-detail");
  const sourceHtml = n.source_url
    ? `<a href="${n.source_url}" target="_blank" rel="noopener">${n.source_url}</a>`
    : `<span class="source-note">${n.source_note || "General knowledge - no single source."}</span>`;

  const related = edges.filter(e => e.source === id || e.target === id);
  const relHtml = related.map(e => {
    const dir = e.source === id
      ? `&#8594; <b>${e.relation}</b> &#8594; ${e.target}`
      : `${e.source} &#8594; <b>${e.relation}</b> &#8594;`;
    return `<li>${dir}</li>`;
  }).join("");

  detail.innerHTML = `
    <span class="node-type-badge">${n.type}</span>
    <h3>${n.label}</h3>
    <div class="node-summary">${n.summary}</div>
    <div class="source-block">${sourceHtml}</div>
    ${related.length ? `<div class="edge-list"><b>Relations</b><ul>${relHtml}</ul></div>` : ""}
  `;
}

function setupPanZoom(svg, gEdges, gNodes) {
  let tx = 0, ty = 0, scale = 1;
  let dragging = false, movedPastThreshold = false;
  let downX = 0, downY = 0, downPointerId = null;
  const DRAG_THRESHOLD = 4;
  const apply = () => {
    const t = `translate(${tx}px,${ty}px) scale(${scale})`;
    gEdges.style.transform = t;
    gNodes.style.transform = t;
  };
  svg.addEventListener("pointerdown", ev => {
    downX = ev.clientX; downY = ev.clientY; downPointerId = ev.pointerId;
    movedPastThreshold = false; dragging = false;
  });
  svg.addEventListener("pointermove", ev => {
    if (ev.pointerId !== downPointerId) return;
    if (!movedPastThreshold) {
      if (Math.hypot(ev.clientX - downX, ev.clientY - downY) < DRAG_THRESHOLD) return;
      movedPastThreshold = true; dragging = true;
      svg.classList.add("grabbing");
      svg.setPointerCapture(downPointerId);
    }
    if (!dragging) return;
    tx += ev.movementX; ty += ev.movementY;
    apply();
  });
  ["pointerup", "pointercancel"].forEach(evt => svg.addEventListener(evt, () => {
    dragging = false; movedPastThreshold = false; downPointerId = null;
    svg.classList.remove("grabbing");
  }));
  svg.addEventListener("wheel", ev => {
    ev.preventDefault();
    scale = Math.min(3, Math.max(0.3, scale * (ev.deltaY < 0 ? 1.1 : 0.9)));
    apply();
  }, { passive: false });
}

/* ---------------- Playground tab ---------------- */

function renderPlayground() {
  const feed = document.getElementById("pg-feed");
  const items = state.data.playground;
  if (items.length === 0) {
    feed.innerHTML = '<p class="muted">Nothing here yet. Ask Claude to drop things in via playground_add_text / playground_add_image.</p>';
    return;
  }
  feed.innerHTML = items.map(it => {
    const ts = new Date(it.ts * 1000).toLocaleString();
    const img = it.asset ? `<img src="/assets/${it.asset}" alt="${it.title}" />` : "";
    return `
      <div class="pg-card">
        <div class="pg-card-head">
          <span class="pg-kind">${it.kind}</span>
          <span class="pg-title">${it.title}</span>
          <span class="pg-ts">${ts}</span>
        </div>
        ${it.body ? `<div class="pg-body">${escapeHtml(it.body)}</div>` : ""}
        ${img}
      </div>
    `;
  }).join("");
}

/* ---------------- Live structure widget (inside Playground) ---------------- */
// No dedicated "Structure" tab on purpose - an always-present static tab
// isn't really agent-controlled, it's just a page. The viewer only shows up
// once something has actually been loaded into it (viewer_load), living at
// the top of Playground instead.

function renderStructure() {
  const commands = state.data.viewer.commands;
  document.getElementById("struct-widget").classList.toggle("visible", commands.length > 0);
  if (commands.length === state.lastViewerCmdCount) return; // nothing new, leave the live view alone
  state.lastViewerCmdCount = commands.length;
  replayViewerCommands(commands);
}

function initViewer3d() {
  const el = document.getElementById("viewer3d");
  el.innerHTML = "";
  return $3Dmol.createViewer(el, { backgroundColor: "#f4f4f4" });
}

async function replayViewerCommands(commands) {
  const viewer = initViewer3d();
  state.viewer3d = viewer;
  for (const cmd of commands) {
    await applyViewerCommand(viewer, cmd);
  }
  viewer.render();
}

// 3Dmol wants resi/chain as an array (or a single "100-110" range string) -
// an LLM will naturally write "182,193,197" or "182+193+197" (PyMOL habit),
// which 3Dmol silently matches zero atoms against. Normalize both spellings.
function normalizeSelector(sel) {
  if (!sel) return sel;
  const out = { ...sel };
  for (const key of ["resi", "chain"]) {
    if (typeof out[key] === "string" && /[,+\s]/.test(out[key])) {
      out[key] = out[key].split(/[,+\s]+/).filter(Boolean).map(tok =>
        /^-?\d+$/.test(tok) ? parseInt(tok, 10) : tok
      );
    }
  }
  return out;
}

function applyViewerCommand(viewer, cmd) {
  const { op, args } = cmd;
  return new Promise(resolve => {
    try {
      if (op === "load") {
        if (args.pdb_id) {
          $3Dmol.download(`pdb:${args.pdb_id.trim().toUpperCase()}`, viewer, {}, () => {
            viewer.setStyle({}, { cartoon: { color: "spectrum" } });
            viewer.zoomTo();
            viewer.render();
            resolve();
          });
        } else if (args.url) {
          fetch(args.url).then(r => r.text()).then(data => {
            viewer.addModel(data, args.format || "pdb");
            viewer.setStyle({}, { cartoon: { color: "spectrum" } });
            viewer.zoomTo();
            viewer.render();
            resolve();
          });
        } else resolve();
      } else if (op === "style") {
        viewer.setStyle(normalizeSelector(args.selector) || {}, args.style || {});
        resolve();
      } else if (op === "surface") {
        viewer.addSurface($3Dmol.SurfaceType.VDW, { opacity: args.opacity ?? 0.7, color: args.color }, normalizeSelector(args.selector) || {});
        resolve();
      } else if (op === "zoom") {
        const sel = normalizeSelector(args.selector) || {};
        // zoomTo() on a selector that matches nothing leaves the camera in a
        // broken state (blank canvas, not just "didn't zoom") - fall back to
        // framing the whole structure instead of silently breaking the view.
        const matched = viewer.selectedAtoms(sel);
        viewer.zoomTo(matched.length ? sel : {});
        resolve();
      } else if (op === "label") {
        const atoms = viewer.selectedAtoms(normalizeSelector(args.selector) || {});
        if (atoms.length) {
          viewer.addLabel(args.text, {
            position: atoms[0],
            backgroundColor: "#111820",
            backgroundOpacity: 0.85,
            fontColor: "white",
            fontSize: 12,
          });
        }
        resolve();
      } else if (op === "spin") {
        viewer.spin(args.on ? (args.axis || "y") : false);
        resolve();
      } else if (op === "snapshot") {
        // style/surface/zoom ops above don't render individually (only the
        // end of replayViewerCommands does) - force a render so the capture
        // reflects everything applied so far, not a stale/blank canvas.
        viewer.render();
        const dataUri = viewer.pngURI();
        fetch(`/api/projects/${state.slug}/viewer/snapshot/${args.request_id}/upload`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ data_uri: dataUri, title: args.title, caption: args.caption }),
        }).finally(resolve);
      } else {
        resolve();
      }
    } catch (err) {
      console.warn("viewer command failed", cmd, err);
      resolve();
    }
  });
}

document.getElementById("struct-load-btn").addEventListener("click", async () => {
  const id = document.getElementById("struct-pdb-input").value.trim();
  if (!id || !state.slug) return;
  await api(`/api/projects/${state.slug}/viewer/load`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pdb_id: id }),
  });
});

document.getElementById("struct-reset-btn").addEventListener("click", async () => {
  if (!state.slug) return;
  await api(`/api/projects/${state.slug}/viewer/reset`, { method: "POST" });
});

/* ---------------- Reports tab ---------------- */

function renderReports() {
  const list = document.getElementById("stage-list");
  list.innerHTML = state.data.stages.map(s => {
    const questions = s.questions.length
      ? `<div><b>Questions</b><ul>${s.questions.map(q => `<li>${q}</li>`).join("")}</ul></div>` : "";
    const tools = `<div><b>Tools</b><ul>${s.tools.map(t => `<li>${t}</li>`).join("")}</ul></div>`;
    return `
      <div class="stage-card">
        <div class="stage-head">
          <span class="stage-num">S${s.id}</span>
          <span class="stage-name">${s.name}</span>
          <span class="stage-owner">${s.owner}</span>
          <span class="pill ${s.status}">${s.status.replace("_", " ")}</span>
        </div>
        <div class="stage-body">
          <div class="stage-meta">${questions}${tools}</div>
          ${reportPreviewHtml()}
        </div>
      </div>
    `;
  }).join("");
}

function reportPreviewHtml() {
  const report = state.data.report;
  if (!report) {
    return `<div class="report-preview-empty">No report generated yet - ask Claude to run generate_report. It'll track progress (complete/incomplete per step) right here once it exists.</div>`;
  }
  // cache-bust with generated_ts so re-generating shows the new PDF, not a stale cached one
  const url = `/assets/${report.pdf_path}?v=${Math.round(report.generated_ts)}`;
  const when = new Date(report.generated_ts * 1000).toLocaleString();
  return `
    <a class="report-preview-link" href="${url}" target="_blank" rel="noopener">
      <div class="report-preview-head">
        <span>Report - generated ${when}</span>
        <span class="open-hint">open in new tab &#8599;</span>
      </div>
      <iframe src="${url}" tabindex="-1"></iframe>
    </a>
  `;
}

function escapeHtml(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

/* ---------------- chrome ---------------- */

document.querySelectorAll(".tab-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".panel").forEach(p => p.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById(`panel-${btn.dataset.tab}`).classList.add("active");
    if (btn.dataset.tab === "playground" && state.data && state.data.viewer.commands.length) {
      // #panel-playground (which now hosts the viewer) was display:none
      // until just now, so any viewer created while hidden got a 0x0 canvas
      // - force a rebuild now that it's actually visible
      replayViewerCommands(state.data.viewer.commands);
      state.lastViewerCmdCount = state.data.viewer.commands.length;
    }
  });
});

document.getElementById("project-select").addEventListener("change", ev => {
  switchProject(ev.target.value);
});

document.getElementById("new-project-btn").addEventListener("click", async () => {
  const name = prompt("New project name (e.g. PXR, CYP3A4):");
  if (!name) return;
  const p = await api("/api/projects", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  await refreshProjectList(p.slug);
});

refreshProjectList();
