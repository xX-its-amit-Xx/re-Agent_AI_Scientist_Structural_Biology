# Saturation: what a finished axis looks like

Saturation is a property of the **discovery curve**, not of how the agent feels. The distinction
is the entire content of this document, because the two are easy to confuse and diverge in a
predictable direction.

## The rule

`AxisSweep` accepts a saturation claim only when all three hold:

1. **≥3 rounds.** Two points cannot distinguish a plateau from a slow start.
2. **≥2 distinct strategies.** Otherwise the flatness measures the query.
3. **`tail_yield` ≤ 0.25.** The last two rounds produced no more than a quarter of all new finds.

Fail any one and `problems()` rejects it. The third is the one that catches real premature
stopping.

## Reading a curve

```
pathway           ██▆▃▁▁     saturated       tail_yield 0.06
```
Steep, then decaying to near-zero across two more rounds with different strategies. The axis is
done. Later rounds cost as much as earlier ones and returned almost nothing.

```
analogous_role    ▃▅█        TRUNCATED       tail_yield 0.62
```
Still climbing when it stopped. **This is the honest shape for a reasoning-bound axis** — the
third rung was the most productive and there was no fourth. `truncated_because="budget"`, and it
goes in `open_leads()` as the first thing a second pass should resume.

```
fold              █▁▁▁▁      saturated       tail_yield 0.00
```
Everything from round 1, nothing after. Legitimate for a well-indexed axis where one structured
query is genuinely exhaustive — but check the strategies actually differed. If rounds 2–5 were
paraphrases of round 1, this is one round wearing five, and `strategies_tried` will say so.

```
promiscuity       ▄▅▄▆▅      neither         tail_yield 0.44
```
Flat but *not decaying* — every round pays about the same. This is the clearest signal that the
axis is nowhere near exhausted: a uniform yield means the population is much larger than what has
been sampled. Do not claim saturation; either keep going or truncate honestly.

## Why model confidence is the wrong signal

A model grows more confident as its sampling grows more uniform. Rounds that return familiar
results feel like convergence, and familiarity is a property of the query — so **confidence rises
exactly when coverage stops improving**. The two signals are not merely different; they are
anti-correlated in the regime that matters.

This is why `saturation_note` must reference an observed quantity. Acceptable:

- "discovery curve flat across rounds 4–6 under three distinct strategies, tail yield 0.08"
- "exploration quota of 20% spent; 3 of 14 candidates admitted"
- "budget cap reached at 180 queries" — which is *truncation*, and must be recorded as such

Not acceptable: "results appeared comprehensive", "no new relevant work found", "the axis seems
well covered". Each is a report of a feeling, and each is what the flattened-tail check exists to
replace.

## Truncated is not a failure

`truncated` is the honest state for most axes on a first pass. It says: this axis is an open lead,
here is why it stopped, resume here. That is strictly more useful than a false saturation claim,
which tells the next run the question is closed and guarantees the work is never resumed.

The validator refuses both at once for exactly this reason. A sweep that ran out of budget did
not exhaust its axis, and conflating the two is how a gap becomes permanent.

## Empty is a finding

An axis that searched properly and found nothing gets `negative_result`:

> "No protein outside the NR1I subfamily shares the target's pocket-volume range (1150–1650 Å³)
> with an adaptable-pocket annotation. Searched RCSB by pocket geometry (rung 3), Foldseek
> structural neighbours filtered on volume, and ChEMBL promiscuity breadth. The pocket-character
> axis is family-bounded for this target."

That bounds the axis, and a bound is usable: it argues against spending Stage 2 effort on
non-family pocket analogues, and it stops the next run repeating the search. Note it also names
what was searched — an empty result without its method is indistinguishable from not having
looked.

## The failure this all guards

Observed, repeatedly: a search runs, results start looking familiar, the agent concludes the
space is covered, and reports a neighbourhood. Nothing in the output distinguishes that from an
exhaustive search, because **an unfound source leaves no trace in the report that cites the ones
you did find.**

The curve is the trace. It is not a perfect measure — a curve can flatten because the *strategy*
saturated rather than the axis — which is why two distinct strategies are required alongside the
flat tail. Together they are the difference between "this axis is exhausted" and "this query is
exhausted", and only the first is a claim about the world.

## Cross-axis check

`NeighborhoodSweep.problems()` adds what per-axis checks cannot see:

- **Axes derived but never swept.** Worse than never deriving them, because the report now shows
  evidence of breadth.
- **A worker owning more than two axes.** The context-pressure failure mode: it runs low on
  context and quietly reprioritises, returning a plausible subset.

Both are structural, and both are invisible from inside any single sweep — which is why the
aggregate is a type rather than a list.
