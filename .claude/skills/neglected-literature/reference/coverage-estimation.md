# Coverage estimation

The question is "what fraction of the relevant retrievable literature did we actually
retrieve?" — and the honest answer is that you cannot know, because the missing material
leaves no trace. Capture-recapture gives a bounded guess, and the value of doing it is less
the number than the fact that it forces you to run two mechanically different searches.

## The estimator

Treat two discovery channels as two independent captures of the same population.

- `n_a` — relevant sources found by channel A
- `n_b` — relevant sources found by channel B
- `m` — found by both
- Chapman bias-corrected estimate: `N̂ = ((n_a + 1)(n_b + 1) / (m + 1)) − 1`
- Coverage = `n_total_observed / N̂`

Chapman rather than plain Lincoln-Petersen (`n_a · n_b / m`) because the plain form is badly
biased at small `m`, and `m` is always small here.

Worked example:

```
keyword_search found 40, backward_snowball found 25, both found 12, distinct total 53
N̂ = (41 × 26 / 13) − 1 = 81
coverage = 53 / 81 = 65%   (upper bound)
```

So roughly 28 relevant sources were plausibly not found by either channel. That is the useful
output: not "we are 65% complete" but "there are probably about 28 more, so decide whether to
keep going."

## How it fails, and in which direction

Two assumptions, both violated in literature search:

1. **Independence.** Channels find the same *easy* sources — the well-indexed, well-titled,
   well-cited ones.
2. **Homogeneous catchability.** Some sources are far harder to find than others.

Both violations push the same way. Correlated channels inflate `m`, which shrinks `N̂`, which
inflates coverage. **The estimate errs toward telling you that you are finished.** That is the
dangerous direction, and it is why:

- `CoverageEstimate.coverage` is documented as an **upper bound** and must be reported that way.
- `channels_are_mechanically_different` returns False for two pull channels, and
  `SearchLedger.problems()` reports it, because two pull channels share the vocabulary
  assumption and their errors correlate by construction.

Pick pairs whose failure modes differ — a keyword query against a citation traversal, not two
keyword queries. The pairing table is in [channels.md](channels.md).

## Zero overlap

If `m = 0` the estimator diverges and `estimated_population` returns None. This is not a
failure to report as missing data. **Two channels that found nothing in common is strong
evidence that the population is much larger than either found** — the opposite of what a
missing number suggests. Say that explicitly in the ledger; `summary()` does.

## What to actually report

In the Model Report, alongside the ledger:

1. **Channel mix** — share of admitted sources per channel. Concentration is the warning sign:
   if one channel produced over 80% of the sources, `problems()` flags it, because the others
   were configured rather than run.
2. **Unique yield per channel** — `n_unique`. A channel with high volume and zero unique finds
   is redundant however productive it looks, and `redundant_channels()` names it. This is the
   number that decides whether to keep a channel next run.
3. **Coverage estimate with its pair and its caveat** — never the bare percentage.
4. **Known gaps** — regions deliberately not searched. An unrecorded gap is indistinguishable
   from a claim of completeness, and this is the cheapest honest thing in the report.
5. **Stopping reason** — an observed quantity. The discovery curve flattened, the quota was
   spent, the budget capped out. Never model confidence: a model grows more confident as its
   sampling grows more uniform, so confidence rises exactly when coverage stops improving.

## Screening at high recall

If a large candidate pool needs triage, the operating point is high recall and low precision,
following the asymmetry that motivates this whole skill. The systematic-review literature
measures this as **WSS@95** — work saved over random sampling at 95% recall (Cohen et al. 2006)
— and it is the right metric here too, because it prices screening effort against a recall
target rather than against accuracy.

Practical consequence: a screener that admits four irrelevant sources for every relevant one is
working correctly. Verification is the filter; screening is not.

## Three-channel refinement

With three or more channels, log-linear capture-recapture can model the dependence between
channels instead of assuming it away, which addresses the main bias directly. It needs enough
overlap counts to fit, which usually means a larger corpus than a single stage produces.

Worth doing at synthesis time across all stages' ledgers, not per stage. Until then, report the
best-separated pair and its caveat — an honest bound beats a precise-looking number resting on
an assumption you know is false.
