---
name: relation-expand
description: >-
  Grow the knowledge graph outward across every relation type — protein-protein interaction,
  pathway and cascade, transcriptional control, RNA silencing, splice isoforms, sequence
  variants, orthology, drug-drug interaction, ADME — with a budget, a relevance decay, a hub
  penalty, an exploration quota, and a recorded frontier of what it could not reach. Every
  admitted node says which relation brought it in and through what, so a bad expansion can be
  undone by predicate. Use after target-properties has derived the axes and you want to go
  further out. Trigger on: "expand the graph", "go further", "more connections", "all possible
  connections", "second-degree", "PPI network", "why is this node here", "how deep should we
  go", or /relation-expand.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, WebSearch, WebFetch, Agent
---

# Relation expand

The request this serves is *"go further and further, for all possible connections."* The honest
answer starts with a refusal, and the refusal is what makes the rest useful.

## Why unbounded expansion fails

**A biological graph is a small world with enormous hubs** — ubiquitin, p53, HSP90, ATP,
calcium, the proteasome. Any two human proteins are typically three hops apart *through* one of
them. So a breadth-first walk from any starting point returns most of the interactome by hop
three, and what you get is not a comprehensive graph but an **undifferentiated** one: the
target's genuine neighbours and a housekeeping protein that touches everything are drawn
identically.

Exhaustive-in-principle is therefore worse than useless. It destroys the signal it was built to
find, and it does so while looking thorough — which is the failure mode this whole project is
arranged against.

## The four mechanisms, and what each one fixes

**Relevance decay.** Multiplied down at every hop. Without it a fourth-hop node arrives with
the same standing as a first-hop one and the ranking carries no information. Default 0.45, so a
fourth-hop node starts around 4% — roughly where "connected to" stops being a reason to include
something.

**Transmission by relation class.** Not every predicate carries relevance equally, and two of
them carry none:

| Class | Transmission | Examples |
|---|---|---|
| identity | 0.95 | isoform, ortholog, variant — nearly the same object |
| composition | 0.90 | part-of, has-pocket, has-fragment |
| physical | 0.80 | binds, contacts, interacts-with |
| similarity | 0.70 | fold, sequence, chemical, analogous-role |
| functional | 0.60 | pathway, transcriptional activation, regulation |
| clinical | 0.55 | DDI, metabolised-by, transported-by |
| contextual | 0.35 | co-expression, shared tissue |
| **bibliographic** | **0.00** | supported-by, measured-in — co-citation is not a relation |
| **methodological** | **0.00** | used-in, evaluated-on — see below |

Letting bibliographic edges propagate turns the frontier into a bibliography. And
`methodological` is non-propagating **for a biology walk** specifically: a frontier expanding
from a protein must not step onto `method:boltz-2.1` and then out to every protein ever
benchmarked with it. Stage 0 expands method space deliberately and needs the inverse map.

**Hub penalty.** A path *through* a high-degree node conveys almost nothing — "both interact
with ubiquitin" is true of most of the proteome. Relevance is divided by how far past the hub
threshold the intermediate sits, which is the same correction the graph-gap queries apply. The
default threshold of 60 is a parameter, not a law: it depends on the graph's density.

**Exploration quota.** A frontier ordered purely by relevance **converges on hubs**, because
hubs are what relevance signals point at. This is the popularity lock-in that
`neglected-literature` counters in the published record, appearing again one level down. A fixed
share of the node budget goes to low-degree frontier nodes — a *quota*, not a preference,
because a preference for exploring loses to schedule pressure every time. `problems()` fails a
run that declared one and underspent it.

## The frontier is recorded, never discarded

Every node the budget could not reach goes into `deferred` with its relevance and the relation
that would have brought it in. **A frontier that silently stops is indistinguishable from one
that finished** — the same failure `AxisSweep.truncated_because` and `SearchLedger.known_gaps`
exist to prevent, and the same asymmetry drives it: an unexplored region leaves no trace in a
graph listing what was explored.

`StopReason` has no value meaning "done". Even `SATURATED` means only that the frontier emptied
*above the relevance floor*, and nodes below the floor are still in `deferred`. Claiming
saturation with a large deferred queue is flagged as a budget stop wearing the wrong label.

## Provenance, so a bad expansion is reversible

Every `Admission` records `hop`, `relevance`, `via_predicate`, `via_node` and `admitted_by`. So:

- *"Why is ATP in my graph?"* → `provenance_of("chebi:ATP")` answers it.
- A relation that turned out to be noise can be undone **by predicate**, not by hand.
- `by_predicate()` shows whether one prolific relation — usually a PPI dump — ate the budget.
  Cap it with `max_per_predicate`.

`problems()` rejects an admission past hop 0 with no `via_node`: it cannot be explained or
undone, which makes it permanent by accident.

## The budget is checked for coherence

`ExpansionBudget` refuses a configuration where nothing at the last hop could clear the
relevance floor — with decay 0.3 and floor 0.05, hop 5 is dead budget and the walk would look
deeper than it is. Either raise the decay, lower the floor, or reduce the hops.

## Which relations to expand along

`target-properties` derives these from the target, and the checklist now includes the layers
this skill reaches: `LIGAND_CENSUS`, `INTENDED_BINDING_MODE`, `TRANSCRIPTIONAL_TARGETS`,
`UPSTREAM_REGULATION`, `RNA_REGULATION`, `SPLICE_ISOFORMS`, `SEQUENCE_VARIANTS`,
`DRUG_INTERACTIONS`, `ADME_ROLE`. Each must be used or explicitly dismissed — **that gate, not
this walk, is what makes the coverage exhaustive.** Expansion goes deep; the checklist goes wide.

Source routing per layer is in [sources.md](reference/sources.md). Two warnings worth having
before you start:

- **STRING's combined score is not evidence of physical interaction.** It aggregates text-mining
  and co-expression alongside experiment. Filter to experimental channels or say which channel
  you used, in the edge's `commentary`.
- **A PPI dump will swallow the budget.** Interaction databases return hundreds of partners of
  wildly varying quality. Set `max_per_predicate` before running `INTERACTS_WITH`.

## Reading the result

```
Expansion from uniprot:O75469: 187 admitted of 2,340 visited, 412 deferred
  by hop: h0=1, h1=64, h2=97, h3=25
  top relations: INTERACTS_WITH(41), IN_PATHWAY(28), BINDS(24), TRANSCRIPTIONALLY_ACTIVATES(19)
  stopped: node_budget — raising to 800 would reach the CYP substrate set and the miRNA layer
  exploration quota 20%, spent 22%
  hubs admitted: ['uniprot:P0CG48', 'uniprot:P04637']
```

The shape to want: hop counts rising then falling, no single predicate above ~60%, quota spent,
few hubs, and a stop note saying what more budget would buy. The shape to distrust: everything
at one hop through one predicate, quota unspent, and `saturated`.

## Anti-patterns

- **Raising `max_hops` to get more.** Past three hops relevance is noise; raise `max_nodes` or
  add a relation type instead.
- **Turning off the hub penalty because interesting nodes are being excluded.** The hub *is* the
  reason they are reachable. If a hub-mediated link matters, assert it directly with commentary.
- **Expanding before the checklist gate passes.** Depth over a graph missing a whole relation
  type just goes further in the directions you already had.
- **Letting bibliographic edges propagate** to "find more literature". That is
  `neglected-literature`'s job, and it has a ledger this walk does not.
- **Reporting the admitted count as coverage.** It is a budget, not a boundary. The deferred
  queue is the honest half.
- **A walk with no `stop_note`.** Say what raising the budget would reach; that sentence is what
  the next run resumes from.

## References

- [sources.md](reference/sources.md) — which database serves which relation type, what each one's score means, and where its coverage stops
- [tuning.md](reference/tuning.md) — choosing decay, hub threshold and quota for a given graph density, with worked examples of over- and under-expansion
