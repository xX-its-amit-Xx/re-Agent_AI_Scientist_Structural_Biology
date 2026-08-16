"""Stage 2: every piece of the target, every piece of every test compound, and the grid
between them.

Stage 1 asked *what is related to the target* and enforced exhaustiveness over **relations**
— a checklist of connection types, each worked until its discovery curve flattened. Stage 2
asks a different question with the same shape: *what is this thing made of, and which piece
touches which*. So the enforcement is exhaustiveness over **parts**, and the failure it
guards against is the same one wearing different clothes.

    Asked to characterise a binding site, an agent profiles the ligands that happen to be
    co-crystallised, reports the residues that recur, and stops. It does not enumerate the
    pocket's sub-regions and check each was examined. It does not decompose every compound
    in the test batch — only the interesting ones. And the interaction matrix it produces is
    sparse in a way that cannot be read: a missing cell means either "measured, nothing
    there" or "never looked", and nothing distinguishes them.

Three mechanisms answer that, and all three are arithmetic rather than judgement.

**Atom accounting.** Every heavy atom of every test compound belongs to at least one part,
and the partition-forming kinds tile without overlap. ``unassigned()`` returns what is left
over, and an unassigned atom is an unexamined liability — a med chemist reading the report
would ask about that nitrogen, and the report should have already answered.

**Pocket accounting.** Every pocket-lining residue belongs to a named sub-region. A residue
that lines the site and sits in no sub-region was found by the detector and then dropped.

**Cell coverage.** The matrix is |compound parts| x |protein parts|, and every cell is either
*measured* or explicitly *out of scope*. A sparse matrix with no coverage record looks
identical whether it was worked thoroughly or worked in one corner — which is the Stage 1
saturated-versus-truncated distinction, applied to a grid.

One inherited discipline worth restating, because it is measured rather than assumed: two
interaction profilers agreed on only **47%** of contact residues on a real complex, and
*neither alone* recovered the canonical contact set while their union did. So a contact is
recorded per source, and how many sources saw it is a free per-cell confidence signal rather
than a detail to average away.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator

from reagent.contracts.evidence import Evidence


class PartKind(str, Enum):
    """A kind of piece. Protein side and compound side, kept in one enum because the
    interaction matrix pairs them and a split enum makes that pairing awkward."""

    # -- protein side ------------------------------------------------------
    DOMAIN = "domain"                  # a structural/functional domain
    POCKET = "pocket"                  # a whole binding site
    SUBPOCKET = "subpocket"            # a named lobe or channel within a pocket
    RESIDUE_GROUP = "residue_group"    # a co-acting set: a catalytic triad, a hydrophobic wall
    RESIDUE = "residue"                # one position
    SECONDARY_ELEMENT = "secondary_element"   # a specific helix, strand, or loop
    PROTEIN_MOTIF = "protein_motif"    # local 3D or sequence motif, incl. learned features
    GATE = "gate"                      # a residue or element that opens/closes access

    # -- compound side -----------------------------------------------------
    SCAFFOLD = "scaffold"              # Murcko core
    RING_SYSTEM = "ring_system"        # one fused ring system
    LINKER = "linker"                  # what joins two ring systems
    SUBSTITUENT = "substituent"        # a decoration hanging off the core
    FUNCTIONAL_GROUP = "functional_group"     # carbonyl, sulfonamide, carboxylate...
    PHARMACOPHORE = "pharmacophore"    # a typed feature: donor, acceptor, hydrophobe, aromatic
    STEREOCENTER = "stereocenter"
    ROTATABLE_BOND = "rotatable_bond"

    @property
    def side(self) -> str:
        return "protein" if self in _PROTEIN_KINDS else "compound"


_PROTEIN_KINDS: frozenset[PartKind] = frozenset({
    PartKind.DOMAIN, PartKind.POCKET, PartKind.SUBPOCKET, PartKind.RESIDUE_GROUP,
    PartKind.RESIDUE, PartKind.SECONDARY_ELEMENT, PartKind.PROTEIN_MOTIF, PartKind.GATE,
})

#: Kinds that must **tile** their entity: cover everything, overlap nothing.
#:
#: Chosen deliberately narrow. A scaffold-plus-substituent decomposition is a genuine
#: partition of a molecule's heavy atoms, and subpockets are a genuine partition of a
#: pocket's lining residues. Functional groups are *not* — an amide is legitimately both a
#: carbonyl and an N-H, and forcing those apart would be chemistry-by-schema.
PARTITION_KINDS: frozenset[PartKind] = frozenset({
    PartKind.SCAFFOLD, PartKind.SUBSTITUENT, PartKind.LINKER, PartKind.SUBPOCKET,
})


class Part(BaseModel):
    """One piece of one entity.

    ``covers`` is what makes the accounting possible. For a compound part it holds
    stringified heavy-atom indices; for a protein part, residue keys. Uniform on purpose —
    the arithmetic that checks completeness does not care which, and a single field means a
    single check.
    """

    id: str = Field(..., description="Namespaced, e.g. 'part:chembl:CHEMBL1200973/scaffold'.")
    kind: PartKind
    of: str = Field(..., description="Graph id of the entity this is a part of.")
    label: str = Field(..., min_length=1, description="What a med chemist would call it.")
    covers: list[str] = Field(
        default_factory=list,
        description=(
            "Heavy-atom indices (compound side) or residue keys (protein side) this part "
            "accounts for. Empty is legal only for kinds that describe a relation rather "
            "than a region, such as a rotatable bond."
        ),
    )
    parent: str | None = Field(
        default=None, description="Enclosing part id, for the containment hierarchy."
    )
    role: str | None = Field(
        default=None,
        description=(
            "What this piece does, in med-chem terms: 'occupies the hydrophobic lobe', "
            "'presents the H-bond donor that reaches Ser247'. Not what it is called."
        ),
    )
    smarts: str | None = Field(default=None, description="SMARTS, for compound parts.")
    attrs: dict[str, float | int | str | bool] = Field(default_factory=dict)
    evidence: list[Evidence] = Field(default_factory=list)

    @property
    def n_covered(self) -> int:
        return len(set(self.covers))

    @model_validator(mode="after")
    def _regions_cover_something(self) -> Part:
        if self.kind in PARTITION_KINDS and not self.covers:
            raise ValueError(
                f"part {self.id!r} is a {self.kind.value}, which must tile its entity, so it "
                "has to say which atoms or residues it covers. A partition member covering "
                "nothing breaks the accounting silently."
            )
        return self


class PartsInventory(BaseModel):
    """Every piece of one entity, with the arithmetic that says whether it is complete.

    ``universe`` is the thing being accounted for: all heavy-atom indices of a compound, or
    all pocket-lining residue keys. Without it, completeness is unanswerable — which is why
    it is required rather than derived.
    """

    entity_id: str
    entity_kind: str = Field(..., description="'compound' or 'protein'.")
    universe: list[str] = Field(
        ...,
        description=(
            "Everything that must be accounted for. Heavy-atom indices for a compound "
            "(hydrogens excluded deliberately — they are not where med-chem attention goes "
            "and including them buries the signal), or pocket-lining residue keys."
        ),
    )
    parts: list[Part] = Field(default_factory=list)
    out_of_scope: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Universe members deliberately excluded, mapped to why. A solvent-exposed tail "
            "with no plausible contact is a legitimate exclusion; 'not interesting' is not."
        ),
    )
    source: str | None = Field(
        default=None, description="Tool that produced the decomposition, e.g. 'rdkit-murcko'."
    )

    # -- accounting --------------------------------------------------------

    def assigned(self) -> set[str]:
        out: set[str] = set()
        for p in self.parts:
            out |= set(p.covers)
        return out

    def unassigned(self) -> list[str]:
        """Universe members in no part and not excluded. **The completeness gate.**"""
        return sorted(set(self.universe) - self.assigned() - set(self.out_of_scope))

    def foreign(self) -> list[str]:
        """Things a part claims to cover that are not in the universe — usually an index
        base mismatch (0- vs 1-indexed atoms), which silently shifts every assignment."""
        return sorted(self.assigned() - set(self.universe))

    def partition_overlaps(self) -> dict[str, list[str]]:
        """Universe members claimed by more than one partition-forming part.

        Overlap among functional groups is chemistry. Overlap among scaffold/substituent
        assignments is a bug, and it inflates apparent coverage.
        """
        seen: dict[str, list[str]] = {}
        for p in self.parts:
            if p.kind not in PARTITION_KINDS:
                continue
            for c in p.covers:
                seen.setdefault(c, []).append(p.id)
        return {c: ids for c, ids in sorted(seen.items()) if len(ids) > 1}

    def orphan_parents(self) -> list[str]:
        """Parts naming a parent that is not in this inventory."""
        ids = {p.id for p in self.parts}
        return sorted({p.parent for p in self.parts if p.parent and p.parent not in ids})

    def by_kind(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for p in self.parts:
            counts[p.kind.value] = counts.get(p.kind.value, 0) + 1
        return dict(sorted(counts.items()))

    @property
    def coverage(self) -> float:
        if not self.universe:
            return 0.0
        return (len(self.universe) - len(self.unassigned())) / len(self.universe)

    def problems(self) -> list[str]:
        out: list[str] = []
        if not self.universe:
            out.append(
                f"{self.entity_id}: empty universe, so completeness cannot be checked. This "
                "is the one field that makes the inventory auditable."
            )
            return out
        if not self.parts:
            out.append(f"{self.entity_id}: no parts recorded")
            return out

        if bad := self.foreign():
            out.append(
                f"{self.entity_id}: parts claim to cover {len(bad)} things outside the "
                f"universe ({bad[:6]}). Usually an index-base mismatch, which shifts every "
                "assignment while leaving the totals looking plausible."
            )
        if missing := self.unassigned():
            out.append(
                f"{self.entity_id}: {len(missing)} of {len(self.universe)} unassigned "
                f"({missing[:8]}). Each is a piece nobody decided about — a med chemist "
                "reading this would ask, and the report should already answer."
            )
        if dup := self.partition_overlaps():
            out.append(
                f"{self.entity_id}: {len(dup)} items claimed by two partition parts "
                f"({list(dup)[:5]}). Functional groups may overlap; a scaffold/substituent "
                "split may not, and overlap inflates apparent coverage."
            )
        if orph := self.orphan_parents():
            out.append(f"{self.entity_id}: parts name missing parents {orph}")
        lazy = [
            k for k, why in self.out_of_scope.items()
            if len((why or "").strip()) < 15
            or why.strip().lower() in {"not interesting", "n/a", "skip", "irrelevant"}
        ]
        if lazy:
            out.append(
                f"{self.entity_id}: {len(lazy)} exclusions with no real reason ({lazy[:5]}). "
                "Say what about this atom or residue makes a contact implausible."
            )
        return out

    def summary(self) -> str:
        lines = [
            f"{self.entity_id} ({self.entity_kind}): {self.coverage:.0%} accounted for, "
            f"{len(self.parts)} parts",
            "  " + ", ".join(f"{k}:{n}" for k, n in self.by_kind().items()),
        ]
        if u := self.unassigned():
            lines.append(f"  UNASSIGNED ({len(u)}): {u[:12]}")
        if self.out_of_scope:
            lines.append(f"  excluded: {len(self.out_of_scope)}")
        return "\n".join(lines)


class ContactKind(str, Enum):
    """Interaction types, as the profilers report them."""

    HBOND_DONOR = "hbond_donor"          # ligand donates
    HBOND_ACCEPTOR = "hbond_acceptor"    # ligand accepts
    HYDROPHOBIC = "hydrophobic"
    PI_STACKING = "pi_stacking"
    PI_CATION = "pi_cation"
    SALT_BRIDGE = "salt_bridge"
    HALOGEN = "halogen"
    WATER_BRIDGE = "water_bridge"
    METAL = "metal_coordination"
    COVALENT = "covalent"

    @property
    def is_directional(self) -> bool:
        """Whether geometry, not just proximity, decides it.

        Matters for pose prediction: a directional contact is a constraint a wrong pose
        violates, while a hydrophobic contact is satisfied by any nearby greasy atom and so
        discriminates much less between poses.
        """
        return self in {
            ContactKind.HBOND_DONOR, ContactKind.HBOND_ACCEPTOR, ContactKind.SALT_BRIDGE,
            ContactKind.HALOGEN, ContactKind.PI_STACKING, ContactKind.PI_CATION,
            ContactKind.METAL, ContactKind.COVALENT,
        }


class ContactObservation(BaseModel):
    """One profiler seeing one contact in one structure.

    Kept as the atomic record rather than folding sources together, because the
    disagreement between profilers is itself the signal — on a real complex two of them
    agreed on 47% of contact residues, and neither alone recovered the canonical set.
    """

    kind: ContactKind
    structure_id: str = Field(..., description="Which complex this was observed in.")
    source: str = Field(..., min_length=1, description="Profiler, e.g. 'plip' or 'prolif'.")
    distance_a: float | None = Field(default=None, gt=0)
    angle_deg: float | None = None
    ligand_atoms: list[str] = Field(default_factory=list)
    residue_atoms: list[str] = Field(default_factory=list)


class InteractionCell(BaseModel):
    """One (compound part, protein part) pair, and what was seen there.

    ``measured`` is the field that makes the matrix readable. An empty cell with
    ``measured=True`` is a finding — this fragment does not engage this sub-region, across
    the complexes examined. An empty cell with ``measured=False`` is an admission. Reporting
    them the same way is how a matrix worked in one corner passes for a matrix worked
    thoroughly.
    """

    compound_part: str
    protein_part: str
    measured: bool = Field(
        default=False,
        description="Whether this pair was actually examined. False means unknown, not absent.",
    )
    observations: list[ContactObservation] = Field(default_factory=list)
    n_complexes_examined: int = Field(default=0, ge=0)
    out_of_scope_because: str | None = Field(
        default=None,
        description=(
            "Why this pair could not interact — geometrically unreachable, opposite faces, "
            "different chains. A legitimate way to keep the matrix honest without measuring "
            "every cell."
        ),
    )

    @model_validator(mode="after")
    def _observations_imply_measurement(self) -> InteractionCell:
        if self.observations and not self.measured:
            raise ValueError(
                f"cell ({self.compound_part}, {self.protein_part}) has observations but is "
                "marked unmeasured"
            )
        if self.observations and self.out_of_scope_because:
            raise ValueError(
                f"cell ({self.compound_part}, {self.protein_part}) is marked out of scope but "
                "has observations, so it was evidently in scope"
            )
        return self

    @property
    def sources(self) -> set[str]:
        return {o.source for o in self.observations}

    @property
    def kinds(self) -> set[ContactKind]:
        return {o.kind for o in self.observations}

    @property
    def n_sources(self) -> int:
        """How many independent profilers saw it. The free confidence signal."""
        return len(self.sources)

    @property
    def recurrence(self) -> float | None:
        """Fraction of examined complexes in which any contact was seen."""
        if not self.n_complexes_examined:
            return None
        seen = {o.structure_id for o in self.observations}
        return len(seen) / self.n_complexes_examined

    @property
    def is_single_source(self) -> bool:
        """True when exactly one profiler saw it — the cells to treat as tentative."""
        return self.n_sources == 1

    @property
    def is_empty_finding(self) -> bool:
        """Measured and nothing there. A result, not a gap."""
        return self.measured and not self.observations


class InteractionMatrix(BaseModel):
    """The grid between one compound's parts and one target's parts.

    This is what "see all the pieces" means operationally: not a list of contacts, but a
    grid whose every cell has a known status. The interesting output is as much the
    ``empty_findings`` as the contacts — a fragment that reaches a sub-region and engages
    nothing there is a specific, actionable med-chem observation.
    """

    compound_id: str
    target_id: str
    compound_parts: list[str] = Field(default_factory=list)
    protein_parts: list[str] = Field(default_factory=list)
    cells: list[InteractionCell] = Field(default_factory=list)
    profilers: list[str] = Field(
        default_factory=list,
        description="Every profiler run. Two minimum — their union recovers what neither does.",
    )

    @property
    def n_possible(self) -> int:
        return len(self.compound_parts) * len(self.protein_parts)

    def _index(self) -> dict[tuple[str, str], InteractionCell]:
        return {(c.compound_part, c.protein_part): c for c in self.cells}

    def missing_cells(self) -> list[tuple[str, str]]:
        """Pairs with no cell at all — neither measured nor excluded."""
        have = set(self._index())
        return [
            (cp, pp)
            for cp in self.compound_parts
            for pp in self.protein_parts
            if (cp, pp) not in have
        ]

    def unmeasured_cells(self) -> list[tuple[str, str]]:
        """Pairs recorded but not examined and not excluded."""
        return [
            (c.compound_part, c.protein_part)
            for c in self.cells
            if not c.measured and not c.out_of_scope_because
        ]

    @property
    def cell_coverage(self) -> float:
        """Fraction of the grid with a known status — measured or excluded."""
        if not self.n_possible:
            return 0.0
        known = sum(1 for c in self.cells if c.measured or c.out_of_scope_because)
        return known / self.n_possible

    def contacts(self) -> list[InteractionCell]:
        return [c for c in self.cells if c.observations]

    def empty_findings(self) -> list[InteractionCell]:
        return [c for c in self.cells if c.is_empty_finding]

    def single_source_contacts(self) -> list[InteractionCell]:
        return [c for c in self.contacts() if c.is_single_source]

    def profiler_agreement(self) -> float | None:
        """Fraction of contacts seen by more than one profiler.

        The reference point measured on a real complex is about **47%**, so a value far
        above that is suspicious — usually it means both profilers were run with the same
        upstream geometry and are not independent. A value far below suggests one of them
        is misconfigured.
        """
        cs = self.contacts()
        if not cs:
            return None
        return sum(1 for c in cs if c.n_sources > 1) / len(cs)

    def parts_touching_nothing(self) -> list[str]:
        """Compound parts measured against everything and engaging nothing.

        A prime med-chem output: dead weight, or a handle for optimisation. Distinguished
        from parts that were simply never measured, which is what makes it usable.
        """
        idx = self._index()
        out = []
        for cp in self.compound_parts:
            cells = [idx.get((cp, pp)) for pp in self.protein_parts]
            present = [c for c in cells if c is not None]
            if not present or len(present) < len(self.protein_parts):
                continue
            if all(c.measured or c.out_of_scope_because for c in present) and not any(
                c.observations for c in present
            ):
                out.append(cp)
        return out

    def problems(self) -> list[str]:
        out: list[str] = []
        if not self.cells:
            out.append(f"{self.compound_id} x {self.target_id}: empty matrix")
            return out
        if len(self.profilers) < 2:
            out.append(
                f"{self.compound_id} x {self.target_id}: {len(self.profilers)} profiler(s). "
                "Two profilers agreed on only 47% of contact residues on a real complex and "
                "neither alone recovered the canonical set — one profiler is a sample, not a "
                "measurement."
            )
        if miss := self.missing_cells():
            out.append(
                f"{len(miss)} of {self.n_possible} cells have no status at all "
                f"({miss[:4]}). A cell with no record is indistinguishable from a measured "
                "absence, which is what makes a sparse matrix unreadable."
            )
        if un := self.unmeasured_cells():
            out.append(f"{len(un)} cells recorded but never examined ({un[:4]})")
        if (agree := self.profiler_agreement()) is not None:
            if agree > 0.9 and len(self.profilers) > 1:
                out.append(
                    f"profiler agreement {agree:.0%} is far above the ~47% reference. Check "
                    "the profilers are genuinely independent rather than reading the same "
                    "upstream geometry — spurious agreement removes the confidence signal."
                )
            elif agree < 0.15:
                out.append(
                    f"profiler agreement {agree:.0%} is far below the ~47% reference, which "
                    "usually means one profiler is misconfigured rather than that the "
                    "contacts are genuinely ambiguous"
                )
        return out

    def summary(self) -> str:
        lines = [
            f"{self.compound_id} x {self.target_id}: {self.cell_coverage:.0%} of "
            f"{self.n_possible} cells have a known status",
            f"  {len(self.contacts())} contacts, {len(self.empty_findings())} measured-empty, "
            f"{len(self.single_source_contacts())} single-source",
        ]
        if (a := self.profiler_agreement()) is not None:
            lines.append(f"  profiler agreement {a:.0%} (reference ~47%)")
        if dead := self.parts_touching_nothing():
            lines.append(f"  parts engaging nothing: {dead}")
        if probs := self.problems():
            lines.append("  problems:")
            lines += [f"    - {p}" for p in probs]
        return "\n".join(lines)


class Anatomy(BaseModel):
    """Stage 2's whole deliverable: the target's pieces, every test compound's pieces, and
    a matrix per compound.

    The batch-level check is the one that catches the Stage 1 failure in Stage 2 clothing:
    decomposing the interesting compounds and reporting a characterisation of the batch.
    ``uninventoried_compounds`` names the omission, because a report that covers 40 of 50
    test items reads exactly like one that covers all 50.
    """

    run_id: str
    target_id: str
    target_inventory: PartsInventory
    compound_inventories: list[PartsInventory] = Field(default_factory=list)
    matrices: list[InteractionMatrix] = Field(default_factory=list)
    test_batch: list[str] = Field(
        ...,
        description=(
            "Every compound in the test batch, from the ProblemSpec. Required, because "
            "completeness over the batch is unanswerable without the denominator."
        ),
    )

    def uninventoried_compounds(self) -> list[str]:
        have = {i.entity_id for i in self.compound_inventories}
        return [c for c in self.test_batch if c not in have]

    def unmatrixed_compounds(self) -> list[str]:
        have = {m.compound_id for m in self.matrices}
        return [c for c in self.test_batch if c not in have]

    def batch_coverage(self) -> float:
        if not self.test_batch:
            return 0.0
        done = len(self.test_batch) - len(self.uninventoried_compounds())
        return done / len(self.test_batch)

    def problems(self) -> list[str]:
        out: list[str] = []
        out += [f"target: {p}" for p in self.target_inventory.problems()]
        if missing := self.uninventoried_compounds():
            out.append(
                f"{len(missing)} of {len(self.test_batch)} test compounds were never "
                f"decomposed ({missing[:6]}). A report covering part of the batch reads "
                "exactly like one covering all of it."
            )
        if nomat := self.unmatrixed_compounds():
            out.append(
                f"{len(nomat)} test compounds have no interaction matrix ({nomat[:6]}), so "
                "nothing says which of their pieces engage the target"
            )
        for inv in self.compound_inventories:
            out += [f"compound: {p}" for p in inv.problems()]
        for m in self.matrices:
            out += [f"matrix: {p}" for p in m.problems()]
        return out

    def summary(self) -> str:
        lines = [
            f"Anatomy for {self.target_id} ({self.run_id})",
            f"  batch coverage: {self.batch_coverage():.0%} "
            f"({len(self.compound_inventories)}/{len(self.test_batch)} compounds)",
            self.target_inventory.summary(),
        ]
        for m in self.matrices[:8]:
            lines.append("  " + m.summary().replace("\n", "\n  "))
        if len(self.matrices) > 8:
            lines.append(f"  ... and {len(self.matrices) - 8} more matrices")
        if probs := self.problems():
            lines.append("  problems:")
            lines += [f"    - {p}" for p in probs]
        return "\n".join(lines)
