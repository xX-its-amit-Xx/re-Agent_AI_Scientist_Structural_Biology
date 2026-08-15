---
name: cross-domain-analogy
description: >-
  Stage 0. Find mechanisms in unrelated fields — quantitative finance,
  cybersecurity, art, ecology, logistics, sport — that transfer to the current
  problem, and convert them into costed, falsifiable proposals a human accepts or
  denies. Sends scout subagents into foreign literature, forces each finding
  through a domain-neutral abstraction step, then grounds it against the problem's
  structure and files it in the decision ledger.
  Use when the in-field literature is exhausted or stuck, when a Stage 0 scouting
  pass produced open gaps, or when the user asks for creative or non-obvious
  approaches.
  Trigger on: "creative ideas", "what would X do", "think outside the field",
  "analogies from other domains", "we're stuck", "novel approach",
  or /cross-domain-analogy.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, Agent, WebSearch, WebFetch, Skill
---

# Cross-domain analogy

The literature bounds what the field already believes. To go past it you need a
prior from somewhere else — another discipline, a patent, a trade practice. This
skill industrialises that: scout foreign domains for *mechanisms*, abstract them
until the source domain is invisible, then test whether our problem has the
structure the mechanism requires.

The failure mode is obvious and worth naming: analogies are cheap, and an agent
asked for creativity will produce forty puns. Everything below exists to make the
output small, concrete, and falsifiable instead.

## Guard rails

- **NEVER let an analogy count as domain evidence.** It is `SourceType.ANALOGY`,
  it must name its `source_domain`, and it caps a finding at `speculative`. The
  contract enforces this. An analogy is a reason to run an experiment, never a
  result — and never a citation.
- **NEVER execute a proposal without an `ACCEPTED` ledger entry.** Check
  `DecisionLedger.is_accepted(id)`. The user decides; you propose.
- **Abstract before mapping.** Write `AnalogyCard.mechanism` so a reader cannot
  tell which domain it came from. If you cannot, you have found a surface
  resemblance ("proteins fold, origami folds") rather than a mechanism, and it
  will not transfer. The contract rejects a mechanism that merely restates the
  source practice.
- **Every card needs a `structural_precondition`** — what must be true of a
  problem for the mechanism to help. This is the field that makes the analogy
  *checkable*, and it is where most candidates die. That is the point.
- **Cap the output.** Ten well-grounded proposals beat forty. A triage sheet a
  human will not read has failed regardless of what is on it.
- **Search the target field for prior art before claiming novelty.** Very often
  the analogy has already been imported under a different name, which is good news
  — it becomes `EMERGING` with citations instead of `TRANSFERRED` with a guess.

## Workflow

### Step 1 — Take the gaps as input, not the whole problem

Run this **after** `pipeline-space-scouting`, and feed it that stage's
`handoff.payload.open_gaps` — the questions the in-field literature does not
answer. Without them the scouts free-associate and you get forty puns.

Restate each gap as a **structural** problem, stripped of domain vocabulary. This
restatement is the query the scouts actually search against, and its quality
determines everything downstream. For example:

> *Domain form:* "Our confidence scores can't identify which predicted poses are
> correct."
>
> *Structural form:* "We must rank candidates by expected quality using only
> self-reported confidence from the generators that produced them, with no ground
> truth available, where generators have correlated errors."

The second form is searchable in six other fields. The first is not.

### Step 2 — Fan out one scout per domain

Spawn subagents in parallel, one per domain, each returning `AnalogyCard` JSON.
Pick domains by *structural affinity to the restated gap*, not by novelty for its
own sake. A starter map — see
[domain-map.md](reference/domain-map.md) for the full version:

| Domain | Structurally good at |
|---|---|
| Quantitative finance | ranking under uncertainty, ensembles, regime detection, backtest overfitting, risk of ruin |
| Cybersecurity | adversarial validation, detection under base-rate imbalance, defence in depth, canaries, red-teaming |
| Ecology / evolution | diversity vs efficiency, niche partitioning, robustness, invasion dynamics |
| Logistics / operations | scarce-resource scheduling, queueing, bottleneck theory, inventory under demand uncertainty |
| Art / design / music | composition under constraint, variation and theme, deliberate imperfection, revision workflow |
| Sport analytics | small-sample evaluation, opponent-adjusted rating, selection vs development |
| Manufacturing / QC | tolerance stacking, statistical process control, acceptance sampling, failure-mode analysis |
| Epidemiology | confounding, sampling bias, surveillance design |
| Information retrieval | relevance ranking, rank fusion, evaluation without complete labels |
| Law / forensics | evidence standards, chain of custody, burden of proof, adversarial testing |

Give every scout the same instruction set: find *practices with mechanisms*, not
metaphors; cite real sources from that domain; and fill
`structural_precondition` honestly. Tell them explicitly that returning **zero**
cards is an acceptable and useful answer — otherwise they will invent.

### Step 3 — Abstract, then ground

For each card, in this order:

1. **Abstract.** Rewrite `mechanism` in domain-neutral language. Delete every noun
   specific to the source domain. If nothing survives, discard the card.
2. **Check the precondition against our problem.** Does our problem actually have
   the structure the mechanism needs? Use the knowledge graph and the Stage 0/1
   reports as the evidence, and answer with specifics.
3. **Search for prior art in the target field.** Invoke `literature-harvest` on the
   abstracted mechanism using target-field vocabulary. Three outcomes:
   - already standard here → `ESTABLISHED_PRACTICE`, drop it, note we should just do it
   - tried recently here → `EMERGING`, cite it, and read what happened
   - genuinely absent → `TRANSFERRED`, and now the analogy is load-bearing
4. **Name the mutation.** Which pipeline step, skill, or parameter changes? "The
   whole pipeline" is not an acceptable answer and the contract rejects it.

Discard aggressively here. A 70 % discard rate at this step is healthy.

### Step 4 — Cost it and write the kill criterion

Each surviving card becomes a `Proposal` with a falsifiable `prediction`, a
`kill_criterion`, a `measurable_on` metric, an effort/cost estimate, and the
credit pools it would consume.

The kill criterion is not a formality. In the reference pipeline, a
pre-committed transitive rejection rule — "if the cheap version of this signal
fails validation, the expensive DFT version is cancelled unbuilt" — fired, and
saved 14 development hours with no further argument. Pre-register the consequence,
not just the test.

### Step 5 — Present the triage sheet and stop

```bash
reagent triage reports/<run-id>/stage0/proposals.json
```

Ordered cheapest-and-most-reversible first, because that is the order a human can
actually act on. Each entry shows the mutation, the prediction, the kill
criterion, the cost, and — for transferred ideas — the source mechanism and its
precondition, so the reviewer can judge the transfer rather than trusting it.

**Then stop.** Do not implement anything. Record verdicts:

```bash
reagent decide P-014 accept -m "cheap, reversible, and the precondition holds"
reagent decide P-015 reject -m "precondition fails: our errors aren't independent"
```

### Step 6 — Write the graph delta and the report

Analogy nodes go into the graph with `ORIGINATES_IN` edges to their `Domain` node
(the contract rejects an analogy without one) and `INSPIRES` edges to the
`PipelineStep` they would mutate. This makes the creative provenance permanently
auditable: six months later you can ask *why* the pipeline has a routing layer and
trace it to a card, a decision, and a person.

## What a good card looks like

```json
{
  "id": "analogy:information-retrieval/reciprocal-rank-fusion",
  "source_domain": "information retrieval",
  "source_practice": "reciprocal rank fusion of multiple retrieval systems",
  "mechanism": "When several scorers rank the same candidates on non-commensurable scales, combining their ordinal ranks is more robust than combining their raw scores, because ranks discard the miscalibration that makes scores incomparable.",
  "why_it_works_there": "Retrieval systems have wildly different score distributions; rank fusion consistently beats score fusion on TREC benchmarks.",
  "structural_precondition": "Multiple scorers must rank a shared candidate set, their score scales must be miscalibrated relative to each other, and their errors must be at least partly independent.",
  "citations": ["doi:10.1145/1571941.1572114"],
  "discovered_by": "cross-domain-analogy/information-retrieval"
}
```

Note what makes it good: the mechanism names *why* it works (discarding
miscalibration), and the precondition is checkable and includes the condition most
likely to fail here — error independence. In the reference case that condition
**did** fail: consensus across co-folding models was actively harmful because
agreeing models share correlated errors. The card would have been correctly killed
at Step 3, which is a success, not a waste.

## Anti-patterns

- **Metaphor mining.** "Protein folding is like origami." No mechanism, no
  precondition, no transfer.
- **Domain tourism.** Scouting ten exotic fields for novelty rather than picking
  fields with structural affinity to the actual gap.
- **Laundering.** Citing the analogy as though it were evidence about the biology.
  The contract blocks it; do not route around it by relabelling the source type.
- **Proposal spam.** Forty ideas with no cost estimates is work moved onto the
  human, not done for them.
- **Skipping the prior-art search.** Most good analogies have already been imported
  under another name. Finding that out is cheaper than rediscovering it, and turns
  a speculative proposal into a cited one.

## References

- [domain-map.md](reference/domain-map.md) — domains, what each is structurally good at, and where to search in them
- [abstraction-ladder.md](reference/abstraction-ladder.md) — worked examples of rewriting a practice into a mechanism
- [scout-prompt.md](reference/scout-prompt.md) — the exact subagent brief and output schema
