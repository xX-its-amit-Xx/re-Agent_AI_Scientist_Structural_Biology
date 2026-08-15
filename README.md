# reagent — an AI scientist that designs pipelines

Most "AI for science" tooling automates a pipeline someone else designed. This
project automates the **design step**: given a challenge brief, it scouts how the
problem has been attacked before, builds a knowledge graph of what the target
resembles, works out which biological or statistical priors are worth injecting,
and hands back a justified pipeline architecture — showing its work at every
stage.

It is built to be **target- and domain-agnostic**. The target might be a protein,
a protein family, a compound library, or an assay endpoint; the domain might be
blind complex prediction, DNA-encoded-library ML, ADMET regression, or binder
design. All of that arrives through a single `ProblemSpec` and is threaded
through the stages. Nothing downstream hardcodes a target.

Our reference exemplar — the pipeline we use to check that the scaffold is
capable of designing something that actually competes — is a rank-2/50 entry in
the OpenADMET PXR blind structure-prediction challenge (0.5640 LDDT-PLI). It is
reverse-engineered in
[`pxr-case-study.md`](.claude/skills/ai-scientist/reference/pxr-case-study.md).
**PXR is an instance, not an assumption.**

## The two ideas that make this different

**1. Every stage must show its work.** `Visualization` is a typed, validated field
of the Model Report, and `reagent report validate --strict` — the gate before any
handoff — fails a stage that is missing its characteristic figures. Each figure
must declare the *question* it answers, its *visual grammar* (which data channel
drives which visual channel), and the *artifacts* it was drawn from. A figure whose
question is not phrased as a question is rejected outright. This is a direct
response to the fact that AI pipelines are usually opaque: you get a number and a
paragraph, and no way to see whether either is real.

(Non-strict validation only warns, so a mid-stage exploratory run is not blocked.)

**2. Creativity is gated, not improvised.** Stage 0 deliberately sends subagents
into unrelated fields — quantitative finance, cybersecurity, art, ecology — to
find *mechanisms* that might transfer. Every such idea becomes a `Proposal` with a
falsifiable prediction, a kill criterion, and a cost, and it cannot be executed
until a human appends an `ACCEPTED` verdict to an immutable decision ledger.
Cross-domain evidence is a distinct `SourceType` that can never raise a finding
above `speculative` on its own. An analogy is a reason to run an experiment, not
a result.

## The stages

| Stage | Question | Owner |
|---|---|---|
| **0 · Scouting** | How has this problem been solved? What is the state of the art, and what is quietly broken? | Amit |
| **1 · Literature** | What resembles our target, on every axis that matters? | Amit |
| **2 · Biochem** | Which atoms actually matter, and does the pocket move? | Denny |
| **3 · Prior** | Which models, templates, samples, and scoring functions? | Sumer |
| **4 · Optimization** | Can we squeeze out the last tenth? | Amit |

Stage 0 is not preamble — it is where the architecture gets chosen, and in our
reference case the winning idea (ensemble + z-scored confidence selection +
failure-tail rescue) was an *architectural* insight, not a better model.

## Quickstart

```bash
uv venv .venv --python 3.12
uv pip install -e ".[dev,graph]"

reagent skills index                 # build the machine-readable skill registry
reagent problem new --domain structural_biology --task complex_prediction \
    --target uniprot:O75469 --name "OpenADMET PXR"
reagent report new --stage stage0_scouting --run-id <run-id> --owner amit
# ... an agent now invokes the Stage 0 skills and fills in the report ...
reagent triage reports/<run-id>/stage0/proposals.json
reagent report render reports/<run-id>/stage0_scouting/report.json
```

There is no `reagent run` command, on purpose. The CLI owns the typed artifacts —
scaffolding, validating, rendering, querying, gating — and an agent owns execution
by invoking skills. A `run` command would have to encode the scientific judgement
that is the entire point of the skills.

See the whole thing working on a fixture:

```bash
python examples/seed_demo_graph.py     # seeds a graph and renders the ego view
```

Or drive it conversationally in Claude Code, which is the intended mode:

```
/ai-scientist design a pipeline for <challenge>
```

## Architecture

```
.claude/skills/          THE DELIVERABLE — the skill ecosystem an agent routes over
  ai-scientist/            top-level orchestrator; plans stages, enforces gates
  pipeline-space-scouting/ Stage 0: map the method landscape
  cross-domain-analogy/    Stage 0: borrow mechanisms from other fields
  literature-harvest/      shared: indexed full text -> typed graph deltas
  source-scout/            Stage 1: patents, repos, Zenodo, Kaggle, grey literature
  data-materialize/        shared: resolve dataset pointers into local files
  target-neighborhood/     Stage 1: the similarity axes
  compound-neighborhood/   Stage 1: chemical space + domain shift
  esmc-sae-motifs/         Stage 1: learned structural motifs
  kg-visualize/            shared: the graph, made legible
  model-report/            shared: how to write and validate a stage report
  pocket-anatomy/          Stage 2 (Denny)
  pocket-dynamics/         Stage 2 (Denny)
  structure-ensemble/      Stage 3 (Sumer)
  confidence-selection/    Stage 3 (Sumer)
  template-and-finetune/   Stage 3 (Sumer)
  medchem-pass/            Stage 4
  dock-and-minimize/       Stage 4

src/reagent/
  contracts/             typed contracts — the only thing stages may not improvise
    problem.py             ProblemSpec: target, domain, metric, similarity axes
    report.py              ModelReport: the stage deliverable
    kg.py                  Node / Edge / GraphDelta, controlled predicate vocabulary
    viz.py                 Visualization: a figure must declare its question
    proposal.py            Proposal / AnalogyCard / DecisionLedger
    data.py                DataRef / FetchPlan: discover now, download later
  domains/               pluggable per-domain definitions of "what counts as similar"
  kg/                    JSONL source of truth + SQLite query layer
  viz/                   self-contained graph renderer + Obsidian exporter
  reports/               Model Report scaffolding and HTML rendering
  skills.py              registry generation and data-flow linting
  cli.py                 the `reagent` command

assets/vendor/           third-party JS, inlined at render time (never fetched)
data/cache/              materialised datasets (gitignored, disposable)

kg/                      nodes.jsonl, edges.jsonl — append-only, git-diffable
reports/<run-id>/        validated Model Reports per stage
decisions/ledger.jsonl   every accept/deny, immutable
```

### Why JSONL plus SQLite for the graph

The knowledge graph's source of truth is two append-only JSONL files, because
that is git-diffable, lets two agents write concurrently without a lock, and
keeps provenance attached to every single assertion. A SQLite cache is rebuilt
from them on demand purely for querying — stdlib only, no server, and deleting
`kg/kg.sqlite` is always safe. Downstream agents ask questions
(`store.neighborhood(target, axes)`) rather than solving graph-traversal puzzles.

### Why the contracts are strict

The validators reject things on purpose:

- A `Finding` of kind `observation` with no `Evidence` — an unciteable claim
  cannot be checked by the next agent.
- A `Finding` above `speculative` whose only support is a cross-domain analogy.
- A `Finding` claiming `established` with fewer than two independent sources, or
  resting on grey literature alone.
- A `Visualization` whose `question` is not a question, or whose `takeaway` merely
  restates it.
- A `ColorMap` assigning more than 8 categories to colour alone with no redundant
  channel — beyond that, colour is not discriminable.
- A `GraphDelta` written with a dangling edge endpoint, an edge whose predicate
  cannot connect those node types, or an `Analogy` node that does not name the
  domain it came from.
- A `Proposal` whose `mutates` names nothing specific, or that claims
  `UNPRECEDENTED` novelty with no prior-art search recorded.
- A `DataRef` behind a registration or API-key wall with no `fetch_hint`.

Each of these is a failure mode we expect from an LLM writing science, made
mechanically impossible rather than discouraged in a prompt.

Two things are deliberately *warnings* rather than errors, because making them
fatal would block legitimate mid-stage work: a report with no figures, and a
headline metric that no figure reads from. `--strict` promotes both, and `--strict`
is the gate before a handoff.

## For teammates starting a stage

Read [`AGENTS.md`](AGENTS.md), then your stage's SKILL.md. The short version: you
consume upstream `ModelReport` JSON and the knowledge graph, you emit one
validated `ModelReport` plus a `VizBundle`, and you never read another stage's
internals. `reagent report validate --strict <path>` is the gate.

## Status

Scaffold and contracts are in place; Stage 0 and Stage 1 skills are implemented,
Stages 2-4 are contract-complete stubs awaiting their owners. See
[`docs/STATUS.md`](docs/STATUS.md).
