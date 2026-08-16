---
name: physics-rescoring
description: >-
  Add force-field and geometric descriptors to a candidate pool as challenger
  signals, and test them fairly against the confidence baseline rather than
  adopting them because they are principled. Covers strain, clashes, buriedness
  and docking scores, and the artifacts that make each one lie. Use when asked to
  score poses on physical plausibility, or when a physics-based filter is
  proposed. Trigger on: "strain energy", "force field score", "physics
  rescoring", "is this pose physically plausible", "clash check", "energy
  minimize the pose", or /physics-rescoring.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
---

# Physics rescoring

A physics score answers "is this geometry reasonable?" The metric asks "is this
geometry *correct*?" Those diverge, and the gap is why principled scores lose to
a model's own confidence more often than anyone expects.

Build them anyway. The alternative is re-litigating the same proposal every few
weeks with no evidence either way. Build them as **challengers**, with the test
specified before the numbers arrive.

## The honest prior

Strain gating, clash filtering and physics-based rescoring have been tried on
co-folding pose pools and lost to plain z-scored native confidence. So has
docking-score rescoring. The pattern is consistent enough to plan around:

**A physics score measures plausibility. Plausibility is not accuracy.** A
generator's confidence is a statement about *its own prediction*; a force field is
a statement about *chemistry in general*. Only the first is correlated with
whether this particular prediction is right.

Where physics does earn its place: as a **filter on the impossible**, not a
ranker of the plausible. A pose with atoms inside the protein backbone is wrong
regardless of confidence. That is a narrow, high-precision use, and it is
different from ranking.

## The descriptors, and what each actually measures

| Descriptor | Measures | Lies when |
|---|---|---|
| **strain** | ligand internal energy at pose geometry minus relaxed | protonation is wrong, or the template match failed — then it measures your parsing, not the pose |
| **clashes** | atom pairs closer than a covalent-radius fraction | the generator output un-minimised coordinates, which is normal and not an error |
| **buriedness / contacts** | protein–ligand heavy-atom pairs within a cutoff | the pocket is large and shallow, where a wrong pose buries as well as a right one |
| **closest approach** | minimum protein–ligand distance | one outlier atom dominates a whole-pose judgement |
| **docking score** | a scoring function's estimate of binding | the pose was not produced by that program's search, so it sits off that function's manifold |

Compute each on the **converted, submittable pose**, not the raw generator
output. A descriptor that describes a structure you cannot submit is describing
the wrong object, and format conversion does change geometry.

## Two artifacts that will waste a day each

**Missing parameters are not zero.** When a force field has no parameters for a
molecule, record the descriptor as *absent*. Filling it with 0.0 credits
unparameterised ligands with perfect strain, and they are disproportionately the
unusual chemistry you most wanted to check.

**Un-minimised output is the norm.** Generators emit coordinates that were never
relaxed, so absolute strain and clash counts are large for everything, including
correct poses. Compare *within* the pool — rank, or z-score per generator — never
against an absolute threshold from the literature.

## Workflow

1. Read `method.candidate_pool`. Convert each candidate to submission format
   once, and compute every descriptor off that file.
2. Compute all descriptors for all candidates, including the ones you expect to
   be useless. Cheap, and the ordering is regularly surprising.
3. Record absent values as absent. Never impute.
4. Emit `method.physics_signals` — one row per candidate, joinable on item,
   generator, seed and sample.
5. Hand to `signal-scoping`, which measures discrimination with the same negative
   control as the native signals, and to `score-normalization`, which requires any
   challenger to beat the z-score baseline on held-out data with a
   non-overlapping interval.

**Do not select on these here.** This skill produces signals. Selection is one
stage, with one baseline, and adding a second selection path is how two
incompatible answers reach the submission.

## If a physics signal does win

Check these before believing it:

- **Is it winning on a subpopulation?** Strain discriminates better on flexible
  ligands than rigid ones, and a global win can be a slice win in disguise.
- **Is it correlated with the confidence signal?** If so it may be adding nothing
  beyond what you already had. Test the combination against the better single one.
- **Does it survive validation-set expansion?** A physics score with a free
  threshold has a parameter, and a parameter can overfit.
- **Is it beating the baseline, or beating a broken baseline?** Confirm the
  baseline was computed with the right scope and z-scoring first.

## Guard rails

- **Rank within the pool, never against an absolute threshold.** Generator output
  is un-minimised, so literature thresholds do not transfer.
- **Absent parameters stay absent.** Imputing zero inverts the ranking for exactly
  the molecules you care about.
- **Compute on the converted pose.** Anything else describes a structure you
  cannot submit.
- **Use physics to exclude the impossible, not to rank the plausible.** High
  precision on hard violations; no claim on the rest.
- **Never adopt on principle.** A physically motivated score still has to beat the
  baseline empirically, on data it was not tuned on.
- **State protonation explicitly.** Strain is a strong function of it, and an
  unstated choice makes the number unreproducible.
- **Report the losers.** A recorded negative result is the whole reason to build
  this, and it is what stops the next person repeating it.

## Anti-patterns

- **Filtering candidates by a strain or clash cutoff before selection.** Removes
  correct answers, because correct answers are sometimes strained, and the
  removal is invisible downstream.
- **Imputing zero for unparameterised molecules.**
- **Comparing strain against a published threshold** computed on minimised
  crystal structures.
- **Rescoring with a docking function** and forgetting the pose came from
  somewhere else entirely.
- **Adopting a physics score because it is interpretable.** Interpretability is a
  property of the explanation, not of the ranking.
- **Building a weighted combination of five descriptors** and fitting the weights
  on the evaluation set.
- **Reporting only that physics "did not help"** without the numbers. The next
  person cannot tell whether you tested it properly.

## Handoff

`method.physics_signals` — every descriptor for every candidate, with absent
values marked absent, the protonation and conversion settings recorded, and the
per-descriptor direction stated so a ranker knows which way is better.

Say plainly in the handoff which descriptors were computed and which failed, and
on how many candidates. A descriptor present on 60% of the pool and silently
missing on the rest will produce a selection that looks fine and is decided by
availability rather than by quality.
