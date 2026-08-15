# Status

Last updated 2026-08-15.

## What works right now

The contracts, the knowledge graph, the visualization layer, and the skill registry
are built and tested. You can run the whole chain on a fixture today:

```bash
uv venv .venv --python 3.12
uv pip install -e ".[dev,graph]"
./.venv/Scripts/python.exe -m pytest tests/ -q          # 48 tests
./.venv/Scripts/python.exe examples/seed_demo_graph.py  # graph + interactive figure
./.venv/Scripts/python.exe examples/seed_demo_report.py # full Model Report + HTML
```

That produces `docs/reports/stage1-demo.html` — one self-contained 600 KB file with
an embedded interactive graph, two SVG charts, and six findings each carrying inline
citations. It is the shape every stage's output should take.

| Component | State |
|---|---|
| `ProblemSpec` — target/domain/metric/axes | working, four domain profiles registered |
| `ModelReport` + validators | working, `--strict` gate implemented |
| `GraphDelta` + JSONL store + SQLite query layer | working, 30 predicates all type-checked |
| `DataRef` / `FetchPlan` — discover now, fetch later | contracts working; the fetcher itself is not written |
| `Proposal` / `AnalogyCard` / `DecisionLedger` | working, gate enforced in code |
| Interactive graph renderer (Cytoscape.js, inlined) | working, validated headlessly |
| SVG charts (bar, heatmap, histogram, scatter) | working, no dependencies |
| Obsidian vault exporter | working — secondary view only, see below |
| Model Report HTML renderer | working |
| Skill registry + data-flow lint | working, 18 skills, no problems |

## Skills

| Skill | Stage | Owner | State |
|---|---|---|---|
| `ai-scientist` | shared | Amit | written |
| `pipeline-space-scouting` | 0 | Amit | written |
| `cross-domain-analogy` | 0 | Amit | written |
| `literature-harvest` | shared | Amit | written |
| `source-scout` | 1 | Amit | written |
| `data-materialize` | shared | Amit | written |
| `target-neighborhood` | 1 | Amit | written |
| `kg-visualize` | shared | Amit | written |
| `model-report` | shared | Amit | written |
| `compound-neighborhood` | 1 | Amit | stub |
| `esmc-sae-motifs` | 1 | Amit | stub |
| `pocket-anatomy` | 2 | **Denny** | contract-complete stub |
| `pocket-dynamics` | 2 | **Denny** | contract-complete stub |
| `structure-ensemble` | 3 | **Sumer** | contract-complete stub |
| `confidence-selection` | 3 | **Sumer** | contract-complete stub |
| `template-and-finetune` | 3 | **Sumer** | contract-complete stub |
| `medchem-pass` | 4 | Amit | stub |
| `dock-and-minimize` | 4 | Amit | stub |

"Contract-complete stub" means the interface is fixed and documented: inputs,
outputs, guard rails, required figures, and the traps that have already cost a real
pipeline points. Replace the body; changing `meta.json`'s `produces` keys changes
someone else's contract, so say so out loud first.

## What is not built yet

**The fetcher.** `DataRef` and `FetchPlan` are complete contracts and
`data-materialize` documents the workflow, but nothing downloads a file yet. Needed
before Stage 2 can read an assay table.

**A provenance-chain figure.** The one characteristic Stage 1 figure with no
renderer, which is why the demo report fails `--strict`. It should show a claim,
its evidence, and its sources as a small directed graph.

**GraphML export.** `kg-visualize` documents it for Gephi and Cytoscape desktop; the
writer is not implemented. The Obsidian exporter is.

**A real literature harvest.** Every number in `kg/demo/` is an illustrative
placeholder, flagged as such in the data and in the report. Running
`literature-harvest` and `source-scout` for real is the next substantive step.

**Stage 0 has never been run end to end.** The skills are written and the contracts
are tested, but no scouting pass has produced a real `ProposalSet` yet.

## Known risks

**ChimeraX is installed nowhere in this environment, and its offscreen rendering is
Linux-only.** This is the largest environment risk in the plan. Stage 2's figures
depend on it, and the route is a user-space install on the Explorer cluster relying
on ChimeraX's bundled software renderer. **Validate offscreen rendering on a compute
node before building on it.** Details and fallbacks in
`.claude/skills/pocket-anatomy/reference/interaction-toolchain.md`.

**Paperclip cannot search patents**, despite its own help text listing them as a
source. Patents route through `source-scout` and WebSearch instead. Several other
documented Paperclip flags also do not behave as documented — see
`.claude/skills/literature-harvest/reference/paperclip-cli.md` before scripting
against it.

**ProLIF requires Python 3.13 or below** and fails when driven from a notebook or
stdin. PLIP fails on every ligand with the pip openbabel wheel. Both have documented
workarounds; neither is obvious from the error.

**No Paperclip routines are enabled on this account**, so `paperclip routines route`
matches nothing and there is no trigger registry to script against. Re-check before
assuming otherwise.

## Decisions worth knowing about

**Obsidian is not the primary graph view.** It was evaluated properly and rejected:
its link model has nowhere to store a per-edge number, so edge weight is
unrepresentable, and the one maintained plugin that does typed edge colours tops out
around 600 nodes against our 500-5,000. It ships as a secondary reading interface
because the exporter is nearly free. Full evaluation in
`.claude/skills/kg-visualize/reference/obsidian-export.md`.

**There is no `reagent run` command.** The CLI owns typed artifacts — scaffolding,
validating, rendering, querying, gating. An agent owns execution by invoking skills.
A `run` command would have to encode the scientific judgement that is the point of
the skills.

**Charts are hand-rolled SVG, not matplotlib.** No stage should need a plotting
stack to satisfy strict validation, and SVG is smaller than base64 PNG, stays sharp,
and follows the report's theme.

**Nine predicate families, at most seven visible at once.** Colour encodes the
family rather than the predicate because roughly 30 predicates cannot be
distinguished by colour; dash pattern separates predicates within a family. Evidence
and data families are hidden by default because they would otherwise bury the
science.

## Next up

1. Run a real Stage 0 scouting pass on an actual challenge brief and produce the
   first `ProposalSet` for human triage.
2. Implement the fetcher in `data-materialize`.
3. Run `literature-harvest` and `source-scout` for real and replace the fixture
   graph with measured edges.
4. Build the provenance-chain figure so a stage can pass `--strict`.
5. Validate ChimeraX offscreen rendering on Explorer before Denny depends on it.
