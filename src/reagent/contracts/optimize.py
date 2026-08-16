"""Stage 4: refine a pose without destroying it.

Stage 3 produced a pool and picked from it. Stage 4 tries to make the pick better — by docking,
by minimising, by running MD, by rescoring against a panel, and by **editing the coordinates
directly**. Every one of those can improve a pose and every one can wreck it, so the whole
module is arranged around one number measured on this project's reference case:

    An agentic free re-draw of a ligand took a pose from **3.88 Å to 24.63 Å**.

That is not a bad edit. That is a model confidently generating unphysical geometry and reporting
success. It is why `EditOp` exists as a closed set of *typed* operations rather than a licence to
rewrite coordinate text, why `RAW_COORDINATE` requires explicit escalation, and why **an LLM may
propose an edit but may never be the last thing that touches the file.**

Three more measured facts shape the defaults, all from the same reference case:

* Applying twenty light-tier medchem edits scored **0.5613 against an unedited 0.5640** — inside
  the noise and slightly negative. **Expect this stage to do nothing, and be pleased if it does
  no harm.** A Stage 4 that reports a large improvement is more likely to have leaked than to
  have worked.
* Ligand-only force-field relaxation of **the ground truth itself** monotonically degraded it.
  The bound conformer is legitimately strained; relaxing toward a gas-phase minimum walks away
  from the answer. So minimisation is never ligand-only and never unrestrained.
* MD did not recover a 2 Å translation. **Refinement polishes a nearly-correct pose; it does not
  relocate a wrong one.** Targeting matters more than method.

And the leakage hazard, which is specific to this stage and worse than anywhere else: if you
adjust coordinates and the score improves, you may have improved the pose or you may have moved
atoms toward the reference. The second is cheating and it feels identical from the inside. Hence
`CoordinateEdit.informed_by` and the blindness guard.

Tooling is deliberately **provider-agnostic**. A skill asks for a *capability* — dock, minimise,
run MD — and `ToolRegistry` says which provider supplies it here, or that none does. Tamarind,
a local Vina, OpenMM, or something the user brings are all bindings for the same capability, and
a plan that needs an unbound capability says so instead of quietly skipping the step.
"""

from __future__ import annotations

import hashlib
from enum import Enum

from pydantic import BaseModel, Field, model_validator

from reagent.contracts.evidence import Evidence

# ---------------------------------------------------------------------------
# Tooling: capabilities, not products
# ---------------------------------------------------------------------------


class Capability(str, Enum):
    """What Stage 4 needs done, independent of what does it.

    Written as capabilities so a skill never names a vendor. The user supplies whatever they
    have — Tamarind, a local binary, a cluster module — and the registry maps it.
    """

    CONFORMER_GEN = "conformer_generation"
    PROTONATE = "protonation"
    DOCK = "docking"                       # generate geometry; never to rank it
    MINIMIZE = "minimization"              # restrained, in the pocket
    MD = "molecular_dynamics"
    RESCORE_PHYSICS = "physics_rescoring"
    RESCORE_LEARNED = "learned_rescoring"
    GEOMETRY_CHECK = "geometry_check"      # bond lengths, angles, chirality, clashes
    STRUCTURE_WRITE = "structure_write"     # format-safe coordinate output

    @property
    def is_metered_by_default(self) -> bool:
        """Whether this usually costs money. Docking and MD are where the credits go."""
        return self in {Capability.DOCK, Capability.MD, Capability.RESCORE_LEARNED}


class ToolBinding(BaseModel):
    """One provider bound to one capability, with what it costs and how it is called."""

    capability: Capability
    provider: str = Field(
        ..., min_length=1,
        description="Whatever supplies it: 'tamarind', 'vina-local', 'openmm', 'rdkit'.",
    )
    invocation: str | None = Field(
        default=None, description="How it is actually run — CLI, endpoint, or module path."
    )
    metered: bool = Field(
        default=False, description="Whether a run spends credits or billable compute."
    )
    unit_cost: str | None = Field(
        default=None,
        description=(
            "Measured cost per unit from a pilot, not an estimate. 'about 40 s and $0.02 per "
            "pose' beats 'cheap', because only the first can be multiplied by the item count."
        ),
    )
    verified: bool = Field(
        default=False,
        description=(
            "Whether this binding has actually been run successfully here. An unverified "
            "binding is a plan, and Stage 4 has already been bitten by tooling that installs "
            "and does not run — ChimeraX offscreen is Linux-only, PLIP crashes with the pip "
            "openbabel wheel, ProLIF segfaults from stdin."
        ),
    )
    note: str | None = None


class ToolRegistry(BaseModel):
    """What is available in this environment. Optional by design.

    The point of the indirection: a skill says *"minimise this"* and does not care whether that
    is Tamarind, OpenMM or a local binary. What it must not do is silently skip the step because
    nothing is bound — `missing_for()` makes an unavailable capability an explicit finding.
    """

    bindings: list[ToolBinding] = Field(default_factory=list)

    def available(self) -> set[Capability]:
        return {b.capability for b in self.bindings}

    def verified_capabilities(self) -> set[Capability]:
        return {b.capability for b in self.bindings if b.verified}

    def provider_for(self, cap: Capability) -> ToolBinding | None:
        verified = [b for b in self.bindings if b.capability is cap and b.verified]
        if verified:
            return verified[0]
        return next((b for b in self.bindings if b.capability is cap), None)

    def missing_for(self, needed: list[Capability]) -> list[str]:
        have = self.available()
        return [c.value for c in needed if c not in have]

    def unverified_for(self, needed: list[Capability]) -> list[str]:
        ok = self.verified_capabilities()
        have = self.available()
        return [c.value for c in needed if c in have and c not in ok]

    def metered_in(self, needed: list[Capability]) -> list[str]:
        return [
            f"{b.capability.value} via {b.provider}"
            for b in self.bindings
            if b.capability in set(needed) and b.metered
        ]

    def problems(self, needed: list[Capability]) -> list[str]:
        out: list[str] = []
        if missing := self.missing_for(needed):
            out.append(
                f"no provider bound for {missing}. Stage 4 cannot do these here — say so as a "
                "limitation rather than quietly skipping the step, because a refinement stage "
                "that silently did not refine reads as one that found nothing to fix."
            )
        if unver := self.unverified_for(needed):
            out.append(
                f"providers bound but never successfully run: {unver}. Verify before planning "
                "around them — this stage's tooling has a history of installing and not running."
            )
        if metered := self.metered_in(needed):
            out.append(
                f"metered capabilities in the plan: {metered}. Estimate the spend, write it into "
                "the proposal, and get the decision before any of it runs."
            )
        return out


# ---------------------------------------------------------------------------
# Coordinate editing
# ---------------------------------------------------------------------------


class EditOp(str, Enum):
    """The closed set of coordinate operations, ordered roughly by how much they can break.

    Closed on purpose. The alternative — letting a model rewrite coordinate text freely — is the
    thing that produced a 24.63 Å pose from a 3.88 Å one, with complete confidence. A typed
    operation has a checkable postcondition; free text does not.
    """

    # -- rigid, cannot change internal geometry -----------------------------
    RIGID_TRANSLATE = "rigid_translate"
    RIGID_ROTATE = "rigid_rotate"

    # -- changes internal geometry in a controlled way ----------------------
    TORSION_SET = "torsion_set"            # rotate about one rotatable bond
    ROTAMER_SWAP = "rotamer_swap"          # protein side chain to a library rotamer
    AMIDE_FLIP = "amide_flip"              # 180 degrees about the C-N axis
    RING_FLIP = "ring_flip"                # chair/boat, or ring pucker

    # -- changes the molecule, not just its shape ---------------------------
    PROTONATION_CHANGE = "protonation_change"
    TAUTOMER_CHANGE = "tautomer_change"
    STEREO_INVERT = "stereo_invert"

    # -- structural surgery -------------------------------------------------
    ATOM_DELETE = "atom_delete"            # e.g. stripping a crystallisation artefact
    OCCUPANCY_SET = "occupancy_set"

    # -- the escape hatch ---------------------------------------------------
    RAW_COORDINATE = "raw_coordinate"
    """Direct coordinate assignment. Requires escalation and full geometry validation.

    Present because sometimes nothing else expresses the fix, and absent from the default path
    because this is the operation that produced the 24.63 Å pose.
    """

    @property
    def preserves_internal_geometry(self) -> bool:
        """Rigid moves cannot create a bad bond length or angle. Everything else can."""
        return self in {EditOp.RIGID_TRANSLATE, EditOp.RIGID_ROTATE, EditOp.OCCUPANCY_SET}

    @property
    def changes_the_graph(self) -> bool:
        """Whether the molecular graph changes, which most submission validators reject."""
        return self in {
            EditOp.PROTONATION_CHANGE, EditOp.TAUTOMER_CHANGE, EditOp.STEREO_INVERT,
            EditOp.ATOM_DELETE,
        }

    @property
    def needs_escalation(self) -> bool:
        return self is EditOp.RAW_COORDINATE

    @property
    def severity(self) -> str:
        """keep / light / drastic, matching the medchem tiering."""
        if self.preserves_internal_geometry:
            return "light"
        if self in {EditOp.TORSION_SET, EditOp.ROTAMER_SWAP, EditOp.AMIDE_FLIP,
                    EditOp.RING_FLIP}:
            return "light"
        return "drastic"


class GeometryCheck(BaseModel):
    """What was verified after an edit. Absence of a check is not a pass.

    Each field is tri-state on purpose: True passed, False failed, None *not checked*. Collapsing
    None into True is how an unvalidated edit ships looking validated.
    """

    bond_lengths_ok: bool | None = None
    bond_angles_ok: bool | None = None
    planarity_ok: bool | None = None
    chirality_preserved: bool | None = None
    no_new_clashes: bool | None = None
    graph_unchanged: bool | None = None
    file_parses: bool | None = None
    max_clash_overlap_a: float | None = Field(default=None, ge=0)
    worst_bond_deviation_a: float | None = Field(default=None, ge=0)
    checked_by: str | None = Field(default=None, description="Which tool ran the checks.")

    @property
    def unchecked(self) -> list[str]:
        return [
            name for name in (
                "bond_lengths_ok", "bond_angles_ok", "planarity_ok", "chirality_preserved",
                "no_new_clashes", "graph_unchanged", "file_parses",
            )
            if getattr(self, name) is None
        ]

    @property
    def failures(self) -> list[str]:
        return [
            name for name in (
                "bond_lengths_ok", "bond_angles_ok", "planarity_ok", "chirality_preserved",
                "no_new_clashes", "graph_unchanged", "file_parses",
            )
            if getattr(self, name) is False
        ]

    @property
    def passed(self) -> bool:
        return not self.failures and not self.unchecked


class CoordinateEdit(BaseModel):
    """One typed edit to a structure file, with its justification and its verification.

    The two guards that matter:

    **Verification is mandatory and is not the editor's own opinion.** `checks` must be populated
    and must pass. A model that has just moved atoms is the worst available judge of whether the
    result is physical.

    **Blindness is mandatory.** `informed_by` may not contain the reference structure. If an edit
    is guided by the answer, an improvement in the score measures the guidance rather than the
    edit — and it feels identical from the inside, which is why it is a contract rule and not a
    piece of advice.
    """

    id: str
    op: EditOp
    target: str = Field(
        ..., min_length=1,
        description="What is being edited: 'ligand HYF chain A', 'residue Ser247 chain A'.",
    )
    atoms: list[str] = Field(
        default_factory=list, description="Atom names or serials the edit touches."
    )
    params: dict[str, float | int | str] = Field(
        default_factory=dict,
        description="The operation's arguments — angle, vector, rotamer id. Replayable.",
    )
    why: str = Field(
        ..., min_length=25,
        description=(
            "The chemistry reason, specific to this pose. 'Relieves a 0.9 A overlap between the "
            "ligand carbonyl and Leu240 CD1 by rotating one torsion' — not 'improves geometry'."
        ),
    )
    informed_by: list[Evidence] = Field(
        default_factory=list,
        description=(
            "What guided the edit: an interaction profile, a homologous complex, a clash report. "
            "May NOT include the reference structure for this item — see the validator."
        ),
    )
    blind_to_reference: bool = Field(
        default=True,
        description=(
            "Asserts the edit was made without seeing the answer for this item. Setting this "
            "False is legitimate only on a validation gate, never on a submission."
        ),
    )
    checks: GeometryCheck = Field(default_factory=GeometryCheck)
    minimized_after: bool = Field(
        default=False,
        description=(
            "Whether a restrained minimisation ran after the edit. An LLM may propose an edit "
            "and may not be the last thing that touches the file."
        ),
    )
    escalation_note: str | None = Field(
        default=None, description="Required for RAW_COORDINATE: why nothing typed would do."
    )
    before_sha256: str | None = None
    after_sha256: str | None = None
    reverted: bool = False

    @model_validator(mode="after")
    def _raw_coordinates_need_escalation(self) -> CoordinateEdit:
        if self.op.needs_escalation and not (self.escalation_note or "").strip():
            raise ValueError(
                f"edit {self.id} uses RAW_COORDINATE without `escalation_note`. This is the "
                "operation that took a pose from 3.88 A to 24.63 A on this project's reference "
                "case — say why no typed operation expresses the fix, or use one that does."
            )
        return self

    @model_validator(mode="after")
    def _edits_are_verified(self) -> CoordinateEdit:
        if self.reverted:
            return self
        if self.checks.failures:
            raise ValueError(
                f"edit {self.id} failed geometry checks {self.checks.failures} and is not marked "
                "reverted. A failed check is a revert, not a warning."
            )
        if self.checks.unchecked:
            raise ValueError(
                f"edit {self.id} left {self.checks.unchecked} unchecked. Absence of a check is "
                "not a pass — an unvalidated edit that happens to look fine is the one that "
                "ships. Set each explicitly, including to False."
            )
        return self

    @model_validator(mode="after")
    def _non_rigid_edits_are_minimized(self) -> CoordinateEdit:
        if self.reverted:
            return self
        if not self.op.preserves_internal_geometry and not self.minimized_after:
            raise ValueError(
                f"edit {self.id} is a {self.op.value}, which can change internal geometry, and "
                "no restrained minimisation followed. The rule is that a model may propose an "
                "edit and may not be the last thing to touch the file."
            )
        return self

    @model_validator(mode="after")
    def _blindness_is_real(self) -> CoordinateEdit:
        if not self.blind_to_reference:
            return self
        leaky = [
            e.locator for e in self.informed_by
            if any(t in e.locator.lower() for t in ("reference", "answer", "ground_truth",
                                                    "groundtruth", "label"))
        ]
        if leaky:
            raise ValueError(
                f"edit {self.id} claims to be blind to the reference but cites {leaky}. An edit "
                "guided by the answer makes the score measure the guidance, and it feels "
                "identical from the inside — which is why this is a rule."
            )
        return self

    @property
    def severity(self) -> str:
        return self.op.severity


def sha256_of(text: str) -> str:
    """Hash a structure file's text, so an edit is provably reversible."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Refinement and scoring
# ---------------------------------------------------------------------------


class Refinement(BaseModel):
    """One docking, minimisation or MD run, with what it was allowed to move."""

    id: str
    capability: Capability
    provider: str
    scope: str = Field(
        ...,
        description=(
            "What was allowed to move: 'ligand in a rigid pocket', 'ligand plus pocket side "
            "chains', 'all atoms'. The single most consequential parameter here."
        ),
    )
    restrained: bool = Field(
        default=True,
        description=(
            "Whether positional restraints were applied. Unrestrained minimisation of a bound "
            "conformer walks toward a gas-phase minimum and away from the answer — on this "
            "project's reference case, relaxing the ground truth itself monotonically degraded "
            "it."
        ),
    )
    ligand_only: bool = Field(
        default=False,
        description="Ligand relaxed outside the pocket. Almost always wrong; see the validator.",
    )
    n_items: int = Field(default=0, ge=0)
    targeted_at: str = Field(
        default="failure_tail",
        description=(
            "Which items. 'failure_tail' is the default because blanket application dilutes "
            "the wins with regressions on already-good poses."
        ),
    )
    cost: str | None = None
    gated_on: str | None = Field(
        default=None,
        description=(
            "The held-out set this was validated against before adoption. Refinement is the "
            "classic place where a plausible improvement is a measurable regression."
        ),
    )

    @model_validator(mode="after")
    def _ligand_only_relaxation_is_rejected(self) -> Refinement:
        if self.ligand_only and self.capability in {Capability.MINIMIZE, Capability.MD}:
            raise ValueError(
                f"refinement {self.id} relaxes the ligand in isolation. The bound conformer is "
                "legitimately strained, so this moves toward a gas-phase minimum and away from "
                "the answer — measured on this project's reference case by degrading the ground "
                "truth itself, monotonically. Minimise in the pocket."
            )
        return self

    @model_validator(mode="after")
    def _unrestrained_needs_a_reason(self) -> Refinement:
        if not self.restrained and self.capability is Capability.MINIMIZE:
            raise ValueError(
                f"refinement {self.id} is an unrestrained minimisation. Use restraints, or use "
                "MD with an explicit scope and say why the restraints were dropped."
            )
        return self


class ScoringFunction(BaseModel):
    """One member of a scoring panel, and what is known about whether it discriminates."""

    name: str
    kind: str = Field(..., description="'physics', 'learned', 'confidence', or 'geometric'.")
    provider: str | None = None
    scores_the_candidate: bool = Field(
        default=True,
        description=(
            "Whether it varies with the *pose* rather than with the input it came from. A "
            "rescorer that reads only ligand identity ranks compounds, not poses, and looks "
            "excellent on a benchmark where the two correlate."
        ),
    )
    discrimination_auc: float | None = Field(
        default=None, ge=0.0, le=1.0,
        description="Measured ability to separate good poses from bad. Not assumed.",
    )
    beat_baseline: bool | None = Field(
        default=None,
        description="Whether it beat the confidence baseline on held-out items. None = untested.",
    )
    normalised_within: bool = Field(
        default=False,
        description=(
            "Whether scores were normalised within this function before being compared across "
            "functions. Raw cross-function comparison silently prefers whichever is most "
            "confident rather than most correct."
        ),
    )
    note: str | None = None

    @property
    def is_usable(self) -> bool:
        """Whether it may contribute to a decision."""
        return self.scores_the_candidate and self.beat_baseline is not False


class ScoringPanel(BaseModel):
    """Several scoring functions as challengers to the incumbent, not as voters.

    The framing is deliberate. A panel is useful because its members fail on *different* poses,
    so one can break a tie another gets wrong. It is not useful as a vote: agreement among
    scoring functions trained on overlapping data is correlation, not evidence, which is the
    same reason inter-agent agreement is not a correctness proxy.
    """

    functions: list[ScoringFunction] = Field(default_factory=list)
    incumbent: str = Field(
        default="confidence",
        description="What a challenger has to beat. Usually the generator's own confidence.",
    )
    aggregation: str = Field(
        default="challenger",
        description=(
            "'challenger' — each is tested against the incumbent separately. 'vote' requires an "
            "argument, because agreement among correlated scorers is not evidence."
        ),
    )

    def usable(self) -> list[ScoringFunction]:
        return [f for f in self.functions if f.is_usable]

    def untested(self) -> list[str]:
        return [f.name for f in self.functions if f.beat_baseline is None]

    def problems(self) -> list[str]:
        out: list[str] = []
        if not self.functions:
            return ["empty scoring panel"]
        if proxies := [f.name for f in self.functions if not f.scores_the_candidate]:
            out.append(
                f"{proxies} do not vary with the pose, so they rank inputs rather than "
                "candidates. On a benchmark where compound identity correlates with pose "
                "quality they will look useful and generalise to nothing."
            )
        if unnorm := [f.name for f in self.functions if not f.normalised_within]:
            out.append(
                f"{unnorm} were not normalised within-function before cross-function comparison, "
                "which prefers whichever scorer is most confident rather than most correct"
            )
        if untested := self.untested():
            out.append(
                f"{untested} were never tested against the {self.incumbent} baseline. A scoring "
                "function is guilty until it beats the incumbent on held-out items; being "
                "principled is not evidence."
            )
        if self.aggregation == "vote":
            out.append(
                "panel is aggregating by vote. Agreement among scoring functions trained on "
                "overlapping data is correlation, not evidence — the same reason inter-agent "
                "agreement is not a correctness proxy. Use 'challenger' or argue for the vote."
            )
        return out


class OptimizationRun(BaseModel):
    """Stage 4's deliverable: what was tried, what it cost, and whether it helped.

    The default expectation is **no improvement**, and that is not pessimism. Twenty light-tier
    edits on this project's reference case scored 0.5613 against an unedited 0.5640 — inside the
    noise and slightly negative. A Stage 4 reporting a large gain should be checked for leakage
    before it is believed.
    """

    run_id: str
    tools: ToolRegistry = Field(default_factory=ToolRegistry)
    capabilities_needed: list[Capability] = Field(default_factory=list)
    edits: list[CoordinateEdit] = Field(default_factory=list)
    refinements: list[Refinement] = Field(default_factory=list)
    panel: ScoringPanel | None = None
    baseline_metric: str | None = Field(
        default=None, description="The incumbent's score, e.g. 'mean LDDT-PLI 0.5640'."
    )
    final_metric: str | None = None
    delta: str | None = Field(
        default=None, description="Change with its noise floor. Without the floor it is a rumour."
    )
    adopted: bool = Field(
        default=False, description="Whether this replaced the incumbent."
    )
    adoption_gate: str | None = Field(
        default=None,
        description="The held-out evidence for adoption. Required when `adopted` is True.",
    )

    @model_validator(mode="after")
    def _adoption_needs_a_gate(self) -> OptimizationRun:
        if self.adopted and not (self.adoption_gate or "").strip():
            raise ValueError(
                f"run {self.run_id} was adopted with no `adoption_gate`. Refinement is the "
                "classic place where a plausible improvement is a measurable regression, so a "
                "pass that cannot demonstrate improvement on held-out items does not ship "
                "however sensible each edit looked."
            )
        return self

    # -- views -------------------------------------------------------------

    def by_severity(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for e in self.edits:
            if not e.reverted:
                out[e.severity] = out.get(e.severity, 0) + 1
        return dict(sorted(out.items()))

    def by_op(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for e in self.edits:
            if not e.reverted:
                out[e.op.value] = out.get(e.op.value, 0) + 1
        return dict(sorted(out.items(), key=lambda kv: -kv[1]))

    def reverted(self) -> list[str]:
        return [e.id for e in self.edits if e.reverted]

    def graph_changing_edits(self) -> list[str]:
        return [e.id for e in self.edits if not e.reverted and e.op.changes_the_graph]

    def raw_coordinate_edits(self) -> list[str]:
        return [e.id for e in self.edits
                if not e.reverted and e.op is EditOp.RAW_COORDINATE]

    def sighted_edits(self) -> list[str]:
        """Edits made while able to see the reference. Fine on a gate, never on a submission."""
        return [e.id for e in self.edits if not e.reverted and not e.blind_to_reference]

    def problems(self) -> list[str]:
        out: list[str] = []
        out += self.tools.problems(self.capabilities_needed)

        if graph := self.graph_changing_edits():
            out.append(
                f"{len(graph)} edits change the molecular graph ({graph[:5]}). Most submission "
                "validators reject an entry whose atom names, connectivity or bond orders "
                "changed, and a rejected entry scores zero rather than badly."
            )
        if raw := self.raw_coordinate_edits():
            out.append(
                f"{len(raw)} RAW_COORDINATE edits survived ({raw[:5]}). This is the operation "
                "that produced a 24.63 A pose from a 3.88 A one — each needs a reviewer, not "
                "just an escalation note."
            )
        if sighted := self.sighted_edits():
            out.append(
                f"{len(sighted)} edits were made with sight of the reference ({sighted[:5]}). "
                "Legitimate on a validation gate and never on a submission: the score then "
                "measures the guidance rather than the edit."
            )
        if self.panel:
            out += [f"panel: {p}" for p in self.panel.problems()]
        if self.edits and self.delta is None:
            out.append(
                "edits were applied and no `delta` recorded. Expect this stage to do nothing — "
                "twenty light-tier edits measured 0.5613 against an unedited 0.5640 — so an "
                "unmeasured pass is indistinguishable from a harmful one."
            )
        if self.refinements and not any(r.gated_on for r in self.refinements):
            out.append(
                "no refinement records a held-out gate. Validate on known complexes before "
                "applying to anything that ships."
            )
        blanket = [r.id for r in self.refinements if r.targeted_at == "all"]
        if blanket:
            out.append(
                f"refinements applied to the whole set ({blanket}). Physics-based refinement "
                "reliably improves some cases and destroys others, so blanket application "
                "dilutes the wins with regressions on already-good poses. Target the tail."
            )
        return out

    def summary(self) -> str:
        lines = [f"Stage 4 run {self.run_id}"]
        if self.capabilities_needed:
            have = self.tools.available()
            lines.append(
                "  capabilities: "
                + ", ".join(
                    f"{c.value}{'' if c in have else ' (MISSING)'}"
                    for c in self.capabilities_needed
                )
            )
        if self.edits:
            lines.append(
                f"  {len(self.edits)} edits ({len(self.reverted())} reverted): "
                + ", ".join(f"{k}={v}" for k, v in self.by_severity().items())
            )
            lines.append("  ops: " + ", ".join(f"{k}({v})" for k, v in self.by_op().items()))
        for r in self.refinements:
            lines.append(
                f"  refine {r.id}: {r.capability.value} via {r.provider}, {r.scope}, "
                f"{r.n_items} items, target={r.targeted_at}"
                + (f", gated on {r.gated_on}" if r.gated_on else ", UNGATED")
            )
        if self.panel:
            lines.append(
                f"  panel: {len(self.panel.usable())}/{len(self.panel.functions)} usable "
                f"against {self.panel.incumbent}"
            )
        if self.baseline_metric or self.final_metric:
            lines.append(f"  {self.baseline_metric} -> {self.final_metric}  ({self.delta})")
        lines.append(f"  adopted: {self.adopted}"
                     + (f" — {self.adoption_gate}" if self.adoption_gate else ""))
        if probs := self.problems():
            lines.append("  problems:")
            lines += [f"    - {p}" for p in probs]
        return "\n".join(lines)
