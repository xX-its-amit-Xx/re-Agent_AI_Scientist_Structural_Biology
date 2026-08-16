# The checklist, item by item

For each: the question it asks, the predicates it licenses, where the answer comes from, and
what goes wrong if you get it wrong. The last column is the one to read — a property answered
sloppily is worse than one dismissed, because it produces a search that looks done.

Get the machine-readable list with `reagent axes checklist --domain <domain>`.

---

## What it is made of

### `sequence_identity`
*Which proteins share detectable sequence identity with the target?*
**Licenses** `SIMILAR_SEQUENCE_TO`. **From** UniProt, MMseqs2, BLAST.
**Failure** Identity computed over the wrong region. A 44% full-length identity can be 70% in
the pocket and 20% elsewhere, and the pocket number is the one that predicts transferability.
Always report the region the number covers.

### `fold`
*Which proteins share the fold at low sequence identity?*
**Licenses** `SIMILAR_FOLD_TO`. **From** Foldseek, TM-align, CATH, ECOD.
**Failure** Chain selection. On a heterodimer with four copies in the asymmetric unit, picking
the longest chain can select the *partner protein* — this has already happened here, on 1XVP,
giving 26% identity to the RXR partner instead of 44% to CAR. Search chain pairs, score by TM.

### `domain_architecture`
*Which proteins have the same arrangement of domains?*
**Licenses** `SIMILAR_FOLD_TO`, `HAS_MOTIF`. **From** InterPro, Pfam, SMART.
**Failure** Matching one domain and ignoring the arrangement. Two proteins sharing a
ligand-binding domain but differing in what is fused to it behave differently in a co-fold,
because the neighbouring domain constrains the pocket.

### `family_membership`
*Which families, subfamilies and superfamilies, and who else is in each?*
**Licenses** `MEMBER_OF_FAMILY`, `HAS_PROPERTY`. **From** UniProt, Pfam, family-specific
nomenclature committees.
**Failure** Stopping at one level. Subfamily gives close relatives with transferable SAR;
superfamily gives the shared mechanism. Both are useful and they answer different questions.

### `motif_content`
*Which local motifs or learned features does it carry, and what else carries them?*
**Licenses** `HAS_MOTIF`, `SHARES_MOTIF`. **From** PROSITE, 3D motif search, ESM-C SAE features.
**Failure** Treating a learned feature as interpretable without checking what else activates
it. An SAE feature is a *candidate* motif; its meaning comes from the set of proteins that fire
it, and reading a label off a feature index is how a plausible story gets built on nothing.

---

## What binds to it

### `pocket_character`
*What kind of pocket, and which unrelated proteins have one of the same character?*
**Licenses** `SIMILAR_POCKET_TO`, `HAS_PROPERTY`. **From** fpocket, CASTp, pocket comparison.
**Failure** Measuring the pocket from a ligand centroid instead of from every ligand atom.
This has already happened here and returned 5 lining residues instead of 35. Pass the whole
point set.

### `pocket_plasticity`
*Does the pocket change shape on binding, and what shares that behaviour?*
**Licenses** `SIMILAR_POCKET_TO`, `HAS_PROPERTY`. **From** comparing apo and holo structures,
multiple holo structures with different ligands, B-factors, MD if available.
**Failure** Concluding rigidity from a single structure. One conformer cannot show plasticity;
absence of evidence here is not evidence of rigidity, and treating it as such is how a
single-template pipeline gets chosen for a target that needed an ensemble.

### `ligand_promiscuity`
*How broad is the ligand range, and which other proteins are similarly promiscuous?*
**Licenses** `PROMISCUOUS_WITH`, breadth over `BINDS`, `HAS_PROPERTY`. **From** ChEMBL,
BindingDB, co-crystal counts, chemotype diversity of known binders.
**Failure** Confusing assay coverage with promiscuity. A protein tested against 10,000
compounds looks promiscuous relative to one tested against 50. Normalise by how much it has
been *screened*, not by raw hit count.

**This property transfers a problem, not a similarity.** Two promiscuous binders share the
adaptable-pocket difficulty: one conformer misrepresents both, cross-docking fails the same way
for both. That can make an *unrelated* promiscuous protein a better template donor than a close
homologue with a rigid pocket — a conclusion a family-first search cannot reach.

### `known_chemotypes`
*Which chemical series engage it, and what else do those series hit?*
**Licenses** `BINDS`, `SHARES_SCAFFOLD`, `SIMILAR_COMPOUND_TO`. **From** ChEMBL, patents, papers.
**Failure** Missing the patent literature, where the densest SAR lives. Paperclip cannot search
patents — use Google Patents, Espacenet, or Lens.org.

### `cofactor_dependence`
*What cofactors or partners does activity require?*
**Licenses** `INTERACTS_WITH`, `COMPETES_WITH`. **From** UniProt, enzyme databases, structures.
**Failure** Modelling the apo protein when the biological unit needs the cofactor, so the
predicted pocket is one that never exists in vivo.

---

## Where it sits in the network

### `pathway_membership`
*Which pathways contain it, and who else is in them?*
**Licenses** `IN_PATHWAY`, `SHARES_PATHWAY_WITH`. **From** Reactome, KEGG, WikiPathways.
**Failure** Using a huge pathway as if it were specific. "Metabolism" as a shared pathway is a
hub and says nothing. Prefer the smallest pathway containing both.

### `cascade_position`
*What is directly upstream and downstream?*
**Licenses** `UPSTREAM_OF`, `MODULATES`. **From** Reactome event hierarchy, regulatory
literature.
**Failure** Recording position without direction. `UPSTREAM_OF` is directed; writing it
backwards inverts every downstream inference built on it.

### `analogous_cascade_role`
*Which proteins occupy the same position in a **different** cascade?*
**Licenses** `ANALOGOUS_ROLE_TO`. **From** manual reasoning over pathway topology; see
[analogous-roles.md](analogous-roles.md).
**Failure** Skipping it. This is the item agents reliably drop, and it is the only one whose
answers no similarity search can produce. Treated at length in its own document.

### `binding_partners`
*Which proteins does it physically interact with, and who else shares those partners?*
**Licenses** `INTERACTS_WITH`, `SHARES_PARTNER_WITH`, `CO_CRYSTALLIZED_WITH`. **From** STRING,
IntAct, BioGRID, co-crystal structures.
**Failure** Taking STRING's combined score as evidence of physical interaction. It aggregates
text-mining and co-expression alongside experimental evidence; filter to experimental channels
or say which channel you used. And always record the partner list in `attrs` — a derived
`SHARES_PARTNER_WITH` edge without the partners is unauditable.

### `shared_regulators`
*What controls it, and what else does that regulator control?*
**Licenses** `MODULATES`, `SHARES_PARTNER_WITH` with `partner_role`. **From** regulatory
databases, TF-target sets.
**Failure** Conflating "regulated by the same thing" with "similar". It means co-regulation,
which implies co-occurrence in time — useful for exposure reasoning, not for structure.

### `complex_membership`
*Does it act as part of an obligate complex, and with whom?*
**Licenses** `INTERACTS_WITH`, `CO_CRYSTALLIZED_WITH`. **From** structures, CORUM, Complex
Portal.
**Failure** Predicting a monomer for an obligate heterodimer. The partner changes the pocket.
For nuclear receptors specifically, the RXR partner is usually present in the crystal and is
part of the functional unit.

---

## Where and when it exists

### `tissue_localisation`
*Where is it expressed, and what else is enriched in the same place?*
**Licenses** `EXPRESSED_IN`, `HAS_PROPERTY`. **From** Human Protein Atlas, GTEx, Expression Atlas.
**Failure** Treating this as metadata. **Co-expression implies co-exposure**: proteins in the
same tissue meet the same chemical matter, so their ligand sets overlap for reasons unrelated
to structure, and assay conditions built for one are often valid for the other.

### `subcellular_localisation`
*Which compartment?*
**Licenses** `HAS_PROPERTY`. **From** UniProt, HPA.
**Failure** Ignoring the pH and ionic environment it implies, which changes protonation states
and therefore which poses are physically available.

### `expression_correlation`
*What is it co-expressed with across tissues or conditions?*
**Licenses** `CO_EXPRESSED_WITH`. **From** GTEx correlation, co-expression atlases.
**Failure** Reading correlation as interaction. It is neither, and it is still useful.

### `inducibility`
*Constitutive or induced, and by what?*
**Licenses** `MODULATES`, `HAS_PROPERTY`. **From** induction literature, reporter assays.
**Failure** Missing that the target regulates its own expression or that of its metabolisers —
which for xenobiotic sensors makes a single-timepoint measurement misleading.

---

## What it does

### `biological_process`
*Which processes, and who else participates?*
**Licenses** `PARTICIPATES_IN`. **From** GO biological process.
**Failure** Using a top-level GO term. A hub again; go as deep in the ontology as the
annotation supports.

### `endogenous_vs_xenobiotic`
*Endogenous ligands, foreign chemicals, or both?*
**Licenses** `HAS_PROPERTY`. **From** function literature.
**Failure** Overlooking that xenobiotic handlers are *selected* for promiscuity — breadth is
their function, not a defect of the assay, and it is the reason a narrow training set will fail
to generalise for them.

### `mechanism_class`
*What kind of molecular machine, and what else is that kind?*
**Licenses** `HAS_PROPERTY`, `MEMBER_OF_FAMILY`. **From** UniProt keywords, family.
**Failure** Collapsing it into family membership. For PXR both land on "ligand-activated
transcription factor", but the mechanism class also includes unrelated ligand-activated TFs
outside the nuclear-receptor superfamily, which is a different population. Do not merge them.

### `conformational_behaviour`
*Rigid, flexible, partly disordered, and what shares that?*
**Licenses** `HAS_PROPERTY`, `SIMILAR_FOLD_TO`. **From** structure ensembles, disorder
predictors, crystallographic B-factors.
**Failure** Ignoring disordered regions because no structure resolves them. Absence in the PDB
is evidence of disorder, not of absence.

### `post_translational`
*Which modifications regulate it, and what else they regulate?*
**Licenses** `HAS_PROPERTY`, `MODULATES`. **From** UniProt, PhosphoSitePlus.
**Failure** Modelling an unmodified sequence when the active form is modified.

---

## How it is studied

### `assay_precedent`
*How does the field measure it, and which targets are measured the same way?*
**Licenses** `SIMILAR_ASSAY_TO`, `MEASURED_IN`, `HAS_DATA`. **From** ChEMBL assay descriptions,
methods sections.
**Failure** Pooling incomparable readouts. A reporter-gene EC50 and a binding Ki are different
quantities; merging them creates a training set with two populations and one label.

### `structural_coverage`
*How much experimental structure exists, in which states?*
**Licenses** `HAS_STRUCTURE`, `HAS_DATA`. **From** RCSB.
**Failure** Counting entries rather than distinct states. Twenty structures of one conformer
with twenty ligands is one conformational observation, and treating it as twenty is how a
confidence estimate becomes fiction.

### `species_conservation`
*How conserved, and which orthologues carry usable data?*
**Licenses** `SIMILAR_SEQUENCE_TO`, `HAS_DATA`. **From** OrthoDB, UniProt.
**Failure** Pooling species data without checking pocket conservation. For xenobiotic sensors
the pocket is *poorly* conserved across species — that is the well-known reason rodent
predictions transfer badly — so orthologue data can be actively misleading.

### `disease_association`
*Which diseases or liabilities?*
**Licenses** `HAS_PROPERTY`, `MODULATES`. **From** OMIM, Open Targets, DisGeNET.
**Failure** Mistaking association for mechanism, and then building a prior on it.

---

## Chemistry-side items (DEL, ADMET, cheminformatics)

### `scaffold_class`
*Which scaffolds define the series, and what else uses them?*
**Licenses** `SHARES_SCAFFOLD`. **From** RDKit Murcko decomposition.
**Failure** Generic vs concrete scaffold confusion. Generic (topology only) groups far more
broadly than concrete; say which you used, since the split it implies differs enormously.

### `functional_group_content`
*Which groups are present, and what do they imply?*
**Licenses** `HAS_FRAGMENT`. **From** SMARTS matching.
**Failure** Listing groups without their role. A carbonyl that can accept a hydrogen bond next
to a polar pocket residue is a checkable claim; "contains a carbonyl" is not.

### `physchem_regime`
*Which region of property space?*
**Licenses** `HAS_PROPERTY`. **From** computed descriptors.
**Failure** Using a rule-of-five style filter as if it were a law rather than a description of
one historical library.

### `synthetic_route_class`
*How is it made, and what shares that chemistry?*
**Licenses** `HAS_PROPERTY`, `SHARES_SCAFFOLD`. **From** reaction schemes, DEL build plans.
**Failure** Ignoring that route determines library bias — which reaction was used decides which
regions of chemical space are even reachable, and therefore what the model can learn.

### `library_design`
*How was the collection built, and what biases does that impose?*
**Licenses** `HAS_PROPERTY`, `DATASET_COVERS`. **From** the library's own documentation.
**Failure** Treating a designed library as a sample of chemical space. It is a sample of
whatever the design enumerated, and a random split over it measures interpolation within that
design rather than generalisation.
