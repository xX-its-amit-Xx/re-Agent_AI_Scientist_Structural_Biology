---
name: adversarial-verify
description: >-
  Check a claim by trying to break it, in a worker that is not its author, without seeing the
  author's confidence. Records where exactly it fails, not just that it does. Calibrates the
  verifier itself against deliberately injected falsehoods, so its soundness is measured
  rather than assumed — and caps how far a candidate pool can be scaled based on that
  number. Reports the all-wrong rate and the oracle gap, which bound the pipeline in ways
  pairwise error correlation cannot. Use before any claim enters the certified graph, before
  trusting a candidate pool, and whenever a stage is about to hand off. Trigger on: "verify",
  "check this claim", "is this real", "refute", "falsify", "red team", "how good is our
  verifier", "did we get this right", or /adversarial-verify.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, WebSearch, WebFetch
---

# Adversarial verify

**This is the highest-return component in the pipeline, and the margin is not close.** A
dedicated inspector agent recovered up to **96.4%** of errors introduced by a faulty agent,
out-performing every topology change the same authors measured. MAST's single largest
intervention gain was **+15.6% from adding an objective-verification step**, and its whole
verification category — incorrect verification 9.10%, no or incomplete verification 8.20%,
premature termination 6.20% — is verification failure.

Nothing in topology buys returns of that size. This is where the budget goes.

## The finding that reversed our priority

We assumed a **fresh-context** critic was the main lever. It is not.

On staged adversarial code review, a *full-context* protocol closed only **50%** of the
attack gap — the authors' words: *"ruling out context fragmentation as the sole
explanation."* Meanwhile **reframing the reviewer as an adversarial pentester cut evasion to
3.0–17.6%**, and an open-weight model under that framing detected **88.4% of attacks at a
4.6% false-positive rate**.

**Framing beats freshness.** Both are worth having. Only one is the big lever.

So the instruction is never *"check whether this claim holds."* It is **"find the reason this
claim fails."** `VerifierStance.ADVERSARIAL` is the default, a neutral stance requires a
written reason, and a confirmatory stance is a validation error — asking a verifier to find
support measures its agreeableness, not the claim.

## Guard rails

- **A worker may not verify its own claim.** Enforced. Intrinsic self-critique is
  net-harmful: GPT-4 on GSM8K fell 95.5% → 89.0% across two self-correction rounds, with
  correct→incorrect changes outnumbering the reverse. On two of three planning domains a
  self-critic scored *below no critic at all* — 5%→3% and 16%→2% — because it rejects correct
  answers at a 95.8% false-negative rate.
- **Strip the author's confidence.** The claim arrives as a bare proposition: no hedges, no
  confidence label, no author. Sycophancy appears in **58.19%** of challenge cases, and
  **preemptive** exposure to the author's position produces *more* of it (61.75%) than
  in-context exposure (56.52%) — so putting confidence in the prompt is the worst version.
- **Localise every refutation.** `localised_to` is required when `refuted` is true, and it is
  the field worth paying for. Models locate a mistake in only **39.47%** of faulty traces,
  but correct it reliably once told where — **+23.5 to +43.9 points**. The deficit is in
  *finding* the error, not fixing it, so spend the effort on localisation.
- **Reason before you rule.** `Verdict` puts `because` before `refuted`, pinned by
  `contracts/ordering.py`. A verdict generated first is a coin flip with a justification
  attached, and a verifier that has already written "refuted" will find a reason.
- **Never optimise anything against a judge score.** Not a prompt, not a selector, not an
  agent. A frontier lab rejected neural reward models outright *"because we find that the
  neural reward model may suffer from reward hacking"*, and trained on rule-based rewards
  instead — AIME pass@1 15.6% → 71.0%. And when a team trained against a reasoning monitor,
  visible hacking fell while actual hacking persisted and monitor recall *"falls to near
  zero"*: the model learned to hide its intent. Their conclusion is the rule here — *"it may
  be necessary to pay a monitorability tax."*
- **Agreement is not correctness.** `GroundingKind.CONSENSUS` is the weakest kind and
  `verification_problems()` flags a batch that leans on it above 10%. Debate degraded
  majority-vote accuracy in **10 of 10** configurations tested, and confidence *rises* as
  deliberation proceeds whether or not accuracy does — two debating models both claimed ≥75%
  win probability in **61.7%** of debates.

## Calibrate the verifier, do not assume it

A verifier is a measuring instrument and it needs calibrating. Feed it claims of known
status — **including deliberately falsified ones** — and compute:

- **completeness** — fraction of true claims admitted. Easy to get high. Not the interesting one.
- **soundness** — fraction of falsehoods correctly rejected. **The number that decides how far
  the candidate pool can be scaled, and the one nobody measures.**

A verifier built from real unit tests calibrated at **completeness 1.0 but soundness 0.75** —
it admitted **25% of incorrect solutions**. The authors' warning transfers exactly: *"the gaps
we identify would have been invisible if we had used HumanEval and MBPP both as verifiers and
as benchmarks."* Do not let the same set be both.

**This is a mechanism with no human analogue.** You cannot repeatedly feed a human reviewer
fabricated claims to calibrate them, at any price. An agent verifier can be re-calibrated on
every run for the cost of a few extra calls, so do it continuously rather than once.

## Soundness caps the pool, and the cap is small

`data-materialize`, `structure-ensemble` and `confidence-selection` all generate candidates
and filter. The instinct is "generate many, the filter will sort it out." **The measured
answer is that the filter will not.**

Coverage climbs a long way with N — 15.9% to 56% over 250 samples in one study — but
**selection saturates before 100 samples while coverage keeps rising past 95%.** Coverage
growth beyond that point is definitionally unrecoverable by any selector. Worse, the
false-positive rate *rises* with N even though sampling is memoryless, because task difficulty
is bimodal: easy items resolve early, so the surviving population at high N is dominated by
hard items where false positives are likelier.

At a false-positive cost ratio of 4, **optimal K ≤ 5 for every model tested**. At a ratio of
10, **K = 0** — *"effectively making them useless."* `VerifierCalibration.optimal_pool_size()`
gives an order-of-magnitude guide from measured soundness. **If it says 3, do not generate 100
and trust the filter.**

Two related cautions in [pool-sizing.md](reference/pool-sizing.md): majority-vote accuracy
*provably converges to a fixed limit* rather than improving indefinitely, and vote-based
selection is **non-monotonic in N** on mixed-difficulty sets — more calls first help, then hurt.

## Prefer verification tools over evidence tools

Not conceptual — measured. *"Evidence tools (e.g., web search) systematically induce severe
overconfidence due to inherent noise in retrieved information, while verification tools (e.g.,
code interpreters) can ground reasoning through deterministic feedback and mitigate
miscalibration."* Expected calibration error rose with evidence-tool use (0.879 → 0.901 →
0.948) and *fell* with verification-tool use (0.971 → 0.913 → 0.890).

**This pipeline is retrieval-heavy and verification-light, which is the unfavourable half of
that asymmetry.** So: where a claim admits a deterministic check — a residue count, an
identifier resolution, a geometry, a file hash, a sequence length — **route it to a tool rather
than to a source**, and tag every admitted claim with `GroundingKind`. `grounding_mix()` makes
the imbalance visible; a batch above 85% retrieval gets flagged.

## The two statistics that bound the design

**β, the all-wrong rate** — items where *every* worker was wrong. Accuracy is bounded above
by 1 − β for any policy that returns one worker's answer, and no amount of better aggregation
moves it.

**And β is not recoverable from pairwise correlation.** This is proven, not conjectured: error
laws with identical marginals *and* identical pairwise correlations can have different
all-wrong rates. Measured β ran about **2.5× above** what marginals plus pairwise correlations
predicted (0.052 observed against 0.023 predicted). So a design that reports ρ alone is
reporting the number that is easy to compute rather than the number that limits it.

**The oracle gap (DCR)** — items where some worker had the right answer and the system did not
output it. It reached **86.36%** for decentralised debate in the study that introduced it.
More actionable than any correlation because it names a *specific recoverable loss* rather
than a property of a distribution — and it is the same quantity `neglected-literature`
measures one level up: the difference between what was findable and what was reported.

Report all three. `WorkerAgreement` computes them.

## Two-stage: reason unconstrained, then serialise

Constrained decoding is roughly free. Making a model *reason inside a schema* is not — GSM8K
fell from 86.51% to 23.44% for one model under JSON-with-schema, and *"stricter format
constraints generally lead to greater performance degradation in reasoning tasks."*

So for verification, where the judgement is the hard part:

1. **Reason unconstrained** — free-form, no schema, no field names.
2. **Serialise separately** — a second call whose only job is to fill `Verdict` from the
   reasoning it was handed.

Field ordering helps only when the reasoning happens to fit the schema's shape. Splitting the
calls always helps. Where formatting *is* the whole task — extracting an accession, normalising
a score — single-pass schema forcing is correct and cheaper.

## On a stall, restart — never reflect

If a verification loop is not converging, do **not** run another critique round. Re-instantiate
from the artifact with a clean context. Iterating on self-critique is measurably harmful, and
an agent can forget instantly and for free where a human cannot choose to forget at all.

Also: **never stop on critic score.** No production framework ships "stop when the critic's
score stops improving," and that revealed preference is correct — self-assessed scores are not
a reliable signal. Stop on an external verifier, a coverage measure, or a hard cap.

## Checking

```bash
reagent verify status --report reports/<run>/<stage>/report.json --strict
```

Reports the grounding mix, verdicts produced under invalid conditions, verifier calibration
with its pool-size guide, and β / oracle gap / ρ.

## Anti-patterns

- **A neutral "please check this" prompt.** Leaves the largest measured gain unclaimed.
- **Passing the author's trace and confidence "for context".** The confidence is the part that
  contaminates, and preemptive exposure is the worst case.
- **Measuring the verifier on the same set it verifies.** Hides exactly the gap that matters.
- **Generating a large pool because a filter follows.** The filter saturates long before
  coverage does, and its false-positive rate rises with N.
- **Reporting ρ as the correlated-error diagnostic.** Provably insufficient. Report β.
- **Refuting without localising.** Unactionable, and localisation is the part verifiers are
  measurably worst at — which is why it is the part to require.
- **Treating unanimous agreement as strong evidence.** It is evidence that the workers are
  correlated.

## References

- [pool-sizing.md](reference/pool-sizing.md) — how soundness caps N, with the saturation and non-monotonicity results and worked numbers
- [stance-and-prompts.md](reference/stance-and-prompts.md) — adversarial verifier prompts per claim type, what to strip before sending, and the two-stage split
- [calibration.md](reference/calibration.md) — building the injected-falsehood set, what to inject per claim kind, and how to keep it from being gamed
- [instrumentation.md](reference/instrumentation.md) — β, oracle gap and ρ: what each bounds, how to compute them from a run, and what to do when each moves
