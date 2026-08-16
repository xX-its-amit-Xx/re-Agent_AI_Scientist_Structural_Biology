---
name: generator-diversity
description: >-
  Build a candidate pool whose members fail on different items, and measure that
  decorrelation rather than assuming it. Covers generator choice, seed budgeting,
  pilot sizing, and the rule that diversity is for widening a pool and never for
  voting within it. Use when assembling an ensemble, choosing which models to
  run, or deciding whether another generator is worth its cost. Trigger on:
  "diversify the pool", "error correlation", "which generators", "widen the
  pool", "decorrelate", "add another model", or /generator-diversity.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
---

# Generator diversity

A pool exists so that when one generator fails, another has already succeeded on
that item. Its value is therefore **not** the average quality of its members. It
is the coverage of their union.

Six mediocre generators that fail on disjoint items beat one strong generator that
fails on a fixed subset. This is counterintuitive enough that teams reliably spend
their budget on the wrong axis: making one member better rather than making the
members differ.

## The number that decides everything

**Pairwise error correlation.** For each pair of generators, correlate their
per-item accuracy across items.

- **Low correlation (≈0.5)** — they fail on different items. Adding the second one
  raises the ceiling. This is what you are paying for.
- **High correlation (≈0.9)** — they fail on the same items. The second one costs
  full price and buys almost nothing.

Two generators with different names, different papers, and different companies can
still be highly correlated, because they were trained on overlapping data with
overlapping inductive biases. **Different provenance is not evidence of
decorrelation.** Measure it.

```python
import numpy as np

def error_correlation(acc_by_generator):
    """acc_by_generator: {name: 1-D array of per-item accuracy, aligned by item}."""
    names = sorted(acc_by_generator)
    m = np.vstack([acc_by_generator[n] for n in names])
    return names, np.corrcoef(m)
```

Report the whole matrix, not the mean. One tightly-coupled pair inside an
otherwise diverse set is a specific, fixable finding: drop the cheaper of the two
and spend the savings on seeds.

## Pilot before you commit

Never size the full run from a plan. The arithmetic is `items × generators ×
seeds`, and all three terms are usually wrong on first estimate.

1. Take a small item subset — enough to estimate correlation, far short of the
   budget. A few dozen items is normally sufficient to separate 0.5 from 0.9.
2. Run every candidate generator on it, at one seed.
3. Compute the correlation matrix and the per-generator unique-win count: on how
   many items is this generator the *only* one that succeeds?
4. Drop generators with near-zero unique wins. They are paying rent on capacity
   without contributing coverage.
5. Only now size the full run, against `method.budget_plan`.

A generator that contributes no unique wins on the pilot will not start
contributing them at scale. A generator that contributes a few will usually
contribute a few percent — which is exactly the size of the margin that decides
most competitive tasks.

## Seeds versus generators

Both widen a pool; they widen it differently.

- **Seeds** explore the same model's output distribution. Cheap, and they saturate
  — past some count, extra samples are near-duplicates.
- **Generators** explore a different distribution entirely. Expensive, and they do
  not saturate in the same way.

Spend on seeds until the best@k curve flattens, then spend on generators. Doing it
in the other order buys expensive diversity before exhausting the cheap kind.

## The rule that everything here turns on

**Use diversity to WIDEN a pool. Never to VOTE within it.**

Consensus across agreeing generators is the intuitive next step and it is wrong.
Generators that agree share correlated errors, so agreement measures shared bias
rather than correctness. A consensus rule preferentially selects the failure mode
that the largest sub-group of your generators has in common — which is precisely
the error you are least able to detect and most likely to make.

This holds broadly, and it is worth internalising as a general property of
ensembles rather than a quirk of one setting: **an ensemble's members are
correlated by construction**, because they were built by people reading the same
literature and training on the same public data. Averaging correlated estimators
does not cancel their shared error; it concentrates it.

Widen the pool here. Pick from it in `score-normalization`. Voting belongs to
neither.

## Workflow

1. Read `problem.spec` for what an item is, what a candidate is, and what the real
   metric will be. Read `method.budget_plan` for the hard capacity ceiling.
2. Enumerate candidate generators. Include at least one that is architecturally
   unlike the others, even if its solo performance is worse — it is the most
   likely source of unique wins and the most likely rescuer of the failure tail.
3. Run the pilot. Compute `method.correlation_matrix` and unique-win counts.
4. Size the full run and get it approved against the budget before dispatching.
5. Generate, writing **every** candidate to disk with full provenance: item id,
   generator, version, seed, sample index, output location, and the generator's
   **native, unnormalised** confidence output.
6. Emit `method.candidate_pool`.

## What provenance must capture

An under-recorded pool cannot be re-analysed, and re-analysis is most of the value
you will extract from it later.

| Field | Why it is needed later |
|---|---|
| generator name **and version** | A silent upgrade invalidates cross-run comparison |
| seed | Reproducibility, and separating seed variance from generator variance |
| sample index | Distinguishes within-run samples from separate runs |
| native confidence, unnormalised | Downstream normalisation needs the raw scale |
| any auxiliary confidence fields | You will not know which one discriminates until later |
| wall time and cost | The only way to compute value-per-dollar per generator |

## Guard rails

- **Measure decorrelation; never assume it.** Different names, different labs, and
  different architectures are all weak proxies for different errors.
- **Record native confidence unnormalised.** Normalising at generation time
  destroys exactly the information the selection stage needs, and it cannot be
  reconstructed.
- **Never discard a candidate at generation time.** Selection is a separate and
  revisable decision. A pruned pool cannot be re-selected when the selector
  improves, and it silently caps every future experiment.
- **Never prune the low-confidence tail to save storage.** That tail is where the
  rescue step finds its points. Storage is cheaper than regeneration.
- **Cost-gate before dispatch.** This is the expensive stage in most pipelines.
  Estimate against the real item count from the authoritative manifest, not from a
  planning document — those numbers drift and you are billed against the real one.
- **Keep the odd generator.** The one with the worst average is frequently the one
  with unique wins, and unique wins are what a pool is for.

## Anti-patterns

- **Voting, averaging, or taking a consensus candidate.** Refuted above; it
  amplifies shared error.
- **Judging the pool by its best member's average.** The pool's value is its
  ceiling and its decorrelation, neither of which is a property of one member.
- **Buying a second generator that correlates at 0.9 with the first**, because it
  scores well solo. You are paying twice for one distribution.
- **Sizing the run from a plan document** rather than the authoritative item
  count. Compute is billed against reality.
- **Adding generators before seeds have saturated.** Expensive diversity purchased
  before the cheap kind was exhausted.
- **Recording one merged "confidence" column** across generators. Cross-generator
  comparison is a downstream problem and it needs the native scales.

## Handoff

`method.candidate_pool` — every candidate produced, unpruned, with the provenance
table above — and `method.correlation_matrix`, the pairwise error correlation with
per-generator unique-win counts.

The correlation matrix is not a byproduct. It is the input the rescue stage uses to
choose *which* generator to rescue the tail with, and that choice is the difference
between a rescue that works and one that re-applies the same error.
