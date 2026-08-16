---
name: target-properties
description: >-
  Derive the search axes from the target itself instead of accepting a fixed list. Works
  through a domain checklist asking what kind of thing the target IS — its family, fold,
  pocket character, promiscuity, pathway membership, position in its cascade, the
  analogous position it occupies in OTHER cascades, its binding partners, its shared
  regulators, where it is expressed, how the field assays it — and turns each answer into
  a predicate to search along, reifying it as a Property node so it cannot be forgotten.
  Every checklist item must be used or explicitly dismissed. Run before any neighbourhood
  search. Trigger on: "what is the target", "which axes", "how else could this connect",
  "meta concepts", "what kind of thing is this", "derive axes", "what are we not
  considering", or /target-properties.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, WebSearch, WebFetch
---

# Target properties

This skill exists because of one specific, repeatable failure.

> Asked to build a target's neighbourhood, an agent works the axes it was handed and stops.
> What it does not do is notice that the target **is a kind of thing** — a nuclear
> receptor, a promiscuous binder, a liver-enriched xenobiotic sensor — and that each of
> those memberships is a connector to a *different population* of proteins. The axes it was
> handed were a fixed list. The axes it should have run were derivable from the target.
> Whole regions go unsearched, and because nothing records the omission, the report reads
> as complete.

The fix is not a better prompt. It is a checklist with a coverage gate, and a graph in
which properties are nodes.

## The two mechanisms

**Reify the property.** "PXR is a promiscuous binder" as a sentence in a report is
something an agent may or may not act on. As a node — `property:promiscuous-binder`, with
`HAS_PROPERTY` edges — it has a degree. Every other promiscuous binder is two hops away, and
a property node with degree 1 is *visibly* an unexplored lead rather than an invisible one.
The graph makes the omission countable, which is the only reliable way to make it noticeable.

**Gate the coverage.** `AxisDerivation.uncovered_kinds()` returns checklist items that were
neither turned into an axis nor explicitly dismissed. Silence is not available, because
silence is exactly what the failure looks like from outside. An agent may decide a dimension
is irrelevant to this target; it may not decide so quietly.

## The checklist

`CHECKLISTS` in `reagent.contracts.axes` is keyed by `Domain` — 29 items for structural
biology, 11 for DEL-ML, and so on, because a checklist spanning both would be dismissed
item-by-item as inapplicable, which trains the habit of dismissing items and defeats the
gate. An unregistered domain falls back to the *largest* checklist, so a new domain makes
the gate harder to pass rather than trivially passable.

Each `PropertyKind` carries its own `question` — the form a worker can act on. Get them with:

```bash
reagent axes checklist --domain structural_biology
```

### Four items that are always worth extra attention

**`analogous_cascade_role`** is the one agents reliably skip, and it is kept as its own
checklist item for exactly that reason. Pathway membership asks *"who else is in my
cascade?"*. This asks *"whose cascade has a slot shaped like mine?"* — and the answer can be
a protein with no homology, no shared pathway and no shared partner. Two proteins can each be
the xenobiotic sensor of their own network, with the same trigger class upstream and the same
effector class downstream, and share nothing a similarity search can see. `ANALOGOUS_ROLE_TO`
is the only predicate that can express it, and nothing else will find it.

**`binding_partners`** and **`shared_regulators`** connect through *third* entities. Two
proteins that both heterodimerise with the same partner have a shared constraint on their
interface, whatever their folds do. Write the PPI as `INTERACTS_WITH` and the derived
relation as `SHARES_PARTNER_WITH` with the partner list in `attrs` — the derived edge without
the partners is unauditable.

**`ligand_promiscuity`** transfers a *problem*, not a similarity. Two promiscuous binders
share the adaptable-pocket difficulty: a single conformer misrepresents both, cross-docking
fails for both in the same way. That makes an unrelated promiscuous protein a better template
donor than a close homologue with a rigid pocket — which is precisely the conclusion a
family-first search cannot reach.

**`tissue_localisation`** looks like metadata and is not. Co-expression implies co-exposure:
proteins in the same tissue meet the same chemical matter, so their ligand sets overlap for
reasons that have nothing to do with structure, and assay conditions built for one are often
valid for the other.

Full treatment of every item — what it means, what it licenses, what it costs to get wrong —
is in [property-kinds.md](reference/property-kinds.md).

## Guard rails

- **`why_it_connects` must name a mechanism, not a category.** Not *"both are nuclear
  receptors"* but *"both use a ligand-binding domain whose helix-12 position reports
  occupancy, so a pose that misplaces helix 12 is wrong in the same way for both."* The
  validator rejects a restatement of the property as its own explanation. The test: does it
  say what a model could **transfer** between the two entities?
- **A property with no `implies_predicates` is the failure, not a partial success.**
  Recognising that the target is a kind of thing and then not searching along it is worse
  than not noticing, because the report now shows evidence of breadth.
- **A dismissal must be about *this* target.** `lazy_dismissals()` rejects "not relevant",
  "n/a", "out of scope" and anything under 20 characters. Say what about this target makes
  the dimension moot, so a reader can disagree with you.
- **Watch for typo'd dismissal keys.** `unknown_kinds()` catches them, because a misspelled
  key covers nothing while looking like it covers something — and the gate then reports a gap
  the author believes they closed.
- **Record `expected_yield` before searching.** A guess written down in advance is what makes
  a thin result noticeable. Written afterwards it is a rationalisation, and three hits will
  feel like plenty.
- **Do not collapse two dimensions because they overlap for this target.** For PXR, family
  membership and mechanism class both land on "ligand-activated transcription factor". They
  still return different populations, and merging them silently drops one.

## Working through it

1. **Resolve the target** to a canonical accession and pull what is cheaply available:
   UniProt (family, domains, localisation, PTM, function), PDB (structural coverage and
   states), ChEMBL (chemotypes, assay precedent), Reactome or KEGG (pathways), STRING or
   IntAct (partners), an expression atlas (tissue).
2. **Answer every checklist item**, in the checklist's order, without skipping ahead to
   the interesting ones. The uninteresting items are where the missed axes live — that is
   what makes them uninteresting to an agent optimising for apparent progress.
3. **For each answer, write the property**: value, the predicates it licenses, the
   mechanism, the evidence, the expected yield.
4. **Reify** each as a `Property` node with `HAS_PROPERTY` edges, using
   `property:<kebab-slug>` ids so two runs converge on the same node.
5. **Dismiss the rest explicitly**, with target-specific reasons.
6. **Emit `AxisSpec`s** and check the gate:

```bash
reagent axes derive --report reports/<run>/stage1/report.json --strict
```

Then hand each axis to its own worker — see `axis-sweep`. One worker per axis is not an
optimisation; it is what makes silent reprioritisation impossible.

## Anti-patterns

- **Starting from the axis list in the `ProblemSpec`.** That list is a floor. If derivation
  produces nothing the spec did not already contain, derivation did not happen.
- **Answering the checklist from the model's own knowledge.** Every property needs evidence.
  A remembered family assignment is right often enough to be dangerous.
- **Treating an empty axis as a dead dimension.** "No protein shares this pocket character"
  is a finding worth recording as a negative result, and it stops the next run repeating
  the search.
- **Writing the derivation after the search.** It becomes a description of what was found
  rather than a plan for what to look for, and the uncovered-kinds gate passes vacuously.
- **One property, one predicate, always.** Promiscuity licenses `PROMISCUOUS_WITH` *and* a
  breadth query over `BINDS`. Pathway membership licenses `IN_PATHWAY`,
  `SHARES_PATHWAY_WITH`, and `UPSTREAM_OF`.

## References

- [property-kinds.md](reference/property-kinds.md) — every checklist item: the question, what it licenses, the data source, and the failure mode of getting it wrong
- [analogous-roles.md](reference/analogous-roles.md) — how to find same-position-different-cascade relatives, with the ranking heuristic and worked non-obvious examples
- [reification.md](reference/reification.md) — Property node conventions, id slugs, and the queries that make a low-degree property visible as an unexplored lead
