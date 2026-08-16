# Decomposition recipes, per part kind

For each: what the universe is, which tool, and the specific way it goes wrong. The last column
is the one to read — a part recorded sloppily is worse than one not recorded, because it counts
toward coverage.

---

## Compound side

Universe = **heavy-atom indices** of the molecule as RDKit numbers them. Hydrogens excluded
deliberately: they are not where med-chem attention goes, and including them roughly doubles the
universe while adding nothing a reader would ask about.

### `scaffold` — the Murcko core
`rdkit.Chem.Scaffolds.MurckoScaffold.GetScaffoldForMol`, then map back to atom indices with a
substructure match on the parent.

**Partition member.** Must tile with substituents and linkers.

**Failure:** confusing the generic scaffold (topology only, all atoms carbon, all bonds single)
with the concrete one. Generic groups far more broadly. State which you used in `attrs` — the
train/test split it implies differs enormously, and two runs disagreeing on this silently
disagree about everything downstream.

**Failure:** a molecule with no rings has no Murcko scaffold. Acyclic test items return empty
and the whole molecule becomes substituent, which is correct and looks like a bug.

### `ring_system` — one fused system
`mol.GetRingInfo().AtomRings()`, merged on shared atoms.

**Failure:** treating each SSSR ring as separate. A fused bicyclic is one system for med-chem
purposes; splitting it produces two parts that always co-occur and never discriminate.

### `linker` — what joins two ring systems
Atoms on the shortest path between two ring systems, excluding the systems themselves.

**Partition member.**

**Failure:** including the attachment atoms, which double-counts against the ring systems and
trips `partition_overlaps()`. That check exists because of this specific mistake.

### `substituent` — a decoration hanging off the core
Connected components after removing the scaffold.

**Partition member.** Together with scaffold and linker, these must cover every heavy atom.

**Failure:** merging two substituents that happen to be adjacent in the index order. Use
connectivity, not index runs.

### `functional_group` — carbonyl, sulfonamide, carboxylate…
SMARTS matching. A curated pattern list beats a generated one; the standard med-chem set is
about 60 patterns and covers most of what matters.

**Not a partition member.** An amide is legitimately both a carbonyl and an N-H, and forcing
those apart would be chemistry-by-schema. Overlap here is expected and correct.

**Failure:** listing a group without its `role`. "Contains a carbonyl" is not a claim; "a
carbonyl positioned to accept from the Ser247 hydroxyl" is. The `role` field is where the
med-chem content lives.

### `pharmacophore` — a typed feature
Donor, acceptor, hydrophobe, aromatic centroid, positive/negative ionisable. RDKit's feature
factory or a hand-rolled SMARTS set.

Gets its own node type (`NodeType.PHARMACOPHORE`) because a med chemist treats *"an acceptor
4.2 Å from an aromatic centroid"* as an object in its own right, and its semantics — a typed
point with a direction — match nothing else in the vocabulary.

**Failure:** protonation state. A carboxylate is an anion at pH 7.4 and neutral in a
gas-phase-optimised structure, and the two give different features. Record the assumed pH in
`attrs`; a pharmacophore with no stated protonation state is not reproducible.

### `stereocenter` / `rotatable_bond`
`FindMolChiralCenters`, and the standard rotatable-bond SMARTS.

**Not partition members** — these describe relations rather than regions, so `covers` may be
empty. That exemption is in the `Part` validator.

**Failure:** treating rotatable-bond count as a proxy for flexibility without checking whether
the rotations are inside a ring system, where they do nothing.

---

## Protein side

Universe = **pocket-lining residue keys**, as the graph names them
(`residue:uniprot:O75469/Ser247`). Not every residue in the protein — the site is the subject,
and using the whole chain makes coverage meaningless.

### `pocket` — the whole site
fpocket, CASTp, or the ligand-derived envelope.

**Failure, already made in this project:** measuring the pocket from the ligand *centroid*
instead of from every ligand atom. That returned 5 lining residues where the correct answer was
35. `Structure.residues_near` takes a point set for this reason — pass every atom.

### `subpocket` — a named lobe or channel
Cluster the lining residues by spatial position and physicochemical character, or take them from
the literature where the field has already named them.

**Partition member.** Every lining residue in exactly one sub-region.

**Failure:** naming sub-regions after the ligands that visited them. Sub-regions are properties
of the *site*; ligand-named ones never generalise, and the second compound needs a new
vocabulary.

**Failure:** a sub-region whose members are not nodes in the graph. It then claims to cover
residues the graph has never heard of, and `foreign()` catches it. The demo fixture hit exactly
this and needed its apolar wall residues added as nodes.

### `residue_group` — a co-acting set
A catalytic triad, a hydrophobic wall, a charge clamp. Overlaps sub-regions freely.

**Not a partition member.** A residue can be in the polar rim and in a charge clamp.

**Failure:** inventing groups with no mechanism. If you cannot say what the members do
*together* that they do not do separately, it is a list, not a group.

### `secondary_element` / `gate`
DSSP for elements; a gate is a residue or element whose movement opens or closes access.

**Failure on gates:** asserting one from a single structure. A gate is defined by *changing*
between states, so it needs at least two.

### `protein_motif`
From Stage 1's `HAS_MOTIF` edges — do not re-derive what the literature stage already found.

**Failure:** reading meaning off an SAE feature index. A learned feature is a *candidate* motif;
its meaning comes from the set of proteins that fire it. Naming it from the index is how a
plausible story gets built on nothing.

---

## Order of operations

1. **Universe first.** Both sides. Without it `unassigned()` returns nothing and every gate
   passes vacuously.
2. **Partition members next**, and check `unassigned()`, `foreign()` and
   `partition_overlaps()` before going further.
3. **Overlapping kinds after** — functional groups, pharmacophores, residue groups. These
   cannot break the accounting, so they are safe to add incrementally.
4. **Only then the matrix.** Fixing an accounting error afterwards invalidates rows, and the
   temptation at that point is to patch the matrix rather than rebuild it.

## Recording an exclusion

`out_of_scope` maps a universe member to why it is excluded. Legitimate:

> `"31": "solvent-exposed methyl on the far face; no lining residue within 8 A in any of the
> five holo structures"`

Not legitimate, and rejected by `lazy_dismissals()`: `"not interesting"`, `"n/a"`, `"skip"`, or
anything under 15 characters. Say what about *this* atom makes a contact implausible, so a
reader can disagree with you.
