# Contracts quick reference

This is the working reference for anyone — human or agent — who has to produce or
consume one of the typed contracts in `src/reagent/contracts/` without reading the
source. Every validation rule below was read out of the actual validators; where a
rule is documented in a field description but *not* enforced in code, that is
stated explicitly, because the difference matters when you are debugging a
rejection.

Two conventions run through all six contracts. First, anything that identifies an
entity is **namespaced** as `<namespace>:<accession>`, so two agents that discover
the same thing independently produce the same key. Second, anything that makes a
claim about the world carries a **resolvable locator**, so the next agent can check
it rather than redo it.

Nothing here is specific to a target or a domain. The examples deliberately rotate
between a protein target, a compound library, and an assay endpoint, because the
same objects carry all three.

Import everything from the package root, not the submodules:

```python
from reagent.contracts import (
    ModelReport, Stage, Finding, FindingKind, Confidence, Evidence, SourceType,
    Handoff, MethodStep, Artifact, InputRef,
    GraphDelta, Node, NodeType, Edge, Predicate,
    Visualization, VizBundle, VizKind, VizMedium, ColorMap,
    Proposal, AnalogyCard, ProposalSet, Decision, DecisionLedger, Novelty, Verdict,
    ProblemSpec, TargetEntity, AxisSpec, Metric, Budget, Domain, TaskType,
    DataRef, FetchPlan, Access, DataFormat, MeasurementKind,
)
```

---

## ProblemSpec

**What it is for.** The single object that makes the pipeline target- and
domain-agnostic. It names what is being predicted, how it is scored, what counts
as "similar" for this problem, and what the budget is. If a stage needs to know
something about the problem, it belongs here rather than in that stage's code.

**Who writes it.** The orchestrator, once, at the start of a run — either by hand
or by reading a challenge brief. `reagent problem new` scaffolds one and fills the
`axes` list from a domain profile in `reagent.domains`.

**Who reads it.** Every stage, every time. Stage 1 in particular dispatches over
`axes` rather than over a hardcoded list of similarity methods, which is why the
same skill serves a protein, a compound library, and an assay endpoint.

**Required fields.** `run_id`, `name`, `domain`, `task_type`, `targets` (at least
one `TargetEntity`), and `metric`. A `TargetEntity` requires `id`, `kind`, and
`label`; `kind` is a closed literal set (`protein`, `protein_family`, `complex`,
`compound`, `compound_library`, `endpoint`, `cell_line`, `organism`, `other`). A
`Metric` requires `name` and a `definition` of at least 20 characters. An
`AxisSpec` requires `name`, a `question` of at least 15 characters, `predicate`,
and `score_key`.

**Minimal valid example.**

```python
spec = ProblemSpec(
    run_id="del-triazine-20260815",
    name="DEL triazine hit identification",
    domain=Domain.DEL_ML,
    task_type=TaskType.HIT_IDENTIFICATION,
    targets=[TargetEntity(
        id="library:DEL-triazine-3cycle",
        kind="compound_library",
        label="Three-cycle triazine DEL",
    )],
    metric=Metric(
        name="PR-AUC",
        definition="Area under the precision-recall curve over held-out enrichment "
                   "labels, computed on the disynthon-disjoint split.",
        eval_set="held-out disynthon split, 12,400 members",
    ),
    axes=[AxisSpec(
        name="scaffold",
        question="Which library members share this member's Murcko scaffold?",
        predicate="SHARES_SCAFFOLD",
        score_key="scaffold_match",
    )],
)
```

**Validation rules and why each exists.**

| Rule | Why |
|---|---|
| `TargetEntity.id` must contain a colon | An unnamespaced id cannot key the knowledge graph, so two agents discovering the same target write two nodes and every downstream join silently halves. |
| `targets` must have at least one entry | A run with no target has nothing to be about; the failure should happen at spec time, not in Stage 1. |
| Every `AxisSpec.predicate` must be a value of `kg.Predicate` | An unregistered predicate is invisible to the SQLite query layer and to the graph renderer, so the axis would run, write edges, and then be unqueryable. |
| Axis `name` values must be unique | `spec.axis(name)` resolves by name; duplicates make the lookup silently ambiguous. |
| `Metric.definition` at least 20 characters | A metric name alone is not reimplementable, and every stage optimises against this. |
| `AxisSpec.question` at least 15 characters | An axis is a question plus machinery. A slug with no question cannot be checked for whether the machinery answers it. |

Two things are *not* enforced and are your responsibility. `Metric.eval_set` is
optional, but a benchmark number without its evaluation set is uncomparable —
`reagent problem new` will happily write `metric.name = "TBD"`, and no validator
stops you running a whole pipeline against a placeholder. And `AxisSpec.score_range`
defaults to `(0.0, 1.0)`; the renderer normalises edge width across axes using it,
so an axis whose score is not on that scale will silently misrepresent its own
strength relative to the others. That is the single most likely way this system
lies to a reader.

---

## ModelReport

**What it is for.** The stage deliverable. A stage that has not written a
validated `ModelReport` did not happen. Downstream stages read reports, never each
other's internals, which is what lets the Stage 2 and Stage 3 owners work without
agreeing on file layout.

**Who writes it.** Every stage, exactly once, including the final `Stage.SYNTHESIS`
report the orchestrator emits.

**Who reads it.** The next stage, the orchestrator, the renderer, and any teammate
picking the run up cold. `Handoff.payload` is the machine-readable part; treat it
as the actual interface and the prose as commentary.

**Required fields.** `report_id`, `run_id`, `stage`, `title`, an `objective` of at
least 10 characters, and an `executive_summary` of at least 30 characters.
Everything else defaults to empty, subject to the rules below.

**Minimal valid example.**

```python
report = ModelReport(
    report_id="stage0-scouting-20260815a",
    run_id="del-triazine-20260815",
    stage=Stage.SCOUTING,
    title="Pipeline space: DEL enrichment-to-activity prediction",
    objective="Map the methods, baselines, and failure modes for this problem class.",
    executive_summary=(
        "Nineteen methods across four pipeline positions; the trivial baseline is "
        "0.31 PR-AUC and published best is 0.58; count normalisation is the "
        "dominant failure mode."
    ),
    limitations=["No patent sweep was run; industrial methods are under-represented."],
)
```

That validates because `limitations` is populated. A report with neither
`findings` nor `limitations` is rejected outright.

**Findings are where most rejections happen.** A `Finding` requires `id`, `kind`,
a `statement` of at least 10 characters, and `confidence`. Its validator enforces
four separate rules:

1. **Certain kinds must cite evidence.** `OBSERVATION`, `BENCHMARK`, `NEGATIVE`,
   and `PRIOR` each require at least one `Evidence`. These are claims about the
   world, and an uncheckable claim about the world forces the next agent to redo
   the work. `HYPOTHESIS`, `CONSTRAINT`, `DESIGN_CHOICE`, and `RISK` may be
   asserted by the agent itself with no evidence at all, because they are the
   agent's own reasoning rather than a reading of a source.
2. **The anti-laundering rule.** If a finding cites evidence but *none* of it is
   grounded — meaning every source is `ANALOGY` or `EXPERT_PRIOR` — then it cannot
   exceed `SPECULATIVE`. This is the rule that stops a cross-domain analogy from
   becoming biology by being cited in a confident sentence. Note the exact shape:
   a finding with one grounded source plus three analogies is fine, and a finding
   with no evidence at all is a *different* case, governed by rule 1.
3. **`ESTABLISHED` needs two independent grounded sources.** Counted as distinct
   `locator` strings among grounded evidence, so citing the same DOI twice does
   not qualify.
4. **`ESTABLISHED` cannot rest on grey literature alone.** Grey means `BLOG`,
   `SOCIAL`, `DOCS`, `TALK`, or `COMPETITION`. These are legitimate evidence — a
   GitHub issue is often the only public record of a negative result — but
   `established` needs at least one reviewed or structured-database source. Use
   `supported` instead.

An `Evidence` requires `source_type` and a non-blank `locator`. If
`source_type` is `ANALOGY`, `source_domain` is additionally required, so an
analogy can never be mistaken for a domain source at a glance.

```python
Finding(
    id="F-SCOUT-004",
    kind=FindingKind.NEGATIVE,
    statement=(
        "Learned pose rescoring trained on fewer than sixty ground-truth complexes "
        "regressed against plain native-confidence ranking."
    ),
    confidence=Confidence.SUPPORTED,
    evidence=[Evidence(
        source_type=SourceType.COMPETITION,
        locator="https://example.org/openadmet-pxr-postmortem",
        title="Challenge post-mortem",
        excerpt="the learned scorer placed 32nd, the team's worst submission",
    )],
    data={"score": 0.4762, "rank": 32, "n_train_complexes": 53},
)
```

**Report-level rules.**

| Rule | Why |
|---|---|
| Finding ids must be unique within a report | `supersedes` and `decision_ids` reference findings by id; a duplicate makes the reference ambiguous. |
| A report must have at least one finding **or** at least one limitation | A silent empty report breaks the chain: the next stage cannot tell whether the stage found nothing or crashed. |

**What `reagent report validate --strict` adds.** The type-level model is
deliberately permissive so an exploratory run is not blocked, but the orchestrator
and CI use `--strict`, which promotes four warnings to failures:

- **Missing characteristic visuals for the stage.** `EXPECTED_VIZ` in
  `contracts/viz.py` states what each stage must show. Stage 0 owes a
  `decision_tree` and a `ranked_bar`; Stage 1 owes a `kg_subgraph`, a `heatmap`,
  and a `provenance_chain`; Stage 2 owes an `interaction_2d`, a
  `structure_render`, and a `heatmap`; Stage 3 owes an `ensemble_overlay`, a
  `scatter`, and `parallel_coords`; Stage 4 owes a `structure_3d`, a `scatter`,
  and a `ranked_bar`; synthesis owes a `decision_tree` and a `provenance_chain`.
  A report with `visuals=None` fails on all of them at once.
- **Metrics no figure reads.** `unvisualized_metrics()` checks each key of
  `metrics` against the concatenated `question`, `takeaway`, and `encoding` values
  of every visualization, lowercased, with underscores treated as spaces. This is
  substring matching, so a metric named `pool_ceiling` is satisfied by a figure
  whose question mentions "pool ceiling" and is *not* satisfied by one that only
  says "oracle gap". Name metrics in the words your figures use.
- **No `handoff`.** The next stage then has no contract to build against.
- **No `limitations`.** Every real stage has some, and a stage that reports only
  wins is under-reporting.

`Artifact.stamp(repo_root)` fills `sha256` and `bytes` from disk; use it so a
downstream reader can tell whether the file changed under them.

---

## GraphDelta, Node, Edge, Predicate

**What it is for.** The knowledge graph's write unit. A skill never edits the
graph in place; it emits a delta and the store merges it. The source of truth is
two append-only JSONL files, `kg/nodes.jsonl` and `kg/edges.jsonl`, which is
git-diffable and lets two agents write concurrently without a lock. The SQLite
cache at `kg/kg.sqlite` is rebuilt on demand and is always safe to delete.

**Who writes it.** Mostly Stage 1, plus `literature-harvest`, `source-scout`, and
Stage 0 (which writes `Method`, `PipelineStep`, `Analogy`, and `Domain` nodes).

**Who reads it.** Stages 2 through 4, through `KGStore` query helpers rather than
raw traversal: `neighbors`, `along_axis`, `neighborhood`, `promiscuity_ranking`,
`shared_motifs`, `family_members`, `evidence_for`.

**Required fields.** A `GraphDelta` requires `run_id` and `asserted_by`. A `Node`
requires `id`, `type`, `label`, and `asserted_by`. An `Edge` requires `src`,
`predicate`, `dst`, and `asserted_by`; `confidence` defaults to `TENTATIVE`.

**One predicate per similarity axis, always.** A generic `SIMILAR_TO` destroys the
point of building a graph: Stage 2 and Stage 3 ask different questions of
different axes and must filter on them separately. The controlled vocabulary is
the `Predicate` enum; adding one means adding it to `Predicate` *and* to
`PREDICATE_DOMAINS`.

**Namespaced id conventions.** Enforced loosely (only the colon is checked) and
documented strictly. Use the canonical external accession wherever one exists.

| Node type | Convention | Example |
|---|---|---|
| `Protein` | `uniprot:<accession>` | `uniprot:O75469` |
| `Structure` | `pdb:<id>` or `pred:<model>/<name>` | `pdb:1M13`, `pred:boltz2/PXR-x00035-seed3` |
| `Pocket` | `pocket:<structure-id>/<site>` | `pocket:pdb:1M13/LBD` |
| `Residue` | `residue:<structure-or-protein>/<position>` | `residue:uniprot:O75469/S247` |
| `Motif` | `motif:<source>/<id>` | `motif:sae/esmc-6b/L24-F3097`, `motif:prosite/PS51843` |
| `Compound` | `chembl:<id>` or `inchikey:<key>` | `chembl:CHEMBL1200973` |
| `Fragment` | `fragment:<scheme>/<id>` | `fragment:brics/BRICS-L3-0042` |
| `Assay` | `assay:<source>/<id>` | `assay:chembl:CHEMBL1613777` |
| `Dataset` | `<source>:<accession>` | `zenodo:10.5281/zenodo.1234567`, `hf:owner/name` |
| `Paper` | `doi:`, `pmid:`, `pmc:`, `patent:` | `doi:10.1016/j.cell.2004.01.008`, `pmc:PMC12690452#L45-L52` |
| `Method` | `method:<name>-<version>` | `method:boltz-2.1` |
| `PipelineStep` | `step:<position>` | `step:candidate-selection` |
| `Family` | `family:<name>` | `family:NR1I`, `family:nuclear-receptor` |
| `Analogy` | `analogy:<domain>/<mechanism>` | `analogy:finance/regime-switching-ensemble` |
| `Domain` | `domain:<field>` | `domain:quantitative-finance` |

The rows for `Protein`, `Structure`, `Pocket`, `Compound`, `Motif`, `Paper`,
`Family`, `Method`, `Analogy`, and `Domain` are the conventions written into the
`Node` docstring itself. The rows for `Residue`, `Fragment`, `Assay`, `Dataset`, and
`PipelineStep` are extensions of the same pattern rather than quotations from the
source; keep them consistent within a run and, if you settle on something better,
put it in the `Node` docstring so the next agent inherits it.

For `Paper` locators, prefer a line-anchored form such as
`pmc:PMC12690452#L45-L52`. An unanchored citation cannot be checked, and a claim
the next agent cannot check is a claim it has to redo.

**Minimal valid example.**

```python
delta = GraphDelta(
    run_id="del-triazine-20260815",
    asserted_by="target-neighborhood/scaffold",
    nodes=[
        Node(id="chembl:CHEMBL240", type=NodeType.COMPOUND,
             label="reference actives series", asserted_by="target-neighborhood/scaffold"),
        Node(id="inchikey:BSYNRYMUTXBXSQ-UHFFFAOYSA-N", type=NodeType.COMPOUND,
             label="library member 41-08-233", asserted_by="target-neighborhood/scaffold"),
    ],
    edges=[
        Edge(
            src="inchikey:BSYNRYMUTXBXSQ-UHFFFAOYSA-N",
            predicate=Predicate.SIMILAR_COMPOUND_TO,
            dst="chembl:CHEMBL240",
            attrs={"tanimoto": 0.41, "fp_type": "morgan-r2"},
            confidence=Confidence.SUPPORTED,
            evidence=[Evidence(source_type=SourceType.COMPUTATION,
                               locator="reports/del-triazine-20260815/stage1/fp_sim.csv")],
            asserted_by="target-neighborhood/scaffold",
        ),
    ],
)

problems = delta.validate_referential_integrity(known_ids=store.node_ids())
if not problems:
    store.merge(delta)          # returns [] on success
```

**Validation rules and why each exists.** Note the shape here: validation is a
*method that returns a list of problem strings*, not an exception. Nothing about
constructing a `GraphDelta` checks referential integrity, and `write_jsonl` does
not call the validator either. `KGStore.merge(delta, strict=True)` does call it,
and with `strict=True` (the default) it returns the problem list and writes
nothing, because a half-merged delta is much worse to debug than a rejected one.
If you write JSONL yourself, you have skipped the only gate.

| Rule | Where | Why |
|---|---|---|
| `Node.id` must contain a colon | `Node` field validator, raises | Unnamespaced ids do not collapse across agents, so the same entity becomes two nodes. |
| Every `Analogy` node needs an `ORIGINATES_IN` edge to a `Domain`, **in the same delta** | `validate_referential_integrity` | An analogy that does not name where it came from is indistinguishable from a domain finding six months later. |
| Every edge endpoint must exist, either in this delta or in `known_ids` | `validate_referential_integrity` | A dangling edge is a claim about a node nobody defined; it will never appear in a query result and never be noticed. |
| Predicates must respect `PREDICATE_DOMAINS` | `validate_referential_integrity` | `SIMILAR_SEQUENCE_TO` between two compounds is a type error dressed as data. |

One important limitation of that type check: it can only look up node types for
nodes present *in the delta*. If `src` or `dst` already lives in the graph and is
only referenced through `known_ids`, its type is not checked. If you are attaching
edges to pre-existing nodes, verify their types yourself with a query first.

Edges deduplicate on `Edge.key`, the triple `(src, predicate, dst)`. Two agents
asserting the same triple should merge rather than duplicate.

**Audit before handing off.** `reagent kg stats` reports `cited_edge_fraction`
and warns below 0.6, which means the harvest asserted more than it read.
`reagent kg audit` lists edges claiming `supported` or better with no citation at
all, and exits non-zero if there are any.

**Predicate families exist for the renderer.** There are roughly 27 predicates
and nine `PredicateFamily` values, but colour is only discriminable to about eight
categories. So colour encodes the family, a dash pattern distinguishes predicates
within a family, and the exact predicate is available on hover. The `EVIDENCE` and
`DATA` families are hidden by default because every claim links to at least one
source and they would bury the signal. Cite generously; it costs nothing visually.

---

## Visualization and VizBundle

**What it is for.** Making "show your work" structural rather than cosmetic. A
figure is a typed, validated field of the report, on the same footing as a
finding. The three load-bearing fields are `question` (what a reader can answer by
looking at it), `encoding` (which data channel drives which visual channel), and
`reads_from` (the artifacts it was drawn from, so any figure can be regenerated or
challenged).

**Who writes it.** Every stage, in its report's `visuals` field.

**Who reads it.** The renderer, the strict validator, and the human reviewing the
run. In practice the `question` field is read by people deciding whether to look
at the figure at all.

**Required fields.** `id`, `kind`, `medium`, `title`, `question` (at least 15
characters), `takeaway` (at least 15 characters), `path`, `reads_from` (at least
one entry), and `alt_text` (at least 20 characters).

**Minimal valid example.**

```python
viz = Visualization(
    id="V-SHIFT-01",
    kind=VizKind.DISTRIBUTION,
    medium=VizMedium.PNG,
    title="Domain shift: test items against the labelled set",
    question="How far does each test item sit from the nearest item with a measured label?",
    takeaway="The distribution is bimodal: 76 items above 0.55 and 108 below 0.30 Tanimoto.",
    path="docs/figures/domain-shift.png",
    reads_from=["reports/del-triazine-20260815/stage1/nn_similarity.csv"],
    encoding={"x": "nn_tanimoto", "y": "count", "fill": "subpopulation"},
    alt_text=(
        "Histogram of nearest-neighbour Tanimoto similarity with two clearly "
        "separated modes and the subpopulation split marked at 0.40."
    ),
    n_elements=184,
)
bundle = VizBundle(stage="stage1_literature", visualizations=[viz], reading_order=["V-SHIFT-01"])
```

**Validation rules and why each exists.**

| Rule | Why |
|---|---|
| `question` must end with a literal `?` | It is the test of whether the figure earns its place. A chart that cannot state its question is decoration, and this one cheap check removes most dashboard-filler. |
| `takeaway` must not equal `question` (case-insensitive, stripped) | Restating the question is not an answer. The takeaway is what the figure *shows*. |
| A `kg_subgraph` must name a `focal_node` | An ego view without a centre is a network dump, which is the classic unreadable graph figure. |
| `n_elements` above 5000 requires `params` to declare one of `clustered`, `aggregated`, or `filtered` | Past a few thousand marks a scatter or network needs aggregation, not more ink. The guard only fires if you populated `n_elements`, so populating it honestly is on you. |
| A categorical `ColorMap` with more than 8 entries in `mapping` requires a `secondary_channel` | Beyond roughly eight categories colour is not discriminable, and it fails first for colour-blind readers. Either group into families or add a redundant channel such as dash pattern or shape. |
| `VizBundle.reading_order` may only reference known visualization ids | A reading order pointing at a deleted figure silently drops it from the narrative. |

`ColorMap` also asks for `domain` on continuous scales. It is optional, but stating
it is what makes the scale auditable — without it a reader cannot tell whether
"dark blue" means 0.9 or 0.09.

`missing_expected(stage, bundle)` is advisory on its own; `--strict` is what turns
it into a gate.

---

## Proposal, AnalogyCard, Decision

**What it is for.** Making creativity gated rather than improvised. Every creative
suggestion becomes a `Proposal` with a falsifiable prediction, a stated cost, a
kill criterion, and an explicit `mutates` target; every human accept or deny
becomes an immutable `Decision` appended to `decisions/ledger.jsonl`. The
orchestrator refuses to execute a proposal with no `ACCEPTED` decision, which is
how "the user opts to accept or deny" lives in code instead of in a prompt.

An `AnalogyCard` is the intermediate object: a mechanism lifted out of a foreign
domain and described in domain-neutral terms *before* anyone maps it onto the
problem. Forcing that abstraction step is what stops the analogy engine producing
surface-level puns.

**Who writes them.** `cross-domain-analogy` and `pipeline-space-scouting` write
`ProposalSet`s and `AnalogyCard`s. Only a human — or a named `auto:<rule>` — writes
a `Decision`.

**Who reads them.** The orchestrator, before executing anything creative, through
`DecisionLedger.is_accepted(proposal_id)` or `reagent decide status <id>`. The
triage sheet rendered by `reagent triage` is what the human actually reads.

**Required fields.** `AnalogyCard` needs `id`, `source_domain`, `source_practice`,
a `mechanism` of at least 40 characters, `why_it_works_there` of at least 20, a
`structural_precondition` of at least 20, and `discovered_by`. `Proposal` needs
`id`, `title`, `target_stage`, `mutates`, a `rationale` of at least 30 characters,
a `prediction` of at least 20, a `kill_criterion` of at least 20, `measurable_on`,
`novelty`, and `proposed_by`. `Decision` needs `id`, `proposal_id`, `verdict`, a
non-blank `decided_by`, and a `rationale` of at least 10 characters.

**Minimal valid example.**

```python
card = AnalogyCard(
    id="analogy:information-retrieval/reciprocal-rank-fusion",
    source_domain="information retrieval",
    source_practice="reciprocal rank fusion of multiple retrieval systems",
    mechanism=(
        "When several scorers rank the same candidates on non-commensurable scales, "
        "combining their ordinal ranks is more robust than combining raw scores, "
        "because ranks discard the miscalibration that makes scores incomparable."
    ),
    why_it_works_there="Retrieval systems have wildly different score distributions.",
    structural_precondition=(
        "Multiple scorers must rank a shared candidate set, their scales must be "
        "miscalibrated relative to each other, and their errors must be at least "
        "partly independent."
    ),
    citations=["doi:10.1145/1571941.1572114"],
    discovered_by="cross-domain-analogy/information-retrieval",
)

prop = Proposal(
    id="P-014",
    title="Rank-fuse per-generator confidences instead of z-scoring them",
    target_stage=Stage.PRIOR,
    mutates="confidence-selection: the cross-model comparison step",
    rationale=(
        "Generator confidence scales are miscalibrated relative to each other and "
        "ordinal fusion discards that miscalibration."
    ),
    prediction="Rank fusion matches or beats z-scored argmax on the local validation set.",
    kill_criterion=(
        "If rank fusion loses by more than 0.05 on the local validation metric, "
        "abandon it and keep z-scored selection."
    ),
    measurable_on="median error on the 53-item local ground-truth validation set",
    novelty=Novelty.TRANSFERRED,
    derived_from_analogy=card.id,
    est_effort_hours=3.0,
    risk="low",
    proposed_by="cross-domain-analogy/information-retrieval",
)

pset = ProposalSet(
    run_id="del-triazine-20260815",
    generated_by="cross-domain-analogy",
    target_stage=Stage.PRIOR,
    proposals=[prop],
    analogies=[card],
)
```

**Validation rules and why each exists.**

| Rule | Why |
|---|---|
| `AnalogyCard.mechanism` must not restate `source_practice` verbatim | If the mechanism cannot be written without the source domain's nouns, it is a surface resemblance rather than a transferable mechanism, and it will not transfer. |
| `mechanism` at least 40 characters, `structural_precondition` at least 20 | The precondition is the field that makes the analogy *checkable* against the problem, and it is where most candidates correctly die. A one-liner cannot be checked. |
| `Proposal` with `novelty=TRANSFERRED` must set `derived_from_analogy` | A transferred idea whose source card is missing cannot be judged by the reviewer, only trusted. |
| `Proposal` with `novelty=UNPRECEDENTED` and empty `prior_art` must say so in `rationale` | The validator looks for the substring `searched` or `no prior art` in the lowercased rationale. Weak, deliberately: it forces you to state what search established the claim, since most "unprecedented" ideas were already imported under another name. |
| `ProposalSet` proposals may only reference analogies included in the same set | Ship the card with the proposal so the reviewer judges the transfer instead of taking it on faith. |
| `Decision.decided_by` must be non-blank | An unattributable accept is not a gate. Use a person's name, or `auto:<rule>` for gated automation. |

Three things are documented but **not** enforced, and are on you. `mutates` says
"'the whole pipeline' is not an acceptable answer" in its description, but no code
checks the string — a vague `mutates` will validate and then be unimplementable.
`kill_criterion` is only length-checked, not checked for being an observation.
And `est_cost_usd`, `est_effort_hours`, and `credits_needed` are all optional, so
an uncosted proposal validates fine; it just cannot be triaged, since
`ProposalSet.triage_order()` sorts by risk, reversibility, and effort and treats a
missing effort estimate as 999 hours.

**Ledger semantics.** The ledger is append-only JSONL. To change your mind, append
a new `Decision` with `supersedes` set to the old decision's id; the trail of
reversals is itself evidence. `DecisionLedger.current()` resolves by sorting on
`decided_utc` and keeping the last entry per proposal, so it is last-write-wins by
timestamp rather than by file order. `reagent decide <id> accept -m "why"` sets
`supersedes` for you and refuses to run without a rationale.

---

## DataRef and FetchPlan

**What it is for.** Separating dataset *discovery* from dataset *fetch*. Stage 1
records where data lives — URL, format, size, licence, what it measures, how to
fetch it — and downloads nothing. A later stage materialises only what it needs,
then writes `local_path`, `sha256`, and `retrieved_utc` back onto the graph node.

This is lazy for four concrete reasons. A broad Stage 1 sweep finds hundreds of
candidate datasets and downloading them all would cost tens of gigabytes to answer
questions about three. The metadata is what supports graph reasoning: "is there a
binding assay between this compound class and this receptor?" is answerable from
metadata alone. Fetch is the step that fails, and separating it means a dead link
degrades one node instead of aborting the harvest. And `retrieved_utc` plus
`sha256` pin exactly what was analysed, which a URL alone never does.

**Who writes them.** `source-scout` and `literature-harvest` write `DataRef`s onto
`Dataset` node `attrs` via `to_node_attrs()`. `data-materialize` builds the
`FetchPlan` and fills the materialisation fields.

**Who reads them.** Any stage that needs bytes rather than metadata, and the human
approving a fetch plan.

**Required fields.** `DataRef` needs `id`, `title`, `url`, and `discovered_by`.
`FetchPlan` needs `run_id`, `requested_by`, and a `purpose` of at least 15
characters.

**Minimal valid example.**

```python
ref = DataRef(
    id="zenodo:10.5281/zenodo.1234567",
    title="Enrichment counts for a three-cycle triazine DEL selection",
    url="https://zenodo.org/records/1234567",
    measures=[MeasurementKind.ENRICHMENT],
    fmt=DataFormat.PARQUET,
    n_records=1_240_000,
    size_bytes=310_000_000,
    entities={"targets": ["uniprot:O75469"], "libraries": ["library:DEL-triazine-3cycle"]},
    access=Access.OPEN,
    licence="CC BY 4.0",
    discovered_by="source-scout",
)

plan = FetchPlan(
    run_id="del-triazine-20260815",
    requested_by="data-materialize",
    purpose="Fit the count-normalisation baseline the Stage 0 report says we must beat.",
    datasets=[ref],
    max_total_bytes=2_000_000_000,
)
print(plan.summary())
```

**Validation rules and why each exists.**

| Rule | Why |
|---|---|
| `DataRef.id` must contain a colon | Same reason as node ids: the dataset becomes a graph node keyed on this. |
| `access` in `api_key`, `registration`, or `request` requires `fetch_hint` | Record how to get in *while you know*. Rediscovering an API call or a registration path months later is pure waste, and this is the field a later agent reads instead of guessing. |
| `local_path` set requires `retrieved_utc` | A cached file with no retrieval timestamp cannot be trusted as provenance — you cannot tell what version you analysed. |

`is_fetchable` is true only for `OPEN` and `API_KEY`; `FetchPlan.blocked()` returns
everything else so a human sees it rather than having it silently skipped.
`within_budget()` compares `total_bytes()` against `max_total_bytes`, treating
unknown sizes as zero — hence `unknown_size_count()`, which the summary prints so
"0.4 GB known, 31 of unknown size" cannot be mistaken for a small download. And
`fetch_error` is worth filling in: a dead link is a finding that stops the next
agent repeating the attempt.

---

## Common rejections and their fixes

| Message you will see | Cause | Fix |
|---|---|---|
| `node id 'O75469' must be namespaced` | Bare accession | Write `uniprot:O75469`. |
| `edge (...) references unknown src node` | Endpoint neither in the delta nor in the graph | Add the node to the delta, or pass `known_ids=store.node_ids()` and confirm it really exists. |
| `analogy node ... has no ORIGINATES_IN edge` | Analogy node written without its `Domain` | Add the `Domain` node and the `ORIGINATES_IN` edge to the *same* delta. |
| `SIMILAR_SEQUENCE_TO cannot start at a Compound` | Predicate used outside `PREDICATE_DOMAINS` | Use the right predicate for the axis, or register a new one in both `Predicate` and `PREDICATE_DOMAINS`. |
| `finding ... is a observation and must cite at least one Evidence` | `OBSERVATION`, `BENCHMARK`, `NEGATIVE`, or `PRIOR` with no evidence | Cite a locator, or change the kind to `HYPOTHESIS` or `DESIGN_CHOICE` if it really is your own reasoning. |
| `finding ... cites only ungrounded evidence` | Every source is `ANALOGY` or `EXPERT_PRIOR` | Drop the confidence to `speculative`, or add one grounded source. Do not relabel the source type. |
| `finding ... claims 'established' but cites fewer than two independent grounded sources` | One source, or the same locator twice | Add a second distinct grounded locator, or use `supported`. |
| `finding ... claims 'established' on grey literature alone` | Only blog, social, docs, talk, or competition sources | Use `supported`, or add one reviewed or structured-database source. |
| `cross_domain_analogy evidence must name its source_domain` | `Evidence(source_type=ANALOGY)` without `source_domain` | Name the field it came from, e.g. `"quantitative finance"`. |
| `visualization ...: question must be phrased as a question` | Missing trailing `?` | Write the actual question. If you cannot, delete the figure. |
| `visualization ...: takeaway restates question` | Copy-paste | Say what the figure shows, not what it asks. |
| `a kg_subgraph must name its focal_node` | Ego view with no centre | Set `focal_node` to the namespaced id at the centre. |
| `draws N elements with no clustering/aggregation/filtering declared` | `n_elements` above 5000 | Collapse communities or filter by weight, then declare `params={"clustered": True}`. |
| `maps N categories to colour alone` | Categorical `ColorMap` past 8 entries | Group into families, or set `secondary_channel`. |
| `reading_order references unknown visualization ids` | Figure renamed or removed | Fix the ids or clear `reading_order`. |
| `proposal ... is TRANSFERRED but names no source analogy card` | Missing `derived_from_analogy` | Point it at the card and ship the card in the same `ProposalSet`. |
| `proposal ... claims UNPRECEDENTED with no prior_art` | No search recorded | Add locators, or state in `rationale` what search you ran. |
| `analogy ...: mechanism restates source_practice` | Not abstracted | Rewrite the mechanism with no nouns from the source domain. |
| `a report with no findings must at least record why` | Empty report | Populate `limitations` with why nothing was found. |
| `dataset ... needs registration access but has no fetch_hint` | Gated source | Record the registration path or API call now. |
| `dataset ... claims a local_path but no retrieved_utc` | Materialised without stamping | Set `retrieved_utc` and `sha256` at fetch time. |
| `decisions must be attributable to a person or a named auto-rule` | Blank `decided_by` | Use a name or `auto:<rule>`. |
| `FAIL (N strict violations)` from `reagent report validate --strict` | Missing visuals, unvisualised metrics, no handoff, or no limitations | Read the four `FAIL` lines; each names exactly which of the four it is. |
