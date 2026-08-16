"""What binds a target, what kind of binder each one is, and whether there is an intended mode.

The question this answers is *"find everything that binds this protein, so we understand the
binding mode it was built for."* Both halves need care, and the second half has a trap in it.

**Everything that binds is not everything in the HETATM records.** A census pulled from the PDB
without a deny list returns glycerol, ethylene glycol, PEG fragments, sulfate, DMSO, acetate and
imidazole — buffer, cryoprotectant and precipitant, present in the crystal and absent from the
biology. They then pollute every downstream statement about the pocket: pharmacophore models
built on the union of "all ligands", promiscuity counts, sub-pocket occupancy. Filtering by atom
count does not fix it — glycerol has six heavy atoms and passes the same threshold a real
fragment does. A curated code list is the only thing that works, and it has to distinguish
*always* artefactual from *context-dependent*, because a zinc in a zinc finger is structural and
a zinc from the buffer is noise.

**"The binding mode intended for this target" may not exist, and the absence is the finding.**
For a xenobiotic sensor, breadth *is* the function: the protein evolved to recognise molecules
it has never encountered, so there is no single endogenous ligand whose pose defines a reference.
A pipeline that assumes one canonical mode and builds a prior on it will be wrong in exactly the
direction that matters — and this has already happened in this project's reference case, where
fragment ligands engaged **zero** canonical anchors and an anchor-based prior applied uniformly
*inverted* on the fragment half of the test set.

So ``BindingModeReference`` is allowed to say there is no reference, and ``BinderCensus``
reports that as a first-class result rather than an empty field. What follows from it is
concrete: no single-conformer prior, no uniform anchor bonus, and an ensemble sized to the
observed conformational range instead of to the best-resolution structure.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator

from reagent.contracts.evidence import Evidence


class BinderClass(str, Enum):
    """What kind of thing this binder is, which decides what its pose is evidence *of*.

    The distinction the whole module rests on: an endogenous ligand's pose is evidence about
    what the protein was selected to bind, a marketed drug's pose is evidence about what
    medicinal chemistry achieved, and a cryoprotectant's pose is evidence about the freezing
    protocol. Pooling them and calling the result "the binding mode" is the error this
    taxonomy exists to prevent.
    """

    # -- tells you what the protein is for --------------------------------
    ENDOGENOUS = "endogenous"
    """A physiological ligand. Its pose is the strongest available evidence about the mode the
    protein was selected for — and for a xenobiotic sensor there may be none."""
    SUBSTRATE = "substrate"
    PRODUCT = "product"
    COFACTOR = "cofactor"
    METABOLITE = "metabolite"

    # -- tells you what chemistry can do ----------------------------------
    ORTHOSTERIC_DRUG = "orthosteric_drug"     # designed for this target, binds the main site
    ALLOSTERIC_MODULATOR = "allosteric_modulator"
    OFF_TARGET_DRUG = "off_target_drug"       # designed for something else, hits this too
    TOOL_COMPOUND = "tool_compound"           # chemical probe, never intended as a medicine
    NATURAL_PRODUCT = "natural_product"
    FRAGMENT = "fragment"                     # screening fragment, sub-threshold affinity
    COVALENT = "covalent"

    # -- tells you about the experiment, not the biology -------------------
    CRYSTALLIZATION_ARTEFACT = "crystallization_artefact"
    """Buffer, cryoprotectant, precipitant, detergent. Present in the crystal, absent from the
    biology. Must be excluded from any statement about the pocket."""
    UNKNOWN = "unknown"

    @property
    def informs_intended_mode(self) -> bool:
        """Whether this binder's pose is evidence about what the protein is *for*."""
        return self in {
            BinderClass.ENDOGENOUS, BinderClass.SUBSTRATE, BinderClass.PRODUCT,
            BinderClass.COFACTOR,
        }

    @property
    def informs_druggability(self) -> bool:
        """Whether it is evidence about what medicinal chemistry can achieve here."""
        return self in {
            BinderClass.ORTHOSTERIC_DRUG, BinderClass.ALLOSTERIC_MODULATOR,
            BinderClass.OFF_TARGET_DRUG, BinderClass.TOOL_COMPOUND,
            BinderClass.NATURAL_PRODUCT, BinderClass.FRAGMENT, BinderClass.COVALENT,
        }

    @property
    def is_usable_evidence(self) -> bool:
        return self not in {BinderClass.CRYSTALLIZATION_ARTEFACT, BinderClass.UNKNOWN}


#: PDB chemical-component codes that are essentially never the biology.
#:
#: Curated rather than derived, because no property of the molecule separates a cryoprotectant
#: from a fragment hit — glycerol and a real six-heavy-atom fragment are indistinguishable by
#: size, polarity or buriedness. What separates them is knowing that glycerol was in the drop.
ALWAYS_ARTEFACT: frozenset[str] = frozenset({
    # solvent and water
    "HOH", "DOD", "D8U",
    # cryoprotectants and precipitants
    "GOL", "EDO", "MPD", "PGE", "PG4", "P6G", "1PE", "2PE", "7PE", "PEG", "SUC", "TRE",
    "XYL", "MRD", "BU3", "PDO", "DEG", "TOE",
    # buffers
    "TRS", "EPE", "MES", "IMD", "BCT", "CIT", "FLC", "TLA", "MLI", "MLA", "ACT", "ACY",
    "FMT", "OXL", "SIN", "PPI", "BTB", "144", "NHE", "CAC",
    # common counter-ions and salts
    "SO4", "PO4", "NO3", "SCN", "BR", "IOD", "AZI", "CO3", "PER",
    # reducing agents and misc reagents
    "BME", "DTT", "DTU", "TCE", "EOH", "IPA", "MOH", "ACN", "DMS", "URE", "GAI",
})

#: Codes whose status depends on the protein. Never auto-classify these.
#:
#: A zinc in a zinc finger is structural; a zinc from the buffer is noise. Palmitic acid is a
#: cryoprotectant contaminant in one structure and the physiological ligand in another. The only
#: correct handling is to require a decision with a reason, which ``BinderCensus`` enforces.
CONTEXT_DEPENDENT: frozenset[str] = frozenset({
    # metals — catalytic, structural, or adventitious
    "ZN", "MG", "CA", "MN", "FE", "FE2", "CU", "CU1", "NI", "CO", "NA", "K", "CD", "HG",
    # cofactors that are also common additives
    "NAD", "NAP", "FAD", "FMN", "SAM", "SAH", "ATP", "ADP", "AMP", "GTP", "GDP", "COA",
    "HEM", "HEC", "PLP", "TPP", "B12",
    # lipids and detergents — sometimes the physiological ligand
    "OLA", "OLC", "PLM", "MYR", "STE", "CHD", "CLR", "LDA", "BOG", "LMT", "C8E", "P15",
    "PEE", "PC1", "D10", "HTG", "SDS",
    # sugars — glycosylation is biology, sucrose in the drop is not
    "NAG", "NDG", "BMA", "MAN", "GAL", "GLC", "FUC", "XYS",
})


def artefact_status(het_code: str) -> str:
    """``'artefact'``, ``'context_dependent'``, or ``'candidate_binder'``."""
    code = het_code.strip().upper()
    if code in ALWAYS_ARTEFACT:
        return "artefact"
    if code in CONTEXT_DEPENDENT:
        return "context_dependent"
    return "candidate_binder"


class Binder(BaseModel):
    """One thing observed to bind the target, and what its pose is evidence of."""

    id: str = Field(..., description="Namespaced: chembl:..., pdb-ligand:HYF, uniprot:... .")
    label: str
    binder_class: BinderClass
    het_code: str | None = Field(default=None, description="PDB chemical-component code.")
    classified_because: str = Field(
        ..., min_length=15,
        description=(
            "Why this class. For a context-dependent code this is required reasoning, not a "
            "formality: 'the zinc is tetrahedrally coordinated by three conserved cysteines "
            "and a histidine, so it is structural' versus 'present at 1.2 sigma in one of "
            "eleven structures, all from the same crystal form'."
        ),
    )
    affinity_nm: float | None = Field(default=None, gt=0)
    affinity_type: str | None = Field(default=None, description="Ki, Kd, IC50, EC50.")
    structures: list[str] = Field(
        default_factory=list, description="Complexes in which it is resolved."
    )
    pocket: str | None = Field(default=None, description="Which pocket or sub-region.")
    evidence: list[Evidence] = Field(default_factory=list)
    n_contacts: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _context_dependent_needs_real_reasoning(self) -> Binder:
        """A metal or lipid classified in one clause has not been thought about.

        This guard exists because the failure is invisible: a zinc silently kept as a cofactor
        or silently dropped as an artefact produces a plausible census either way, and the
        pocket statement built on it is wrong in a way nothing downstream detects.
        """
        if (
            self.het_code
            and artefact_status(self.het_code) == "context_dependent"
            and len(self.classified_because.split()) < 8
        ):
            raise ValueError(
                f"{self.het_code} is context-dependent — it can be biology or buffer "
                "depending on the protein — so `classified_because` must give the actual "
                f"reasoning, not {self.classified_because!r}. Coordination geometry, "
                "conservation, occupancy, or how many independent crystal forms show it."
            )
        return self

    @property
    def is_artefact_by_code(self) -> bool:
        return bool(self.het_code) and artefact_status(self.het_code) == "artefact"


class BindingModeReference(BaseModel):
    """The pose, if any, that defines what the target was built to bind.

    ``is_defined`` is allowed to be False, and for a promiscuous xenobiotic sensor it usually
    should be. That is the single most decision-relevant fact this module can report, because
    every downstream prior that assumes a canonical mode is wrong for such a target — and wrong
    confidently, since the prior looks better-informed than having none.
    """

    target_id: str
    is_defined: bool
    reference_binders: list[str] = Field(
        default_factory=list, description="Binder ids whose poses define the mode."
    )
    reference_structures: list[str] = Field(default_factory=list)
    anchor_residues: list[str] = Field(
        default_factory=list,
        description="Residues the reference pose engages. NOT a requirement for other ligands.",
    )
    why: str = Field(
        ..., min_length=25,
        description=(
            "Why there is or is not a reference mode. When there is not, say what makes the "
            "target's function incompatible with one — that reasoning is what stops the next "
            "run from assuming otherwise."
        ),
    )
    anchor_policy: str = Field(
        default="additive",
        description=(
            "How anchors may be used downstream. 'additive' means engaging one is a bonus and "
            "not engaging one is not a penalty. 'required' needs evidence that every "
            "subpopulation engages them, which is rare and must be argued."
        ),
    )
    conformational_range: str | None = Field(
        default=None,
        description="Observed spread across holo structures — what an ensemble must cover.",
    )
    evidence: list[Evidence] = Field(default_factory=list)

    @model_validator(mode="after")
    def _defined_means_evidenced(self) -> BindingModeReference:
        if self.is_defined and not (self.reference_binders or self.reference_structures):
            raise ValueError(
                f"{self.target_id}: claims a defined binding mode but names no reference "
                "binder or structure. A mode without a pose is an assumption."
            )
        if not self.is_defined and self.anchor_policy == "required":
            raise ValueError(
                f"{self.target_id}: no reference mode is defined, so anchors cannot be "
                "'required'. This is the specific error that inverted an anchor-based prior "
                "on the fragment half of a real test set — fragments engaged zero canonical "
                "anchors and were penalised for it."
            )
        return self

    @model_validator(mode="after")
    def _required_policy_must_be_argued(self) -> BindingModeReference:
        if self.anchor_policy == "required" and len(self.why.split()) < 25:
            raise ValueError(
                f"{self.target_id}: 'required' anchors need an argument that every "
                "subpopulation engages them, not a sentence. Fragments, covalent binders and "
                "allosteric ligands routinely do not."
            )
        return self


class BinderCensus(BaseModel):
    """Everything observed to bind one target, classified, with the artefacts named.

    Completeness here is a *screening-normalised* claim, not an absolute one. A protein tested
    against ten thousand compounds looks promiscuous next to one tested against fifty, and the
    difference is the testing. ``screening_breadth`` records the denominator so the count means
    something.
    """

    target_id: str
    binders: list[Binder] = Field(default_factory=list)
    mode: BindingModeReference
    n_structures_searched: int = Field(default=0, ge=0)
    n_het_codes_seen: int = Field(
        default=0, ge=0,
        description="Distinct heteroatom groups encountered before filtering.",
    )
    screening_breadth: int | None = Field(
        default=None, ge=0,
        description=(
            "How many distinct compounds have been *tested* against this target, from an "
            "activity database. The denominator that turns a hit count into a rate."
        ),
    )
    sources: list[str] = Field(
        default_factory=list,
        description="Where the census was drawn from: rcsb, chembl, bindingdb, pdbe, papers.",
    )
    unclassified: list[str] = Field(
        default_factory=list,
        description="Het codes seen and not decided about. Each is a hole in the census.",
    )

    # -- views -------------------------------------------------------------

    def by_class(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for b in self.binders:
            counts[b.binder_class.value] = counts.get(b.binder_class.value, 0) + 1
        return dict(sorted(counts.items(), key=lambda kv: -kv[1]))

    def usable(self) -> list[Binder]:
        """Binders whose poses may inform a statement about the pocket."""
        return [b for b in self.binders if b.binder_class.is_usable_evidence]

    def artefacts(self) -> list[Binder]:
        return [b for b in self.binders
                if b.binder_class is BinderClass.CRYSTALLIZATION_ARTEFACT]

    def canonical(self) -> list[Binder]:
        return [b for b in self.binders if b.binder_class.informs_intended_mode]

    def misclassified_artefacts(self) -> list[str]:
        """Binders with an always-artefact code that were classified as something else.

        The commonest way a census gets polluted, and it is pure arithmetic to catch.
        """
        return [
            f"{b.id} ({b.het_code})" for b in self.binders
            if b.is_artefact_by_code
            and b.binder_class is not BinderClass.CRYSTALLIZATION_ARTEFACT
        ]

    @property
    def hit_rate(self) -> float | None:
        """Usable binders as a fraction of compounds tested. The comparable number."""
        if not self.screening_breadth:
            return None
        return len(self.usable()) / self.screening_breadth

    def chemotype_spread(self) -> int:
        """Distinct binder classes among usable binders — a crude diversity proxy."""
        return len({b.binder_class for b in self.usable()})

    def problems(self) -> list[str]:
        out: list[str] = []
        if not self.binders:
            out.append(f"{self.target_id}: empty census")
            return out

        if bad := self.misclassified_artefacts():
            out.append(
                f"{len(bad)} binders carry an always-artefact code but are classified as "
                f"something else: {bad[:6]}. These are buffer, cryoprotectant or precipitant, "
                "and leaving them in pollutes every statement about the pocket — "
                "pharmacophore models, promiscuity counts, sub-pocket occupancy."
            )
        if self.unclassified:
            out.append(
                f"{len(self.unclassified)} heteroatom codes were seen and never decided about "
                f"({self.unclassified[:8]}). Each is a hole: it is neither counted as a binder "
                "nor recorded as an artefact, so the census total means nothing."
            )
        if not self.sources:
            out.append(
                f"{self.target_id}: no sources recorded, so the census cannot be reproduced "
                "or extended"
            )
        elif len(self.sources) == 1:
            out.append(
                f"{self.target_id}: drawn from one source ({self.sources[0]}). Structural "
                "databases hold co-crystals and activity databases hold binders never "
                "crystallised; either alone is a systematic subset."
            )
        if self.screening_breadth is None and len(self.usable()) > 5:
            out.append(
                f"{self.target_id}: {len(self.usable())} binders and no `screening_breadth`. "
                "A raw count cannot be compared across targets — it measures how much the "
                "protein has been tested as much as how promiscuous it is."
            )
        if not self.canonical() and self.mode.is_defined:
            out.append(
                f"{self.target_id}: a binding mode is claimed as defined, but no endogenous, "
                "substrate, product or cofactor binder is in the census. The reference is "
                "resting on ligands that tell you what chemistry achieved, not what the "
                "protein is for."
            )
        if self.n_structures_searched <= 1 and len(self.usable()) > 1:
            out.append(
                f"{self.target_id}: {self.n_structures_searched} structure(s) searched. A "
                "single complex gives that ligand's interactions, not the pocket's grammar."
            )
        return out

    def summary(self) -> str:
        lines = [
            f"Binder census for {self.target_id}: {len(self.binders)} entries, "
            f"{len(self.usable())} usable, {len(self.artefacts())} artefacts",
            "  " + ", ".join(f"{k}:{v}" for k, v in self.by_class().items()),
        ]
        if (hr := self.hit_rate) is not None:
            lines.append(f"  hit rate {hr:.2%} of {self.screening_breadth} tested")
        lines.append(
            f"  intended binding mode: {'DEFINED' if self.mode.is_defined else 'NOT DEFINED'}"
            f" — {self.mode.why[:110]}"
        )
        if self.mode.is_defined:
            lines.append(f"  anchors ({self.mode.anchor_policy}): {self.mode.anchor_residues}")
        if self.mode.conformational_range:
            lines.append(f"  conformational range: {self.mode.conformational_range}")
        if probs := self.problems():
            lines.append("  problems:")
            lines += [f"    - {p}" for p in probs]
        return "\n".join(lines)
