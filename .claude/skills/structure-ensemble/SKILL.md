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

**Owner: Sumer.** The claim here — *diversity across generators beats quality of
any one generator, and the oracle gap tells you which lever to pull* — is not a
fact about proteins. It holds for anything that produces a pool and then picks
from it. The worked example throughout is co-folding for the OpenADMET PXR
challenge, because that is where these numbers were measured; read the structure
of the argument, not the domain it is stated in.

The compute backend is provisioned and verified — see
[`reference/backends.md`](reference/backends.md) for what is deployed, what it
costs, and the capacity ceiling you are working under. Everything below is
judgement; the backend doc is the part you must not improvise.

## The one number this stage exists to produce

The **oracle gap**: how good the pool's best candidate is, versus what the
selector actually picks. It decides where the whole team spends next.

- Oracle far above realised → **selection** is the bottleneck. Stop adding models.
- Oracle close to realised → **generation** is the bottleneck. Widen the pool.

In the reference case the pool oracle was ~1.08 Å median RMSD while realised
performance was far worse, which correctly redirected all effort to selection.
**Compute this before anything else in Stage 3.** A pool you have not measured
the ceiling of is a pool you cannot reason about.

## Guard rails

- **Diversity over quality.** Different models fail on *different* items, and that
  is what a pool is for. Six mediocre-but-decorrelated generators beat one good
  one. Measure decorrelation on a pilot subset; do not assume it.
- **Use cross-model diversity to WIDEN, never to VOTE.** Consensus across agreeing
  models is a trap — they share correlated errors, so consensus can be *actively
  harmful*. This is established in the literature and was confirmed empirically in
  the reference case. Voting belongs to no stage; see `confidence-selection`.
- **Record each model's native confidence signal, unnormalised.** These are not
  commensurable across models and `confidence-selection` needs the raw per-model
  value. Normalising here destroys the information that stage depends on.
- **Restrict any confidence you record to the ligand and interface.** Global
  protein pLDDT correlates with pose accuracy at r ≈ +0.04 — nothing. Store the
  global score too, but only as a labelled negative control.
- **Cost gate before launching.** This is the expensive stage. Estimate per-model
  cost against the real capacity ceiling, write it into a `Proposal`, get an
  accepted decision, and log spend per `MethodStep.credits`.
- **Never discard a candidate at generation time.** Selection is a separate,
  revisable decision; a pruned pool cannot be re-selected when the selector
  improves. Write every sample to disk with its provenance.

## Workflow

### Step 1 — Read the priors, and respect their domain of validity

Read `stage1.priors`, `stage1.template_candidates`, `stage2.conformer_ensemble`.
Applying a prior outside its stated domain is how pipelines regress. If Stage 2
reports a flexible pocket, note it now — see the sampling caveat below.

### Step 2 — Cost the pool before committing

The arithmetic that matters is `items x models x seeds`, against a hard capacity
ceiling. Get the item count from the manifest rather than from a plan document —
in the reference challenge the announced count (110) and the real count (184)
differed by 67%, and the manifest is authoritative:

```python
import pandas as pd
n_items = len(pd.read_csv("manifest/ligands.csv"))     # 184, not the announced 110
jobs = n_items * len(models) * len(seeds)
```

Pilot before committing the full budget. Run one small decorrelated subset,
measure cross-model correlation, and only then size the real run.

### Step 3 — Generate, recording everything

Dispatch through `modal/client.py:cofold()`, which routes each model to whichever
backend owns it. Do not call a backend directly — the routing is not uniform and
[`reference/backends.md`](reference/backends.md) explains why.

Every candidate gets a row: item id, model, seed, sample index, output path, and
the model's **native** confidence fields, unaltered.

### Step 4 — Compute the oracle gap

Score every candidate against whatever ground truth exists, take the best per
item, and compare with what a baseline selector would have picked. Use the
**real metric**, not a proxy — for a pose-prediction task that means an in-place,
symmetry-corrected metric, never a protein-fold score like TM-score. A pose with
the ligand in the wrong subpocket scores well on TM-score and badly on the metric
that counts.

Report `best@1`, `best@5`, `best@20` so the curve shows whether more sampling
still buys anything.

### Step 5 — Report the gap prominently

It is the headline metric, and it is a directive to the rest of the team, not a
statistic.

## Two published findings worth designing around

**Decorrelation is measurable before you spend.** In the closest published
analogue, cross-model accuracy correlation was **0.72 between the two most
similar co-folders and 0.52 between the most dissimilar pair.** That spread is
exactly what you are buying — run a pilot subset and compute it rather than
assuming your models are diverse because they have different names.

**Co-folding models largely do not sample receptor plasticity.** In that same
study the models sampled a receptor's alternative conformational state **zero
times out of twenty.** If Stage 2 reports a flexible pocket, say plainly in your
report that generation cannot be expected to explore it — that changes what
Stage 4 should attempt, and hiding it wastes their time.

## Required visuals

- **Oracle-vs-realised curve** against pool size (best@1, best@5, best@20) — the
  figure that tells the team which lever to pull.
- **Per-model coverage matrix**: item x model, cell = candidate quality. Shows
  decorrelation directly, and where each model uniquely wins.
- **Parallel-coordinates plot** comparing models across cost, coverage, and
  confidence calibration.

## Anti-patterns

- **Sizing the run from a plan document instead of the manifest.** The counts
  drift, and compute is billed against the real one.
- **Averaging or voting candidates together.** That is consensus wearing a
  different hat, and it is refuted. Widen; never vote.
- **Recording one normalised "confidence" column.** Cross-model comparison is
  `confidence-selection`'s job and it needs native units to do it.
- **Dropping low-confidence samples to save disk.** They are the failure tail,
  which is the one place a rescue step can still buy points.
- **Declaring the pool good because the best model is good.** The pool's value is
  its ceiling and its decorrelation, not its best member's average.

## Handoff

`stage3.pose_pool` (every candidate, with native confidence and provenance) and
`stage3.pool_oracle` (achievable ceiling, overall and per subpopulation).
