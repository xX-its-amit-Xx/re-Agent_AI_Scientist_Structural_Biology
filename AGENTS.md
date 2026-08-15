# Working in this repo

Read this before starting a stage. It is short on purpose.

## The one rule

**Stages communicate through validated `ModelReport` JSON and the knowledge graph.
Nothing else.** No stage reads another stage's notebooks, dataframes, or scratch
files. That constraint is the only reason three people can build five stages in
parallel without a daily sync.

## Starting your stage

1. Read your stage's SKILL.md under `.claude/skills/`. If it is a stub, its
   interface is already fixed — replace the body, keep `meta.json`'s `consumes` and
   `produces` keys. Changing those keys changes someone else's contract, so say so
   out loud first.
2. Read `.claude/skills/ai-scientist/reference/pxr-case-study.md`. It reverse-
   engineers a real rank-2/50 entry in a blind structure-prediction challenge and
   records what was refuted as well as what won. Most of the traps you are about to
   hit are named there with numbers attached.
3. Read `.claude/skills/model-report/SKILL.md` for what you owe downstream.
4. `reagent skills list --stage <your-stage>` to see what you can call.

## Setup

```bash
uv venv .venv --python 3.12
uv pip install -e ".[dev,graph]"
./.venv/Scripts/python.exe -m pytest tests/ -q        # 34 tests, should be green
./.venv/Scripts/python.exe scripts/bootstrap_skills.py
./.venv/Scripts/python.exe -m reagent.cli skills check
```

Optional extras when you need them: `.[chem]` for RDKit and pandas, `.[struct]` for
Biopython, MDAnalysis, and ProLIF. They are extras so a teammate who only needs the
contracts is not waiting on a scientific stack.

The demo end-to-end, which is the fastest way to see the shape of things:

```bash
./.venv/Scripts/python.exe examples/seed_demo_graph.py   # seeds a graph and renders it
```

## Nothing is hardcoded to a target or a domain

This is the constraint people break first. The target may be a protein, a protein
family, a compound library, or an assay endpoint. The domain may be structural
biology, DNA-encoded-library machine learning, ADMET, or protein design. All of it
arrives in a `ProblemSpec`:

```python
from reagent.contracts import ProblemSpec
spec = ProblemSpec.load(Path(f"reports/{run_id}/problem.json"))
target = spec.primary_target        # never a literal
axes   = spec.required_axes()       # never a hardcoded list of similarity types
```

Even "what counts as similar" is a parameter: similarity axes are declared per
domain in `src/reagent/domains/__init__.py`. If your domain needs an axis that does
not exist, register a profile there — do not special-case it inside a stage.

PXR appears throughout as the *reference example* because we have a real,
well-documented pipeline for it. It is an instance, not an assumption.

## Discovery and download are separate

Stage 1 records **where** data lives — a `Dataset` node carrying a `DataRef` with
the URL, format, size, licence, access mode, what it measures, and which graph
entities it covers. It downloads nothing.

Your stage fetches what it needs, when it needs it, via `data-materialize`: query
the graph, build a costed `FetchPlan` with a stated purpose, review the total size,
then download. See `.claude/skills/source-scout/reference/lazy-data.md`.

`data/cache/` is gitignored. The graph is the index; the cache is disposable.

## The contracts will reject things, on purpose

Each validator corresponds to a specific way an LLM writing science goes wrong:

- An `observation` finding with no `Evidence` — unciteable, so uncheckable.
- A finding above `speculative` whose only support is a cross-domain analogy.
- `established` on one source, or on grey literature alone.
- A `Visualization` whose `question` is not a question.
- More than eight categorical colours with no redundant channel.
- A `GraphDelta` with a dangling edge endpoint, or an `Analogy` node that does not
  name its source domain.
- A `Proposal` claiming novelty with no prior-art search recorded.
- A `DataRef` needing an API key with no `fetch_hint`.

If a validator blocks you, the fix is almost never to route around it. It is
usually telling you the claim is weaker than you wrote it.

## Spending credits

Stages 0, 1, and most of 2 are free — literature, web, structured databases, and
local computation. Stage 3 is where real money goes.

Before spending a metered credit pool (Boltz, Modal, Tamarind, OpenProtein, AF3):
estimate the cost, write it into a `Proposal`, and get an `ACCEPTED` verdict in the
ledger. Then record actual spend in `MethodStep.cost_usd` and `MethodStep.credits`.

```bash
reagent decide status P-014          # exit 0 only if accepted
reagent decide P-014 accept -m "why" --by <your-name>
```

The ledger is append-only. To change your mind, append a superseding decision; the
reversal trail is itself useful evidence.

## Before you hand off

```bash
reagent report validate --strict reports/<run>/<stage>/report.json
reagent kg audit                     # edges claiming confidence with no citation
reagent kg stats                     # cited_edge_fraction should be above ~0.6
reagent skills check                 # your declared consumes/produces still line up
./.venv/Scripts/python.exe -m pytest tests/ -q
```

`--strict` is the gate. It fails a report missing its stage's characteristic
figures, missing a handoff, missing limitations, or carrying headline metrics that
no figure reads from.

## Visualization is not optional

Every stage must show what happened under the hood. This is a deliberate
differentiator, not polish: the usual AI-pipeline output is a number and a
paragraph, with no way to see whether either is real.

A figure needs four things or it does not count: a `question` phrased as a
question, a `takeaway` saying what it shows, `reads_from` naming its data, and an
`encoding` mapping visual channels to data fields. `EXPECTED_VIZ` in
`reagent/contracts/viz.py` lists what your stage should produce.

Output must be self-contained — the publish target blocks every external host, so
inline everything and vendor third-party JavaScript under `assets/vendor/`
(`reagent assets fetch`).

## Conventions

- **Graph node ids are namespaced**: `uniprot:O75469`, `pdb:1M13`,
  `chembl:CHEMBL432657`, `zenodo:10.5281/...`. The contract enforces it so that two
  agents discovering the same entity produce the same node.
- **One predicate per similarity axis.** A generic `SIMILAR_TO` destroys the ability
  to ask a precise question, which is the whole reason for a graph.
- **Edges accumulate metrics.** The store merges `attrs` on a repeated triple, so
  add every metric you measured. Disagreement between metrics is a finding.
- **Scores are normalised within their axis** using `AxisSpec.score_range`.
- **Skill directory name == frontmatter `name` == registry key.** All lowercase,
  hyphenated. `reagent skills index` fails otherwise.
- **SKILL.md stays under 500 lines**; detail goes in `reference/`, linked from the
  body so it is loaded only when needed. Reference links must resolve —
  `reagent skills index` checks.
- **Two files describe a skill**: `SKILL.md` (portable, harness-standard) and
  `meta.json` (this project's pipeline metadata). `skills/registry.json` is
  generated; never hand-edit it.

## Things that have already cost someone points

From the reference case study, so you do not have to learn them the expensive way:

- A prior that helps one subpopulation can **invert sign** on another. Always report
  a prior's domain of validity, not just the prior.
- Cross-model consensus can be *actively harmful* because agreeing models share
  correlated errors. Use ensemble diversity to widen a candidate pool, not to vote.
- A learned selector trained on a few dozen ground-truth examples will overfit. A
  ±0.05 win on 50 items is noise.
- Letting an agent freely redraw a molecular pose took one prediction from 3.88 Å to
  24.63 Å. Constrain generative edits.
- Submission mechanics — file format, residue naming, connectivity records — have
  decided real leaderboards. Treat them as `FindingKind.CONSTRAINT`.
- Pre-register the kill criterion *and its consequence*. In the reference case a
  pre-committed transitive rejection ("if the cheap version fails, the expensive
  version is cancelled unbuilt") fired and saved 14 hours with no argument.
