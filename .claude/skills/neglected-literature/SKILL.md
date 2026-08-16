---
name: neglected-literature
description: >-
  Deliberately recover relevant work the field has under-attended: recent papers with no
  citations yet, small-field work with a low ceiling, papers cited three times by the
  three papers that matter, sleeping beauties, interdisciplinary orphans, negative
  results, non-English and regional literature, theses and tech reports, methods
  abandoned for reasons that have since expired, work using vocabulary that predates the
  field's current terms, and connections that exist in no single paper. Runs as the
  exploration quota against a search that otherwise converges on hubs. Use after a first
  literature pass, before declaring coverage, and whenever a search feels finished.
  Trigger on: "what are we missing", "underground sources", "understudied", "low
  citations", "serendipity", "obscure", "overlooked", "did we miss anything",
  "exhaustive search", "coverage", or /neglected-literature.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, WebSearch, WebFetch
---

# Neglected literature

One asymmetry justifies everything in this skill.

**A recall failure is unrecoverable. A precision failure is not.** A source you never
retrieved cannot be down-weighted later, argued with, or noticed — and nothing downstream
can distinguish *"we considered it and rejected it"* from *"we never saw it"*. A source
retrieved wrongly gets filtered by the verification gate at known cost. So this stage runs
at high recall and low precision on purpose, and reports coverage rather than accuracy.

The corollary is that **"we searched thoroughly" is not a claim this project accepts
without a ledger.** Fill in `SearchLedger` or the assertion is unfalsifiable.

## Why low citation count says almost nothing

Citations measure accumulated attention. Attention accrues by cumulative advantage — the
Matthew effect (Merton 1968) formalised as preferential attachment (Price 1976) — which is
only loosely coupled to relevance and is *strongly* coupled to how visible a work already
was. Any recommender trained on that signal, including an agent doing a literature search,
inherits the bias and amplifies it.

So citation count is used here as one input among many, never as a filter. Twelve distinct
reasons a relevant paper can be under-cited, each with its own detection strategy, are in
[recovery-mechanisms.md](reference/recovery-mechanisms.md). The summary:

| Reason (`NeglectReason`) | How you detect it, rather than assume it |
|---|---|
| `too_recent` | Age-normalise. A 2026 paper with 2 citations is uninformative, not weak. |
| `small_field` | Percentile within **field and year**. A small field has a low ceiling. |
| `high_quality_citers` | Look at *who* cites it. Three citations from the three papers the subfield is built on is a different signal from three passing mentions. |
| `sleeping_beauty` | Dormancy then acceleration (van Raan 2004; Ke et al. 2015 give the "beauty coefficient"). Find the awakening paper. |
| `interdisciplinary_orphan` | Reference list spans distant fields; neither field's core cites it. Search the *union* of two literatures. |
| `negative_result` | Query explicitly for nulls and failures. Citation practice favours positive findings (Duyx et al. 2017), and nulls are the highest-value input to pipeline design. |
| `language_barrier` | Regional indexes with translated terms — SciELO, J-STAGE, KCI, CNKI, African Journals Online. |
| `not_indexed` | Theses, tech reports, conference-only work, pre-digital literature. |
| `prematurely_abandoned` | Find why it was dropped, then check whether the reason still holds. Compute cost and data scarcity both expire. |
| `low_amplification` | Do not filter on venue or institution. |
| `vocabulary_mismatch` | Re-query in each field's own dialect, including the dialect that predates the current term. |
| `never_stated` | No search finds this. It is a graph query — see below. |

## The one that is not a search at all

`never_stated` is Swanson's *undiscovered public knowledge* (1986): A relates to B in one
literature, B relates to C in another, and no paper has ever stated A–C. His fish-oil /
Raynaud's and magnesium / migraine cases were found this way, by hand, from complementary
literatures that did not cite each other.

**We have the graph, so this is a query rather than an insight.** Find two-hop paths
`A → B → C` where no `A → C` edge exists, rank by how disjoint A's and C's literatures
are, and emit each as a candidate with channel `graph_gap`. Most will be noise. The ones
that are not are unreachable by any keyword search, because the sentence you would search
for has never been written. Query recipes are in
[graph-gap-queries.md](reference/graph-gap-queries.md).

## Guard rails

- **A neglect reason must be evidenced, never narrated.** `Evidence._neglect_claims_are_backed`
  rejects a bibliometric reason with no supporting field in `AttentionProfile`, and requires
  written justification for the reasons no citation data can establish. This is the most
  important guard in the skill, because *"few citations, but ahead of its time"* fits every
  paper ever written, and a skill that hunts under-cited work will otherwise become a
  laundering machine for irrelevance.
- **Relevance is established independently of neglect.** Being overlooked is not evidence of
  being right. Run the same verification you would run on a well-cited source; the only thing
  neglect buys is *entry to the candidate pool*.
- **Record the channel on every source.** `found_via` is what makes coverage estimable. Without
  it the ledger cannot tell a thorough search from a lucky one.
- **A channel that finds nothing unique is redundant, however productive it looks.** Track
  `n_unique`, not just `n_admitted`. Two keyword channels differing by a synonym are one channel.
- **Never report a coverage figure without its direction of error.** See below.
- **Grey and neglected are different axes.** A GitHub repo is grey (`source-scout`'s remit);
  a 2019 Scientometrics paper with four citations is neglected. A well-cited blog post is
  grey and not neglected. Do not conflate them.

## Coverage, and why the estimate lies in a specific direction

Capture-recapture with the Chapman estimator: two channels as two captures, `n1`, `n2`,
overlap `m`, population `((n1+1)(n2+1)/(m+1)) − 1`, coverage = observed / population.

It assumes the channels are independent and every source equally catchable. Both fail in
literature search, because channels tend to find the same *easy* sources. That inflates
the overlap, shrinks the population estimate, and therefore **overstates coverage** — the
direction that tells you to stop when you should not. Two consequences, both enforced:

1. **Report coverage as an upper bound.** `CoverageEstimate.coverage` is documented that way.
2. **Never estimate from two pull channels.** Both share the vocabulary assumption, so their
   errors correlate by construction. `channels_are_mechanically_different` flags it and
   `SearchLedger.problems()` reports it. Pair a keyword query with a citation traversal.

Disjoint channels give no estimate at all, and that is informative rather than a failure:
if two channels found nothing in common, the population is probably much larger than
either found.

## The exploration quota

Set `exploration_quota` before searching and spend it. It exists because the alternative —
preferring exploration when convenient — loses to schedule pressure every time, and because
a search that follows relevance signals converges on the literature's existing hubs. There
is direct evidence that collective search over-concentrates on high-degree nodes and that a
more exploratory allocation would be more efficient (Rzhetsky et al. 2015, PNAS).

Uzzi et al. (2013, *Science*) give the shape to aim for: the highest-impact work pairs a
**conventional core with an atypical tail**, not atypicality throughout. So the quota is a
tail, deliberately sized — typically 15–25% of retrieval effort — and not the main effort.

`SearchLedger.problems()` fails a run that declared a quota and underspent it, because that
is the first thing dropped under pressure and the failure leaves no other trace.

## Stopping

State the reason in `saturation_note`, and make it an **observed quantity**: the discovery
curve flattened across at least three rounds with distinct strategies, the quota was spent,
or the budget capped out. Never model confidence — a model grows more confident as its
sampling grows more uniform, so confidence rises exactly when coverage stops improving.

A run that stopped on budget is **truncated**, not saturated. `AxisSweep` enforces the
distinction and refuses to accept both at once, because a truncated axis is an open lead and
a saturated one is a closed question, and conflating them is how the next run repeats the work.

Then fill `known_gaps`. Every real search has regions it did not reach; not naming them
reads as a claim of completeness, and it is the cheapest honest thing in the whole report.

## Where to actually look

Channel-by-channel tool routing — Paperclip's verified switches, OpenAlex and Semantic
Scholar for citation traversal and venue quality, GitHub and Zenodo and Kaggle for orphaned
deposits, regional indexes, thesis archives — is in
[channels.md](reference/channels.md). Two things worth knowing before you start:

- **Paperclip cannot search patents**, despite what its help text implies. Patents go
  through a separate channel. And `--save-as` is the JSON switch, not `--json`.
- **Snowballing is not a fallback.** In an audit of a review of complex evidence, protocol-driven
  database search accounted for a minority of the primary sources actually used, with citation
  chaining and personal contacts supplying most of the rest (Greenhalgh & Peacock 2005, *BMJ*
  — verify the exact split before quoting it). If your ledger shows no traversal channel,
  you have not run the productive half of the search.

## Anti-patterns

- **Treating obscurity as merit.** The inverse of citation-chasing is not rigour, it is
  contrarianism. Neglect gets a source *considered*, nothing more.
- **One search, many synonyms, called exhaustive.** That measures the query.
- **Reporting coverage without the upper-bound caveat.** The number is optimistic by
  construction; presenting it bare converts a caveat into a false assurance.
- **Filling the quota with junk to satisfy the counter.** `n_unique` and the verification
  gate catch it; more importantly it defeats the purpose, which was recall of *relevant* work.
- **Deferring the ledger to the end.** Channel attribution reconstructed afterwards is
  guesswork, and the redundancy analysis silently becomes fiction.
- **Skipping `known_gaps` because none come to mind.** If none come to mind, the search was
  not wide enough to find its own edges.

## References

- [recovery-mechanisms.md](reference/recovery-mechanisms.md) — the twelve reasons, each with detection strategy, the signal that evidences it, and its failure mode
- [channels.md](reference/channels.md) — concrete tool routing per discovery channel, with what each index does and does not cover
- [graph-gap-queries.md](reference/graph-gap-queries.md) — Swanson-style two-hop queries over our own KG, with ranking heuristics and worked examples
- [coverage-estimation.md](reference/coverage-estimation.md) — capture-recapture worked through, assumption violations, and what to report
