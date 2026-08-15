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
