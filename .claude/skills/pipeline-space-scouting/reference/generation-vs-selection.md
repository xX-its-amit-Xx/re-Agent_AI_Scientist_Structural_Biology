# Generation or selection: the oracle-gap diagnostic

This is the most consequential thing Stage 0 produces, and it takes an afternoon.
You compute three numbers, subtract them in two places, and the answer tells you
which half of the pipeline to build. Getting it right reorganises the architecture.
Skipping it means allocating months of effort by taste.

The question is not "which model is best". It is: **given the candidates our
pipeline can already produce, is our score limited by the candidates or by our
choice among them?** Those two conditions call for opposite work, and no amount of
effort on the wrong one helps.

## The three numbers

**1. The trivial baseline.** What the dumbest legitimate approach scores. Not a
strawman — a real method someone would ship if nobody thought about the problem.
For blind complex prediction, transferring the pose from the nearest homolog with a
known structure, or docking into the apo structure. For pose selection from an
existing pool, picking uniformly at random. For property regression, predicting the
training mean, then a single-descriptor linear model. For hit identification, the
library's base hit rate under random sampling. For binder design, the success rate
of an unmodified natural scaffold.

You must run this yourself. A trivial baseline you read about is on someone else's
eval set and is therefore not your baseline.

**2. The current best.** What the leaderboard or the honest benchmark literature
achieves, **with its eval set attached**. This number comes from the challenge
post-mortem and benchmark-paper modalities rather than from method papers; see
`evidence-modalities.md`. If it was measured on a different eval set than yours, it
is not subtractable from your other two numbers, and the correct action is to
record both with their protocols and refuse the subtraction rather than to do it
anyway.

**3. The ceiling — what an oracle would score given the same candidate pool.** Build
the pool you can actually afford to build, then for each item ask what score you
would get if you always picked the best candidate in that item's pool. This
requires ground truth, so it is measured on the validation subset where you have
it, and extrapolated to the blind set with an explicit caveat.

The ceiling is the number nobody computes, and it is the one that decides the
architecture.

## The two subtractions

**Headroom = current best − trivial baseline.** How much the field has managed to
extract from thinking about this problem. If headroom is small, the interesting
question is whether the project is worth doing at all, and Stage 0 should say so.

**Selection gap = pool oracle − what your selector actually realises.** Points
sitting inside the pool you already have, which your selector is failing to
collect. Zero effort in generation is required to collect them.

**Generation gap = task ceiling − pool oracle.** Points that are not in the pool at
all. Collecting them requires new or better candidates. The task ceiling is either
the metric's maximum or, more honestly, the reproducibility limit of the reference
measurement, which is usually well below the maximum.

## How to compute the ceiling

Two matrices over your validation items.

- `truth[i, j]` is the **realised quality of candidate j for item i, in the metric
  you are graded on.** Not a proxy. Use `np.nan` for candidate slots that do not
  exist, because pools are ragged.
- `score[i, j]` is your selector's preference for that candidate, higher meaning
  more preferred. This is what the selector knows without the answer.

Then the oracle curve is the mean or median, over items, of the best true quality
among the top k candidates by `score`.

```python
import numpy as np


def oracle_curve(truth, score, maximize=True, agg=np.nanmedian):
    """Best-of-top-k curve: curve[k-1] is best@k.

    truth : (n_items, n_candidates) realised quality in the GRADED metric,
            np.nan where a candidate slot is empty.
    score : (n_items, n_candidates) selector preference, higher = preferred,
            np.nan where the slot is empty.
    maximize : True for LDDT-PLI, Spearman, hit rate; False for RMSD, MAE.
    agg   : np.nanmedian to match a median-reported metric, np.nanmean for a mean.

    curve[0]  = best@1, i.e. what the selector actually delivers.
    curve[-1] = best@all, i.e. the pool oracle, the ceiling of this pool.
    """
    truth = np.asarray(truth, dtype=float)
    score = np.asarray(score, dtype=float)

    # Rank candidates by the selector, pushing empty slots to the back.
    ranked_by_selector = np.argsort(
        np.where(np.isnan(score), -np.inf, score), axis=1
    )[:, ::-1]
    ranked_truth = np.take_along_axis(truth, ranked_by_selector, axis=1)

    # Empty slots must never win the running best.
    neutral = -np.inf if maximize else np.inf
    ranked_truth = np.where(np.isnan(ranked_truth), neutral, ranked_truth)

    running_best = (
        np.maximum.accumulate(ranked_truth, axis=1)
        if maximize
        else np.minimum.accumulate(ranked_truth, axis=1)
    )
    running_best = np.where(np.isinf(running_best), np.nan, running_best)
    return agg(running_best, axis=0)
```

The three points on that curve worth reporting are `best@1`, `best@5` and
`best@20`, because together they say something a single number cannot: how much of
the pool's value a human or a downstream filter could reach if allowed a shortlist.

```python
def gap_report(truth, score, trivial_baseline, task_ceiling,
               maximize=True, agg=np.nanmedian):
    curve = oracle_curve(truth, score, maximize=maximize, agg=agg)

    realised    = curve[0]
    pool_oracle = curve[-1]
    sign        = 1.0 if maximize else -1.0

    # What an uninformative selector gets: the expected value of a random pick.
    random_pick = agg(np.nanmean(np.asarray(truth, dtype=float), axis=1), axis=0)

    return {
        "best_at_1":       float(realised),
        "best_at_5":       float(curve[min(4, len(curve) - 1)]),
        "best_at_20":      float(curve[min(19, len(curve) - 1)]),
        "pool_oracle":     float(pool_oracle),
        "random_selector": float(random_pick),
        "trivial_baseline": float(trivial_baseline),
        "selection_gap":   float(sign * (pool_oracle - realised)),
        "generation_gap":  float(sign * (task_ceiling - pool_oracle)),
        # How much of the available selection signal the selector captures.
        # 0.0 means no better than random; 1.0 means oracle. Defined here as a
        # working diagnostic, not a published metric.
        "selection_efficiency": float(
            (realised - random_pick) / (pool_oracle - random_pick)
        ) if pool_oracle != random_pick else float("nan"),
    }
```

Three practical notes on computing it honestly.

**Use the graded metric, in the graded units.** If you compute the ceiling in one
metric and your realised score in another, the difference between them is not a
gap, it is a category error. This is not a hypothetical: the reference case study
reports its pool ceiling as roughly **1.08 Å median RMSD** while being graded on
**LDDT-PLI**, so those two numbers cannot be subtracted, and the qualitative
conclusion survived only because the difference was overwhelming rather than
marginal. Compute the ceiling in the graded metric so that the subtraction is real.

**Bootstrap the whole thing.** Every number here is an aggregate over a
validation set that is usually small, and differences below its noise floor are not
differences. Resample items with replacement, recompute the curve, and report the
spread — the case study's validation set had a noise floor of about 0.05 Å at 35
items, which was wider than the differences between the methods being compared.

```python
def bootstrap_gap(truth, score, n_boot=1000, seed=0, **kw):
    rng = np.random.default_rng(seed)
    n = truth.shape[0]
    draws = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        draws.append(oracle_curve(truth[idx], score[idx], **kw))
    draws = np.asarray(draws)
    return draws[:, 0], draws[:, -1]   # best@1 and pool-oracle distributions
```

**The oracle you measure is optimistic for the blind set.** It is computed where
you have ground truth, and you have ground truth where the field has already
solved things. State that as a limitation rather than quietly inheriting it.

## The worked example, with the case study's real figures

The reference case study is a clean instance because the diagnostic was run, it
returned an unambiguous answer, and the team acted on it.

**The pool.** Six co-folding models, with deliberately uneven seed counts:
AlphaFold3 at 4 to 10 seeds, Boltz-2.1 at 5 to 10, OpenFold3 at 20, Chai-1 at 5,
Protenix-v2 at 25, and ESMFold2 at 25 seeds across each of 4 MSA modes. That is a
wide pool by construction, and building it was the deliberate first move.

**The ceiling.** The pool oracle was roughly **1.08 Å median RMSD**, described as
far better than any single model realised. In this problem class a median around
one ångström is close to the resolution of the reference measurement itself. The
right answer was in the pool for almost every item.

**The realised performance.** The graded score before any cross-model selection
work was **0.4996 LDDT-PLI**, and per-model scores across the submitted co-folders
ran about 0.46 on the drug-like half of the test set and about 0.55 to 0.57 on the
fragment half.

**The diagnosis.** The ceiling was excellent and the realisation was not, with the
pool held fixed. That is a selection-limited regime, and it says that adding a
seventh model or fine-tuning harder would move the ceiling that was not the
constraint, while leaving the constraint alone.

**What was done with the diagnosis, and what it earned.** Effort went to the
selector, and only to the selector.

| Change | Score | Delta |
|---|---|---|
| Pool, selected without cross-model normalisation | 0.4996 | — |
| Select within each model by its own native confidence, then across models by z-score | 0.5472 | +0.0476 |
| Overwrite the 8 lowest-confidence items with a different model's poses | 0.5640 | +0.0168 |

Total: **+0.0644 with no new model, no new training, and no new candidates.** For
scale, the gap between that result at rank 2 and the winner at 0.5725 was 0.0085,
so the selection work was worth roughly seven times the margin that separated
first from second. And the winner's advantage was not a better selector or a
better algorithm; it was a federated fine-tune on four pharma companies'
proprietary crystals, which is a data advantage rather than a method advantage.

The counterfactual matters as much as the result. Had the same effort gone into
generation — a seventh co-folder, more seeds, a better sampler — it would have
pushed a ceiling of 1.08 Å median downwards while the realised score stayed near
0.50, and the project would have finished with a better pool and the same score.
The diagnostic is what prevented that, and it cost an afternoon.

## The selection wall, and why the answer was not "train a better selector"

Having established a selection-limited regime, the obvious move is to build a
better selector. The case study ran that experiment thoroughly and it failed
comprehensively: with a fixed pool and no ground truth to train on, **every**
learned, agentic, and consensus selector regressed against the plain z-scored
native-confidence argmax.

The concrete casualties, all on the same pool and the same 184-item eval set:

| Attempted selector | Outcome |
|---|---|
| XGBoost LambdaMART re-scorer, 37 features, trained on 35 to 53 holo structures | 0.4762, rank 32 of about 50 — the project's worst submission |
| Consensus, medoid, Borda count, reciprocal-rank fusion | All regressed against the plain argmax |
| Agentic ligand re-drawing | One item went from 3.88 Å to 24.63 Å |
| MMFF strain gating (`blend_top3`) | 2.251 Å against the interface-error baseline's 2.230 Å, so 0.020 worse, with large wins on 4 holos and catastrophic losses on 3 |
| Genetic anchor-and-tail crossover | Oracle improved; no selector could find the hybrid |
| Crystal anchor priors | Fine on drug-like items, failed on the fragment items |

An independent literature review conducted in that project reached the same
conclusion *before* the experiments confirmed it: on co-folding pose pools,
native-confidence ranking and cross-model consensus largely do not beat random,
and consensus can be actively harmful. Two modalities, one answer.

The compressed form is the sentence worth carrying: **chemically plausible is not
native.** A selector can only rank by properties it can evaluate without the
answer, and validity, plausibility and internal consistency are all satisfiable by
the wrong candidate. That is a ceiling on selection given your information, not a
tuning problem, which is why more sophisticated selectors did not climb it.

So a selection-limited diagnosis does not license arbitrary selector work. It
licenses exactly three things, in this order.

1. **Normalisation**, which is not learning and needs no labels. Each model's
   confidence is meaningful within that model and meaningless across models, so
   z-score each model's per-item best scores across the test set and take the
   per-item argmax of the z-score. Worth 0.0476 here. Note that constructing the
   within-model signal required per-model sign and field choices: AlphaFold3
   `iptm`, Boltz-2 negated `complex_ipde`, OpenFold3 negated mean predicted
   alignment error over the pocket-and-ligand block, Chai-1 `iptm`. Two of the four
   needed a sign flip, and getting that wrong inverts the selector silently.
2. **Failure-tail rescue**, which sidesteps ranking entirely. Do not try to score
   the tail correctly; identify it by low confidence and replace it wholesale with a
   decorrelated model's output. Worth 0.0168 here, and one rescued item went from
   0.123 to 0.919. Confidence adequate for *detecting* a tail is a much lower bar
   than confidence adequate for *ranking*, and asking only for what you need is
   what makes an unreliable signal usable.
3. **Dose control on the rescue**, because the curve has an interior optimum: 4
   swaps gave 0.5578, 8 gave 0.5640, 12 gave 0.5629, and 20 gave 0.5587. The tail
   is real and small.

Everything else on the list above was refuted.

## Why cross-model consensus can be actively harmful

Consensus is the intuitive way to spend a diverse pool, and on this class of
problem it is the wrong way, for a reason worth understanding rather than
memorising.

Ensemble arguments assume approximately independent member errors. Modern models
in one domain are trained on the same public repositories, with related
architectures, often sharing pretrained components, so their errors are strongly
correlated. If member errors have pairwise correlation rho, the variance of their
average falls only to a fraction `(1 + (m - 1) * rho) / m` of a single member's
variance — at rho near one, it barely falls at all no matter how many members you
add. So the variance-reduction argument for consensus is close to void.

Then consensus does something averaging does not. Selecting the modal candidate
means selecting the candidate that most members agree on, which by construction
**discards the one member that disagreed** — and on the items where models disagree
strongly, the disagreeing member is disproportionately likely to be the one that
got it right, because the other members are wrong together for a shared reason.
Consensus therefore concentrates on the shared error mode precisely on the items
where you most needed the diversity. It is not merely uninformative; it converts
the pool's diversity from an asset into a liability.

The productive inversion is the whole trick: **use cross-model diversity to widen
the pool and to cover the failure tail, never to vote.** The case study spent six
models on exactly that and never on agreement, and both of the levers that worked
— widening and rescuing — consume diversity in ways that benefit from it.

Before ensembling anything, measure the member error correlation on your validation
set. If it is high, voting cannot help and you have saved yourself the experiment.

## What to do in each regime

Read the regime off the two gaps and the selection efficiency together.

| Selection gap | Generation gap | Regime | What to do |
|---|---|---|---|
| Large | Small | **Selection-limited** | Everything on the selector, in the order above: normalise, then rescue the tail, then control the dose. Do not add models. |
| Small | Large | **Generation-limited** | Everything on the pool: more seeds, more models, more input variants, templates, fine-tuning on a curated corpus. Keep the plain selector. |
| Large | Large | **Generation first** | Widening the pool is more reliable than climbing the selection wall. Check selection efficiency: if a plain baseline already captures most of the available signal, further selector work will not pay. |
| Small | Small | **Saturated** | The pipeline is near its ceiling and the remaining points are elsewhere: data advantage, metric mechanics, submission hygiene, subpopulation routing. Say so plainly rather than tuning. |

### Selection-limited

The gap is inside the pool, so the work is free of new compute.

- Normalise before comparing across models, and verify the sign of every signal.
- Sanity-check the per-model selection counts. If one model wins nearly every
  item, normalisation has not worked.
- Detect and rescue the failure tail with a decorrelated generator; sweep the dose.
- Do not train a selector on tens of labels. The crossover label count at which a
  learned selector overtakes a native-confidence baseline is not published for this
  problem class, so treat it as unknown rather than as nearby.
- Do not vote.
- Route this to Stage 3 as `confidence-selection` work.

### Generation-limited

The right answer is not in the pool, so no selector can find it.

- Add seeds before adding models. Cheaper, and it raises the ceiling on the items
  where the model is nearly right.
- Add models for decorrelation rather than for individual quality. A weaker model
  with independent errors raises the ceiling more than a stronger duplicate.
- Vary the inputs, not only the seed. The case study ran one model across 4 MSA
  modes, which is input diversity from a single model.
- Inject the prior into the model where a curated corpus exists. The case study's
  4-stage curriculum fine-tune escalated specificity while decreasing learning
  rate: drug-like compounds for 2000 steps at 3e-4, promiscuous target classes for
  1500 at 1e-4, all 1,264 nuclear-receptor ligand-binding domains with the target
  up-weighted threefold and two relatives twofold for 800 at 5e-5, and finally the
  70 target holo structures for 350 at 2e-5, with interface loss weight rising from
  1.0 to 3.0.
- Beware of widening by recombination. Crossover raised the oracle in the case
  study and no selector could reach the hybrids, so the ceiling moved and the score
  did not.
- Route this to Stage 3 as `structure-ensemble` and `template-and-finetune` work.

### Both large

Prefer generation, because the selection wall is a real ceiling and pool widening
is not. But check the selection efficiency first: if your plain baseline is already
close to the oracle relative to random, the selection gap is mostly unreachable and
generation is the only live lever. If the baseline is barely above random, spend one
afternoon on normalisation before committing, since normalisation is nearly free and
in the case study it was the single largest gain.

### Saturated

Say so, and look at the four places points hide when the model pipeline is done.
A data advantage you cannot match by method, which is what beat the case study's
entry by 0.0085. Metric structure and how it has been gamed. Submission mechanics,
where a connectivity failure scored an item **0** with a 20 Å RMSD penalty and a
leaderboard displaying the most recent rather than the best submission cost
competitor teams up to 16 rank positions. And subpopulation routing, where a prior
fitted to one half of a heterogeneous test set inverts sign on the other.

## Reporting it

The three numbers and the two gaps go into `ModelReport.metrics` under the keys the
skill names, extended with the decomposition:

```json
{
  "trivial_baseline": 0.0,
  "current_sota": 0.0,
  "pool_ceiling": 0.0,
  "headroom": 0.0,
  "selection_gap": 0.0,
  "generation_gap": 0.0,
  "selection_efficiency": 0.0,
  "n_methods": 0
}
```

Alongside them:

- A `FindingKind.BENCHMARK` finding per number, each citing where it came from,
  each naming its eval set. A bare ceiling with no eval set is as unusable as a bare
  benchmark number.
- A `FindingKind.DESIGN_CHOICE` finding stating the regime and the resulting
  allocation, because this is the decision the stage exists to make.
- `handoff.payload.must_beat` populated with the trivial baseline and the current
  best, both with eval sets, so Stage 3 optimises against real targets.
- The oracle curve as a figure. `ModelReport.unvisualized_metrics()` flags headline
  metrics that no figure reads from, and `reagent report validate --strict`
  promotes visual gaps to errors before a stage may hand off, so the curve is not
  optional. The natural figure plots k on the horizontal axis against the aggregate
  best@k on the vertical, with horizontal reference lines for the trivial baseline,
  the random-selector value, and the current best, and the question it answers
  written on it: *"is our score limited by the candidates or by our choice among
  them?"*
- A limitation recording that the oracle was measured where ground truth exists and
  is therefore optimistic for the blind set.

## The one-paragraph version

Build the pool you can afford. For the items where you have ground truth, compute
what you would score if you always picked the best candidate in the pool, in the
metric you are graded on. Compare that to what your selector actually delivers, and
to what a random pick delivers. If the ceiling is far above your realised score,
you have a selection problem: normalise the confidence signals across models,
detect and replace the failure tail with a decorrelated model, sweep the dose, and
do not train a selector on tens of labels and do not vote. If the ceiling is close
to your realised score, you have a generation problem: add seeds, add decorrelated
models, vary the inputs, and inject the prior into the model. In the reference case
study the first diagnosis was correct, and acting on it was worth 0.0644 against a
margin of 0.0085 that separated second place from first.
