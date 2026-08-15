# Interaction-detection toolchain: measured findings

Everything marked **[measured]** was verified on this machine against PDB `1M13`
(human PXR ligand-binding domain with hyperforin). The rest is cited. Re-verify
before trusting anything after a dependency bump.

This document exists because the obvious setup does not work: two of the three
recommended tools fail on install in ways that produce *silence or wrong answers*
rather than errors, and the HTML they generate violates our content-security
policy.

## The headline: use PLIP **and** ProLIF, not one of them

They disagree badly, and the disagreement is the useful part. **[measured]** On
PXR–hyperforin, against the six canonical contact residues from the literature
(Met243, Ser247, Gln285, Trp299, His407, Phe420):

| | residues called | canonical recovered | polar anchors | unique contribution |
|---|---|---|---|---|
| PLIP 3.0.1 | 9 | 4 of 6 | 1 of 4 | Trp299, Phe420; **the only tool to call the Ser247 hydrogen bond** |
| ProLIF 2.2.1 | 13 | 4 of 6 | 3 of 4 | Gln285, His407 (the adaptive polar pair), Cys284, Met246, Met323, Leu411 |
| union | 15 | **6 of 6** | 3 of 4 | — |

Agreement is only **Jaccard 0.47** — seven shared residues out of fifteen. PLIP
called twelve hydrophobic contacts and one hydrogen bond; ProLIF called seven
hydrophobic and eleven van der Waals contacts and rated Ser247 as *merely* a van
der Waals contact. For a promiscuous pocket that difference is the science, not
noise.

Two consequences worth building on:

1. **Run both and store both, tagged by source.** Collapsing them loses real
   information. Keeping both makes per-edge concordance a free confidence signal.
2. **Report concordance as a per-pose metric.** Two independent profilers agreeing
   on a contact is stronger evidence than either alone, and it costs nothing extra.

This is independently supported by the interaction-recovery literature: ignoring
interaction fingerprints overestimates model performance, most notably for
protein-ligand co-folding models (Errington et al., arXiv:2409.20227).

## Three installation blockers, with fixes

### PLIP crashes on every ligand with the pip `openbabel` wheel **[measured]**

The wheel exposes 128 output formats but **no InChI**, and `Ligand.__init__` calls
`molecule.write(format='inchikey')` unconditionally, raising `ValueError`. Either
install openbabel from conda-forge, or apply this shim — validated, after which
PLIP profiled 1M13 in 2.7 seconds:

```python
from openbabel import pybel

_orig = pybel.Molecule.write

def _safe(self, format="smi", filename=None, overwrite=False, opt=None):
    if format in ("inchi", "inchikey") and format not in pybel.outformats:
        return ""          # reporting-only field; geometry is unaffected
    return _orig(self, format, filename, overwrite, opt)

pybel.Molecule.write = _safe
from plip.plipcmd import main
```

### ProLIF dies when driven from stdin or a notebook **[measured]**

`Fingerprint.run*` uses `multiprocess`, whose spawn method re-imports `__main__` in
each child. From a heredoc `__main__` is `<stdin>`, producing
`OSError [Errno 22]`. **Run it from a real `.py` file behind
`if __name__ == "__main__":`, or pass `n_jobs=1`.**

This is easy to misdiagnose as ProLIF being slow. It is not — once fixed, the same
job takes 0.4 seconds.

### ProLIF segfaults on Python 3.14 **[measured]**

`Molecule.from_mda(..., NoImplicit=True)` raises SIGSEGV on a 6 Å pocket (778
atoms) but survives at 5 Å (558 atoms). ProLIF 2.2.1 declares support only through
**Python 3.13**. **Pin the interpreter at 3.13 or below** in a locked environment.
This project's venv is 3.12, which is fine.

### They want different protonation

PLIP adds polar hydrogens only (43 in this pocket). ProLIF needs full explicit
hydrogens, or `NoImplicit=False` — which then *silently disables hydrogen-bond
detection*, the worst kind of failure. The recipe that works: protonate once
yourself with `obabel` at pH 7.4, pass `--nohydro` to PLIP (its internal routine is
non-deterministic), and give ProLIF `NoImplicit=True`.

## Tools evaluated

| Tool | Version | Scriptable | Interaction types | Output | Licence | Status |
|---|---|---|---|---|---|---|
| **ProLIF** | 2.2.1 | yes | 18, including van der Waals, face-to-face and edge-to-face pi, halogen both roles, multi-order water bridges | DataFrame, bitvectors, HTML, matplotlib | Apache-2.0 | very active |
| **PLIP** | 3.0.1 | yes, CLI and Python | 8: hydrophobic, hydrogen bond, pi-stacking, pi-cation, salt bridge, halogen, water bridge, metal | XML, TXT, PyMOL session, PNG — **no JSON** | GPL-2.0 | active |
| **pdbe-arpeggio** | 1.4.4 (2024) | yes, pip | finest ontology: weak hydrogen bond, carbonyl, weak polar, **methionine-sulphur-pi**, amide-amide | **JSON** | GPL-3.0 | stalled |
| **PoseView** (ProteinsPlus) | 2025 | yes, **free REST, no auth** | hydrogen bond, hydrophobic, ionic, pi-stack, cation-pi, water, metal; **no halogen** | SVG | free academic and commercial, 30 jobs/min | active |
| **PandaMap** | 4.3.0 | yes, pip | 15 classes | PNG, CSV, 3D HTML, report | MIT | new, single maintainer |
| **PyMOL open source** | 3.1.0 | yes, headless | **pi-stacking and pi-cation are Incentive-only** | session, ray-traced PNG | permissive | active |
| **MDAnalysis** | 2.10.0 | yes | hydrogen bond, best multi-order water bridges | ndarray | LGPL | excellent |

### Two disqualifications, stated plainly

**LigPlot+ detects no pi-interactions at all** — no pi-stacking, no pi-cation, no
halogen. A Phe/Trp/Met-lined pocket is exactly the case it cannot describe. Its
bundled licence also forbids use "as part of a service supplied to any third party
for financial reward".

**MDTraj silently fails on ligands.** It derives hydrogen-bond donors from
`topology.bonds`, which are template-built from standard residue names. A ligand
with no CONECT records gets zero bonds, so it can be an acceptor but **never a
donor, with no error raised**. That is a silent directional bias. Use MDTraj for
trajectory input/output and RMSF only.

**PoseEdit's REST endpoint is dead.** Its rendering engine,
`rareylab/InteractionDrawer` (BSD-3), is open source and JSON-driven — harvest that
instead for offline interactive 2D diagrams with no rate limit.

Also worth knowing: `psico.prolif.prolif_interactions` (BSD-2) runs ProLIF on a
PyMOL selection and materialises every typed interaction as coloured distance
objects. That is how you get pi-stacking into a headless PyMOL session, which
open-source PyMOL cannot compute itself.

**There is no deep-learning interaction annotator worth adopting.** The
deep-learning frontier is *pocket detection* (RAPID-Net, GENEOnet, DeepPocket,
GrASP). PLIP is used to generate training labels for those models, not replaced by
them.

## Pocket detection

A regression anchor, via the ProteinsPlus REST API: the PXR ligand-binding domain
(`1ILG`) through DoGSiteScorer gives **volume 1447 Å³, 57 % apolar residues,
drugScore 0.81, depth 31 Å, 284 lining atoms**. If a pipeline stage reports 300 Å³
for PXR, it fragmented the pocket. Use `/dogsite_rest`, not `/dogsite3_rest` — the
latter returns eleven pockets with a maximum of 369 Å³ on the same input, because
it subdivides a large fused cavity.

- **fpocket 4.2.3** (MIT). Accepts mmCIF since 3.0. **Its volume is Monte-Carlo
  with 2500 samples by default and jitters between runs** — pass `-b 60` for
  reproducibility. Widen `-M 7.0 -D 3.0` to stop a large pocket fragmenting.
- **pyKVFinder 0.9.3** (GPL-3, pip, pure Python, most actively maintained). The one
  usually missed, and the direct quantitative handle on "large hydrophobic pocket":
  **per-cavity hydropathy across seven scales**, plus volume, depth, lining
  residues, and residue-class frequencies. Its default `volume_cutoff=5.0` Å³
  yields dozens of junk cavities — raise it to 100-200.
- **P2Rank 2.5.1** `fpocket-rescore -c rescore_2024` (MIT) had the highest recall,
  about 60 %, in a 2024 benchmark of thirteen predictors
  (doi:10.1186/s13321-024-00923-z). Use `-c alphafold` on predicted models so
  B-factor and pLDDT are not used as features.
- **Excluded:** CASTp and CavityPlus (web only, no API), PyVOL (abandoned, plus an
  MSMS licence trap), SiteMap (commercial).

## Embedding 3D structures under our content-security policy

### Measured bundle sizes **[measured]**

| Library | Size | Verdict |
|---|---|---|
| **3Dmol.js 2.5.5 `3Dmol-min.js`** | **525 KB** | **use this** |
| 3Dmol.js unminified | 5,277 KB | ten times larger — always take the `-min` build |
| NGL 2.3.1 | 1,253 KB | inlinable, heavier |
| Mol* 4.9.0 | 4,965 KB + 73 KB CSS | 31 % of the budget for the library alone |
| pdbe-molstar 3.3.0 | 5,298 KB | marginal, and designed around PDBe APIs |
| pako_inflate 2.1.0 | 20 KB | cheap and reliable |

**3Dmol.js at 525 KB.** The selection API keys we need (`within`, `byres`,
`expand`, `invert`) plus `selectedAtoms`, `addStyle`, `addLabel`, `addSurface` and
`pngURI` were all verified present in the vendored bundle. Mol* only earns its five
megabytes if you need its specific interface, and for scripted scenes we do not.

The whole Stage 3 comparison fits in one file: a self-contained pocket viewer with
six model-coloured poses measured **622 KB, or 3.8 % of the 16 MB budget**.
Extrapolated to 184 ligands × 6 models = 1,104 poses: **1.68 MB, 10.5 %**.

Payload compression **[measured]**: a real PXR structure went 239 KB raw → 56 KB
gzip → 75 KB as base64-of-gzip, a net 3.2× after base64 overhead. Stripping waters
took 213 KB of text to 67 KB. A ligand-only pose is 3 KB → 1 KB.
`pako.inflate(bytes, {to:'string'})` round-trips every payload correctly.

### The content-security-policy trap

**`$3Dmol.download()` and py3Dmol's `query=` parameter perform a remote fetch to
RCSB. Never use them. Always `addModel(inline_string)`.**

Worse, **py3Dmol's own HTML output is CSP-fatal** **[measured]**.
`py3Dmol.view.__init__` defaults `js=` to a jsDelivr URL and loads it by injecting
a `<script>` element. `write_html(fullpage=True)` emits one external host and three
dynamic script injections; under our policy the page renders py3Dmol's own fallback
text, "3Dmol.js failed to load for some reason."

ProLIF has the same problem: its `network.html` template hard-codes an unpkg URL,
and the stylesheet `href` contains a doubled `/dist/dist/` typo so it 404s even
*with* network access.

A validated post-processor for both:

```python
import re
from pathlib import Path

VENDOR = Path("assets/vendor")   # 3Dmol-min.js (525 KB), vis-network.min.js (450 KB)

def inline_py3dmol(html: str) -> str:
    lib = (VENDOR / "3Dmol-min.js").read_text(encoding="utf-8", errors="replace")
    html = re.sub(r"\$3Dmolpromise\s*=\s*loadScriptAsync\((['\"]).*?\1\)\s*;",
                  "$3Dmolpromise = Promise.resolve();", html, flags=re.S)
    html = re.sub(r"<script[^>]*src=['\"][^'\"]*3[Dd]mol[^'\"]*['\"][^>]*>\s*</script>",
                  "", html)
    inject = f"<script>{lib}</script>\n"
    return html.replace("<head>", "<head>\n" + inject, 1) if "<head>" in html else inject + html

def inline_lignetwork(html: str) -> str:
    lib = (VENDOR / "vis-network.min.js").read_text(encoding="utf-8", errors="replace")
    # A lambda, never an f-string replacement: minified JavaScript contains \d, \n
    # and similar, and re.sub interprets escapes in a string replacement, raising
    # re.PatternError: bad escape \d.
    html = re.sub(r"<script[^>]*src=['\"][^'\"]*vis-network[^'\"]*['\"][^>]*>\s*</script>",
                  lambda _m: f"<script>{lib}</script>", html)
    return re.sub(r"<link[^>]*href=['\"][^'\"]*vis-network[^'\"]*['\"][^>]*>", "", html)
```

Validated results **[measured]**: py3Dmol output 238 KB with one CDN reference and
three injections became 764 KB with **zero** external references; ProLIF's
`LigNetwork.save()` output 32 KB with two CDN references became 481 KB with zero.
Both parse cleanly.

## Interaction fingerprints as the knowledge-graph bridge

This is the right bridge, and it is a small amount of code. **[measured]**

ProLIF's `to_dataframe()` returns rows of frames or poses against a three-level
column MultiIndex `(ligand, protein_residue, interaction)`, values boolean or
counts. Confirmed on the PXR run: `levels = ['ligand', 'protein', 'interaction']`,
shape `(1, 18)`. `fp.ifp` keeps richer per-interaction metadata including `indices`
and `parent_indices`, so **every edge is traceable to specific atoms**.
`to_bitvectors()` gives RDKit `ExplicitBitVect` for Tanimoto comparison.

A validated extraction produced thirteen triples from PXR–hyperforin, each carrying
distance, sidechain flag, and source:

```
(LIG:HYF) -[hydrophobic d=3.37A]-> (RES:LEU209)   source=xtal_1M13
```

Three design points to lock in:

**Make the source model and source structure first-class edge properties.** Then
"which residues do five of six models agree contact this ligand?" is a single graph
query — and it is the *same* query that produces the cross-model consensus
confidence signal. The graph becomes the consensus engine rather than just a store.

**Store both profilers' edges with a source tag**, given the measured 0.47
agreement.

**The taxonomy is the schema decision.** ProLIF's eighteen types are the natural
vocabulary. pdbe-arpeggio's finer ontology is worth mapping in as sub-types if you
want the resolution — its methionine-sulphur-pi class is genuinely relevant to a
Met-rich pocket.

Also relevant: **PLIPify** (MIT, actively pushed) aggregates PLIP profiles across
many structures into interaction-frequency fingerprints, which is exactly the right
shape for an ensemble of predicted poses.

## Rendering figures headlessly

Only `plot_barcode()` returns a matplotlib `Axes` and is therefore the **only
reliable headless static output** from ProLIF. `save_png()` on `LigNetwork` and
`Complex3D` triggers a *browser download* and is useless from a script.

`plot_lignetwork(kind="aggregate", threshold=0.3)` gives a consensus 2D diagram
with per-interaction occurrence percentages — the right figure for an ensemble.

## Reproducibility guardrails

Pin these, all measured or documented:

- **Python ≤ 3.13** for ProLIF.
- **`posebusters`** — 0.4.5 changed the ring checks.
- **OpenStructure 2.8.0** specifically, per Boltz's own documentation.
- **fpocket `-b 60`** rather than the stochastic Monte-Carlo default.
- **Protonate once yourself** and pass `--nohydro` to PLIP.

And never report PandaMap's free-energy estimate, fpocket's default Monte-Carlo
volume, or an absolute cryptic-pocket opening probability — a 2026 benchmark
(doi:10.1021/acs.jctc.6c00135) shows no method predicts the last of these reliably.
