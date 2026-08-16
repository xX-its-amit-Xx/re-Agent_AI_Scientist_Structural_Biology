# Reifying properties as nodes

A property written as prose is a sentence an agent may or may not act on. A property written as
a node has a degree.

That is the whole argument, and it is worth being precise about why the difference matters.
"PXR is a promiscuous binder" in a report is a true statement that changes nothing unless
something reads it and decides to search along it. As `property:promiscuous-binder` with
`HAS_PROPERTY` edges, it is a countable object: every other promiscuous binder is two hops
away, a query can enumerate the properties nothing was ever searched along, and a property with
degree 1 is *visibly* an unexplored lead.

**Making the omission countable is what makes it noticeable.** Prompts asking an agent to be
thorough do not survive context pressure. A query returning `n_members = 1` does.

## Conventions

Ids are `property:<kebab-slug>`, and the slug is the *property*, never the target:

```
property:promiscuous-binder          not  property:pxr-promiscuous
property:liver-enriched              not  property:expressed-in-liver-pxr
property:ligand-activated-tf
property:adaptable-pocket
property:xenobiotic-sensor
property:obligate-heterodimer
property:induces-own-metabolism
```

Target-specific slugs defeat the purpose entirely: the node's value is that two independently
discovered proteins collapse onto the same one, and a slug containing the target's name can only
ever have degree 1.

Node payload:

```python
Node(
    id="property:adaptable-pocket",
    type=NodeType.PROPERTY,
    label="Adaptable binding pocket",
    aliases=["induced fit", "plastic pocket", "conformationally flexible site"],
    attrs={
        "kind": "pocket_plasticity",     # the PropertyKind that produced it
        "basis": "pocket volume varies >30% across holo structures with distinct ligands",
        "threshold": "volume CV > 0.3 over >=3 distinct-ligand holo structures",
    },
    asserted_by="target-properties",
)
```

`basis` and `threshold` are what stop the property from being a vibe. Without a stated
threshold, two runs will disagree about which proteins have it and the node quietly means two
different things — which is worse than not having it, because the degree count then looks
meaningful and is not.

`aliases` matter more here than elsewhere: the same property is called different things in
different subfields, and the alias list is what lets an agent searching for "induced fit" find
the node created for "adaptable pocket".

## Edges

```python
Edge(src="uniprot:O75469", predicate=Predicate.HAS_PROPERTY,
     dst="property:adaptable-pocket",
     attrs={"evidence_basis": "5 holo structures, pocket volume 1150-1650 A^3"},
     confidence=Confidence.SUPPORTED,
     evidence=[...], asserted_by="target-properties")
```

`HAS_PROPERTY` is deliberately unrestricted on the source side. A compound class, an assay, or a
method can each be "a kind of thing" whose peers matter — a method that is
`property:requires-holo-template` has peers worth knowing about.

Do **not** add a derived `SHARES_PROPERTY_WITH` edge. The two-hop path through the property node
is the query, and it keeps the property explicit and enumerable. A derived edge would let the
property node fall out of use, at which point nothing counts what is unexplored.

## The queries this buys

**Unexplored properties** — the most actionable query in the graph:

```sql
SELECT p.dst AS property, COUNT(DISTINCT p.src) AS n_members
FROM edges p WHERE p.predicate = 'HAS_PROPERTY'
GROUP BY p.dst ORDER BY n_members ASC;
```

Ascending. A property with one member was derived and never swept, or swept and found empty
without recording it. Either way it is the first thing to fix, and descending order would bury
it under the properties that already worked.

**Peers by property, excluding the family** — the query that finds non-obvious template donors:

```sql
SELECT DISTINCT b.src AS peer
FROM edges a
JOIN edges b ON a.dst = b.dst AND b.predicate = 'HAS_PROPERTY'
WHERE a.src = :target AND a.predicate = 'HAS_PROPERTY'
  AND a.dst = :property AND b.src <> :target
  AND b.src NOT IN (
      SELECT f2.src FROM edges f1
      JOIN edges f2 ON f1.dst = f2.dst AND f2.predicate = 'MEMBER_OF_FAMILY'
      WHERE f1.src = :target AND f1.predicate = 'MEMBER_OF_FAMILY');
```

*"Proteins sharing the target's adaptable-pocket problem that are not in its family."* This is
the shape of query the whole graph exists for, and it is one join away only because the property
is a node.

**Property co-occurrence** — which properties travel together across the graph. A property that
always co-occurs with another is probably not independent, and treating it as a separate axis
double-counts the evidence.

## Visual encoding

`HAS_PROPERTY` sits in `PredicateFamily.CONTEXT`, visible by default. Property nodes appear in
the ego view as hubs at ring 1 with a distinct fill, and their degree is legible as size — so a
degree-1 property is visually a stub. That is intentional: it is the one place in the render
where **the absence of edges is the information**.

Deliberately not hidden by default despite being numerous. The reason CONTEXT and SYSTEMS are
on by default is that network position and meta-properties are precisely the connections an
agent forgets, and defaulting them to invisible would restore the blind spot they exist to fix.

## Anti-patterns

- **A property per target.** Degree 1 forever, and the count becomes noise rather than signal.
- **A property with no threshold.** Two runs will populate it differently.
- **Free-text properties that duplicate an existing node.** Check `aliases` before creating.
  `property:flexible-pocket` and `property:adaptable-pocket` as separate nodes split the
  population in half and neither degree means anything.
- **Reifying everything.** A property earns a node when it *connects* — when other entities
  plausibly share it. "Has 434 residues" is an attribute, not a property; put it in `attrs` on
  the protein.
- **Asserting the property without evidence.** `HAS_PROPERTY` edges carry evidence like any
  other. A remembered class membership is right often enough to be dangerous.
