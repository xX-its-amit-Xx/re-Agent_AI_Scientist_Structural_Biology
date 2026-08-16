# Stance, and what to strip before sending

## The one-line rule

Not *"check whether this claim holds."* **"Find the reason this claim fails."**

Measured margin: reframing a reviewer adversarially cut evasion from a 53–86% baseline to
**3.0–17.6%**, and an open-weight model under that framing detected **88.4% of attacks at a
4.6% false-positive rate**. In the same study a *full-context* protocol closed only **50%** of
the gap. **Framing is the larger lever.** Both are worth having; only one is worth arguing about.

## What to strip

The claim arrives as a bare proposition. Remove, in order of how much damage each does:

| Strip | Why |
|---|---|
| **The author's confidence** | Sycophancy in **58.19%** of challenge cases, and *preemptive* exposure produces more of it (61.75%) than in-context exposure (56.52%). Putting confidence in the prompt is the worst version. |
| **Hedges in the claim itself** | "It appears that X may be…" invites agreement with the hedge rather than assessment of X. Rewrite as a flat proposition the verifier can fail. |
| **The author's identity** | Removes any capability-gradient deference. A model capitulates to a peer it reads as stronger on **92.36%** of disagreements. |
| **The author's trace** | Smaller lever than the above, and it has a real cost — the verifier loses the context to notice a subtle inferential leap. Strip it for factual claims, consider keeping it for claims about a *method*. |
| **Other verifiers' verdicts** | A verdict shown alongside peers stops being an independent vote. Unanimity, not dialogue, is what drives conformity — and removing the last dissenting voice is what causes the jump (32.6% → 69.9%). |

What to **keep**: the claim, the cited span verbatim, the locator, and whatever tools are needed
to check it independently.

## Prompt shapes by claim type

Each pairs an adversarial instruction with the specific failure to hunt for. Generic
adversarial framing is better than neutral framing; specific adversarial framing is better
still, because it tells the verifier where this *kind* of claim usually breaks.

### A factual claim from a source

> The following proposition is claimed to be supported by the quoted span. **Find the reason it
> is not.** Consider specifically: the span may support a weaker claim than the one stated; it
> may be about a different entity, species, construct or condition; it may be the source
> *reporting someone else's* finding; the numbers may not match; the span may be from a
> limitations or future-work section. If after genuine effort you cannot find a failure, say so
> and name the strongest objection you considered and rejected.

That last sentence matters. Without it an adversarial prompt produces a refutation rate near
100%, which is the mirror failure — and over-rejection is the documented weakness of LLM
verifiers, with false-negative rates above **95%** on some planning tasks. **A verifier that
never admits anything is as useless as one that never refuses.**

### A numeric or structural claim

Route it to a tool. This is the single most valuable line in this document.

> The proposition asserts a value. **Do not assess it by reading. Compute it.** Resolve the
> identifier, count the residues, measure the distance, check the hash. Report the computed
> value and whether it matches.

Evidence tools *"systematically induce severe overconfidence"* while verification tools *"can
ground reasoning through deterministic feedback and mitigate miscalibration"* — ECE rose with
retrieval use (0.879 → 0.901 → 0.948) and fell with computation (0.971 → 0.913 → 0.890). Tag
the resulting verdict `GroundingKind.COMPUTATION`.

### A method or design claim

> A design choice is claimed to be justified. **Find the condition under which it is wrong.**
> Name a concrete situation where this choice degrades the result, and say whether that
> situation obtains here. If the claim already states its own domain of validity, attack the
> boundary rather than the interior.

### A negative result

> A claim is made that something does not work. **Find the reason it might work after all** —
> most likely that it was run wrong, run at the wrong scale, or run under a condition that has
> since changed. Compute cost and data availability both expire.

This is the mirror-image stance and it needs stating separately, because an adversarial
verifier pointed at a negative result will otherwise happily agree that the thing failed. The
whole value of `NeglectReason.PREMATURELY_ABANDONED` depends on somebody asking this question.

### A neglect claim

> Work is claimed to be under-attended but relevant. **Find the reason it is simply
> irrelevant.** Low citation counts are compatible with every reason in the recovery list *and
> with plain irrelevance.* Assess the relevance argument on its own, as if the paper had a
> thousand citations.

## The two-stage split

Do not make the verifier reason inside `Verdict`'s schema. GSM8K fell from **86.51% to 23.44%**
for one model under JSON-with-schema, and *"stricter format constraints generally lead to
greater performance degradation in reasoning tasks."*

**Call one — reason.** Free-form, no schema, no field names. Just the adversarial prompt, the
claim, the span, and the tools.

**Call two — serialise.** Hand the reasoning back and ask only for the `Verdict` object. The
second call does no judging.

Constrained decoding itself is roughly free — a matched-prompt reproduction found structured
output at or above unstructured throughout. What costs accuracy is reasoning *within* the
schema. Field ordering (`because` before `refuted`) mitigates it; splitting the calls removes it.

Where formatting is the whole task — extracting an accession, normalising a score — single-pass
schema forcing is correct and cheaper.

## What not to do

**Do not run a debate between verifiers.** Debate degraded majority-vote accuracy in **10 of
10** configurations tested, worst case −12.0 points; in up to **86.36%** of cases where a worker
started correct, debate never reached that answer; and confidence *rises* as deliberation
proceeds — two debating models both claimed ≥75% win probability in **61.7%** of debates.
Collect independent verdicts and adjudicate against sources.

**Do not let the verifier see the vote so far.** That converts independent verdicts into a
conformity cascade.

**Do not iterate.** If a verdict is unsatisfying, restart from the artifact with a clean
context rather than asking for another round. Self-correction rounds move accuracy the wrong
way: 95.5% → 91.5% → 89.0%.

**Do not optimise the prompt against verdict agreement with a judge.** That is training against
a monitor, and the measured outcome is that visible failures fall while actual failures persist
and monitor recall *"falls to near zero"*.

## The one exception where deliberation works

Asymmetric-information debate, and all four of its properties are load-bearing:

1. **Two adversarial** debaters, arguing opposite sides.
2. Both with **verified quote access** to a source.
3. A judge that **cannot see the source**.
4. **No interaction needed** — *"identical judge accuracy between static and interactive
   debate."*

Measured: judge accuracy **76%** (LLM) and **88%** (human) under debate, against **54% / 78%**
for a single source-privileged consultant and **48% / 60%** with no experts, p = 0.001.

And the failure direction worth internalising: *"judge accuracy decreases as consultants are
more persuasive"* while it *increases* with more persuasive debaters. **So never run a
one-sided source-privileged critic** — it is worse than having none. If you cannot field two
adversaries, do not field one.
