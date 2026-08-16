"""Generate per-skill meta.json and create contract-complete stubs for unowned stages.

Idempotent: existing SKILL.md files are never overwritten, so a teammate's work is
safe. meta.json IS rewritten, because it is generated registry input rather than
authored content.

Run: python scripts/bootstrap_skills.py
"""

from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SKILLS = REPO / ".claude" / "skills"

# ---------------------------------------------------------------------------
# Pipeline metadata. `consumes`/`produces` are the handoff contract keys that
# `reagent skills check` lints, so they must agree across stage boundaries.
# ---------------------------------------------------------------------------

META: dict[str, dict] = {
    "ai-scientist": {
        "stage": "shared", "owner": "amit", "status": "implemented",
        "summary": "Top-level orchestrator: plans stages, enforces gates, chains reports.",
        "consumes": ["problem.spec", "stage0.report", "stage1.report", "stage2.report",
                     "stage3.report", "stage4.report"],
        "produces": ["run.plan", "synthesis.report"],
        "external_tools": ["Agent", "WebSearch"], "credits": [],
    },
    "pipeline-space-scouting": {
        "stage": "stage0_scouting", "owner": "amit", "status": "implemented",
        "summary": "Map the method landscape, baselines, and failure modes for a problem class.",
        "consumes": ["problem.spec"],
        "produces": ["stage0.report", "stage0.method_landscape", "stage0.open_gaps",
                     "stage0.baselines", "kg.method_nodes"],
        "external_tools": ["paperclip", "WebSearch", "WebFetch"], "credits": [],
    },
    "cross-domain-analogy": {
        "stage": "stage0_scouting", "owner": "amit", "status": "implemented",
        "summary": "Borrow mechanisms from unrelated fields; emit gated, falsifiable proposals.",
        "consumes": ["stage0.open_gaps"],
        "produces": ["stage0.proposals", "kg.analogy_nodes", "decisions.pending"],
        "external_tools": ["Agent", "WebSearch", "paperclip"], "credits": [],
    },
    "literature-harvest": {
        "stage": "shared", "owner": "amit", "status": "implemented",
        "summary": "Literature to typed, line-cited graph deltas via schema-forced extraction.",
        "consumes": ["problem.spec"],
        "produces": ["kg.paper_nodes", "kg.claim_edges", "literature.assertions"],
        "external_tools": ["paperclip", "WebSearch"], "credits": [],
    },
    "source-scout": {
        "stage": "stage1_literature", "owner": "amit", "status": "implemented",
        "summary": "Patents, repos, Zenodo, Kaggle, blogs — plus dataset pointers, not downloads.",
        "consumes": ["problem.spec", "kg.neighbourhood"],
        "produces": ["kg.dataset_nodes", "data.availability", "kg.paper_nodes"],
        "external_tools": ["WebSearch", "WebFetch", "github", "zenodo", "huggingface",
                           "kaggle", "chembl", "bindingdb"],
        "credits": [],
    },
    "data-materialize": {
        "stage": "shared", "owner": "amit", "status": "implemented",
        "summary": "Resolve Dataset pointers into local files, costed and checksummed.",
        "consumes": ["kg.dataset_nodes", "data.availability"],
        "produces": ["data.local_cache", "data.fetch_report"],
        "external_tools": ["WebFetch", "curl"], "credits": [],
    },
    "adversarial-verify": {
        "stage": "shared", "owner": "amit", "status": "implemented",
        "summary": "Break a claim in a worker that is not its author; calibrate the verifier "
                   "against injected falsehoods and report what bounds the pipeline.",
        "consumes": ["kg.claim_edges", "literature.assertions", "stage1.report",
                     "stage0.report"],
        "produces": ["verify.verdicts", "verify.calibration", "verify.agreement",
                     "kg.claim_edges"],
        "external_tools": ["Agent", "WebFetch", "rcsb-search-api", "uniprot", "chembl"],
        "credits": [],
    },
    "neglected-literature": {
        "stage": "stage1_literature", "owner": "amit", "status": "implemented",
        "summary": "Recover under-attended but relevant work; the exploration quota and "
                   "the coverage ledger.",
        "consumes": ["problem.spec", "kg.neighbourhood", "stage1.axis_derivation"],
        "produces": ["kg.paper_nodes", "kg.dataset_nodes", "search.ledger",
                     "search.coverage", "stage1.neglected_sources"],
        "external_tools": ["paperclip", "WebSearch", "WebFetch", "openalex",
                           "semantic-scholar", "github", "zenodo"],
        "credits": [],
    },
    "target-properties": {
        "stage": "stage1_literature", "owner": "amit", "status": "implemented",
        "summary": "Derive search axes from what the target IS, against a domain checklist "
                   "with a coverage gate.",
        "consumes": ["problem.spec"],
        "produces": ["stage1.axis_derivation", "stage1.axes", "kg.property_nodes"],
        "external_tools": ["uniprot", "reactome", "string-db", "chembl", "WebSearch",
                           "WebFetch"],
        "credits": [],
    },
    "axis-sweep": {
        "stage": "stage1_literature", "owner": "amit", "status": "implemented",
        "summary": "Work one axis to exhaustion in its own worker, with an observable "
                   "stopping rule.",
        "consumes": ["stage1.axes", "stage1.axis_derivation"],
        "produces": ["kg.neighbourhood", "stage1.axis_sweeps", "search.ledger"],
        "external_tools": ["Agent", "foldseek", "mmseqs2", "rcsb-search-api", "uniprot",
                           "chembl", "reactome", "string-db", "WebSearch"],
        "credits": [],
    },
    "target-neighborhood": {
        "stage": "stage1_literature", "owner": "amit", "status": "implemented",
        "summary": "Multi-axis neighbourhood of the target; measures the domain shift.",
        "consumes": ["problem.spec", "kg.paper_nodes", "kg.claim_edges", "motif.features",
                     "stage1.axes", "stage1.axis_sweeps", "search.ledger"],
        "produces": ["stage1.report", "kg.neighbourhood", "stage1.template_candidates",
                     "stage1.corpus_for_finetune", "stage1.subpopulations", "stage1.priors"],
        "external_tools": ["foldseek", "mmseqs2", "rcsb-search-api", "uniprot", "chembl"],
        "credits": [],
    },
    "compound-neighborhood": {
        "stage": "stage1_literature", "owner": "amit", "status": "stub",
        "summary": "Chemical space around the test items; quantifies train/test chemotype shift.",
        "consumes": ["problem.spec"],
        "produces": ["stage1.compound_neighbourhood", "stage1.chemotype_split"],
        "external_tools": ["rdkit", "chembl"], "credits": [],
    },
    "esmc-sae-motifs": {
        "stage": "stage1_literature", "owner": "amit", "status": "stub",
        "summary": "Sparse-autoencoder features over a protein LM as candidate structural motifs.",
        "consumes": ["problem.spec"],
        "produces": ["motif.features", "kg.motif_nodes"],
        "external_tools": ["esm-c", "sae"], "credits": ["esmc"],
    },
    "kg-visualize": {
        "stage": "shared", "owner": "amit", "status": "implemented",
        "summary": "Render the graph as a self-contained interactive ego view, plus exports.",
        "consumes": ["kg.neighbourhood"],
        "produces": ["viz.kg_html", "viz.obsidian_vault", "viz.graphml"],
        "external_tools": ["cytoscape.js"], "credits": [],
    },
    "explain-significance": {
        "stage": "shared", "owner": "amit", "status": "implemented",
        "summary": "Write why a finding matters, for each audience, and how the agent decided.",
        "consumes": ["stage0.report", "stage1.report", "kg.neighbourhood"],
        "produces": ["report.interpretation", "report.glossary", "report.reasoning_trace"],
        "external_tools": [], "credits": [],
    },
    "progressive-disclosure": {
        "stage": "shared", "owner": "amit", "status": "implemented",
        "summary": "Anticipate the reader's next question and answer it in place, nested "
                   "five levels deep with no dead ends.",
        "consumes": ["report.interpretation", "report.glossary"],
        "produces": ["report.follow_ups"],
        "external_tools": [], "credits": [],
    },
    "report-mcp": {
        "stage": "shared", "owner": "amit", "status": "implemented",
        "summary": "Serve a report and its graph over MCP; compare two structures in 3D.",
        "consumes": ["report.validated", "kg.neighbourhood", "kg.dataset_nodes"],
        "produces": ["mcp.server", "viz.structure_comparison"],
        "external_tools": ["3dmol.js", "rcsb", "alphafold-db"], "credits": [],
    },
    "model-report": {
        "stage": "shared", "owner": "amit", "status": "implemented",
        "summary": "How to write, visualize, and validate a stage's Model Report.",
        "consumes": ["report.interpretation", "report.glossary", "report.reasoning_trace",
                     "report.follow_ups", "search.ledger", "stage1.axis_sweeps"],
        "produces": ["report.rendered", "report.validated"],
        "external_tools": [], "credits": [],
    },
    "pocket-anatomy": {
        "stage": "stage2_biochem", "owner": "denny", "status": "stub",
        "summary": "Critical residues and the ligand fragments complementary to them.",
        "consumes": ["stage1.report", "kg.neighbourhood", "stage1.template_candidates",
                     "data.availability", "data.local_cache"],
        "produces": ["stage2.report", "stage2.critical_residues", "stage2.fragment_map",
                     "kg.residue_nodes", "viz.interaction_2d"],
        "external_tools": ["chimerax", "plip", "prolif", "fpocket"], "credits": [],
    },
    "pocket-dynamics": {
        "stage": "stage2_biochem", "owner": "denny", "status": "stub",
        "summary": "How much the pocket moves, and which conformer a prediction should target.",
        "consumes": ["stage2.critical_residues", "stage1.template_candidates"],
        "produces": ["stage2.conformer_ensemble", "stage2.flexibility_map"],
        "external_tools": ["chimerax", "mdanalysis", "openmm"], "credits": ["tamarind"],
    },
    "structure-ensemble": {
        "stage": "stage3_prior", "owner": "sumer", "status": "stub",
        "summary": "Generate a diverse candidate pool across multiple models and seeds.",
        "consumes": ["stage1.priors", "stage2.conformer_ensemble", "stage1.template_candidates"],
        "produces": ["stage3.pose_pool", "stage3.pool_oracle"],
        "external_tools": ["boltz", "openprotein", "modal", "tamarind", "esm"],
        "credits": ["boltz", "modal", "tamarind"],
    },
    "confidence-selection": {
        "stage": "stage3_prior", "owner": "sumer", "status": "stub",
        "summary": "Pick one candidate per item from the pool; the step that decides the score.",
        "consumes": ["stage3.pose_pool", "stage3.pool_oracle", "stage2.critical_residues"],
        "produces": ["stage3.report", "stage3.selection", "stage3.failure_tail"],
        "external_tools": [], "credits": [],
    },
    "template-and-finetune": {
        "stage": "stage3_prior", "owner": "sumer", "status": "stub",
        "summary": "Structural templating and curriculum fine-tuning on the Stage 1 corpus.",
        "consumes": ["stage1.corpus_for_finetune", "stage1.subpopulations"],
        "produces": ["stage3.finetuned_model", "stage3.template_set"],
        "external_tools": ["openprotein", "modal", "slurm"], "credits": ["modal", "openprotein"],
    },
    "medchem-pass": {
        "stage": "stage4_optimization", "owner": "amit", "status": "stub",
        "summary": "Chemistry-aware geometry review of selected poses, tiered by severity.",
        "consumes": ["stage3.selection", "stage2.fragment_map"],
        "produces": ["stage4.edited_poses", "stage4.edit_ledger"],
        "external_tools": ["rdkit", "chimerax"], "credits": [],
    },
    "dock-and-minimize": {
        "stage": "stage4_optimization", "owner": "amit", "status": "stub",
        "summary": "Docking and restrained minimization as a refinement, gated on ground truth.",
        "consumes": ["stage3.selection", "stage3.failure_tail", "stage2.conformer_ensemble"],
        "produces": ["stage4.report", "stage4.refined_poses"],
        "external_tools": ["vina", "openmm", "tamarind"], "credits": ["tamarind"],
    },
}

# ---------------------------------------------------------------------------
# Stub bodies. Deliberately opinionated: each names the trap that has already
# cost a real pipeline points, so a teammate starts ahead of where we started.
# ---------------------------------------------------------------------------

STUBS: dict[str, dict[str, str]] = {
    "compound-neighborhood": {
        "desc": (
            "Stage 1. Map the chemical space around the items a pipeline must predict for, "
            "and quantify how far they sit from the compounds anything was trained or "
            "measured on. Produces chemotype clusters, a scaffold census, and the "
            "train/test similarity distribution that decides whether one model can serve "
            "the whole test set. Use when characterising test compounds, choosing a "
            "chemical split, or checking whether a chemical prior will transfer. "
            'Trigger on: "what compounds are similar", "chemical space", "scaffold split", '
            '"chemotype", "will this prior transfer", or /compound-neighborhood.'
        ),
        "tools": "Read, Write, Edit, Glob, Grep, Bash, Agent",
        "body": """# Compound neighbourhood

Characterise the chemistry we must predict for, and measure its distance from the
chemistry anything was trained on. The second half is the point.

## Guard rails

- **Report distributions, never means.** A mean similarity of 0.45 is compatible
  with a unimodal set and with two disjoint clusters at 0.2 and 0.7, and those
  demand different pipelines. Bimodality is the finding.
- **Run this on the TEST items, not on the target's known ligands.** The gap
  between them *is* the domain shift, and it is the single most decision-relevant
  number Stage 1 produces.
- **A similarity threshold is a modelling choice, not a fact.** State the
  fingerprint, radius, and metric with every number. Morgan-r2 Tanimoto 0.3 is
  not comparable to MCES 0.3.
- **NEVER assume a chemical prior transfers across a chemotype gap.** In the
  reference case, signals trained on drug-like ligands *inverted sign* on the
  fragment half of the test set — confirmed four independent ways. Report the
  domain of validity, not just the prior.

## Workflow

1. **Load the test manifest** from `ProblemSpec.test_items`. Standardise every
   structure (neutralise, strip salts, canonical tautomer) before any comparison;
   unstandardised SMILES silently inflate dissimilarity.
2. **Census the scaffolds** — Murcko and generic-Murcko frameworks, with counts.
   A scaffold appearing once is a different prediction problem from one appearing
   forty times.
3. **Build the reference set**: known binders of the target and its Stage 1
   neighbours, from ChEMBL/BindingDB plus co-crystallised ligands in the graph.
4. **Compute nearest-neighbour similarity** from each test item to the reference
   set. Report the full distribution plus the fraction below 0.3, which is the
   conventional "no useful analogue" line.
5. **Cluster into chemotypes** and check whether the clusters align with any
   physicochemical property split (heavy atoms, rotatable bonds, logP). If they
   do, that property is your subpopulation label and Stage 3 should route on it.
6. **Emit** `SIMILAR_COMPOUND_TO` and `SHARES_SCAFFOLD` edges with the
   fingerprint recorded in `attrs`, plus `Compound` and `Fragment` nodes.

## Required visuals

- Nearest-neighbour similarity **histogram**, with the subpopulation split marked.
- Chemotype cluster map (UMAP or MDS over fingerprints), coloured by
  subpopulation — the figure that shows whether the test set is one problem or two.
- Scaffold census as a ranked bar chart.

## Handoff

`stage1.compound_neighbourhood` and `stage1.chemotype_split`, the latter being the
labels Stage 3 routes on. Include, for each subpopulation: n, median
nearest-neighbour similarity, and which priors are valid for it.
""",
    },
    "esmc-sae-motifs": {
        "desc": (
            "Stage 1. Use sparse-autoencoder features over a protein language model "
            "(ESM-C) to find structural or functional motifs the target shares with other "
            "proteins, including motifs that sequence and fold search miss. Emits Motif "
            "nodes and SHARES_MOTIF edges, but only for features that survive a structural "
            "interpretation check. Use for the motif similarity axis, or when conventional "
            "homology search returns nothing useful. "
            'Trigger on: "structural motif", "SAE features", "ESM-C", "latent features", '
            '"what motifs does it share", or /esmc-sae-motifs.'
        ),
        "tools": "Read, Write, Edit, Glob, Grep, Bash",
        "body": """# ESM-C sparse-autoencoder motifs

Protein language models encode structure and function in superposed features; a
sparse autoencoder over the residue embeddings can pull individual features apart.
Some correspond to recognisable motifs — a catalytic triad, a hydrophobic pocket
lining, a dimerisation surface. This axis finds neighbours that share those
features, which is exactly the set that sequence identity and fold similarity can
both miss.

It is also the axis most likely to produce confident nonsense, so the bar is high.

## Guard rails

- **A feature is not a motif until it has a structural interpretation.** An SAE
  feature index is a number. Before emitting a `SHARES_MOTIF` edge you must be
  able to say *what* the feature fires on, verified against structure or
  annotation. Unverified features go in the report as `open_questions`, not in the
  graph.
- **Verify with a negative control.** Check the feature does *not* fire on a
  matched set of unrelated proteins. Without that, high activation is
  uninformative — many features fire on everything.
- **Report activation, position, and context.** A feature firing on 3 contiguous
  residues in a helix is a different claim from the same feature firing scattered
  across a domain.
- **Confidence caps at `tentative`** for a motif supported only by feature
  similarity. Promote to `supported` only when structure or literature
  independently backs it.
- **Record the model and SAE checkpoint** in every edge's `attrs`. Features are
  not portable across checkpoints, and an unlabelled feature index is unusable
  six weeks later.

## Workflow

1. **Embed** the target and the candidate set (Stage 1's family and promiscuity
   neighbours are the natural pool) with ESM-C. Record model id and layer.
2. **Encode with the SAE** to per-residue sparse feature activations.
3. **Select the target's characteristic features**: high activation on the region
   of interest (e.g. the pocket-lining residues Stage 2 cares about), low
   elsewhere. Specificity matters more than magnitude.
4. **Interpret each candidate feature.** Which residues does it fire on across
   many proteins? Do those positions share a known annotation (InterPro, PROSITE)
   or a 3D arrangement? Name it, or discard it.
5. **Negative control.** Confirm it does not fire on a matched unrelated set.
6. **Score sharing** between the target and each candidate on the surviving
   features, and emit `Motif` nodes plus `HAS_MOTIF` / `SHARES_MOTIF` edges.

## Required visuals

- **Feature activation heatmap**: residue position x feature, for the target, with
  the region of interest marked.
- **Motif-sharing matrix**: candidate proteins x interpreted motifs.
- For the top motifs, a **structure render** with the firing residues highlighted
  — the figure that turns a feature index into a claim a biochemist can judge.

## Handoff

`motif.features` and `kg.motif_nodes`. For each motif: an interpretation, the
residues involved, the negative-control result, and the checkpoint it came from.
Motifs that failed interpretation belong in `limitations` — that is a real result
about the method, and hiding it invites someone to repeat the work.
""",
    },
    "pocket-anatomy": {
        "desc": (
            "Stage 2. Work out which residues in a binding site actually matter and which "
            "ligand fragments are complementary to each, producing an interaction map that "
            "downstream sampling and scoring can be conditioned on. Detects hydrogen bonds, "
            "hydrophobic contacts, pi-stacking, and salt bridges across known complexes, and "
            "renders publication-quality pocket figures. Use when characterising a binding "
            "site, choosing restraints, or explaining why a pose is or is not plausible. "
            'Trigger on: "critical residues", "binding site", "pocket residues", '
            '"which amino acids matter", "interaction map", "anchor residues", '
            "or /pocket-anatomy."
        ),
        "tools": "Read, Write, Edit, Glob, Grep, Bash, Agent",
        "body": """# Pocket anatomy

**Owner: Denny.** This stub is contract-complete: the inputs, outputs, guard rails
and required figures are fixed, so Stage 3 can be built against it before the body
is written. Replace this body; do not change `meta.json`'s `produces` keys without
telling Sumer, because his stage consumes them.

## What this stage answers

1. Which residues line the site, and which of those are load-bearing rather than
   merely nearby?
2. For each load-bearing residue, what ligand chemistry is complementary to it?
3. Which interactions recur across *all* known complexes, and which are idiosyncratic?

## Guard rails

- **"Lines the pocket" is not "matters".** Rank residues by evidence — mutational
  data, conservation across the Stage 1 family corpus, recurrence across holo
  structures — not by proximity. A residue within 4 Å of every ligand may still be
  a bystander.
- **Derive the interaction map from MANY complexes, not one.** A single co-crystal
  gives you that ligand's interactions, not the pocket's grammar.
- **State whether an anchor is required or optional.** This is the trap that has
  already cost a real pipeline points: in the reference case, fragment ligands
  engaged **zero** canonical anchors, so an anchor-based prior applied uniformly
  *inverted* on the fragment half of the test set. Anchors are additive bonuses,
  never penalties for absence, unless you have evidence otherwise.
- **Report per-subpopulation validity.** Use the `stage1.subpopulations` labels.
  An interaction map valid only for drug-like ligands must say so.
- **ChimeraX must run headless and scripted.** A figure produced by clicking is
  not reproducible. Commit the `.cxc` script alongside the image.

## Workflow sketch

1. Load `stage1.template_candidates` and the target's holo structures from the graph.
2. Detect interactions per complex with PLIP or ProLIF — hydrogen bonds,
   hydrophobic contacts, pi-stacking, pi-cation, salt bridges, halogen bonds.
3. Build an **interaction fingerprint matrix**: ligand x residue x interaction type.
   This is the natural bridge to the knowledge graph — each nonzero cell is a
   `POCKET_LINED_BY` / `BINDS` edge with the interaction type in `attrs`.
4. Rank residues by recurrence and by independent evidence.
5. Map complementary fragments: for each load-bearing residue, which chemical
   groups engage it across the corpus.
6. Render figures headlessly and emit the graph delta and Model Report.

## Required visuals

- **2D interaction diagram** (PLIP/LigPlot style) for a representative complex.
- **Interaction fingerprint heatmap**: ligand x residue, cell coloured by
  interaction type — the figure that shows the pocket's grammar at a glance.
- **3D pocket render** with load-bearing residues as labelled sticks, plus a
  surface coloured by hydrophobicity.
- **Recurrence bar chart**: fraction of complexes engaging each residue, which is
  what separates anchors from bystanders.

## Handoff

`stage2.critical_residues` — per residue: id, evidence, recurrence fraction,
required-vs-optional, and the subpopulations it is valid for.
`stage2.fragment_map` — per residue: complementary chemistry.
""",
    },
    "pocket-dynamics": {
        "desc": (
            "Stage 2. Characterise how much a binding site moves, which conformational "
            "states it occupies, and therefore which conformer a structure prediction "
            "should be targeting. Produces a conformer ensemble and a per-residue "
            "flexibility map, with movies and overlays that make the motion visible. "
            "Use when a pocket is suspected to be plastic, when predictions disagree in a "
            "flexible region, or when choosing a receptor conformer for docking. "
            'Trigger on: "pocket dynamics", "flexibility", "conformational change", '
            '"is the pocket rigid", "which conformer", "induced fit", or /pocket-dynamics.'
        ),
        "tools": "Read, Write, Edit, Glob, Grep, Bash",
        "body": """# Pocket dynamics

**Owner: Denny.** Contract-complete stub — replace the body, keep the interface.

## What this stage answers

Is the pocket one shape or several? If several, which shape should a predictor aim
at, and does the right answer depend on the ligand?

## Guard rails

- **Prefer experimental ensembles to simulation.** Multiple crystal structures of
  the same protein with different ligands are direct evidence of accessible
  states; an MD trajectory is a model of them. Use the structures you have before
  buying trajectory time.
- **A flexible pocket is a warning about the metric, not just the biology.** If the
  site moves more than the scoring tolerance, then "correct" is ill-defined and a
  single predicted conformer cannot win. Say so explicitly — it changes what
  Stage 3 should optimise.
- **Simulation must be gated on ground truth before it is trusted.** In the
  reference case, local MD refinement could not recover a 2 Å ligand translation
  and was correctly abandoned. Validate against known complexes first; MD that
  cannot fix a known error will not fix an unknown one.
- **Cost gate.** MD spends real credits. Estimate first, write it into a proposal,
  and get an accepted decision before launching.

## Workflow sketch

1. Superpose all holo structures of the target from the graph; measure per-residue
   displacement. This is free and often sufficient.
2. Cluster into discrete conformational states; check whether state correlates with
   ligand size, chemotype, or the Stage 1 subpopulation labels.
3. Compute pocket volume per state (fpocket or equivalent) and report the range.
4. Only if 1-3 leave a real question open, run restrained MD — and gate it on
   recovering known complexes first.

## Required visuals

- **Ensemble overlay**: all states superposed, coloured by state, pocket residues
  as sticks.
- **Per-residue displacement (RMSF-style) trace**, with the load-bearing residues
  from `pocket-anatomy` marked — the figure that says whether the residues that
  matter are also the ones that move.
- **Pocket volume distribution** across states.
- Optionally a short **movie** interpolating between states; motion is the one
  thing a still image genuinely cannot convey.

## Handoff

`stage2.conformer_ensemble` — the states worth predicting against, with which
ligand classes each suits. `stage2.flexibility_map` — per-residue displacement
with the tolerance comparison spelled out.
""",
    },
    "structure-ensemble": {
        "desc": (
            "Stage 3. Generate a diverse pool of candidate structures or poses across "
            "multiple models, seeds, and templates, and measure the pool's achievable "
            "ceiling. Widening the pool is one of only two levers that reliably improve a "
            "prediction pipeline, so this stage is about diversity and oracle gap rather "
            "than any single model's quality. Use when producing candidates, choosing which "
            "models to run, or deciding whether the bottleneck is generation or selection. "
            'Trigger on: "generate poses", "run co-folding", "sampling", "pose pool", '
            '"which models should we run", "oracle gap", or /structure-ensemble.'
        ),
        "tools": "Read, Write, Edit, Glob, Grep, Bash, Agent",
        "body": """# Structure ensemble

**Owner: Sumer.** Contract-complete stub — replace the body, keep the interface.

## The one number this stage exists to produce

The **oracle gap**: how good the pool's best candidate is, versus what our
selector actually picks. It tells the whole team where to spend next.

- Oracle far above realised → **selection** is the bottleneck. Stop adding models.
- Oracle close to realised → **generation** is the bottleneck. Widen the pool.

In the reference case the pool oracle was ~1.08 Å median while realised
performance was far worse, which correctly redirected all effort to selection.
Compute this before anything else in Stage 3.

## Guard rails

- **Diversity over quality.** Different models fail on *different* items, and that
  is what a pool is for. Six mediocre-but-decorrelated generators beat one good
  one. Measure decorrelation, do not assume it.
- **Use cross-model diversity to WIDEN, never to VOTE.** Consensus across agreeing
  models is a trap: they share correlated errors, so consensus can be *actively
  harmful*. This is established in the literature and was confirmed empirically in
  the reference case.
- **Record each model's native confidence signal.** These are not interchangeable
  and not commensurable across models; `confidence-selection` needs the raw
  per-model signal, not a normalised one.
- **Cost gate before launching.** This is the expensive stage. Estimate per-model
  cost, write it into a proposal, get an accepted decision, and log spend per
  `MethodStep.credits`.
- **Never discard a candidate at generation time.** Selection is a separate,
  revisable decision; a pruned pool cannot be re-selected when the selector
  improves.

## Workflow sketch

1. Read `stage1.priors`, `stage1.template_candidates`, `stage2.conformer_ensemble`.
   Respect each prior's stated domain of validity — applying one outside it is how
   pipelines regress.
2. Choose generators for **decorrelation**, cheapest first, and start with a small
   pilot subset before committing credits.
3. Generate with multiple seeds/samples per item; record every candidate with its
   native confidence.
4. Compute the pool oracle against whatever ground truth exists, plus per-model
   coverage of the failure set.
5. Report the oracle gap prominently. It is the headline metric.

## Required visuals

- **Oracle-vs-realised curve** as a function of pool size (best@1, best@5, best@20)
  — the figure that tells the team which lever to pull.
- **Per-model coverage matrix**: item x model, cell = candidate quality. Shows
  decorrelation directly, and where each model uniquely wins.
- **Parallel-coordinates plot** comparing models across cost, coverage, and
  confidence calibration.

## Handoff

`stage3.pose_pool` (every candidate, with native confidence and provenance) and
`stage3.pool_oracle` (achievable ceiling, overall and per subpopulation).
""",
    },
    "confidence-selection": {
        "desc": (
            "Stage 3. Choose one candidate per item from a generated pool. In a pipeline "
            "with a fixed pool and no ground truth, this step usually decides the score "
            "outright, so it is treated as a first-class modelling problem: normalise "
            "non-commensurable confidence signals, select per item, then rescue the "
            "failure tail with a decorrelated generator. Use when ranking candidates, "
            "picking a final answer, or diagnosing why a good pool scores badly. "
            'Trigger on: "select poses", "rank candidates", "which pose do we submit", '
            '"confidence score", "z-score selection", "failure tail", '
            "or /confidence-selection."
        ),
        "tools": "Read, Write, Edit, Glob, Grep, Bash",
        "body": """# Confidence selection

**Owner: Sumer.** Contract-complete stub — replace the body, keep the interface.

This is the highest-leverage step in the whole pipeline and the one where clever
approaches most reliably lose to simple ones. Read
`ai-scientist/reference/pxr-case-study.md` before designing anything here.

## The selection wall

With a fixed pool and no ground truth to train on, **every** learned, agentic, or
consensus selector in the reference case regressed against a plain z-scored
native-confidence argmax. Ranked by realised score, the losers included a
37-feature XGBoost LambdaMART ranker (worst submission of the project), agentic
pose review, geometric consensus, medoid selection, Borda and reciprocal-rank
fusion, and MMFF strain gating.

The independent literature review agreed *before* the experiments did: on
co-folding pose pools, native-confidence ranking and cross-model consensus
largely do not beat random, and consensus can be actively harmful.

Treat any proposal to build a smarter selector as guilty until proven innocent,
and require it to beat the z-hybrid baseline on held-out data before adoption.

## What did work

1. **Within-model selection by that model's own native signal.** Not a universal
   score — the model knows what it does not know, in its own units.
2. **Cross-model selection by z-score.** Raw confidences are not commensurable, so
   z-score each model's best-sample scores across all items, then take the argmax
   over models per item. This alone took 0.4996 to 0.5472 in the reference case.
3. **Failure-tail rescue with a decorrelated generator.** Overwrite only the N
   lowest-confidence items with a different model's candidates. N=8 was optimal
   (0.5640); N=4 and N=12 were both worse. The tail is real but small, and
   over-swapping destroys good picks.

## Guard rails

- **Z-score within a model before comparing across models.** Skipping this lets one
  model's inflated scale dominate every item.
- **Sweep the rescue count; do not guess it.** The optimum is a narrow peak.
- **Validate against the real metric, not a proxy.** In the reference case a
  secondary metric was statistically decoupled from the primary one (Spearman
  ~+0.01) while a third tracked it closely (~+0.94). Ranking by the decoupled one
  would have been actively misleading. Check the correlation yourself.
- **Beware tiny validation sets.** All methods clustered inside the noise floor on
  a 35-structure set while the leaderboard spanned a 5x wider range. A ±0.05 win
  on 50 items is noise.
- **Use validation-set expansion as an overfit detector.** When the task gets
  easier, every honest method should improve. One that does not is overfit — this
  signature caught a pLDDT-based selector that had ranked first.

## Required visuals

- **Confidence-vs-accuracy scatter** per model, with the correlation stated. The
  figure that shows whether a signal is worth anything at all.
- **Selection-divergence matrix**: which items each candidate selector picks
  differently. Divergence outside a sane band is a strong early warning.
- **Failure-tail sweep curve**: score vs number of rescued items, peak marked.
- **Per-subpopulation score breakdown**, since a selector can win overall while
  losing on the half that carries the points.

## Handoff

`stage3.selection` (the chosen candidate per item, with the signal and reason) and
`stage3.failure_tail` (the low-confidence items, for Stage 4 to work on).
""",
    },
    "template-and-finetune": {
        "desc": (
            "Stage 3. Inject the biological prior into the model itself, via structural "
            "templating and curriculum fine-tuning on the corpus Stage 1 assembled. "
            "Escalates specificity in stages with decreasing learning rate, and gates every "
            "checkpoint against held-out complexes before it is allowed near a prediction. "
            "Use when a general model underperforms on a specific target family, or when a "
            "curated corpus with sample weights is available. "
            'Trigger on: "fine-tune", "curriculum", "structural template", "LoRA", '
            '"transfer learning", "train on the family", or /template-and-finetune.'
        ),
        "tools": "Read, Write, Edit, Glob, Grep, Bash",
        "body": """# Template and fine-tune

**Owner: Sumer.** Contract-complete stub — replace the body, keep the interface.

## Guard rails

- **Gate every checkpoint against held-out complexes.** A fine-tune that does not
  beat the public model on held-out ground truth is a regression with extra steps.
  Make this gate the first thing you build, not the last.
- **Escalate specificity, decay the learning rate.** Broad and general first,
  narrow and specific last, with the interface weight rising as the corpus
  narrows. A single-stage fine-tune on the narrow corpus overfits.
- **Use the sample weights Stage 1 supplied.** They encode which corpus members
  resemble the target and are the difference between a curriculum and a shuffle.
- **Beware activation lag on external platforms.** In the reference case, external
  compute had a ~12-week practical activation lag against a 30-day window, and
  **0 of 8** attempts produced a submittable output. Budget accordingly, and keep
  a local fallback.
- **Templating is often illegal.** Check `ProblemSpec.withheld` before using any
  structure as a template; a blind challenge usually forbids the obvious ones.

## The reference curriculum, as a starting point

Four stages of escalating specificity over a corpus assembled by Stage 1:

| Stage | Corpus | Steps | LR | Interface weight |
|---|---|---|---|---|
| 1 | broad drug-like complexes | 2000 | 3e-4 | 1.0 |
| 2 | promiscuous target classes | 1500 | 1e-4 | 1.5 |
| 3 | the target's full family, weighted (target 3x, close homologs 2x, rest 1x) | 800 | 5e-5 | 2.0 |
| 4 | the target's own complexes | 350 | 2e-5 | 3.0 |

Other settings that mattered: ligand-pocket cropping on, 3 recycles, bf16, EMA
0.999, gradient clipping 1.0, checkpoint and evaluate every 100 steps.

Note this path was packaged but **never produced a scored result** in the reference
work, so the table is a credible starting configuration, not a validated recipe.
Treat it as a hypothesis and gate it like one.

## Required visuals

- **Training curves per curriculum stage**, with the held-out gate line drawn on.
- **Before/after per-subpopulation comparison** — a fine-tune that helps the
  family average while hurting the hard subpopulation is a net loss.
- **Corpus composition chart** showing what the model actually saw at each stage.

## Handoff

`stage3.finetuned_model` (checkpoint plus its gate result, or an explicit
statement that it failed the gate) and `stage3.template_set`.
""",
    },
    "medchem-pass": {
        "desc": (
            "Stage 4. Review selected poses for chemistry that a medicinal chemist would "
            "reject — clashes, strained conformers, implausible placements — and apply "
            "conservative coordinate-only corrections tiered by severity. Every edit is "
            "logged and reversible, and the pass is validated as a whole before it is "
            "allowed to replace the incumbent. Use when polishing final poses or triaging "
            "geometry problems. "
            'Trigger on: "medchem review", "fix the poses", "clashes", "strained '
            'conformer", "geometry cleanup", or /medchem-pass.'
        ),
        "tools": "Read, Write, Edit, Glob, Grep, Bash, Agent",
        "body": """# Medchem pass

## Guard rails

- **Coordinates only. Never touch the molecular graph.** Atom names, connectivity,
  and bond orders must survive untouched or the submission validator rejects the
  entry and the item scores zero.
- **Tier every edit and apply conservatively.** keep / light / drastic. In the
  reference case, applying the 20 light-tier edits landed within noise of the base
  and was a small net *negative* (0.5613 vs 0.5640). Expect this pass to do
  nothing, and be pleased if it does no harm.
- **NEVER let an agent redraw a ligand freely.** The reference case has the
  cautionary number: an agentic free re-draw took one pose from 3.88 Å to
  **24.63 Å**. Agents hallucinate unphysical geometry with total confidence.
  Constrain edits to small rigid-body and torsion adjustments.
- **Validate the whole pass before adopting it.** Compare against the incumbent on
  held-out ground truth. A pass that cannot demonstrate improvement should not
  ship, however sensible each individual edit looked.
- **Log every edit** with before/after and a reason. `stage4.edit_ledger` is what
  lets you revert one bad decision instead of the whole pass.

## Required visuals

- **Before/after 3D overlays** for every applied edit — the reviewer needs to see
  the change, not read about it.
- **Severity histogram** across all poses (how many keep / light / drastic).
- **Score delta per edited item**, so a single catastrophic edit cannot hide inside
  a favourable mean.
""",
    },
    "dock-and-minimize": {
        "desc": (
            "Stage 4. Refine selected poses with docking and restrained minimization, "
            "gated on ground truth so refinement is only adopted where it demonstrably "
            "helps. Targets the failure tail rather than the whole set, because physics-based "
            "refinement reliably improves some cases and destroys others. Use when "
            "polishing final predictions, relieving clashes, or attempting to rescue "
            "low-confidence items. "
            'Trigger on: "dock", "minimize", "refine the poses", "Vina", "MD refinement", '
            '"relieve clashes", or /dock-and-minimize.'
        ),
        "tools": "Read, Write, Edit, Glob, Grep, Bash",
        "body": """# Dock and minimize

## Guard rails

- **Gate on ground truth before adopting anything.** Refinement is the classic
  place where a plausible improvement is a measurable regression. Validate on known
  complexes first, then apply.
- **Expect minimization to hurt as often as it helps.** In the reference case,
  ligand-only force-field relaxation of the *ground truth itself* monotonically
  degraded it — the bound conformer is legitimately strained, so relaxing toward a
  gas-phase minimum moves away from the answer. Never minimise a ligand in
  isolation.
- **Local refinement cannot fix a placement error.** MD did not recover a 2 Å
  translation. Refinement polishes a nearly-correct pose; it does not relocate a
  wrong one. Target it accordingly.
- **Apply to the failure tail, not the whole set.** Use `stage3.failure_tail`.
  Blanket application dilutes the wins with regressions on already-good poses.
- **Docking scores are not accuracy.** Use docking to *generate* geometry, never to
  rank it. Selection belongs to `confidence-selection`.
- **Cost gate.** MD spends credits. Estimate, propose, get the decision, log spend.

## Required visuals

- **Before/after RMSD scatter** on the validation gate, with the identity line
  drawn — points below it are the regressions, and they are the story.
- **Per-item delta ranked bar chart**, wins and losses side by side.
- **3D overlay** of before, after, and reference for the largest win and the
  largest loss. Show the failure, not only the success.
"""
    },
}


def write_meta() -> int:
    n = 0
    for name, meta in META.items():
        d = SKILLS / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
        n += 1
    return n


def write_stubs() -> tuple[int, int]:
    created = skipped = 0
    for name, spec in STUBS.items():
        d = SKILLS / name
        d.mkdir(parents=True, exist_ok=True)
        md = d / "SKILL.md"
        if md.exists():
            skipped += 1
            continue
        fm = (
            "---\n"
            f"name: {name}\n"
            "description: >-\n"
            + "".join(f"  {line}\n" for line in _wrap(spec["desc"], 76))
            + f"allowed-tools: {spec['tools']}\n"
            "---\n\n"
        )
        md.write_text(fm + spec["body"], encoding="utf-8")
        created += 1
    return created, skipped


def _wrap(text: str, width: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return lines


def main() -> int:
    n_meta = write_meta()
    created, skipped = write_stubs()
    print(f"meta.json written: {n_meta}")
    print(f"stub SKILL.md created: {created}, left alone (already authored): {skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
