---
name: signal-scoping
description: >-
  Find a confidence signal actually predictive of candidate quality, and prove it
  is before anything ranks on it. Restricts the signal to the sub-object being
  scored, measures discrimination directly, and carries a known-useless signal as
  a negative control that validates the harness. Use when choosing what to rank
  on, when a plausible confidence score is not working, or when building any
  selector. Trigger on: "which confidence signal", "scope the signal", "is this
  score predictive", "negative control", "discrimination auc", "what should we
  rank on", or /signal-scoping.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
---

# Signal scoping

Before you can pick a candidate you need a number that tracks quality. Most
pipelines grab whatever the generator emits by default, and most default fields
are near-useless for this purpose. This skill finds one that works and proves it.

Two failures dominate, and both are silent:

1. The signal is measured over the **wrong scope** — the whole output rather than
   the part being judged.
2. Nobody ever **measured** whether the signal discriminates at all. It was
   plausible, so it was adopted.

## Failure 1 — scope

A generator is confident about most of its output for reasons unrelated to the
part you are scoring. Averaging that in buries the signal under a large,
irrelevant, high-confidence mass.

The pattern generalises across every domain where it has been looked at:

| Scope | Relationship to quality |
|---|---|
| Whole emitted object | essentially none |
| Restricted to the scored sub-object | strong, and usable |

In a structural setting, model-wide confidence correlates with placement accuracy
at roughly r ≈ 0.04 — indistinguishable from nothing — while the same confidence
restricted to the ligand atoms reaches r ≈ −0.46. Same model, same run, same
underlying field. The only difference is what was averaged over.

The text-pipeline version of this mistake is ranking on whole-response log
probability when only a generated span is being judged. The retrieval version is
ranking a document by its global relevance score when only one passage answers the
query. **It is the same error every time: the denominator includes material the
metric never looks at.**

So the first question is never "which field?" It is **"over what?"** Restrict to
the sub-object the metric scores, plus its immediate context, and nothing else.

Defining "immediate context" needs an external definition of what matters — the
interacting region, the relevant residues, the answer-bearing span. If you do not
have one, say so, because guessing at the boundary is how a global score sneaks
back in wearing a local name.

## Failure 2 — never measuring

Plausibility is not evidence. Measure discrimination directly.

Binarise candidate quality at whatever threshold the task treats as success, then
compute ROC AUC of the signal against that label.

```python
import numpy as np

def auc(signal, is_good):
    """Rank-based AUC. Handles ties correctly, no sklearn dependency."""
    signal, is_good = np.asarray(signal, float), np.asarray(is_good, bool)
    order = signal.argsort()
    ranks = np.empty(len(signal), float)
    ranks[order] = np.arange(1, len(signal) + 1)
    # average ranks within tied groups
    for v in np.unique(signal):
        m = signal == v
        ranks[m] = ranks[m].mean()
    n_pos, n_neg = is_good.sum(), (~is_good).sum()
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    return float((ranks[is_good].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))
```

Interpretation, and be strict about it:

| AUC | Meaning |
|---|---|
| 0.50 | No information. Ranking on this is ranking at random. |
| 0.55-0.60 | Marginal. Probably inside the noise on a small set. |
| 0.70-0.80 | Genuinely useful. This is roughly the ceiling for native confidence. |
| > 0.90 | Suspicious. Check for leakage before celebrating. |

Rank every available field, including ones you expect to be useless. The ordering
is frequently surprising, and the fields a generator names most prominently are
rarely the best ones.

## The negative control

**Carry a signal you are confident is useless, and measure it alongside the
others.** The whole-object score from Failure 1 is the natural choice.

It should land near 0.5 AUC. If it does not, one of these is true:

- Your quality labels are wrong.
- Your alignment between candidates and labels is off by one.
- Something in the harness is leaking the answer.

In every case, **nothing downstream is trustworthy**, and you have found out
cheaply instead of after a full run. This single check catches more real bugs than
any amount of inspection, because it fails loudly on exactly the class of error
that otherwise produces plausible-looking numbers.

Keep it in the pipeline permanently. It costs one column and it is the only
continuous evidence you have that the evaluation still works.

## Workflow

1. Read `method.candidate_pool` for the native confidence fields recorded per
   candidate, and `method.scored_pool` for true quality.
2. Enumerate **every** available signal, not just the obvious one. Include
   auxiliary fields, per-part breakdowns, and anything reducible to a scalar.
   Challenger signals arrive here too: `method.physics_signals` from
   `physics-rescoring` and `method.learned_signals` from `learned-rescoring`.
   Rank them in the same table as the native ones, against the same control — a
   challenger evaluated on its own terms is a challenger that has not been tested.
3. For each, produce both the whole-object and restricted-scope variants. This
   doubles the candidate list and is usually where the winner comes from.
4. Compute AUC for all of them plus the negative control. Verify the control sits
   near 0.5 **before reading any other row**.
5. Report the full ranked table, including the losers. Which signals failed is a
   finding, and the next person will otherwise re-test them.
6. Emit `method.signal_spec` naming the chosen signal, its scope, and its measured
   discrimination — plus `method.discrimination_report` with the whole table.

## Choosing among several that work

When more than one signal discriminates, prefer in this order:

1. **Cheapest to compute.** Signals derived from files you already have beat
   anything requiring a second pass.
2. **Most local.** Tighter scope generalises better across item types.
3. **Least correlated with the others**, if you intend to combine them. Two
   signals at AUC 0.75 that correlate at 0.95 are one signal.

Combining signals is usually not worth it. A weighted blend adds parameters you
must fit, and fitting them without held-out labels is how a selector overfits.
Take the single best unless a combination beats it on held-out data.

## Guard rails

- **Ask "over what scope" before "which field".** Scope beats field choice, by a
  large margin, in every case where both have been measured.
- **Measure discrimination; never assume it.** A field named `confidence` is a
  naming decision by the generator's authors, not a measurement.
- **Verify the negative control first.** A control away from 0.5 invalidates the
  whole table, and reading the table first anchors you to numbers you will be
  reluctant to discard.
- **Never fit signal weights on the data you evaluate on.** With no held-out
  labels, prefer a single unfitted signal to any tuned combination.
- **Report the signals that failed.** Suppressing them guarantees someone repeats
  the work.
- **Re-measure after any generator change.** Signal quality is a property of the
  generator, and a version bump can silently invalidate it.
- **A signal measured on one subpopulation may invert on another.** Break the AUC
  out by slice before adopting it globally.

## Anti-patterns

- **Ranking on the generator's default output field** because it is there and it
  is called something reassuring.
- **Using a whole-object score** when the metric scores a part. The single most
  costly mistake available here.
- **Adopting a signal at AUC 0.55 on a small set** and treating it as established.
  That is inside the noise; bootstrap it before believing it.
- **Skipping the negative control** because the numbers already look sensible.
  Sensible-looking numbers are exactly what a leak produces.
- **Blending five signals with hand-tuned weights.** Every weight is a parameter
  fit on data you do not have enough of.
- **Reporting only the winner**, so the next person re-tests all the losers.

## Handoff

`method.signal_spec` — the chosen signal, the scope it is computed over, its
measured AUC with an interval, and the negative control's value — and
`method.discrimination_report`, the full ranked table with the failures included.

State the scope explicitly and unambiguously in `method.signal_spec`. Downstream
selection depends on it, and "confidence" without a scope is the ambiguity this
entire skill exists to remove.
