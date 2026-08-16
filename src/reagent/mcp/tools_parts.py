"""MCP tools for the Stage 2 anatomy layer: pairs, parts, and the side-by-side view.

The interaction these exist for is the one a med chemist actually has: *"the graph says these
two are connected — show me the pieces and tell me what is the same."* In a chat client that
is two nodes named in a sentence, so the tools take node ids and do the rest.

``explain_pair`` is deliberately the cheap one and comes first. Before rendering anything, a
reader wants the graph's own account of why the pair belongs together — the predicate, the
score, whether it is a placeholder, and the edge's ``commentary``. That answer is one query
and no coordinates, and most of the time it is the whole answer.
"""

from __future__ import annotations

from pathlib import Path

from reagent.mcp.tools import NUM, STR, _illustrative_warning, _obj, _store, tool


def _label(store, node_id: str) -> str:
    rows = store.query("SELECT label, type FROM nodes WHERE id = ?", (node_id,))
    return f"{rows[0]['label']} ({rows[0]['type']})" if rows else node_id


@tool(
    "explain_pair",
    "Why are these two nodes connected? Returns the edges between them with their scores, "
    "confidence, citations and commentary — or, when there is no direct edge, the shared "
    "neighbours that link them. Ask this before rendering anything.",
    _obj({"a": {**STR, "description": "First node id, e.g. uniprot:O75469"},
          "b": {**STR, "description": "Second node id, e.g. uniprot:P08684"},
          "kg": STR},
         ["a", "b"]),
)
def explain_pair(a: str, b: str, kg: str | None = None) -> str:
    store = _store(kg)
    known = store.node_ids()
    missing = [n for n in (a, b) if n not in known]
    if missing:
        return (
            f"not in the graph: {missing}. Node ids are namespaced — try `kg_search` to find "
            "the right one."
        )

    rel = store.between(a, b)
    out = [f"{_label(store, a)}", f"{_label(store, b)}", ""]

    if rel["direct"]:
        out.append(f"{len(rel['direct'])} direct edge(s):")
        for d in rel["direct"]:
            arrow = "<-" if d["direction"] == "reverse" else "->"
            nums = ", ".join(
                f"{k}={v}" for k, v in (d["attrs"] or {}).items()
                if isinstance(v, (int, float)) and not isinstance(v, bool)
            )
            out.append(
                f"  {d['predicate']} {arrow}  [{d['confidence']}"
                + (f", {nums}" if nums else "")
                + f", {d['n_evidence']} citation(s), by {d['asserted_by']}]"
            )
            out.append(_illustrative_warning(d["attrs"] or {}).rstrip("\n") or "")
            if d["commentary"]:
                out.append(f"    {d['commentary']}")
            else:
                out.append(
                    "    NO COMMENTARY. The graph records that these are related and not "
                    "what it means for what to do next. Treat the number as checkable but "
                    "not yet usable."
                )
    elif rel["paths"]:
        out.append(
            f"No direct edge. {len(rel['paths'])} two-hop connection(s) — a weaker claim, and "
            "the intermediate is usually the interesting part:"
        )
        seen = set()
        for p in rel["paths"]:
            key = (p["via"], p["pred_a"], p["pred_b"])
            if key in seen:
                continue
            seen.add(key)
            out.append(f"  {p['pred_a']} · {p['via_label'] or p['via']} · {p['pred_b']}")
            if p.get("comment_a") or p.get("comment_b"):
                out.append(f"    {p.get('comment_a') or p.get('comment_b')}")
    else:
        out.append(
            "Nothing connects these two in the graph — no edge, no shared neighbour. That is "
            "a real answer: whatever prompted the comparison came from outside the graph and "
            "is not auditable from it."
        )

    return "\n".join(x for x in out if x is not None)


@tool(
    "compare_parts",
    "Render two graph nodes side by side in 3D with their interactions: contacting residues "
    "as sticks coloured by interaction kind, directional contacts dashed, and a table of "
    "which interactions both sides make. Use for fragment-vs-fragment, fragment-vs-pocket, "
    "or motif-vs-motif. Writes a self-contained HTML file and returns its path.",
    _obj({
        "a": {**STR, "description": "First node id — a Fragment, Compound, Pocket or Motif."},
        "b": {**STR, "description": "Second node id."},
        "structure_a": {**STR, "description":
                        "Coordinates for the left panel, e.g. pdb:1M13. Defaults to a "
                        "structure the graph attaches to `a`."},
        "structure_b": {**STR, "description": "Coordinates for the right panel."},
        "pocket_radius": {**NUM, "description":
                          "Angstroms from the ligand used to pick contacting residues "
                          "when the graph has no CONTACTS edges. Default 4.5."},
        "out": STR,
        "kg": STR,
    }, ["a", "b"]),
)
def compare_parts(
    a: str,
    b: str,
    structure_a: str | None = None,
    structure_b: str | None = None,
    pocket_radius: float = 4.5,
    out: str | None = None,
    kg: str | None = None,
) -> str:
    from reagent.structure import fetch
    from reagent.viz.compare_parts import Contact, PartView
    from reagent.viz.compare_parts import render as render_parts

    store = _store(kg)
    known = store.node_ids()
    missing = [n for n in (a, b) if n not in known]
    if missing:
        return f"not in the graph: {missing}. Use `kg_search` to find the right node ids."

    #: Predicates a search for coordinates may traverse, in either direction. A fragment is
    #: the *destination* of HAS_FRAGMENT and the *source* of OCCUPIES, so a one-directional
    #: walk finds one and misses the other — which is how this first failed.
    _CONTAINMENT = (
        "PART_OF", "HAS_FRAGMENT", "HAS_POCKET", "POCKET_LINED_BY", "HAS_MOTIF",
        "HAS_PHARMACOPHORE", "OCCUPIES", "BINDS", "CONTACTS", "HAS_STRUCTURE",
    )

    def structure_for(node_id: str, override: str | None, max_hops: int = 4) -> str | None:
        """Find coordinates for a node by walking containment in either direction.

        Breadth-first rather than a nested join, because the chain is genuinely variable —
        fragment to compound to target to structure is three hops through three predicates
        with two different directions — and a fixed join shape gets one of them wrong.
        """
        if override:
            return override
        # A node id may name its own structure: pocket:pdb:1M13/LBD.
        segs = node_id.split(":")
        for i, seg in enumerate(segs):
            if seg == "pdb" and i + 1 < len(segs):
                return "pdb:" + segs[i + 1].split("/")[0]

        placeholders = ",".join("?" * len(_CONTAINMENT))
        seen, frontier = {node_id}, [node_id]
        for _ in range(max_hops):
            if not frontier:
                break
            nxt: list[str] = []
            for cur in frontier:
                rows = store.query(
                    f"""
                    SELECT dst AS other FROM edges
                     WHERE src = ? AND predicate IN ({placeholders})
                    UNION
                    SELECT src AS other FROM edges
                     WHERE dst = ? AND predicate IN ({placeholders})
                    """,
                    (cur, *_CONTAINMENT, cur, *_CONTAINMENT),
                )
                for r in rows:
                    other = r["other"]
                    if other in seen:
                        continue
                    if str(other).startswith("pdb:"):
                        return other
                    seen.add(other)
                    nxt.append(other)
            frontier = nxt
        return None

    sa, sb = structure_for(a, structure_a), structure_for(b, structure_b)
    if not sa or not sb:
        unresolved = [n for n, s in ((a, sa), (b, sb)) if not s]
        return (
            f"could not find coordinates for {unresolved}. The graph has no HAS_STRUCTURE "
            "path from these nodes and the ids do not name a PDB entry. Pass `structure_a` "
            "and/or `structure_b` explicitly."
        )

    def contacts_for(node_id: str, st, chain: str) -> tuple[list[Contact], str | None]:
        """Prefer recorded CONTACTS edges; fall back to geometry and say which was used."""
        rows = store.query(
            """
            SELECT dst AS other, attrs_json FROM edges
             WHERE src = ? AND predicate = 'CONTACTS'
            UNION ALL
            SELECT src AS other, attrs_json FROM edges
             WHERE dst = ? AND predicate = 'CONTACTS'
            """,
            (node_id, node_id),
        )
        import json as _json

        found: list[Contact] = []
        for r in rows:
            attrs = _json.loads(r["attrs_json"] or "{}")
            tail = str(r["other"]).rsplit("/", 1)[-1]        # 'Ser247'
            resn, digits = tail[:3].upper(), "".join(ch for ch in tail if ch.isdigit())
            if not digits:
                continue
            found.append(Contact(
                resi=int(digits), resn=resn,
                kind=attrs.get("interaction", "hydrophobic"),
                distance_a=attrs.get("distance_a"),
                source=attrs.get("source"),
            ))
        if found:
            return found, None

        lig = st.primary_ligand(chain)
        if lig is None:
            return [], "no CONTACTS edges and no ligand to measure from"
        near = st.residues_near(lig.coords, pocket_radius, chain)
        geo = [
            Contact(resi=r.seq_num, resn=r.label[:3].upper(), kind="hydrophobic",
                    source=f"geometry<{pocket_radius}A")
            for r in near
        ]
        return geo, (
            f"no CONTACTS edges in the graph, so contacts were derived from geometry "
            f"({pocket_radius} A from the ligand) and every one is typed 'hydrophobic' by "
            "default. Interaction kinds require a profiler — run pocket-anatomy."
        )

    st_a, st_b = fetch(sa), fetch(sb)
    ch_a, ch_b = st_a.best_chain(), st_b.best_chain()
    ca, note_a = contacts_for(a, st_a, ch_a)
    cb, note_b = contacts_for(b, st_b, ch_b)

    left = PartView(node_id=a, label=_label(store, a), pdb_text=st_a.raw_text,
                    chain=ch_a, ligand_resn=st_a.primary_ligand(ch_a), contacts=ca)
    right = PartView(node_id=b, label=_label(store, b), pdb_text=st_b.raw_text,
                     chain=ch_b, ligand_resn=st_b.primary_ligand(ch_b), contacts=cb)

    # A SMARTS pattern makes a legal node id and an illegal-ish filename: brackets, parens
    # and equals signs survive on disk and then need escaping in every URL that references
    # the figure. Reduce to a safe slug and keep the real ids inside the page.
    import re as _re

    def _slug(node_id: str) -> str:
        tail = node_id.split(":")[-1]
        return _re.sub(r"[^A-Za-z0-9._-]+", "-", tail).strip("-")[:28] or "node"

    slug = f"{_slug(a)}__{_slug(b)}"
    out_path = Path(out) if out else Path("docs/figures") / f"parts_{slug}.html"
    path, viz = render_parts(
        left, right, out_path, repo_root=Path.cwd(),
        connection=store.between(a, b),
        title=f"{left.label} and {right.label}",
    )

    lines = [
        f"wrote {path.as_posix()} ({path.stat().st_size // 1024} KB)",
        f"structures: left {sa} chain {ch_a} · right {sb} chain {ch_b}",
        f"takeaway: {viz.takeaway}",
    ]
    for side, note in (("left", note_a), ("right", note_b)):
        if note:
            lines.append(f"CAVEAT ({side}): {note}")
    lines.append(
        "The page leads with the graph's own account of why these two are together, then "
        "shows both panels with linked cameras and a shared/unique interaction table."
    )
    return "\n".join(lines)


@tool(
    "parts_of",
    "What is this entity made of? Lists the parts recorded for a compound, pocket or "
    "protein, with what each covers and what it touches. Use before comparing, to find "
    "which piece is worth comparing.",
    _obj({"node": STR, "kg": STR}, ["node"]),
)
def parts_of(node: str, kg: str | None = None) -> str:
    store = _store(kg)
    if node not in store.node_ids():
        return f"{node!r} is not in the graph. Use `kg_search`."

    rows = store.query(
        """
        SELECT e.src AS part, n.label, n.type, e.predicate, e.commentary, e.attrs_json
          FROM edges e LEFT JOIN nodes n ON n.id = e.src
         WHERE e.dst = ? AND e.predicate IN ('PART_OF')
        UNION ALL
        SELECT e.dst AS part, n.label, n.type, e.predicate, e.commentary, e.attrs_json
          FROM edges e LEFT JOIN nodes n ON n.id = e.dst
         WHERE e.src = ? AND e.predicate IN
               ('HAS_FRAGMENT','HAS_POCKET','POCKET_LINED_BY','HAS_MOTIF','HAS_PHARMACOPHORE')
        ORDER BY predicate, part
        """,
        (node, node),
    )
    if not rows:
        return (
            f"{_label(store, node)} has no parts recorded. Nothing decomposed it — which is "
            "not the same as it having no parts. Run parts-inventory."
        )

    out = [f"{_label(store, node)}: {len(rows)} part(s)"]
    for r in rows:
        out.append(f"  [{r['predicate']}] {r['label'] or r['part']}  <{r['part']}>")
        if r["commentary"]:
            out.append(f"      {r['commentary']}")
        touches = store.query(
            "SELECT dst, attrs_json FROM edges WHERE src = ? AND predicate = 'CONTACTS'",
            (r["part"],),
        )
        if touches:
            import json as _json
            bits = []
            for t in touches:
                kind = _json.loads(t["attrs_json"] or "{}").get("interaction", "?")
                bits.append(f"{str(t['dst']).rsplit('/', 1)[-1]}({kind})")
            out.append("      contacts: " + ", ".join(bits))
    return "\n".join(out)
