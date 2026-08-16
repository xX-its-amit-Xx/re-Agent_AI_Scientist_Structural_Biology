---
name: significance-discipline
description: >-
  Decide whether a measured improvement is real before it changes anything.
  Bootstraps every comparison, requires non-overlapping intervals for adoption,
  and uses validation-set expansion as an overfit detector that catches methods
  which tuned themselves to a small evaluation set. Use when comparing configs,
  reporting a result, or deciding whether to adopt a change. Trigger on: "is this
  improvement real", "error bars", "noise floor", "did we actually improve",
  "bootstrap the result", "should we adopt this", or /significance-discipline.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
---

# Significance discipline

Most reported improvements in small-evaluation-set pipelines are noise. Adopting
them is worse than doing nothing, because each one adds complexity, consumes the
budget for real work, and makes the next comparison harder to interpret.

This skill is the gate between "the number went up" and "we changed the pipeline".

## The noise floor

With a few dozen to a few hundred items, per-item variance is large and the mean
moves substantially under resampling alone. Two configurations differing by a small
margin are frequently indistinguishable.

A concrete calibration: in one setting, every method under comparison clustered
inside the noise floor on a 35-item validation set, while the same methods spanned a
five-times-wider range on the full task. The small set could not tell them apart at
all — and it produced confident-looking rankings anyway.

**Compute your noise floor before comparing anything.** Bootstrap a single
configuration against itself and look at the spread of the resampled mean. That
spread is the smallest difference your evaluation can resolve. Any reported gain
below it is not a result.

## Bootstrap

Resample items with replacement, recompute the mean, repeat. The spread of those
means is the sampling uncertainty of your score.

```python
import numpy as np

def bootstrap_mean(per_item, n=1000, seed=0):
    """per_item: 1-D array of per-item scores. Returns mean, std, and 95% CI."""
    rng = np.random.default_rng(seed)
    x = np.asarray(per_item, float)
    means = np.array([x[rng.integers(0, len(x), len(x))].mean() for _ in range(n)])
    return {
        "mean": float(means.mean()),
        "std": float(means.std()),
        "ci_lo": float(np.percentile(means, 2.5)),
        "ci_hi": float(np.percentile(means, 97.5)),
    }
```

Resample **items**, not per-candidate scores. Items are the independent unit; a
candidate is not independent of the other candidates for its own item, and
resampling at the wrong level produces intervals that are far too narrow.

## Paired comparison

When two configurations are evaluated on the same items — which they should be —
compare them **paired**. Bootstrap the per-item *difference*, not the two means
separately.

Paired comparison removes item difficulty from the variance, which is usually the
dominant term. It is substantially more sensitive, and it is free.

```python
def bootstrap_delta(a_per_item, b_per_item, n=1000, seed=0):
    """Paired difference b - a, resampled by item."""
    rng = np.random.default_rng(seed)
    d = np.asarray(b_per_item, float) - np.asarray(a_per_item, float)
    means = np.array([d[rng.integers(0, len(d), len(d))].mean() for _ in range(n)])
    return {
        "delta": float(means.mean()),
        "ci_lo": float(np.percentile(means, 2.5)),
        "ci_hi": float(np.percentile(means, 97.5)),
        "wins": int((d > 0).sum()),
        "losses": int((d < 0).sum()),
    }
```

**If the interval on the difference includes zero, there is no result.** Say that
plainly rather than reporting the point estimate and letting a reader infer more
than the data supports.

The win/loss counts are worth reporting alongside. A change that wins on 60 items
and loses on 55 by a hair is a different object from one that wins on 8 items
enormously and is neutral elsewhere, even when the means match.

## Validation-set expansion as an overfit detector

The strongest cheap diagnostic available, and almost nobody runs it.

**When the task gets easier, every honest method should improve.** Expand the
evaluation set, or restrict it to an easier slice, and re-rank. A method that does
not improve when the task gets easier has fitted itself to the original set.

This signature has caught real cases — including a selector that ranked first on a
small set and was revealed as overfit the moment the set grew. Nothing about its
original numbers looked wrong.

Run it whenever a method wins by an unexpected margin, and whenever a method is
complex enough to have fitted anything.

## The multiple-comparisons problem

Sweeping twenty configurations and reporting the best one is not a measurement. At
a 5% threshold, roughly one in twenty null results looks significant, so the winner
of a twenty-way sweep is expected to look good by chance alone.

Two defences, and use both:

- **Hold out a set the sweep never touched**, and confirm the winner there. This is
  the reliable one.
- **Report how many configurations were tried.** A reader cannot calibrate the
  winner without it, and omitting it is the most common way honest people overstate
  results.

## Workflow

1. Read `method.scored_pool` for per-item scores and `method.selection` for what
   the current configuration picks.
2. Establish the noise floor by bootstrapping the incumbent against itself.
3. For each candidate change, bootstrap the **paired** per-item difference.
4. Apply the gate: adopt only if the difference interval excludes zero.
5. For anything that passes and involved tuning, run the expansion check.
6. Break results out by subpopulation. A change can win overall and lose on the
   slice that carries the weight, and the aggregate hides it.
7. Emit `method.significance_report`.

## What the report must contain

- The noise floor, stated first, so every later number is interpretable.
- Per comparison: paired delta, 95% interval, win/loss counts, item count.
- The number of configurations tried in total.
- Every comparison run, including the ones that failed the gate. Suppressing them
  is what turns a sweep into a fishing expedition.
- The adoption decision, and which criterion decided it.

## Guard rails

- **Bootstrap by item, not by candidate.** The wrong resampling unit produces
  intervals that are far too narrow and a gate that passes everything.
- **Compare paired when evaluated on the same items.** Unpaired comparison wastes
  most of your sensitivity.
- **An interval including zero is not a result.** Not a weak result, not a
  promising trend.
- **Report the number of configurations tried.** Without it, the best of twenty is
  uninterpretable.
- **Confirm on a set the sweep never saw.** This is the only defence that actually
  works against multiple comparisons.
- **Run the expansion check on anything that was tuned.** It is nearly free and it
  catches the failure that is otherwise invisible.
- **Never re-bootstrap with a new seed until you like the interval.** That is
  sampling until significance, and it is fabrication.

## Anti-patterns

- **Reporting a point estimate with no interval.** It cannot be acted on.
- **Adopting a change inside the noise floor** because it is "directionally
  right". Direction is what noise looks like.
- **Reporting the best of a large sweep** as though it were a single measurement.
- **Comparing configurations evaluated on different item subsets.** Different
  denominators, incomparable means.
- **Concluding "no difference" from a wide interval on a tiny set.** That is a
  statement about the evaluation's power, not about the methods.
- **Treating a subpopulation win as a global win**, or the reverse.
- **Dropping the failed comparisons from the writeup.**

## Handoff

`method.significance_report` — the noise floor, every comparison with paired
intervals and win/loss counts, the number of configurations tried, the expansion
check where it applies, and the adoption decision with its criterion.

Write the noise floor at the top. It is the number that makes every other number in
the report interpretable, and a reader who does not have it will over-read every
delta below it.
