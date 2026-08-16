# Tuning the frontier

Four parameters, and the defaults are chosen for a moderately dense biological graph. When they
are wrong the walk fails in one of two recognisable ways, and both have a signature in
`summary()`.

## The defaults, and what each one is for

| Parameter | Default | Raise it when | Lower it when |
|---|---|---|---|
| `max_nodes` | 400 | the deferred queue holds nodes you can name and want | the graph is a hairball and the render exceeds ~5,000 elements |
| `max_hops` | 3 | almost never — see below | the graph is dense and hop 2 already returns hubs |
| `decay` | 0.45 | you want depth: 0.6 keeps hop 3 alive | you want a tight neighbourhood: 0.3 makes hop 2 marginal |
| `relevance_floor` | 0.05 | admissions are arriving that nobody can justify | the frontier empties too early |
| `hub_degree` | 60 | the graph is dense and legitimate nodes are being penalised | hubs are getting through |
| `exploration_quota` | 0.2 | the walk keeps returning the same well-studied region | never below ~0.1; the quota is the only counterweight to hub convergence |

**`max_hops` is the parameter to leave alone.** Past three hops relevance is noise — a fourth-hop
node starts at about 4% of the focal node's standing at the default decay, which is below the
floor. If a walk feels shallow the fix is more `max_nodes` or another relation type, not another
hop. `ExpansionBudget` enforces the arithmetic: a configuration where nothing at the last hop can
clear the floor is rejected, because it would make the walk *look* deeper than it is.

## Over-expansion, and its signature

```
Expansion from uniprot:O75469: 400 admitted of 8,900 visited, 3,100 deferred
  by hop: h0=1, h1=61, h2=338
  top relations: INTERACTS_WITH(291), IN_PATHWAY(52), BINDS(31)
  stopped: node_budget
  exploration quota 20%, spent 3%
  hubs admitted: ['uniprot:P0CG48', 'uniprot:P04637', 'uniprot:P62988', ...]
```

Four tells, all present:

- **73% of admissions through one predicate.** A PPI dump ate the walk. `max_per_predicate` is
  the fix, and it should have been set before running.
- **Hop 2 is five times hop 1.** Correct expansion narrows; this is fanning out.
- **Quota at 3% of 20%.** Relevance ordering won, which means hubs won.
- **Hubs in the admitted list.** Ubiquitin and p53 are connected to everything, so their presence
  says nothing about the target.

Fixes, in order: set `max_per_predicate` to roughly `max_nodes / n_relation_types`, raise
`hub_degree` scrutiny by *lowering* the threshold, and enforce the quota by admitting
low-degree frontier nodes before the budget runs out rather than after.

## Under-expansion, and its signature

```
Expansion from uniprot:O75469: 14 admitted of 22 visited, 3 deferred
  by hop: h0=1, h1=13
  top relations: MEMBER_OF_FAMILY(8), HAS_STRUCTURE(5)
  stopped: saturated
```

Also four tells:

- **Nothing past hop 1.** The decay or the floor is too aggressive for this graph.
- **Only composition predicates.** The graph does not *have* the other relation types yet —
  which is a `target-properties` and `relation-expand` sourcing problem, not a tuning one.
- **`saturated` with 22 visited.** Genuine saturation of a 22-node region is possible and here it
  means the graph is nearly empty.
- **Almost nothing deferred.** There was no frontier to run out of.

**Do not fix this by raising the budget.** A deeper walk over a graph missing whole relation
types just goes further in the directions you already had. Fix the sourcing first: the checklist
gate in `target-properties` is what catches a missing layer, and expansion depth cannot
substitute for it.

## The shape to want

```
  by hop: h0=1, h1=64, h2=97, h3=25
  top relations: INTERACTS_WITH(41), IN_PATHWAY(28), BINDS(24), TRANSCRIPTIONALLY_ACTIVATES(19)
  stopped: node_budget — raising to 800 would reach the CYP substrate set and the miRNA layer
  exploration quota 20%, spent 22%
  hubs admitted: ['uniprot:P0CG48']
```

Rising then falling hop counts, no predicate above ~60%, several relation types represented,
quota met, one or two hubs, and **a stop note naming what more budget would buy.** That last
sentence is what the next run resumes from, and it is the cheapest honest thing in the record.

## Density and the hub threshold

`hub_degree = 60` assumes a graph where a typical protein has tens of neighbours. Two sanity
checks before trusting it:

```sql
-- degree distribution
SELECT n, COUNT(*) FROM (
  SELECT src AS id, COUNT(*) n FROM edges GROUP BY src
  UNION ALL
  SELECT dst AS id, COUNT(*) n FROM edges GROUP BY dst
) GROUP BY n ORDER BY n DESC LIMIT 20;
```

If the 95th percentile degree is 20, a threshold of 60 penalises nothing and the hub correction
is inert. If the median is 200 — which happens once a PPI dump lands — a threshold of 60
penalises everything and relevance collapses uniformly, which is the same as having no ranking.

**Set the threshold from the distribution, not from the default**, and put the value you used in
the run record. A hub penalty tuned to a different graph is worse than none, because it looks
like a correction was applied.

## Interaction with the render

The ego view caps at ~5,000 elements before it becomes a hairball, and `extract_ego` has its own
fan-out cap that records what it dropped. So a 400-node expansion is comfortable and a
4,000-node one is not viewable as one picture — it has to be sliced by **tier** (see
`FamilyTier`), which is what the tier filter exists for.

That is worth knowing before raising `max_nodes` into the thousands: the walk will succeed and
the figure will not, and the honest move at that scale is to expand wide and *view* narrow
rather than to expand narrow.

## Resuming

`deferred` holds each node with its relevance and the relation that would have brought it in, so
a second pass is a re-run with a higher `max_nodes` and the same seed, not a fresh walk. Two
things make that work:

- **Node ids are derived from what the thing is**, so a second walk converges on the same nodes
  rather than duplicating them.
- **`stop_note` says what the next budget buys**, so the decision to spend it is informed.

Record both runs. Two expansions with different budgets are the cheapest available evidence about
whether the frontier was worth pursuing — if doubling the budget admitted nothing anyone cared
about, the first walk was the right size, and that is worth knowing next time.
