# Obsidian export: what works, and what Obsidian cannot do

Obsidian was evaluated as the primary knowledge-graph view and **rejected**. It
ships here as a secondary reading interface because the exporter is nearly free
once the JSONL exists. This document records the evaluation so nobody has to repeat
it, then documents the export convention.

## The verdict

Obsidian is a note-graph tool. Used as a network-analysis tool for a scientific
graph it fails on requirements we actually have, in descending order of severity.

**Edge weight is unrepresentable.** This is the disqualifying one. Obsidian's link
model is `(source file, target file, optional display alias)` — there is nowhere in
the format to store a per-edge number that any renderer reads. `[[NR1I3|tm_score=0.82]]`
sets a *display alias*; the edge renders identically. Typed edges *can* be
coloured, via the Extended Graph plugin reading frontmatter properties or Dataview
inline fields, but thickness can only be driven by **computed graph statistics**
(co-citation counts, Jaccard, Adamic-Adar) — never by our stored `tm_score` or
`tanimoto`. Our stated requirement is that edge type *and* weight are both encoded.
Obsidian can do the first and not the second.

There is a hack: emit the same wikilink `round(score * 5)` times so Extended
Graph's occurrence-count thickness approximates the score in five quantised steps.
It pollutes every backlink panel and every Dataview query. That this is the best
available mechanism is itself the verdict.

**Scale.** Extended Graph — the single plugin the whole typed-edge story rests on —
is documented and tested to roughly 400-600 nodes, with an auto-disable threshold
you have to raise yourself. A real Stage 1 graph is 500-5,000 nodes and up to
20,000 edges. The native renderer handles the node count but shows none of our
semantics: every edge is an identical monochrome line.

**Parallel edges collapse.** Obsidian draws **one** line between two notes. Two
proteins related on four different axes is our normal case, and the whole reason
the primary renderer uses a library with automatic bezier fanning. Extended Graph's
multi-type curved links mitigate this partially; a 30-predicate vocabulary with
several predicates per pair still visually collapses.

**No programmatic layout, no legend, no reproducible figure.** Force layout is
non-deterministic and there is no API to pin the target at the centre and lay rings
by score. You cannot script "the figure for the report".

**Single-plugin dependency risk.** Everything above depends on one
solo-maintained plugin, in the ecosystem's highest-churn category. The three
previous plugins in this exact niche — Juggl, Graph Analysis, and the 3D graph
plugin — are all abandoned, the earliest since 2022.

**Obsidian Publish runs no community plugins.** So sharing a vault as a website
shows teammates the unstyled monochrome graph regardless of local configuration.
Extended Graph does offer SVG export, subject to the same node-count ceiling.

## What the vault is genuinely good for

Once the export exists, you get things the HTML figure does not offer:

- **Click-through navigation** with backlinks and hover previews. Following
  "which papers support this edge, and what else do they support" is pleasant here
  and clumsy anywhere else.
- **Full-text search** across every node and its attributes.
- **Dataview queries over edge payloads** — "every `BINDS` edge with an affinity
  below 1 micromolar", "every claim resting on a single source", "every protein with
  no data pointer". These are real audit queries and they are easier to write here
  than in SQL.

Use it for exploration and for reading. Use `reagent viz kg` for the deliverable.

## Running the export

```bash
reagent viz obsidian --kg kg --out docs/vault --focal uniprot:O75469
```

Add `--include-evidence` to include `SUPPORTED_BY` and friends. Off by default,
because every claim cites sources and they will swamp both the graph view and the
backlink panel.

Teammates need two plugins installed for the styling to appear: **Extended Graph**
(coloured typed edges) and **Dataview** (the queries). Neither travels with the
vault. The export does pre-seed `.obsidian/graph.json` with a colour group per
entity type, so native node colouring works without configuring fifteen groups by
hand — which is the step most likely to make someone give up before seeing anything.

## The export convention

Every edge is written **twice**, deliberately, because no single representation
serves both the renderer and the query engine.

**As a frontmatter typed link.** A property named after the predicate, holding
quoted wikilinks. This is what Extended Graph reads to assign the edge its *type*,
and therefore its colour, and it also registers as a real link in the native graph
and the backlink panel.

**As a Dataview inline field in the body.** Carries the quantitative payload.
Nothing renders this on the edge — no plugin can — but it is queryable, which is
the part that stays useful.

A node file looks like this:

```markdown
---
node-id: "uniprot:O75469"
node-type: Protein
aliases: ["PXR", "NR1I2"]
asserted-by: "target-neighborhood"
tags: [type/Protein]
degree: 35
ligand_bound_pdb_entries: 70
SIMILAR_FOLD_TO:
  - "[[uniprot Q14994]]"
  - "[[uniprot P11473]]"
BINDS:
  - "[[chembl CHEMBL432657]]"
MEMBER_OF_FAMILY:
  - "[[family NR1I]]"
---

# PXR (NR1I2)

`uniprot:O75469` · Protein

## Edges

### SIMILAR_FOLD_TO  *(structural)*

- SIMILAR_FOLD_TO:: [[uniprot Q14994]] [confidence:: speculative] [tm_score:: 0.87] [rmsd:: 1.9]
- SIMILAR_FOLD_TO:: [[uniprot P11473]] [confidence:: speculative] [tm_score:: 0.79]

### BINDS  *(interaction)*

- BINDS:: [[chembl CHEMBL432657]] [confidence:: supported] [role:: agonist] [evidence:: pmc:PMC12690452]
```

Notes on the mechanics:

- **Filenames sanitise the colon out of namespaced ids** (`uniprot:O75469` becomes
  `uniprot O75469.md`), because a colon is illegal in a Windows filename and inside
  a wikilink. The original id is preserved in the `node-id` property, and **that is
  what you should join on** — never the filename.
- **`degree` is written as a numeric property** because Extended Graph's
  "individual node size" setting can scale nodes by an arbitrary numeric frontmatter
  property. Node size is therefore the one quantitative channel that does work here.
- **`tags: [type/Protein]`** gives native graph groups an easy target
  (`tag:#type/Protein` → a colour), which is what the pre-seeded config uses.
- **A "Referenced by" section** lists incoming edges, capped, so navigation works
  in both directions without relying on the backlink panel alone.

## Configuring Extended Graph for coloured edges

After installing it: enable **Color links**, then point link-type detection at
frontmatter properties (the predicate names are the property names). Optionally
enable edge type labels and curved multi-type links. Node styling can key off the
`node-type` property directly rather than the tags.

Set the auto-disable node threshold above your graph size, and expect load times of
several seconds past a few hundred nodes.

## Useful Dataview queries

Included in the generated `Knowledge graph.md`, repeated here for reference.

Strongest fold neighbours, which is the query Obsidian *can* answer well even
though it cannot draw the answer:

```dataview
TABLE WITHOUT ID
  regexreplace(string(L.link), "\\[|\\]", "") AS Neighbour,
  L.tm_score AS TM, L.confidence AS Confidence
FROM "nodes"
FLATTEN file.lists AS L
WHERE L.SIMILAR_FOLD_TO AND L.tm_score
SORT L.tm_score DESC
LIMIT 25
```

Claims resting on a single source — worth running before shipping a report:

```dataview
TABLE WITHOUT ID file.link AS Entity, L.link AS Target, L.evidence AS Evidence
FROM "nodes"
FLATTEN file.lists AS L
WHERE L.confidence = "supported" AND L.evidence
```

Entities with no data pointer, which is where the gaps are:

```dataview
LIST
FROM "nodes"
WHERE node-type = "Protein" AND !HAS_DATA
```

## If you want a better desktop tool

For publication-quality static layouts or real network analysis, export GraphML and
open it in **Gephi** (layout and visual polish) or **Cytoscape desktop** (the
bio-focused one, scriptable from Python via py4cytoscape). Both handle typed,
coloured, weighted edges properly and neither is a note-taking app being asked to
do something it was not built for.
