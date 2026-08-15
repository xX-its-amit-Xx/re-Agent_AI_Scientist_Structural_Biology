"""Interactive side-by-side and overlay 3D comparison of two structures.

The question this answers is the one a biochemist asks out loud: *these two proteins
are connected in the graph — show me them next to each other and tell me what is
actually the same.* So the page does three things a static figure cannot:

1. **Side by side with linked cameras.** Rotating one rotates the other, which is the
   single interaction that makes two folds comparable by eye. Unlinked viewers force
   the reader to re-orient constantly and they give up.
2. **Overlay in a shared frame.** Structure B's coordinates are transformed into A's
   frame in Python, so the browser does no matrix maths and the overlay is exactly
   the superposition the reported RMSD was measured over.
3. **Colour by conservation, not by identity.** The default colouring answers "which
   parts of these two proteins correspond, and how well" rather than "which one is
   which" — you can already tell them apart by position.

3Dmol.js is vendored and inlined (538 KB). The page makes no network request:
``$3Dmol.download()`` and py3Dmol's ``query=`` parameter both fetch from RCSB at
runtime and are never used — coordinates are inlined as strings.
"""

from __future__ import annotations

import html
import json
from pathlib import Path

from reagent.contracts import ColorMap, Visualization, VizKind, VizMedium
from reagent.structure import Alignment, Structure

VENDOR_REL = Path("assets/vendor/3Dmol-min.js")

#: Conservation classes, in the order a legend should read them.
CONSERVED = "conserved"        # superposes closely AND same amino acid
EQUIVALENT = "equivalent"      # superposes closely, different amino acid
SHIFTED = "shifted"            # aligned but 5-10 A apart
DIVERGENT = "divergent"        # aligned but >10 A apart
UNALIGNED = "unaligned"        # no partner in the other structure

CLASS_COLOR = {
    CONSERVED: "#0072B2",
    EQUIVALENT: "#56B4E9",
    SHIFTED: "#E69F00",
    DIVERGENT: "#D55E00",
    UNALIGNED: "#9a9a9a",
}
CLASS_NOTE = {
    CONSERVED: "within 5 A and the same residue",
    EQUIVALENT: "within 5 A, different residue",
    SHIFTED: "aligned but 5-10 A apart",
    DIVERGENT: "aligned but over 10 A apart",
    UNALIGNED: "no aligned partner",
}


def _classify(distance: float, identical: bool) -> str:
    if distance <= 5.0:
        return CONSERVED if identical else EQUIVALENT
    return SHIFTED if distance <= 10.0 else DIVERGENT


def strip_waters(pdb_text: str) -> str:
    """Drop solvent. Roughly a 10-15 % size saving and it declutters the view."""
    drop = {"HOH", "DOD", "WAT"}
    keep = []
    for line in pdb_text.splitlines():
        if line[:6] in ("ATOM  ", "HETATM") and line[17:20].strip() in drop:
            continue
        if line[:6] in ("ANISOU", "CONECT", "MASTER"):
            continue
        keep.append(line)
    return "\n".join(keep)


def transform_pdb(pdb_text: str, aln: Alignment) -> str:
    """Rewrite every coordinate line with B's atoms moved into A's frame."""
    import numpy as np

    out = []
    for line in pdb_text.splitlines():
        if line[:6] not in ("ATOM  ", "HETATM"):
            out.append(line)
            continue
        try:
            xyz = np.array([float(line[30:38]), float(line[38:46]), float(line[46:54])])
        except ValueError:
            out.append(line)
            continue
        m = xyz @ aln.rotation.T + aln.translation
        out.append(f"{line[:30]}{m[0]:8.3f}{m[1]:8.3f}{m[2]:8.3f}{line[54:]}")
    return "\n".join(out)


def render(
    a: Structure,
    b: Structure,
    aln: Alignment,
    out_path: Path,
    *,
    pocket: dict | None = None,
    label_a: str | None = None,
    label_b: str | None = None,
    graph_context: list[str] | None = None,
    repo_root: Path | None = None,
) -> tuple[Path, Visualization]:
    """Write the comparison page and return it with its contract object."""
    repo_root = Path(repo_root or Path.cwd())
    vendor = repo_root / VENDOR_REL
    if not vendor.is_file():
        raise FileNotFoundError(
            f"{VENDOR_REL} is missing. Run `reagent assets fetch` — the page must "
            "inline 3Dmol.js because the publish target blocks external hosts."
        )

    name_a = label_a or a.id
    name_b = label_b or b.id

    # Per-residue conservation class, keyed the way the viewer selects residues.
    by_a = {p.a.key: p for p in aln.pairs}
    by_b = {p.b.key: p for p in aln.pairs}

    def classes(st: Structure, chain: str, table: dict, other_side: str) -> list[dict]:
        rows = []
        for r in st.chains.get(chain, []):
            pair = table.get(r.key)
            if pair is None:
                rows.append({"resi": r.seq_num, "cls": UNALIGNED, "label": r.label,
                             "partner": None, "d": None})
                continue
            partner = pair.b if other_side == "b" else pair.a
            rows.append({
                "resi": r.seq_num,
                "cls": _classify(pair.distance, pair.identical),
                "label": r.label,
                "partner": partner.label,
                "d": round(pair.distance, 2),
            })
        return rows

    res_a = classes(a, aln.chain_a, by_a, "b")
    res_b = classes(b, aln.chain_b, by_b, "a")

    lig_a, lig_b = a.primary_ligand(), b.primary_ligand()
    pocket = pocket or {}
    shared = pocket.get("shared", [])

    payload = {
        "nameA": name_a, "nameB": name_b,
        "idA": a.id, "idB": b.id,
        "chainA": aln.chain_a, "chainB": aln.chain_b,
        "sourceA": a.source, "sourceB": b.source,
        "titleA": a.title, "titleB": b.title,
        "ligandA": lig_a.name3 if lig_a else None,
        "ligandB": lig_b.name3 if lig_b else None,
        "residuesA": res_a, "residuesB": res_b,
        "classColor": CLASS_COLOR,
        "classNote": CLASS_NOTE,
        "stats": {
            "method": aln.method,
            "isEstimate": aln.is_estimate,
            "nAligned": aln.n_aligned,
            "nClose": aln.n_close,
            "rmsd": round(aln.rmsd, 2) if aln.rmsd == aln.rmsd else None,
            "tmScore": round(aln.tm_score, 3),
            "seqIdentity": round(aln.seq_identity, 3),
            "lenA": aln.len_a, "lenB": aln.len_b,
            "coverage": round(aln.coverage, 3),
            "nConserved": len(aln.conserved_pairs()),
        },
        "caveats": aln.caveats,
        "pocket": {
            "shared": shared,
            "onlyA": pocket.get("only_in_a", []),
            "onlyB": pocket.get("only_in_b", []),
            "jaccard": pocket.get("jaccard"),
            "nA": pocket.get("n_pocket_residues_a"),
            "nB": pocket.get("n_pocket_residues_b"),
            "conservedIdentity": pocket.get("conserved_identity"),
            "note": pocket.get("note"),
            # Residue numbers, so the viewer can select them directly.
            "sharedResiA": [_resi(s["a"]) for s in shared],
            "sharedResiB": [_resi(s["b"]) for s in shared],
        },
        "graphContext": graph_context or [],
    }

    pdb_a = strip_waters(a.raw_text)
    pdb_b = strip_waters(b.raw_text)
    pdb_b_moved = transform_pdb(pdb_b, aln)

    doc = _HTML
    doc = doc.replace("/*__3DMOL__*/", vendor.read_text(encoding="utf-8"))
    doc = doc.replace("/*__DATA__*/", json.dumps(payload, separators=(",", ":")))
    for token, value in (
        ("__PDB_A__", pdb_a), ("__PDB_B__", pdb_b), ("__PDB_B_MOVED__", pdb_b_moved),
    ):
        doc = doc.replace(token, json.dumps(value))
    doc = doc.replace("__TITLE__", html.escape(f"{name_a} vs {name_b}"))
    doc = doc.replace("__SUB__", html.escape(
        f"TM-score {aln.tm_score:.3f} · C-alpha RMSD {aln.rmsd:.2f} A over {aln.n_close} "
        f"residues · {aln.seq_identity:.0%} sequence identity"
    ))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as fh:
        fh.write(doc)

    try:
        rel = str(out_path.relative_to(repo_root)).replace("\\", "/")
    except ValueError:
        rel = str(out_path)

    n_shared = len(shared)
    viz = Visualization(
        id=f"V-CMP-{a.id.split(':')[-1]}-{b.id.split(':')[-1]}"[:40],
        kind=VizKind.ENSEMBLE_OVERLAY,
        medium=VizMedium.HTML_SELF_CONTAINED,
        title=f"{name_a} compared with {name_b}",
        question=(
            f"Which parts of {name_a} and {name_b} correspond structurally, and is "
            "their binding pocket built from the same residues?"
        ),
        takeaway=(
            f"{aln.n_close} of {min(aln.len_a, aln.len_b)} residues superpose within 5 A "
            f"(TM-score {aln.tm_score:.3f}, RMSD {aln.rmsd:.2f} A) at "
            f"{aln.seq_identity:.0%} sequence identity"
            + (f"; {n_shared} pocket residues are shared, {pocket.get('conserved_identity', 0)} "
               f"of them the same amino acid." if shared else ".")
        ),
        path=rel,
        reads_from=[
            a.local_path or a.id, b.local_path or b.id,
            "computed superposition (reagent.structure.align.superpose)",
        ],
        encoding={
            "cartoon_color": "conservation class of the aligned residue pair",
            "left_right_position": "which structure (side-by-side mode)",
            "spatial_overlay": "superposition in a shared frame (overlay mode)",
            "stick_residues": "ligand-pocket lining",
            "camera": "linked between the two viewers",
        },
        color_maps=[ColorMap(
            channel="cartoon_color", data_field="conservation_class",
            scale_type="categorical", mapping=CLASS_COLOR,
        )],
        interactive=True,
        alt_text=(
            f"An interactive three-dimensional comparison of {name_a} and {name_b}, "
            "shown either side by side with linked cameras or superposed in one frame. "
            "Backbone colour encodes how well each residue pair corresponds: blue where "
            "residues superpose within five angstroms and are the same amino acid, light "
            "blue where they superpose but differ, orange and vermillion where they are "
            f"aligned but displaced, grey where unaligned. {aln.n_close} residues "
            f"superpose closely out of {min(aln.len_a, aln.len_b)}."
        ),
        n_elements=aln.len_a + aln.len_b,
        params={"filtered": True, "mode": "side-by-side and overlay",
                "n_close": aln.n_close, "is_estimate": aln.is_estimate},
        covers_metrics=["tm_score", "rmsd", "seq_identity", "n_shared_pocket_residues"],
    )
    return out_path, viz


def _resi(label: str) -> int:
    """'Ser247' -> 247."""
    digits = "".join(c for c in label if c.isdigit())
    return int(digits) if digits else -1


_HTML = r"""<title>__TITLE__</title>
<style>
  :root { --bg:#fbfbfa; --panel:#fff; --ink:#1a1a1a; --muted:#5c5c5c; --line:#e2e2de;
          --accent:#0072B2; --warn:#b0562f; --code:#f4f4f2; }
  @media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
    --bg:#16171a; --panel:#1e2024; --ink:#e8e8e6; --muted:#9a9a96; --line:#32343a;
    --accent:#56B4E9; --warn:#e0a080; --code:#24262b; } }
  :root[data-theme="dark"] { --bg:#16171a; --panel:#1e2024; --ink:#e8e8e6;
    --muted:#9a9a96; --line:#32343a; --accent:#56B4E9; --warn:#e0a080; --code:#24262b; }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--ink);
         font:14px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; }
  header { padding:12px 16px 10px; border-bottom:1px solid var(--line); }
  h1 { margin:0 0 2px; font-size:16px; font-weight:600; letter-spacing:-.01em; }
  .sub { color:var(--muted); font-size:12.5px; }
  #wrap { display:flex; height:calc(100vh - 58px); }
  @media (max-width:900px){ #wrap{flex-direction:column;height:auto} #stage{height:62vh}
                            #side{width:100%;max-height:none} }
  #stage { flex:1; min-width:0; position:relative; background:var(--bg); }
  .grid { position:absolute; inset:0; }
  .grid canvas { display:block; }
  .divider { position:absolute; top:0; bottom:0; left:50%; width:1px;
             background:var(--line); z-index:4; pointer-events:none; }
  .cap { position:absolute; top:8px; z-index:5; font-size:12.5px;
         font-weight:600; background:color-mix(in srgb,var(--panel) 80%,transparent);
         padding:3px 8px; border-radius:5px; pointer-events:none; }
  .cap small { font-weight:400; color:var(--muted); }
  .hidden { display:none !important; }
  #side { width:310px; flex-shrink:0; border-left:1px solid var(--line);
          background:var(--panel); overflow-y:auto; padding:12px 14px 40px; }
  h2 { font-size:11px; text-transform:uppercase; letter-spacing:.07em; color:var(--muted);
       margin:16px 0 7px; font-weight:600; } h2:first-child{margin-top:0}
  button { font:inherit; font-size:12px; padding:5px 10px; border:1px solid var(--line);
           background:var(--bg); color:var(--ink); border-radius:5px; cursor:pointer; }
  button:hover { border-color:var(--accent); }
  button.on { background:var(--accent); color:#fff; border-color:var(--accent); }
  .row { display:flex; gap:6px; flex-wrap:wrap; }
  table.st { width:100%; border-collapse:collapse; font-size:12.5px; }
  table.st td { padding:2.5px 0; border-bottom:1px solid var(--line); }
  table.st td:last-child { text-align:right; font-variant-numeric:tabular-nums;
                           font-weight:600; }
  .lg { display:flex; align-items:center; gap:7px; font-size:12px; padding:2.5px 0; }
  .lg i { width:14px; height:6px; border-radius:2px; flex-shrink:0; }
  .lg span.n { color:var(--muted); margin-left:auto; font-variant-numeric:tabular-nums; }
  .note { color:var(--muted); font-size:11.5px; margin:6px 0; }
  .warn { background:color-mix(in srgb,var(--warn) 12%,transparent);
          border-left:3px solid var(--warn); padding:7px 9px; border-radius:4px;
          font-size:11.5px; margin:8px 0; color:var(--ink); }
  ul.pk { list-style:none; padding:0; margin:0; font-size:12px; max-height:230px;
          overflow-y:auto; }
  ul.pk li { padding:3px 0; border-bottom:1px solid var(--line); cursor:pointer;
             display:flex; gap:6px; align-items:baseline; }
  ul.pk li:hover { color:var(--accent); }
  ul.pk .d { margin-left:auto; color:var(--muted); font-variant-numeric:tabular-nums; }
  ul.pk .same { color:var(--accent); font-weight:600; }
  code { background:var(--code); padding:.05em .3em; border-radius:3px; font-size:11.5px; }
  #tip { position:fixed; z-index:30; display:none; max-width:280px; background:var(--panel);
         border:1px solid var(--line); border-radius:6px; padding:8px 10px; font-size:12.5px;
         box-shadow:0 6px 22px rgba(0,0,0,.18); pointer-events:none; }
</style>

<header>
  <h1>__TITLE__</h1>
  <div class="sub">__SUB__</div>
</header>
<div id="wrap">
  <div id="stage">
    <!-- createViewerGrid appends ONE shared canvas to this container and splits it
         into viewports, so there are no per-viewer child divs here. The captions
         and the divider are absolutely positioned above that canvas. -->
    <div class="grid" id="sbs">
      <div class="cap" id="capA" style="left:10px"></div>
      <div class="cap" id="capB" style="left:calc(50% + 10px)"></div>
      <div class="divider"></div>
    </div>
    <div class="grid hidden" id="ovl">
      <div class="cap" id="capO" style="left:10px"></div>
    </div>
  </div>

  <div id="side">
    <h2>View</h2>
    <div class="row">
      <button id="bSbs" class="on">Side by side</button>
      <button id="bOvl">Overlay</button>
    </div>
    <div class="note" id="modeNote">Cameras are linked — rotating one rotates both.</div>

    <h2>Colour by</h2>
    <div class="row">
      <button id="cCons" class="on">Conservation</button>
      <button id="cChain">Structure</button>
      <button id="cPocket">Pocket</button>
    </div>

    <h2>Show</h2>
    <div class="row">
      <button id="tLig" class="on">Ligands</button>
      <button id="tPocket">Pocket sticks</button>
      <button id="tSurf">Surface</button>
      <button id="bReset">Reset view</button>
    </div>

    <h2>Alignment</h2>
    <table class="st" id="stats"></table>
    <div id="caveats"></div>

    <h2>Legend</h2>
    <div id="legend"></div>

    <h2 id="pkHead">Shared pocket residues</h2>
    <div class="note" id="pkNote"></div>
    <ul class="pk" id="pkList"></ul>

    <h2>Graph context</h2>
    <div class="note" id="ctx"></div>
  </div>
</div>
<div id="tip"></div>

<script>/*__3DMOL__*/</script>
<script>
const D = /*__DATA__*/;
const PDB_A = __PDB_A__, PDB_B = __PDB_B__, PDB_B_MOVED = __PDB_B_MOVED__;

document.getElementById("capA").innerHTML =
  `${D.nameA} <small>${D.idA} · chain ${D.chainA}${D.ligandA ? " · " + D.ligandA : ""}</small>`;
document.getElementById("capB").innerHTML =
  `${D.nameB} <small>${D.idB} · chain ${D.chainB}${D.ligandB ? " · " + D.ligandB : ""}</small>`;
document.getElementById("capO").innerHTML =
  `<span style="color:${D.classColor.conserved}">${D.nameA}</span> +
   <span style="color:${D.classColor.divergent}">${D.nameB}</span>
   <small>superposed in ${D.nameA}'s frame</small>`;

// A linked pair for side-by-side, plus a single viewer for the overlay.
// `control_all: true` on the grid is what makes the cameras move together, and that
// one behaviour is most of what makes two folds comparable by eye.
const CFG = { backgroundAlpha: 0, antialias: true };
// Call this exactly once: it appends a canvas to the container, so calling it twice
// leaves a second orphaned canvas stacked on the first.
const grid = $3Dmol.createViewerGrid("sbs", { rows: 1, cols: 2, control_all: true }, CFG);
const vA = grid[0][0], vB = grid[0][1];
const vO = $3Dmol.createViewer("ovl", CFG);
// control_all already ties the grid together; linkViewer both ways is what 3Dmol's
// own stereo viewer does on top of it, and it is what keeps getView/setView in step.
vA.linkViewer(vB); vB.linkViewer(vA);

const mA = vA.addModel(PDB_A, "pdb");
const mB = vB.addModel(PDB_B, "pdb");
const mOA = vO.addModel(PDB_A, "pdb");
const mOB = vO.addModel(PDB_B_MOVED, "pdb");

// resi -> conservation class, for fast style lookups.
const clsA = {}, clsB = {}, partnerA = {}, partnerB = {};
D.residuesA.forEach(r => { clsA[r.resi] = r.cls; partnerA[r.resi] = r; });
D.residuesB.forEach(r => { clsB[r.resi] = r.cls; partnerB[r.resi] = r; });

const groupsBy = (cls) => {
  const out = {};
  Object.entries(cls).forEach(([resi, c]) => { (out[c] = out[c] || []).push(+resi); });
  return out;
};
const gA = groupsBy(clsA), gB = groupsBy(clsB);

let mode = "sbs", colorMode = "cons", showLig = true, showPocket = false, showSurf = false;

function styleProtein(viewer, chain, groups, flatColor) {
  viewer.setStyle({ chain, hetflag: false }, { cartoon: { color: flatColor || "#9a9a9a" } });
  if (colorMode === "cons") {
    Object.entries(groups).forEach(([c, resis]) => {
      viewer.setStyle({ chain, resi: resis, hetflag: false },
                      { cartoon: { color: D.classColor[c] } });
    });
  } else if (colorMode === "pocket") {
    const resis = groups === gA ? D.pocket.sharedResiA : D.pocket.sharedResiB;
    viewer.setStyle({ chain, hetflag: false }, { cartoon: { color: "#9a9a9a" } });
    if (resis && resis.length)
      viewer.setStyle({ chain, resi: resis, hetflag: false },
                      { cartoon: { color: D.classColor.conserved } });
  }
}

function decorate(viewer, chain, which, flatColor) {
  viewer.removeAllSurfaces();
  styleProtein(viewer, chain, which === "A" ? gA : gB, flatColor);

  if (showLig) {
    viewer.setStyle({ hetflag: true, not: { resn: ["HOH", "DOD", "WAT"] } },
                    { stick: { radius: 0.18, colorscheme: "greenCarbon" } });
  } else {
    viewer.setStyle({ hetflag: true }, {});
  }
  if (showPocket) {
    const resis = which === "A" ? D.pocket.sharedResiA : D.pocket.sharedResiB;
    if (resis && resis.length)
      viewer.addStyle({ chain, resi: resis, hetflag: false },
                      { stick: { radius: 0.12, colorscheme: "whiteCarbon" } });
  }
  if (showSurf) {
    viewer.addSurface($3Dmol.SurfaceType.VDW,
      { opacity: 0.55, color: flatColor || D.classColor.equivalent },
      { chain, hetflag: false });
  }
}

function redraw(keepView) {
  const view = keepView ? (mode === "sbs" ? vA.getView() : vO.getView()) : null;
  if (mode === "sbs") {
    decorate(vA, D.chainA, "A", colorMode === "chain" ? D.classColor.conserved : null);
    decorate(vB, D.chainB, "B", colorMode === "chain" ? D.classColor.divergent : null);
    if (view) { vA.setView(view); vB.setView(view); } else { vA.zoomTo(); vB.zoomTo(); }
    vA.render(); vB.render();
  } else {
    vO.removeAllSurfaces();
    // In overlay, colour by structure by default: you cannot tell them apart by
    // position any more, so identity becomes the useful channel.
    vO.setStyle({ model: mOA, hetflag: false }, { cartoon: { color: D.classColor.conserved } });
    vO.setStyle({ model: mOB, hetflag: false }, { cartoon: { color: D.classColor.divergent } });
    if (colorMode === "cons") {
      Object.entries(gA).forEach(([c, resis]) =>
        vO.setStyle({ model: mOA, resi: resis, hetflag: false },
                    { cartoon: { color: D.classColor[c] } }));
      vO.setStyle({ model: mOB, hetflag: false },
                  { cartoon: { color: D.classColor.unaligned, opacity: 0.65 } });
    }
    if (showLig)
      vO.setStyle({ hetflag: true, not: { resn: ["HOH", "DOD", "WAT"] } },
                  { stick: { radius: 0.2, colorscheme: "greenCarbon" } });
    if (showPocket) {
      if (D.pocket.sharedResiA?.length)
        vO.addStyle({ model: mOA, resi: D.pocket.sharedResiA, hetflag: false },
                    { stick: { radius: 0.13, colorscheme: "whiteCarbon" } });
      if (D.pocket.sharedResiB?.length)
        vO.addStyle({ model: mOB, resi: D.pocket.sharedResiB, hetflag: false },
                    { stick: { radius: 0.13, colorscheme: "yellowCarbon" } });
    }
    if (view) vO.setView(view); else vO.zoomTo();
    vO.render();
  }
}

// ---- hover: name the residue and its partner ---------------------------
const tip = document.getElementById("tip");
function hoverable(viewer, table, otherName) {
  viewer.setHoverable({}, true,
    (atom, v, ev) => {
      if (!atom) return;
      const r = table[atom.resi];
      const lines = [`<b>${atom.resn}${atom.resi}</b> chain ${atom.chain}`];
      if (r && r.partner)
        lines.push(`${D.classNote[r.cls]}<br>partner in ${otherName}: <b>${r.partner}</b> (${r.d} A)`);
      else if (r) lines.push(D.classNote[r.cls]);
      tip.innerHTML = lines.join("<br>");
      tip.style.display = "block";
      const e = ev?.pageX != null ? ev : (window.event || {});
      tip.style.left = Math.min((e.pageX || 0) + 14, window.innerWidth - 300) + "px";
      tip.style.top = ((e.pageY || 0) + 14) + "px";
    },
    () => { tip.style.display = "none"; });
}
hoverable(vA, partnerA, D.nameB);
hoverable(vB, partnerB, D.nameA);
hoverable(vO, partnerA, D.nameB);

// ---- panels ------------------------------------------------------------
const s = D.stats;
document.getElementById("stats").innerHTML = [
  ["TM-score", s.tmScore], ["C-alpha RMSD", (s.rmsd ?? "—") + " Å"],
  ["residues within 5 Å", `${s.nClose} / ${Math.min(s.lenA, s.lenB)}`],
  ["coverage", (s.coverage * 100).toFixed(0) + "%"],
  ["sequence identity", (s.seqIdentity * 100).toFixed(0) + "%"],
  ["same residue & close", s.nConserved],
  [`${D.nameA} length`, s.lenA], [`${D.nameB} length`, s.lenB],
].map(([k, v]) => `<tr><td>${k}</td><td>${v}</td></tr>`).join("");

document.getElementById("caveats").innerHTML =
  (s.isEstimate ? `<div class="warn"><b>These numbers are an estimate.</b> ` +
     D.caveats.join(" ") + `</div>` : "");

const counts = {};
D.residuesA.forEach(r => counts[r.cls] = (counts[r.cls] || 0) + 1);
document.getElementById("legend").innerHTML = Object.keys(D.classColor).map(c =>
  `<div class="lg"><i style="background:${D.classColor[c]}"></i>
     <span>${c} <span style="color:var(--muted)">— ${D.classNote[c]}</span></span>
     <span class="n">${counts[c] || 0}</span></div>`).join("");

const pk = D.pocket;
document.getElementById("pkNote").textContent = pk.note
  ? pk.note
  : `${pk.nA} residues line ${D.nameA}'s pocket and ${pk.nB} line ${D.nameB}'s; ` +
    `${pk.shared.length} correspond (${pk.conservedIdentity} are the same amino acid). ` +
    `Jaccard ${pk.jaccard}. Click one to centre on it.`;
document.getElementById("pkList").innerHTML = (pk.shared || []).map(x =>
  `<li data-a="${x.a.replace(/\D/g,'')}" data-b="${x.b.replace(/\D/g,'')}">
     <span class="${x.identical ? 'same' : ''}">${x.a}</span>
     <span style="color:var(--muted)">↔</span>
     <span class="${x.identical ? 'same' : ''}">${x.b}</span>
     <span class="d">${x.ca_distance} Å</span></li>`).join("")
  || `<li style="cursor:default;color:var(--muted)">No shared pocket residues.</li>`;

document.getElementById("pkList").addEventListener("click", ev => {
  const li = ev.target.closest("li[data-a]"); if (!li) return;
  const ra = +li.dataset.a, rb = +li.dataset.b;
  if (mode === "sbs") {
    vA.zoomTo({ chain: D.chainA, resi: [ra] }); vB.zoomTo({ chain: D.chainB, resi: [rb] });
    vA.render(); vB.render();
  } else { vO.zoomTo({ model: mOA, resi: [ra] }); vO.render(); }
});

document.getElementById("ctx").innerHTML = D.graphContext.length
  ? D.graphContext.map(c => `<div>• ${c}</div>`).join("")
  : `<div>Sources: <code>${D.sourceA}</code>, <code>${D.sourceB}</code></div>`;

// ---- controls ----------------------------------------------------------
const on = (id, fn) => document.getElementById(id).addEventListener("click", fn);
const setOn = (ids, active) => ids.forEach(i =>
  document.getElementById(i).classList.toggle("on", i === active));

on("bSbs", () => { mode = "sbs"; setOn(["bSbs","bOvl"],"bSbs");
  document.getElementById("sbs").classList.remove("hidden");
  document.getElementById("ovl").classList.add("hidden");
  document.getElementById("modeNote").textContent =
    "Cameras are linked — rotating one rotates both.";
  vA.resize(); vB.resize(); redraw(false); });
on("bOvl", () => { mode = "ovl"; setOn(["bSbs","bOvl"],"bOvl");
  document.getElementById("ovl").classList.remove("hidden");
  document.getElementById("sbs").classList.add("hidden");
  document.getElementById("modeNote").textContent =
    `${D.nameB} has been transformed into ${D.nameA}'s frame using the reported superposition.`;
  vO.resize(); redraw(false); });

on("cCons", () => { colorMode = "cons"; setOn(["cCons","cChain","cPocket"],"cCons"); redraw(true); });
on("cChain", () => { colorMode = "chain"; setOn(["cCons","cChain","cPocket"],"cChain"); redraw(true); });
on("cPocket", () => { colorMode = "pocket"; setOn(["cCons","cChain","cPocket"],"cPocket"); redraw(true); });

on("tLig", e => { showLig = !showLig; e.target.classList.toggle("on", showLig); redraw(true); });
on("tPocket", e => { showPocket = !showPocket; e.target.classList.toggle("on", showPocket); redraw(true); });
on("tSurf", e => { showSurf = !showSurf; e.target.classList.toggle("on", showSurf); redraw(true); });
on("bReset", () => redraw(false));

window.addEventListener("resize", () => { vA.resize(); vB.resize(); vO.resize(); });
redraw(false);
</script>
"""
