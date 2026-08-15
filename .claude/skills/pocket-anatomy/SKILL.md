---
name: pocket-anatomy
description: >-
  Stage 2. Work out which residues in a binding site actually matter and which
  ligand fragments are complementary to each, producing an interaction map
  that downstream sampling and scoring can be conditioned on. Detects hydrogen
  bonds, hydrophobic contacts, pi-stacking, and salt bridges across known
  complexes, and renders publication-quality pocket figures. Use when
  characterising a binding site, choosing restraints, or explaining why a pose
  is or is not plausible. Trigger on: "critical residues", "binding site",
  "pocket residues", "which amino acids matter", "interaction map", "anchor
  residues", or /pocket-anatomy.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, Agent
---

# Pocket anatomy

**Owner: Denny.** This stub is contract-complete: the inputs, outputs, guard rails
and required figures are fixed, so Stage 3 can be built against it before the body
is written. Replace this body; do not change `meta.json`'s `produces` keys without
telling Sumer, because his stage consumes them.

## What this stage answers

1. Which residues line the site, and which of those are load-bearing rather than
   merely nearby?
2. For each load-bearing residue, what ligand chemistry is complementary to it?
3. Which interactions recur across *all* known complexes, and which are idiosyncratic?

## Read this before installing anything

[interaction-toolchain.md](reference/interaction-toolchain.md) records findings
measured on this machine against a real structure. Three of them will cost you an
afternoon each if you meet them cold:

- **ChimeraX is installed nowhere in this environment, and `--offscreen` is
  Linux-only.** `--nogui` alone creates no OpenGL context, so `save image` fails
  outright. On Windows you must run scripted-with-GUI, which needs a logged-in
  interactive desktop and will fail over SSH. The plan is a user-space install of
  the distro-matched build in `$HOME` on the Explorer cluster, relying on
  ChimeraX's *bundled* OSMesa because the system has none — and it is CPU
  rendering, so request cores and memory, not a GPU. **Validate `--offscreen` on a
  compute node before committing to it.** This is the largest environment risk in
  Stage 2.
- **PLIP crashes on every ligand with the pip `openbabel` wheel** (no InChI format).
  Use conda-forge openbabel, or the four-line shim in the reference.
- **ProLIF dies when driven from stdin or a notebook**, and segfaults on Python
  3.14. Run it from a real `.py` behind a `__main__` guard, on Python 3.13 or below.

## Guard rails

- **Use PLIP and ProLIF together, not one of them.** Measured on a real complex,
  they agree on only 47 % of contact residues, and *neither alone* recovers the
  canonical contact set while their union does. Their disagreement is also a free
  per-pose confidence signal, so store both edges tagged by source.

- **"Lines the pocket" is not "matters".** Rank residues by evidence — mutational
  data, conservation across the Stage 1 family corpus, recurrence across holo
  structures — not by proximity. A residue within 4 Å of every ligand may still be
  a bystander.
- **Derive the interaction map from MANY complexes, not one.** A single co-crystal
  gives you that ligand's interactions, not the pocket's grammar.
- **State whether an anchor is required or optional.** This is the trap that has
  already cost a real pipeline points: in the reference case, fragment ligands
  engaged **zero** canonical anchors, so an anchor-based prior applied uniformly
  *inverted* on the fragment half of the test set. Anchors are additive bonuses,
  never penalties for absence, unless you have evidence otherwise.
- **Report per-subpopulation validity.** Use the `stage1.subpopulations` labels.
  An interaction map valid only for drug-like ligands must say so.
- **ChimeraX must run headless and scripted.** A figure produced by clicking is
  not reproducible. Commit the `.cxc` script alongside the image.

## Workflow sketch

1. Load `stage1.template_candidates` and the target's holo structures from the graph.
2. Detect interactions per complex with PLIP or ProLIF — hydrogen bonds,
   hydrophobic contacts, pi-stacking, pi-cation, salt bridges, halogen bonds.
3. Build an **interaction fingerprint matrix**: ligand x residue x interaction type.
   This is the natural bridge to the knowledge graph — each nonzero cell is a
   `POCKET_LINED_BY` / `BINDS` edge with the interaction type in `attrs`.
4. Rank residues by recurrence and by independent evidence.
5. Map complementary fragments: for each load-bearing residue, which chemical
   groups engage it across the corpus.
6. Render figures headlessly and emit the graph delta and Model Report.

## Required visuals

- **2D interaction diagram** (PLIP/LigPlot style) for a representative complex.
- **Interaction fingerprint heatmap**: ligand x residue, cell coloured by
  interaction type — the figure that shows the pocket's grammar at a glance.
- **3D pocket render** with load-bearing residues as labelled sticks, plus a
  surface coloured by hydrophobicity.
- **Recurrence bar chart**: fraction of complexes engaging each residue, which is
  what separates anchors from bystanders.

## Handoff

`stage2.critical_residues` — per residue: id, evidence, recurrence fraction,
required-vs-optional, and the subpopulations it is valid for.
`stage2.fragment_map` — per residue: complementary chemistry.

## The interaction fingerprint is the bridge to the graph

ProLIF's `to_dataframe()` gives a three-level column index of
`(ligand, residue, interaction)`, and `fp.ifp` keeps per-interaction atom indices,
so **every nonzero cell is traceable to specific atoms and becomes one edge**. Emit
them with the source model and source structure as first-class edge attributes.

That one decision pays off twice: "which residues do five of six models agree
contact this ligand?" becomes a single graph query, and it is the *same* query that
produces the cross-model consensus signal Stage 3 wants. The graph becomes the
consensus engine rather than just a store.

## References

- [interaction-toolchain.md](reference/interaction-toolchain.md) — measured findings: which profilers to use and why both, the three install blockers with fixes, pocket-detection tools with a regression anchor, embedding 3D structures under our content-security policy, and the fingerprint-to-graph bridge
