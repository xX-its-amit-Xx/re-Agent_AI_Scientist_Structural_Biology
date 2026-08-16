# The cost tiers, and when to leave one

Five tiers. The ordering is enforced — `Experiment` rejects an out-of-order ladder — and the
reason is behavioural rather than economic: **the expensive remedies are the interesting ones and
the cheap ones resolve most failures**, so an agent choosing freely reaches for a fine-tune when
the real problem was a tautomer.

---

## `FREE` — costs a re-read

Re-checking inputs, verifying the harness, comparing against the noise floor. No new compute.

**Always exhausted first, on every signal.** `ladder_for()` prepends the three universal checks
for exactly this reason.

**Leave this tier when** all three have run and the failure survived. Not before — and the
temptation to skip is strongest precisely when the failure looks obviously structural, which is
when a lost stereocentre most resembles a model failure.

**What it buys.** Roughly speaking, a large fraction of apparent failures. Every one it catches
would otherwise have consumed a real remedy and produced a confusing partial improvement.

---

## `CHEAP` — minutes to an hour of the same compute

More seeds, deeper MSA, more recycles, a different conformer generator, re-running with a fixed
input.

**Leave this tier when** the change had no effect *and* you have checked that the change actually
happened. An MSA search that silently returned few sequences looks identical to a deep MSA that
did not help — check the returned depth, not the flag you passed.

**The trap here is more seeds.** They help under-convergence and do nothing for systematic bias.
`high_seed_variance` and `consistent_but_wrong` look similar and want opposite remedies: seeds
for the first, a decorrelated generator for the second. More seeds of a biased model reproduce
the bias exactly.

---

## `MODERATE` — a different method on the same budget

Templating from a homologue, pocket restraints, physics rescoring, a learned rescorer,
constrained docking, tail rescue.

**Enter this tier only after `bottleneck-triage`.** It answers whether the problem is generation
or selection, and it changes which half of this tier applies. Spending on generation when the
oracle gap is large is the most expensive common mistake available here — the good answer was
already in the pool.

**Leave this tier when** the remedy beat the baseline on held-out items with non-overlapping
intervals, or clearly did not. Both are results. A moderate remedy that "seems to help" on the
eval set has not been tested; route through `significance-discipline`.

**Two specific cautions:**

- **Restraints must be additive, never required.** A required pocket restraint inverts on
  ligands that do not make that contact — which is the same failure that inverted an
  anchor-based prior on the fragment half of this project's reference test set, arriving through
  a different door.
- **A learned rescorer must be checked for what it reads.** One that reads only the ligand
  identity ranks compounds, not poses, and will look excellent on a benchmark where the two
  correlate.

---

## `EXPENSIVE` — buys a new artifact

Fine-tuning, a scoring function fit to this pocket, MD refinement, free-energy calculation.

**Route through `budget-calibration` first**, with measured per-unit cost from a pilot rather
than an estimate, and with the kill criteria written before the run starts.

**Justified when three things hold at once:**

1. The cheap and moderate rungs have been tried and recorded, including the ones that failed.
2. The failure is **specific to this target or family** rather than general. A general weakness
   is someone else's research problem; a family-specific one is what a curated corpus can fix.
3. The artifact will be **reused**. A fine-tuned checkpoint used for one prediction is a very
   expensive prediction; used for a hundred it is cheap.

**And two things that must be true of the data:**

- Enough held-out complexes exist to gate the checkpoint. A fine-tune with no held-out gate will
  improve its training metric and you will not know whether anything else moved.
- The corpus is not contaminated with the evaluation items. Route through `leak-containment` —
  a fine-tune is the easiest place in the whole pipeline to leak the answers, and the result
  looks like success.

**Leave this tier when** the gated checkpoint failed to beat the baseline on held-out complexes.
That is a real finding and belongs in `what_did_not()`; the next run should not spend the same
money.

**A custom scoring function specifically.** Worth it when the pocket is unusual — the general
scorer was trained on the average pocket — *and* enough family complexes exist to fit against.
The failure mode is fitting to a handful of structures and getting a scorer that ranks those
beautifully and nothing else, which is why it needs held-out items like any other model.

---

## `NOVEL` — no known remedy applies

Escalate to research: adjacent fields, the neglected literature, a cross-domain analogy.

**Every ladder ends here**, and `ladder_problems()` fails a ladder that does not. A registry
without an escalation rung would present itself as complete, which is the same failure as a
search presented as exhaustive.

**Entered legitimately when** the ladder is exhausted *and recorded* — `what_did_not()` shows
what was tried. Entered illegitimately when it is reached first because it is the most
interesting rung.

**Where to send it:**

| Situation | Skill | Why that one |
|---|---|---|
| the in-field methods may share the blind spot | `cross-domain-analogy` | systematic bias across methods trained on the same structures is exactly where a foreign mechanism helps |
| the method probably exists and is not well cited | `neglected-literature` | a prematurely abandoned method is the highest-yield category there, and compute cost and data scarcity both expire |
| nobody has done this | record it as an open question | an honest gap beats an invented remedy |

**And the escalation must return something falsifiable.** A cross-domain analogy arrives as a
`Proposal` with a `mutates` field and a human decision gate — it does not get applied because it
sounds promising. Analogy-derived evidence is capped at speculative confidence by contract.

---

## Reading the profile

`ExperimentLedger.escalation_profile()` should be a pyramid:

```
free=11, cheap=6, moderate=3, expensive=1, novel=0
```

That shape means the cheap rungs did their job. Flagged shapes:

```
free=1, cheap=2, moderate=4, expensive=3, novel=2     # top-heavy
```

`problems()` reports this: more expensive-and-novel than free-and-cheap almost always means the
free rung was skipped. The fix is not more discipline in the prompt — it is running
`ladder_for()` with its universal checks rather than picking a remedy by hand.

```
free=14, cheap=0, moderate=0, expensive=0, novel=0    # stalled
```

Not flagged, and worth noticing anyway: fourteen free checks and no remedy means the failure was
never diagnosed, only re-examined. At some point the inputs are fine and the model is wrong.

## The one thing worth more than the ladder

**Record the remedies that did not work.** `what_did_not()` is the more valuable half of the
ledger and the half nobody keeps. A remedy that sounds right and fails is the expensive thing to
rediscover, and agents have no memory across sessions — the ledger *is* the memory.

Include *why* it did not apply, not just that it failed. "Deeper MSA did not help; the returned
depth was already 4,800 sequences and the low confidence is localised to a loop that is
disordered in all five holo structures" saves the next run the whole branch. "Deeper MSA: no
effect" saves it nothing.
