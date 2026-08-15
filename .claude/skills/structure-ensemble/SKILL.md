---
name: structure-ensemble
description: >-
  Stage 3. Generate a diverse pool of candidate structures or poses across
  multiple models, seeds, and templates, and measure the pool's achievable
  ceiling. Widening the pool is one of only two levers that reliably improve a
  prediction pipeline, so this stage is about diversity and oracle gap rather
  than any single model's quality. Use when producing candidates, choosing
  which models to run, or deciding whether the bottleneck is generation or
  selection. Trigger on: "generate poses", "run co-folding", "sampling", "pose
  pool", "which models should we run", "oracle gap", or /structure-ensemble.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, Agent
---

# Structure ensemble

**Owner: Sumer.** Contract-complete stub — replace the body, keep the interface.

## The one number this stage exists to produce

The **oracle gap**: how good the pool's best candidate is, versus what our
selector actually picks. It tells the whole team where to spend next.

- Oracle far above realised → **selection** is the bottleneck. Stop adding models.
- Oracle close to realised → **generation** is the bottleneck. Widen the pool.

In the reference case the pool oracle was ~1.08 Å median while realised
performance was far worse, which correctly redirected all effort to selection.
Compute this before anything else in Stage 3.

## Guard rails

- **Diversity over quality.** Different models fail on *different* items, and that
  is what a pool is for. Six mediocre-but-decorrelated generators beat one good
  one. Measure decorrelation, do not assume it.
- **Use cross-model diversity to WIDEN, never to VOTE.** Consensus across agreeing
  models is a trap: they share correlated errors, so consensus can be *actively
  harmful*. This is established in the literature and was confirmed empirically in
  the reference case.
- **Record each model's native confidence signal.** These are not interchangeable
  and not commensurable across models; `confidence-selection` needs the raw
  per-model signal, not a normalised one.
- **Cost gate before launching.** This is the expensive stage. Estimate per-model
  cost, write it into a proposal, get an accepted decision, and log spend per
  `MethodStep.credits`.
- **Never discard a candidate at generation time.** Selection is a separate,
  revisable decision; a pruned pool cannot be re-selected when the selector
  improves.

## Workflow sketch

1. Read `stage1.priors`, `stage1.template_candidates`, `stage2.conformer_ensemble`.
   Respect each prior's stated domain of validity — applying one outside it is how
   pipelines regress.
2. Choose generators for **decorrelation**, cheapest first, and start with a small
   pilot subset before committing credits.
3. Generate with multiple seeds/samples per item; record every candidate with its
   native confidence.
4. Compute the pool oracle against whatever ground truth exists, plus per-model
   coverage of the failure set.
5. Report the oracle gap prominently. It is the headline metric.

## One published finding worth designing around

In the closest published analogue, cross-model accuracy correlation was **0.72
between the two most similar co-folders and 0.52 between the most dissimilar pair.**
That spread is the decorrelation you are buying, and it is measurable before you
commit a full budget — run a pilot subset and compute it.

More soberingly: in that study the models sampled a receptor's alternative
conformational state **zero times out of twenty**. Co-folding models largely do not
sample receptor plasticity. If Stage 2 reports a flexible pocket, say plainly in
your report that the generation step cannot be expected to explore it, because that
changes what Stage 4 should attempt.

## Required visuals

- **Oracle-vs-realised curve** as a function of pool size (best@1, best@5, best@20)
  — the figure that tells the team which lever to pull.
- **Per-model coverage matrix**: item x model, cell = candidate quality. Shows
  decorrelation directly, and where each model uniquely wins.
- **Parallel-coordinates plot** comparing models across cost, coverage, and
  confidence calibration.

## Handoff

`stage3.pose_pool` (every candidate, with native confidence and provenance) and
`stage3.pool_oracle` (achievable ceiling, overall and per subpopulation).
