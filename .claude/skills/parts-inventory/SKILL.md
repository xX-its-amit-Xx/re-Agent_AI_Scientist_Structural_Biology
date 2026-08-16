---
name: parts-inventory
description: >-
  Stage 2's entry point. Decompose the target and every compound in the test batch into
  their pieces — domains, pockets, sub-pockets, residue groups, motifs; scaffolds, ring
  systems, linkers, substituents, functional groups, pharmacophore features — and build the
  interaction grid between them. Enforces atom accounting: every heavy atom of every test
  compound belongs to a part, every pocket-lining residue belongs to a sub-region, and every
  cell of the grid is either measured or explicitly out of scope. Writes into the Stage 1
  graph rather than a new one. Use before pocket-anatomy, and whenever a med chemist would
  ask "what about that nitrogen?". Trigger on: "all the pieces", "decompose", "fragments",
  "sub-pockets", "what is this made of", "every compound in the batch", "interaction
  matrix", "which fragment touches what", or /parts-inventory.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, Agent
---

# Parts inventory

**Stage 1 asked what the target is *related to*. Stage 2 asks what everything is *made of*,
and which piece touches which.** Same discipline, different object: where Stage 1 enforced
exhaustiveness over relation types, this enforces it over parts.

The failure is the same one wearing med-chem clothes:

> Asked to characterise a binding site, an agent profiles whatever ligands happen to be
> co-crystallised, reports the residues that recur, and stops. It does not enumerate the
> pocket's sub-regions and check each was examined. It decomposes the interesting compounds,
> not all fifty. And the interaction matrix it produces is sparse in a way nobody can read —
> a missing cell means either *"measured, nothing there"* or *"never looked"*, and nothing
> distinguishes them.

## One graph, not two

**Write into the Stage 1 store.** `PART_OF`, `CONTACTS`, `OCCUPIES`, `HAS_PHARMACOPHORE` and
`COMPLEMENTARY_TO` extend the same `nodes.jsonl` / `edges.jsonl` that the literature axes
populated. Do not start a second graph.

The payoff is that the useful question becomes one query. *"Which fragment in my test batch
engages a sub-pocket residue that is conserved across the promiscuous non-family proteins
Stage 1 found?"* spans a literature axis, a family corpus, a sub-pocket decomposition and an
interaction profile — four hops in one graph, and four incompatible files if Stage 2 had
started fresh.

Node ids follow the Stage 1 rule: derived from what the part *is*, never from who found it,
so two profilers decomposing the same molecule converge on one node.

```
pocket:pdb:1M13/LBD/hydrophobic-lobe    PART_OF  pocket:pdb:1M13/LBD
fragment:murcko:c1ccc2ccccc2c1          OCCUPIES pocket:pdb:1M13/LBD/hydrophobic-lobe
fragment:smarts:[CX3](=O)[OX2H1]        CONTACTS residue:uniprot:O75469/Ser247
```

## The three completeness gates

All arithmetic, none judgement. That is the point — a coverage claim you can check beats a
thoroughness claim you cannot.

**Atom accounting.** Every heavy atom of every test compound belongs to at least one part,
and the partition-forming kinds (`scaffold`, `substituent`, `linker`) tile without overlap.
`PartsInventory.unassigned()` returns the leftovers. **An unassigned atom is an unexamined
liability** — a med chemist reading the report would ask about that nitrogen, and the report
should have already answered.

Hydrogens are excluded from the universe deliberately. They are not where med-chem attention
goes and including them buries the signal.

**Pocket accounting.** Every pocket-lining residue belongs to a named sub-region. A residue
that lines the site and sits in no sub-region was found by the detector and then dropped.

**Cell coverage.** The matrix is |compound parts| × |protein parts|, and every cell is either
measured or explicitly out of scope. `out_of_scope_because` is the honest escape hatch —
*"geometrically unreachable, opposite face of the pocket"* keeps the grid complete without
measuring a cell that cannot exist.

## Guard rails

- **Measured-empty is a finding; unmeasured is an admission.** `InteractionCell.measured`
  distinguishes them and nothing else can. This is the Stage 1 saturated-versus-truncated
  distinction applied to a grid, and it matters for the same reason: a sparse matrix looks
  identical whether it was worked thoroughly or worked in one corner.
- **A fragment that reaches a sub-region and engages nothing there is a result.** Probably the
  most actionable single output of this stage —
  `InteractionMatrix.parts_touching_nothing()` names dead weight, which is either a handle for
  optimisation or a group to delete. It only works because unmeasured cells are excluded from
  it.
- **Two profilers, never one.** They agreed on **47%** of contact residues on a real complex,
  and *neither alone* recovered the canonical contact set while their union did. Record each
  observation per source; `n_sources` is then a free per-cell confidence signal. A single
  profiler is a sample, not a measurement.
- **Watch the agreement figure in both directions.** Far below ~47% usually means one profiler
  is misconfigured. Far *above* usually means they are reading the same upstream geometry and
  are not independent — spurious agreement destroys the signal it appears to strengthen.
- **Every compound in the batch, not the interesting ones.**
  `Anatomy.uninventoried_compounds()` names the omission, because a report covering 40 of 50
  test items reads exactly like one covering all 50.
- **Overlap is chemistry for functional groups and a bug for partitions.** An amide is
  legitimately both a carbonyl and an N-H. A scaffold/substituent split that double-counts an
  atom inflates apparent coverage. `partition_overlaps()` separates the two cases.
- **Check `foreign()` first when coverage looks wrong.** Atom indices claimed but not in the
  universe almost always mean a 0-versus-1 indexing mismatch, which shifts every assignment
  while leaving the totals plausible.
- **Every `PART_OF` and `CONTACTS` edge needs `commentary`.** See below — this is the field
  the visualisation is built on.

## The commentary requirement

`Edge.commentary` is the reading of the connection in domain terms, and it is **not
optional for anatomy edges**. Not *"the fragment contacts Ser247"* — the predicate already
says that. What a med chemist needs is:

> "The single directional contact this ligand makes. Both profilers see it, which is why it
> is the one restraint worth imposing on Stage 3 sampling."

That sentence is what any view putting two nodes side by side displays, and it belongs on the
edge because the edge is where the pair is asserted. A contract validator rejects commentary
that restates the predicate; `KGStore.uncommented_edges()` lists scored edges still missing
one. A scored edge with no commentary is checkable and unusable — it tells a reader that two
things are related by 0.72 of something and leaves them to work out what to do.

## The visualisation this stage exists to feed

Select two nodes in the ego view — click one, shift-click another — and the panel names both,
surfaces the connecting edge's commentary immediately, and hands over the comparison command.
Then:

```
compare_parts fragment:smarts:[CX3](=O)[OX2H1] pocket:pdb:1M13/LBD/polar-rim
```

renders both sides in 3D with linked cameras, each panel **zoomed to the part rather than the
protein**, contacts as sticks coloured by interaction kind, directional contacts dashed, and a
table of which interactions both sides make. The page leads with the graph's own account of
why the pair is together.

Three deliberate choices, explained in [visual-grammar.md](reference/visual-grammar.md):
colour encodes interaction kind rather than chemical element, because the reader already knows
which atom is nitrogen; the redundant channel is dashed-for-directional, because that is the
distinction a med chemist acts on; and the page **states that it does not assert positional
equivalence** between the two sides, since that needs an alignment `compare_structures`
computes and labels an estimate.

If the graph has no `CONTACTS` edges, `compare_parts` falls back to geometry and says so
loudly — every contact comes back typed `hydrophobic`, which is useless for pose reasoning and
is exactly the signal to run a profiler first.

## Working through it

1. **Resolve the batch.** Every `test_item` from the `ProblemSpec`. This is the denominator
   and coverage is unanswerable without it.
2. **Decompose the target.** Pockets from a detector, sub-regions by hand or by clustering the
   lining residues, motifs from Stage 1's `HAS_MOTIF` edges. Build the universe from the
   pocket-lining residue keys.
3. **Decompose every compound.** RDKit Murcko for scaffold, ring perception for ring systems,
   SMARTS for functional groups, a pharmacophore typer for features. Universe = heavy-atom
   indices.
4. **Check the gates before profiling.** `problems()` on each inventory. Fixing an accounting
   error after the matrix is built means rebuilding the matrix.
5. **Profile with two tools, per complex**, and record each observation with its source.
6. **Fill the grid, including the cells with nothing in them.** Mark unreachable pairs out of
   scope with a reason.
7. **Write the graph delta and the commentary**, then hand to `pocket-anatomy` for ranking.

`parts-inventory` says what exists and what was measured; `pocket-anatomy` says what matters.
Keep the split — the first is arithmetic, the second is judgement, and merging them lets
judgement hide inside a coverage number.

## Checking

```bash
reagent report validate --strict reports/<run>/stage2/report.json
```

`anatomy_coverage()` returns the three numbers together, because they fail independently: a
run can account for every atom of every compound and still have measured one corner of the
grid.

## Anti-patterns

- **Decomposing only the compounds that bound.** The test batch includes the ones that did
  not, and their unengaged pieces are the informative half.
- **A sub-pocket per ligand.** Sub-regions are properties of the site, not of who visited it.
  Naming them after ligands guarantees they never generalise.
- **Reporting contact counts.** "Ser247: 14 contacts" pools 14 observations from two profilers
  across seven complexes into one meaningless number. Report recurrence and source count.
- **Treating proximity as contact.** A 4.5 Å cut-off produces a list of neighbours. A profiler
  produces typed, directional interactions. Only the second constrains a pose.
- **Filling `commentary` with the predicate in lower case.** The validator catches the obvious
  cases; the reviewable test is whether it says what to *do*.
- **Building the matrix before the accounting passes.** Every fix afterwards invalidates rows.

## References

- [decomposition-recipes.md](reference/decomposition-recipes.md) — per-kind recipes: which tool, which parameters, what the universe is, and the failure mode of each
- [visual-grammar.md](reference/visual-grammar.md) — the side-by-side view: what each channel encodes, why colour is not element, and what the page refuses to claim
- [matrix-completeness.md](reference/matrix-completeness.md) — filling the grid, legitimate out-of-scope reasons, and reading profiler agreement in both directions
