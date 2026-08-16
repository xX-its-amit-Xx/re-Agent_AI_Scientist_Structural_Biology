# Which source serves which relation

For each layer: the database, the predicate it populates, **what its score actually means**, and
where its coverage stops. The third column is the one that matters — most of these expose a
number that looks like a confidence and is not.

---

## Protein–protein interaction

| Source | Predicate | Score meaning | Coverage limit |
|---|---|---|---|
| IntAct | `INTERACTS_WITH` | MI score from curated experimental evidence | curation lag; binary interactions over-represented |
| BioGRID | `INTERACTS_WITH` | none — it is an evidence list | includes genetic interactions, which are *not* physical |
| STRING | `INTERACTS_WITH` | **combined score, not physical evidence** | see below |
| Complex Portal / CORUM | `INTERACTS_WITH` (obligate) | manually curated complexes | small, high precision |
| PDB co-crystals | `CO_CRYSTALLIZED_WITH` | resolution, interface area | only what crystallised together |

**STRING is the trap.** Its combined score aggregates text-mining, co-expression, genomic
neighbourhood and database transfer alongside experiment. A 0.9 combined score can come almost
entirely from two proteins being mentioned together in abstracts. Either filter to the
`experiments` channel or put the channel in the edge's `commentary` — *"STRING 0.91, of which
0.12 experimental; the rest is text-mining"* is honest and usable, and a bare 0.91 is neither.

**And genetic interaction is not physical interaction.** BioGRID mixes them. A synthetic-lethal
pair may never touch.

**Budget warning.** A PPI query returns hundreds of partners. Set `max_per_predicate` before
running `INTERACTS_WITH` or it will consume the entire walk.

---

## Pathway and cascade

| Source | Predicate | Score meaning | Coverage limit |
|---|---|---|---|
| Reactome | `IN_PATHWAY`, `UPSTREAM_OF` | none; curated event hierarchy | human-centric; hierarchical depth varies by area |
| KEGG | `IN_PATHWAY` | none | licensing restrictions on bulk use |
| WikiPathways | `IN_PATHWAY` | none; community-curated | quality varies by pathway |
| SIGNOR | `UPSTREAM_OF`, `INHIBITS` | signed, directed causal statements | signalling only |

**Prefer the smallest pathway containing both entities.** "Metabolism" as a shared pathway is a
hub and says nothing. Reactome's hierarchy makes this checkable — go as deep as the annotation
supports.

**SIGNOR is under-used and worth knowing.** It gives *signed and directed* causal relations,
which is what `UPSTREAM_OF` and `TRANSCRIPTIONALLY_ACTIVATES` actually need; most pathway
databases give unsigned membership and leave the direction to be inferred.

---

## Transcriptional control

| Source | Predicate | Score meaning | Coverage limit |
|---|---|---|---|
| ChIP-Atlas / ReMap | `BINDS_PROMOTER_OF` | peak score, MACS2 q-value | binding ≠ regulation |
| TRRUST / DoRothEA | `TRANSCRIPTIONALLY_ACTIVATES` / `_REPRESSES` | DoRothEA confidence level A–E | curated TF sets, human/mouse |
| JASPAR | motif for `BINDS_PROMOTER_OF` attrs | information content | motif ≠ occupancy |
| GTRD | `BINDS_PROMOTER_OF` | meta-cluster support | ChIP-seq only |

**Binding a promoter is not regulating a gene.** ChIP peaks vastly outnumber functional
regulatory events. When you have both, `BINDS_PROMOTER_OF` from ChIP and
`TRANSCRIPTIONALLY_ACTIVATES` from a perturbation experiment are different claims and should be
different edges — the commentary should say which one you have.

**For a ligand-activated transcription factor this layer is the entire output of binding.** A
graph that records what binds the target but not what the target then transcribes has stopped
one step short of why anyone cares. For PXR specifically, the chain
`ligand → PXR → CYP3A4 → drug clearance` is the clinical significance.

---

## RNA regulation and silencing

| Source | Predicate | Score meaning | Coverage limit |
|---|---|---|---|
| miRTarBase | `TARGETS_TRANSCRIPT` | experimental support level | validated subset is small |
| TargetScan | `TARGETS_TRANSCRIPT` | context++ score — a **prediction** | predictions vastly outnumber validated targets |
| RNAcentral | RNA node identity | — | identity only |
| GenomeRNAi / BioGRID ORCS | `SILENCED_BY` | screen hit score | screen-specific; many false negatives |

**Keep predicted and validated miRNA targets apart.** TargetScan will return dozens of
predictions per gene; treating them as edges of the same standing as a validated one floods the
regulatory layer with noise. Put the support level in `attrs.validated` and cap confidence at
`tentative` for predictions.

**Knockdown evidence is directional evidence about function, not about binding.** A miRNA that
reduces the target's protein level tells you the transcript is regulated; it says nothing about
the pocket.

---

## Splice isoforms and variants

| Source | Predicate | Score meaning | Coverage limit |
|---|---|---|---|
| Ensembl / APPRIS | `HAS_ISOFORM`, `SPLICE_VARIANT_OF` | APPRIS principal-isoform annotation | annotation, not expression |
| UniProt isoforms | `HAS_ISOFORM` | curated | canonical choice is a curation decision |
| GTEx / isoform atlases | isoform `attrs.expression` | TPM | tissue-level, not cell-level |
| gnomAD | `HAS_VARIANT` | allele frequency | population coverage uneven |
| ClinVar | `HAS_VARIANT` + `VARIANT_AFFECTS` | clinical significance, review status | assertion quality varies enormously |
| dbNSFP / AlphaMissense | `VARIANT_AFFECTS` attrs | predicted pathogenicity | prediction, not measurement |

**This is the layer most likely to be silently wrong, and the reason `GENE` is its own node
type.** An exon-skipping event that removes part of the ligand-binding domain produces an
isoform whose pocket does not exist. Pooling its activity data with the canonical form averages
two different proteins — and if isoforms hang off the protein node as attributes rather than
their own nodes, nothing in the graph can express the distinction.

**So always check whether an isoform shares the pocket** before letting its data into a
pocket-level claim. `SPLICE_VARIANT_OF.attrs.functional_effect` is where that goes.

**For variants, the question is whether it touches the site.** Use `VARIANT_AFFECTS` pointing at
the pocket or residue, not just at the protein. A variant in a distal loop and a variant in the
polar rim are different findings and the graph should not flatten them.

---

## Orthology

| Source | Predicate | Score meaning | Coverage limit |
|---|---|---|---|
| OrthoDB / Ensembl Compara | `ORTHOLOG_OF` | ortholog confidence | one-to-many relations are common and awkward |
| UniProt | `ORTHOLOG_OF` | curated | sparse |

**Record `pocket_identity` separately from full-length identity.** For xenobiotic sensors the
pocket is *poorly* conserved across species — that is the well-known reason rodent predictions
transfer badly — so an orthologue at 80% full-length identity can be useless as a data source.
The full-length number is the misleading one, and it is the one every database gives you.

---

## Drug–drug interaction and ADME

| Source | Predicate | Score meaning | Coverage limit |
|---|---|---|---|
| DrugBank | `INTERACTS_CLINICALLY_WITH`, `METABOLIZED_BY` | severity category | licence restricts redistribution |
| DrugCentral | `METABOLIZED_BY`, `TRANSPORTED_BY` | — | approved drugs only |
| FDA labelling / DDInter | `INTERACTS_CLINICALLY_WITH` | severity | mechanism often absent |
| ChEMBL | `INHIBITS`, `INDUCES` | measured IC50/EC50 with assay | assay heterogeneity |
| PharmGKB | `VARIANT_AFFECTS` + clinical | evidence level 1A–4 | pharmacogenomics only |

**`via` is the field that makes a DDI usable.** A DDI recorded without its mechanism is a warning
label. Recorded as *"rifampicin induces PXR, which transcribes CYP3A4, which clears the other
drug"* it is a causal chain the graph can check, a model can use, and a reviewer can disagree
with. Most DDI sources give you the pair and the severity and omit the mechanism — the mechanism
usually has to come from the label text or the literature.

**Induction and inhibition are opposite and both are "an interaction".** Keep them as
`INDUCES` and `INHIBITS` rather than collapsing into `MODULATES`, because the clinical direction
is the whole content.

---

## What no source gives you

- **The endogenous ligand.** Databases record what was crystallised; *"this is the physiological
  ligand"* is a claim someone argued in prose. Route it through `literature-harvest`, and
  through `neglected-literature` when it is contested — a disputed endogenous ligand is exactly
  where the low-citation dissenting paper matters.
- **Whether a canonical binding mode exists at all.** Reasoning, not retrieval. See
  `binder-census`.
- **The analogous cascade role.** No index holds *"whose cascade has a slot shaped like mine?"*.
  See `target-properties`.

Those three are why the checklist gate matters more than the walk. Expansion goes deep along
relations that exist in a database; the checklist forces an answer on the ones that do not.
