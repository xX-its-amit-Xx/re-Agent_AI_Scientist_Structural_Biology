# Calibrating the verifier

A verifier is a measuring instrument. Nobody would report a distance from an uncalibrated ruler,
and the same standard applies here — except that in this field it usually is not applied, which
is why the reference number is so bad: real unit tests as a verifier calibrated at
**completeness 1.0, soundness 0.75.** Perfect at admitting correct solutions, and admitting
**25% of incorrect ones.**

The authors' warning generalises exactly to us:

> *"the gaps we identify would have been **invisible** if we had used HumanEval and MBPP both as
> verifiers and as benchmarks."*

**Never let the same set be both the verifier and the benchmark.** That single mistake makes a
verifier look perfect while it admits a quarter of everything wrong.

## The capability with no human analogue

You cannot repeatedly feed a human reviewer fabricated claims to calibrate them. Not at any
price — they would notice, resent it, and adapt. **An agent verifier can be re-calibrated on
every run for the cost of a few extra calls, and it has no memory of having been tested.**

So calibration here is not an occasional audit. It is **continuous**: inject falsehoods into
every verification batch, and recompute soundness per run. `06`'s revisit condition — "if
false-edge rejection falls below ~0.7" — previously had no mechanism to detect the fall. This
is that mechanism.

## Building the injected set

Two rules before the specifics.

**Inject falsehoods of the kind the pipeline actually produces**, not obvious nonsense. A
verifier that rejects "PXR is a mineral" tells you nothing. The failure modes worth calibrating
against are the plausible ones — because those are the ones that get through.

**Keep the generator separate from the verifier.** If the same worker writes the falsehoods and
checks them, soundness is measuring a self-consistency loop.

### Per claim kind

**Factual claims from a source.** Take a true claim and degrade it in one specific way:
- **Strengthen it.** The span supports "reduced binding"; the claim says "abolished binding."
  This is the single most common real failure and the hardest to catch.
- **Swap the entity.** Right claim, wrong species, isoform, construct, or paralogue.
- **Swap the direction.** "Upstream of" for "downstream of"; "inhibits" for "activates."
- **Attribute a reported finding.** The source is describing someone else's result; the claim
  presents it as the source's own.
- **Move the number.** Change one digit, or change the unit.
- **Cite the limitations section.** Take a span from "future work" and present it as a finding.

**Numeric and structural claims.** Perturb the value past tolerance but within plausibility — a
pocket volume 30% off, a residue number shifted by one, a chain identifier changed. These
should be caught at ~100% by a computation-grounded verifier, so any miss here is diagnostic of
the verifier not actually running the tool.

**Graph edges.** Attach a true relationship to the wrong node pair; keep the predicate and
score plausible. This is the `false-edge rejection` metric `06` already names.

**Method claims.** Take a real design choice and invert its stated condition — "use an ensemble
when the pocket is rigid."

**Neglect claims.** The important one for `neglected-literature`. Fabricate a plausible neglect
justification for a paper that is genuinely irrelevant: *"few citations, but from a small field
and cited by a seminal review."* If the verifier admits these, the whole neglected-literature
channel becomes a laundering machine, which is the failure mode that skill's own validators
exist to prevent — and this is how you check they work.

## Sizing

Enough falsehoods that soundness has usable resolution. With 10 injected, soundness moves in
10% steps and cannot distinguish 0.75 from 0.80. **20–40 per claim kind** is a reasonable floor;
below 20 the estimate is noise.

Balance matters less than you would think, because completeness and soundness are computed
separately. But do not inject so many that the batch's overall base rate is unrealistic — a
verifier can pick up on a high falsehood rate and become trigger-happy, which inflates soundness
and destroys completeness.

## Reading the result

```python
cal = VerifierCalibration(
    verifier="claim-verifier-v3", as_of="run-2026-08-16a",
    n_true_claims=120, n_true_admitted=111,   # completeness 0.925
    n_false_claims=40,  n_false_admitted=6,   # soundness 0.85
)
cal.summary()
# verifier claim-verifier-v3 · completeness 93% · soundness 85% · pool guide ~1
```

**Soundness below 0.7** → `problems()` flags it. At that level, scaling any candidate pool adds
more accepted errors than accepted truths.

**Completeness below 0.8** → also flagged, and this is the failure people forget. Over-rejection
is the *documented* weakness of LLM verifiers — false-negative rates above **95%** on some
planning domains, which is why a self-critic scored *below no critic at all* (5%→3%, 16%→2%). A
verifier that rejects everything is not conservative, it is broken, and it will silently discard
the neglected literature you paid to find.

**Soundness of exactly 1.0** → suspicious. `optimal_pool_size()` returns `None`, meaning "no
ceiling imposed." Usually it means too few falsehoods were injected, or they were too easy.
Make them harder before believing it.

## Keeping it from being gamed

Three failure modes, all real:

**The verifier memorises the injected set.** Fresh falsehoods per run, generated from the run's
own true claims rather than from a fixed list. This is cheap because the true claims are already
there.

**The injected falsehoods drift easier than the real errors.** Track soundness and the *real*
false-edge rate together. If soundness rises while downstream corrections stay flat, the
injections got easier rather than the verifier getting better.

**Somebody optimises the verifier prompt against soundness.** This is training against a
monitor, and the measured outcome is unambiguous: visible failures fall, actual failures persist,
and monitor recall *"falls to near zero"* as the system learns to satisfy the monitor rather than
the objective. The authors' conclusion is the rule — *"it may be necessary to pay a monitorability
tax by not applying strong optimization pressures directly to the chain-of-thought."*

**Improve the verifier by changing its stance, its grounding, and what it is shown — never by
tuning it against its own score.**

## Where to record it

`VerifierCalibration` per verifier per run, alongside the `SearchLedger`. Both answer questions
about what is *absent* rather than present, which is why neither can be reconstructed afterwards
and both have to be written at the time.
