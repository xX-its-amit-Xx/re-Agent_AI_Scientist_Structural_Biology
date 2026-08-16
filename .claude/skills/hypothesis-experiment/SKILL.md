---
name: hypothesis-experiment
description: >-
  Run small cheap experiments instead of one expensive guess. Enumerate rival hypotheses,
  predict the outcome BEFORE running, name the ways it could fail and what to do about each,
  then run it and follow the branch you already chose. When a co-fold comes back with bad
  pLDDT or LDDT-PLI this is what lets the agent pivot rather than shrug: a registry of 17
  known failure signals, each with a cost-ordered remedy ladder that routes to existing
  skills, ending in escalation to research when the known remedies are exhausted. Records what
  worked and what did not, because that is the only memory the system has. Trigger on: "the
  pLDDT is terrible", "this failed", "what should we try next", "run an experiment", "test a
  hypothesis", "why did this fail", "pivot", "it's not working", or /hypothesis-experiment.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, WebSearch, WebFetch, Agent
---

# Hypothesis experiment

A co-fold comes back with pLDDT in the fifties, or LDDT-PLI near zero. What happens next
decides whether the pipeline improves or thrashes.

**The thing that makes pivoting possible is not a bigger model. It is having decided, before
the run, what each way it could fail would mean and what to do about each one.**

## Why the prediction must come first

An outcome explained afterwards teaches nothing. Any result can be rationalised, and a model
asked *"why did this happen?"* produces a fluent answer whether or not it knows — which is the
same knowledge-telling failure the interpretive layer guards against, arriving in a new place.

An outcome compared against a prediction written down beforehand is **informative in exact
proportion to how surprising it is.** So the contract enforces the ordering:

- `Prediction` must exist before `Observation` may be attached.
- `if_then` branches must be populated before the run. An experiment that recorded a result
  with no branches is rejected, because choosing the remedy after seeing the outcome is how a
  pipeline drifts toward whatever it happened to try.
- `predicted.metric` must equal `observed.metric`. Comparing a prediction to a different
  measurement is not a test of it.

Two consequences that are easy to get backwards:

**A failed prediction is a success of the method.** The experiment moved a belief. What is
wasted is a run whose outcome was compatible with every hypothesis on the table —
`Prediction.discriminates` catches that *before* the compute is spent, which is the only time
it is worth catching.

**A ledger with no surprises is a warning.** `problems()` flags it: either the predictions were
vague enough to accommodate anything, or they were written afterwards. A run that learns
nothing is indistinguishable from a run that got everything right.

## The first branch is always "is the failure real?"

A bad number can mean a bad model. It can also mean a bad metric, a wrong reference, a
symmetric-ligand RMSD artefact, a lost stereocentre, or a chain-selection error. Three free
checks come before any diagnosis, and `ladder_for()` prepends them to every signal:

1. **Re-read the inputs as the pipeline received them** — protonation, tautomer, stereocentres,
   SMILES round-trip, chain selection, and whether a crystallisation artefact was passed in as
   the ligand.
2. **Verify the harness** — identity test, the metric actually being graded, units, reference.
3. **Check against the noise floor** — a difference smaller than the bootstrap interval is not
   a failure, and chasing it tunes the pipeline to noise.

These resolve a large fraction of apparent failures and cost nothing. **Skipping them is how an
afternoon gets spent deepening an MSA for a complex whose ligand SMILES had the wrong
stereocentre.**

## The ladder is ordered by cost, and that is the point

`RemedyTier` — free, cheap, moderate, expensive, novel — and `Experiment` **rejects an
out-of-order ladder**. The reason is behavioural rather than economic: the expensive remedies
are the interesting ones and the cheap ones resolve most failures, so an agent left to choose
freely reaches for a fine-tuned model when the real problem was a tautomer.

`ExperimentLedger.escalation_profile()` should look like a pyramid — many free, fewer cheap,
rare expensive. An expensive-heavy profile is flagged, because it almost always means the free
rung was skipped.

## The registry routes; it does not reimplement

17 failure signals in `contracts/remedies.py`, each with a ladder. Almost every rung hands off
to a skill that already exists:

| Signal | Where it goes |
|---|---|
| low global confidence | deepen MSA → seeds (`structure-ensemble`) → templates (`template-and-finetune`) → fine-tune |
| low pocket confidence | is the loop just flexible? → pocket-matched templates → additive restraints (`pocket-anatomy`) |
| low ligand accuracy | symmetry check (`harness-verification`) → oracle gap (`bottleneck-triage`) → `physics-rescoring` → `learned-rescoring` → pocket-specific scorer |
| ligand outside pocket | apo-like prediction? → holo seeding → `dock-and-minimize` |
| pocket collapsed | is it induced-fit? (`binder-census`) → holo ensemble → fine-tune on holo |
| consistent but wrong | check the reference → **decorrelated** generator (`generator-diversity`) → `tail-rescue` → cross-domain |
| good pool, bad pick | `score-normalization` → `signal-scoping` → challenger signal |
| confidence uncorrelated | is the signal scoped to what varies? → measure AUC against a negative control |
| metric artefact | `harness-verification` — and stop there if it fails |

A remedy that duplicates one of those skills is worse than a pointer to it, because it drifts.

**And the registry is a floor, not a ceiling.** Every ladder ends at `RemedyTier.NOVEL` —
escalate to `neglected-literature` or `cross-domain-analogy` — and
`unanticipated_signals()` reports what the table missed so the next run's table is better. A
registry presented as complete would be the same failure as a search presented as exhaustive.

## Guard rails

- **Two hypotheses minimum.** With one explanation on the table the experiment can only confirm
  it. Flagged.
- **Every hypothesis needs `would_refute`.** One with nothing that would rule it out is a
  preference, and an experiment against it cannot come out either way.
- **`discriminates` must name real hypothesis ids.** A typo'd id means the experiment
  discriminates nothing while appearing to.
- **A remedy recorded as helping needs a `delta`.** Validation error. An improvement with no
  magnitude cannot be compared against the noise floor, and the next run will believe it.
- **And a `significance_checked` flag.** An unchecked "helped" on a small eval set is how a
  pipeline tunes itself to noise; route through `significance-discipline`.
- **Record the remedies that did *not* work.** `what_did_not()` is the more valuable half and
  the half nobody keeps. A remedy that sounds right and fails is the expensive thing to
  rediscover.
- **Never escalate before the free rung.** `ladder_for()` prepends the universal checks for
  exactly this reason; pass `include_universal=False` only when they have already run.

## Writing one

```python
Experiment(
    id="X-01",
    question="Why is LDDT-PLI near zero for the fragment subset while the drug-like subset is fine?",
    hypotheses=[
        Hypothesis(id="H1", claim="The fragments are being placed in a collapsed apo pocket.",
                   because="Pocket volume in the predictions is at the low end of the observed "
                           "holo range, and the failures are size-correlated.",
                   would_refute="Predicted pocket volume matches the holo range for the "
                                "failing items."),
        Hypothesis(id="H2", claim="The metric is penalising correct poses of symmetric fragments.",
                   because="Several fragments have two-fold symmetry and the harness's symmetry "
                           "handling was never verified.",
                   would_refute="The identity test passes and symmetry-corrected scores are "
                                "unchanged."),
    ],
    predicted=Prediction(
        metric="mean LDDT-PLI, fragment subset",
        expected="0.55-0.70 after symmetry correction if H2 holds; unchanged near 0.05 if H1 holds",
        discriminates=["H1", "H2"],
    ),
    if_then={
        FailureSignal.METRIC_ARTEFACT.value: ladder_for(FailureSignal.METRIC_ARTEFACT),
        FailureSignal.POCKET_COLLAPSED.value: ladder_for(FailureSignal.POCKET_COLLAPSED),
    },
    cost_estimate="one rescoring pass, no new prediction — about 4 GPU-minutes",
)
```

Note the prediction is *conditional on which hypothesis holds*, which is what makes it
discriminating. A prediction of "it should improve" discriminates nothing and would be flagged.

Then run it, attach the `Observation`, take `next_move()` — the cheapest untried remedy for a
signal the run actually raised — and record a `RemedyOutcome` either way.

## Anti-patterns

- **One big experiment.** The point of small ones is that a surprise is cheap and localisable.
- **A prediction that is a direction.** "Should get better" is compatible with everything.
- **Adding a failure branch after seeing the failure.** Rejected by the contract, and it is the
  behaviour the contract exists to prevent.
- **Escalating to a fine-tune or a custom scoring function first.** They are the interesting
  remedies, which is exactly why the ladder is cost-ordered.
- **Recording only the successes.** Then the next run retries every failed remedy at full cost.
- **A verdict that restates the observation.** The verdict says what is now *believed* and which
  hypothesis survived, not what the number was.
- **Treating a flagged uncertainty as a failure.** Low pLDDT on a genuinely flexible loop, or an
  unmodelled disordered tail, is the model being correct about uncertainty. Several free rungs
  exist purely to check this before anything is "fixed".

## References

- [failure-atlas.md](reference/failure-atlas.md) — all 17 signals: how each is diagnosed, what it usually means, and which are commonly mistaken for each other
- [escalation.md](reference/escalation.md) — the cost tiers with real numbers, when an expensive remedy is justified, and how to escalate to research without abandoning the ladder
