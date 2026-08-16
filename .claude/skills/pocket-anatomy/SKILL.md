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

## What you are handed, and the split with `parts-inventory`

Run `parts-inventory` first. It does the arithmetic; this skill does the judgement, and the
split is deliberate — **merging them lets judgement hide inside a coverage number.**

| `parts-inventory` gives you | This skill decides |
|---|---|
| every sub-region of the pocket, with its lining residues accounted for | which of those residues are load-bearing |
| every piece of every test compound, with atom accounting | which pieces matter and which are dead weight |
| the interaction grid, each cell measured or explicitly out of scope | the recurrence ranking and the required-vs-optional call |

So you inherit `stage2.parts_inventory` and `stage2.interaction_matrix`, and you do **not**
have to build the fingerprint matrix yourself — it arrives with the measured-empty cells
already distinguished from the unmeasured ones. `InteractionMatrix.parts_touching_nothing()`
is the free win: compound parts measured against every protein part that engage none of them,
which is either a group to delete or a handle to grow from.

**And it is all in the Stage 1 graph, not a new one.** `PART_OF`, `CONTACTS`, `OCCUPIES` and
`COMPLEMENTARY_TO` extend the same store the literature axes populated, so *"does this
substituent engage a residue that is conserved across the promiscuous non-family templates
Stage 1 found?"* is a query rather than a project.

Two things to add on the edges you write:

- **`Edge.commentary` on every anatomy edge.** The reading of the connection in med-chem
  terms, not a restatement of the predicate. This is the sentence any side-by-side view of two
  nodes displays, and `KGStore.uncommented_edges()` lists scored edges still missing one. A
  scored edge with no commentary tells a reader that two things are related by 0.72 of
  something and leaves them to work out what to do.
- **`viz.part_comparison`** — `compare_parts <node-a> <node-b>` renders two parts side by side
  with contacts coloured by interaction kind and directional ones dashed. `INTERACTION_3D` is
  now a *required* Stage 2 figure, because a contact heatmap is a summary of a thing the reader
  has never actually seen.

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

- **Part-vs-part 3D comparison** (`INTERACTION_3D`) — two nodes side by side, each panel zoomed
  to the part rather than the protein, contacts as sticks coloured by interaction kind,
  directional contacts dashed, and a table of which interactions both sides make. This is the
  figure a med chemist actually reads; the heatmap below summarises it.
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
