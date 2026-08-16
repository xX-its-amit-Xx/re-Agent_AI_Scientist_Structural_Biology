---
name: medchem-pass
description: >-
  Stage 4. Review selected poses for chemistry that a medicinal chemist would
  reject — clashes, strained conformers, implausible placements — and apply
  conservative coordinate-only corrections tiered by severity. Every edit is
  logged and reversible, and the pass is validated as a whole before it is
  allowed to replace the incumbent. Use when polishing final poses or triaging
  geometry problems. Trigger on: "medchem review", "fix the poses", "clashes",
  "strained conformer", "geometry cleanup", or /medchem-pass.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, Agent
---

# Medchem pass

**Owner: Amit.** Stage 4's chemistry review: look at the selected poses the way a medicinal
chemist would, and apply conservative coordinate-only corrections where something is clearly
wrong.

## Expect this pass to do nothing

Twenty light-tier edits on this project's reference case scored **0.5613 against an unedited
0.5640** - inside the noise and slightly negative. That is the honest prior, and it should change
how the pass is run: **the goal is to do no harm while fixing the few poses that are genuinely
broken**, not to improve the mean.

A medchem pass reporting a large gain should be checked for leakage before it is believed. The
leakage path is short here - adjust coordinates, the score improves, and you cannot tell from the
inside whether you improved the pose or moved atoms toward the answer. `coordinate-surgery`
enforces blindness for exactly this reason.

## What to look for, in order

Findings come from a profiler and the Stage 2 interaction matrix, not from looking at pictures.
"0.9 A overlap between the ligand carbonyl O and Leu240 CD1" is a defect that can be verified as
fixed; "the pose looks wrong" is not.

1. **Clashes** - overlaps with pocket residues. Most are a protonation mismatch between the
   prediction and the clash checker, which is free to rule out and is not a geometry problem.
2. **Internal strain** - implausible torsions, non-planar aromatics. Sensitive to force-field
   parameterisation, so confirm the strain is real before acting on it.
3. **Amides and rings 180 degrees out** - common, discrete, and hard for a model to fix. The best
   value-for-risk edits available.
4. **Occluding side chains** - a library rotamer swap, never a free adjustment.
5. **A group in the wrong sub-pocket lobe** - a rigid move, using `parts-inventory`'s sub-region
   decomposition to say which lobe it should be in.
6. **Poses that are simply misplaced** - not this pass. That is a `pocket_collapsed` or placement
   failure and belongs to `hypothesis-experiment`'s ladder. **Local refinement cannot fix a
   placement error**, and neither can editing by hand.

## How to run it

Every edit goes through `coordinate-surgery`: typed operation, seven geometry checks, restrained
minimisation after anything non-rigid, hashed before and after, blind to the reference. Route the
whole pass as a `hypothesis-experiment` - predict the delta *before* applying, so a surprise is
informative rather than rationalised afterwards.

Target the failure tail, using `stage3.failure_tail`. Blanket application dilutes the wins with
regressions on already-good poses, and the per-item chart is where that shows up.

## Guard rails

- **Coordinates only. Never touch the molecular graph.** Atom names, connectivity,
  and bond orders must survive untouched or the submission validator rejects the
  entry and the item scores zero.
- **Tier every edit and apply conservatively.** keep / light / drastic. In the
  reference case, applying the 20 light-tier edits landed within noise of the base
  and was a small net *negative* (0.5613 vs 0.5640). Expect this pass to do
  nothing, and be pleased if it does no harm.
- **NEVER let an agent redraw a ligand freely.** The reference case has the
  cautionary number: an agentic free re-draw took one pose from 3.88 Å to
  **24.63 Å**. Agents hallucinate unphysical geometry with total confidence.
  Constrain edits to small rigid-body and torsion adjustments.
- **Validate the whole pass before adopting it.** Compare against the incumbent on
  held-out ground truth. A pass that cannot demonstrate improvement should not
  ship, however sensible each individual edit looked.
- **Log every edit** with before/after and a reason. `stage4.edit_ledger` is what
  lets you revert one bad decision instead of the whole pass.

## Required visuals

- **Before/after 3D overlays** for every applied edit — the reviewer needs to see
  the change, not read about it.
- **Severity histogram** across all poses (how many keep / light / drastic).
- **Score delta per edited item**, so a single catastrophic edit cannot hide inside
  a favourable mean.
