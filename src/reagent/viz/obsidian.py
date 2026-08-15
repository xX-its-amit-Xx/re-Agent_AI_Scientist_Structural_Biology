"""Export the knowledge graph as an Obsidian vault — a secondary browsing layer.

Read ``.claude/skills/kg-visualize/reference/obsidian-export.md`` before relying on
this. The short version: Obsidian **cannot** encode edge weight, so this is a
reading interface, not the deliverable figure. `reagent viz kg` is the figure.

What the vault genuinely gives you, nearly free once the JSONL exists: wiki-style
navigation with backlinks and hover previews, full-text search across every node,
and Dataview queries over edge payloads ("every BINDS edge with Kd below 1 uM").
That is a pleasant way to *read* a graph, and it costs one function.

Each edge is written **twice**, deliberately:

1. As a quoted wikilink inside a frontmatter property named after the predicate.
   This is what the Extended Graph plugin reads to assign an edge its *type*, and
   therefore its colour, and it also registers as a real link in the native graph.
2. As a Dataview inline field in the body, carrying the quantitative payload
   (``[tm_score:: 0.87]``). Nothing renders this on the edge — no plugin can — but
   it is queryable, which is the part that stays useful.

Filenames sanitise the colon out of namespaced ids, because a colon is illegal in a
Windows filename and inside a wikilink. The original id is preserved in the
``node-id`` frontmatter property, which is what you should join on.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from reagent.contracts import Confidence, Predicate, family_of
from reagent.kg.store import KGStore

_UNSAFE = re.compile(r'[:<>"/\\|?*\x00-\x1f]')


def safe_name(node_id: str) -> str:
    """``uniprot:O75469`` -> ``uniprot O75469``. Reversible enough to be readable."""
    return _UNSAFE.sub(" ", node_id).strip()


def _fm_scalar(v: Any) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v).replace('"', "'")
    return f'"{s}"'


def export(
    store: KGStore,
    out_dir: Path,
    *,
    focal: str | None = None,
    min_confidence: Confidence = Confidence.SPECULATIVE,
    include_evidence_edges: bool = False,
) -> dict[str, Any]:
    """Write one Markdown file per node. Returns a summary dict.

    ``include_evidence_edges`` defaults to False for the same reason the renderer
    hides them: every claim cites sources, so they swamp both the graph view and
    the backlink panel.
    """
    out_dir = Path(out_dir)
    nodes_dir = out_dir / "nodes"
    nodes_dir.mkdir(parents=True, exist_ok=True)

    con = store.connect()
    try:
        nodes = {
            r["id"]: dict(r)
            for r in con.execute(
                "SELECT id, type, label, aliases, attrs_json, asserted_by FROM nodes"
            )
        }
        edge_rows = [
            dict(r)
            for r in con.execute(
                "SELECT src, predicate, dst, confidence, conf_rank, attrs_json,"
                " n_evidence, evidence_json, asserted_by FROM edges WHERE conf_rank >= ?",
                (min_confidence.rank,),
            )
        ]
    finally:
        con.close()

    if not include_evidence_edges:
        edge_rows = [
            e for e in edge_rows
            if family_of(Predicate(e["predicate"])).value not in {"evidence"}
        ]

    outgoing: dict[str, list[dict]] = defaultdict(list)
    incoming: dict[str, list[dict]] = defaultdict(list)
    for e in edge_rows:
        outgoing[e["src"]].append(e)
        incoming[e["dst"]].append(e)

    written = 0
    for nid, n in nodes.items():
        try:
            attrs = json.loads(n["attrs_json"] or "{}")
        except json.JSONDecodeError:
            attrs = {}
        try:
            aliases = json.loads(n["aliases"] or "[]")
        except json.JSONDecodeError:
            aliases = []

        out_edges = outgoing.get(nid, [])
        by_pred: dict[str, list[dict]] = defaultdict(list)
        for e in out_edges:
            by_pred[e["predicate"]].append(e)

        lines = ["---", f"node-id: {_fm_scalar(nid)}", f"node-type: {n['type']}"]
        if aliases:
            lines.append("aliases: [" + ", ".join(_fm_scalar(a) for a in aliases) + "]")
        lines.append(f"asserted-by: {_fm_scalar(n['asserted_by'])}")
        lines.append(f"tags: [type/{n['type']}]")
        # Node size in Extended Graph can be driven by a numeric property, so give
        # it degree — the one node-level number that is always meaningful.
        lines.append(f"degree: {len(out_edges) + len(incoming.get(nid, []))}")
        for k, v in attrs.items():
            if isinstance(v, (str, int, float, bool)):
                lines.append(f"{k}: {_fm_scalar(v)}")

        # Typed links as frontmatter list properties: what Extended Graph colours by.
        for pred, es in sorted(by_pred.items()):
            lines.append(f"{pred}:")
            for e in es:
                if e["dst"] in nodes:
                    lines.append(f'  - "[[{safe_name(e["dst"])}]]"')
        lines.append("---")
        lines.append("")
        lines.append(f"# {n['label']}")
        lines.append("")
        lines.append(f"`{nid}` · {n['type']}")
        lines.append("")

        if attrs:
            lines.append("## Attributes")
            lines.append("")
            for k, v in attrs.items():
                lines.append(f"- **{k}**: {json.dumps(v) if not isinstance(v, str) else v}")
            lines.append("")

        if out_edges:
            lines.append("## Edges")
            lines.append("")
            lines.append(
                "> Payloads below are Dataview inline fields — queryable, but no "
                "Obsidian plugin can render them on the edge itself. Use "
                "`reagent viz kg` for the weighted figure."
            )
            lines.append("")
            for pred, es in sorted(by_pred.items()):
                fam = family_of(Predicate(pred)).value
                lines.append(f"### {pred}  *({fam})*")
                lines.append("")
                for e in es:
                    if e["dst"] not in nodes:
                        continue
                    try:
                        eattrs = json.loads(e["attrs_json"] or "{}")
                    except json.JSONDecodeError:
                        eattrs = {}
                    payload = "".join(
                        f" [{k}:: {v}]" for k, v in eattrs.items()
                        if isinstance(v, (str, int, float, bool))
                    )
                    ev = ""
                    try:
                        evs = json.loads(e["evidence_json"] or "[]")
                        if evs:
                            ev = " [evidence:: " + "; ".join(
                                str(x.get("locator", "")) for x in evs[:3]
                            ) + "]"
                    except json.JSONDecodeError:
                        pass
                    lines.append(
                        f"- {pred}:: [[{safe_name(e['dst'])}]]"
                        f" [confidence:: {e['confidence']}]{payload}{ev}"
                    )
                lines.append("")

        if inc := incoming.get(nid):
            lines.append("## Referenced by")
            lines.append("")
            for e in sorted(inc, key=lambda r: r["predicate"])[:60]:
                if e["src"] in nodes:
                    lines.append(
                        f"- [[{safe_name(e['src'])}]] --{e['predicate']}--> this"
                    )
            lines.append("")

        (nodes_dir / f"{safe_name(nid)}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        written += 1

    _write_index(out_dir, nodes, edge_rows, focal)
    _write_config(out_dir, nodes)

    return {
        "vault": str(out_dir),
        "nodes_written": written,
        "edges_written": len(edge_rows),
        "evidence_edges_included": include_evidence_edges,
    }


def _write_index(out_dir: Path, nodes: dict, edges: list[dict], focal: str | None) -> None:
    by_type: dict[str, int] = defaultdict(int)
    for n in nodes.values():
        by_type[n["type"]] += 1
    by_fam: dict[str, int] = defaultdict(int)
    for e in edges:
        by_fam[family_of(Predicate(e["predicate"])).value] += 1

    lines = [
        "# Knowledge graph",
        "",
        "**This vault is a reading interface, not the figure.** Obsidian cannot encode",
        "edge weight — its link model has nowhere to store a per-edge number that any",
        "renderer reads — so the graph view here shows structure without strength. For",
        "the weighted, colour-coded figure use `reagent viz kg`.",
        "",
        "What this vault is good for: clicking through entities, backlinks, hover",
        "previews, full-text search, and Dataview queries over edge payloads.",
        "",
    ]
    if focal and focal in nodes:
        lines += [f"Focal entity: [[{safe_name(focal)}]] — {nodes[focal]['label']}", ""]

    lines += ["## Contents", "", f"{len(nodes)} nodes, {len(edges)} edges.", ""]
    lines += ["| Entity type | n |", "|---|---|"]
    lines += [f"| {t} | {c} |" for t, c in sorted(by_type.items(), key=lambda kv: -kv[1])]
    lines += ["", "| Predicate family | n |", "|---|---|"]
    lines += [f"| {f} | {c} |" for f, c in sorted(by_fam.items(), key=lambda kv: -kv[1])]

    lines += [
        "",
        "## Setup for typed, coloured edges",
        "",
        "Native Obsidian draws every edge the same monochrome line. To get edge",
        "colours you need the **Extended Graph** plugin (the only maintained plugin",
        "that does it), then enable *Color links* and point link-type detection at",
        "frontmatter properties. Node colours come from the `type/*` tags via graph",
        "groups, or from the `node-type` property in Extended Graph.",
        "",
        "Install **Dataview** to run the queries below. Neither plugin travels with",
        "the vault, so a teammate must install both.",
        "",
        "## Useful queries",
        "",
        "Strongest fold neighbours:",
        "",
        "```dataview",
        "TABLE WITHOUT ID",
        '  regexreplace(string(L.link), "\\\\[|\\\\]", "") AS Neighbour,',
        "  L.tm_score AS TM, L.confidence AS Confidence",
        'FROM "nodes"',
        "FLATTEN file.lists AS L",
        "WHERE L.SIMILAR_FOLD_TO AND L.tm_score",
        "SORT L.tm_score DESC",
        "LIMIT 25",
        "```",
        "",
        "Every measured binding interaction:",
        "",
        "```dataview",
        "TABLE WITHOUT ID file.link AS Entity, L.link AS Compound, L.confidence AS Conf",
        'FROM "nodes"',
        "FLATTEN file.lists AS L",
        "WHERE L.BINDS",
        "```",
        "",
        "Claims resting on a single source — the audit query worth running:",
        "",
        "```dataview",
        "TABLE WITHOUT ID file.link AS Entity, L.link AS Target, L.evidence AS Evidence",
        'FROM "nodes"',
        "FLATTEN file.lists AS L",
        "WHERE L.confidence = \"supported\" AND L.evidence",
        "```",
        "",
        "Entities with no data pointer, which is where the gaps are:",
        "",
        "```dataview",
        "LIST",
        'FROM "nodes"',
        "WHERE node-type = \"Protein\" AND !HAS_DATA",
        "```",
    ]
    (out_dir / "Knowledge graph.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_config(out_dir: Path, nodes: dict) -> None:
    """Pre-seed graph groups so node colours work without manual setup.

    Native graph groups are search queries with a colour each. Writing them here
    saves a teammate configuring fifteen groups by hand, which is the step most
    likely to make them give up before seeing anything.
    """
    from reagent.viz.graph_html import NODE_COLOR

    cfg_dir = out_dir / ".obsidian"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    present = sorted({n["type"] for n in nodes.values()})
    groups = [
        {"query": f"tag:#type/{t}", "color": {"a": 1, "rgb": _hex_to_int(NODE_COLOR.get(t, "#888888"))}}
        for t in present
    ]
    (cfg_dir / "graph.json").write_text(
        json.dumps(
            {
                "collapse-filter": False, "search": "", "showTags": False,
                "showAttachments": False, "hideUnresolved": True, "showOrphans": False,
                "collapse-color-groups": False, "colorGroups": groups,
                "collapse-display": False, "showArrow": True, "textFadeMultiplier": 0,
                "nodeSizeMultiplier": 1.1, "lineSizeMultiplier": 1,
                "collapse-forces": False, "centerStrength": 0.4,
                "repelStrength": 12, "linkStrength": 0.7, "linkDistance": 180,
                "scale": 1, "close": False,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def _hex_to_int(hex_color: str) -> int:
    return int(hex_color.lstrip("#"), 16)
