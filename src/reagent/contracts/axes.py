"""Axis derivation and per-axis exhaustion.

This module exists because of one observed failure, and it is worth stating precisely
because everything here is shaped by it.

    Asked to build the neighbourhood of a target, an agent enumerates the axes it was
    handed, works them until the results feel sufficient, and stops. What it does *not*
    do is notice that the target **is a kind of thing** — a nuclear receptor, a
    promiscuous binder, a liver-enriched xenobiotic sensor — and that each of those
    memberships is itself a connector to a different population of proteins. The axes it
    was handed were a fixed list; the axes it *should* have run were derivable from the
    target's own properties. So it misses whole regions, and because nothing records the
    miss, the report reads as complete.

Two mechanisms answer that, and neither is a prompt.

**Derivation with a coverage gate.** ``AxisDerivation`` enumerates the target's properties
against a declared checklist for its domain. Every checklist item must be either turned
into an axis or explicitly dismissed with a reason. Silence is not an option, because
silence is exactly what the failure looks like from outside.

**Per-axis exhaustion with an observable stopping rule.** One ``AxisSweep`` per axis, each
run by its own worker, each recording its discovery curve round by round. Saturation means
the curve flattened. "It felt like enough" is not saturation, and a sweep that ran out of
budget is recorded as *truncated*, which is a different word on purpose.

The asymmetry driving both: a region never searched cannot be recovered downstream,
because nothing distinguishes "searched and found nothing" from "never looked".
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator

from reagent.contracts.discovery import SearchLedger
from reagent.contracts.evidence import Evidence
from reagent.contracts.problem import Domain


class PropertyKind(str, Enum):
    """A dimension along which a target can *be a kind of thing*.

    This is the checklist. Its purpose is to be boring and complete rather than clever:
    each entry is a question that, asked of any target in its domain, either yields a
    connector or is explicitly ruled out. The list being fixed is the point — an agent
    cannot forget an item on a checklist it has to sign off.
    """

    # -- what it is made of ------------------------------------------------
    SEQUENCE_IDENTITY = "sequence_identity"        # homologues, orthologues, paralogues
    FOLD = "fold"                                  # topology / architecture
    DOMAIN_ARCHITECTURE = "domain_architecture"    # the arrangement of domains
    FAMILY_MEMBERSHIP = "family_membership"        # family, subfamily, superfamily
    MOTIF_CONTENT = "motif_content"                # local 3D or sequence motifs, SAE features

    # -- what binds to it -------------------------------------------------
    POCKET_CHARACTER = "pocket_character"          # size, hydrophobicity, polarity
    POCKET_PLASTICITY = "pocket_plasticity"        # rigid, induced-fit, expandable
    LIGAND_PROMISCUITY = "ligand_promiscuity"      # polypharmacology breadth
    KNOWN_CHEMOTYPES = "known_chemotypes"          # the chemical series with precedent
    COFACTOR_DEPENDENCE = "cofactor_dependence"

    # -- where it sits in the network -------------------------------------
    PATHWAY_MEMBERSHIP = "pathway_membership"
    CASCADE_POSITION = "cascade_position"          # what is upstream, what is downstream
    ANALOGOUS_CASCADE_ROLE = "analogous_cascade_role"
    """Occupying the *same position* in a different cascade.

    Kept as its own checklist item rather than folded into pathway membership, because
    it is the one an agent reliably skips. Pathway membership asks "who else is in my
    cascade?"; this asks "whose cascade has a slot shaped like mine?" — and the answer
    can be a protein with no homology, no shared pathway, and no shared partner, which
    is precisely why no similarity search returns it.
    """
    BINDING_PARTNERS = "binding_partners"           # obligate and transient PPI
    SHARED_REGULATORS = "shared_regulators"         # common upstream control
    COMPLEX_MEMBERSHIP = "complex_membership"       # heterodimers, obligate partners

    # -- where and when it exists ------------------------------------------
    TISSUE_LOCALISATION = "tissue_localisation"
    SUBCELLULAR_LOCALISATION = "subcellular_localisation"
    EXPRESSION_CORRELATION = "expression_correlation"
    INDUCIBILITY = "inducibility"                   # constitutive vs induced

    # -- what it does ------------------------------------------------------
    BIOLOGICAL_PROCESS = "biological_process"
    ENDOGENOUS_VS_XENOBIOTIC = "endogenous_vs_xenobiotic"
    MECHANISM_CLASS = "mechanism_class"             # TF, kinase, transporter, protease...
    CONFORMATIONAL_BEHAVIOUR = "conformational_behaviour"
    POST_TRANSLATIONAL = "post_translational"

    # -- how it is studied -------------------------------------------------
    ASSAY_PRECEDENT = "assay_precedent"             # how the field measures it
    STRUCTURAL_COVERAGE = "structural_coverage"     # how much experimental structure exists
    SPECIES_CONSERVATION = "species_conservation"
    DISEASE_ASSOCIATION = "disease_association"

    # -- chemistry-side analogues (DEL / cheminformatics targets) ----------
    SCAFFOLD_CLASS = "scaffold_class"
    FUNCTIONAL_GROUP_CONTENT = "functional_group_content"
    PHYSCHEM_REGIME = "physchem_regime"             # the property space it occupies
    SYNTHETIC_ROUTE_CLASS = "synthetic_route_class"
    LIBRARY_DESIGN = "library_design"               # how the collection was built

    @property
    def question(self) -> str:
        """The question this item asks of a target, in the form a worker can act on."""
        return _KIND_QUESTIONS[self.value]


_KIND_QUESTIONS: dict[str, str] = {
    "sequence_identity": "Which proteins share detectable sequence identity with the target?",
    "fold": "Which proteins share the target's fold or topology at low sequence identity?",
    "domain_architecture": "Which proteins have the same arrangement of domains?",
    "family_membership": "Which families, subfamilies and superfamilies does the target belong "
                         "to, and who else is in each?",
    "motif_content": "Which local motifs or learned features does the target carry, and what "
                     "else carries them?",
    "pocket_character": "What kind of pocket is it, and which unrelated proteins have a pocket "
                        "of the same character?",
    "pocket_plasticity": "Does the pocket change shape on binding, and which proteins share "
                         "that behaviour?",
    "ligand_promiscuity": "How broad is its ligand range, and which other proteins are "
                          "similarly promiscuous?",
    "known_chemotypes": "Which chemical series are known to engage it, and what else do those "
                        "series hit?",
    "cofactor_dependence": "What cofactors or partners does activity require?",
    "pathway_membership": "Which pathways contain the target, and who else is in them?",
    "cascade_position": "What is directly upstream and downstream of the target?",
    "analogous_cascade_role": "Which proteins occupy the same position in a *different* "
                              "cascade — same trigger class, same effector class, different "
                              "network?",
    "binding_partners": "Which proteins does it physically interact with, and who else shares "
                        "those partners?",
    "shared_regulators": "What controls the target, and what else does that regulator control?",
    "complex_membership": "Does it act as part of an obligate complex, and with whom?",
    "tissue_localisation": "Where is it expressed, and what else is enriched in the same place?",
    "subcellular_localisation": "Which compartment does it occupy?",
    "expression_correlation": "What is it co-expressed with across tissues or conditions?",
    "inducibility": "Is it constitutive or induced, and by what?",
    "biological_process": "Which processes does it participate in, and who else does?",
    "endogenous_vs_xenobiotic": "Does it handle endogenous ligands, foreign chemicals, or both?",
    "mechanism_class": "What kind of molecular machine is it, and what else is that kind?",
    "conformational_behaviour": "Is it rigid, flexible, or partly disordered, and what shares "
                                "that behaviour?",
    "post_translational": "Which modifications regulate it, and what else they regulate?",
    "assay_precedent": "How does the field measure it, and which targets are measured the "
                       "same way?",
    "structural_coverage": "How much experimental structure exists, in which states?",
    "species_conservation": "How conserved is it, and which orthologues carry usable data?",
    "disease_association": "Which diseases or liabilities is it implicated in?",
    "scaffold_class": "Which scaffolds define the series, and what else uses them?",
    "functional_group_content": "Which functional groups are present, and what do they imply?",
    "physchem_regime": "Which region of property space does it occupy?",
    "synthetic_route_class": "How is it made, and what shares that chemistry?",
    "library_design": "How was the collection built, and what biases does that impose?",
}


#: Which checklist applies to which domain.
#:
#: Domain-keyed rather than hardcoded, because the meta-pipeline is not about any one
#: target. A structural-biology run and a DEL run ask genuinely different questions, and a
#: checklist that tried to cover both would be dismissed item-by-item as inapplicable —
#: which trains the habit of dismissing items, defeating the gate.
CHECKLISTS: dict[Domain, tuple[PropertyKind, ...]] = {
    Domain.STRUCTURAL_BIOLOGY: (
        PropertyKind.SEQUENCE_IDENTITY, PropertyKind.FOLD,
        PropertyKind.DOMAIN_ARCHITECTURE, PropertyKind.FAMILY_MEMBERSHIP,
        PropertyKind.MOTIF_CONTENT, PropertyKind.POCKET_CHARACTER,
        PropertyKind.POCKET_PLASTICITY, PropertyKind.LIGAND_PROMISCUITY,
        PropertyKind.KNOWN_CHEMOTYPES, PropertyKind.COFACTOR_DEPENDENCE,
        PropertyKind.PATHWAY_MEMBERSHIP, PropertyKind.CASCADE_POSITION,
        PropertyKind.ANALOGOUS_CASCADE_ROLE, PropertyKind.BINDING_PARTNERS,
        PropertyKind.SHARED_REGULATORS, PropertyKind.COMPLEX_MEMBERSHIP,
        PropertyKind.TISSUE_LOCALISATION, PropertyKind.SUBCELLULAR_LOCALISATION,
        PropertyKind.EXPRESSION_CORRELATION, PropertyKind.INDUCIBILITY,
        PropertyKind.BIOLOGICAL_PROCESS, PropertyKind.ENDOGENOUS_VS_XENOBIOTIC,
        PropertyKind.MECHANISM_CLASS, PropertyKind.CONFORMATIONAL_BEHAVIOUR,
        PropertyKind.POST_TRANSLATIONAL, PropertyKind.ASSAY_PRECEDENT,
        PropertyKind.STRUCTURAL_COVERAGE, PropertyKind.SPECIES_CONSERVATION,
        PropertyKind.DISEASE_ASSOCIATION,
    ),
    Domain.PROTEIN_DESIGN: (
        PropertyKind.SEQUENCE_IDENTITY, PropertyKind.FOLD,
        PropertyKind.DOMAIN_ARCHITECTURE, PropertyKind.FAMILY_MEMBERSHIP,
        PropertyKind.MOTIF_CONTENT, PropertyKind.POCKET_CHARACTER,
        PropertyKind.POCKET_PLASTICITY, PropertyKind.BINDING_PARTNERS,
        PropertyKind.COMPLEX_MEMBERSHIP, PropertyKind.CONFORMATIONAL_BEHAVIOUR,
        PropertyKind.MECHANISM_CLASS, PropertyKind.STRUCTURAL_COVERAGE,
        PropertyKind.SPECIES_CONSERVATION, PropertyKind.ASSAY_PRECEDENT,
    ),
    Domain.DEL_ML: (
        PropertyKind.SCAFFOLD_CLASS, PropertyKind.FUNCTIONAL_GROUP_CONTENT,
        PropertyKind.PHYSCHEM_REGIME, PropertyKind.SYNTHETIC_ROUTE_CLASS,
        PropertyKind.LIBRARY_DESIGN, PropertyKind.KNOWN_CHEMOTYPES,
        PropertyKind.ASSAY_PRECEDENT, PropertyKind.LIGAND_PROMISCUITY,
        PropertyKind.FAMILY_MEMBERSHIP, PropertyKind.POCKET_CHARACTER,
        PropertyKind.DISEASE_ASSOCIATION,
    ),
    Domain.ADMET: (
        PropertyKind.SCAFFOLD_CLASS, PropertyKind.FUNCTIONAL_GROUP_CONTENT,
        PropertyKind.PHYSCHEM_REGIME, PropertyKind.KNOWN_CHEMOTYPES,
        PropertyKind.LIGAND_PROMISCUITY, PropertyKind.MECHANISM_CLASS,
        PropertyKind.TISSUE_LOCALISATION, PropertyKind.INDUCIBILITY,
        PropertyKind.PATHWAY_MEMBERSHIP, PropertyKind.ASSAY_PRECEDENT,
        PropertyKind.SPECIES_CONSERVATION, PropertyKind.DISEASE_ASSOCIATION,
    ),
    Domain.CHEMINFORMATICS: (
        PropertyKind.SCAFFOLD_CLASS, PropertyKind.FUNCTIONAL_GROUP_CONTENT,
        PropertyKind.PHYSCHEM_REGIME, PropertyKind.KNOWN_CHEMOTYPES,
        PropertyKind.LIBRARY_DESIGN, PropertyKind.ASSAY_PRECEDENT,
        PropertyKind.LIGAND_PROMISCUITY, PropertyKind.FAMILY_MEMBERSHIP,
    ),
}


def checklist_for(domain: Domain) -> tuple[PropertyKind, ...]:
    """The checklist for a domain, falling back to the structural-biology superset.

    Falling back to the *largest* checklist rather than an empty one is deliberate: an
    unregistered domain should make the gate harder to pass, not trivially passable.
    """
    return CHECKLISTS.get(domain, CHECKLISTS[Domain.STRUCTURAL_BIOLOGY])


class MetaProperty(BaseModel):
    """One property of the target, and the edges it therefore implies.

    The last field is the one that matters. A property recorded without
    ``implies_predicates`` is trivia; the whole claim of this module is that "the target
    is X" should mechanically produce "therefore search along predicate Y".
    """

    kind: PropertyKind
    value: str = Field(
        ..., min_length=2,
        description="What the target actually is on this dimension, e.g. 'ligand-activated "
                    "transcription factor, NR1I subfamily' or 'liver- and intestine-enriched'.",
    )
    property_node_id: str | None = Field(
        default=None,
        description=(
            "Graph id of the reified Property node, e.g. 'property:promiscuous-binder'. "
            "Reifying it is what makes the property countable and therefore hard to forget."
        ),
    )
    # `why_it_connects` precedes `implies_predicates` deliberately — see
    # `reagent.contracts.ordering`. Under constrained decoding the field order is the
    # generation order, so licensing predicates first means picking whatever looks
    # plausible for the property's *name* and then writing a mechanism to fit.
    why_it_connects: str = Field(
        ..., min_length=20,
        description=(
            "The mechanism by which this property makes two entities comparable. Not "
            "'both are nuclear receptors' but 'both use a ligand-binding domain whose "
            "helix-12 position reports occupancy, so a pose that misplaces helix 12 is "
            "wrong in the same way for both'."
        ),
    )
    implies_predicates: list[str] = Field(
        default_factory=list,
        description=(
            "kg predicates this property licenses a search along, following from the "
            "mechanism above. Empty means this property was noted and then not used, which "
            "is the failure this module exists to make visible."
        ),
    )
    evidence: list[Evidence] = Field(default_factory=list)
    expected_yield: str | None = Field(
        default=None, description="Rough guess at how many entities this axis should return, "
                                  "recorded before searching so a thin result is noticeable."
    )

    @model_validator(mode="after")
    def _connection_is_mechanistic(self) -> MetaProperty:
        """Reject a restatement of the property as its own explanation."""
        v = self.value.strip().lower().rstrip(".")
        w = self.why_it_connects.strip().lower().rstrip(".")
        if w == v or (len(v) > 10 and w.replace("both are ", "").replace("both ", "") == v):
            raise ValueError(
                f"why_it_connects for {self.kind.value} just restates the property "
                f"({self.value!r}). Name the shared mechanism that makes two entities "
                "comparable, and therefore what a model could transfer between them."
            )
        return self


class AxisDerivation(BaseModel):
    """The record of turning a target into a set of search axes.

    The coverage gate is the reason this type exists: ``considered`` plus ``dismissed``
    must together cover the whole checklist. An agent may decide a dimension is
    irrelevant — it may not decide it silently.
    """

    run_id: str
    domain: Domain
    target_id: str
    considered: list[MetaProperty] = Field(default_factory=list)
    dismissed: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "PropertyKind value -> why it does not apply to this target. A reason like "
            "'not relevant' fails the check; say what about the target makes it moot."
        ),
    )
    derived_axes: list[str] = Field(
        default_factory=list, description="AxisSpec names produced from these properties."
    )

    @property
    def checklist(self) -> tuple[PropertyKind, ...]:
        return checklist_for(self.domain)

    def uncovered_kinds(self) -> list[str]:
        """Checklist items neither used nor dismissed. **The premature-stop detector.**"""
        seen = {p.kind for p in self.considered} | {
            PropertyKind(k) for k in self.dismissed if k in PropertyKind._value2member_map_
        }
        return [k.value for k in self.checklist if k not in seen]

    def unused_properties(self) -> list[str]:
        """Properties noted but wired to no predicate — recognised and then dropped."""
        return [p.kind.value for p in self.considered if not p.implies_predicates]

    def lazy_dismissals(self) -> list[str]:
        """Dismissals that do not say anything about *this* target."""
        lazy: list[str] = []
        for kind, reason in self.dismissed.items():
            r = (reason or "").strip().lower()
            if len(r) < 20 or r in {
                "not relevant", "n/a", "not applicable", "no data", "unknown",
                "not needed", "out of scope", "irrelevant",
            }:
                lazy.append(kind)
        return lazy

    def unknown_kinds(self) -> list[str]:
        """Dismissal keys that are not real checklist items — usually a typo.

        Worth catching because a typo'd key silently fails to cover the item it meant to,
        and the coverage gate then reports a gap the author believes they closed.
        """
        return sorted(k for k in self.dismissed if k not in PropertyKind._value2member_map_)

    def problems(self) -> list[str]:
        out: list[str] = []
        if bad := self.unknown_kinds():
            out.append(
                f"dismissed names {bad} which are not checklist items for "
                f"{self.domain.value} — likely a typo, and it covers nothing"
            )
        if gaps := self.uncovered_kinds():
            out.append(
                f"{len(gaps)} checklist items neither used nor dismissed: {gaps}. "
                "Each is a way the target could be connected that nobody decided about. "
                "This is the exact shape of the miss that cannot be recovered later."
            )
        if unused := self.unused_properties():
            out.append(
                f"properties recognised but wired to no predicate: {unused}. Noting that "
                "the target is a kind of thing, then not searching along it, is the "
                "failure this derivation exists to prevent."
            )
        if lazy := self.lazy_dismissals():
            out.append(
                f"dismissals with no target-specific reason: {lazy}. Say what about this "
                "target makes the dimension moot, so a reader can disagree."
            )
        return out

    def summary(self) -> str:
        total = len(self.checklist)
        covered = total - len(self.uncovered_kinds())
        lines = [
            f"Axis derivation for {self.target_id} ({self.domain.value})",
            f"  checklist coverage: {covered}/{total}",
            f"  {len(self.considered)} properties -> {len(self.derived_axes)} axes",
        ]
        for p in self.considered:
            preds = ", ".join(p.implies_predicates) or "NO PREDICATE"
            lines.append(f"    {p.kind.value:<26} {p.value[:52]:<52} -> {preds}")
        if self.dismissed:
            lines.append("  dismissed:")
            lines += [f"    {k}: {v}" for k, v in sorted(self.dismissed.items())]
        if probs := self.problems():
            lines.append("  problems:")
            lines += [f"    - {p}" for p in probs]
        return "\n".join(lines)


class SweepRound(BaseModel):
    """One round of searching within a single axis. The unit of the discovery curve."""

    n_queries: int = Field(..., ge=0)
    n_candidates: int = Field(..., ge=0, description="Entities returned this round.")
    n_new: int = Field(..., ge=0, description="Of those, not seen in an earlier round.")
    strategy: str = Field(
        ..., min_length=5,
        description="What was tried this round, and how it differed from the last. Repeating "
                    "a strategy and getting nothing new is not evidence of saturation.",
    )

    @model_validator(mode="after")
    def _new_within_candidates(self) -> SweepRound:
        if self.n_new > self.n_candidates:
            raise ValueError(
                f"n_new ({self.n_new}) exceeds n_candidates ({self.n_candidates})"
            )
        return self


class AxisSweep(BaseModel):
    """One axis, worked by one worker, until the discovery curve flattens.

    ``worker`` is required and is meant to be distinct per axis. The reason is the
    observed failure: a single agent holding every axis at once runs out of context,
    silently reprioritises, and returns a plausible subset. Splitting one worker per axis
    makes the reprioritisation impossible rather than discouraged — a worker that can only
    see one axis cannot trade it against another.
    """

    axis: str
    worker: str = Field(
        ..., min_length=1,
        description="Identifier of the subagent that owned this axis, e.g. 'sweep:pathway#1'.",
    )
    question: str = Field(..., min_length=15)
    predicate: str
    rounds: list[SweepRound] = Field(default_factory=list)
    n_admitted: int = Field(default=0, ge=0, description="Entities that entered the graph.")
    ledger: SearchLedger | None = None
    saturated: bool = Field(
        default=False,
        description="Claim that the curve flattened. Checked against `rounds` — a claim "
                    "without a flat tail is rejected.",
    )
    truncated_because: str | None = Field(
        default=None,
        description=(
            "Set when the sweep stopped for a reason other than saturation: budget, time, "
            "a missing tool. A different word from saturation on purpose, because a "
            "truncated sweep is an open lead and a saturated one is a closed question."
        ),
    )
    negative_result: str | None = Field(
        default=None,
        description=(
            "What was searched and found empty. An axis that legitimately returns nothing "
            "is a finding, and recording it is what stops the next run repeating the work."
        ),
    )

    @property
    def total_new(self) -> int:
        return sum(r.n_new for r in self.rounds)

    @property
    def tail_yield(self) -> float | None:
        """New finds in the last two rounds as a share of all new finds.

        The flatness measure. A low value means late rounds stopped paying, which is what
        saturation looks like from the outside.
        """
        if len(self.rounds) < 3 or not self.total_new:
            return None
        return sum(r.n_new for r in self.rounds[-2:]) / self.total_new

    @property
    def strategies_tried(self) -> int:
        return len({r.strategy.strip().lower() for r in self.rounds})

    @model_validator(mode="after")
    def _stop_reason_is_exclusive(self) -> AxisSweep:
        if self.saturated and self.truncated_because:
            raise ValueError(
                f"axis {self.axis!r} claims both saturation and truncation. A sweep that "
                "ran out of budget did not exhaust its axis; pick the honest one."
            )
        return self

    def problems(self) -> list[str]:
        """Ways this sweep is not yet a defensible claim about the axis."""
        out: list[str] = []
        if not self.rounds:
            out.append(f"axis {self.axis!r}: no rounds recorded — nothing to audit")
            return out
        if self.saturated:
            if len(self.rounds) < 3:
                out.append(
                    f"axis {self.axis!r} claims saturation after {len(self.rounds)} round(s). "
                    "A curve needs at least three points before flatness means anything; "
                    "two rounds cannot distinguish a plateau from a slow start."
                )
            elif (tail := self.tail_yield) is not None and tail > 0.25:
                out.append(
                    f"axis {self.axis!r} claims saturation but its last two rounds produced "
                    f"{tail:.0%} of all new finds. The curve is still climbing; that is the "
                    "signature of stopping early, not of exhausting the axis."
                )
            if self.strategies_tried < 2:
                out.append(
                    f"axis {self.axis!r} claims saturation after one distinct strategy. "
                    "Repeating a query and getting the same answer measures the query, not "
                    "the literature."
                )
        elif not self.truncated_because and not self.negative_result:
            out.append(
                f"axis {self.axis!r} is neither saturated nor truncated and reports no "
                "negative result, so its state is simply unknown"
            )
        if self.ledger:
            out += [f"axis {self.axis!r} ledger: {p}" for p in self.ledger.problems()]
        if self.total_new and not self.n_admitted:
            out.append(
                f"axis {self.axis!r} found {self.total_new} candidates and admitted none. "
                "If they all failed verification, say so as a negative result; otherwise "
                "the admission step was skipped."
            )
        return out

    def curve(self) -> str:
        """The discovery curve as a sparkline, so flatness is visible at a glance."""
        if not self.rounds:
            return ""
        peak = max(r.n_new for r in self.rounds) or 1
        blocks = " ▁▂▃▄▅▆▇█"
        return "".join(blocks[min(8, round(8 * r.n_new / peak))] for r in self.rounds)


class NeighborhoodSweep(BaseModel):
    """All axes for one target, each worked independently.

    The aggregate check is the one that catches the original failure: an axis that was
    derived and then never swept. Deriving twenty axes and running six is worse than
    deriving six, because the report carries the appearance of breadth.
    """

    run_id: str
    target_id: str
    derivation: AxisDerivation
    sweeps: list[AxisSweep] = Field(default_factory=list)

    def unswept_axes(self) -> list[str]:
        done = {s.axis for s in self.sweeps}
        return [a for a in self.derivation.derived_axes if a not in done]

    def open_leads(self) -> list[str]:
        """Axes that stopped short. The honest to-do list for a second pass."""
        return [s.axis for s in self.sweeps if s.truncated_because]

    def overloaded_workers(self) -> dict[str, list[str]]:
        """Workers that owned more than one axis, with the axes they owned."""
        by_worker: dict[str, list[str]] = {}
        for s in self.sweeps:
            by_worker.setdefault(s.worker, []).append(s.axis)
        return {w: axes for w, axes in by_worker.items() if len(axes) > 1}

    def problems(self) -> list[str]:
        out: list[str] = []
        out += [f"derivation: {p}" for p in self.derivation.problems()]
        if unswept := self.unswept_axes():
            out.append(
                f"axes derived but never swept: {unswept}. Deriving an axis and not running "
                "it is worse than never deriving it, because the report reads as broad."
            )
        for w, axes in self.overloaded_workers().items():
            if len(axes) > 2:
                out.append(
                    f"worker {w!r} owned {len(axes)} axes ({axes}). One worker holding many "
                    "axes is the observed failure mode: it runs low on context and quietly "
                    "reprioritises, returning a plausible subset. Split it."
                )
        for s in self.sweeps:
            out += s.problems()
        return out

    def summary(self) -> str:
        lines = [
            f"Neighbourhood sweep for {self.target_id}",
            self.derivation.summary(),
            f"  {len(self.sweeps)} axes swept:",
        ]
        for s in self.sweeps:
            state = (
                "saturated" if s.saturated
                else f"TRUNCATED ({s.truncated_because})" if s.truncated_because
                else "empty" if s.negative_result else "UNKNOWN STATE"
            )
            lines.append(
                f"    {s.axis:<24} {s.curve():<10} {s.n_admitted:>4} admitted  "
                f"[{s.worker}] {state}"
            )
        if leads := self.open_leads():
            lines.append(f"  open leads (truncated, worth resuming): {leads}")
        if probs := self.problems():
            lines.append("  problems:")
            lines += [f"    - {p}" for p in probs]
        return "\n".join(lines)
