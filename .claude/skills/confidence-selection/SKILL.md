---
name: confidence-selection
description: >-
  Stage 3. Choose one candidate per item from a generated pool. In a pipeline
  with a fixed pool and no ground truth, this step usually decides the score
  outright, so it is treated as a first-class modelling problem: normalise
  non-commensurable confidence signals, select per item, then rescue the
  failure tail with a decorrelated generator. Use when ranking candidates,
  picking a final answer, or diagnosing why a good pool scores badly. Trigger
  on: "select poses", "rank candidates", "which pose do we submit",
  "confidence score", "z-score selection", "failure tail", or
  /confidence-selection.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
---

# Confidence selection

**Owner: Sumer.** Contract-complete stub — replace the body, keep the interface.

This is the highest-leverage step in the whole pipeline and the one where clever
approaches most reliably lose to simple ones. Read
`ai-scientist/reference/pxr-case-study.md` before designing anything here.

## The selection wall

With a fixed pool and no ground truth to train on, **every** learned, agentic, or
consensus selector in the reference case regressed against a plain z-scored
native-confidence argmax. Ranked by realised score, the losers included a
37-feature XGBoost LambdaMART ranker (worst submission of the project), agentic
pose review, geometric consensus, medoid selection, Borda and reciprocal-rank
fusion, and MMFF strain gating.

The independent literature review agreed *before* the experiments did: on
co-folding pose pools, native-confidence ranking and cross-model consensus
largely do not beat random, and consensus can be actively harmful.

Treat any proposal to build a smarter selector as guilty until proven innocent,
and require it to beat the z-hybrid baseline on held-out data before adoption.

## What did work

1. **Within-model selection by that model's own native signal.** Not a universal
   score — the model knows what it does not know, in its own units.
2. **Cross-model selection by z-score.** Raw confidences are not commensurable, so
   z-score each model's best-sample scores across all items, then take the argmax
   over models per item. This alone took 0.4996 to 0.5472 in the reference case.
3. **Failure-tail rescue with a decorrelated generator.** Overwrite only the N
   lowest-confidence items with a different model's candidates. N=8 was optimal
   (0.5640); N=4 and N=12 were both worse. The tail is real but small, and
   over-swapping destroys good picks.

## Guard rails

- **Z-score within a model before comparing across models.** Skipping this lets one
  model's inflated scale dominate every item.
- **Sweep the rescue count; do not guess it.** The optimum is a narrow peak.
- **Validate against the real metric, not a proxy.** In the reference case a
  secondary metric was statistically decoupled from the primary one (Spearman
  ~+0.01) while a third tracked it closely (~+0.94). Ranking by the decoupled one
  would have been actively misleading. Check the correlation yourself.
- **Beware tiny validation sets.** All methods clustered inside the noise floor on
  a 35-structure set while the leaderboard spanned a 5x wider range. A ±0.05 win
  on 50 items is noise.
- **Use validation-set expansion as an overfit detector.** When the task gets
  easier, every honest method should improve. One that does not is overfit — this
  signature caught a pLDDT-based selector that had ranked first.

## Required visuals

- **Confidence-vs-accuracy scatter** per model, with the correlation stated. The
  figure that shows whether a signal is worth anything at all.
- **Selection-divergence matrix**: which items each candidate selector picks
  differently. Divergence outside a sane band is a strong early warning.
- **Failure-tail sweep curve**: score vs number of rescued items, peak marked.
- **Per-subpopulation score breakdown**, since a selector can win overall while
  losing on the half that carries the points.

## Handoff

`stage3.selection` (the chosen candidate per item, with the signal and reason) and
`stage3.failure_tail` (the low-confidence items, for Stage 4 to work on).
