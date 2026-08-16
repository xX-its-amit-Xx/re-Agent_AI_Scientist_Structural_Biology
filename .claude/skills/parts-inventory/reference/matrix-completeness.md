# Filling the grid

The matrix is |compound parts| × |protein parts|. For one compound with 8 parts against a pocket
with 5 sub-regions that is 40 cells — small. For 50 test compounds it is 2,000, which is where
the temptation to measure a corner and report a characterisation comes from.

## The distinction the whole grid rests on

| Cell state | Meaning | Field |
|---|---|---|
| contacts recorded | this piece engages that piece | `observations` non-empty |
| **measured, empty** | **this piece was examined against that piece and engages nothing** | `measured=True`, no observations |
| out of scope | cannot interact, with a reason | `out_of_scope_because` set |
| unmeasured | **unknown** | `measured=False`, no reason |
| absent | no cell at all — worse than unmeasured, because it is invisible | not in `cells` |

**A measured-empty cell is a finding. An unmeasured cell is an admission.** Nothing except the
`measured` flag distinguishes them, and a matrix that conflates them looks identical whether it
was worked thoroughly or worked in one corner.

This is exactly the `saturated` versus `truncated` distinction from Stage 1's axis sweeps,
applied to a grid instead of a search. Same reason, same asymmetry: what was never examined
leaves no trace in a report listing what was found.

## Why measured-empty is the valuable output

`parts_touching_nothing()` returns compound parts that were measured against **every** protein
part and engage none of them. That is:

- **dead weight** — a substituent adding molecular weight and no affinity, a candidate for
  deletion; or
- **a handle** — a group pointing into solvent, which is where you attach a solubilising tail
  or a linker without disturbing the binding mode.

Either way it is directly actionable, and it is only computable because unmeasured cells are
excluded. The function returns nothing for a part with any unexamined cell — deliberately, since
"engages nothing we looked at" is not "engages nothing".

## Legitimate out-of-scope reasons

Keeping the grid complete without measuring every cell:

- **Geometrically unreachable.** *"The substituent is 14 Å from this sub-region in every holo
  structure; no conformer brings them within contact distance."*
- **Opposite face.** *"This sub-region lines the coactivator interface, not the ligand pocket."*
- **Different chain.** *"This residue group belongs to the RXR partner, and the ligand is in the
  PXR subunit."* Worth stating explicitly — chain confusion has already cost this project
  once, when chain selection by length picked a partner protein and gave 26% identity instead of
  44%.
- **No coordinates.** *"This sub-region is disordered in all five structures."* Note this is
  different from "we did not look".

Not legitimate: *"unlikely"*, *"low priority"*, *"probably nothing there"*. Those are
predictions, and a prediction is what measuring the cell would test.

## Profiler agreement, read in both directions

The reference figure: two profilers agreed on about **47%** of contact residues on a real
complex, and *neither alone* recovered the canonical contact set while their union did.

`profiler_agreement()` returns the fraction of contacts seen by more than one source.

**Far below ~15%** — one profiler is probably misconfigured. Check the openbabel build (PLIP
crashes on every ligand with the pip wheel, no InChI format) and that ProLIF is running from a
real `.py` behind a `__main__` guard rather than from stdin.

**Far above ~90%** — suspicious in the other direction. Usually it means both profilers are
reading the same upstream geometry — the same protonation, the same pose, the same water model —
and are not independent. **Spurious agreement destroys the confidence signal it appears to
strengthen**, which is the same failure as decorrelating agents by persona: two things that look
different and share their inputs are one thing.

Around 40–60% is what genuine partial independence looks like. Record both sources per
observation rather than merging them; `n_sources` on a cell is then free.

## Recurrence

`recurrence` is the fraction of examined complexes in which any contact was seen for that cell.
It needs `n_complexes_examined` set, and it is what separates an anchor from an idiosyncrasy.

**Derive the matrix from many complexes, not one.** A single co-crystal gives that ligand's
interactions, not the pocket's grammar.

And the trap this project has already recorded: in the reference case, **fragment ligands engaged
zero canonical anchors**, so an anchor-based prior applied uniformly *inverted* on the fragment
half of the test set. High recurrence across drug-like ligands says nothing about fragments.
Report recurrence per subpopulation using Stage 1's `subpopulations` labels, or the number is a
weighted average of two different pockets.

## Batch coverage

`Anatomy.uninventoried_compounds()` and `unmatrixed_compounds()` name test items that were
skipped. Both exist because a report covering 40 of 50 reads exactly like one covering all 50 —
the missing ten leave no gap on the page.

Three numbers, reported together by `anatomy_coverage()`, because they fail independently:

- **target_parts** — fraction of pocket-lining residues assigned to a sub-region
- **test_batch** — fraction of test compounds decomposed
- **matrix_cells** — mean cell coverage across matrices

A run can score 100% on the first two and 12% on the third. That is the common shape, and
reporting only the first two would describe it as complete.

## Costing the grid

Two profilers × N complexes × M compounds is the real cost, and it is linear in each. Levers, in
order of preference:

1. **Reduce protein parts** by merging sub-regions that no compound distinguishes — measurable,
   since two sub-regions with identical columns across every compound are one sub-region.
2. **Mark unreachable cells out of scope** rather than measuring them. Free, and it keeps
   coverage honest.
3. **Reduce complexes**, accepting that recurrence gets noisier. Say so.

What not to do is measure a subset of cells and leave the rest with no status. That converts a
visible budget constraint into an invisible completeness claim, which is the trade this whole
contract exists to prevent.
