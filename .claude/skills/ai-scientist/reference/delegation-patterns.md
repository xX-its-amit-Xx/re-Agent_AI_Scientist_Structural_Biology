# Delegation patterns

Your context window is the scarcest resource in a pipeline-design run, and it is
the one thing no subagent can give back to you. A single broad literature sweep can
easily produce more raw text than the rest of the run put together, and once that
text is in your context it stays there, crowding out the synthesis you were
actually hired to do. So the rule is simple: **push breadth outward, keep judgement
inward.** A subagent reads forty sources and returns twelve fields; you read the
twelve fields.

Everything below is machinery for making that trade without losing information you
needed.

## When to delegate and when to do it inline

Delegate when the work is *wide* rather than *deep*: many methods, many domains,
many candidate datasets, many files to grep, many axes that do not depend on each
other. Delegate when the work is file-heavy — sweeping a repository for how a tool
is actually configured, or reading twenty GitHub issue threads — because the raw
material is bulky and the conclusion is small. Delegate when you can state the
output schema before the work starts, which is a good proxy for "this is a
retrieval task, not a decision".

Do it inline when the work is synthesis, when it requires comparing this stage's
result against the problem's structure, or when the decision is the deliverable.
Specifically, keep these to yourself: classifying the task type and reading the
metric's failure modes, choosing which branch of the method landscape the problem
is on, judging whether an analogy's `structural_precondition` actually holds for
this problem, writing the plan and its kill criteria, deciding what goes in
`handoff.payload`, and writing the synthesis report. Also keep anything that spends
metered credits, and anything that writes to the decision ledger, because those are
gated on a human and the gate has to be visible in one place.

The intermediate case is a whole stage you do not own. Delegate it, but delegate it
as a *stage*: the subagent runs the stage's skills, writes a validated
`ModelReport` to disk, and returns the report path plus a short card. You then read
the report. Do not let stage internals into your context — that is exactly what the
report contract exists to prevent.

A useful test before spawning: if you cannot write down what the agent returns,
you do not yet know what you are asking for, and the agent will fill the gap with
prose.

## Every subagent returns a structured card

Not prose. Ever. A subagent that returns three paragraphs has moved the reading
work to you and thrown away the machine-readability that makes merging cheap. A
subagent that returns JSON matching a schema you stated can be merged
mechanically, diffed against its siblings, counted, and dropped into a report
without rewriting.

State the schema in the brief, literally, as the JSON shape you want back. Require
every field explicitly and make the ones that may be unknown *nullable rather than
omissible* — an agent that is allowed to omit a field will omit exactly the hard
one. Ask for the locator or line range supporting each assertion as a required
field; requiring it measurably suppresses invention, because a fabricated number
has nowhere to point.

Two mechanical rules that save a lot of grief. First, give every sibling agent in
a fan-out the *same* schema, so the merge is a concatenation rather than a
reconciliation. Second, require a provenance field naming the agent (a
`discovered_by` or `asserted_by` slug like `cross-domain-analogy/logistics`), so
that when one card turns out to be wrong you can tell which scout produced it and
whether its siblings share the flaw.

## Anatomy of a subagent brief

A brief that omits any of these produces work you cannot use:

1. **The run id.** Everything the agent writes is keyed on it. Without it the
   agent invents a path and you lose the artifact.
2. **The upstream report paths, as paths.** Say `reports/<run-id>/stage0/report.json`
   and let the agent read it. Do not paste report contents into the brief; that is
   your context being spent on the agent's behalf.
3. **The graph path.** Normally `kg/`. State whether the agent may write to it.
   Usually the answer is no.
4. **Its skills, by name.** Read `skills/registry.json` and name the skills the
   agent should invoke, rather than describing the work and hoping it finds them.
   The registry is regenerated with `reagent skills index` and teammates add skills
   while you run, so route on the file rather than on memory.
5. **Its output schema.** The JSON shape, field by field, with nullability stated.
6. **Its scope boundary.** What it must *not* do: no metered credits, no ledger
   writes, no graph merges, no wandering into an adjacent axis.
7. **Its budget.** A rough cap on searches or tool calls, and a wall-clock
   expectation. Unbounded scouting is how a 20-minute task becomes an hour.
8. **The permission to return nothing.** See the section below; this is not
   optional politeness.
9. **Where to put bulk output.** A path under `reports/<run-id>/` for anything
   large, with only the summary card coming back through the return value.

Say once, explicitly, "return only the JSON card; write everything else to disk."
Agents default to narrating.

## Concurrency

Cap parallel subagents at **six to eight**. This is not arbitrary. Above that
range you start contending for the same rate-limited backends — Paperclip, web
search, structured-registry APIs — and the wall-clock gain flattens while the
failure rate rises. More importantly, you have to *read* every card that comes
back, so eight cards of twelve fields is already a substantial synthesis job, and
sixteen is one you will do badly.

If you have more than eight independent units of work, batch them: run six or
seven, merge, then decide whether the next batch is still worth running. Very
often the first batch answers the question and the second was never needed. That
decision is only available to you if you batch.

Launch a batch in a single message with multiple tool calls so they actually run
concurrently. Prefer a fresh agent over a fork for breadth work: a fork inherits
your entire context, which defeats the purpose of delegating in order to protect
it. Fork only when the agent genuinely needs the conversation so far.

## Merging structured results

Because every sibling returned the same schema, the merge is mechanical, and it
should stay mechanical:

- **Concatenate, then deduplicate on a stable key.** For graph work that key is
  `Edge.key`, the triple of source, predicate, and destination. For method cards it
  is the method id. Two agents finding the same thing is corroboration, so record
  both locators on the merged object rather than dropping one.
- **Do not average conflicting numbers.** If two scouts report different values for
  the same relation, that is a contradiction and contradictions are findings.
  Record both, with both locators, and either resolve it by reading the sources or
  emit it as an open question. Averaging destroys the only signal that something is
  wrong.
- **Validate every delta yourself before it touches the graph.** Call
  `delta.validate_referential_integrity(known_ids=store.node_ids())` and only merge
  on an empty problem list, or use `KGStore.merge(delta)` which does the same thing
  and refuses to write a delta with problems. Constructing a `GraphDelta` does not
  validate it and `write_jsonl` does not either, so an agent that writes JSONL
  directly has bypassed the only gate.
- **Attribute in the report.** Each merged card becomes one or more `Finding`s with
  the agent's slug in the evidence or in `MethodStep.skill`, so the provenance chain
  runs from the claim back to the agent that made it.
- **Count what came back empty.** Three scouts returning zero cards out of seven is
  information about the problem, and it belongs in `limitations` or
  `open_questions`. Silently dropping the empties makes the run look more
  productive than it was and hides the shape of the gap.

## Anti-patterns

**Spawning an agent per paper.** `literature-harvest` already fans out over a
corpus with `map --from <result-set> --worker structured-extraction -j 32`, which
does the same work an order of magnitude more cheaply and returns schema-conformant
output by construction. Delegate one agent *per sub-question* and let the batch
extraction tool fan out over documents inside it. The same logic applies anywhere a
tool already parallelises: your job is to fan out over questions, not over rows.

**Letting a subagent write to the graph.** A delta that reaches `nodes.jsonl`
without passing `validate_referential_integrity` can carry dangling endpoints,
unnamespaced ids, predicates used between illegal node types, or an `Analogy` node
with no `ORIGINATES_IN` edge — and because the files are append-only, cleaning that
up means rewriting history. Have the agent return the delta as JSON, or write it to
a staging path, and merge it yourself.

**Asking an open-ended question.** "Look into confidence scoring and tell me what
you find" returns an essay whose length is set by the agent's stamina rather than
by the problem. Ask for the fields you will use: which methods, on which evaluation
set, at what cost, with which reported failure modes, and where each number came
from.

**Letting each agent invent its own schema.** Then the merge becomes translation,
and you pay in context exactly what you delegated to save.

**Scouting without the gaps.** `cross-domain-analogy` takes
`handoff.payload.open_gaps` from `pipeline-space-scouting` as its input for a
reason: without them the scouts free-associate and you get forty puns. The same
holds for any scout — give it the specific unanswered question, restated
structurally, not the whole problem.

**Delegating the decision.** A subagent may propose; it may not accept. Nothing
outside the ledger authorises execution, and `reagent decide status <proposal-id>`
is the authority, not the conversation.

## Zero results is an acceptable answer

Say this in every scouting brief, in those words. An agent that believes it has
been sent to find something will find something, and what it finds when there is
nothing there is fabrication: a plausible method name, a DOI-shaped string, a
mechanism that sounds like it transfers. This is the most expensive failure mode in
the whole system, because a fabricated card is indistinguishable from a real one
until someone tries to use it, and by then it is in the graph being treated as
fact.

The fix is to make emptiness a success condition and to give it somewhere to go.
Tell the scout: returning `{"cards": [], "searched": [...], "why_empty": "..."}` is
a useful and complete answer, and a card you are not confident in is worse than no
card. Then require `searched` — the queries actually run — so an empty return is
distinguishable from a lazy one. In the reference case, negative results were the
highest-value output of the whole effort and the thing the literature omitted
entirely; the same is true of your scouts. `FindingKind.NEGATIVE` exists precisely
so an empty sweep has a place in the report.

Pair it with the honesty rule for numbers: an agent must never assert a value it
did not read. If extraction returns null, the assertion is either omitted or
written at `Confidence.SPECULATIVE` with an `illustrative` or `unmeasured` flag in
the edge attributes. Confidently-wrong numbers are worse than missing ones, because
everything downstream treats the graph as fact.

---

## Worked example 1: one scout per similarity axis (Stage 1)

The axes in a `ProblemSpec` are independent by construction, which makes them the
cleanest fan-out in the system. One agent per axis, all returning a `GraphDelta`
plus a coverage statement.

**Brief.**

> You are running the **`fold`** similarity axis for run
> `del-triazine-20260815`.
>
> Read `reports/del-triazine-20260815/problem.json` and use only the `AxisSpec`
> named `fold`: its `question`, its `predicate`, its `score_key`, its
> `score_range`, and its `methods` list in preference order. Do not substitute a
> different axis or a different predicate.
>
> Read `reports/del-triazine-20260815/stage0/report.json` for the failure modes
> already catalogued, so you do not rediscover them.
>
> Invoke the skill `target-neighborhood` and, for anything needing literature
> support, `literature-harvest`. The graph is at `kg/`; you may **read** it via
> `KGStore` but you must not write to it. Free tools only — no Boltz, Modal, or
> Tamarind credits.
>
> Use the first tool in `AxisSpec.methods` that is actually available and record
> which one. Every quantitative edge must be either measured or flagged
> `illustrative: true` at `Confidence.SPECULATIVE`. Normalise nothing across axes;
> report raw scores in this axis's own units.
>
> Write the full delta to
> `reports/del-triazine-20260815/stage1/deltas/fold.json` and return only the card
> below. Zero neighbours is an acceptable answer — say so and say why. Budget:
> about 25 tool calls.

**Output schema.**

```json
{
  "axis": "fold",
  "predicate": "SIMILAR_FOLD_TO",
  "delta_path": "reports/<run-id>/stage1/deltas/fold.json",
  "n_nodes": 0,
  "n_edges": 0,
  "method_used": "foldseek 9.427 --alignment-type 1",
  "method_unavailable": ["tmalign"],
  "score_key": "tm_score",
  "score_observed_range": [0.0, 0.0],
  "top_neighbours": [
    {"id": "uniprot:...", "score": 0.0, "locator": "computation:...", "note": null}
  ],
  "could_not_cover": ["..."],
  "domain_of_validity": "which subpopulation this axis's scores are meaningful for",
  "contradictions": [{"claim": "...", "locators": ["...", "..."]}],
  "why_empty": null
}
```

`could_not_cover` and `domain_of_validity` are the two fields people forget to ask
for and then most need. In the reference case a drug-like-trained similarity signal
inverted sign on the fragment half of the test set, confirmed four times
independently — a prior that helps one subpopulation and hurts another is worse
than no prior if it arrives unlabelled.

## Worked example 2: one scout per evidence modality (Stage 0)

Different modalities surface different methods, and running only one is the main
way scouting goes shallow. Peer-reviewed literature gives you validated methods and
ablations; preprints give the frontier six to eighteen months ahead; challenge
post-mortems give what actually won and the tricks; code and issue trackers give
real failure modes, defaults, and cost; patents give industrial methods absent from
papers; practitioner talk gives what people default to; benchmark papers give
honest head-to-head numbers.

**Brief.**

> You are the **code-and-issues** modality scout for run
> `del-triazine-20260815`, problem class: enrichment-to-activity prediction for
> DNA-encoded libraries.
>
> Read `reports/del-triazine-20260815/problem.json` for the task, the metric, and
> what is withheld. Your job is what the papers do not contain: default
> parameters, silent failure modes, unmaintained code, cost in wall-clock and
> hardware, and licence terms that would stop us using a method.
>
> Search GitHub and GitLab repositories, their issue trackers, and their release
> notes. Invoke `source-scout` for the sweep. Record any dataset you find as a
> `DataRef`-shaped entry with its URL, format, size, licence, and access level, and
> **do not download anything**. No credits, no graph writes.
>
> Return one `MethodCard` per method, plus dataset pointers. A method with no
> reported performance is still worth a card if the failure modes are documented —
> say `reported_performance: null` rather than guessing. Returning zero cards for
> this modality is acceptable and useful; if so, list the repositories you checked.
> Write long extracts to `reports/<run-id>/stage0/modality-code.md`.

**Output schema.**

```json
{
  "modality": "code_and_issues",
  "cards": [{
    "method_id": "method:<name>-<version>",
    "label": "...",
    "pipeline_position": "sampling | templating | scoring | ranking | refinement | other",
    "what_it_does": "...",
    "inputs_required": ["..."],
    "reported_performance": {"metric": "...", "value": 0.0, "eval_set": "..."},
    "cost": {"hardware": "...", "wall_clock": "...", "usd_estimate": null},
    "licence": "...",
    "maintained": true,
    "failure_modes": [{"symptom": "...", "condition": "...", "locator": "github:owner/repo#issue-412"}],
    "alternative_to": ["method:..."],
    "used_by": ["..."],
    "locators": ["github:owner/repo", "github:owner/repo#issue-412"]
  }],
  "datasets": [{
    "id": "hf:owner/name", "url": "...", "fmt": "parquet", "size_bytes": null,
    "access": "open", "licence": "...", "measures": ["enrichment"], "fetch_hint": null
  }],
  "searched": ["query or repo list actually checked"],
  "why_empty": null
}
```

Insist on `eval_set` inside `reported_performance`. A bare number is uncomparable
and worse than none: "0.56" means nothing without knowing on which items, with what
split, and whether templates or labels were allowed.

## Worked example 3: one cross-domain scout per foreign field

Send these only after in-field scouting has produced open gaps, and send each one a
gap restated *structurally* — stripped of domain vocabulary. The restatement is the
query the scout actually searches against, and its quality determines everything
downstream.

**Brief.**

> You are the **quantitative finance** scout for run `del-triazine-20260815`.
>
> The structural problem, which is all you need to know about our field: *we must
> rank candidates by expected quality using only self-reported confidence from the
> generators that produced them, with no ground truth available, where the
> generators have correlated errors.*
>
> Find **practices with mechanisms** in quantitative finance that address that
> structure — ranking under uncertainty, ensemble construction, regime detection,
> backtest overfitting, risk of ruin. Not metaphors. For each, write the mechanism
> in language that does not reveal which field it came from; if nothing survives
> that rewrite, discard it rather than shipping it.
>
> Cite real sources from that field with resolvable locators. Fill
> `structural_precondition` honestly — what must be true of a problem for this to
> help — including the condition most likely to fail. That field is what makes the
> card checkable, and a card that cannot be checked is worse than no card.
>
> Do **not** map anything onto biology, do not search our field, and do not write
> proposals. Return at most five cards; three good ones beat five padded. **Zero
> cards is an acceptable and useful answer** — if the field has nothing structurally
> relevant, return an empty list and the queries you ran.

**Output schema.** Field-for-field an `AnalogyCard`, so the merge into a
`ProposalSet` needs no translation:

```json
{
  "source_domain": "quantitative finance",
  "cards": [{
    "id": "analogy:finance/<mechanism-slug>",
    "source_practice": "what practitioners call and do",
    "mechanism": "domain-neutral, at least 40 characters, no source-domain nouns",
    "why_it_works_there": "at least 20 characters",
    "structural_precondition": "what must be true of a problem, at least 20 characters",
    "most_likely_to_fail": "which clause of the precondition is the fragile one",
    "citations": ["doi:...", "isbn:...", "url:..."],
    "discovered_by": "cross-domain-analogy/quantitative-finance"
  }],
  "searched": ["..."],
  "why_empty": null
}
```

The abstraction step, the precondition check against our problem, the prior-art
search in our own field, and the costing all happen **in the orchestrator or in the
`cross-domain-analogy` skill, not in the scout**. A 70% discard rate at that step
is healthy. The reference case is the illustration: a rank-fusion card would have
been correctly killed because our generators' errors were *not* independent —
consensus across co-folding models was actively harmful — and killing it cheaply is
the mechanism working, not failing.

## Worked example 4: one reviewer per review dimension

Before a synthesis report goes out, or before a stage is allowed to hand off, fan
out a red-team pass. One agent per dimension, each with a narrow mandate and a
verdict field. This is the pattern that catches the errors you cannot see because
you made them.

Dimensions worth running: **evidence integrity** (does every finding's confidence
survive the grounding rules, and does every locator resolve), **metric alignment**
(does the recommended architecture optimise the stated metric, including its known
caveats), **cost and feasibility** (is the plan runnable inside the budget,
deadline, and credit pools in the `ProblemSpec`), and **failure-mode coverage**
(does the design address the catalogued failure modes, or has one been quietly
dropped).

**Brief.**

> You are the **evidence-integrity** reviewer for run `del-triazine-20260815`.
>
> Read `reports/del-triazine-20260815/synthesis/report.json` and every stage report
> it cites. For each `Finding`, check three things: that its `confidence` is
> defensible under the contract's grounding rules (see
> `.claude/skills/ai-scientist/reference/contracts.md`), that every `Evidence`
> locator is resolvable and actually says what the finding claims, and that no
> `SourceType.ANALOGY` evidence is carrying a finding above `speculative`.
>
> Spot-check at most eight findings, chosen to include every `ESTABLISHED` one.
> Run `reagent report validate --strict` on each report and `reagent kg audit` on
> `kg/`, and report their exit status.
>
> You are reviewing, not fixing. Do not edit any file. Return the card below;
> "no issues found" is a legitimate verdict and you should not manufacture
> findings to justify the pass.

**Output schema.**

```json
{
  "dimension": "evidence_integrity",
  "verdict": "pass | pass_with_notes | block",
  "checked": {"n_findings_reviewed": 0, "n_locators_resolved": 0},
  "tool_results": {"report_validate_strict": "PASS | FAIL", "kg_audit": "PASS | FAIL"},
  "issues": [{
    "severity": "blocking | major | minor",
    "where": "report_id / finding_id / node_id",
    "what": "...",
    "evidence": "the locator or command output that shows it",
    "suggested_fix": "..."
  }],
  "not_checked": ["what this pass did not cover"]
}
```

The `not_checked` field is what stops a green card from being read as full
coverage. A reviewer that reports only what it looked at, and says what it did not,
is worth several that claim to have looked at everything.
