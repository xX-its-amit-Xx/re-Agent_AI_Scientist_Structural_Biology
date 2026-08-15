---
name: target-neighborhood
description: >-
  Stage 1. Build the multi-axis neighbourhood of a target entity in the knowledge
  graph — what resembles it by sequence, fold, pocket, structural motif,
  promiscuity, and family — and measure the domain shift between what is known
  and what must be predicted. Dispatches over the similarity axes declared in the
  ProblemSpec, so it works for a protein, a compound library, or an assay endpoint
  without modification.
  Use when starting the literature/knowledge-graph stage, when asked what is
  similar to a target, or when a downstream stage needs templates or transfer
  sources.
  Trigger on: "what proteins are similar to", "build the knowledge graph",
  "find templates for", "neighbourhood of", "what's related to the target",
  or /target-neighborhood.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, Agent, WebSearch, WebFetch, Skill
---

# Target neighbourhood

Answer "what is our target like?" on every axis that matters, as a **queryable
graph with citations**, and quantify how far the things we must predict sit from
the things we know. That last number is the most valuable thing this stage
produces.

## Guard rails

- **NEVER hardcode the target or the axes.** Read them from
  `reports/<run-id>/problem.json`. The axes come from the `ProblemSpec`, supplied
  by a domain profile in `reagent.domains`. If an axis is missing for this
  problem's domain, register a profile — do not special-case here.
- **One predicate per axis, always.** A generic `SIMILAR_TO` destroys the whole
  point: Stage 2 and Stage 3 ask different questions of different axes and need
  to filter on them separately.
- **Report each prior's domain of validity, not just the prior.** This is the
  hardest-won lesson available. In the reference case, drug-like-trained
  similarity signals **inverted sign** on the fragment half of the test set —
  confirmed four times independently. A prior that helps one subpopulation and
  hurts another is worse than no prior if you hand it over unlabelled.
- **Measure the domain shift explicitly.** Never assume the test items resemble
  the known ligands. In the reference case the fragments had Tanimoto < 0.3 to
  *every* known holo ligand, which reorganised the entire pipeline.
- **Every quantitative edge is either measured or flagged.** Run the tool, or set
  `illustrative: true` and `Confidence.SPECULATIVE`. Never emit a plausible number.
- **Normalise scores within their own axis.** A TM-score of 0.8 and a Tanimoto of
  0.8 are different claims. `AxisSpec.score_range` exists so the renderer can be
  honest about relative strength; respect it.
- **Free tier only.** Sequence/fold/chemistry search and literature are free. Do
  not spend Boltz/Modal/Tamarind credits in Stage 1.

## Workflow

### Step 1 — Load the problem and resolve the target

```python
from reagent.contracts import ProblemSpec
from reagent.domains import profile_for
spec = ProblemSpec.load(Path(f"reports/{run_id}/problem.json"))
target = spec.primary_target          # never a literal
axes = spec.required_axes()
```

Resolve the target to canonical identifiers first and write them into the graph as
the anchor node. Getting the accession wrong silently poisons every axis, so
verify: accession ↔ gene name ↔ organism ↔ sequence length should all agree.

### Step 2 — Run each axis, one at a time, and record the method

Axes are independent, so fan them out — one subagent per axis, each returning a
`GraphDelta` as JSON. For each axis, use the first tool in `AxisSpec.methods` that
is actually available, and record which one in the `MethodStep`.

An axis is done when it has produced: edges with real scores, a `MethodStep` with
parameters, and an explicit statement of what it *could not* cover.

Guidance per axis type, in rough order of reliability:

- **family** — the most reliable and least surprising. Its value is *coverage*: it
  defines the corpus a downstream fine-tune weights over. Prefer a structured
  registry query over literature. In the reference case, one RCSB Search API call
  for Pfam PF00104 with `nonpolymer_entity_count > 0`, filtered against a curated
  ~230-entry additive exclude list (waters, ions, buffers, cryoprotectants, PEGs,
  detergents), produced 1,264 labelled ligand-bound entries across 30 receptors.
  That filter list is the real work — see
  [structured-corpus-harvest.md](reference/structured-corpus-harvest.md).
- **sequence** — cheap and reliable, but weakly predictive of pocket similarity
  for promiscuous targets. Do not let it dominate the ranking.
- **fold** — needs a structure for the target. If only a prediction exists, record
  its confidence: fold-similarity scores inherit the model's error and will be
  over-trusted downstream otherwise.
- **pocket** — often *more* predictive than fold for ligand-transfer questions,
  and more fragile. The pocket definition is a free parameter; write it down.
- **promiscuity** — operationalise as measured breadth of `BINDS` (distinct
  chemotypes), never as a literature adjective. The highest-value neighbours here
  are often **outside** the target's family, because they share the *problem* — a
  large adaptable pocket — without sharing the fold. The reference case harvested
  six such classes deliberately: cytochrome P450 (419 entries), kinase (5,784),
  transporter (755), protease (4,433), phosphodiesterase (517), GPCR (25).
- **motif** — the most upside and least established practice. Delegate to
  `esmc-sae-motifs`. A learned feature is only evidence once it has a structural
  interpretation.

### Step 3 — Measure the domain shift

Compare the distribution of **what we must predict** against **what is known**.
Concretely: nearest-neighbour similarity from each test item to the known set,
reported as a distribution, not a mean.

Then partition the test items into subpopulations by that similarity and report
per-subpopulation statistics. This partition is the thing Stage 3 designs against.

Emit as `FindingKind.PRIOR` with the validity domain in the statement, plus a
heatmap visualization. If the distribution is bimodal, say so loudly — it means
one pipeline will not serve both halves.

### Step 4 — Contradiction sweep

Query for pairs of edges that disagree (`CONTRADICTED_BY`, or the same relation
asserted at different values by different sources). Contradictions are findings,
not noise, and surfacing them is a large part of why the graph is worth building.

### Step 5 — Visualize (required)

At minimum:

1. **Ego network** — the target at the centre, neighbours in rings, one edge
   colour per predicate family. `reagent viz kg --focal <id> --depth 2`.
2. **Axis-agreement heatmap** — neighbours × axes, cell = normalised score. This
   is the figure that shows whether the axes agree, and disagreement is
   informative: a protein that is a fold neighbour but not a pocket neighbour is a
   different kind of template than one that is both.
3. **Domain-shift distribution** — test items' nearest-neighbour similarity to the
   known set, with the subpopulation split marked.

Every figure must declare its question. See `kg-visualize` and `model-report`.

### Step 5b — Say what each relationship means

For every axis that produced neighbours, answer three questions in the finding's
`interpretation`:

- **Why are these related?** The mechanism, not the score. "These share a large
  adaptable pocket because both must accommodate chemically unrelated partners" is a
  mechanism; "TM-score 0.79" is not.
- **What would a chemist and a biologist each see here?** They see different things in
  the same shared motif — one a pharmacophore, the other a fold constraint.
- **What does it change?** Which template, corpus, or restraint decision this bears on,
  and what breaks if the reading is wrong.

Define the jargon once in the report glossary: what a nuclear receptor is, what a
binding pocket is, what promiscuity means and why it makes prediction harder. A reader
who does not have those cannot use any of the rest.

### Step 6 — Hand off

```json
"handoff": {
  "to_stage": "stage2_biochem",
  "payload": {
    "target": "<id>",
    "neighbours_by_axis": {"fold": [...], "promiscuity": [...]},
    "template_candidates": [{"id": "...", "axes_supporting": ["fold","pocket"], "score": 0.86}],
    "corpus_for_finetune": {"entries": [...], "sample_weights": {...}},
    "subpopulations": {"<name>": {"n": 76, "nn_similarity_median": 0.22}},
    "priors": [{"claim": "...", "valid_for": "...", "invalid_for": "..."}]
  },
  "blocking_unknowns": ["..."]
}
```

`corpus_for_finetune` with per-entry sample weights is the concrete artifact Stage
3 needs. The reference pipeline weighted its curriculum by receptor
(target 3×, close homologs 2×, rest 1×) across four stages of escalating
specificity — supply the weights, not just the list.

## Anti-patterns

- **A ranked list of "similar proteins" with no axis attribution.** Useless: the
  consumer cannot tell why anything is on it.
- **Stopping at the family.** The family is the easy axis. The promiscuity and
  motif axes are where non-obvious transfer sources live.
- **Reporting a mean similarity.** Distributions decide pipelines; means hide
  bimodality, which is exactly the thing you most need to see.
- **Treating the target's known ligands as representative of the test items.**
  Check it. In the reference case they were not, and everything followed from that.

## References

- [structured-corpus-harvest.md](reference/structured-corpus-harvest.md) — RCSB/UniProt/ChEMBL query recipes and the additive-ligand exclude list
- [axis-methods.md](reference/axis-methods.md) — concrete tools per axis, with parameters and gotchas
- [domain-shift.md](reference/domain-shift.md) — how to measure it and how it has broken real pipelines
