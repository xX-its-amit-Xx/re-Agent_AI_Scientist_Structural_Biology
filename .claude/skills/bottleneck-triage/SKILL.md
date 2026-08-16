---
name: bottleneck-triage
description: >-
  Decide whether a prediction pipeline is limited by what it can produce or by
  what it picks, before spending anything on improving either. Computes the pool
  ceiling against realised performance and returns a verdict that tells the whole
  team where to spend next. Use at the start of any optimisation effort, when a
  pipeline underperforms for unclear reasons, or when two people disagree about
  what to work on. Trigger on: "where should we spend", "is it generation or
  selection", "ceiling analysis", "best-of-n curve", "what's limiting us",
  "why is this underperforming", or /bottleneck-triage.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
---

# Bottleneck triage

Almost every pipeline that produces many candidates and returns one is limited by
exactly one of two things, and teams routinely work on the wrong one for weeks.
This skill takes an afternoon and settles it.

Run this **first**. Before tuning a generator, before building a selector, before
buying more compute. A measurement that redirects a month of work is worth
delaying a month of work by a day.

## The two numbers

**Realised** — the score you actually get, using whatever selection rule is
currently in place.

**Oracle** — the score you would get if an omniscient picker chose the best
candidate in the pool for every item. This is the pool's ceiling. No selector,
however clever, can exceed it.

The gap between them is the entire opportunity available to selection. What lies
above the oracle is the entire opportunity available to generation.

```
score
  ^
  |  ......................... oracle        <- ceiling of the current pool
  |         gap = what a perfect selector would buy
  |  _________________________ realised      <- what you ship today
  +---------------------------------------> 
```

## The decision rule

| Observation | Verdict | What to do |
|---|---|---|
| Oracle far above realised | **selection-limited** | Stop adding generators. Every hour goes into the picker. |
| Oracle close to realised | **generation-limited** | The picker is nearly optimal. Widen the pool or improve the generators. |
| Oracle itself below target | **generation-limited, hard** | Even perfect selection loses. No selector work is justified until the pool improves. |

"Far" and "close" are relative to the distance to your target, not absolute. A
0.05 gap is enormous if you need 0.02 to win and irrelevant if you need 0.3.

The third row is the one people skip, and it is the most important: **compute the
oracle against the target, not only against the realised score.** A pool whose
ceiling is below the number you need is a pool that cannot win, and no amount of
selection sophistication changes that. Finding this out early is the single
highest-value outcome of this skill.

## The best@k curve

One number is a verdict. The curve is a plan.

For each item, sample k candidates from the pool at random, take the best, and
average across items. Sweep k over 1, 2, 5, 10, 20, and the full pool size.

```python
import numpy as np

def best_at_k(scores_by_item, k, trials=200, rng=None, higher_is_better=True):
    """scores_by_item: list of 1-D arrays, one per item, oracle score per candidate."""
    rng = rng or np.random.default_rng(0)
    pick = np.max if higher_is_better else np.min
    out = []
    for _ in range(trials):
        out.append(np.mean([
            pick(rng.choice(s, size=min(k, len(s)), replace=False))
            for s in scores_by_item
        ]))
    return float(np.mean(out)), float(np.std(out))
```

Read the shape:

- **Still climbing at full pool size** — more sampling buys more ceiling. Sampling
  is cheap relative to a new generator; do that first.
- **Flat after k≈5** — the pool has saturated. Additional samples from the same
  generators are wasted spend. A *different* generator is the only thing that
  raises the ceiling.
- **best@1 already near oracle** — your generators barely disagree. That is a
  correlation problem, not a sampling problem.

The saturation point is directly actionable: it is the sample count to buy per
item, and everything beyond it is a refund.

## Workflow

1. Read `method.candidate_pool` — every candidate with its item id, generator,
   and provenance. If candidates were pruned before reaching you, stop: the
   ceiling you compute will be wrong in an unknown direction.
2. Read `method.scored_pool` — the true score of every candidate under the real
   metric. This requires ground truth, so it can only be done on a set where you
   have it. That is fine and expected; the point is to characterise the *pipeline*
   on a labelled set, then trust the characterisation on an unlabelled one.
3. Compute realised with the current selector, oracle with the argmax, and the
   best@k curve between them.
4. Break all three out by subpopulation. A pipeline is often generation-limited on
   one slice and selection-limited on another, and the aggregate hides it.
5. Emit `method.oracle_curve` and `method.bottleneck_verdict`. State the verdict
   as an instruction, not an observation.

## Subpopulation splits worth trying

- **Difficulty** — cheap proxies like item size, complexity, or the variance
  across generators. The hard tail usually has a different verdict from the bulk.
- **Generator agreement** — items where the generators concur versus diverge.
  High-agreement items are usually already solved; the score lives in the rest.
- **Any axis the problem statement names.** If the organisers or stakeholders
  distinguish two classes of item, measure them separately; a win on the larger
  class can be a loss on the one that carries the weight.

## Guard rails

- **Never compute the oracle with a metric different from the one you are
  scored on.** A proxy metric produces a proxy ceiling and therefore a proxy
  verdict, which is worse than no verdict because it feels quantitative.
- **The oracle is not a score you can claim.** It is a diagnostic. Reporting it
  as pipeline performance is the most common misuse of this measurement and it
  is straightforwardly dishonest.
- **Never let the oracle computation touch the selection path.** Ground-truth
  scores enter this skill and must not leave it in any form a selector can read.
  If the oracle ranking leaks into selection, every downstream number is invalid
  and the failure is invisible.
- **A pool that was filtered before you saw it has no measurable ceiling.**
  Insist on the unpruned pool. If it does not exist, say the verdict is
  unavailable rather than computing one from the survivors.
- **Recompute after any change to generation.** The verdict has a shelf life
  exactly as long as the pool it was computed on.
- **Report the gap with an interval.** On a small item set the gap has real
  variance, and a verdict derived from noise sends the team in a random direction.

## Anti-patterns

- **Optimising the selector when the oracle is barely above realised.** The
  ceiling is the ceiling. This is the most expensive mistake this skill prevents.
- **Adding a sixth generator when best@k went flat at k=3.** Measure saturation
  before buying capacity.
- **Computing the oracle on the same items you tuned the selector on**, then
  being surprised the gap looks small. Use a held-out slice.
- **Reporting a single aggregate verdict** when the subpopulation breakdown
  disagrees with it. Two verdicts are a finding; one averaged verdict is a
  mistake waiting to be made twice.
- **Treating the oracle as fixed.** It moves whenever generation changes, and a
  stale ceiling justifies stale priorities.
- **Skipping this because the answer feels obvious.** It is frequently not. The
  intuition "our models are good, our picker is naive" and the intuition "our
  picker is fine, our models are weak" are both common, and at most one is right.

## Handoff

`method.oracle_curve` — best@k for every k measured, overall and per
subpopulation, with intervals — and `method.bottleneck_verdict`, which names the
limiting stage in one word plus the evidence for it.

Write the verdict as a directive the rest of the team can act on without
re-reading the analysis. "Selection-limited: the pool's ceiling is 0.71 against a
realised 0.50, and best@k saturates at k=5, so additional generators are wasted
spend" is a plan. "The oracle gap is large" is a statistic.
