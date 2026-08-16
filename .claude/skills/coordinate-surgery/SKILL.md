---
name: coordinate-surgery
description: >-
  Edit structure coordinates directly, as typed operations with mandatory geometry
  verification. Lets the agent fix a clashing rotamer, rotate a torsion, flip an amide, or
  reposition a ligand — and stops it from freely redrawing a molecule, which took a pose from
  3.88 A to 24.63 A on this project's reference case. A model may propose an edit; it may never
  be the last thing that touches the file. Every edit is blind to the reference, verified,
  minimised after, hashed, and reversible. Use when a pose has a specific fixable geometry
  defect. Trigger on: "fix the coordinates", "edit the PDB", "move the ligand", "flip that
  amide", "bad rotamer", "clashing side chain", "adjust the pose by hand", or
  /coordinate-surgery.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
---

# Coordinate surgery

Editing coordinates is a legitimate medicinal-chemistry operation and an illegitimate way to
change a number. Everything here follows from keeping those apart.

## The number that governs this skill

> An agentic free re-draw of a ligand took a pose from **3.88 Å to 24.63 Å.**

Measured on this project's reference case. That is not a bad edit — it is a model generating
unphysical geometry with complete confidence and reporting success. Two rules follow:

**Edits are typed operations, not coordinate text.** `EditOp` is a closed set — rigid translate,
rigid rotate, torsion set, rotamer swap, amide flip, ring flip, protonation, tautomer, stereo
inversion, atom delete, occupancy. A typed operation has a checkable postcondition; free text
does not. `RAW_COORDINATE` exists because sometimes nothing else expresses the fix, and it
requires an `escalation_note` saying why — enforced.

**A model may propose an edit and may never be the last thing that touches the file.** Any
operation that can change internal geometry must be followed by a restrained minimisation, and
`CoordinateEdit` rejects one that is not.

## Verification is mandatory, and absence of a check is not a pass

`GeometryCheck` is tri-state on every field: True passed, False failed, **None not checked**. All
seven must be set explicitly, and leaving one as None is a validation error.

That is deliberate and slightly annoying, because the alternative is worse: an unvalidated edit
that happens to look fine is exactly the one that ships. A failed check is a **revert**, not a
warning — the contract will not accept a failing edit that is not marked reverted.

What gets checked: bond lengths, bond angles, planarity, chirality, new clashes, the molecular
graph, and whether the file still parses. The editor does not get to certify its own work —
`checked_by` names the tool.

## Blindness, which is the part that feels fine while being wrong

If you adjust coordinates and the score improves, you may have improved the pose **or you may
have moved atoms toward the reference.** The second is leakage and it is indistinguishable from
the first from the inside.

So `blind_to_reference` defaults True, `informed_by` may not cite the answer for that item, and
the validator scans locators for reference-like names. Sighted editing is legitimate **only on a
validation gate** — where you are measuring whether the *procedure* works — and never on
anything that ships. `OptimizationRun.sighted_edits()` names them so the distinction survives
into the report.

## Never touch the molecular graph

Atom names, connectivity and bond orders must survive untouched, or the submission validator
rejects the entry and **the item scores zero rather than badly.** `EditOp.changes_the_graph`
flags the four operations that can — protonation, tautomer, stereo inversion, atom delete — and
`OptimizationRun.problems()` reports any that survived.

The one common legitimate exception is deleting a crystallisation artefact that was passed in as
a ligand. That is a `binder-census` failure being corrected late, and it should be fixed upstream
instead.

## What an edit is worth

Expect nothing. Twenty light-tier edits on the reference case scored **0.5613 against an
unedited 0.5640** — inside the noise and slightly negative. **Be pleased if this pass does no
harm.**

A Stage 4 reporting a large improvement should be checked for leakage before it is believed,
and that is not cynicism: the leakage path here is short and it feels like diligence.

## Which edits are worth attempting

Ordered by the ratio of upside to risk.

| Edit | When | Why it is safe-ish |
|---|---|---|
| rigid translate / rotate | the pose is right and sits 1–2 Å off, or in the wrong sub-pocket lobe | cannot create bad internal geometry at all |
| torsion set | one substituent clashes and a rotation relieves it | one degree of freedom, checkable |
| rotamer swap | a protein side chain occludes the ligand and a library rotamer does not | library-constrained, so it lands somewhere real |
| amide flip | the amide is 180° out, which happens and is hard for a model to fix | discrete, and the check is unambiguous |
| ring flip | the pucker is implausible for the bound conformation | discrete |
| occupancy set | partial occupancy needs recording | does not move anything |
| protonation / tautomer | the state is wrong for the pocket's pH | **changes the graph** — fix upstream if at all possible |
| atom delete | an artefact was passed in as the ligand | **changes the graph** — fix in `binder-census` instead |
| raw coordinate | nothing above expresses it | it does not, almost always. This is the 24.63 Å operation |

**And what not to attempt at all:** redrawing a ligand, rebuilding a loop, changing a fold,
placing a ligand into a pocket that does not exist. That last one is a `pocket_collapsed`
failure and belongs to `hypothesis-experiment`'s ladder — holo seeding, not surgery. **Local
refinement cannot fix a placement error;** MD did not recover a 2 Å translation on the reference
case, and neither will hand-editing.

## Reversibility

`before_sha256` and `after_sha256` on every edit, so a pass is provably reversible and a single
bad decision can be reverted without discarding the whole pass. That is what makes it safe to
try twenty edits: the unit of rollback is one edit, not the run.

## Working through it

1. **Name the defect precisely**, from a profiler or a clash report — not from looking at a
   picture. "0.9 Å overlap between the ligand carbonyl O and Leu240 CD1" is a defect; "the pose
   looks wrong" is not, and cannot be verified as fixed.
2. **Pick the least powerful operation that addresses it.** Reach for rigid before torsion,
   torsion before rotamer, and essentially never for raw.
3. **Write `why` specific to this pose.** The validator requires 25 characters and the reviewable
   standard is higher: it must name the atoms and the mechanism.
4. **Hash before, apply, hash after.**
5. **Run the geometry checks, all seven.**
6. **Minimise, restrained, in the pocket** — never ligand-only. Relaxing a bound conformer
   outside its pocket walks toward a gas-phase minimum and away from the answer, measured by
   degrading the ground truth itself, monotonically.
7. **Measure the delta with its noise floor**, and revert if it is not clearly positive.

## Anti-patterns

- **Batch-editing every pose.** Target the failure tail. Blanket application dilutes wins with
  regressions on already-good poses.
- **Trusting your own eye on geometry.** A model that has just moved atoms is the worst available
  judge of whether the result is physical. That is what the checks are for.
- **Editing toward the reference "just to see".** It will improve the score and teach nothing,
  and it is very hard to un-know afterwards.
- **Reporting a mean.** One catastrophic edit hides inside a favourable mean, which is why the
  per-item delta chart is a required figure.
- **Using raw coordinates because the typed op is fiddly.** The fiddliness is the guard rail.
- **Fixing a graph problem here** that `binder-census` or the input preparation should have
  caught. Late fixes to the graph are how a submission gets rejected.

## Required visuals

- **Before/after 3D overlay per applied edit**, via `compare_parts` — the reviewer needs to see
  the change, not read about it.
- **Severity histogram** across all poses: keep / light / drastic.
- **Per-item score delta, ranked**, wins and losses side by side, so a single catastrophic edit
  cannot hide inside a favourable mean.

## References

- [edit-catalogue.md](reference/edit-catalogue.md) — each operation: what it does to the file, its checkable postcondition, and how it fails
- [verification.md](reference/verification.md) — the seven checks, the tools that run them, and the tolerances worth using
