# The seven checks

`GeometryCheck` has seven boolean fields and every one must be set explicitly. None means *not
checked* and is a validation error, because the alternative — treating unchecked as passed — ships
exactly the edit nobody looked at.

| Check | Catches | Tool | Tolerance worth using |
|---|---|---|---|
| `file_parses` | a broken record, a truncated line, a bad column | the parser you will read it with | binary |
| `graph_unchanged` | atom names, connectivity, bond orders altered | RDKit canonical SMILES before/after | exact match |
| `bond_lengths_ok` | stretched or collapsed bonds | RDKit / OpenMM | no bond >0.1 Å from ideal |
| `bond_angles_ok` | bent geometry a force field would reject | RDKit / OpenMM | no angle >10° from ideal |
| `planarity_ok` | aromatic rings puckered, amides twisted | RDKit ring/amide checks | ring RMS out-of-plane <0.05 Å |
| `chirality_preserved` | an inverted stereocentre | RDKit `FindMolChiralCenters` before/after | exact match |
| `no_new_clashes` | overlaps introduced by the edit | any contact profiler | no *new* overlap >0.4 Å |

## Run them with the tool you will be graded with

`checked_by` is a required-in-practice field for a reason: a check run by a permissive parser and
a submission validated by a strict one disagree, and the disagreement surfaces at submission
time. Prefer the grader's own checker where one exists — the same discipline
`harness-verification` applies to metrics applies here to geometry.

## Two tolerances that are wrong by default

**`no_new_clashes` compares against the pre-edit state, not against zero.** Bound conformers
routinely have contacts a strict clash checker flags, and requiring zero clashes after an edit
would reject a fix that left an existing contact untouched. What matters is whether the edit
*introduced* one.

**Bond and angle tolerances are for detecting damage, not for judging quality.** A bound
conformer is legitimately strained. Tight tolerances here will reject correct geometry, which is
the same error as relaxing a ligand toward a gas-phase minimum — and that one was measured
degrading the ground truth itself, monotonically.

## The order to run them in

1. **`file_parses` first.** Everything else is meaningless if the file is broken, and this is
   the cheapest.
2. **`graph_unchanged` second.** A graph change means the submission is rejected and the item
   scores zero, which dominates any geometric consideration.
3. **The four geometric checks.** These are what minimisation will also complain about, so a
   failure here often means the minimisation would have fixed it — run the check first anyway,
   because knowing whether the edit or the minimisation did the work matters.
4. **`no_new_clashes` last**, because it needs the post-minimisation coordinates to be meaningful.

## Then minimise, and the minimisation is not optional

Any operation that can change internal geometry — everything except rigid translate, rigid rotate
and occupancy — must be followed by a restrained minimisation in the pocket.
`CoordinateEdit._non_rigid_edits_are_minimized` enforces it.

Restrained, and **never ligand-only**. `Refinement` rejects a ligand-only relaxation outright
because the bound conformer is legitimately strained and relaxing it in isolation walks toward a
gas-phase minimum — measured on this project's reference case by degrading the ground truth
monotonically.

## What a failed check means

**It means revert.** The contract will not accept a `CoordinateEdit` with a failing check that is
not marked `reverted`, and that is not a formality: a failed geometry check on an edit that
improved the score is the clearest available signal that the score improved for the wrong reason.

Record the revert rather than deleting the edit. `OptimizationRun.reverted()` is part of the
story — twenty attempted edits with eight reverted is a more informative pass than twelve edits
with the failures quietly dropped, and the reverted ones tell the next run which fixes do not
work on this target.

## Hashes

`before_sha256` and `after_sha256`, via `sha256_of()`. Two things this buys:

- **Provable reversibility.** The unit of rollback is one edit, not the run, which is what makes
  it reasonable to attempt twenty.
- **Detecting an edit that did nothing.** Equal hashes mean the operation was a no-op — usually a
  selector that matched no atoms, which otherwise passes every check and looks like a successful
  edit.

That second case is worth checking for explicitly. An edit that matched nothing is not an edit
that was safe; it is one that did not happen, and it will be recorded as a success.

## The check the contract cannot do

**Whether the edit was a good idea.** Every check here verifies that the file is still physical
and still the same molecule. None of them says the pose is better — that is the delta against the
noise floor, and it belongs to `significance-discipline`.

A pass where every edit verified cleanly and the delta was −0.003 is a pass that did no harm and
no good, which is the expected outcome. Twenty light-tier edits measured 0.5613 against an
unedited 0.5640.
