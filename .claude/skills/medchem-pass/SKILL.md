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
