---
name: pipeline-space-scouting
description: >-
  Stage 0. Map the space of pipelines that have been tried for a computational
  challenge before designing a new one: what the state of the art is, what
  actually gets used in practice, what the known failure modes are, and which
  baselines must be beaten. Produces a method landscape, a benchmark table, and
  a failure-mode catalogue as a Model Report plus knowledge-graph nodes.
  Use when starting a new challenge, onboarding to an unfamiliar problem class,
  or asking whether an approach has been tried.
  Trigger on: "how has this been done before", "state of the art", "scope the
  problem", "what's the baseline", "has anyone tried", "prior art",
  or /pipeline-space-scouting.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, Agent, WebSearch, WebFetch, Skill
---

# Pipeline-space scouting

Before designing a pipeline, find out what the field already knows — including
what it has quietly failed at. You are writing the document you wish you had on
day one: **not** a literature review of the biology (that is Stage 1), but a
review of *the methods people point at this class of problem*.

## Guard rails

- **Separate "published" from "used".** Papers report bests; practitioners report
  defaults. A method that wins benchmarks but nobody runs is a signal about
  cost or fragility, and you must record which of the two you found.
- **Hunt for failure modes explicitly.** They are systematically under-published.
  Look in: limitations sections, GitHub issues, challenge post-mortems, reviewer
  comments on preprints, community forums, and the gap between a paper's
  benchmark and its leaderboard performance. Emit these as
  `FindingKind.NEGATIVE` and `Predicate.FAILS_ON` edges.
- **NEVER report a benchmark number without its evaluation set.** "0.56 LDDT-PLI"
  is meaningless without knowing on which ligands, with what pocket definition,
  and whether templates were allowed. An uncomparable number is worse than none.
- **Do not rank methods you have not costed.** Include compute, licence, and
  wall-clock. A method the team cannot run is not a candidate.
- **Stay in the free tier.** This stage is literature and web only. It must not
  spend Boltz/Modal/Tamarind credits.

## Workflow

### Step 1 — Frame the problem class, not the instance

Write one sentence of the form:

> *Given {inputs}, predict {output}, scored by {metric}, where {what is withheld}.*

Then name the problem class it belongs to (blind protein-ligand complex
prediction; affinity ranking; pose selection; ADMET regression; binder design).
Scout the **class**, because that is where the transferable methods live. A
challenge about PXR is an instance of blind co-folding, and almost everything
useful was learned on other targets.

### Step 2 — Fan out across evidence modalities

Different modalities surface different methods; running only one is the main way
this stage goes shallow. Spawn one subagent per modality, in parallel, each
returning `MethodCard` JSON (schema in `reference/method-card.md`):

| Modality | What it uniquely surfaces | Tool |
|---|---|---|
| Peer-reviewed literature | validated methods, ablations | `paperclip`, `literature-harvest` |
| Preprints | the current frontier, 6-18 months ahead | bioRxiv/arXiv, `paperclip` |
| Challenge post-mortems | what actually won, and the tricks | WebSearch: CASP, CACHE, PoseBusters, OpenADMET, D3R, CAPRI |
| Code & issues | real failure modes, defaults, cost | GitHub repos + issue trackers, via `source-scout` |
| Patents | industrial methods absent from papers | **WebSearch against Google Patents / Espacenet — Paperclip cannot search patents**, despite its help text listing them. Delegate to `source-scout`. |
| Practitioner talk | what people default to | forums, blogs, Substack, conference recaps — `source-scout` |
| Benchmark papers | honest head-to-head comparisons | `paperclip` |

For everything the indexed full-text corpora cannot see — patents, repositories,
grey literature, competition write-ups, and datasets — invoke **`source-scout`**
rather than reimplementing it here. It also records datasets as graph nodes with
metadata and a URL, which is how a later stage finds them without downloading
anything now.

Prefer benchmark and post-mortem sources over method papers when they disagree.
A method paper is written by people who want it to work.

### Step 3 — Build the method landscape

For each method, fill a `MethodCard`: what it does, its inputs, its reported
performance *with* evaluation set, its cost, its licence, its known failure
modes, what it is an alternative to, and who uses it.

Then write the landscape as a **decision tree over the problem's structure**, not
as a list. The useful artifact answers "given that our target has a large
flexible hydrophobic pocket and no close-homolog holo structure, which branch am
I on?"

Emit to the graph:

- `Method` nodes for each method, `PipelineStep` nodes for each pipeline position
  (sampling, templating, scoring, ranking, refinement).
- `Predicate.USED_IN` (method → step), `Predicate.OUTPERFORMS` with `{metric, delta,
  eval_set}`, `Predicate.FAILS_ON`, `Predicate.ALTERNATIVE_TO`.
- `Predicate.SUPPORTED_BY` to every `Paper` node. An uncited method node is a bug.

### Step 4 — Fix the baselines and the ceiling

Three numbers decide whether the project is worth doing:

1. **The trivial baseline** — what does the dumbest legitimate approach score?
   (nearest-homolog template transfer; docking into the apo structure.)
2. **The current best** — what does the leaderboard/SOTA score?
3. **The ceiling** — what would an oracle score given the same candidate pool?

The gap between 1 and 2 is the headroom. The gap between 2 and 3 tells you
whether to improve *generation* or *selection*, and that single distinction
reorganises the whole pipeline. If the oracle over your pool is far above SOTA,
you have a selection problem and should spend everything on the selector.

### Step 5 — Catalogue the failure modes

Produce a table: failure mode · which methods suffer · observable symptom ·
known mitigations · residual risk. Sort by how much of the metric it costs.

This table is what Stage 3 designs against, and it is the deliverable teammates
will actually reread.

### Step 6 — Write the Model Report

```bash
reagent report new --stage stage0_scouting --run-id <run-id> \
  --title "Pipeline space: <problem class>"
reagent report validate reports/<run-id>/stage0/report.json
```

Required content:

- `metrics`: `{trivial_baseline, current_sota, pool_ceiling, headroom, n_methods}`
- **an oracle-curve figure** reading from those metrics. `--strict` validation
  demands a figure for every headline metric, and the oracle curve is the one that
  earns its place: it is what tells the team whether to improve generation or
  selection. Compute the ceiling **in the graded metric**, not in a convenient
  proxy — the reference case reported its pool ceiling as a median RMSD while being
  graded on LDDT-PLI, which makes the two numbers non-comparable.
- `findings`: the landscape as `DESIGN_CHOICE` + `BENCHMARK` + `NEGATIVE` findings
- `handoff.payload`: `{recommended_architecture, candidate_methods, must_beat,
  failure_modes, open_gaps}`
- `open_questions`: what the literature does not answer. Hand these to
  `cross-domain-analogy` — an unanswered question in-field is precisely where an
  out-of-field mechanism is worth borrowing.

### Step 7 — Hand off to analogy scouting

Invoke `cross-domain-analogy` with the `open_gaps` list. The gaps are the input;
without them the analogy engine free-associates.

## Anti-patterns

- **Surveying instead of deciding.** Twenty methods with no branch structure is
  a reading list, not scouting. Always end on "therefore we are on branch X".
- **Chasing the newest model.** A month-old model with no independent evaluation
  is a risk, not an advantage. Record it; do not build on it without a fallback.
- **Ignoring submission mechanics.** Format validators, CONECT records, resname
  conventions, and scoring-server quirks have decided real leaderboards. Scout
  these too; they belong in `FindingKind.CONSTRAINT`.
- **Treating the metric as neutral.** Metrics have exploitable structure. Scout
  how the metric has been gamed, then decide deliberately how far to go.

## References

- [method-card.md](reference/method-card.md) — the JSON schema subagents must return
- [evidence-modalities.md](reference/evidence-modalities.md) — where to search per modality, with query templates
- [failure-mode-catalogue.md](reference/failure-mode-catalogue.md) — failure modes of computational prediction pipelines, domain-general, with a symptom lookup table
- [generation-vs-selection.md](reference/generation-vs-selection.md) — the oracle-gap diagnostic, worked through
