---
name: dock-and-minimize
description: >-
  Stage 4. Refine selected poses with docking and restrained minimization,
  gated on ground truth so refinement is only adopted where it demonstrably
  helps. Targets the failure tail rather than the whole set, because
  physics-based refinement reliably improves some cases and destroys others.
  Use when polishing final predictions, relieving clashes, or attempting to
  rescue low-confidence items. Trigger on: "dock", "minimize", "refine the
  poses", "Vina", "MD refinement", "relieve clashes", or /dock-and-minimize.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
---

# Dock and minimize

**Owner: Amit.** Stage 4's physics: generate better geometry with docking, relieve strain with
restrained minimisation, and sample with MD where it is justified.

## Tools are whatever the user brought

The skill asks for a **capability** - `DOCK`, `MINIMIZE`, `MD` - and `ToolRegistry` says which
provider supplies it here. Tamarind, a local Vina, OpenMM, a cluster module, or nothing are all
answers, and the last one is a *limitation to report* rather than a step to skip quietly. A
refinement stage that silently did not refine reads as one that found nothing to fix.

Three things the registry tracks that matter more than which vendor it is:

- **`verified`** - has this binding actually run here, successfully, once? Stage 2 has already
  been bitten three times by tooling that installs and does not run: ChimeraX offscreen is
  Linux-only, PLIP crashes with the pip openbabel wheel, ProLIF segfaults from stdin. An
  unverified binding is a plan.
- **`metered`** - docking and MD are where credits go. Estimate, write it into the proposal, get
  the decision, log the spend. Never spend during design.
- **`unit_cost`** - measured from a pilot, not estimated. Only a measured per-pose cost can be
  multiplied by the item count, which is what `budget-calibration` needs.

## Scope is the consequential parameter

`Refinement.scope` - what was allowed to move - matters more than which engine ran. Two rules are
enforced by the contract rather than suggested:

**Never relax the ligand in isolation.** The bound conformer is legitimately strained, so
relaxing it toward a gas-phase minimum walks away from the answer. Measured on this project's
reference case by degrading **the ground truth itself, monotonically.** `Refinement` rejects a
ligand-only minimisation outright.

**Never minimise unrestrained.** The same failure, less extreme. Restraints keep the pose where
the prediction put it and let the strain out.

## What docking is for, and what it is not

**Use docking to generate geometry. Never to rank it.** A docking score is a scoring function
with its own biases, and selection belongs to `confidence-selection`. Feeding docking scores into
selection is the most common way a Stage 4 makes a Stage 3 worse.

## Target the tail

Use `stage3.failure_tail`. Physics-based refinement reliably improves some cases and destroys
others, so blanket application dilutes the wins with regressions on already-good poses - and the
before/after scatter with the identity line drawn is where those regressions become visible.

And the boundary: **refinement polishes a nearly-correct pose; it does not relocate a wrong one.**
MD did not recover a 2 A translation on the reference case. A badly placed pose is a generation
problem, and `hypothesis-experiment`'s ladder routes it to holo seeding or a decorrelated
generator rather than to more physics.

## Guard rails

- **Gate on ground truth before adopting anything.** Refinement is the classic
  place where a plausible improvement is a measurable regression. Validate on known
  complexes first, then apply.
- **Expect minimization to hurt as often as it helps.** In the reference case,
  ligand-only force-field relaxation of the *ground truth itself* monotonically
  degraded it — the bound conformer is legitimately strained, so relaxing toward a
  gas-phase minimum moves away from the answer. Never minimise a ligand in
  isolation.
- **Local refinement cannot fix a placement error.** MD did not recover a 2 Å
  translation. Refinement polishes a nearly-correct pose; it does not relocate a
  wrong one. Target it accordingly.
- **Apply to the failure tail, not the whole set.** Use `stage3.failure_tail`.
  Blanket application dilutes the wins with regressions on already-good poses.
- **Docking scores are not accuracy.** Use docking to *generate* geometry, never to
  rank it. Selection belongs to `confidence-selection`.
- **Cost gate.** MD spends credits. Estimate, propose, get the decision, log spend.

## Required visuals

- **Before/after RMSD scatter** on the validation gate, with the identity line
  drawn — points below it are the regressions, and they are the story.
- **Per-item delta ranked bar chart**, wins and losses side by side.
- **3D overlay** of before, after, and reference for the largest win and the
  largest loss. Show the failure, not only the success.
