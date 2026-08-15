---
name: pocket-dynamics
description: >-
  Stage 2. Characterise how much a binding site moves, which conformational
  states it occupies, and therefore which conformer a structure prediction
  should be targeting. Produces a conformer ensemble and a per-residue
  flexibility map, with movies and overlays that make the motion visible. Use
  when a pocket is suspected to be plastic, when predictions disagree in a
  flexible region, or when choosing a receptor conformer for docking. Trigger
  on: "pocket dynamics", "flexibility", "conformational change", "is the
  pocket rigid", "which conformer", "induced fit", or /pocket-dynamics.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
---

# Pocket dynamics

**Owner: Denny.** Contract-complete stub — replace the body, keep the interface.

## What this stage answers

Is the pocket one shape or several? If several, which shape should a predictor aim
at, and does the right answer depend on the ligand?

## Guard rails

- **Prefer experimental ensembles to simulation.** Multiple crystal structures of
  the same protein with different ligands are direct evidence of accessible
  states; an MD trajectory is a model of them. Use the structures you have before
  buying trajectory time.
- **A flexible pocket is a warning about the metric, not just the biology.** If the
  site moves more than the scoring tolerance, then "correct" is ill-defined and a
  single predicted conformer cannot win. Say so explicitly — it changes what
  Stage 3 should optimise.
- **Simulation must be gated on ground truth before it is trusted.** In the
  reference case, local MD refinement could not recover a 2 Å ligand translation
  and was correctly abandoned. Validate against known complexes first; MD that
  cannot fix a known error will not fix an unknown one.
- **Cost gate.** MD spends real credits. Estimate first, write it into a proposal,
  and get an accepted decision before launching.

## Workflow sketch

1. Superpose all holo structures of the target from the graph; measure per-residue
   displacement. This is free and often sufficient.
2. Cluster into discrete conformational states; check whether state correlates with
   ligand size, chemotype, or the Stage 1 subpopulation labels.
3. Compute pocket volume per state (fpocket or equivalent) and report the range.
4. Only if 1-3 leave a real question open, run restrained MD — and gate it on
   recovering known complexes first.

## Required visuals

- **Ensemble overlay**: all states superposed, coloured by state, pocket residues
  as sticks.
- **Per-residue displacement (RMSF-style) trace**, with the load-bearing residues
  from `pocket-anatomy` marked — the figure that says whether the residues that
  matter are also the ones that move.
- **Pocket volume distribution** across states.
- Optionally a short **movie** interpolating between states; motion is the one
  thing a still image genuinely cannot convey.

## Handoff

`stage2.conformer_ensemble` — the states worth predicting against, with which
ligand classes each suits. `stage2.flexibility_map` — per-residue displacement
with the tolerance comparison spelled out.
