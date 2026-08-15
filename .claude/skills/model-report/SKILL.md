---
name: model-report
description: >-
  How to write, visualize, and validate the Model Report that every pipeline stage
  must emit. Covers the required structure, the evidence and confidence rules the
  validator enforces, what each stage is expected to show visually, and the handoff
  contract that lets the next stage build without reading your internals.
  Use whenever writing or reviewing a stage report, when a report fails validation,
  or when starting work on a stage.
  Trigger on: "write the report", "model report", "validate the report",
  "what goes in the report", "report failed validation", or /model-report.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
---

# Model Report

A stage that has not written a validated Model Report did not happen. The report is
not documentation of the work — it *is* the deliverable, because it is the only
thing the next stage reads.

## Guard rails

- **Downstream stages read reports, never your internals.** No stage may reach into
  another's directory, notebook, or dataframe. This is what lets three people work
  in parallel without coordinating on file layout.
- **Every `observation`, `benchmark`, `negative_result`, or `prior` finding must
  cite `Evidence` with a resolvable locator.** A claim the next agent cannot check
  is a claim it has to redo.
- **`established` needs two independent grounded sources, at least one of them
  reviewed or from a structured database.** Grey literature — blogs, forum threads,
  GitHub issues — is legitimate evidence and often the only record of a negative
  result, but it cannot carry `established` alone.
- **A cross-domain analogy caps a finding at `speculative`.** It is a reason to run
  an experiment, never a result.
- **Record negative results.** `FindingKind.NEGATIVE` is the highest-value output a
  stage produces and the thing the literature systematically omits. A stage that
  reports only wins is under-reporting.
- **Every stage must show its work.** `visuals` is required in practice, and
  `reagent report validate --strict` fails a report missing its stage's
  characteristic figures. See below.
- **An empty report must explain itself.** The contract rejects a report with no
  findings *and* no `limitations`. Silent empty reports break the chain.

## Structure

Write the report as you work, not at the end. The fields, in the order they matter:

**`executive_summary`** — what a reader needs if they read nothing else. Lead with
the outcome, not the method.

**`objective`** — what this stage was asked to do. If it drifted from the plan, say
so here rather than pretending it did not.

**`findings`** — the claims you will stand behind. One assertion per finding, in
plain prose, with `kind`, `confidence`, `evidence`, and a `data` payload so a
downstream agent can act without parsing your prose. Use `kg_nodes` to link a
finding to the graph nodes it touches, so the report and the graph stay in sync.

**`methods`** — one `MethodStep` per tool invocation, with parameters, call counts,
wall-clock, and cost. This is what makes a run replayable and costable. Record
failures too: `failed=True` with a `failure_note` is information.

**`visuals`** — a `VizBundle`, with `reading_order` set so the figures tell a story
rather than arriving in declaration order.

**`metrics`** — the headline numbers. Anything here should be readable off one of
your figures; `reagent report validate` warns about metrics no figure reads from,
because a number nobody can see is just an assertion.

**`handoff`** — the explicit contract with the next stage. The part a teammate reads
first, so keep it blunt: `ready`, a machine-readable `payload`,
`recommended_actions`, and `blocking_unknowns`. Set `ready=False` if the next stage
should not build on this yet — that is far more useful than a hedged summary.

**`limitations` and `open_questions`** — what you could not do, and what the
evidence does not settle. Open questions are the input to the next scouting pass and
to the cross-domain analogy engine, so write them as questions.

## Confidence, honestly

| Level | Means | Requires |
|---|---|---|
| `established` | multiple independent sources agree | ≥2 grounded locators, ≥1 non-grey |
| `supported` | one solid grounded source | ≥1 grounded locator |
| `tentative` | weak or indirect support | may rest on the agent's own reasoning |
| `speculative` | hypothesis, or analogy-derived | nothing, but say so |

The common error is inflation — writing `supported` because a claim feels right.
The validator catches the mechanical cases; the rest is discipline. When unsure,
drop a level and say what would raise it.

## What each stage must show

`EXPECTED_VIZ` in `reagent.contracts.viz` is the authority. In summary:

| Stage | Characteristic figures |
|---|---|
| 0 · Scouting | decision tree over the pipeline space; ranked method comparison |
| 1 · Literature | knowledge-graph ego view; axis-agreement heatmap; provenance chain |
| 2 · Biochem | 2D interaction diagram; pocket render; interaction-fingerprint heatmap |
| 3 · Prior | ensemble overlay; confidence-vs-accuracy scatter; multi-metric comparison |
| 4 · Optimization | 3D before/after; per-item delta scatter; ranked improvement bars |
| Synthesis | decision tree of the recommended pipeline; provenance chain |

Every `Visualization` needs a `question` phrased as a question, a `takeaway` stating
what it shows, `reads_from` naming the data artifacts, and `encoding` mapping visual
channels to data fields. Those four fields are what stop a figure being decoration.

## Validating

```bash
reagent report validate reports/<run>/<stage>/report.json          # warnings
reagent report validate --strict reports/<run>/<stage>/report.json # gate before handoff
```

`--strict` promotes missing visuals, missing handoff, unvisualized metrics, and
absent limitations from warnings to failures. Use it before advancing a stage and in
CI. The non-strict mode exists so an exploratory mid-stage run is not blocked.

## Common rejections, and the fix

| Rejection | Why it exists | Fix |
|---|---|---|
| `finding X is a observation and must cite at least one Evidence` | an unciteable claim cannot be checked | add a locator, or change the kind to `hypothesis`/`design_choice` |
| `cites only ungrounded evidence ... cap it at speculative` | stops an analogy being laundered into a fact | lower the confidence, or find domain evidence |
| `claims 'established' but cites fewer than two independent grounded sources` | one paper is not consensus | add a second source or drop to `supported` |
| `claims 'established' on grey literature alone` | a blog post is a claim, not a consensus | corroborate against a reviewed or database source |
| `question must be phrased as a question` | a figure that cannot state its question is decoration | write the question, or delete the figure |
| `takeaway restates question` | the reader needs the answer, not the prompt again | say what the figure shows |
| `maps N categories to colour alone` | past ~8 categories colour is not discriminable | group into families, or add a `secondary_channel` |
| `draws N elements with no clustering declared` | it will read as a hairball | filter, cluster, or aggregate, and declare it in `params` |
| `a report with no findings must populate limitations` | silent empty reports break the chain | say why nothing was found — that is a real result |
| `evidence.locator must be a resolvable identifier` | a blank locator is worse than none | use a DOI, PMID, PDB ID, accession, or repo-relative path |

## Writing style for the report itself

The report is read by a teammate who stepped away, and by a judge who has never
seen the project. Lead with the outcome. Spell out technical terms. Use complete
sentences rather than fragments and arrow chains. Do not invent shorthand and then
require the reader to remember it. A table is for short enumerable facts; put the
reasoning in prose around it.

Above all, be faithful. If a stage failed, say so with the evidence. If a step was
skipped, say that. Confidence you cannot defend is the one thing that makes the
whole pipeline worthless, because it makes every other number unverifiable too.
