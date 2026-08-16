---
name: axis-sweep
description: >-
  Work a single neighbourhood axis to exhaustion in its own subagent, with an observable
  stopping rule. One worker owns one axis, sees only that axis, records its discovery curve
  round by round, and may claim saturation only when the curve has flattened across at
  least three rounds using distinct strategies. A sweep that ran out of budget is recorded
  as truncated, not saturated. Use after target-properties has derived the axes, to
  populate each one. Trigger on: "sweep this axis", "exhaust this connection", "keep
  going", "did it stop early", "saturate", "one agent per axis", "fan out over axes", or
  /axis-sweep.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, WebSearch, WebFetch
---

# Axis sweep

One axis, one worker, one stopping rule you can check.

The failure being engineered away: a single agent holding every axis at once runs low on
context, silently reprioritises, and returns a plausible subset. It is not lying and it did
not fail — it *traded* axes against each other, off the record, and the report shows no
trace of the trade.

**A worker that can only see one axis cannot trade it against another.** That is the whole
design. Independence by construction rather than by instruction, which is the same principle
the orchestration design rests on (see `docs/research/06-chosen-design.md`).

## The stopping rule

`AxisSweep` accepts three end states and no fourth:

| State | What it means | What it requires |
|---|---|---|
| **saturated** | The axis is exhausted; this is a closed question. | ≥3 rounds, ≥2 distinct strategies, and the last two rounds yielding ≤25% of all new finds |
| **truncated** | Budget, time, or a missing tool stopped it. An open lead. | `truncated_because` naming the constraint |
| **empty** | Searched properly, genuinely nothing there. A finding. | `negative_result` describing what was searched |

Anything else leaves the axis in `UNKNOWN STATE`, which `problems()` reports. Claiming both
saturation and truncation is a validation error — a sweep that ran out of budget did not
exhaust its axis, and conflating the two is how the next run repeats the work instead of
resuming it.

**`tail_yield` is the check that matters.** If the last two rounds produced more than a
quarter of everything new, the curve is still climbing and the claim of saturation is
rejected. That is the signature of stopping because it felt like enough.

**Two distinct strategies minimum.** Re-running the same query and getting the same answer
measures the query, not the literature. `strategy` on each round must say how it differed
from the last, and identical strings collapse in `strategies_tried`.

## Rounds

Each `SweepRound` records `n_queries`, `n_candidates`, `n_new`, and `strategy`. Together they
are the discovery curve, which `curve()` renders as a sparkline so flatness is visible without
reading numbers:

```
pathway          ██▆▃▁▁      37 admitted  [sweep:pathway#1] saturated
analogous_role   ▃▅█         12 admitted  [sweep:analog#1]  TRUNCATED (budget)
```

The second line is the useful one: an axis still climbing when it ran out of budget, named as
an open lead rather than buried.

Escalate strategy between rounds rather than repeating it. A workable ladder, with the specific
query forms for each, is in [strategy-ladder.md](reference/strategy-ladder.md):

1. The obvious query in our own vocabulary.
2. The same question in the field's *other* dialects, including the term that predates the
   current one.
3. Structured/database query instead of text — the axis's native index, if it has one.
4. Citation traversal from the best hit so far, both directions.
5. The negative form: who reports this *failing*, or reports no relationship.
6. Adjacent-field query: who outside this field has the same structural problem.
7. Hand off to `neglected-literature` for the exploration quota on this axis.

Rounds 5 and 6 are the ones that get skipped and the ones that pay. A negative result on an
axis is often the most decision-relevant thing the axis produces.

## Guard rails

- **The worker sees one axis.** Do not pass it the other axes "for context". Context is exactly
  what lets it reprioritise, and the aggregate check flags any worker owning more than two axes.
- **Admit through verification, not through retrieval.** `n_candidates` is what the query
  returned; `n_admitted` is what survived. A sweep with candidates and zero admitted must say
  whether they failed verification (a negative result) or whether verification was skipped.
- **Score within the axis's own range.** Each axis declares `score_range`; a TM-score and a
  Tanimoto are not comparable and normalising across axes invents a ranking.
- **Write the negative result even when the axis is thin.** "Three proteins share this pocket
  character and all are family members" bounds the axis, and a bound is usable.
- **One predicate per axis.** The axis writes its declared predicate and no other. An axis
  that writes two predicates is two axes that will be reported as one.
- **Report the ledger per axis, not once per run.** Channel mix differs by axis, and a run-level
  ledger hides an axis that only ever ran one keyword query.

## Fan-out

Axes are independent, so run them concurrently. Each worker gets: the axis question, its
predicate and score range, the target's resolved identifiers, the relevant property from
`AxisDerivation`, and the graph write path. Nothing else.

Workers write `GraphDelta`s independently. Merge through `KGStore.merge`, which validates
against the full graph and knows the existing node types — `write_jsonl` alone cannot, and
will let a dangling edge into the source of truth.

Two workers discovering the same protein must produce the same node id. That is what the
namespaced-id convention is for; it is also why the id convention is enforced at the `Node`
validator rather than by agreement.

## Checking

```bash
reagent axes sweep-status --report reports/<run>/stage1/report.json --strict
```

Reports, per axis: the curve, admitted count, worker, state, and every problem. Then the
aggregate checks that catch what per-axis checks cannot — axes derived but never swept, and
workers holding too many axes.

An axis derived and never swept is worse than an axis never derived, because the report now
carries the appearance of breadth. That check is the reason `NeighborhoodSweep` exists as a
type rather than a list.

## Anti-patterns

- **Stopping when results start looking familiar.** Familiarity is a property of the query.
- **Counting queries as effort.** Ten paraphrases of one query is one round, and
  `strategies_tried` will say so.
- **Letting a rich axis crowd out a thin one.** The thin axis is the interesting one — it is
  either a real boundary worth recording or an unexplored region worth pushing on, and both
  outcomes beat a fourth homologue.
- **Filling `truncated_because` with "done".** If it was done, it was saturated. If it was
  not, name the constraint.
- **Merging two axes because one returned little.** That is how `analogous_cascade_role`
  disappears into `pathway_membership`, which is the specific loss this whole design is built
  to prevent.

## References

- [strategy-ladder.md](reference/strategy-ladder.md) — the seven escalation rungs with concrete query forms per axis type
- [saturation.md](reference/saturation.md) — what a flattened discovery curve looks like, worked examples of real vs premature flattening, and why model confidence is the wrong signal
- [fanout.md](reference/fanout.md) — worker briefing template, what to withhold and why, and the merge protocol
