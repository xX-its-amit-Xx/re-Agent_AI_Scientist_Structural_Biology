"""Render a knowledge-graph ego view as a single self-contained HTML file.

Design decisions and why, since they are the difference between a useful figure
and a hairball:

**Cytoscape.js, inlined.** 435 KB MIT UMD with zero dependencies, vendored at
``assets/vendor/cytoscape.min.js``. It is the only mainstream library where the
three things we need are all built in: automatic fanning of *parallel edges*
(two proteins related on four different axes must show four distinguishable
edges), a genuine concentric/ego layout, and a selector engine that makes
"isolate one predicate" a one-liner. No network access at runtime, which the
publish target requires.

**Colour encodes a predicate *family*, not a predicate.** The vocabulary has ~27
predicates and the ceiling for a colour-blind-safe categorical palette is about
8. So the 27 collapse to 8 families on an Okabe-Ito palette, a dash pattern
separates predicates inside a family, and the exact predicate is on hover. This
is the single most important legibility decision in the file.

**Edge width is normalised per axis.** A TM-score of 0.8 and a Tanimoto of 0.8
are not the same claim, and drawing them at the same thickness would silently
misrepresent one of them. Each axis declares its ``score_range`` and widths are
normalised inside it.

**Evidence edges are hidden by default.** Every claim links to its sources, so
``SUPPORTED_BY`` edges outnumber everything else and bury the signal. They are
one checkbox away, never gone.

**Nothing is drawn that a reader did not ask for.** The default view is the focal
node's k-hop neighbourhood with a per-node fan-out cap. Full-graph rendering at
5k nodes is available and clearly labelled as such.
"""

from __future__ import annotations

import html
import json
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from reagent.contracts import (
    AxisSpec,
    ColorMap,
    NodeType,
    Predicate,
    Visualization,
    VizKind,
    VizMedium,
)
from reagent.contracts.kg import (
    FAMILY_COLOR,
    HIDDEN_BY_DEFAULT,
    dash_for,
    family_of,
    visual_encoding_summary,
)
from reagent.kg.store import KGStore

VENDOR_REL = Path("assets/vendor/cytoscape.min.js")

#: Node fills. Deliberately muted so edges — which carry the science — dominate.
NODE_COLOR: dict[str, str] = {
    NodeType.PROTEIN.value: "#1f6f8b",
    NodeType.STRUCTURE.value: "#3d8ea8",
    NodeType.POCKET.value: "#7fb2c4",
    NodeType.RESIDUE.value: "#b8d4dd",
    NodeType.MOTIF.value: "#8d6cab",
    NodeType.COMPOUND.value: "#2e8b57",
    NodeType.FRAGMENT.value: "#6bbf8a",
    NodeType.ASSAY.value: "#b8a06b",
    NodeType.DATASET.value: "#6A3D9A",
    NodeType.PAPER.value: "#9a9a9a",
    NodeType.METHOD.value: "#c4622d",
    NodeType.PIPELINE_STEP.value: "#e08a4a",
    NodeType.ANALOGY.value: "#d4a017",
    NodeType.DOMAIN.value: "#e0c060",
    NodeType.FAMILY.value: "#5a6b8c",
}

#: Distinct silhouettes as a redundant channel for node type, so the picture
#: survives greyscale printing and colour-blind readers.
NODE_SHAPE: dict[str, str] = {
    NodeType.PROTEIN.value: "ellipse",
    NodeType.STRUCTURE.value: "round-rectangle",
    NodeType.POCKET.value: "diamond",
    NodeType.RESIDUE.value: "triangle",
    NodeType.MOTIF.value: "hexagon",
    NodeType.COMPOUND.value: "round-diamond",
    NodeType.FRAGMENT.value: "vee",
    NodeType.ASSAY.value: "rectangle",
    NodeType.DATASET.value: "round-octagon",
    NodeType.PAPER.value: "round-tag",
    NodeType.METHOD.value: "octagon",
    NodeType.PIPELINE_STEP.value: "round-hexagon",
    NodeType.ANALOGY.value: "star",
    NodeType.DOMAIN.value: "pentagon",
    NodeType.FAMILY.value: "barrel",
}

_CONF_OPACITY = {
    "established": 1.0,
    "supported": 0.8,
    "tentative": 0.55,
    "speculative": 0.32,
}


@dataclass
class EgoSubgraph:
    """The extracted neighbourhood, plus an honest record of what was left out."""

    nodes: list[dict[str, Any]] = field(default_factory=list)
    edges: list[dict[str, Any]] = field(default_factory=list)
    depth: dict[str, int] = field(default_factory=dict)
    truncated: dict[str, int] = field(default_factory=dict)
    n_edges_dropped: int = 0

    @property
    def n_elements(self) -> int:
        return len(self.nodes) + len(self.edges)

    def truncation_note(self) -> str:
        if not self.truncated and not self.n_edges_dropped:
            return "Complete neighbourhood — nothing was dropped."
        parts = []
        if self.truncated:
            worst = sorted(self.truncated.items(), key=lambda kv: -kv[1])[:3]
            parts.append(
                "fan-out capped at "
                + ", ".join(f"{nid} (+{n} hidden)" for nid, n in worst)
            )
        if self.n_edges_dropped:
            parts.append(f"{self.n_edges_dropped} edges outside the depth limit")
        return "Truncated: " + "; ".join(parts) + "."


def extract_ego(
    store: KGStore,
    focal: str,
    *,
    max_depth: int = 2,
    max_fanout: int = 30,
    min_confidence_rank: int = 0,
) -> EgoSubgraph:
    """Breadth-first neighbourhood extraction with a per-node fan-out cap.

    The cap is what keeps a promiscuous hub from swamping the picture. Which
    edges it dropped is recorded rather than silently discarded — a figure that
    hides its own truncation reads as "this is everything", which is a lie.
    """
    con = store.connect()
    try:
        adj: dict[str, list[dict[str, Any]]] = defaultdict(list)
        rows = con.execute(
            "SELECT src, predicate, dst, confidence, conf_rank, attrs_json, n_evidence,"
            " evidence_json, asserted_by FROM edges WHERE conf_rank >= ?",
            (min_confidence_rank,),
        ).fetchall()
        for r in rows:
            rec = dict(r)
            adj[rec["src"]].append(rec)
            adj[rec["dst"]].append(rec)

        node_rows = {
            r["id"]: dict(r)
            for r in con.execute("SELECT id, type, label, attrs_json FROM nodes").fetchall()
        }
    finally:
        con.close()

    if focal not in node_rows:
        raise KeyError(
            f"focal node {focal!r} is not in the graph. Present node ids include: "
            f"{sorted(node_rows)[:5]}{'...' if len(node_rows) > 5 else ''}"
        )

    out = EgoSubgraph()
    out.depth[focal] = 0
    seen_nodes = {focal}
    seen_edges: set[tuple[str, str, str]] = set()
    queue: deque[str] = deque([focal])

    while queue:
        cur = queue.popleft()
        d = out.depth[cur]
        if d >= max_depth:
            continue
        # Strongest first, so a cap keeps the most informative edges.
        cand = sorted(
            adj.get(cur, []),
            key=lambda r: (-r["conf_rank"], -_best_numeric(r["attrs_json"])),
        )
        kept = 0
        for r in cand:
            key = (r["src"], r["predicate"], r["dst"])
            if key in seen_edges:
                continue
            if kept >= max_fanout:
                out.truncated[cur] = out.truncated.get(cur, 0) + 1
                continue
            other = r["dst"] if r["src"] == cur else r["src"]
            if other not in node_rows:
                continue
            seen_edges.add(key)
            kept += 1
            out.edges.append(r)
            if other not in seen_nodes:
                seen_nodes.add(other)
                out.depth[other] = d + 1
                queue.append(other)

    out.nodes = [node_rows[n] for n in seen_nodes if n in node_rows]
    # Edges whose far endpoint fell outside the depth horizon are not drawn.
    inside = {n["id"] for n in out.nodes}
    before = len(out.edges)
    out.edges = [e for e in out.edges if e["src"] in inside and e["dst"] in inside]
    out.n_edges_dropped = before - len(out.edges)
    return out


def _best_numeric(attrs_json: str | None) -> float:
    try:
        vals = [v for v in json.loads(attrs_json or "{}").values() if isinstance(v, (int, float))]
    except json.JSONDecodeError:
        return 0.0
    return max(vals) if vals else 0.0


def _normalised_width(predicate: str, attrs: dict[str, Any], axes: list[AxisSpec]) -> float:
    """Map an axis score into 1-8 px inside that axis's own declared range."""
    for a in axes:
        if a.predicate == predicate and a.score_key in attrs:
            raw = attrs[a.score_key]
            if not isinstance(raw, (int, float)):
                continue
            lo, hi = a.score_range
            span = (hi - lo) or 1.0
            frac = min(1.0, max(0.0, (float(raw) - lo) / span))
            return round(1.2 + 6.8 * frac, 2)
    # No declared axis for this predicate: draw thin, so an unscored edge never
    # looks stronger than a measured one.
    return 1.2


def build_elements(
    ego: EgoSubgraph, axes: list[AxisSpec], focal: str
) -> tuple[list[dict], list[dict], dict[str, Any]]:
    """Cytoscape element lists plus the legend payload."""
    cy_nodes = []
    degree: dict[str, int] = defaultdict(int)
    for e in ego.edges:
        degree[e["src"]] += 1
        degree[e["dst"]] += 1

    for n in ego.nodes:
        try:
            attrs = json.loads(n["attrs_json"] or "{}")
        except json.JSONDecodeError:
            attrs = {}
        cy_nodes.append(
            {
                "data": {
                    "id": n["id"],
                    "label": n["label"],
                    "ntype": n["type"],
                    "color": NODE_COLOR.get(n["type"], "#888888"),
                    "shape": NODE_SHAPE.get(n["type"], "ellipse"),
                    "depth": ego.depth.get(n["id"], 9),
                    "deg": min(degree.get(n["id"], 1), 40),
                    "size": 14 + 2.2 * min(degree.get(n["id"], 1), 18),
                    "isFocal": 1 if n["id"] == focal else 0,
                    "attrs": attrs,
                }
            }
        )

    cy_edges = []
    families_present: set[str] = set()
    predicates_present: dict[str, str] = {}
    # Curvature index so parallel edges between one pair fan out instead of overlapping.
    pair_count: dict[tuple[str, str], int] = defaultdict(int)

    for e in ego.edges:
        try:
            attrs = json.loads(e["attrs_json"] or "{}")
        except json.JSONDecodeError:
            attrs = {}
        try:
            pred = Predicate(e["predicate"])
        except ValueError:
            continue
        fam = family_of(pred)
        families_present.add(fam.value)
        predicates_present[pred.value] = fam.value

        pair = tuple(sorted((e["src"], e["dst"])))
        k = pair_count[pair]
        pair_count[pair] += 1

        try:
            evidence = json.loads(e["evidence_json"] or "[]")
        except json.JSONDecodeError:
            evidence = []

        dash = dash_for(pred)
        cy_edges.append(
            {
                "data": {
                    "id": f"{e['src']}|{e['predicate']}|{e['dst']}",
                    "source": e["src"],
                    "target": e["dst"],
                    "predicate": pred.value,
                    "family": fam.value,
                    "color": FAMILY_COLOR[fam],
                    "width": _normalised_width(pred.value, attrs, axes),
                    "opacity": _CONF_OPACITY.get(e["confidence"], 0.5),
                    "confidence": e["confidence"],
                    "dash": dash or [],
                    "hasDash": 1 if dash else 0,
                    "fan": k,
                    "attrs": attrs,
                    "nEvidence": e["n_evidence"],
                    "evidence": evidence[:6],
                    "assertedBy": e["asserted_by"],
                    "hidden": 1 if fam in HIDDEN_BY_DEFAULT else 0,
                }
            }
        )

    legend = {
        "families": [
            {"name": f, "color": FAMILY_COLOR[fam]}
            for fam in FAMILY_COLOR
            if (f := fam.value) in families_present
        ],
        "predicates": sorted(
            ({"name": p, "family": f} for p, f in predicates_present.items()),
            key=lambda d: (d["family"], d["name"]),
        ),
        "nodeTypes": sorted(
            {
                n["data"]["ntype"]: {
                    "name": n["data"]["ntype"],
                    "color": n["data"]["color"],
                    "shape": n["data"]["shape"],
                }
                for n in cy_nodes
            }.values(),
            key=lambda d: d["name"],
        ),
        "hiddenByDefault": sorted(f.value for f in HIDDEN_BY_DEFAULT),
    }
    return cy_nodes, cy_edges, legend


def render(
    store: KGStore,
    focal: str,
    axes: list[AxisSpec],
    out_path: Path,
    *,
    title: str = "Knowledge graph",
    subtitle: str = "",
    max_depth: int = 2,
    max_fanout: int = 30,
    repo_root: Path | None = None,
) -> tuple[Path, Visualization]:
    """Write the HTML and return it alongside its contract object.

    Returning the ``Visualization`` here rather than leaving it to the caller is
    deliberate: the encoding declared in the report is then generated by the same
    code that draws the picture, so the two cannot drift apart.
    """
    repo_root = Path(repo_root or Path.cwd())
    vendor = repo_root / VENDOR_REL
    if not vendor.is_file():
        raise FileNotFoundError(
            f"{VENDOR_REL} is missing. Run `reagent assets fetch` to vendor "
            "cytoscape.min.js — the page must inline it because the publish target "
            "blocks external hosts."
        )

    ego = extract_ego(store, focal, max_depth=max_depth, max_fanout=max_fanout)
    cy_nodes, cy_edges, legend = build_elements(ego, axes, focal)

    focal_label = next(
        (n["data"]["label"] for n in cy_nodes if n["data"]["id"] == focal), focal
    )
    payload = {
        "nodes": cy_nodes,
        "edges": cy_edges,
        "legend": legend,
        "focal": focal,
        "focalLabel": focal_label,
        "maxDepth": max_depth,
        "truncation": ego.truncation_note(),
        "axes": [
            {"name": a.name, "predicate": a.predicate, "scoreKey": a.score_key,
             "range": list(a.score_range), "question": a.question}
            for a in axes
        ],
    }

    doc = _HTML.replace("/*__CYTOSCAPE__*/", vendor.read_text(encoding="utf-8"))
    doc = doc.replace("/*__DATA__*/", json.dumps(payload, separators=(",", ":")))
    doc = doc.replace("__TITLE__", html.escape(title))
    doc = doc.replace("__SUBTITLE__", html.escape(subtitle or ego.truncation_note()))
    doc = doc.replace("__FOCAL_LABEL__", html.escape(str(focal_label)))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    # newline="" keeps LF endings on Windows. Without it Python's text mode rewrites
    # every \n to \r\n, which inflates a 475 KB page by several KB and breaks any
    # downstream tool that greps the inlined payload with an LF-anchored pattern.
    with out_path.open("w", encoding="utf-8", newline="") as fh:
        fh.write(doc)

    try:
        rel = str(out_path.relative_to(repo_root)).replace("\\", "/")
    except ValueError:
        rel = str(out_path)

    # Declared here so the report's legend is generated by the same code that
    # paints the edges. secondary_channel is not a formality: colour alone would
    # be at its discriminability limit, and dash pattern genuinely carries the
    # within-family distinction.
    family_map = ColorMap(
        channel="edge_stroke",
        data_field="edge.predicate_family",
        scale_type="categorical",
        mapping={f["name"]: f["color"] for f in legend["families"]},
        secondary_channel="edge_dash_pattern",
    )

    viz = Visualization(
        id="V-KG-EGO",
        kind=VizKind.KG_SUBGRAPH,
        medium=VizMedium.HTML_SELF_CONTAINED,
        title=title,
        question=(
            f"Which entities are closest to {focal_label} on each similarity axis, "
            "and how strong is each relationship?"
        ),
        takeaway=(
            f"{len(cy_nodes)} entities within {max_depth} hops, connected by "
            f"{len(cy_edges)} typed edges across {len(legend['families'])} predicate "
            f"families. {ego.truncation_note()}"
        ),
        path=rel,
        reads_from=["kg/nodes.jsonl", "kg/edges.jsonl"],
        encoding=visual_encoding_summary(),
        color_maps=[family_map],
        interactive=True,
        focal_node=focal,
        n_elements=ego.n_elements,
        alt_text=(
            f"An interactive ego network centred on {focal_label}. Concentric rings are "
            f"graph distance; node shape and colour encode entity type; edge colour "
            f"encodes one of {len(legend['families'])} predicate families with dash "
            "pattern separating predicates inside a family; edge thickness is the "
            "similarity score normalised within its axis; edge opacity is confidence."
        ),
        params={
            "filtered": True,
            "max_depth": max_depth,
            "max_fanout": max_fanout,
            "hidden_by_default": legend["hiddenByDefault"],
            "n_nodes": len(cy_nodes),
            "n_edges": len(cy_edges),
        },
    )
    return out_path, viz


_HTML = r"""<title>__TITLE__</title>
<style>
  :root {
    --bg: #fbfbfa; --panel: #ffffff; --ink: #1a1a1a; --muted: #5c5c5c;
    --line: #dcdcd8; --accent: #0072B2; --focal: #d4491f;
  }
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) {
      --bg: #16171a; --panel: #1e2024; --ink: #e8e8e6; --muted: #9a9a96;
      --line: #32343a; --accent: #56B4E9; --focal: #ff7a4d;
    }
  }
  :root[data-theme="dark"] {
    --bg: #16171a; --panel: #1e2024; --ink: #e8e8e6; --muted: #9a9a96;
    --line: #32343a; --accent: #56B4E9; --focal: #ff7a4d;
  }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--bg); color: var(--ink);
         font: 14px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
  header { padding: 14px 18px 10px; border-bottom: 1px solid var(--line); }
  h1 { margin: 0 0 2px; font-size: 17px; font-weight: 600; letter-spacing: -0.01em; }
  .sub { color: var(--muted); font-size: 12.5px; }
  #wrap { display: flex; height: calc(100vh - 62px); }
  @media (max-width: 780px) { #wrap { flex-direction: column; height: auto; }
                              #cy { height: 60vh; } #side { max-height: none; } }
  #cy { flex: 1; min-width: 0; background: var(--bg); }
  #side { width: 288px; flex-shrink: 0; border-left: 1px solid var(--line);
          background: var(--panel); overflow-y: auto; padding: 12px 14px 40px; }
  h2 { font-size: 11px; text-transform: uppercase; letter-spacing: 0.07em;
       color: var(--muted); margin: 18px 0 7px; font-weight: 600; }
  h2:first-child { margin-top: 0; }
  label { display: flex; align-items: center; gap: 7px; padding: 2px 0;
          font-size: 12.5px; cursor: pointer; }
  input[type=search] { width: 100%; padding: 6px 8px; border: 1px solid var(--line);
      border-radius: 5px; background: var(--bg); color: var(--ink); font-size: 13px; }
  .swatch { width: 22px; height: 0; border-top-width: 3px; border-top-style: solid;
            flex-shrink: 0; }
  .dot { width: 11px; height: 11px; border-radius: 50%; flex-shrink: 0; }
  .row { display: flex; align-items: center; gap: 7px; padding: 2px 0; font-size: 12.5px; }
  button { font: inherit; font-size: 12px; padding: 5px 9px; border: 1px solid var(--line);
      background: var(--bg); color: var(--ink); border-radius: 5px; cursor: pointer; }
  button:hover { border-color: var(--accent); }
  #tip { position: fixed; z-index: 20; max-width: 330px; display: none;
      background: var(--panel); color: var(--ink); border: 1px solid var(--line);
      border-radius: 6px; padding: 9px 11px; font-size: 12.5px; line-height: 1.45;
      box-shadow: 0 6px 22px rgba(0,0,0,.16); pointer-events: none; }
  #tip .p { font-weight: 600; color: var(--accent); }
  #tip .k { color: var(--muted); }
  #tip code { font-size: 11.5px; word-break: break-all; }
  .note { color: var(--muted); font-size: 11.5px; margin-top: 5px; }
  .axis { font-size: 11.5px; color: var(--muted); margin: 0 0 6px; }
  .axis b { color: var(--ink); font-weight: 600; }
</style>

<header>
  <h1>__TITLE__</h1>
  <div class="sub">__SUBTITLE__</div>
</header>
<div id="wrap">
  <div id="cy"></div>
  <div id="side">
    <h2>Find</h2>
    <input type="search" id="q" placeholder="Search label or id…" autocomplete="off">
    <div class="note">Click an edge to isolate its predicate. Click empty space to reset.</div>

    <h2>Predicate families</h2>
    <div id="fams"></div>

    <h2>Entity types</h2>
    <div id="ntypes"></div>

    <h2>Similarity axes</h2>
    <div id="axes"></div>

    <h2>Layout</h2>
    <div style="display:flex; gap:6px; flex-wrap:wrap">
      <button id="btnConcentric">Rings</button>
      <button id="btnForce">Force</button>
      <button id="btnFit">Fit</button>
    </div>

    <h2>Encoding</h2>
    <div class="note" id="enc"></div>
  </div>
</div>
<div id="tip"></div>

<script>/*__CYTOSCAPE__*/</script>
<script>
const DATA = /*__DATA__*/;

// Depth drives the concentric rings; Cytoscape wants "higher = more central".
const maxD = Math.max(1, ...DATA.nodes.map(n => n.data.depth === 9 ? 0 : n.data.depth));

const cy = cytoscape({
  container: document.getElementById('cy'),
  elements: { nodes: DATA.nodes, edges: DATA.edges },
  wheelSensitivity: 0.25,
  hideEdgesOnViewport: DATA.edges.length > 4000,
  textureOnViewport: DATA.nodes.length > 1200,
  style: [
    { selector: 'node', style: {
        'background-color': 'data(color)', 'shape': 'data(shape)',
        'width': 'data(size)', 'height': 'data(size)',
        'label': 'data(label)', 'font-size': 9.5, 'color': 'var(--ink)',
        'text-valign': 'bottom', 'text-margin-y': 3, 'text-outline-width': 2,
        'text-outline-color': 'var(--bg)', 'border-width': 0.8,
        'border-color': 'rgba(0,0,0,.25)', 'min-zoomed-font-size': 7 } },
    { selector: 'node[isFocal = 1]', style: {
        'border-width': 3.5, 'border-color': 'var(--focal)',
        'font-size': 13, 'font-weight': 'bold', 'z-index': 99 } },
    { selector: 'edge', style: {
        'curve-style': 'bezier', 'control-point-step-size': 26,
        'line-color': 'data(color)', 'width': 'data(width)',
        'opacity': 'data(opacity)', 'target-arrow-color': 'data(color)',
        'target-arrow-shape': 'triangle', 'arrow-scale': 0.55 } },
    { selector: 'edge[hasDash = 1]', style: { 'line-style': 'dashed', 'line-dash-pattern': 'data(dash)' } },
    { selector: '.dim',  style: { 'opacity': 0.06, 'z-index': 0 } },
    { selector: '.hide', style: { 'display': 'none' } },
    { selector: '.hit',  style: { 'border-width': 3, 'border-color': 'var(--accent)' } },
  ],
});

// Evidence-family edges start hidden: every claim cites sources, so they would
// otherwise outnumber and bury the substantive edges.
cy.edges().filter(e => e.data('hidden') === 1).addClass('hide');

// Ring spacing scales with the busiest ring. A focal node in a dense graph puts
// most of its neighbours on ring 1, and a fixed minNodeSpacing then packs them
// shoulder to shoulder — legible in the small case, a solid band in the real one.
const ringPop = {};
DATA.nodes.forEach(n => { const d = n.data.depth; ringPop[d] = (ringPop[d] || 0) + 1; });
const busiest = Math.max(...Object.values(ringPop));
const spacing = Math.min(90, Math.max(34, Math.round(34 + busiest * 0.9)));

const layouts = {
  concentric: { name: 'concentric',
                concentric: n => (maxD + 1) - (n.data('depth') === 9 ? maxD : n.data('depth')),
                levelWidth: () => 1, minNodeSpacing: spacing, spacingFactor: 1.35,
                avoidOverlap: true, animate: false, padding: 46 },
  force: { name: 'cose', animate: false, padding: 40, nodeRepulsion: 9000,
           idealEdgeLength: 90, nestingFactor: 0.9, avoidOverlap: true },
};
function runLayout(kind) { cy.layout(layouts[kind]).run(); }
runLayout('concentric');

// ---- legend + filters -------------------------------------------------
const fams = document.getElementById('fams');
DATA.legend.families.forEach(f => {
  const hiddenDefault = DATA.legend.hiddenByDefault.includes(f.name);
  const l = document.createElement('label');
  l.innerHTML = `<input type="checkbox" data-fam="${f.name}" ${hiddenDefault ? '' : 'checked'}>
                 <span class="swatch" style="border-top-color:${f.color}"></span>
                 <span>${f.name}${hiddenDefault ? ' <span class="k">(off)</span>' : ''}</span>`;
  fams.appendChild(l);
});
fams.addEventListener('change', e => {
  const fam = e.target.dataset.fam; if (!fam) return;
  const sel = cy.edges(`[family = "${fam}"]`);
  e.target.checked ? sel.removeClass('hide') : sel.addClass('hide');
});

const nt = document.getElementById('ntypes');
DATA.legend.nodeTypes.forEach(t => {
  const r = document.createElement('div'); r.className = 'row';
  r.innerHTML = `<span class="dot" style="background:${t.color}"></span><span>${t.name}</span>
                 <span class="k" style="margin-left:auto">${t.shape}</span>`;
  nt.appendChild(r);
});

const ax = document.getElementById('axes');
if (DATA.axes.length) {
  DATA.axes.forEach(a => {
    const d = document.createElement('div'); d.className = 'axis';
    d.innerHTML = `<b>${a.name}</b> — ${a.scoreKey} ∈ [${a.range[0]}, ${a.range[1]}]`;
    d.title = a.question; ax.appendChild(d);
  });
} else { ax.innerHTML = '<div class="axis">No axes declared.</div>'; }

document.getElementById('enc').textContent =
  'Ring = graph distance from the focal node · node colour+shape = entity type · ' +
  'edge colour = predicate family · dash = predicate within family · ' +
  'thickness = score normalised within its axis · opacity = confidence.';

// ---- tooltips ---------------------------------------------------------
const tip = document.getElementById('tip');
function showTip(htmlStr, ev) {
  tip.innerHTML = htmlStr; tip.style.display = 'block';
  const e = ev.originalEvent || ev;
  const x = Math.min(e.clientX + 14, window.innerWidth - 350);
  tip.style.left = x + 'px';
  tip.style.top = Math.min(e.clientY + 14, window.innerHeight - tip.offsetHeight - 12) + 'px';
}
const esc = s => String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

cy.on('mouseover', 'edge', ev => {
  const d = ev.target.data();
  const attrs = Object.entries(d.attrs || {}).map(([k, v]) =>
    `<div><span class="k">${esc(k)}</span> ${esc(v)}</div>`).join('');
  const ev_ = (d.evidence || []).map(x =>
    `<div><code>${esc(x.locator || '')}</code>${x.title ? ' — ' + esc(x.title) : ''}</div>`).join('');
  showTip(
    `<div class="p">${esc(d.predicate)}</div>` +
    `<div class="k">${esc(d.source)} → ${esc(d.target)}</div>` +
    (attrs ? `<div style="margin-top:5px">${attrs}</div>` : '') +
    `<div style="margin-top:5px"><span class="k">confidence</span> ${esc(d.confidence)} · ` +
    `<span class="k">sources</span> ${d.nEvidence}</div>` +
    (ev_ ? `<div style="margin-top:5px">${ev_}</div>` : '') +
    `<div class="k" style="margin-top:5px">asserted by ${esc(d.assertedBy || '?')}</div>`, ev);
});
cy.on('mouseover', 'node', ev => {
  const d = ev.target.data();
  const attrs = Object.entries(d.attrs || {}).slice(0, 8).map(([k, v]) =>
    `<div><span class="k">${esc(k)}</span> ${esc(JSON.stringify(v)).slice(0, 90)}</div>`).join('');
  showTip(`<div class="p">${esc(d.label)}</div><div class="k"><code>${esc(d.id)}</code></div>` +
          `<div style="margin-top:4px">${esc(d.ntype)} · degree ${d.deg} · ring ${d.depth}</div>` +
          (attrs ? `<div style="margin-top:5px">${attrs}</div>` : ''), ev);
});
cy.on('mousemove', ev => { if (tip.style.display === 'block') showTip(tip.innerHTML, ev); });
cy.on('mouseout', 'node, edge', () => { tip.style.display = 'none'; });

// ---- isolate by predicate --------------------------------------------
cy.on('tap', 'edge', ev => {
  const p = ev.target.data('predicate');
  cy.elements().addClass('dim');
  const sel = cy.edges(`[predicate = "${p}"]`);
  sel.removeClass('dim'); sel.connectedNodes().removeClass('dim');
});
cy.on('tap', 'node', ev => {
  cy.elements().addClass('dim');
  ev.target.removeClass('dim');
  ev.target.neighborhood().removeClass('dim');
  ev.target.connectedEdges().removeClass('dim');
});
cy.on('tap', ev => { if (ev.target === cy) cy.elements().removeClass('dim'); });

// ---- search -----------------------------------------------------------
document.getElementById('q').addEventListener('input', e => {
  const v = e.target.value.trim().toLowerCase();
  cy.elements().removeClass('dim'); cy.nodes().removeClass('hit');
  if (!v) return;
  const hits = cy.nodes().filter(n =>
    n.data('label').toLowerCase().includes(v) || n.id().toLowerCase().includes(v));
  if (!hits.length) return;
  cy.elements().addClass('dim');
  hits.removeClass('dim').addClass('hit');
  hits.neighborhood().removeClass('dim');
  cy.animate({ fit: { eles: hits, padding: 90 }, duration: 220 });
});

document.getElementById('btnConcentric').onclick = () => runLayout('concentric');
document.getElementById('btnForce').onclick = () => runLayout('force');
document.getElementById('btnFit').onclick = () => cy.animate({ fit: { padding: 40 }, duration: 200 });
</script>
"""
