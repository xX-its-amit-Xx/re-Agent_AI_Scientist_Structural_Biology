---
name: learned-rescoring
description: >-
  Add trained scoring models to a candidate pool as challenger signals, and check
  first whether each one scores the candidate or merely the input it came from.
  Covers affinity heads, interface quality scorers, and the training-distribution
  questions that decide whether a learned score transfers. Use when adding an ML
  rescorer or asked whether a scoring model will help. Trigger on: "affinity
  prediction", "ml rescorer", "learned scoring function", "does the affinity head
  help", "interface scorer", "rescore with a model", or /learned-rescoring.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
---

# Learned rescoring

A trained scorer is attractive because it optimises something close to what you
want. It fails in ways a force field does not, and the failures are harder to see
because the output looks like a considered judgement.

## Check this first: does it score the pose, or the pair?

The single most common wasted day in this stage.

Many scoring models take **the same input the generator took** — a sequence and a
ligand — and re-predict from scratch. An affinity head of this shape returns an
identical number for every candidate of an item, because it never saw the
candidates. **It cannot rank poses.** It is a property predictor wearing a
rescorer's name.

Read the input schema before you write any integration code:

- Input is a **structure** → it can discriminate between candidates. Usable.
- Input is a **sequence plus a ligand spec** → one value per item. Useless for
  selection, whatever its accuracy.

A cheap empirical check that costs nothing: score two different candidates of the
same item and compare. Identical values mean it is scoring the pair.

This is not hypothetical. A deployed affinity tool in this project's own stack
takes a complex specification rather than coordinates, so its per-item score is
constant across the pool. Discovering that after writing a batch harness is the
expensive order to discover it in.

## What the useful ones look like

Scorers that take coordinates and return interface quality — the PAE- and
pLDDT-derived family — are the ones with a real chance here, and several are
computable from files a cofold run already produced.

Their advantage is that they were built for exactly this question: *given this
predicted complex, how likely is the interface to be right?* That is much closer
to pose accuracy than a general binding-affinity estimate is.

Their limitation: most were developed and validated on **protein–protein**
interfaces. Applying one to a protein–ligand interface is a domain shift, and the
score may be well-calibrated on the population it was fitted to and arbitrary on
yours. Say so, and measure it rather than assuming either way.

## The training-distribution questions

Ask all four before integrating, and record the answers next to the numbers:

1. **What was it trained on?** If your targets are in its training set, its score
   here is optimistic and will not reproduce.
2. **What was it trained to predict?** Affinity, interface accuracy and pose
   correctness are three different labels, and only the third is your objective.
3. **What input distribution did it see?** A scorer fitted on crystal structures
   sees un-minimised generator output as out-of-distribution.
4. **Is it calibrated, or only ranked?** You need ranking. Calibration is a bonus
   and its absence is not a defect.

## Workflow

1. Read `method.candidate_pool`. For every scorer, check the input schema and run
   the two-candidates-same-item test **before** building anything.
2. Drop any scorer that returns a constant per item. Record that you dropped it
   and why — it will be proposed again.
3. Run the survivors over every candidate. Keep native units, unnormalised.
4. Record which candidates a scorer failed on, and why. A scorer that silently
   covers 70% of the pool produces selections decided by coverage.
5. Emit `method.learned_signals`, joinable on item, generator, seed and sample.
6. Hand to `signal-scoping` for discrimination against the same negative control,
   and to `score-normalization`, where any challenger must clear the z-score
   baseline on held-out data with a non-overlapping interval.

## The correlation question that decides value

A learned scorer that correlates highly with the generator's own confidence is
adding cost, not information — the two are frequently trained on overlapping data
and share their errors.

Compute the correlation between each learned signal and the native confidence
before adopting it. Low correlation plus comparable discrimination is the
combination worth having, and it is the case where combining them might beat
either alone. High correlation means you bought a second copy.

This is the same logic `generator-diversity` applies to generators, at the level
of signals: what you want is decorrelation, not agreement.

## Guard rails

- **Verify it scores candidates, not inputs.** Two candidates, one item, compare.
  Everything else is wasted if this fails.
- **Read what it was trained on and to predict.** A scorer optimising a different
  label is a proxy, and proxies diverge where decisions are made.
- **Treat cross-domain application as a measurement, not an assumption.** A
  protein–protein interface scorer on protein–ligand data may work; find out.
- **Keep native units.** Cross-scorer comparison is `score-normalization`'s job
  and it needs the raw scale.
- **Record coverage per scorer.** Partial coverage silently decides selections.
- **Check correlation with the native confidence** before adopting. A correlated
  scorer is a duplicate.
- **Never fine-tune a scorer on the pool.** With no held-out labels this is the
  route that has produced the worst results on record.

## Anti-patterns

- **Integrating an affinity predictor without checking its input.** It will return
  one value per item and the selection will silently become arbitrary within items.
- **Assuming a published AUC transfers.** It was measured on that paper's
  distribution, not on your generator's output.
- **Adopting a scorer because it is newer or better-cited.** Neither is a property
  of your pool.
- **Blending several learned scores with fitted weights.** Every weight is a
  parameter fitted on data you do not have enough of.
- **Reporting a scorer's discrimination without its coverage.** They are not
  separable.
- **Dropping candidates the scorer could not handle.** That is selection by
  availability, and it flatters whichever generator the scorer happens to like.
- **Skipping the negative control** because a learned scorer feels more
  trustworthy than a heuristic. It is not; it is just harder to inspect.

## Handoff

`method.learned_signals` — every scorer's value per candidate in native units,
with per-scorer coverage, the training-distribution answers, and the measured
correlation against the generator's own confidence.

Include the scorers you dropped and the reason. "This one returns a constant per
item" is the single most reusable sentence this skill produces, and without it
written down the same integration gets attempted again next month.
