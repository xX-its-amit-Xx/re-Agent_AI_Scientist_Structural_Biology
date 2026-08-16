---
name: binder-census
description: >-
  Find everything observed to bind a target and classify what kind of binder each one is —
  endogenous ligand, substrate, cofactor, drug designed for it, drug designed for something
  else, tool compound, fragment, covalent warhead, or crystallisation artefact. Names and
  excludes the buffer and cryoprotectant that a raw PDB census returns as ligands. Then
  decides whether a reference binding mode exists at all, and records what follows when it
  does not. Run for the target and for every compound of interest. Trigger on: "what binds
  this", "all known ligands", "canonical binder", "intended binding mode", "endogenous
  ligand", "is this a real ligand", "promiscuity", "ligand census", or /binder-census.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, WebSearch, WebFetch, Agent
---

# Binder census

Two questions, and the second has a trap in it.

1. **What binds this target?** Everything — not the ligands someone found interesting.
2. **What binding mode was it built for?** Which may have no answer, and the absence is the
   most decision-relevant thing this skill can report.

## Everything that binds is not everything in the HETATM records

A census pulled from the PDB without a deny list returns **glycerol, ethylene glycol, PEG
fragments, sulfate, DMSO, acetate, imidazole and MPD**. Buffer, cryoprotectant, precipitant.
Present in the crystal, absent from the biology, and once they are in the census they pollute
everything downstream: pharmacophore models built on "all ligands", promiscuity counts,
sub-pocket occupancy, the interaction matrix.

**Filtering by atom count does not fix this.** Glycerol has six heavy atoms and passes exactly
the threshold a real fragment hit passes. Nothing about the molecule distinguishes a
cryoprotectant from a fragment — what distinguishes them is knowing glycerol was in the drop.
So `ALWAYS_ARTEFACT` in `contracts/biology.py` is a curated code list, and
`misclassified_artefacts()` catches the ones that slipped through as arithmetic rather than
judgement.

**And a second list, because auto-classifying would be wrong.** `CONTEXT_DEPENDENT` holds
metals, cofactors, lipids and sugars — codes whose status depends on the protein. A zinc
tetrahedrally coordinated by three conserved cysteines is structural; a zinc at 1.2 σ in one of
eleven structures from the same crystal form is noise. Palmitic acid is a contaminant in one
structure and the physiological ligand in another. The contract requires real reasoning for
these — coordination geometry, conservation, occupancy, how many independent crystal forms —
and rejects a one-clause justification, because a metal silently kept or silently dropped
produces a plausible census either way and a wrong pocket statement nothing detects.

## The intended binding mode may not exist

For a xenobiotic sensor, **breadth is the function.** The protein evolved to recognise
molecules it has never encountered, so there is no single endogenous ligand whose pose defines
a reference. `BindingModeReference.is_defined` is allowed to be False, and for a promiscuous
target it usually should be.

This is not a philosophical point. **It has already cost this project's reference case points.**
Fragment ligands engaged *zero* canonical anchors, so an anchor-based prior applied uniformly
**inverted** on the fragment half of the test set — the prior actively made predictions worse,
and it looked better-informed than having none. So:

- `anchor_policy="required"` is a **validation error** when no mode is defined.
- `anchor_policy="additive"` is the default: engaging an anchor is a bonus, not engaging one is
  never a penalty.
- Claiming `"required"` needs an argument that *every subpopulation* engages them. Fragments,
  covalent binders and allosteric ligands routinely do not.

What follows from an undefined mode is concrete and belongs in the report: no single-conformer
prior, no uniform anchor bonus, and an ensemble sized to the **observed conformational range**
rather than to the best-resolution structure. Put the range in `conformational_range`; it is
what Stage 3 needs to size its ensemble.

## Guard rails

- **Classify by what the pose is evidence *of*.** An endogenous ligand's pose is evidence about
  what the protein was selected for. A marketed drug's pose is evidence about what medicinal
  chemistry achieved. A cryoprotectant's pose is evidence about the freezing protocol. Pooling
  them and calling the result "the binding mode" is the error the taxonomy exists to prevent —
  `informs_intended_mode` and `informs_druggability` keep them apart.
- **Two sources minimum.** Structural databases hold co-crystals; activity databases hold
  binders never crystallised. Either alone is a systematic subset, and `problems()` says so.
- **Record `screening_breadth`.** A protein tested against ten thousand compounds looks
  promiscuous next to one tested against fifty, and the difference is the testing.
  `hit_rate` is the comparable number; a raw count is not.
- **Never leave a het code unclassified.** `unclassified` is a list of holes: each entry is
  neither counted as a binder nor recorded as an artefact, so the census total means nothing.
- **A defined mode needs a canonical binder in the census.** If the reference rests on drugs
  and tool compounds, it describes what chemistry achieved, not what the protein is for.
  Flagged.
- **One structure is not the pocket's grammar.** It is that ligand's interactions.

## Where to look

| Source | What it gives | What it misses |
|---|---|---|
| RCSB / PDBe | co-crystals, het codes, occupancies, resolution | anything never crystallised; and it returns the buffer |
| ChEMBL | measured activities, assay context, screening breadth | no pose; activity ≠ binding site |
| BindingDB | affinities with assay conditions | narrower coverage than ChEMBL |
| PDBe-KB / ligand pages | aggregated ligand-site mappings across entries | curation lag |
| DrugBank / DrugCentral | approved-drug status, targets, ADME role | licensing constraints on redistribution |
| Papers | endogenous-ligand proposals, negative results | slowest, and where the canonical-mode answer usually lives |

The endogenous-ligand question is almost always a literature question, not a database one —
databases record what was crystallised, and "this is the physiological ligand" is a claim
someone argued in prose. Route it through `literature-harvest`, and through
`neglected-literature` when the answer is contested, since a disputed endogenous ligand is
exactly the kind of claim where the low-citation dissenting paper matters.

## Graph output

Write into the same store as everything else. `BINDS` carries `binder_class` in its attrs;
`CO_CRYSTALLIZED_WITH` carries `is_reference_pose` when the complex defines the mode. Artefacts
are recorded as nodes with `binder_class: crystallization_artefact` rather than dropped — **the
exclusion has to be visible**, or the next run rediscovers glycerol and wonders whether it
matters.

Every `BINDS` edge needs `commentary` saying what the binding is evidence of. *"An orthosteric
agonist from a series designed against this target, so its pose shows what chemistry can
achieve here and not what the protein evolved to hold."*

## Doing the same for compounds

The census inverts: for a compound, *"everything it binds"* is its polypharmacology, and the
same classification applies from the other side — which of its targets was it designed for, and
which does it hit incidentally. `SHARES_TARGET_WITH` links compounds by target overlap, and
`INTERACTS_CLINICALLY_WITH` records the drug-drug consequence with `via` naming the mediating
protein.

That `via` field is the point. A DDI recorded without its mechanism is a warning label; recorded
as *"rifampicin induces this target, which transcribes CYP3A4, which clears the other drug"* it
is a causal chain the graph can check and a model can use.

## Anti-patterns

- **Taking the PDB ligand list as the census.** It is a list of what was in the crystal.
- **Reporting a promiscuity count without the screening denominator.**
- **Assuming a canonical mode because the target has a well-studied ligand.** Well-studied is
  not endogenous.
- **Dropping artefacts silently.** Record the exclusion; the next run will otherwise redo the
  work and may reach a different answer.
- **Classifying a metal in four words.** The contract rejects it, and the rejection is the point.
- **Treating an activity measurement as a binding-site claim.** A compound with a measured IC50
  may act allosterically, covalently, or on a partner.

## References

- [artefact-codes.md](reference/artefact-codes.md) — the two code lists, why each entry is there, and how to decide a context-dependent case
- [binder-classes.md](reference/binder-classes.md) — each class: how to recognise it, what its pose is evidence of, and the failure mode of misclassifying it
- [canonical-mode.md](reference/canonical-mode.md) — deciding whether a reference mode exists, with the worked PXR case and what an undefined mode implies for Stages 3 and 4
