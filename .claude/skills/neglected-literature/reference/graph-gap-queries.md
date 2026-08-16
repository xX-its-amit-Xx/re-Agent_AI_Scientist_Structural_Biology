# Graph-gap queries: connections no paper has stated

Swanson's *undiscovered public knowledge* (1986, Library Quarterly): A relates to B in one
literature, B relates to C in another, and no paper has ever stated A–C. His fish-oil /
Raynaud's case and the magnesium / migraine case were both found this way, by hand, from
complementary literatures that did not cite each other.

He did it by reading. **We have the graph, so it is a query.**

The distinctive property: no keyword search can find these, because the sentence you would
search for has never been written. That makes this the one channel whose blind spot is not
shared with any other, and it is why the estimated coverage of a search without it is
overstated in a way capture-recapture cannot detect.

## The basic query

Find `A → B → C` where no `A → C` edge exists. Against the SQLite view:

```sql
SELECT a.src AS a, a.predicate AS p1, a.dst AS b,
       b.predicate AS p2, b.dst AS c,
       COUNT(*) AS n_paths
FROM edges a
JOIN edges b ON a.dst = b.src
WHERE a.src <> b.dst
  AND NOT EXISTS (
        SELECT 1 FROM edges d
        WHERE (d.src = a.src AND d.dst = b.dst)
           OR (d.src = b.dst AND d.dst = a.src))
GROUP BY a.src, b.dst
ORDER BY n_paths DESC;
```

Run it and you get thousands of rows, almost all worthless. **The query is trivial; the
ranking is the entire craft.** Report the ranking you used, so a reader can see what was
filtered out rather than trusting that the survivors were the good ones.

## Ranking heuristics

### 1. Penalise hub intermediates, hard

A path through a high-degree B is noise. If B is `family:nuclear-receptor`, then every pair of
nuclear receptors is two hops apart and the query has told you nothing. Weight by
`1 / degree(B)`, or exclude any B above a degree percentile.

**A specific intermediate is the whole signal.** A path through a shared, unusual cofactor, a
single shared partner protein, or one rare motif is interesting precisely because few things
share it.

### 2. Reward literature disjointness

The Swanson insight is not that A and C are connected — it is that **two communities that
should be talking are not**. Estimate disjointness from the paper nodes:

```sql
-- Do the papers supporting A→B and the papers supporting B→C overlap at all?
```

Zero overlap in supporting papers, authors, and venues is the strong signal. Substantial
overlap means the connection is already known to the people who would care, and someone has
simply not written the sentence.

### 3. Reward predicate complementarity

Some predicate pairs compose meaningfully and some do not:

| p1 → p2 | Composes? | Reading |
|---|---|---|
| `HAS_PROPERTY` → `HAS_PROPERTY`⁻¹ | **yes** | A and C are the same kind of thing. The core meta-concept query. |
| `SHARES_MOTIF` → `SHARES_MOTIF`⁻¹ | **yes** | A shared local feature, at any global dissimilarity. |
| `BINDS` → `BINDS`⁻¹ | **yes** | A shared ligand implies a comparable subsite. Strong. |
| `IN_PATHWAY` → `IN_PATHWAY`⁻¹ | weakly | Only if the pathway is small. Otherwise a hub. |
| `INTERACTS_WITH` → `INTERACTS_WITH` | **yes** | A shared partner constrains both interfaces. |
| `EXPRESSED_IN` → `EXPRESSED_IN`⁻¹ | weakly | Co-localisation implies co-exposure, not similarity. |
| `SUPPORTED_BY` → `SUPPORTED_BY`⁻¹ | **no** | Co-citation, not a relationship. Exclude. |
| anything → `MEMBER_OF_FAMILY` | **no** | Family is a hub by construction. |

Exclude the evidence and data families entirely: those paths say two things appear in the same
paper, which is co-citation wearing a graph edge.

### 4. Reward asymmetric attention

The best candidates connect a well-studied A to a barely-studied C. If both are well studied,
someone has probably checked. If both are obscure, verifying the path is expensive and the
prior is poor.

## The query that matters most for this project

`HAS_PROPERTY → HAS_PROPERTY⁻¹` — two entities sharing a reified property with no direct edge.
This is the meta-concept search made mechanical:

```sql
SELECT p.dst AS property, COUNT(DISTINCT p.src) AS n_members
FROM edges p
WHERE p.predicate = 'HAS_PROPERTY'
GROUP BY p.dst
ORDER BY n_members ASC;   -- ascending: low-degree properties first
```

**Ascending order is the point.** A property with one member is a claim about the target that
nobody has searched along — `target-properties` derived it, and either the sweep found nothing
(which should be recorded as a negative result) or the sweep never ran. Either way it is the
most actionable row in the graph, and sorting descending would bury it under the properties
that already worked.

This is why properties are reified at all. As prose, "PXR is a promiscuous binder" is a
sentence an agent may forget to act on. As a node with degree 1, it is a visible hole.

## Verifying a candidate

A ranked gap is a hypothesis, and most are wrong. Before it becomes an edge:

1. **Search for the connection directly**, in both fields' vocabularies. Often it has been
   stated and our graph simply lacks the edge — that is a graph-completeness finding, still
   worth recording, but not a discovery.
2. **Check the intermediate is the same thing on both sides.** The commonest failure: B is a
   node id shared by two genuinely different entities, or a family assignment that means
   something different in each subfield.
3. **State the mechanism.** If you cannot say *why* A and C should be comparable, the path is
   a coincidence. This is what `MetaProperty.why_it_connects` demands, and the same standard
   applies here.
4. **Cap confidence at `tentative`** unless a direct source turns up. The path is a reason to
   look, not evidence. Channel `graph_gap`, reason `never_stated`, and the path itself in the
   justification.

## Expected yield

Low, and say so. Out of thousands of raw paths, expect single digits worth verifying and
fewer that survive. That is an acceptable return for the only channel that can find a
connection nobody has written down — but report the funnel (`n_paths → n_ranked → n_verified →
n_admitted`) so the reader can see the cost, rather than seeing only the survivors and
inferring a hit rate that was never real.
