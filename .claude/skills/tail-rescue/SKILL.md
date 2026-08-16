---
name: tail-rescue
description: >-
  Recover the last few points of a pipeline's score by overwriting only the
  lowest-confidence items with a decorrelated generator's candidates. Sweeps how
  many to replace rather than guessing, because over-replacement destroys good
  picks, and reports the whole curve as evidence the peak is real. Use when a
  selector is tuned and the remaining loss is concentrated in a small number of
  bad items. Trigger on: "worst cases", "rescue the tail", "lowest confidence
  items", "swap sweep", "salvage failures", "fix the bad items", or /tail-rescue.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
---

# Tail rescue

After selection is tuned, the remaining loss is rarely spread evenly. It
concentrates in a small number of items where the whole pool was bad, or where the
selector picked badly and its own confidence says so.

Those items are recoverable, and they are recoverable **only** by a different
generator — not by a better score over the same candidates. A selector that has
already ranked an item last has said everything it has to say about it.

This is a small, cheap, late-stage move that reliably buys a fraction of a point.
On a competitive task, a fraction of a point is often the whole margin.

## The core insight

**The tail needs a different model, not a better score.**

If every candidate for an item is bad, no ranking over those candidates helps. The
only fix is candidates that were not in the pool — which means running a generator
that fails differently. That is exactly what `method.correlation_matrix` was
measured for.

The mirrored insight, equally important: **over-replacement destroys good picks.**
Replace too many items and you start overwriting selections that were correct,
with candidates from a generator that is worse on average. The curve turns over.

So there is an optimum, it is not at either end, and it is not guessable.

## The sweep

Rank items by selected confidence, ascending. Replace the bottom N with the rescue
generator's candidate. Sweep N. Plot the whole curve.

```python
def sweep_rescue(ranking, baseline_pick, rescue_pick, score_fn, n_values):
    """ranking: item ids, worst-confidence first. Returns {N: score}."""
    out = {}
    for n in n_values:
        swapped = set(ranking[:n])
        picks = {i: (rescue_pick[i] if i in swapped else baseline_pick[i])
                 for i in baseline_pick}
        out[n] = score_fn(picks)
    return out
```

A representative shape, from a case where the pipeline had ~180 items:

| N replaced | 0 | 4 | **8** | 12 | 20 |
|---|---|---|---|---|---|
| Score | 0.5472 | 0.5578 | **0.5640** | 0.5629 | 0.5587 |

Note what this shows. The peak is at 8 — roughly 4% of items. By 20 the gain has
substantially eroded. A team that guessed "replace the worst 10%" would have landed
past the peak and reported a smaller improvement as if it were the ceiling.

Within that peak, individual rescues can be dramatic: one item went from 0.123 to
0.919. **The tail is real but small.** Both halves of that sentence are load
bearing.

## Choosing the rescue generator

Not the best generator. The **most decorrelated** one, among those that are decent.

Read `method.correlation_matrix` and pick the generator whose per-item errors
correlate least with the one that produced most of your selections. If your primary
selections come mostly from generator A, a rescuer correlating 0.5 with A is worth
far more than one correlating 0.9, even if the latter scores better on average.

The reasoning is direct: you are asking for candidates on precisely the items where
your current generators failed. A highly correlated rescuer will fail on the same
ones and buy nothing.

If the correlation matrix shows nothing below about 0.8, say so plainly. Your pool
lacks the diversity this stage requires, and the honest finding is that the fix
belongs upstream in `generator-diversity`, not here.

## Workflow

1. Read `method.selection` and `method.confidence_ranking`. The ranking's bottom
   end must be meaningful — if `score-normalization` flagged the signal as
   uncalibrated in the tail, this stage cannot proceed on it.
2. Read `method.correlation_matrix` and choose the rescue generator by
   decorrelation, not by average quality. Record why.
3. Ensure the rescue generator has candidates for the tail items. If it does not,
   generate them — this is a small, targeted, cheap run, not a full pass.
4. Sweep N over a range spanning both sides of the plausible peak. Include N=0.
   A sweep that does not include the baseline cannot demonstrate an improvement.
5. Bootstrap the peak against N=0. A peak inside the noise is not a peak.
6. Emit `method.rescued_selection` and `method.rescue_sweep`.

## Choosing the sweep range

Start with N values spanning roughly 1% to 15% of items, log-spaced. The optimum in
observed cases has landed at a few percent, but that is a starting prior and not a
rule — a pipeline with a broader failure mode will peak later.

Two rules for the range:

- **Always include N=0.** It is the baseline and the sweep is meaningless without
  it.
- **Extend past the apparent peak** until the curve is clearly declining. A sweep
  that stops at the maximum tested value cannot distinguish a peak from a plateau
  you never reached the end of.

## Guard rails

- **Sweep N; never guess it.** Both directions cost real points, and the optimum is
  not at either extreme.
- **Report the whole curve, not the peak.** The shape is the evidence that the peak
  is real rather than a noise spike. A single number cannot distinguish those.
- **Choose the rescuer by decorrelation.** Rescuing with a correlated generator
  reapplies the same failure and buys nothing.
- **Rescue by confidence rank, never by true quality.** Selecting the tail using
  labels is a leak, and it produces an improvement that will not reproduce.
- **Bootstrap the peak against N=0.** A 0.005 gain on a small item set is noise.
- **Do not iterate the rescue.** Rescuing the rescued tail with a third generator
  compounds selection on the same confidence signal and overfits it. One pass.
- **Keep the unrescued selection.** You will want to compare, and reconstructing it
  after the fact is error-prone.

## Anti-patterns

- **Replacing a fixed fraction because it sounded reasonable.** The measured
  optimum has been well under 10%; a 10% guess lands past the peak.
- **Rescuing with the best-scoring generator** rather than the most decorrelated
  one. Average quality is the wrong criterion for this specific job.
- **Reporting only the peak value.** Without the curve, a reader cannot tell a real
  optimum from a fluctuation, and neither can you.
- **Running the rescue before selection is settled.** This stage is worth a
  fraction of a point; selection is worth many times more. Order matters.
- **Using true scores to pick which items to rescue.** The leak that makes this
  stage look far better than it is.
- **Iterating until the number stops improving.** That is fitting the confidence
  signal, one item at a time.
- **Concluding the tail does not exist because the first sweep was flat.** Check
  the rescuer's correlation first — a flat sweep with a correlated rescuer is a
  statement about the rescuer, not about the tail.

## Guarding against the flat sweep

If the sweep is flat or monotonically declining, work through this in order:

1. **Is the rescuer decorrelated?** Below about 0.8 correlation, or the result is
   uninformative.
2. **Is the confidence ranking meaningful at the bottom?** If the signal's AUC was
   measured only in aggregate, it may carry no information in the tail
   specifically. Re-measure discrimination restricted to the lowest-ranked items.
3. **Is the loss actually concentrated?** Plot per-item loss sorted descending. If
   it is close to uniform, there is no tail to rescue and this stage does not
   apply — which is a legitimate and reportable outcome.

## Handoff

`method.rescued_selection` — the final candidate per item, with rescued items
flagged and the baseline pick retained alongside — and `method.rescue_sweep`, the
full N-versus-score curve with the peak marked and its interval against N=0.

Flagging the rescued items matters beyond bookkeeping: they are the pipeline's
known-hard cases, and they are the natural starting point for whatever comes next.
