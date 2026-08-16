# Fan-out: briefing workers and merging their results

## The principle

**A worker that can only see one axis cannot trade it against another.**

This is independence by construction rather than by instruction, and it is the same principle the
orchestration design rests on — see `docs/research/06-chosen-design.md`. Telling one agent to
work all axes thoroughly does not survive context pressure. Giving each agent one axis makes the
trade-off structurally unavailable.

The specific failure being engineered away: a single agent holding every axis runs low on
context, silently reprioritises, and returns a plausible subset. It did not fail and it is not
lying. It made a resource decision off the record, and no field in the report shows it happened.

## What a worker gets

Exactly this, and nothing else:

```
AXIS:        pathway_membership
QUESTION:    Which pathways contain the target, and who else is in them?
PREDICATE:   IN_PATHWAY, SHARES_PATHWAY_WITH
SCORE_KEY:   jaccard
SCORE_RANGE: [0.0, 1.0]
TARGET:      uniprot:O75469  (aliases: PXR, NR1I2, SXR)
PROPERTY:    pathway_membership = "xenobiotic metabolism regulation; nuclear receptor
             transcriptional response"  (from AxisDerivation)
EXPECTED:    ~15-40 proteins, mostly outside the NR1I subfamily
GRAPH:       reports/<run>/stage1/graph/     (write a GraphDelta; do not merge)
LADDER:      see strategy-ladder.md; minimum two distinct strategies
BUDGET:      120 queries or 20 minutes, whichever first
QUOTA:       20% of effort on the exploration rungs (5-7)
RETURN:      AxisSweep JSON — rounds, n_admitted, ledger, and exactly one of
             saturated / truncated_because / negative_result
```

## What a worker does not get

**The other axes.** Not "for context". Context is precisely what enables reprioritisation.

**The other workers' findings.** Two reasons. Independence: a worker that sees another's results
anchors on them, and correlated workers give a false impression of convergence. And correctness:
seeing a strong hit on the fold axis biases the pathway worker toward fold-similar proteins,
which is how one axis quietly becomes a filter on another.

**The report being written.** A worker aiming at a narrative selects for it. Its job is to
exhaust an axis, including finding out the axis is empty.

**A relevance target.** "Find the most relevant proteins" invites early stopping the moment
something relevant appears. The instruction is to work the ladder until the curve flattens.

## What to do with the aggregate

The orchestrator holds what the workers cannot see, and that is where cross-axis reasoning
belongs — not smuggled into a worker's briefing:

- **Deduplicate** across axes. The same protein arriving on four axes is the strongest signal in
  the graph, and only the orchestrator can see it.
- **Notice thin axes.** An axis returning far under its `expected_yield` is either a real
  boundary or an unexplored region, and both beat a fourth homologue.
- **Compare curves.** An axis still climbing when its neighbours flattened is where the next
  round of budget goes.
- **Detect a collapsed axis.** If `ANALOGOUS_ROLE_TO` returned only family members, the axis
  collapsed into `MEMBER_OF_FAMILY` and did not run. That is a briefing bug, not a finding.

## Merging

Workers write `GraphDelta`s independently. Merge through `KGStore.merge`, never
`GraphDelta.write_jsonl` alone:

```python
store = KGStore(graph_dir)
for delta in worker_deltas:
    problems = store.merge(delta)     # validates against the FULL graph
```

`write_jsonl` validates only within the delta, so it cannot see that an edge's endpoint exists
in the stored graph — and cannot see that it does *not*. Merging through the store is what keeps
dangling edges out of the source of truth, and a dangling edge is much harder to find later than
to reject now.

**Two workers discovering the same protein must produce the same node id.** That is what the
namespaced-id convention is for, and it is enforced at the `Node` validator rather than left to
agreement between workers who cannot see each other. Independently-discovered duplicates collapse
because the id is derived from the canonical accession, not from whoever found it first.

Deltas are append-only JSONL, so concurrent writes are safe and the merge is replayable. Provenance
travels per assertion via `asserted_by`, so after the fact you can ask which worker claimed what —
which is what makes a disagreement between two axes adjudicable rather than just confusing.

## Costing

Each axis is one worker, so cost scales linearly with axis count. A 29-item checklist deriving 12
axes means 12 workers. That is the price of not dropping axes silently, and it is worth stating
plainly rather than discovering at the invoice.

Two levers if the budget will not stretch, in order of preference:

1. **Reduce the axis count at derivation**, explicitly, with target-specific reasons in
   `dismissed`. A dismissed axis is visible; a starved one is not.
2. **Truncate some axes early**, recording `truncated_because="budget"` so they surface in
   `open_leads()`.

What not to do is give one worker several axes. That converts a visible budget constraint into an
invisible quality loss, which is the trade this whole design exists to prevent.
