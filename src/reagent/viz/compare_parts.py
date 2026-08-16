"""Two parts of the graph, side by side, with their interactions.

``compare_3d`` answers *"these two proteins are connected — show me the folds."* This answers
the med chemist's version, one level down: **"these two nodes are connected — show me the
fragment and the residues it touches, next to the other one, and tell me what is the same."**

The difference matters because the useful comparison is not the fold. It is the contact
pattern: two fragments in the same pocket engaging the same serine and the same phenylalanine
is a transferable observation about chemistry, and it is invisible in a whole-protein overlay
where both ligands are two pixels of hetero-atom.

Three things this page does that a static figure cannot:

1. **Zoom each panel to the part, not the protein.** A pocket fills the frame, so contact
   geometry is legible. Linked cameras still apply, because comparing two poses by eye needs
   them held in the same orientation.
2. **Colour by interaction kind, not by element.** CPK colouring answers "which atom is
   nitrogen", which the reader already knows. What they cannot see is which contacts are
   directional constraints a wrong pose would violate, and which are hydrophobic contacts
   that any nearby greasy atom satisfies.
3. **Say what is shared and what is not, in a table.** The comparison is the point, and a
   reader should not have to derive it by alternating between two panels.

**One honesty constraint, stated in the page itself.** This view does *not* assert positional
equivalence between the two sides. Two proteins number their residues differently, and
deciding that Ser247 in one "is" Ser208 in the other requires an alignment — which
``compare_structures`` computes and labels an estimate. So the shared-contact table compares
**interaction kinds and residue identities**, which are claims the coordinates support, and
says so rather than implying more.
"""

from __future__ import annotations

import html
import json
from dataclasses import dataclass, field
from pathlib import Path

from reagent.contracts import ColorMap, Visualization, VizKind, VizMedium
from reagent.contracts.parts import ContactKind

VENDOR_REL = Path("assets/vendor/3Dmol-min.js")

#: Okabe-Ito, reusing the graph's interaction palette so a contact colour means the same
#: thing in the ego view and here. Directional kinds get the saturated hues because they are
#: the ones that constrain a pose; hydrophobic gets grey because it constrains very little.
CONTACT_COLOR: dict[str, str] = {
    ContactKind.HBOND_DONOR.value: "#0072B2",
    ContactKind.HBOND_ACCEPTOR.value: "#56B4E9",
    ContactKind.SALT_BRIDGE.value: "#CC79A7",
    ContactKind.PI_STACKING.value: "#009E73",
    ContactKind.PI_CATION.value: "#6A3D9A",
    ContactKind.HALOGEN.value: "#E69F00",
    ContactKind.METAL.value: "#8C6D31",
    ContactKind.COVALENT.value: "#D55E00",
    ContactKind.WATER_BRIDGE.value: "#767676",
    ContactKind.HYDROPHOBIC.value: "#A6A6A6",
}

CONTACT_NOTE: dict[str, str] = {
    ContactKind.HBOND_DONOR.value: "ligand donates a hydrogen bond — directional",
    ContactKind.HBOND_ACCEPTOR.value: "ligand accepts a hydrogen bond — directional",
    ContactKind.SALT_BRIDGE.value: "charged pair — directional and distance-sensitive",
    ContactKind.PI_STACKING.value: "aromatic faces — directional",
    ContactKind.PI_CATION.value: "cation over an aromatic face — directional",
    ContactKind.HALOGEN.value: "halogen bond — strongly directional",
    ContactKind.METAL.value: "metal coordination — geometry-defining",
    ContactKind.COVALENT.value: "covalent bond",
    ContactKind.WATER_BRIDGE.value: "mediated by an ordered water",
    ContactKind.HYDROPHOBIC.value: "non-directional; satisfied by any nearby apolar atom",
}


@dataclass
class Contact:
    """One contact to draw: a residue, what kind, and optionally the distance."""

    resi: int
    resn: str = ""
    kind: str = ContactKind.HYDROPHOBIC.value
    distance_a: float | None = None
    source: str | None = None

    @property
    def label(self) -> str:
        return f"{self.resn}{self.resi}" if self.resn else str(self.resi)

    @property
    def is_directional(self) -> bool:
        try:
            return ContactKind(self.kind).is_directional
        except ValueError:
            return False


@dataclass
class PartView:
    """One side of the comparison: a part, the coordinates it lives in, and its contacts."""

    node_id: str
    label: str
    pdb_text: str
    chain: str = "A"
    ligand_resn: str | None = None
    """Residue name of the ligand to show as sticks. None renders the protein side only."""
    highlight_atoms: list[int] = field(default_factory=list)
    """PDB atom serial numbers of the *part* — the fragment, rather than the whole ligand.
    Empty highlights the whole ligand, which is the right default for a whole-compound node."""
    contacts: list[Contact] = field(default_factory=list)
    subtitle: str | None = None

    def __post_init__(self) -> None:
        """Accept a ``Ligand`` where a residue name is expected.

        ``Structure.primary_ligand()`` returns a ``Ligand``, which is what a caller has in
        hand, and passing it straight through fails much later with a JSON encoding error
        that says nothing about the cause. Coercing here costs three lines and removes a
        papercut that would otherwise land on whoever builds Stage 2.
        """
        lg = self.ligand_resn
        if lg is not None and not isinstance(lg, str):
            name = getattr(lg, "name3", None)
            if name is None:
                raise TypeError(
                    f"ligand_resn must be a three-letter residue name or a Ligand, got "
                    f"{type(lg).__name__}"
                )
            self.ligand_resn = name

    def contact_kinds(self) -> set[str]:
        return {c.kind for c in self.contacts}

    def residue_types(self) -> set[str]:
        return {c.resn.upper() for c in self.contacts if c.resn}

    def kind_by_residue(self) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        for c in self.contacts:
            out.setdefault(c.label, []).append(c.kind)
        return out


def _shared_table(left: PartView, right: PartView) -> list[dict]:
    """Rows comparing the two sides by interaction kind.

    Deliberately keyed on kind rather than on residue position. Residue numbering is not
    comparable across structures without an alignment, and inventing an equivalence here
    would be the kind of quiet overstatement the rest of this project exists to prevent.
    """
    rows: list[dict] = []
    lk, rk = left.contact_kinds(), right.contact_kinds()
    for kind in sorted(lk | rk, key=lambda k: (k not in (lk & rk), k)):
        lres = sorted({c.label for c in left.contacts if c.kind == kind})
        rres = sorted({c.label for c in right.contacts if c.kind == kind})
        rows.append({
            "kind": kind,
            "note": CONTACT_NOTE.get(kind, ""),
            "shared": kind in lk and kind in rk,
            "left": lres,
            "right": rres,
            "directional": ContactKind(kind).is_directional
            if kind in {k.value for k in ContactKind} else False,
        })
    return rows


def _connection_block(connection: dict | None) -> dict:
    """Normalise ``KGStore.between()`` output into what the page renders.

    The commentary is the point. Two things shown side by side raise one question before any
    other — *why are these together?* — and the answer is already an edge attribute. Pulling
    it from the graph rather than asking the caller to retype it means the sentence a med
    chemist reads here is the same sentence the graph will hand to Stage 3.
    """
    if not connection:
        return {"direct": [], "paths": [], "kind": "none"}
    direct = connection.get("direct") or []
    paths = connection.get("paths") or []
    rows = []
    for d in direct:
        score = None
        for k, v in (d.get("attrs") or {}).items():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                score = f"{k} {v}"
                break
        rows.append({
            "predicate": d.get("predicate", ""),
            "direction": d.get("direction", "forward"),
            "confidence": d.get("confidence", ""),
            "n_evidence": d.get("n_evidence", 0),
            "score": score,
            "commentary": d.get("commentary"),
            "asserted_by": d.get("asserted_by", ""),
            "illustrative": bool((d.get("attrs") or {}).get("illustrative")),
        })
    return {
        "direct": rows,
        "paths": [
            {"via": p.get("via_label") or p.get("via"), "via_type": p.get("via_type"),
             "pred_a": p.get("pred_a"), "pred_b": p.get("pred_b"),
             "commentary": p.get("comment_a") or p.get("comment_b")}
            for p in paths[:12]
        ],
        "kind": "direct" if rows else ("path" if paths else "none"),
        "n_uncommented": sum(1 for r in rows if not r["commentary"]),
    }


def render(
    left: PartView,
    right: PartView,
    out_path: Path,
    *,
    repo_root: Path | None = None,
    title: str | None = None,
    connection: dict | None = None,
    graph_context: list[str] | None = None,
) -> tuple[Path, Visualization]:
    """Write the part-comparison page and return it with its contract object.

    ``connection`` is ``KGStore.between(left.node_id, right.node_id)``. Pass it and the page
    leads with the graph's own account of why these two belong together — the predicate, the
    score, the confidence, the citations, and the ``commentary`` sentence. Without it the page
    still renders, and opens by saying it does not know why the reader is looking at this pair,
    which is the honest version of not being told.
    """
    repo_root = Path(repo_root or Path.cwd())
    vendor = repo_root / VENDOR_REL
    if not vendor.is_file():
        raise FileNotFoundError(
            f"{VENDOR_REL} is missing. Run `reagent assets fetch` — the page must inline "
            "3Dmol.js because the publish target blocks external hosts."
        )

    rows = _shared_table(left, right)
    shared_kinds = [r["kind"] for r in rows if r["shared"]]
    only_left = [r["kind"] for r in rows if r["left"] and not r["right"]]
    only_right = [r["kind"] for r in rows if r["right"] and not r["left"]]
    shared_res_types = sorted(left.residue_types() & right.residue_types())
    conn = _connection_block(connection)
    relation = conn["direct"][0]["predicate"] if conn["direct"] else None

    payload = {
        "left": {
            "id": left.node_id, "label": left.label, "chain": left.chain,
            "ligandResn": left.ligand_resn, "highlight": left.highlight_atoms,
            "contacts": [
                {"resi": c.resi, "resn": c.resn, "kind": c.kind,
                 "d": c.distance_a, "src": c.source, "dir": c.is_directional}
                for c in left.contacts
            ],
        },
        "right": {
            "id": right.node_id, "label": right.label, "chain": right.chain,
            "ligandResn": right.ligand_resn, "highlight": right.highlight_atoms,
            "contacts": [
                {"resi": c.resi, "resn": c.resn, "kind": c.kind,
                 "d": c.distance_a, "src": c.source, "dir": c.is_directional}
                for c in right.contacts
            ],
        },
        "contactColor": CONTACT_COLOR,
        "contactNote": CONTACT_NOTE,
        "rows": rows,
        "graphContext": graph_context or [],
        "connection": conn,
    }

    doc = _HTML
    doc = doc.replace("/*__3DMOL__*/", vendor.read_text(encoding="utf-8"))
    doc = doc.replace("/*__DATA__*/", json.dumps(payload, separators=(",", ":")))
    doc = doc.replace("__PDB_L__", json.dumps(left.pdb_text))
    doc = doc.replace("__PDB_R__", json.dumps(right.pdb_text))
    doc = doc.replace("__TITLE__", html.escape(title or f"{left.label} vs {right.label}"))
    rel_bit = f"connected by {relation} · " if relation else ""
    doc = doc.replace("__SUB__", html.escape(
        f"{rel_bit}{len(shared_kinds)} interaction types on both sides, "
        f"{len(only_left)} only on the left, {len(only_right)} only on the right"
    ))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    # newline="" because a CRLF inside the inlined JS breaks a regex literal, which has
    # already cost this project an afternoon once.
    with out_path.open("w", encoding="utf-8", newline="") as fh:
        fh.write(doc)

    try:
        rel_path = str(out_path.relative_to(repo_root)).replace("\\", "/")
    except ValueError:
        rel_path = str(out_path)

    n_dir_shared = sum(1 for r in rows if r["shared"] and r["directional"])
    viz = Visualization(
        id=f"V-PARTS-{left.node_id.split(':')[-1]}-{right.node_id.split(':')[-1]}"[:40],
        kind=VizKind.INTERACTION_3D,
        medium=VizMedium.HTML_SELF_CONTAINED,
        title=f"{left.label} and {right.label}: interactions side by side",
        question=(
            f"Which interactions does {left.label} make that {right.label} also makes, "
            "and which are unique to one of them?"
        ),
        takeaway=(
            f"{len(shared_kinds)} interaction types occur on both sides, "
            f"{n_dir_shared} of them directional; {len(only_left)} occur only for "
            f"{left.label} and {len(only_right)} only for {right.label}"
            + (f". Both engage {', '.join(shared_res_types)}." if shared_res_types else ".")
        ),
        path=rel_path,
        reads_from=[left.node_id, right.node_id],
        encoding={
            "stick_color_ligand": "interaction kind of the contact that atom makes",
            "stick_residues": "residues in contact with the part",
            "dashed_line": "a directional contact (hydrogen bond, salt bridge, pi-stacking)",
            "left_right_position": "which of the two selected nodes",
            "camera": "linked between the two panels",
            "table_row_weight": "shared between both sides versus unique to one",
        },
        # Ten interaction kinds exceed the ~8 categorical-colour ceiling, so colour is paired
        # with a redundant channel: directional contacts get a dashed connector, everything
        # else does not. That is the distinction a med chemist actually acts on — a
        # directional contact is a constraint a wrong pose violates, a hydrophobic one is
        # satisfied by any nearby apolar atom — so the redundant channel carries the more
        # decision-relevant half of the encoding rather than merely duplicating hue.
        color_maps=[ColorMap(
            channel="stick_color_ligand", data_field="interaction_kind",
            scale_type="categorical", mapping=CONTACT_COLOR,
            secondary_channel=(
                "connector style: dashed for directional contacts (hydrogen bond, salt "
                "bridge, pi-stacking, pi-cation, halogen, metal, covalent), absent for "
                "non-directional ones"
            ),
        )],
        interactive=True,
        alt_text=(
            f"An interactive side-by-side three-dimensional view of {left.label} and "
            f"{right.label}, each zoomed to the part rather than the whole protein, with "
            "contacting residues drawn as sticks and directional contacts as dashed lines. "
            "Colour encodes interaction kind rather than chemical element. A table below "
            f"lists each interaction kind and whether both sides make it: {len(shared_kinds)} "
            f"are shared, {len(only_left)} occur only for {left.label}, and "
            f"{len(only_right)} only for {right.label}."
        ),
        n_elements=len(left.contacts) + len(right.contacts),
        params={
            "filtered": True,
            "mode": "part-level side-by-side",
            "asserts_positional_equivalence": False,
            "n_shared_kinds": len(shared_kinds),
        },
        covers_metrics=["n_shared_interaction_kinds"],
    )
    return out_path, viz


_HTML = """<!doctype html>
<meta charset="utf-8">
<title>__TITLE__</title>
<style>
  :root { --bg:#fbfbfa; --panel:#fff; --ink:#1a1a1a; --muted:#5c5c5c; --line:#e2e2df;
          --code:#f1f1ef; --accent:#0072B2; }
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) { --bg:#16171a; --panel:#1e2024; --ink:#e8e8e6;
      --muted:#9a9a96; --line:#2e3036; --code:#24262b; --accent:#56B4E9; }
  }
  :root[data-theme="dark"] { --bg:#16171a; --panel:#1e2024; --ink:#e8e8e6; --muted:#9a9a96;
    --line:#2e3036; --code:#24262b; --accent:#56B4E9; }
  * { box-sizing: border-box; }
  body { margin:0; background:var(--bg); color:var(--ink);
         font:15px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
  .wrap { max-width:1240px; margin:0 auto; padding:22px 20px 60px; }
  h1 { font-size:1.32rem; margin:0 0 .2rem; letter-spacing:-.01em; }
  .sub { color:var(--muted); font-size:.88rem; margin:0 0 1rem; }
  .panelrow { display:grid; grid-template-columns:1fr 1fr; gap:12px; }
  @media (max-width:860px) { .panelrow { grid-template-columns:1fr; } }
  .cap { font-size:.82rem; font-weight:600; padding:.4rem .1rem .3rem; }
  .cap .k { font-weight:400; color:var(--muted); }
  /* createViewerGrid appends ONE shared canvas to this container and splits it into
     cells, so the two captions sit outside it rather than inside each half. */
  #grid { position:relative; width:100%; height:460px; border:1px solid var(--line);
          border-radius:9px; overflow:hidden; background:var(--panel); }
  .bar { display:flex; flex-wrap:wrap; gap:8px; align-items:center; margin:.8rem 0; }
  button { font:inherit; font-size:.82rem; padding:.32rem .7rem; border-radius:7px;
           border:1px solid var(--line); background:var(--panel); color:var(--ink);
           cursor:pointer; }
  button.on { border-color:var(--accent); color:var(--accent); }
  .legend { display:flex; flex-wrap:wrap; gap:.5rem 1rem; margin:.7rem 0 1.1rem;
            font-size:.8rem; }
  .legend span.sw { display:inline-block; width:22px; height:3px; vertical-align:middle;
                    margin-right:.35rem; border-radius:2px; }
  table { width:100%; border-collapse:collapse; font-size:.85rem; }
  th, td { text-align:left; padding:.4rem .5rem; border-bottom:1px solid var(--line);
           vertical-align:top; }
  th { color:var(--muted); font-weight:600; font-size:.75rem; text-transform:uppercase;
       letter-spacing:.04em; }
  tr.shared td { font-weight:500; }
  tr.shared td:first-child { border-left:3px solid var(--accent); }
  .pill { display:inline-block; font-size:.7rem; padding:.05rem .4rem; border-radius:10px;
          background:var(--code); color:var(--muted); }
  code { background:var(--code); padding:.05rem .3rem; border-radius:4px; font-size:.85em; }
  .note { color:var(--muted); font-size:.8rem; margin:.8rem 0; }
  .caveat { border-left:3px solid var(--muted); padding:.55rem .8rem; background:var(--panel);
            border-radius:0 7px 7px 0; font-size:.83rem; color:var(--muted);
            margin:1.2rem 0 0; }
  /* The "why these two" block. Given prominence deliberately: it is the first question. */
  .why { background:var(--panel); border:1px solid var(--line); border-left:3px solid
         var(--accent); border-radius:0 9px 9px 0; padding:.7rem .9rem; margin:0 0 1.1rem; }
  .whyhead { font-size:.74rem; text-transform:uppercase; letter-spacing:.05em;
             color:var(--muted); font-weight:600; margin-bottom:.4rem; }
  .conn { padding:.25rem 0; }
  .conn + .conn { border-top:1px solid var(--line); margin-top:.5rem; padding-top:.5rem; }
  .connmeta { font-size:.8rem; margin-bottom:.25rem; }
  .comment { margin:.15rem 0; font-size:.9rem; }
  .comment.missing { color:var(--muted); font-style:italic; }
  .pill.warn { color:#D55E00; }
  ul.paths { margin:.4rem 0 0; padding-left:1.1rem; font-size:.85rem; }
  ul.paths li { margin:.2rem 0; }
</style>
<script>/*__3DMOL__*/</script>

<div class="wrap">
  <h1>__TITLE__</h1>
  <p class="sub">__SUB__</p>

  <!-- Leads the page on purpose. A reader shown two things side by side asks why they are
       together before they ask anything else, and the graph already knows. -->
  <div id="why"></div>

  <div class="panelrow">
    <div class="cap" id="capL"></div>
    <div class="cap" id="capR"></div>
  </div>
  <div id="grid"></div>

  <div class="bar">
    <button id="bPart" class="on">Part only</button>
    <button id="bPocket">Part plus pocket</button>
    <button id="bSurface">Pocket surface</button>
    <button id="bLabels" class="on">Residue labels</button>
    <button id="bDir">Directional only</button>
    <button id="bFit">Re-centre</button>
  </div>
  <div class="legend" id="legend"></div>

  <h2 style="font-size:1rem;margin:1.3rem 0 .4rem">Interactions, shared and unique</h2>
  <p class="note">Rows with a coloured left edge occur on <b>both</b> sides. Ordered so those
    come first, because that is the transferable part.</p>
  <table id="tbl">
    <thead><tr><th>Interaction</th><th>Left residues</th><th>Right residues</th>
      <th>What it constrains</th></tr></thead>
    <tbody></tbody>
  </table>

  <div id="ctx"></div>

  <div class="caveat">
    <b>This view does not claim the two sides are positionally equivalent.</b> Residue
    numbering differs between structures, so deciding that a residue on the left "is" a
    residue on the right needs a sequence-guided superposition — which
    <code>compare_structures</code> computes and labels an estimate. The table above compares
    interaction <i>kinds</i> and residue <i>identities</i>, which the coordinates support
    directly.
  </div>
</div>

<script>
const D = /*__DATA__*/;
const PDB = { left: __PDB_L__, right: __PDB_R__ };

document.getElementById('capL').innerHTML =
  D.left.label + ' <span class="k">' + (D.left.id) + '</span>';
document.getElementById('capR').innerHTML =
  D.right.label + ' <span class="k">' + (D.right.id) + '</span>';

// ---- legend, built only from kinds actually present -------------------
const present = new Set([...D.left.contacts, ...D.right.contacts].map(c => c.kind));
document.getElementById('legend').innerHTML = [...present].sort().map(k =>
  '<div><span class="sw" style="background:' + (D.contactColor[k] || '#888') + '"></span>' +
  k.replace(/_/g, ' ') + '</div>').join('');

// ---- table -----------------------------------------------------------
document.querySelector('#tbl tbody').innerHTML = D.rows.map(r =>
  '<tr class="' + (r.shared ? 'shared' : '') + '">' +
  '<td><span class="sw" style="display:inline-block;width:16px;height:3px;background:' +
    (D.contactColor[r.kind] || '#888') + ';margin-right:.4rem;vertical-align:middle"></span>' +
    r.kind.replace(/_/g, ' ') +
    (r.shared ? ' <span class="pill">both</span>' : '') + '</td>' +
  '<td>' + (r.left.join(', ') || '<span class="pill">none</span>') + '</td>' +
  '<td>' + (r.right.join(', ') || '<span class="pill">none</span>') + '</td>' +
  '<td>' + r.note + '</td></tr>').join('');

// ---- why these two are together, straight off the edge ----------------
(function () {
  const C = D.connection || { kind: 'none', direct: [], paths: [] };
  const esc = s => String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const el = document.getElementById('why');
  let h = '<div class="why">';

  if (C.kind === 'direct') {
    h += '<div class="whyhead">Connected in the graph</div>';
    for (const r of C.direct) {
      const arrow = r.direction === 'reverse' ? '&larr;' : '&rarr;';
      h += '<div class="conn">';
      h += '<div class="connmeta"><code>' + esc(r.predicate) + '</code> ' + arrow +
           ' <span class="pill">' + esc(r.confidence) + '</span>' +
           (r.score ? ' <span class="pill">' + esc(r.score) + '</span>' : '') +
           (r.n_evidence ? ' <span class="pill">' + r.n_evidence + ' citation' +
              (r.n_evidence > 1 ? 's' : '') + '</span>'
            : ' <span class="pill warn">uncited</span>') +
           (r.illustrative ? ' <span class="pill warn">placeholder value</span>' : '') +
           '</div>';
      h += r.commentary
        ? '<p class="comment">' + esc(r.commentary) + '</p>'
        : '<p class="comment missing">This edge carries no commentary, so the graph records ' +
          'that these two are related and not what that means. The number above is ' +
          'checkable and not yet usable.</p>';
      h += '</div>';
    }
  } else if (C.kind === 'path') {
    h += '<div class="whyhead">No direct edge &mdash; connected through ' +
         C.paths.length + ' shared neighbour' + (C.paths.length > 1 ? 's' : '') + '</div>';
    h += '<p class="comment">Nothing in the graph asserts these two are related directly. ' +
         'They share the neighbours below, which is a weaker claim and often the more ' +
         'interesting one &mdash; the intermediate is what they have in common.</p>';
    h += '<ul class="paths">' + C.paths.map(p =>
      '<li><code>' + esc(p.pred_a) + '</code> &middot; <b>' + esc(p.via) + '</b>' +
      (p.via_type ? ' <span class="pill">' + esc(p.via_type) + '</span>' : '') +
      ' &middot; <code>' + esc(p.pred_b) + '</code>' +
      (p.commentary ? '<br><span class="comment">' + esc(p.commentary) + '</span>' : '') +
      '</li>').join('') + '</ul>';
  } else {
    h += '<div class="whyhead">Why these two are side by side is not recorded</div>';
    h += '<p class="comment missing">No connecting edge and no shared neighbour was passed ' +
         'to this view. The comparison below is still readable, but nothing here says the ' +
         'pair is worth comparing &mdash; that judgement was made outside the graph and is ' +
         'not auditable from this page.</p>';
  }
  h += '</div>';
  el.innerHTML = h;
})();

if (D.graphContext && D.graphContext.length) {
  document.getElementById('ctx').innerHTML =
    '<h2 style="font-size:1rem;margin:1.3rem 0 .4rem">Also in the graph</h2>' +
    '<ul style="font-size:.86rem;padding-left:1.1rem">' +
    D.graphContext.map(s => '<li>' + s + '</li>').join('') + '</ul>';
}

// ---- viewers ---------------------------------------------------------
const CFG = { backgroundAlpha: 0 };
// Called exactly once. Calling it per side appends a second canvas and the panes desync.
const grid = $3Dmol.createViewerGrid("grid", { rows: 1, cols: 2, control_all: true }, CFG);
const V = { left: grid[0][0], right: grid[0][1] };

const models = {};
for (const side of ["left", "right"]) {
  models[side] = V[side].addModel(PDB[side], "pdb");
}

let mode = "part", labels = true, dirOnly = false, surface = false;

function contactsFor(side) {
  const cs = D[side].contacts;
  return dirOnly ? cs.filter(c => c.dir) : cs;
}

function draw() {
  for (const side of ["left", "right"]) {
    const d = D[side], v = V[side];
    v.removeAllLabels();
    v.removeAllShapes();
    v.removeAllSurfaces();

    // Protein: thin cartoon so the part reads as the subject, not the backbone.
    v.setStyle({ chain: d.chain, hetflag: false },
               { cartoon: { color: "#c9c9c6", thickness: 0.22, opacity: mode === "part" ? 0.55 : 0.9 } });

    const cs = contactsFor(side);
    const resis = cs.map(c => c.resi);

    // Contact residues as sticks, coloured by the kind of contact they make.
    for (const c of cs) {
      v.addStyle({ chain: d.chain, resi: c.resi, hetflag: false },
                 { stick: { radius: 0.16, color: D.contactColor[c.kind] || "#888" } });
      if (labels) {
        v.addResLabels({ chain: d.chain, resi: c.resi, atom: "CA" }, {
          fontSize: 10, showBackground: true, backgroundOpacity: 0.55,
          backgroundColor: "black", fontColor: "white",
        });
      }
    }

    // The part itself. highlight[] narrows the ligand to a fragment by atom serial.
    if (d.ligandResn) {
      const whole = { resn: d.ligandResn };
      const part = (d.highlight && d.highlight.length)
        ? { resn: d.ligandResn, serial: d.highlight } : whole;
      // Non-part ligand atoms stay as thin lines, so a fragment is visibly part of a whole.
      v.setStyle(whole, { line: { colorscheme: "greyCarbon", opacity: 0.5 } });
      v.addStyle(part, { stick: { radius: 0.2, colorscheme: "cyanCarbon" } });
    }

    if (mode !== "part" && resis.length) {
      v.addStyle({ chain: d.chain, resi: resis, hetflag: false },
                 { stick: { radius: 0.1 } });
    }
    if (surface && resis.length) {
      v.addSurface($3Dmol.SurfaceType.VDW, { opacity: 0.62, color: "#b8b8b4" },
                   { chain: d.chain, resi: resis, hetflag: false });
    }

    // Dashed lines for directional contacts, drawn residue-CA to ligand centroid. An
    // approximation of the true donor-acceptor vector, and labelled as one in the caption
    // rather than drawn as if it were the measured geometry.
    if (d.ligandResn) {
      const lig = v.getModel().selectedAtoms({ resn: d.ligandResn });
      if (lig.length) {
        const cen = lig.reduce((a, at) => ({ x: a.x + at.x / lig.length,
                                             y: a.y + at.y / lig.length,
                                             z: a.z + at.z / lig.length }),
                               { x: 0, y: 0, z: 0 });
        for (const c of cs.filter(x => x.dir)) {
          const ca = v.getModel().selectedAtoms(
            { chain: d.chain, resi: c.resi, atom: "CA" })[0];
          if (!ca) continue;
          v.addLine({ start: { x: ca.x, y: ca.y, z: ca.z }, end: cen,
                      dashed: true, color: D.contactColor[c.kind] || "#888" });
        }
      }
    }

    if (d.ligandResn) v.zoomTo({ resn: d.ligandResn });
    else if (resis.length) v.zoomTo({ chain: d.chain, resi: resis });
    else v.zoomTo();
    v.zoom(mode === "part" ? 1.5 : 1.1);
  }
  V.left.render(); V.right.render();
}

function tog(id, on) { document.getElementById(id).classList.toggle('on', on); }
document.getElementById('bPart').onclick = () => {
  mode = "part"; tog('bPart', true); tog('bPocket', false); draw(); };
document.getElementById('bPocket').onclick = () => {
  mode = "pocket"; tog('bPart', false); tog('bPocket', true); draw(); };
document.getElementById('bSurface').onclick = () => {
  surface = !surface; tog('bSurface', surface); draw(); };
document.getElementById('bLabels').onclick = () => {
  labels = !labels; tog('bLabels', labels); draw(); };
document.getElementById('bDir').onclick = () => {
  dirOnly = !dirOnly; tog('bDir', dirOnly); draw(); };
document.getElementById('bFit').onclick = () => draw();

draw();
</script>
"""
