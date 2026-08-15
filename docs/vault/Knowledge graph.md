# Knowledge graph

**This vault is a reading interface, not the figure.** Obsidian cannot encode
edge weight — its link model has nowhere to store a per-edge number that any
renderer reads — so the graph view here shows structure without strength. For
the weighted, colour-coded figure use `reagent viz kg`.

What this vault is good for: clicking through entities, backlinks, hover
previews, full-text search, and Dataview queries over edge payloads.

Focal entity: [[uniprot O75469]] — PXR (NR1I2)

## Contents

41 nodes, 67 edges.

| Entity type | n |
|---|---|
| Protein | 17 |
| Residue | 7 |
| Structure | 5 |
| Compound | 4 |
| Family | 3 |
| Paper | 3 |
| Pocket | 1 |
| Motif | 1 |

| Predicate family | n |
|---|---|
| composition | 34 |
| structural | 15 |
| interaction | 9 |
| sequence | 6 |
| chemical | 3 |

## Setup for typed, coloured edges

Native Obsidian draws every edge the same monochrome line. To get edge
colours you need the **Extended Graph** plugin (the only maintained plugin
that does it), then enable *Color links* and point link-type detection at
frontmatter properties. Node colours come from the `type/*` tags via graph
groups, or from the `node-type` property in Extended Graph.

Install **Dataview** to run the queries below. Neither plugin travels with
the vault, so a teammate must install both.

## Useful queries

Strongest fold neighbours:

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

Every measured binding interaction:

```dataview
TABLE WITHOUT ID file.link AS Entity, L.link AS Compound, L.confidence AS Conf
FROM "nodes"
FLATTEN file.lists AS L
WHERE L.BINDS
```

Claims resting on a single source — the audit query worth running:

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
