# Axis methods

Concrete tools for each similarity axis: the command or API call, the parameters
that change the answer, the score's real range, what counts as "similar" on that
scale, and the characteristic way the axis lies to you.

Two rules govern everything below, and both come from the contracts rather than
from taste.

**Each axis writes its own predicate.** The `AxisSpec` in
`reagent.contracts.problem` names the predicate (`SIMILAR_FOLD_TO`,
`SIMILAR_POCKET_TO`, `SHARES_MOTIF`, …) and the score attribute
(`AxisSpec.score_key`). A generic `SIMILAR_TO` edge is unusable downstream,
because "give me templates that share the pocket but are outside the family" is
the query Stage 3 actually asks, and that query needs the axes separated. Read the
predicate from the spec; do not choose one here.

**Scores are normalised within the axis, to the axis's declared `score_range`.**
The graph renderer maps edge width onto the score after normalising by
`AxisSpec.score_range`, so a raw score on a different scale silently
misrepresents strength relative to every other axis — per
`AXIS_REGISTRY_NOTE`, the most likely way this system lies to a reader. If a tool
emits an unbounded score (a BLAST bit score, a DALI Z-score, a ligand count),
either transform it into the declared range and record the transform in the
`MethodStep` parameters, or change the axis's `score_range` in the domain profile.
Do not pass an out-of-range number through.

Store the raw score too, alongside the normalised one, in the edge `attrs`. A
downstream stage that wants the E-value should not have to re-run the search.

## Sequence

Axis defaults in the structural-biology profile: predicate `SIMILAR_SEQUENCE_TO`,
`score_key` `identity`, range `(0.0, 1.0)`, methods `["blast", "mmseqs2",
"jackhmmer"]`.

### BLAST (NCBI web service, no install)

```
# Submit, then poll. The RID comes back in the response body as "RID = <id>".
curl -s -X POST "https://blast.ncbi.nlm.nih.gov/Blast.cgi" \
  -d CMD=Put -d PROGRAM=blastp -d DATABASE=nr \
  -d EXPECT=1e-5 -d HITLIST_SIZE=250 -d QUERY="$SEQ"

curl -s "https://blast.ncbi.nlm.nih.gov/Blast.cgi?CMD=Get&FORMAT_TYPE=JSON2_S&RID=$RID"
```

Parameters that matter: `DATABASE` (`nr` for breadth, `pdb` when you only care
about things with structures, `swissprot` for a clean reviewed set),
`EXPECT` (1e-5 is a reasonable default; 1e-3 for a remote-homology fishing trip),
`HITLIST_SIZE`, and `WORD_SIZE` (default 3 for blastp; reduce to 2 only for very
short queries). Poll no more often than every 10 seconds — the service throttles.

Score range and interpretation: percent identity runs 0-100 (divide by 100 for
the axis), coverage 0-1, E-value from 0 upward with smaller meaning better. As a
guide, above 30 % identity over 70 % coverage is a confident homolog; 20-30 % is
the twilight zone where alignment-based identity is nearly uninformative about
function; below 20 % you should be on the fold axis instead. Always store
`identity`, `coverage`, and `evalue` together — identity over a 40-residue
alignment of a 400-residue protein is not similarity, and identity alone cannot
tell you that.

### MMseqs2 (local, fast, the right tool for a big search)

```
mmseqs createdb target.fasta queryDB
mmseqs createdb reference_set.fasta refDB
mmseqs search queryDB refDB resultDB tmp -s 7.5 -e 1e-5 --max-seqs 1000
mmseqs convertalis queryDB refDB resultDB hits.tsv \
  --format-output "query,target,fident,alnlen,qcov,tcov,evalue,bits"
```

The parameter that decides the answer is `-s` (sensitivity, roughly 1 to 7.5).
The default near 5.7 misses remote homologs; use 7.5 for a neighbourhood sweep
where you can afford the time. `--max-seqs` prunes the prefilter and defaults low
enough to truncate a large family, so set it explicitly. `fident` from
`convertalis` is already a fraction in 0-1, which is what the axis wants.

Characteristic failure: MMseqs2 at low sensitivity returns nothing and looks like
a definitive negative. If a sequence search returns zero hits, re-run at `-s 7.5`
before writing "no sequence neighbours" as a finding.

### jackhmmer (iterative, for remote homology)

```
jackhmmer -N 5 --incE 1e-3 -E 10 --cpu 8 \
  --tblout hits.tbl -A aln.sto target.fasta uniref90.fasta
```

`-N` sets the iteration count; each iteration widens the profile and increases
drift risk. `--incE` is the inclusion threshold that decides which hits build the
next profile and is therefore the parameter that controls whether the search stays
on target.

Characteristic failure: **profile drift**. Five iterations with a loose `--incE`
on a protein with a promiscuous domain will walk the profile into a neighbouring
family and return confident nonsense. Check that the target's own accession stays
the top hit in every iteration, and record `-N` and `--incE` in the `MethodStep`.

### Axis-wide gotcha

Sequence identity is a weak predictor of *pocket* similarity, and that is exactly
the property the downstream stages care about. Two receptors at 60 % identity can
have pockets that differ by hundreds of cubic ångströms. The axis is cheap and
reliable about what it measures; it is not a proxy for transferability. Do not let
it dominate the combined ranking, and say so in the axis's coverage note.

## Fold

Predicate `SIMILAR_FOLD_TO`, `score_key` `tm_score`, range `(0.0, 1.0)`, methods
`["foldseek", "tmalign", "dali", "us-align"]`.

### Foldseek (first choice: fast, structure-database scale)

```
foldseek easy-search target.pdb pdb100 aln.m8 tmp \
  --format-output "query,target,fident,alntmscore,qtmscore,ttmscore,lddt,prob,evalue" \
  -e 0.001 --max-seqs 2000 --alignment-type 2
```

`--alignment-type 2` selects TM-align-style structural alignment and is what makes
the reported TM-score meaningful; the default 3Di+AA mode is faster but its
alignment is not a TM-align alignment. `-e` behaves like a sequence E-value.
Databases are pulled with `foldseek databases PDB pdb100 tmp` (experimental
structures) or `AlphaFoldDB/Proteome` (predicted models); the choice changes the
population you are comparing against and belongs in the `MethodStep`.

**TM-score is length-normalised and asymmetric.** `qtmscore` normalises by the
query length and `ttmscore` by the target's; they differ, sometimes a lot, when
the two proteins differ in size. Pick one convention (normalise by the target of
interest), record which, and use it consistently — mixing them across an axis
makes the ranking meaningless.

Interpretation of TM-score: range 0-1. Above roughly 0.5 the two proteins are
generally taken to share a fold; 0.3 or below is in the range expected for random
pairs, so a TM-score of 0.35 is not weak evidence of shared fold, it is closer to
no evidence. Values between 0.4 and 0.5 deserve a look at the alignment before you
write an edge.

### TM-align and US-align (pairwise, authoritative)

```
TMalign target.pdb candidate.pdb -a T     # -a T normalises by the average length
USalign -mm 0 -ter 0 target.cif candidate.cif
```

Use these to confirm the pairwise scores of your top Foldseek hits — Foldseek's
score is an approximation optimised for throughput. US-align handles nucleic acids
and multi-chain complexes, which TM-align does not; `-ter` controls how chain
termination is treated and gets multi-chain comparisons wrong by default if you
ignore it.

### DALI

Available as a web server (`http://ekhidna2.biocenter.helsinki.fi/dali/`) and
locally as DaliLite. Its output is a **Z-score, not a TM-score**: unbounded above,
with values above about 20 indicating strong structural similarity, 8-20 probable,
and below 2 noise. Because the axis declares `score_range = (0.0, 1.0)` with
`score_key = "tm_score"`, a DALI Z-score cannot go into that field. Either store
the Z-score in `attrs["dali_z"]` and populate `tm_score` from a follow-up
TM-align run, or declare a separate axis with its own honest range. Silently
dividing a Z-score by 100 is the exact failure `AXIS_REGISTRY_NOTE` warns about.

### Axis-wide gotchas

The fold axis needs a structure for the target. If only a prediction exists,
record the prediction's confidence (pLDDT or equivalent) on the edge, because the
fold score inherits the model's error and will be over-trusted downstream
otherwise. Also: fold similarity is dominated by the scaffold, so two proteins
with the same fold and completely different pockets score highly. For
ligand-transfer questions the pocket axis is usually more informative — which is
why they are separate axes.

## Pocket

Predicate `SIMILAR_POCKET_TO`, `score_key` `score`, range `(0.0, 1.0)`, methods
`["fpocket+comparison", "prank", "sitehound", "probis", "apoc"]`.

**Contract note before anything else:** `PREDICATE_DOMAINS` validates
`SIMILAR_POCKET_TO` as Pocket-to-Pocket. So this axis must create `Pocket` nodes
(`pocket:pdb:1M13/LBD`) and `HAS_POCKET` edges from the structure or protein
before it can write a single similarity edge. A delta that writes
`SIMILAR_POCKET_TO` between two `Structure` nodes fails
`validate_referential_integrity`.

### fpocket (detection)

```
fpocket -f structure.pdb -m 3.4 -M 6.2 -i 35 -D 1.73
```

`-m`/`-M` are the minimum and maximum alpha-sphere radii and control what
"pocket" means: raising `-M` merges adjacent subpockets into one large cavity,
lowering it fragments a large cavity into several. `-i` is the minimum number of
alpha spheres per pocket. For a large adaptable pocket the defaults tend to
fragment it, and the fix is to raise `-M` — but that is a modelling decision, not
a detail. Write the parameters down.

Useful outputs per pocket, from `*_info.txt` and the pocket PDB files: druggability
score (0-1, a trained composite), pocket volume in cubic ångströms, hydrophobicity
and polarity scores, and the residue list. Rank by volume and by druggability
separately; they disagree, and for a promiscuous target volume is usually the more
relevant number.

### Comparing two pockets

fpocket detects; it does not compare. For comparison:

- **ProBiS** (`http://probis.cmm.ki.si/`, also ProBiS-Dock/ProBiS-ligands and a
  local ProBiS-CHARMMing) does local structural alignment of binding-site
  surfaces and returns a Z-score plus an alignment. Unbounded score, so normalise
  explicitly.
- **APoc** compares pockets by structural alignment and returns a **PS-score**
  with a P-value. PS-score runs 0-1 and, in the same spirit as TM-score, values
  above roughly 0.4-0.5 with a small P-value indicate genuine pocket similarity.
  This is the cleanest fit to the axis's declared `(0.0, 1.0)` range.
- **PRANK / P2Rank** (`prank predict -f structure.pdb`) is a ligandability
  *ranking* tool, not a comparison tool. Use it to choose which pocket on your
  target is the one to compare, especially when you have no holo structure to
  define the site from.
- **SiteHound** and other energy-grid methods identify sites by probe interaction
  energy and are useful when the pocket is shallow enough that geometric
  detection misses it.

Verify the current endpoints and flag spellings for ProBiS and APoc before
scripting against them — both are academic tools whose web interfaces have changed
and whose local builds are finicky.

### Axis-wide gotchas

**The pocket definition is a free parameter and it dominates the result.** A
pocket defined from a holo structure's ligand contacts (usually every residue
within 4.5 Å of any ligand atom) is not the same pocket fpocket finds on the apo
structure, and the two give different neighbour rankings. State which definition
you used, on the `Pocket` node, in these terms: "residues within 4.5 Å of ligand
X in entry Y" or "fpocket pocket 1 of entry Y at `-M 6.2`".

Second gotcha: pockets computed on apo structures of proteins that undergo induced
fit are not the pockets ligands actually bind. If Stage 2's pocket-dynamics work
exists yet, use its conformer ensemble; if not, record the risk as a limitation
rather than pretending the apo pocket is definitive.

## Motif

Predicate `SHARES_MOTIF`, `score_key` `score`, range `(0.0, 1.0)`, methods
`["esmc-sae", "prosite", "interpro", "3d-motif-search", "pyscomotif"]`.

The learned-feature route is the `esmc-sae-motifs` skill's job — delegate to it
rather than reimplementing here. The rule that skill enforces and that this axis
inherits: **a sparse-autoencoder feature is not evidence until it has a
structural interpretation.** A feature that fires on the target and on 40 other
proteins is a hypothesis; a feature whose firing positions map onto a contiguous
structural element in both is a motif. Emit `SHARES_MOTIF` only for the second
kind, and give the `Motif` node the id form `motif:sae/<model>/<layer>-<feature>`
from the `Node` docstring conventions.

Conventional routes, worth running because they are cheap and interpretable:

```
# PROSITE patterns and profiles against a sequence, via InterProScan (local).
interproscan.sh -i target.fasta -f TSV,JSON -appl PROSITEPATTERNS,PROSITEPROFILES,Pfam,CDD -goterms
```

InterProScan gives you a match per signature with start and end positions. The
signature accession (`PS51843`, `PF00104`) becomes the `Motif` node id
(`motif:prosite/PS51843`). PROSITE patterns are regular expressions, so their
"score" is presence or absence — set the edge score to 1.0 for a pattern match and
record `attrs["match_type"] = "pattern"` so nobody mistakes it for a graded
similarity; PROSITE *profiles* do give a graded score, which needs normalising
against the profile's own cutoff.

Three-dimensional motif search finds spatial arrangements of residues that no
sequence method sees — a catalytic triad, a metal site, a specific hydrogen-bond
geometry. `pyScoMotif` indexes a structure set and searches by residue-pair
distance constraints; RCSB also exposes a structure-motif search through the
Search API's `strucmotif` service, which takes a residue list from a reference
entry and finds recurrences across the archive. Both are position-list driven, so
the motif you search for is a hypothesis you supply — which makes this the axis
most exposed to confirmation bias. Pre-register the motif definition before
searching.

Characteristic failure: a short pattern matches by chance. A three-residue motif
will recur thousands of times across the archive and mean nothing. Report the
expected background frequency alongside the hit count, or the axis produces a long
list of meaningless neighbours.

## Promiscuity

Predicate `PROMISCUOUS_WITH`, `score_key` `breadth_score`, range `(0.0, 1.0)`,
methods `["pdb-ligand-census", "chembl-breadth", "bindingdb"]`.
`PREDICATE_DOMAINS` validates it Protein-to-Protein.

Operationalise promiscuity as **measured breadth of `BINDS`** — the count of
distinct chemotypes a protein is known to bind — never as a literature adjective.
"PXR is promiscuous" is a sentence; "this protein has co-crystallised ligands
spanning 41 Murcko scaffolds" is a measurement.

### The three counting sources

1. **PDB ligand census.** Run the harvest in
   [structured-corpus-harvest.md](structured-corpus-harvest.md) per candidate
   protein and count distinct surviving components after the additive exclude
   list and InChIKey deduplication. Cheap, structural, and biased towards whatever
   is easy to crystallise.
2. **ChEMBL breadth.** Distinct chemotypes with a measured `=` relation activity
   against the target. Broader than the PDB and biased towards drug discovery
   programmes, which means well-funded targets look more promiscuous than they
   are.
3. **BindingDB.** Overlaps ChEMBL heavily; deduplicate on
   `(target, ligand InChIKey, measurement type)` across the two before counting or
   you will double the apparent breadth of any target both curate.

### Counting chemotypes, not rows

```python
from rdkit import Chem, DataStructs
from rdkit.Chem import rdFingerprintGenerator
from rdkit.Chem.Scaffolds import MurckoScaffold
from rdkit.ML.Cluster import Butina

gen = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=2048)


def n_chemotypes(smiles_list: list[str], cutoff: float = 0.4) -> int:
    """Butina clusters at Tanimoto distance `cutoff`. Report the cutoff with the count."""
    mols = [m for m in (Chem.MolFromSmiles(s) for s in set(smiles_list)) if m is not None]
    fps = [gen.GetFingerprint(m) for m in mols]
    dists = []
    for i in range(1, len(fps)):
        sims = DataStructs.BulkTanimotoSimilarity(fps[i], fps[:i])
        dists.extend(1.0 - s for s in sims)
    clusters = Butina.ClusterData(dists, len(fps), cutoff, isDistData=True)
    return len(clusters)
```

Then normalise into the declared 0-1 range. Two defensible transforms:

```python
import math

# (a) Percentile rank of this protein's chemotype count within the candidate set.
#     Honest, interpretable, but only meaningful relative to the set you chose.
def breadth_percentile(counts: dict[str, int], protein: str) -> float:
    vals = sorted(counts.values())
    n_below = sum(1 for v in vals if v < counts[protein])
    return n_below / max(1, len(vals) - 1)

# (b) Saturating log transform against a declared reference scale. Absolute, but the
#     reference constant is a choice you must record.
def breadth_log(n_chemotypes: int, reference: int = 100) -> float:
    return min(1.0, math.log1p(n_chemotypes) / math.log1p(reference))
```

Record which transform, and its constants, in the `MethodStep` and in the edge
`attrs` alongside the raw `n_distinct_ligands`. Two runs using different
transforms produce incomparable graphs.

### Axis-wide gotchas

**Study bias is the dominant confound.** Breadth measured from public data is
partly a measure of how much attention a protein has received. Normalise against
something — the number of distinct publications, or the number of deposited
structures — or at minimum report the raw counts so a reader can see that a target
with 5,784 structures and one with 25 are not being compared on equal footing.

**The valuable neighbours here are often outside the family.** That is the point
of the axis: a protein that shares the *problem* — a large, adaptable, solvent-
exposed pocket that accommodates chemically unrelated ligands — is a useful
transfer source even at 10 % sequence identity and a different fold. A promiscuity
axis that returns only family members has been run wrong.

## Family

Predicate `MEMBER_OF_FAMILY`, `score_key` `confidence_numeric`, range
`(0.0, 1.0)`, methods `["pfam", "interpro", "uniprot-family", "rcsb-search"]`.
`PREDICATE_DOMAINS` validates it Protein-to-Family.

Prefer a structured registry query over literature for this axis; the recipes are
in [structured-corpus-harvest.md](structured-corpus-harvest.md). In short: Pfam or
InterPro accession from InterProScan or from the UniProt entry, then an RCSB
Search API query for that annotation to get the structural corpus, then the
UniProt cross-references to label each entry with its protein.

Note that `confidence_numeric` is not a similarity score — it is how sure you are
that the membership assertion holds. Use 1.0 for a curated InterPro or UniProt
family assignment, and something lower only when you are inferring membership from
a marginal domain hit, in which case record the hit's E-value in `attrs`. Do not
try to smuggle a graded similarity into this field; the family axis's value is
coverage, and coverage is a set, not a ranking.

Characteristic failure: family boundaries are conventions, and different registries
draw them differently. Pfam's domain-level family, InterPro's homologous
superfamily, and a receptor nomenclature committee's subfamily are three different
sets, and "close homolog" for weighting purposes needs to be defined against one
of them explicitly. Name the registry and the accession on the `Family` node.

## Compound

Predicate `SIMILAR_COMPOUND_TO`, `score_key` `tanimoto`, range `(0.0, 1.0)`,
methods `["rdkit-morgan", "rdkit-scaffold", "mces", "shape-tanimoto"]`.
`PREDICATE_DOMAINS` validates it Compound-to-Compound.

Run this on the **test** items, not only on the target's known ligands. The gap
between the two is the domain shift, and measuring it is the highest-value thing
Stage 1 does — see [domain-shift.md](domain-shift.md).

### Morgan fingerprint Tanimoto (the default)

```python
from rdkit import Chem, DataStructs
from rdkit.Chem import rdFingerprintGenerator

# radius=2 is the ECFP4 convention (diameter 4). Report radius and fpSize always:
# a "Tanimoto of 0.35" with unstated parameters is not a reproducible number.
gen = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=2048)

fp_a = gen.GetFingerprint(Chem.MolFromSmiles(smi_a))
fp_b = gen.GetFingerprint(Chem.MolFromSmiles(smi_b))
tanimoto = DataStructs.TanimotoSimilarity(fp_a, fp_b)      # 0.0 - 1.0
```

Interpretation, and this is the parameter-dependent part everyone forgets: with
Morgan radius 2 at 2048 bits, roughly 0.7 and above is "same series", 0.4-0.7 is
"related chemotype", and below about 0.3 is effectively unrelated — around the
level of random drug-like pairs. Those thresholds do not transfer to other
fingerprints. MACCS keys give systematically higher values (0.7 is unremarkable);
path-based fingerprints differ again; and increasing the radius lowers similarity
across the board by making features more specific.

**The characteristic failure is fragments.** Morgan fingerprints are sparse for
small molecules, so a 12-heavy-atom fragment has very few set bits and its
Tanimoto to any larger molecule is low almost regardless of chemistry. In the
reference case the crystallographic fragments had Morgan radius-2 Tanimoto below
0.3 to *every* known holo ligand of the target, and that is partly a real chemical
statement and partly an artefact of comparing molecules of very different size.
Both readings lead to the same conclusion — you cannot transfer a drug-like prior
onto them — but do not report the number without noting the size dependence.
Corroborate with a size-insensitive measure before drawing a conclusion.

### Murcko scaffolds (for census and splitting)

```python
from rdkit.Chem.Scaffolds import MurckoScaffold

mol = Chem.MolFromSmiles(smi)
scaffold = MurckoScaffold.GetScaffoldForMol(mol)                 # keeps atom types
generic = MurckoScaffold.MakeScaffoldGeneric(scaffold)           # all atoms -> C, all bonds -> single
scaffold_smiles = Chem.MolToSmiles(scaffold)
```

Scaffold identity is binary, which makes it the right basis for an honest
train/test split (a random split flatters every chemical model) and for a
chemotype census. The generic form merges heteroatom-substituted analogues and is
usually what you want for counting distinct chemotypes. Note that acyclic
molecules have an empty Murcko scaffold — every one of them collapses into a
single "scaffold", which will quietly ruin a scaffold split on a fragment set.

### MCES (maximum common edge subgraph)

Graph-based similarity that does not depend on fingerprint bit collisions and is
much less size-biased than Morgan Tanimoto, which makes it the right corroborating
measure for fragment comparisons. RDKit's `rdFMCS.FindMCS` is the accessible
implementation:

```python
from rdkit.Chem import rdFMCS

res = rdFMCS.FindMCS(
    [mol_a, mol_b],
    ringMatchesRingOnly=True,
    completeRingsOnly=True,
    bondCompare=rdFMCS.BondCompare.CompareOrderExact,
    timeout=10,                # seconds; MCS is NP-hard and WILL hang without this
)
# Normalise into 0-1 as a fraction of the smaller molecule's bonds.
mces_sim = res.numBonds / min(mol_a.GetNumBonds(), mol_b.GetNumBonds())
```

The `timeout` is not optional, and a timed-out MCS returns a *partial* result
rather than an error — check `res.canceled` before using the number. Note also
that normalising by the smaller molecule versus by the union gives systematically
different values; pick one, record it.

### Shape Tanimoto (three-dimensional)

```python
from rdkit.Chem import AllChem, rdShapeHelpers

for m in (mol_a, mol_b):
    AllChem.EmbedMolecule(m, randomSeed=0xF00D)
    AllChem.MMFFOptimizeMolecule(m)
AllChem.AlignMol(mol_a, mol_b)
shape_sim = 1.0 - rdShapeHelpers.ShapeTanimotoDist(mol_a, mol_b)
```

Useful when the question is "could this occupy the same pocket volume" rather than
"is this the same chemistry", which is often the more relevant question for a
promiscuous pocket. The characteristic failure is conformer dependence: the number
depends entirely on which conformer you embedded and how you aligned. Use an
ensemble (`EmbedMultipleConfs` with a fixed `randomSeed`) and report the best or
the median over the ensemble, saying which. A single-conformer shape Tanimoto is
not reproducible across runs.

## Recording the axis honestly

Every axis is done when it has produced three things, and a `MethodStep` for one
axis should let a reader reproduce it exactly:

1. **Edges with real scores**, each carrying the raw score and the normalised
   score, the tool name, and the tool version.
2. **A `MethodStep`** with every parameter that changes the answer — sensitivity,
   alignment type, radius, cutoff, pocket definition, normalisation transform.
3. **An explicit statement of what the axis could not cover.** "Fold axis run
   against `pdb100` only; predicted-structure space not searched" is a finding.
   Silence reads downstream as "there is nothing there".

If a tool was unavailable and you fell back to the second method in
`AxisSpec.methods`, say which one ran and why. If no measurement was possible, the
edge is `Confidence.SPECULATIVE` with `attrs["illustrative"] = True`, or it is not
written at all. A plausible number is worse than a missing one, because everything
downstream treats the graph as fact.
