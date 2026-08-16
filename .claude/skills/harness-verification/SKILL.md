---
name: harness-verification
description: >-
  Prove the scoring harness measures what it claims before any decision is made
  from a number it produced. Runs identity and perturbation tests, checks that the
  implemented metric is the one being graded on, and makes failures penalties
  rather than silent skips. Use before building on a new evaluation, when scores
  look surprising, or when adopting a convenient metric in place of the official
  one. Trigger on: "verify the scorer", "is my metric right", "identity test",
  "does the harness work", "sanity check the evaluation", "the scores look
  wrong", or /harness-verification.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
---

# Harness verification

Every number downstream comes from here. A harness that is subtly wrong does not
announce itself — it produces plausible numbers that rank configurations in the
wrong order, and every decision made from them is quietly wrong.

Verify it before you build on it. The tests below take under an hour and have
repeatedly caught errors that would have invalidated weeks of work.

## Test 1 — identity

**Score the ground truth against itself.** The result must be the metric's perfect
value: 1.0 for a normalised similarity, 0.0 for a distance.

This is trivial and it catches an enormous class of bugs: misaligned item ids,
transposed arguments, wrong file parsing, a metric computed over the wrong subset,
unit confusion. If a reference does not perfectly match itself, nothing else the
harness says means anything.

Run it on a handful of items, not one. A single item can pass by coincidence when
ids are misaligned.

## Test 2 — perturbation monotonicity

Take a correct answer and degrade it by a known, increasing amount. The score must
degrade monotonically.

If small perturbations produce large score changes, the metric is unstable near the
answer and small differences between configurations are not meaningful. If large
perturbations produce small changes, the metric is not sensitive to the thing you
care about and will not distinguish a good pipeline from a mediocre one.

Both outcomes are worth knowing before you start optimising against it.

## Test 3 — the metric is the graded metric

Read the actual definition of what you are scored on, then read your
implementation, then compare them line by line.

The failure mode here is substituting a *convenient* metric for the *real* one.
These often correlate, which is what makes the substitution tempting and what makes
it dangerous — they correlate right up until the point where they diverge, which is
usually near the top of the ranking where the decisions get made.

A concrete instance: an available toolkit measured whole-object agreement while the
task graded a specific interaction. An answer with the right overall shape and the
detail in entirely the wrong place scored *well* on the convenient metric and
*badly* on the real one. Optimising the convenient metric would have optimised
against the actual objective.

Three specific things to check:

- **Symmetry and equivalence.** If parts of the object are interchangeable, the
  metric must account for it. Comparing by index order when multiple valid
  correspondences exist accrues pure bookkeeping error, and it accrues it precisely
  at the decision boundary.
- **Alignment side effects.** A metric that transforms the candidate onto the
  reference before comparing will score a correctly-shaped answer in entirely the
  wrong place as a success. Read what the implementation does before comparing, not
  just what it computes after.
- **Normalisation and direction.** Is higher better? Over what range? Two
  implementations of "the same" metric frequently differ here.

## Test 4 — failures are penalties, not skips

When the scorer cannot produce a value, it must record a **worst-case penalty**,
not drop the item.

Dropping failures makes a pipeline that fails on hard items look better than one
that attempts them and does poorly, which inverts the ranking exactly where it
matters. Two configurations are only comparable if they were scored over the same
items.

Alongside the penalised mean, report **coverage**: the fraction of items the scorer
handled at all. A mean over 60% coverage and a mean over 100% coverage are
different quantities and must never be compared as if they were the same one.

```python
def apply_penalties(df, metrics, penalties):
    """Record coverage first, then fill failures with worst-case values."""
    df["coverage"] = df[metrics[0]].notna().astype(float)
    for m in metrics:
        df[m] = df[m].fillna(penalties[m])
    return df
```

## Test 5 — secondary metrics are not proxies for the primary

If the task reports several metrics, check how correlated they actually are with
the one that decides the outcome.

They are frequently less correlated than assumed. In one measured case, one
secondary metric tracked the primary at roughly +0.94 while another was
statistically decoupled at about +0.01. Ranking configurations by the decoupled one
would have been actively misleading, and it looked entirely reasonable.

Compute the correlation yourself, on your own data, and write it down. Then rank on
the primary.

## Workflow

1. Read `problem.spec` for the official metric definition, its direction, and the
   penalty convention for unscoreable items.
2. Implement or wire up the scorer. Prefer the official implementation over a
   reimplementation — a reimplementation is a second thing that can be wrong, and
   it will be wrong in ways that are hard to detect.
3. Run tests 1 through 5. Fix before proceeding; do not note and continue.
4. Score the candidate pool, emitting `method.scored_pool`.
5. Record `method.harness_certificate`: which tests were run, what they returned,
   the exact scorer version, and the date. A harness verified six months and three
   dependency upgrades ago is not a verified harness.

## What the certificate should contain

| Field | Why |
|---|---|
| Identity test result | The single most informative line |
| Perturbation curve | Establishes sensitivity and stability |
| Metric definition, as implemented | Lets a reader check the substitution question |
| Penalty values and coverage convention | Makes two runs comparable |
| Inter-metric correlations | Prevents ranking on a decoupled secondary |
| Scorer version and environment | Makes the certificate reproducible |

## Guard rails

- **Never substitute a convenient metric for the graded one.** Correlated is not
  identical, and they diverge where decisions are made.
- **Run the identity test before anything else.** A harness that fails it produces
  numbers with no interpretation at all.
- **Penalise failures; never drop them.** Dropping inverts comparisons between
  configurations with different failure rates.
- **Always report coverage next to the mean.** They are meaningless apart.
- **Prefer the official implementation.** Yours is a second thing that can be
  wrong, in ways nobody will look for.
- **Re-verify after any dependency change.** A container tag, a library upgrade, or
  a parsing change can silently alter results.
- **Treat a suspiciously good score as a bug report.** The prior on "we did
  unexpectedly well" is much lower than the prior on "something leaked".

## Anti-patterns

- **Building a full pipeline before verifying the scorer.** Every number produced
  in the meantime has to be recomputed, and some conclusions will not survive it.
- **Reimplementing the metric because the official one is inconvenient to
  install.** Install it. Inconvenience is cheaper than a wrong ranking.
- **Comparing runs with different coverage** as though the means were commensurate.
- **Using an alignment-based comparison** that transforms the candidate onto the
  reference and thereby scores misplaced answers as correct.
- **Ranking on a secondary metric** without checking its correlation with the
  primary.
- **Trusting a certificate from before the last upgrade.**

## Handoff

`method.scored_pool` — every candidate's true score under the verified metric —
and `method.harness_certificate`, the evidence that those scores mean what they
appear to mean.

Everything downstream is conditional on this certificate. When it is stale, say so
loudly rather than quietly rerunning: a stale certificate makes every conclusion
built on it provisional, and readers need to know which conclusions those are.
