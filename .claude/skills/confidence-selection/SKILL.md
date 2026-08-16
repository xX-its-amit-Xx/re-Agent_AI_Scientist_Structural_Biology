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

**Owner: Sumer.** This is the highest-leverage step in the pipeline and the one
where clever approaches most reliably lose to simple ones. Read
`ai-scientist/reference/pxr-case-study.md` before designing anything here, and
[`reference/scoring.md`](reference/scoring.md) before trusting any number you
compute.

## The selection wall

With a fixed pool and no ground truth to train on, **every** learned, agentic, or
consensus selector in the reference case regressed against a plain z-scored
native-confidence argmax. Ranked by realised score, the losers included a
37-feature XGBoost LambdaMART ranker (worst submission of the project), agentic
pose review, geometric consensus, **medoid selection**, Borda and reciprocal-rank
fusion, and MMFF strain gating.

The independent literature review agreed *before* the experiments did: on
co-folding pose pools, native-confidence ranking and cross-model consensus
largely do not beat random, and consensus can be actively harmful, because
agreeing models share correlated errors.

Treat any proposal to build a smarter selector as **guilty until proven
innocent**, and require it to beat the z-hybrid baseline on held-out data before
adoption. "Chemically plausible" is not the same as "what the model actually
predicted", and the difference is where these methods die.

## What did work

Build these three in order. Each is cheap, and the ordering is the finding.

1. **Within-model selection by that model's own native signal.** Not a universal
   score — a model knows what it does not know, in its own units.
2. **Cross-model selection by z-score.** Raw confidences are not commensurable, so
   z-score each model's best-sample scores across *all* items, then take the
   argmax over models per item. This alone took **0.4996 → 0.5472** in the
   reference case.
3. **Failure-tail rescue with a decorrelated generator.** Overwrite only the N
   lowest-confidence items with a different model's candidates. The sweep:

   | N swapped | 4 | **8** | 12 | 20 |
   |---|---|---|---|---|
   | Score | 0.5578 | **0.5640** | 0.5629 | 0.5587 |

   One rescue went 0.123 → 0.919. The tail is real but small, and over-swapping
   destroys good picks. **Sweep N; never guess it.**

## Which confidence signal to use

From the closest published analogue — 557 protein-ligand complexes, three
co-folding models, two-angstrom accuracy threshold:

| Signal | Discrimination (ROC AUC) |
|---|---|
| ligand-atom-mean pLDDT | 0.76 |
| interface pTM (two models) | 0.73 |
| a model's own affinity head | 0.55 |

And the correlation that decides the design: **global protein pLDDT against pose
accuracy is r ≈ +0.04 — nothing. Ligand-restricted pLDDT is r ≈ −0.46.**

So restrict every signal to the ligand and the interface, and never rank on a
global score or a model's default `ranking_score` field. Carry global protein
pLDDT as a deliberate **negative control**: it should land near 0.5 AUC, and if it
does not, your harness is wrong and nothing downstream of it is trustworthy.

**Better than interface pTM: minimum interface PAE** — the minimum predicted
aligned error over protein-ligand token pairs. It beat interface pTM on every
metric in a 2026 study and is cheap to compute from files you already have.

## Guard rails

- **Z-score within a model before comparing across models.** Skipping this lets
  one model's inflated scale dominate every item.
- **Restrict the signal to ligand and interface.** See the table above.
- **Validate with symmetry-corrected, in-place accuracy metrics.** Chemically
  indistinguishable atoms admit multiple valid correspondences, and index-order
  comparison accrues one to two angstroms of pure bookkeeping error *precisely at
  the decision boundary*. Never use an accuracy function that superposes the
  candidate onto the reference as a side effect — that scores a correctly-shaped
  molecule in entirely the wrong site as a success.
- **Validate against the real metric, not a proxy.** In the reference case one
  secondary metric was statistically decoupled from the primary (Spearman ~+0.01)
  while a third tracked it closely (~+0.94). Ranking by the decoupled one would
  have been actively misleading. Check the correlation yourself.
- **Beware tiny validation sets.** All methods clustered inside the noise floor on
  a 35-structure set while the leaderboard spanned a 5x wider range. A ±0.05 win
  on 50 items is noise.
- **Use validation-set expansion as an overfit detector.** When the task gets
  easier, every honest method should improve. One that does not is overfit — that
  signature caught a pLDDT-based selector which had ranked first.
- **Never let the selector see ground truth.** The leak is invisible in the final
  score, because the score is computed from the same files.

## Workflow

1. Load `stage3.pose_pool` and `stage3.pool_oracle`. If the oracle gap is small,
   stop — the bottleneck is generation, and this stage cannot fix it.
   Load `stage2.critical_residues` too: it defines which residues count as the
   interface, and every guard rail above turns on restricting the signal to the
   ligand and interface rather than the whole protein. Without it you are
   guessing at the pocket boundary, which is how a global score sneaks back in.
2. Per model, pick the best sample per item by that model's native signal.
3. Z-score each model's best-sample scores across all items; `argmax` per item.
   This is the baseline every later idea must beat.
4. Rank items by selected confidence, sweep N over the lowest-confidence tail,
   and overwrite with a decorrelated model's candidate. Report the whole sweep,
   not just the peak.
5. Break every score out by subpopulation. A selector can win overall while
   losing on the half that carries the points.

## Required visuals

- **Confidence-vs-accuracy scatter** per model, with the correlation stated — the
  figure that shows whether a signal is worth anything at all.
- **Selection-divergence matrix**: which items each candidate selector picks
  differently. Divergence outside a sane band is an early warning.
- **Failure-tail sweep curve**: score vs number rescued, peak marked.
- **Per-subpopulation score breakdown.**

## Anti-patterns

- **Medoid, consensus, or any agreement-based pick.** Refuted directly, twice —
  in the literature and in the reference case. Agreement measures shared bias.
- **Ranking on global pLDDT or a default `ranking_score`.** r ≈ +0.04.
- **Training a ranker on the pool.** With no ground truth to train against, this
  produced the single worst submission of the reference project.
- **Reporting only the peak of the rescue sweep.** The shape is the evidence that
  the peak is real and not a noise spike.
- **Declaring a win inside the noise floor.** Bootstrap it, and state the interval.

## Handoff

`stage3.selection` (the chosen candidate per item, with the signal and the
reason), `stage3.failure_tail` (the low-confidence items, for Stage 4), and
`stage3.report` — the Model Report section for this stage, carrying the four
required figures, the baseline-vs-candidate comparison with bootstrap intervals,
and the per-subpopulation breakdown.

`stage3.report` is the one a reader will actually judge the stage by, so state
plainly in it which selectors were tried and which lost. A stage that reports
only its winner hides the evidence that the winner is simple for a reason.
