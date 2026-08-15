---
name: literature-harvest
description: >-
  Turn literature into typed, cited knowledge-graph deltas rather than prose.
  Runs Paperclip full-text search plus schema-forced structured extraction over
  papers, preprints, clinical trials, and FDA documents, emitting Paper nodes and
  provenanced edges with line-level citation anchors. The shared evidence engine
  used by Stage 0 scouting and every Stage 1 axis.
  Use when a claim needs literature support, when building the knowledge graph
  from sources, or when asked what is known about something.
  Trigger on: "what does the literature say", "find papers on", "cite this",
  "harvest the literature", "build the knowledge graph from papers",
  or /literature-harvest.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, Agent, WebSearch, WebFetch
---

# Literature harvest

Produce **data, not a reading list**. A prose summary of forty papers cannot be
queried, joined, or contradicted by the next agent. A set of typed edges with
line-level citations can be.

The reference pipeline we are trying to beat did a version of this by hand and it
was the highest-leverage thing it built: it turned "the nuclear-receptor
literature" into a 1,264-row labelled structure corpus with per-entry sample
weights that fed a curriculum fine-tune. Match that standard — your output is a
corpus, not an essay.

## Guard rails

- **Paperclip is MCP-only.** There is no local binary. Drive
  `mcp__claude_ai_Paperclip_for_literature_search__paperclip` with a `command`
  string and no `paperclip` prefix. See
  [paperclip-cli.md](reference/paperclip-cli.md) — read it before your first call,
  because several documented flags do not behave as documented.
- **`--save-as NAME` is the JSON switch, not `--json`.** And carry the returned
  `s_`/`m_` result IDs between calls; the human aliases do not persist.
- **Every edge gets a line-anchored locator.** `pmc:PMC12690452#L45-L52`, not
  `pmc:PMC12690452`. An unanchored citation cannot be checked, and a claim the
  next agent cannot check is a claim it has to redo.
- **NEVER assert a number you did not read.** If extraction returns null, the
  edge is `speculative` with an `illustrative`/`unmeasured` flag in its attrs, or
  it is not written at all. Confidently-wrong numbers are the single worst thing
  this skill can produce, because everything downstream treats the graph as fact.
- **Patents are unavailable through Paperclip** despite appearing in the help
  text. Use WebSearch against Google Patents or Espacenet, and record such
  evidence as `SourceType.PATENT` with the patent number as locator.
- **Search reviews for orientation, then exclude them for extraction.** A review's
  claims are second-hand; extract from primary sources so the citation points at
  the measurement.
- **Record what you did not find.** An axis with no literature support is a real
  finding (`FindingKind.NEGATIVE` or an `open_question`), and pretending otherwise
  sends Stage 3 into a gap with false confidence.

## Workflow

### Step 1 — Turn the question into a corpus, cheaply

Scope the landscape before spending on extraction. `sql` is free and fast (but
sees only titles and abstracts):

```
sql "SELECT pub_year, COUNT(*) n FROM documents WHERE title ILIKE '%<term>%'
     GROUP BY pub_year ORDER BY pub_year DESC LIMIT 15"
```

If the count is in the thousands your query is too broad; if it is under five, too
narrow or the term is wrong — check synonyms and gene aliases first.

### Step 2 — Build the result set

```
search -s pmc,biorxiv,medrxiv "<query>" -n 50 --has-full-text --year-min 2015 --save-as h1
refine --from s_XXXX --exclude-article-type review-article --save-as h2
```

Keep `-n <= 100`: above 100 the candidate pool expands and *reorders earlier
results*, so a rerun is not reproducible.

Run several complementary queries and `merge` them rather than one broad query.
Different phrasings surface disjoint literatures — the mechanism name, the gene
name, the protein name, and the drug class often each find papers the others miss.

### Step 3 — Extract with a schema that mirrors the graph

This is the step that makes the output a corpus. Define a JSON Schema whose fields
map **one-to-one onto `Node` and `Edge` fields**, then let Paperclip's workers fan
out over the corpus:

```
map --from s_YYYY --worker structured-extraction -j 32 \
  --output-schema '<schema from reference/extraction-schemas.md>' \
  "<field-by-field instructions>"
```

Rules that decide whether this works:

- `additionalProperties: false`, and every field explicitly nullable rather than
  absent. A worker that can omit a field will omit the hard one.
- Ask for the **line range** supporting each assertion as a required field. This
  is what produces checkable citations, and requiring it measurably suppresses
  invention.
- Ask for the assertion's **polarity** (supports / contradicts / no-claim). The
  contradictions are what make the graph worth building.
- One concept per schema. A schema extracting binding affinities *and* pocket
  residues *and* method choices returns mush for all three.
- Write the prompt field by field. A vague prompt against a strict schema yields
  confidently-wrong values, which is worse than a validation failure.

### Step 4 — Verify a sample by hand

Take 5 extracted assertions at random, open the cited lines, and check them:

```
grep -n -C 2 "<claimed term>" /papers/<ID>/content.lines
```

Record the hit rate in the Model Report's `metrics` as
`extraction_spot_check_accuracy`. If it is below ~0.8, fix the schema or the
prompt and re-run rather than shipping the graph — a graph nobody trusts costs
more than no graph.

### Step 5 — Emit the graph delta

Map extraction output onto typed nodes and edges, then validate before merging:

```python
from reagent.contracts import Edge, Evidence, GraphDelta, Node, Predicate, SourceType
from reagent.kg import KGStore

delta = GraphDelta(run_id=RUN, asserted_by="literature-harvest", nodes=[...], edges=[...])
problems = delta.validate_referential_integrity(known_ids=store.node_ids())
if not problems:
    store.merge(delta)
```

Always write a `Paper` node per source and a `SUPPORTED_BY` edge from each claim
to it. Evidence-family edges are hidden by default in the renderer precisely
because there are so many of them, so cite generously — it costs nothing visually.

### Step 6 — Audit before handing off

```python
store.unsupported_edges()   # edges claiming >= supported with zero citations
store.stats()               # cited_edge_fraction belongs in the report metrics
```

`cited_edge_fraction` below ~0.6 means the harvest asserted more than it read.

## Choosing the corpus for the question

| Question | Scope |
|---|---|
| Mechanism, structure, measurements | `-s pmc,biorxiv,medrxiv` |
| The current frontier (6-18 months ahead) | `-s biorxiv,medrxiv,arxiv` |
| Was it tried in humans, and what happened | `-s trials` |
| Regulatory view, liabilities, label language | `-s fda` |
| Broad recall where full text is not needed | `-s abstracts` |
| Sequence/annotation lookup | `-s proteins` (**run `paperclip skill proteins` first**) |
| Industrial methods absent from papers | WebSearch → Google Patents (not Paperclip) |

## Parallelising

For a broad harvest, spawn one subagent per sub-question, each returning
structured assertion JSON rather than prose, and merge in the orchestrator. Give
each the same schema so the merge is mechanical. Cap at 6-8 concurrent.

Do not fan out over *papers* yourself — that is what `map -j 32` already does,
far more cheaply than subagents.

## References

- [paperclip-cli.md](reference/paperclip-cli.md) — verified CLI surface, including the flags that lie
- [extraction-schemas.md](reference/extraction-schemas.md) — ready-made `--output-schema` payloads per claim type
- [citation-hygiene.md](reference/citation-hygiene.md) — locator formats, line anchors, and what makes a citation checkable
