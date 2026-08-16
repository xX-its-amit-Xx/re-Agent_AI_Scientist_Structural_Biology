# The two code lists

`contracts/biology.py` holds `ALWAYS_ARTEFACT` (61 codes) and `CONTEXT_DEPENDENT` (56 codes).
`artefact_status()` returns `artefact`, `context_dependent`, or `candidate_binder`.

## Why a curated list rather than a rule

**No property of the molecule separates a cryoprotectant from a fragment hit.** Glycerol has six
heavy atoms, is polar, sits in a pocket, and makes hydrogen bonds — exactly like a real fragment.
The atom-count filter that `Structure.primary_ligand()` uses (`n_atoms >= 6`) passes glycerol and
rejects sulfate, which is precisely backwards from useful: both are artefacts and neither is
distinguishable by size.

What distinguishes them is knowing **glycerol was in the drop**. That is metadata about the
experiment, not chemistry, so it has to be a list.

## `ALWAYS_ARTEFACT`, by why it is there

**Solvent** — `HOH`, `DOD`, `D8U`. Usually stripped upstream, listed for completeness.

**Cryoprotectants and precipitants** — `GOL` (glycerol), `EDO` (ethylene glycol), `MPD`, `MRD`,
`PGE`/`PG4`/`P6G`/`1PE`/`2PE`/`7PE`/`PEG` (PEG fragments of various lengths), `SUC`, `TRE`,
`XYL`, `BU3`, `PDO`, `DEG`, `TOE`. **The PEG fragments are the most numerous single class of
false ligand in the PDB** — a long PEG threads through a groove and looks like a lead.

**Buffers** — `TRS` (Tris), `EPE` (HEPES), `MES`, `IMD` (imidazole), `BCT`, `CIT`, `FLC`, `TLA`
(tartrate), `MLI`/`MLA` (malonate), `ACT`/`ACY` (acetate), `FMT` (formate), `OXL`, `SIN`, `PPI`,
`BTB`, `144`, `NHE`, `CAC`. Imidazole is worth calling out: it comes from nickel-column elution
and lands in histidine-rich sites, which is exactly where a real ligand would also sit.

**Counter-ions and salts** — `SO4`, `PO4`, `NO3`, `SCN`, `BR`, `IOD`, `AZI`, `CO3`, `PER`. Sulfate
and phosphate are frequently modelled into positively charged pockets and are then mistaken for
the phosphate of a real cofactor.

**Reducing agents and reagents** — `BME`, `DTT`, `DTU`, `TCE`, `EOH`, `IPA`, `MOH`, `ACN`, `DMS`
(DMSO), `URE`, `GAI`. **DMSO deserves attention**: it is the screening solvent, it binds in
hydrophobic sub-pockets, and it appears in fragment-screening structures where a fragment is
what you were looking for.

## `CONTEXT_DEPENDENT` — never auto-classify

**Metals** — `ZN`, `MG`, `CA`, `MN`, `FE`/`FE2`, `CU`/`CU1`, `NI`, `CO`, `NA`, `K`, `CD`, `HG`.
Catalytic, structural, or adventitious. `NI` is usually column leachate. `CD` and `HG` are
usually heavy-atom derivatives for phasing. `ZN` is the hard one.

**Cofactors that are also additives** — `NAD`, `NAP`, `FAD`, `FMN`, `SAM`, `SAH`, `ATP`, `ADP`,
`AMP`, `GTP`, `GDP`, `COA`, `HEM`, `HEC`, `PLP`, `TPP`, `B12`. Genuine biology in the right
protein and a soak artefact in the wrong one.

**Lipids and detergents** — `OLA`, `OLC` (monoolein), `PLM` (palmitic acid), `MYR`, `STE`, `CHD`,
`CLR` (cholesterol), `LDA`, `BOG`, `LMT`, `C8E`, `P15`, `PEE`, `PC1`, `D10`, `HTG`, `SDS`.
**The most genuinely ambiguous class.** Monoolein is the lipidic cubic phase for membrane-protein
crystallography and also occupies real lipid-binding sites. Palmitic acid is a contaminant in one
structure and the physiological ligand in another. Cholesterol in a GPCR structure may be either.

**Sugars** — `NAG`, `NDG`, `BMA`, `MAN`, `GAL`, `GLC`, `FUC`, `XYS`. Glycosylation is biology;
sucrose in the drop is not. `NAG` at an asparagine is almost always a real glycan.

## Deciding a context-dependent case

The contract requires more than one clause, and `Binder._context_dependent_needs_real_reasoning`
rejects anything under eight words. Five things that actually decide it:

**Coordination geometry.** *"Tetrahedrally coordinated by Cys23, Cys26, His41 and Cys44"* is
structural zinc. *"Octahedral with five waters"* is a hydrated ion from the buffer.

**Conservation of the coordinating residues.** Run it against the Stage 1 family corpus. A metal
site whose ligating residues are conserved across the family is functional; one coordinated by
residues unique to this protein probably is not.

**Occupancy and B-factor.** A partial-occupancy ion at high B in one structure is adventitious.
Full occupancy with B comparable to the surrounding protein is real.

**How many independent crystal forms show it.** This is the strongest single signal and the one
most often available. Present in eleven structures across three space groups and two labs is
biology; present in one is the crystal.

**Whether the crystallisation condition contained it.** In the PDB entry's own metadata, and
decisive when available. Zinc in the well solution plus zinc in the model is not evidence of a
zinc site.

Worked examples of each phrasing are the *point* of `classified_because` — a reviewer should be
able to disagree with your reasoning, which requires seeing it.

## Recording exclusions rather than dropping them

**Artefacts stay in the graph as nodes with `binder_class: crystallization_artefact`.** The
exclusion has to be visible, for two reasons: the next run otherwise rediscovers glycerol and
spends time wondering, and a reviewer cannot check a filter whose output is invisible.

`BinderCensus.misclassified_artefacts()` catches the inverse failure — a binder carrying an
always-artefact code that was classified as something else — as pure arithmetic. That check
exists because it is the commonest way a census gets polluted and the easiest to miss by eye.

## Keeping the lists current

Both lists are curated and therefore incomplete. When you meet a code that is clearly an additive
and is not listed, add it *with a comment saying why* — a bare code addition is unreviewable, and
these lists are the kind of thing nobody audits after the fact.

The PDB Chemical Component Dictionary is the authority on what a code *is*; it does not say
whether a given instance is biology. That judgement is per-structure and is what
`classified_because` records.
