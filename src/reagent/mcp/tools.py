"""The tools the MCP server exposes.

Design rules, learned from what makes a tool usable by a model rather than merely
callable:

* **Return prose with numbers in it, not raw JSON.** A model reads the text and
  relays it. A wall of JSON gets summarised badly and the caveats get dropped.
* **Every response that contains an estimate says so in the same breath.** If the
  caveat lives in a separate field the model will not carry it through.
* **Suggest the next call.** Ending a response with the two or three tools that
  naturally follow turns a flat tool list into a workflow.
* **Fail with the fix.** An error should name what was wrong and what to try, since
  the model's next action is decided entirely by the error text.
* **Say when a number is a placeholder.** The graph marks unmeasured edges with
  ``illustrative: true``; a tool that renders one without saying so launders a
  placeholder into a finding.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from reagent.contracts import Confidence, ModelReport, Predicate, ProblemSpec
from reagent.contracts.kg import family_of
from reagent.kg import KGStore

REGISTRY: dict[str, Callable[..., str]] = {}
_SCHEMAS: list[dict[str, Any]] = []

REPO = Path.cwd()
FIGURES = Path("docs/figures/mcp")


def tool(name: str, description: str, schema: dict[str, Any]):
    """Register a tool with its JSON Schema."""
    def deco(fn: Callable[..., str]) -> Callable[..., str]:
        REGISTRY[name] = fn
        _SCHEMAS.append({"name": name, "description": description, "inputSchema": schema})
        return fn
    return deco


def tool_schemas() -> list[dict[str, Any]]:
    return list(_SCHEMAS)


def _obj(props: dict, required: list[str] | None = None) -> dict:
    return {
        "type": "object",
        "properties": props,
        "required": required or [],
        "additionalProperties": False,
    }


# Schema shorthands. Spelled out rather than single letters: `I` reads as `l`/`1`
# in most fonts, which ruff rightly flags.
STR = {"type": "string"}
INT = {"type": "integer"}
NUM = {"type": "number"}


def _store(kg: str | None = None) -> KGStore:
    root = Path(kg) if kg else _default_kg()
    if not (root / "nodes.jsonl").is_file():
        raise FileNotFoundError(
            f"no knowledge graph at {root} (expected nodes.jsonl). "
            f"Available graph directories: {_list_graphs() or 'none found under kg/'}. "
            "Pass one as the `kg` argument, or run examples/seed_demo_graph.py to "
            "create a demo graph."
        )
    return KGStore(root)


def _default_kg() -> Path:
    for cand in (Path("kg"), Path("kg/demo")):
        if (cand / "nodes.jsonl").is_file():
            return cand
    return Path("kg")


def _list_graphs() -> list[str]:
    out = []
    base = Path("kg")
    if (base / "nodes.jsonl").is_file():
        out.append("kg")
    if base.is_dir():
        out += [str(p.parent) for p in base.glob("*/nodes.jsonl")]
    return sorted(out)


def _illustrative_warning(attrs: dict) -> str:
    return (
        "  NOTE: this edge is marked illustrative — the number is a placeholder, not a "
        "measurement. Do not present it as a finding.\n"
        if attrs.get("illustrative") else ""
    )


# --------------------------------------------------------------------------
# orientation
# --------------------------------------------------------------------------


@tool(
    "report_list",
    "List the pipeline runs and Model Reports available in this repo, with each "
    "report's stage, headline metrics, and whether it is ready to hand off. Start here.",
    _obj({}),
)
def report_list() -> str:
    reports = sorted(Path("reports").glob("*/*/report.json")) if Path("reports").is_dir() else []
    specs = sorted(Path("reports").glob("*/problem.json")) if Path("reports").is_dir() else []
    if not reports and not specs:
        return (
            "No runs found under reports/. Create one with:\n"
            "  reagent problem new --name '<challenge>' --domain <domain> "
            "--task <task> --target <namespaced-id>\n"
            "Or run examples/seed_demo_report.py for a worked demo."
        )

    lines = []
    for sp in specs:
        spec = ProblemSpec.load(sp)
        lines.append(
            f"Run `{spec.run_id}` — {spec.name}\n"
            f"  domain {spec.domain.value} / task {spec.task_type.value}\n"
            f"  target {spec.primary_target.id} ({spec.primary_target.label})\n"
            f"  metric {spec.metric.name} ({spec.metric.direction.value})\n"
            f"  axes   {', '.join(a.name for a in spec.axes)}"
        )
    for rp in reports:
        try:
            r = ModelReport.load(rp)
        except Exception as exc:
            lines.append(f"  {rp} — UNREADABLE: {exc}")
            continue
        ready = "ready" if (r.handoff and r.handoff.ready) else "NOT ready to hand off"
        metrics = ", ".join(f"{k}={v}" for k, v in list(r.metrics.items())[:5])
        lines.append(
            f"\nReport `{r.report_id}` [{r.stage.value}] — {r.title}\n"
            f"  path      {rp.as_posix()}\n"
            f"  findings  {len(r.findings)} · figures "
            f"{len(r.visuals.visualizations) if r.visuals else 0} · {ready}\n"
            f"  metrics   {metrics or 'none'}\n"
            f"  summary   {r.executive_summary}"
        )
    lines.append(
        "\nNext: `report_read` for a full report, `graph_overview` for the knowledge graph."
    )
    return "\n".join(lines)


@tool(
    "report_read",
    "Read one Model Report in full: its findings with confidence and citations, "
    "limitations, open questions, and handoff. Use after report_list.",
    _obj({"path": {**STR, "description": "Path from report_list, e.g. reports/demo/stage1_literature/report.json"},
          "kind": {"type": "string", "enum": ["all", "findings", "limitations", "handoff", "methods"],
                   "description": "Which section. Default all."}},
         ["path"]),
)
def report_read(path: str, kind: str = "all") -> str:
    r = ModelReport.load(Path(path))
    out = [f"{r.title}  [{r.stage.value}]  run {r.run_id}", f"\n{r.executive_summary}\n"]

    if kind in ("all", "findings"):
        out.append(f"FINDINGS ({len(r.findings)})")
        for f in r.findings:
            out.append(f"\n  {f.id} [{f.kind.value}, {f.confidence.value}]")
            out.append(f"    {f.statement}")
            for ev in f.evidence:
                grey = " (grey literature)" if ev.source_type.is_grey else ""
                ungrounded = " (NOT domain evidence)" if not ev.source_type.is_grounded else ""
                out.append(f"      cite: {ev.source_type.value}{grey}{ungrounded} {ev.locator}"
                           + (f" — {ev.title}" if ev.title else ""))
            if not f.evidence:
                out.append("      cite: none (asserted by the agent)")
            if f.data:
                out.append(f"      data: {json.dumps(f.data, default=str)[:400]}")
    if kind in ("all", "methods") and r.methods:
        out.append(f"\nMETHODS ({len(r.methods)})")
        for m in r.methods:
            flag = "  [FAILED/NOT RUN]" if m.failed else ""
            out.append(f"  {m.skill} via {m.tool or '—'}{flag}: {m.summary}")
            if m.failure_note:
                out.append(f"    {m.failure_note}")
    if kind in ("all", "limitations"):
        out.append("\nLIMITATIONS")
        out += [f"  - {x}" for x in r.limitations] or ["  none recorded"]
        out.append("\nOPEN QUESTIONS")
        out += [f"  - {x}" for x in r.open_questions] or ["  none recorded"]
    if kind in ("all", "handoff") and r.handoff:
        h = r.handoff
        out.append(f"\nHANDOFF to {h.to_stage.value} — {'ready' if h.ready else 'NOT ready'}")
        out += [f"  action: {a}" for a in h.recommended_actions]
        out += [f"  blocked on: {b}" for b in h.blocking_unknowns]
        out.append(f"  payload keys: {sorted(h.payload)}")

    if r.visuals:
        out.append("\nFIGURES")
        for v in r.visuals.ordered():
            out.append(f"  {v.id} [{v.kind.value}] {v.path}")
            out.append(f"    asks: {v.question}")
            out.append(f"    shows: {v.takeaway}")
    if gaps := r.visual_gaps():
        out.append(f"\n  Missing characteristic figures for this stage: {gaps}")
    return "\n".join(out)


@tool(
    "graph_overview",
    "Summarise the knowledge graph: node and edge counts by type, citation coverage, "
    "the most connected entities, and which similarity axes are actually populated.",
    _obj({"kg": {**STR, "description": "Graph directory. Defaults to kg/ or kg/demo/."}}),
)
def graph_overview(kg: str | None = None) -> str:
    st = _store(kg)
    s = st.stats()
    out = [
        f"Knowledge graph at {st.root.as_posix()}",
        f"  {s['n_nodes']} nodes, {s['n_edges']} edges, "
        f"{s['cited_edge_fraction']:.0%} of edges carry a citation",
        "",
        "Nodes by type:",
    ]
    out += [f"  {k:<14} {v}" for k, v in sorted(s["nodes_by_type"].items(), key=lambda kv: -kv[1])]
    out.append("\nEdges by predicate:")
    for k, v in sorted(s["edges_by_predicate"].items(), key=lambda kv: -kv[1]):
        try:
            fam = family_of(Predicate(k)).value
        except ValueError:
            fam = "?"
        out.append(f"  {k:<22} {v:>5}  ({fam})")

    hubs = st.query(
        "SELECT n.id, n.label, n.type, COUNT(*) AS deg FROM nodes n "
        "JOIN edges e ON e.src = n.id OR e.dst = n.id GROUP BY n.id "
        "ORDER BY deg DESC LIMIT 8"
    )
    out.append("\nMost connected entities:")
    out += [f"  {h['label']} ({h['id']}, {h['type']}) — {h['deg']} edges" for h in hubs]

    illus = st.query(
        "SELECT COUNT(*) c FROM edges e JOIN edge_attrs a "
        "ON a.src=e.src AND a.predicate=e.predicate AND a.dst=e.dst "
        "WHERE a.key = 'illustrative'"
    )
    n_illus = illus[0]["c"] if illus else 0
    if n_illus:
        out.append(
            f"\n  WARNING: {n_illus} edges are marked illustrative — those numbers are "
            "placeholders, not measurements. Never report one as a finding."
        )
    out.append("\nNext: `neighbors` to explore an entity, `compare_structures` to see two in 3D.")
    return "\n".join(out)


# --------------------------------------------------------------------------
# exploration
# --------------------------------------------------------------------------


@tool(
    "neighbors",
    "List what an entity is connected to, grouped by relationship type, with scores "
    "and confidence. The main way to explore the graph around a protein or compound.",
    _obj({"node_id": {**STR, "description": "Namespaced id, e.g. uniprot:O75469 or pdb:1M13"},
          "predicate": {**STR, "description": "Optional: restrict to one predicate, e.g. SIMILAR_FOLD_TO"},
          "limit": {**INT, "description": "Max neighbours per relationship. Default 15."},
          "kg": STR},
         ["node_id"]),
)
def neighbors(node_id: str, predicate: str | None = None, limit: int = 15,
              kg: str | None = None) -> str:
    st = _store(kg)
    known = st.node_ids()
    if node_id not in known:
        hits = [n for n in known if node_id.lower() in n.lower()][:8]
        labels = st.query(
            "SELECT id, label FROM nodes WHERE lower(label) LIKE ? LIMIT 8",
            (f"%{node_id.lower()}%",),
        )
        return (
            f"No node {node_id!r} in the graph.\n"
            + (f"Similar ids: {hits}\n" if hits else "")
            + (f"Matching labels: {[(r['id'], r['label']) for r in labels]}\n" if labels else "")
            + "Use `graph_search` to find an entity by name."
        )

    pred = Predicate(predicate) if predicate else None
    rows = st.neighbors(node_id, pred, undirected=True, limit=None)
    if not rows:
        return f"{node_id} has no edges" + (f" with predicate {predicate}" if predicate else "") + "."

    label = st.query("SELECT label, type FROM nodes WHERE id = ?", (node_id,))
    head = f"{label[0]['label']} ({node_id}, {label[0]['type']})" if label else node_id

    by_pred: dict[str, list] = {}
    for r in rows:
        by_pred.setdefault(r["predicate"], []).append(r)

    out = [f"{head} — {len(rows)} edges across {len(by_pred)} relationship types\n"]
    for p, rs in sorted(by_pred.items(), key=lambda kv: -len(kv[1])):
        try:
            fam = family_of(Predicate(p)).value
        except ValueError:
            fam = "?"
        out.append(f"{p}  ({fam}, {len(rs)} edges)")
        for r in rs[:limit]:
            attrs = {k: v for k, v in r["attrs"].items() if k != "illustrative"}
            score = " ".join(f"{k}={v}" for k, v in attrs.items()) or "—"
            arrow = "->" if r["direction"] == "out" else "<-"
            out.append(
                f"  {arrow} {r['other_label']} ({r['other']}, {r['other_type']})"
                f"  [{r['confidence']}, {r['n_evidence']} cites]  {score}"
            )
            out.append(_illustrative_warning(r["attrs"]).rstrip("\n") or "")
        if len(rs) > limit:
            out.append(f"  ... and {len(rs) - limit} more")
        out.append("")
    out = [line for line in out if line != ""] + [""]
    out.append(
        "Next: `explain_edge` for the evidence behind one of these, or "
        "`compare_structures` to view two of them together in 3D."
    )
    return "\n".join(out)


@tool(
    "graph_search",
    "Find entities by name, alias, or id fragment. Use when you know what something "
    "is called but not its namespaced id.",
    _obj({"query": {**STR, "description": "Substring of a label, alias, or id"},
          "node_type": {**STR, "description": "Optional filter, e.g. Protein, Compound, Dataset"},
          "limit": INT, "kg": STR},
         ["query"]),
)
def graph_search(query: str, node_type: str | None = None, limit: int = 20,
                 kg: str | None = None) -> str:
    st = _store(kg)
    q = f"%{query.lower()}%"
    sql = (
        "SELECT n.id, n.label, n.type, n.aliases, "
        "  (SELECT COUNT(*) FROM edges e WHERE e.src=n.id OR e.dst=n.id) AS deg "
        "FROM nodes n WHERE (lower(n.label) LIKE ? OR lower(n.id) LIKE ? "
        "  OR lower(n.aliases) LIKE ?)"
    )
    params: list[Any] = [q, q, q]
    if node_type:
        sql += " AND n.type = ?"
        params.append(node_type)
    sql += " ORDER BY deg DESC LIMIT ?"
    params.append(limit)

    rows = st.query(sql, params)
    if not rows:
        types = st.query("SELECT DISTINCT type FROM nodes ORDER BY type")
        return (
            f"Nothing matching {query!r}"
            + (f" of type {node_type}" if node_type else "")
            + f".\nNode types present: {[t['type'] for t in types]}"
        )
    out = [f"{len(rows)} matches for {query!r}:"]
    for r in rows:
        al = json.loads(r["aliases"] or "[]")
        out.append(f"  {r['label']} ({r['id']}, {r['type']}, {r['deg']} edges)"
                   + (f"  aliases: {', '.join(al[:4])}" if al else ""))
    return "\n".join(out)


@tool(
    "explain_edge",
    "Show everything behind one assertion: its quantitative attributes, confidence, "
    "which skill asserted it, and every citation. Use to check a claim rather than "
    "trusting it.",
    _obj({"src": STR, "predicate": STR, "dst": STR, "kg": STR}, ["src", "predicate", "dst"]),
)
def explain_edge(src: str, predicate: str, dst: str, kg: str | None = None) -> str:
    st = _store(kg)
    try:
        pred = Predicate(predicate)
    except ValueError:
        return (f"{predicate!r} is not in the predicate vocabulary. "
                f"Valid: {sorted(p.value for p in Predicate)}")
    rows = st.query(
        "SELECT * FROM edges WHERE src=? AND predicate=? AND dst=?",
        (src, pred.value, dst),
    )
    if not rows:
        rev = st.query("SELECT 1 FROM edges WHERE src=? AND predicate=? AND dst=?",
                       (dst, pred.value, src))
        hint = (f"\nThe edge exists in the other direction: "
                f"{dst} -{predicate}-> {src}. Try that." if rev else "")
        return f"No edge {src} -{predicate}-> {dst}.{hint}"

    e = rows[0]
    attrs = json.loads(e["attrs_json"] or "{}")
    evidence = json.loads(e["evidence_json"] or "[]")
    out = [
        f"{src} -{predicate}-> {dst}",
        f"  family      {family_of(pred).value}",
        f"  confidence  {e['confidence']}",
        f"  asserted by {e['asserted_by']}" + (f" (run {e['run_id']})" if e["run_id"] else ""),
        f"  attributes  {json.dumps(attrs) if attrs else 'none'}",
    ]
    if attrs.get("illustrative"):
        out.append("  WARNING: illustrative — these numbers are placeholders, not "
                   "measurements. Do not report them as findings.")
    out.append(f"  citations   {len(evidence)}")
    for ev in evidence:
        st_ = ev.get("source_type", "?")
        out.append(f"    [{st_}] {ev.get('locator')}"
                   + (f" — {ev.get('title')}" if ev.get("title") else ""))
        if ev.get("excerpt"):
            out.append(f"        \"{ev['excerpt'][:220]}\"")
    if not evidence:
        out.append("    none — this assertion is uncited. Treat it as unverified.")
    return "\n".join(out)


@tool(
    "graph_query",
    "Run a read-only SQL SELECT against the graph for questions the other tools do "
    "not cover. Tables: nodes(id,type,label,aliases,attrs_json), "
    "edges(src,predicate,dst,confidence,conf_rank,attrs_json,n_evidence,asserted_by), "
    "edge_attrs(src,predicate,dst,key,num,txt), and the view edges_labeled which adds "
    "src_label/dst_label/src_type/dst_type.",
    _obj({"sql": {**STR, "description": "A SELECT or WITH statement. Writes are refused."},
          "kg": STR},
         ["sql"]),
)
def graph_query(sql: str, kg: str | None = None) -> str:
    st = _store(kg)
    try:
        rows = st.query(sql)
    except ValueError as exc:
        return f"Refused: {exc}"
    except Exception as exc:
        return (
            f"SQL error: {exc}\n\n"
            "Tables: nodes(id, type, label, aliases, attrs_json, asserted_by), "
            "edges(src, predicate, dst, confidence, conf_rank, attrs_json, n_evidence, "
            "asserted_by), edge_attrs(src, predicate, dst, key, num, txt), "
            "edges_labeled(+ src_label, dst_label, src_type, dst_type)."
        )
    if not rows:
        return "0 rows."
    head = list(rows[0])
    out = [" | ".join(head), "-" * min(100, 3 * len(head) + sum(len(h) for h in head))]
    for r in rows[:60]:
        out.append(" | ".join(str(r[h])[:44] for h in head))
    if len(rows) > 60:
        out.append(f"... {len(rows) - 60} more rows (total {len(rows)})")
    return "\n".join(out)


@tool(
    "axis_neighborhood",
    "For a target, list its neighbours on every declared similarity axis at once, so "
    "you can see where the axes agree and disagree. Needs a run's problem.json.",
    _obj({"run_id": {**STR, "description": "Run id, e.g. demo"},
          "node_id": {**STR, "description": "Defaults to the run's primary target."},
          "limit": INT, "kg": STR},
         ["run_id"]),
)
def axis_neighborhood(run_id: str, node_id: str | None = None, limit: int = 10,
                      kg: str | None = None) -> str:
    sp = Path("reports") / run_id / "problem.json"
    if not sp.is_file():
        runs = [p.parent.name for p in Path("reports").glob("*/problem.json")] \
            if Path("reports").is_dir() else []
        return f"No problem.json for run {run_id!r}. Runs available: {runs}"
    spec = ProblemSpec.load(sp)
    st = _store(kg)
    target = node_id or spec.primary_target.id

    out = [f"{spec.name} — axis neighbourhood of {target}", ""]
    empty = []
    for a in spec.axes:
        rows = st.along_axis(target, a, limit=limit)
        if not rows:
            empty.append(a.name)
            continue
        out.append(f"{a.name}  ({a.predicate}, score {a.score_key} in "
                   f"[{a.score_range[0]}, {a.score_range[1]}])")
        out.append(f"  asks: {a.question}")
        for r in rows:
            v = r["attrs"].get(a.score_key)
            flag = "  [ILLUSTRATIVE]" if r["attrs"].get("illustrative") else ""
            out.append(f"    {r['other_label']:<28} {a.score_key}={v}  "
                       f"[{r['confidence']}]{flag}")
        out.append("")
    if empty:
        out.append(f"Axes with NO edges: {', '.join(empty)}")
        out.append("  That is a real gap, not an absence of similarity — those "
                   "measurements have not been made.")
    out.append("\nNext: `compare_structures` on any two of these to see them in 3D.")
    return "\n".join(out)


# --------------------------------------------------------------------------
# the headline: 3D structure comparison
# --------------------------------------------------------------------------


@tool(
    "compare_structures",
    "Fetch two protein structures, superpose them, compute what is structurally and "
    "chemically similar, and render an interactive 3D page showing them side by side "
    "with linked cameras and as a superposed overlay. Accepts graph node ids: "
    "'pdb:1M13' for an experimental structure, 'uniprot:O75469' for an AlphaFold "
    "model, or 'file:path.pdb'. Returns the findings plus the path to the page.",
    _obj({
        "a": {**STR, "description": "First structure, e.g. pdb:1M13 or uniprot:O75469"},
        "b": {**STR, "description": "Second structure"},
        "label_a": {**STR, "description": "Display name, e.g. 'PXR (NR1I2)'"},
        "label_b": STR,
        "chain_a": {**STR, "description": "Chain id. Defaults to the longest chain."},
        "chain_b": STR,
        "pocket_radius": {**NUM, "description": "Angstroms from ligand atoms. Default 6."},
        "out": {**STR, "description": "Output HTML path. Defaults under docs/figures/mcp/."},
        "kg": STR,
    }, ["a", "b"]),
)
def compare_structures(
    a: str, b: str,
    label_a: str | None = None, label_b: str | None = None,
    chain_a: str | None = None, chain_b: str | None = None,
    pocket_radius: float = 6.0,
    out: str | None = None,
    kg: str | None = None,
) -> str:
    from reagent.structure import fetch, pocket_comparison, superpose
    from reagent.viz.compare_3d import render as render_cmp

    # Resolve labels and any graph relationship between the two, so the page and the
    # answer carry the context the user was reasoning about when they asked.
    graph_context: list[str] = []
    resolved_a, resolved_b = a, b
    try:
        st = _store(kg)
        rows = st.query(
            "SELECT id, label FROM nodes WHERE id IN (?, ?)", (a, b)
        )
        got = {r["id"]: r["label"] for r in rows}
        label_a = label_a or got.get(a)
        label_b = label_b or got.get(b)
        edges = st.query(
            "SELECT src, predicate, dst, confidence, attrs_json FROM edges "
            "WHERE (src=? AND dst=?) OR (src=? AND dst=?)", (a, b, b, a)
        )
        for e in edges:
            at = json.loads(e["attrs_json"] or "{}")
            flag = " [ILLUSTRATIVE placeholder]" if at.pop("illustrative", None) else ""
            graph_context.append(
                f"{e['src']} --{e['predicate']}--> {e['dst']} "
                f"({e['confidence']}) {json.dumps(at) if at else ''}{flag}"
            )
        fams = st.query(
            "SELECT e1.src AS a, e2.src AS b, n.id AS fam, n.label FROM edges e1 "
            "JOIN edges e2 ON e1.dst = e2.dst AND e1.predicate='MEMBER_OF_FAMILY' "
            "  AND e2.predicate='MEMBER_OF_FAMILY' "
            "JOIN nodes n ON n.id = e1.dst WHERE e1.src=? AND e2.src=?", (a, b)
        )
        for f in fams:
            graph_context.append(f"Both are members of {f['label']} ({f['fam']})")
    except Exception:
        pass

    sa = fetch(resolved_a)
    sb = fetch(resolved_b)
    aln = superpose(sa, sb, chain_a=chain_a, chain_b=chain_b)
    pc = pocket_comparison(sa, sb, aln, radius=pocket_radius)

    FIGURES.mkdir(parents=True, exist_ok=True)
    safe = f"{a}_{b}".replace(":", "_").replace("/", "_")
    out_path = Path(out) if out else FIGURES / f"cmp_{safe}.html"
    page, _viz = render_cmp(
        sa, sb, aln, out_path, pocket=pc,
        label_a=label_a, label_b=label_b, graph_context=graph_context, repo_root=REPO,
    )

    name_a = label_a or sa.id
    name_b = label_b or sb.id
    lines = [
        f"{name_a} vs {name_b} — structural comparison",
        "",
        aln.summary(),
        "",
    ]
    if graph_context:
        lines.append("Graph says about this pair:")
        lines += [f"  {c}" for c in graph_context]
        lines.append("")

    if pc.get("note"):
        lines.append(f"Pocket: {pc['note']}")
    else:
        lines += [
            f"Binding pocket ({pc['radius_angstrom']} A from any ligand atom):",
            f"  {name_a} ligand {pc['ligand_a']} ({pc['ligand_size_a']} atoms), "
            f"{pc['n_pocket_residues_a']} lining residues",
            f"  {name_b} ligand {pc['ligand_b']} ({pc['ligand_size_b']} atoms), "
            f"{pc['n_pocket_residues_b']} lining residues",
            f"  {len(pc['shared'])} residues correspond between the two pockets "
            f"(Jaccard {pc['jaccard']}), of which {pc['conserved_identity']} are the "
            f"same amino acid",
        ]
        if pc["shared"]:
            lines.append("  corresponding pocket residues, closest first:")
            for s in pc["shared"][:14]:
                same = "  SAME RESIDUE" if s["identical"] else ""
                lines.append(f"    {s['a']:>10s} <-> {s['b']:<10s} "
                             f"{s['ca_distance']} A{same}")
        if pc["only_in_a"]:
            lines.append(f"  only in {name_a}: {', '.join(pc['only_in_a'][:12])}")
        if pc["only_in_b"]:
            lines.append(f"  only in {name_b}: {', '.join(pc['only_in_b'][:12])}")

    div = aln.divergent_pairs(threshold=8.0)[:6]
    if div:
        lines += [
            "",
            "Regions that align in sequence but diverge in space (largest first):",
            *[f"  {p.a.label} vs {p.b.label}: {p.distance:.1f} A apart" for p in div],
        ]

    lines += [
        "",
        f"Interactive 3D page: {page.as_posix()}",
        "  Side-by-side with linked cameras, plus a superposed overlay. Colour encodes "
        "how well each residue pair corresponds; hover any residue to see its partner "
        "and their separation; click a shared pocket residue to centre both views on it.",
        "",
        "IMPORTANT when relaying this: the similarity numbers are a sequence-guided "
        "estimate, not the output of a structural aligner such as TM-align or Foldseek. "
        "TM-score here is a lower bound. Say so.",
    ]
    return "\n".join(lines)


@tool(
    "structure_info",
    "Inspect a structure without comparing it: chains, lengths, ligands, and the "
    "residues lining its main binding pocket.",
    _obj({"structure": {**STR, "description": "pdb:1M13, uniprot:O75469, or file:path.pdb"},
          "pocket_radius": NUM},
         ["structure"]),
)
def structure_info(structure: str, pocket_radius: float = 6.0) -> str:
    from reagent.structure import fetch

    st = fetch(structure)
    out = [f"{st.id} — {st.title or '(no title)'}", f"  source: {st.source}"]
    out.append("  chains:")
    for c, res in sorted(st.chains.items(), key=lambda kv: -len(kv[1])):
        first, last = res[0], res[-1]
        out.append(f"    {c}: {len(res)} residues ({first.label}..{last.label})")
    real = [lg for lg in st.ligands if lg.n_atoms >= 6]
    out.append(f"  non-solvent heteroatom groups: {len(real)}")
    for lg in sorted(real, key=lambda x: -x.n_atoms)[:8]:
        out.append(f"    {lg.name3} chain {lg.chain} #{lg.seq_num}: {lg.n_atoms} atoms")

    lig = st.primary_ligand()
    if lig is None:
        out.append("  no primary ligand — nothing to define a pocket around.")
    else:
        near = st.residues_near(lig.coords, pocket_radius)
        out.append(f"  pocket around {lig.name3} within {pocket_radius} A: "
                   f"{len(near)} residues")
        out.append("    " + ", ".join(r.label for r in near))
    return "\n".join(out)


@tool(
    "list_figures",
    "List the figures this repo has produced, with the question each one answers. "
    "Use to find an existing visualization before generating a new one.",
    _obj({}),
)
def list_figures() -> str:
    figs = sorted(Path("docs").rglob("*.html")) + sorted(Path("docs").rglob("*.svg")) \
        if Path("docs").is_dir() else []
    if not figs:
        return "No figures under docs/. Generate one with `compare_structures`."
    # Pull the declared question from any report that references the figure.
    questions: dict[str, str] = {}
    for rp in Path("reports").glob("*/*/report.json") if Path("reports").is_dir() else []:
        try:
            r = ModelReport.load(rp)
        except Exception:
            continue
        if r.visuals:
            for v in r.visuals.visualizations:
                questions[v.path] = v.question
    out = [f"{len(figs)} figures:"]
    for f in figs:
        rel = f.as_posix()
        q = questions.get(rel)
        out.append(f"  {rel}  ({f.stat().st_size // 1024} KB)")
        if q:
            out.append(f"    asks: {q}")
    return "\n".join(out)


@tool(
    "kg_audit",
    "Check the graph's honesty: edges claiming confidence they have no citation for, "
    "edges carrying placeholder numbers, and overall citation coverage. Run before "
    "relaying graph claims as findings.",
    _obj({"kg": STR}),
)
def kg_audit(kg: str | None = None) -> str:
    st = _store(kg)
    s = st.stats()
    bad = st.unsupported_edges(Confidence.SUPPORTED)
    illus = st.query(
        "SELECT e.src, e.predicate, e.dst, e.asserted_by FROM edges e "
        "JOIN edge_attrs a ON a.src=e.src AND a.predicate=e.predicate AND a.dst=e.dst "
        "WHERE a.key='illustrative' LIMIT 40"
    )
    out = [
        f"Graph audit — {st.root.as_posix()}",
        f"  citation coverage: {s['cited_edge_fraction']:.0%} of {s['n_edges']} edges",
    ]
    out.append(
        f"  edges claiming >= supported with no citation: {len(bad)}"
        + ("  (good)" if not bad else "")
    )
    for r in bad[:15]:
        out.append(f"    {r['src']} -{r['predicate']}-> {r['dst']}  ({r['asserted_by']})")
    out.append(f"  edges with placeholder (illustrative) numbers: {len(illus)}")
    for r in illus[:15]:
        out.append(f"    {r['src']} -{r['predicate']}-> {r['dst']}  ({r['asserted_by']})")
    if illus:
        out.append("  Those numbers are NOT measurements. Do not present them as findings.")
    if s["cited_edge_fraction"] < 0.6:
        out.append("\n  Coverage below 60% means the harvest asserted more than it read.")
    return "\n".join(out)
