---
name: score-normalization
description: >-
  Pick one candidate per item from a pool whose generators report confidence in
  incomparable units. Normalises within each generator before comparing across
  them, then takes the per-item argmax, and treats any more sophisticated selector
  as guilty until it beats that baseline on held-out data. Use when collapsing a
  pool to a final answer or diagnosing why a strong pool scores badly. Trigger
  on: "normalize scores", "compare across models", "incommensurable", "argmax per
  item", "pick the winner", "collapse the pool", or /score-normalization.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
---

# Score normalization

The step that converts a pool into an answer. When the pool is fixed and there are
no labels to train against, this step usually decides the score outright — and it
is the step where clever approaches most reliably lose to simple ones.

## The commensurability problem

Two generators both emit a number called "confidence". One ranges 0.3-0.6 with a
tight spread; the other ranges 0.1-0.95 with a wide one. Comparing them directly
does not select the better candidate — it selects **the generator with the more
inflated scale**, on nearly every item.

This is not a small distortion. An uncorrected cross-generator argmax frequently
degenerates into "always pick generator B", which throws away the entire pool.

The fix is to compare each candidate against **its own generator's distribution**
rather than against the raw numbers.

```python
import numpy as np

def z_by_generator(best_score_per_item):
    """best_score_per_item: {generator: 1-D array over items, aligned by item}."""
    out = {}
    for gen, s in best_score_per_item.items():
        s = np.asarray(s, float)
        sd = s.std()
        # A generator with no spread carries no ranking information. Zeroing it
        # abstains rather than dividing by ~0 and producing garbage extremes.
        out[gen] = np.zeros_like(s) if sd < 1e-12 else (s - s.mean()) / sd
    return out
```

Z-score **across all items, within one generator**. That is the axis that matters:
it asks "is this generator unusually confident here, by its own standards?", which
is the only question whose answer is comparable across generators.

## The three-step baseline

Build these in order. Each is cheap. The ordering is itself the finding.

1. **Within-generator selection.** For each generator and each item, keep that
   generator's best sample by its own native signal. A generator knows what it does
   not know, in its own units. Do not normalise yet.
2. **Cross-generator selection by z-score.** Z-score each generator's
   best-sample scores across all items, then take the argmax over generators per
   item. This step alone is typically worth more than everything else in the
   selection stage combined.
3. **Hand off the ranking.** Order items by their selected candidate's z-score.
   The bottom of that ranking is the failure tail, and it is the input to
   `tail-rescue`.

That is the baseline. It has no fitted parameters, it cannot overfit, and it is
the number every later idea has to beat.

## The selection wall

With a fixed pool and no labels to train on, sophisticated selectors lose. Not
occasionally — reliably. Things that have been tried and have regressed against the
plain z-scored argmax include:

- **Learned rankers.** A many-feature gradient-boosted ranker produced the single
  worst result of the project it was built for. With no ground truth to train
  against, the ranker learns the pool's idiosyncrasies, not quality.
- **Agentic review.** Having a capable model inspect candidates and reason about
  which looks better. It selects for *plausibility*, and plausibility is not the
  same as what the generator actually predicted.
- **Consensus and medoid.** Picking the candidate most similar to the others.
  Agreement measures shared bias; see `generator-diversity` for why.
- **Rank fusion.** Borda counts, reciprocal-rank fusion, and their relatives. They
  inherit the consensus problem with extra steps.
- **Physical or structural plausibility gates.** Filtering candidates that violate
  some domain constraint. Frequently removes correct answers, because the
  constraint is a heuristic and the correct answer is sometimes unusual.

The common thread: **each substitutes a proxy for "what did the generator actually
predict, and how sure was it?"** — and the proxy is worse.

Treat any proposal for a smarter selector as **guilty until proven innocent**.
Require it to beat the z-score baseline on held-out data, with a non-overlapping
interval, before adoption. Most will not survive that test, and the test is cheap.

## When a more complex selector is justified

Not never. The conditions:

- **You have real labels to train on**, in quantity, from the same distribution.
  This is the big one, and it is usually false.
- **The baseline's failures are systematic and characterised.** "It loses on a
  specific identifiable slice" is a reason. "It should be beatable" is not.
- **The complex selector wins on held-out data with a clear interval.** Not on the
  data it was tuned on, and not by an amount inside the noise.

## Workflow

1. Read `method.bottleneck_verdict` first. **If the verdict is
   generation-limited, stop.** The ceiling is the constraint and no selector can
   exceed it; work spent here is wasted, and the verdict exists to tell you that.
2. Read `method.candidate_pool` and `method.signal_spec`. Use the signal and the
   scope that `signal-scoping` established. Do not substitute a different field
   because it is more convenient to read.
3. Step 1: per generator, per item, best sample by native signal.
4. Step 2: z-score per generator across items, argmax per item.
5. Compute the selection-divergence matrix against any alternative selector you are
   considering — which items would each pick differently. Divergence outside a
   sane band is an early warning that one of them is broken.
6. Break results out by subpopulation. A selector can win overall while losing on
   the slice that carries the weight.
7. Emit `method.selection` and `method.confidence_ranking`.

## Reading the divergence matrix

Two selectors agreeing on 95% of items and differing on 5% is normal and useful —
the disagreements are where the comparison lives, and they are a small enough set
to inspect by hand.

Two selectors agreeing on 55% of items means one of them is close to random, and
you should find out which before comparing their scores. A near-random selector can
still post a competitive aggregate on an easy item set, and that coincidence has
misled real projects.

## Guard rails

- **Z-score within a generator before comparing across generators.** Skipping this
  lets one generator's scale dominate every item.
- **Use the scope from `method.signal_spec`.** A globally-scoped signal
  reintroduces the failure that skill exists to prevent.
- **Never let the selector see ground truth.** The leak is invisible in the final
  score, because the score is computed from the same labels. This is the one
  mistake with no external symptom.
- **Beat the baseline on held-out data, with an interval**, or do not adopt.
- **A win inside the noise floor is not a win.** Bootstrap every comparison.
- **Report every selector tried, including the losers.** A stage that reports only
  its winner hides the evidence that the winner is simple for a reason.
- **Handle the degenerate case explicitly.** A generator with near-zero spread
  produces meaningless z-scores; abstain rather than dividing by noise.

## Anti-patterns

- **Comparing raw confidences across generators.** Selects the most inflated
  scale, not the best candidate.
- **Training a ranker with no labels to train on.** Reliably the worst option
  available.
- **Consensus, medoid, or any agreement-based pick.** Measures shared bias.
- **Letting a model reason its way to a choice.** Optimises plausibility, which is
  not the target.
- **Filtering on a plausibility constraint** and quietly removing correct answers.
- **Adopting a selector that wins by 0.005 on 50 items.** That is noise wearing a
  decimal point.
- **Running this stage at all when the verdict is generation-limited.**

## Handoff

`method.selection` — the chosen candidate per item, with the generator, the raw
signal, the z-score, and the reason — and `method.confidence_ranking`, all items
ordered by selected confidence.

`method.confidence_ranking` is what makes the rescue stage possible, so its
ordering must be meaningful at the bottom end specifically. If the signal is only
calibrated in its middle range, say so: the rescue stage is about to trust the tail
of exactly this ranking.
