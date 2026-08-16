# β, the oracle gap, and ρ

Three numbers. One bounds the design, one names a recoverable loss, and one is the number
everybody reports because it is easy to compute.

---

## β — the all-wrong rate

**Definition.** The fraction of items on which *every* worker was wrong.

**What it bounds.** Accuracy is bounded above by **1 − β** for any policy that returns one
worker's answer. No aggregation, selector, judge, or debate protocol moves it. If β is 0.10,
the pipeline cannot exceed 90% however good everything downstream becomes.

**Why it is not derivable from ρ.** This is proven, not conjectured: **error laws with identical
marginals *and* identical pairwise correlations can have different all-wrong rates.** Average
pairwise correlation simply does not identify the joint tail.

**And the tail is underpriced in practice.** Across 67 models from 21 providers, the observed
all-wrong rate on open-ended maths was **β = 0.052** against **0.023** predicted from
correlation-calibrated marginals — a **~2.5× underestimate** (90% CI 1.7–3.4). On
execution-graded code β = 0.079; on free-response GPQA-Diamond β = 0.127.

**So a design that reports ρ as its correlated-error diagnostic is reporting the number that is
easy rather than the number that limits it.** `06` previously named pairwise worker error
correlation as "the diagnostic that distinguishes this design from a story about this design."
It is necessary and insufficient; β is the one that binds.

**What to do when it moves.** β rising means the workers share a blind spot, and adding workers
of the same kind will not help. Decorrelate the *inputs*: different sources, different query
phrasing, different partitions of the corpus. Different model families roughly halve error
correlation (~0.67 within family, ~0.53 across), but note the ceiling — heterogeneity bought
**+0.07 points** in one compute-matched comparison, and adding a *weaker* model costs accuracy
rather than adding diversity.

---

## Oracle gap (DCR) — the recoverable loss

**Definition.** Of the items where *at least one* worker was right, the fraction the system did
not output.

```
oracle_gap = (n_any_right − n_system_right) / n_any_right
```

**Why it is the most actionable number here.** Unlike a correlation, it names a specific loss
with a specific cause: the information existed inside the system and the aggregation threw it
away. Every point of oracle gap is recoverable without improving any worker.

It reached **86.36%** for decentralised debate in the study that introduced it — in 86% of cases
where a worker started with the correct answer, the group never got there. That is the clearest
available demonstration that deliberation is a lossy aggregator.

**It is also the same quantity `neglected-literature` measures one level up.** There, it is the
difference between what was findable and what was reported. Here, it is the difference between
what a worker found and what the system said. Same shape, same asymmetry: an unrecoverable loss
if unmeasured, a fixable one if named.

**What to do when it moves.** Above ~15%, `problems()` flags it. Look at the aggregation step,
not the workers:
- Is a minority-correct answer being outvoted? Then the selector is the problem, and majority
  vote is the wrong selector for this task.
- Is a correct claim failing verification? Check **completeness** — over-rejection is the
  documented weakness of LLM verifiers, and it is exactly how a correct minority answer
  disappears.
- Is a worker's finding being dropped in a handoff? Check `AxisSweep` — an axis whose candidates
  exceed its admissions and reports no negative result has a silent drop.

---

## ρ — mean pairwise error correlation

**Definition.** Average correlation between workers' error vectors.

**What it is good for.** Continuity with the literature, a quick check that decorrelation
measures are doing anything at all, and diagnosing the specific case of workers being closer to
one worker than to N.

Reference values: **within-family ~0.67** and **cross-family ~0.53**, replicated in two
independent studies across different modalities. Above 0.6, treat the ensemble as roughly one
worker. Effective ensemble dimensionality across 17 models from 8 families measured **2.49–3.59**
— seventeen models, three workers' worth of independence.

**What it is not good for.** Bounding accuracy. See β.

**And note the mechanism finding that changes what to do about it.** Across 350+ models, the
driver of correlated errors is **capability level, not shared lineage** — same-company effects
were weak or null on two of three datasets while the accuracy-interaction term was significant on
all three, and *"larger and more accurate models have highly correlated errors, even with
distinct architectures and providers."* So "use a different provider" is a weaker intervention
than it sounds. Varying the *input* is the better-measured lever.

---

## Computing them from a run

```python
agree = WorkerAgreement(
    n_items=240, n_workers=4,
    n_all_wrong=14,        # nobody got these
    n_any_right=226,
    n_system_right=205,    # what we actually output
    mean_pairwise_rho=0.58,
    worker_family="claude",
)
print(agree.summary())
# 4 workers over 240 items
#   all-wrong rate (beta): 5.8%  -> accuracy ceiling 94.2%
#   oracle gap (DCR):      9.3%
#   mean pairwise rho:     0.58 (insufficient alone)
```

`n_all_wrong + n_any_right == n_items` is enforced, and `n_system_right > n_any_right` is
rejected — a system cannot output what no worker found. That second check is worth having
because a violation means the ground-truth labelling is wrong, not that the system did something
impressive.

## Getting the labels

All three need per-item correctness for each worker, which means a ground truth. Three sources,
in descending order of trustworthiness:

1. **Computation.** Anything checkable deterministically — identifier resolution, counts,
   geometry. Cheapest and soundest.
2. **A held-out set with known answers.** The withheld items in the `ProblemSpec`.
3. **The injected-falsehood set** from [calibration.md](calibration.md), which gives labels for
   free on the negative side.

**Do not use a judge to produce the labels.** That makes β and the oracle gap measurements of the
judge, and it is the specific mistake that produces a confident number bounding nothing. A judge
scored the *worse* chemistry system higher on fluency grounds while four expert chemists scored
the better one higher.

## Reporting

All three, together, per run — with β first, because it is the one that bounds. And report the
oracle gap even when it is small, since a small gap is the evidence that aggregation is not
where the loss is, which is worth knowing before anyone spends effort improving it.
