"""Expanding the graph outward, bounded and on the record.

The request this answers is *"go further and further, for all possible connections."* The
honest response has two parts, and the first is a refusal.

**Unbounded expansion over a biological graph reaches everything, fast.** Biology is a small
world with enormous hubs — ubiquitin, p53, HSP90, ATP, calcium, the proteasome. Any two human
proteins are typically three hops apart *through* one of them, so a breadth-first walk from any
starting point returns most of the interactome by hop three, and the result is not a
comprehensive graph but an undifferentiated one. Exhaustive-in-principle is worse than useless
here: it produces a picture in which the target's genuine neighbours and a housekeeping protein
that touches everything are drawn identically.

**So the useful version is a prioritised frontier with a stated budget.** Four mechanisms, and
each exists because of a specific way the naive version fails:

``relevance decay``
    Relevance is multiplied down at each hop. Without it, a fourth-hop node arrives with the
    same standing as a first-hop one and the ranking carries no information.

``hub penalty``
    A path *through* a high-degree node conveys almost nothing — "both interact with ubiquitin"
    is true of most of the proteome. Penalising by the intermediate's degree is the same
    correction the graph-gap queries apply, and for the same reason.

``exploration quota``
    A frontier ordered purely by relevance converges on hubs, because hubs are what relevance
    signals point at. This is the popularity lock-in that ``neglected-literature`` counters in
    the published record, appearing again one level down. A fixed fraction of the budget is
    spent on low-degree frontier nodes, as a quota rather than a preference, because a
    preference loses to schedule pressure every time.

``deferred queue``
    What the budget could not reach is **recorded, not dropped**. A frontier that silently
    stops is indistinguishable from one that finished, which is the same failure
    ``AxisSweep.truncated_because`` and ``SearchLedger.known_gaps`` exist to prevent — and the
    same asymmetry drives it: an unexplored region leaves no trace in a graph listing what was
    explored.

The provenance requirement is what makes the result auditable. Every admitted node records
which relation brought it in, at which hop, and through which intermediate — so *"why is
ubiquitin in my graph?"* has an answer, and a bad expansion can be undone by predicate rather
than by hand.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator

#: Relevance multiplier per hop. Steep on purpose: at 0.45, a fourth-hop node starts at about
#: 4% of the focal node's standing, which is roughly the point at which "connected to" stops
#: being a reason to include something.
DEFAULT_DECAY = 0.45

#: Degree at which a node is treated as a hub and paths through it are discounted hard.
#: Not a universal constant — it depends on the graph's density, so it is a parameter with a
#: default rather than a rule.
DEFAULT_HUB_DEGREE = 60


class StopReason(str, Enum):
    """Why expansion stopped. There is no 'finished' — see the module docstring."""

    SATURATED = "saturated"
    """The frontier emptied at or above the relevance floor. The only reason that means the
    region is genuinely covered, and it is rare outside a small subgraph."""

    NODE_BUDGET = "node_budget"
    HOP_BUDGET = "hop_budget"
    RELEVANCE_FLOOR = "relevance_floor"
    TIME_BUDGET = "time_budget"
    QUOTA_EXHAUSTED = "quota_exhausted"

    @property
    def leaves_open_leads(self) -> bool:
        """Whether anything was left on the table. Everything except saturation does."""
        return self is not StopReason.SATURATED


class RelationClass(str, Enum):
    """How far a predicate is allowed to carry relevance.

    Not every relation transmits relevance equally. Two proteins in the same pathway are
    meaningfully related; two compounds appearing in the same paper are not, and letting
    co-citation propagate turns the frontier into a bibliography. So each predicate class gets
    its own multiplier, and the ones that should not propagate at all say so.
    """

    IDENTITY = "identity"          # isoform, ortholog, variant — nearly the same object
    COMPOSITION = "composition"    # part-of; relevance passes almost undiminished
    SIMILARITY = "similarity"      # fold, sequence, chemical
    PHYSICAL = "physical"          # binds, contacts, complexes
    FUNCTIONAL = "functional"      # pathway, regulation, transcription
    CLINICAL = "clinical"          # DDI, ADME
    CONTEXTUAL = "contextual"      # co-expression, shared tissue
    BIBLIOGRAPHIC = "bibliographic"  # supported-by, co-citation. Does NOT propagate.
    METHODOLOGICAL = "methodological"
    """Method-space relations: used-in, evaluated-on, outperforms, alternative-to.

    Non-propagating **for a biology walk**, and that qualifier matters. A frontier expanding
    from a protein must not step onto ``method:boltz-2.1`` and then out to every other protein
    ever evaluated with it — that is a hub of a different kind, and it would flood the walk
    with entities related only by having been benchmarked together. Stage 0, which expands
    method space deliberately, needs its own transmission map where these are the propagating
    class and the biological ones are not.
    """

    @property
    def transmission(self) -> float:
        """Fraction of relevance this class of relation carries to the next node."""
        return {
            "identity": 0.95, "composition": 0.9, "physical": 0.8, "similarity": 0.7,
            "functional": 0.6, "clinical": 0.55, "contextual": 0.35, "bibliographic": 0.0,
            "methodological": 0.0,
        }[self.value]

    @property
    def propagates(self) -> bool:
        return self.transmission > 0.0


#: Which class each predicate belongs to, for relevance transmission. Predicates absent from
#: this map default to ``FUNCTIONAL``, which is deliberately middling — an unmapped predicate
#: should neither dominate the frontier nor be silently excluded from it.
PREDICATE_CLASS: dict[str, RelationClass] = {
    # identity
    "HAS_ISOFORM": RelationClass.IDENTITY, "SPLICE_VARIANT_OF": RelationClass.IDENTITY,
    "ORTHOLOG_OF": RelationClass.IDENTITY, "ENCODED_BY": RelationClass.IDENTITY,
    "HAS_VARIANT": RelationClass.IDENTITY, "VARIANT_AFFECTS": RelationClass.IDENTITY,
    # composition
    "PART_OF": RelationClass.COMPOSITION, "HAS_FRAGMENT": RelationClass.COMPOSITION,
    "HAS_POCKET": RelationClass.COMPOSITION, "POCKET_LINED_BY": RelationClass.COMPOSITION,
    "HAS_STRUCTURE": RelationClass.COMPOSITION, "HAS_MOTIF": RelationClass.COMPOSITION,
    "HAS_PHARMACOPHORE": RelationClass.COMPOSITION,
    "MEMBER_OF_FAMILY": RelationClass.COMPOSITION,
    # similarity
    "SIMILAR_FOLD_TO": RelationClass.SIMILARITY,
    "SIMILAR_SEQUENCE_TO": RelationClass.SIMILARITY,
    "SIMILAR_POCKET_TO": RelationClass.SIMILARITY,
    "SIMILAR_COMPOUND_TO": RelationClass.SIMILARITY,
    "SHARES_MOTIF": RelationClass.SIMILARITY, "SHARES_SCAFFOLD": RelationClass.SIMILARITY,
    "PARALOG_OF": RelationClass.SIMILARITY, "ANALOGOUS_ROLE_TO": RelationClass.SIMILARITY,
    # physical
    "BINDS": RelationClass.PHYSICAL, "CONTACTS": RelationClass.PHYSICAL,
    "OCCUPIES": RelationClass.PHYSICAL, "CO_CRYSTALLIZED_WITH": RelationClass.PHYSICAL,
    "INTERACTS_WITH": RelationClass.PHYSICAL, "COMPLEMENTARY_TO": RelationClass.PHYSICAL,
    "PROMISCUOUS_WITH": RelationClass.PHYSICAL, "COMPETES_WITH": RelationClass.PHYSICAL,
    # functional
    "IN_PATHWAY": RelationClass.FUNCTIONAL, "SHARES_PATHWAY_WITH": RelationClass.FUNCTIONAL,
    "UPSTREAM_OF": RelationClass.FUNCTIONAL, "MODULATES": RelationClass.FUNCTIONAL,
    "PARTICIPATES_IN": RelationClass.FUNCTIONAL,
    "SHARES_PARTNER_WITH": RelationClass.FUNCTIONAL,
    "TRANSCRIPTIONALLY_ACTIVATES": RelationClass.FUNCTIONAL,
    "TRANSCRIPTIONALLY_REPRESSES": RelationClass.FUNCTIONAL,
    "BINDS_PROMOTER_OF": RelationClass.FUNCTIONAL, "REGULATED_BY": RelationClass.FUNCTIONAL,
    "TARGETS_TRANSCRIPT": RelationClass.FUNCTIONAL, "SILENCED_BY": RelationClass.FUNCTIONAL,
    # clinical
    "METABOLIZED_BY": RelationClass.CLINICAL, "TRANSPORTED_BY": RelationClass.CLINICAL,
    "INHIBITS": RelationClass.CLINICAL, "INDUCES": RelationClass.CLINICAL,
    "INTERACTS_CLINICALLY_WITH": RelationClass.CLINICAL,
    "SHARES_TARGET_WITH": RelationClass.CLINICAL,
    # contextual
    "EXPRESSED_IN": RelationClass.CONTEXTUAL, "CO_EXPRESSED_WITH": RelationClass.CONTEXTUAL,
    "CO_REGULATED_WITH": RelationClass.CONTEXTUAL, "HAS_PROPERTY": RelationClass.CONTEXTUAL,
    "SIMILAR_ASSAY_TO": RelationClass.CONTEXTUAL,
    # bibliographic — deliberately non-propagating
    "SUPPORTED_BY": RelationClass.BIBLIOGRAPHIC,
    "CONTRADICTED_BY": RelationClass.BIBLIOGRAPHIC,
    "MEASURED_IN": RelationClass.BIBLIOGRAPHIC, "HAS_DATA": RelationClass.BIBLIOGRAPHIC,
    "DATASET_COVERS": RelationClass.BIBLIOGRAPHIC, "DERIVED_FROM": RelationClass.BIBLIOGRAPHIC,
    "MEASURED_BETWEEN": RelationClass.BIBLIOGRAPHIC,
    # method space — non-propagating in a biology walk; see RelationClass.METHODOLOGICAL
    "USED_IN": RelationClass.METHODOLOGICAL, "EVALUATED_ON": RelationClass.METHODOLOGICAL,
    "OUTPERFORMS": RelationClass.METHODOLOGICAL, "FAILS_ON": RelationClass.METHODOLOGICAL,
    "ALTERNATIVE_TO": RelationClass.METHODOLOGICAL,
    "ANALOGOUS_TO": RelationClass.METHODOLOGICAL,
    "ORIGINATES_IN": RelationClass.METHODOLOGICAL, "INSPIRES": RelationClass.METHODOLOGICAL,
}


def class_of(predicate: str) -> RelationClass:
    """Relation class for a predicate.

    The fallback is ``FUNCTIONAL`` — deliberately middling, so an unmapped predicate neither
    dominates the frontier nor vanishes from it. The test suite asserts the map is complete, so
    the fallback should only ever fire for a predicate added and not yet classified.
    """
    return PREDICATE_CLASS.get(predicate, RelationClass.FUNCTIONAL)


def unclassified_predicates(all_predicates: list[str]) -> list[str]:
    """Predicates with no transmission class. Should always be empty; checked by CI."""
    return sorted(p for p in all_predicates if p not in PREDICATE_CLASS)


class ExpansionBudget(BaseModel):
    """What the walk is allowed to spend, and where a fixed share of it must go."""

    max_nodes: int = Field(default=400, gt=0, description="Admitted nodes, not visited ones.")
    max_hops: int = Field(default=3, ge=1, le=6)
    relevance_floor: float = Field(
        default=0.05, ge=0.0, le=1.0,
        description="Below this, a node is not worth admitting however it was reached.",
    )
    decay: float = Field(default=DEFAULT_DECAY, gt=0.0, le=1.0)
    hub_degree: int = Field(default=DEFAULT_HUB_DEGREE, gt=0)
    exploration_quota: float = Field(
        default=0.2, ge=0.0, le=1.0,
        description=(
            "Share of `max_nodes` reserved for low-degree frontier nodes. A quota, because a "
            "frontier ordered by relevance converges on hubs and a preference for exploring "
            "loses to schedule pressure."
        ),
    )
    max_per_predicate: int | None = Field(
        default=None,
        description=(
            "Cap on nodes admitted through any single predicate. Stops one prolific relation "
            "— usually a PPI dump — from consuming the whole budget."
        ),
    )

    @model_validator(mode="after")
    def _hops_and_decay_agree(self) -> ExpansionBudget:
        reachable = self.decay ** (self.max_hops - 1)
        if reachable < self.relevance_floor:
            raise ValueError(
                f"with decay {self.decay} and floor {self.relevance_floor}, nothing at hop "
                f"{self.max_hops} can clear the floor (best case {reachable:.3f}). Either "
                "raise the decay, lower the floor, or reduce max_hops — as configured the "
                "last hop is dead budget and the walk will look deeper than it is."
            )
        return self


class Admission(BaseModel):
    """One node admitted to the graph, with why it was let in.

    The provenance fields are the point. Without them a fifty-node expansion is fifty nodes
    somebody has to justify by hand, and *"why is ATP in my graph?"* has no answer short of
    re-running the walk.
    """

    node_id: str
    hop: int = Field(..., ge=0)
    relevance: float = Field(..., ge=0.0, le=1.0)
    via_predicate: str = Field(..., description="The relation that brought it in.")
    via_node: str | None = Field(default=None, description="The intermediate it came through.")
    degree: int | None = Field(default=None, ge=0)
    admitted_by: str = Field(
        default="relevance",
        description="'relevance' or 'quota' — the quota admissions are the deliberate ones.",
    )

    @property
    def is_hub(self) -> bool:
        return self.degree is not None and self.degree >= DEFAULT_HUB_DEGREE


class Deferred(BaseModel):
    """A frontier node the budget could not reach. Recorded so the walk can be resumed."""

    node_id: str
    hop: int = Field(..., ge=0)
    relevance: float = Field(..., ge=0.0, le=1.0)
    via_predicate: str
    reason: str = Field(..., description="Which budget it fell outside.")


class ExpansionRun(BaseModel):
    """One outward walk, with everything it admitted and everything it left.

    ``stop_reason`` is required and there is no value meaning "done". Even ``SATURATED`` means
    only that the frontier emptied above the floor — nodes below the floor were still not
    looked at, and they are in ``deferred``.
    """

    run_id: str
    focal: str
    budget: ExpansionBudget
    admitted: list[Admission] = Field(default_factory=list)
    deferred: list[Deferred] = Field(default_factory=list)
    stop_reason: StopReason
    n_visited: int = Field(default=0, ge=0)
    stop_note: str | None = None

    # -- views -------------------------------------------------------------

    def by_hop(self) -> dict[int, int]:
        out: dict[int, int] = {}
        for a in self.admitted:
            out[a.hop] = out.get(a.hop, 0) + 1
        return dict(sorted(out.items()))

    def by_predicate(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for a in self.admitted:
            out[a.via_predicate] = out.get(a.via_predicate, 0) + 1
        return dict(sorted(out.items(), key=lambda kv: -kv[1]))

    def hubs_admitted(self) -> list[str]:
        return [a.node_id for a in self.admitted if a.is_hub]

    @property
    def quota_spent(self) -> float:
        if not self.budget.max_nodes:
            return 0.0
        return sum(1 for a in self.admitted if a.admitted_by == "quota") / self.budget.max_nodes

    @property
    def frontier_left(self) -> int:
        return len(self.deferred)

    def provenance_of(self, node_id: str) -> Admission | None:
        """Why this node is in the graph. The question a reviewer asks first."""
        return next((a for a in self.admitted if a.node_id == node_id), None)

    def problems(self) -> list[str]:
        out: list[str] = []
        if not self.admitted:
            out.append(f"{self.focal}: nothing admitted — the walk did not run or found nothing")
            return out

        if self.stop_reason.leaves_open_leads and not self.deferred:
            out.append(
                f"stopped on {self.stop_reason.value} but recorded no deferred nodes. Any stop "
                "other than saturation leaves a frontier, and an unrecorded frontier is "
                "indistinguishable from a finished walk."
            )
        if self.stop_reason is StopReason.SATURATED and self.frontier_left > 20:
            out.append(
                f"claims saturation with {self.frontier_left} nodes still deferred. Saturation "
                "means the frontier emptied above the relevance floor; this looks like a "
                "budget stop wearing the wrong label."
            )
        if self.budget.exploration_quota and self.quota_spent < self.budget.exploration_quota * 0.7:
            out.append(
                f"exploration quota was {self.budget.exploration_quota:.0%} and "
                f"{self.quota_spent:.0%} was spent. A relevance-ordered frontier converges on "
                "hubs, and the quota is the only thing pulling against that — it is also the "
                "first thing dropped under pressure, which is why it is checked."
            )
        mix = self.by_predicate()
        if mix and max(mix.values()) / len(self.admitted) > 0.6:
            top = max(mix, key=mix.get)
            out.append(
                f"{mix[top] / len(self.admitted):.0%} of admissions came through one predicate "
                f"({top}). One prolific relation has consumed the walk; set "
                "`max_per_predicate` so the other axes get budget."
            )
        hubs = self.hubs_admitted()
        if hubs and len(hubs) / len(self.admitted) > 0.15:
            out.append(
                f"{len(hubs)} of {len(self.admitted)} admissions are hubs ({hubs[:5]}). "
                "A hub is connected to everything, so its presence says little about the "
                "focal node — check the hub penalty is being applied."
            )
        untraced = [a.node_id for a in self.admitted if a.hop > 0 and not a.via_node]
        if untraced:
            out.append(
                f"{len(untraced)} admissions past hop 0 have no `via_node`, so they cannot be "
                f"explained or undone: {untraced[:5]}"
            )
        if self.stop_reason.leaves_open_leads and not self.stop_note:
            out.append("no `stop_note` — say what would be reached by raising the budget")
        return out

    def summary(self) -> str:
        lines = [
            f"Expansion from {self.focal}: {len(self.admitted)} admitted of "
            f"{self.n_visited} visited, {self.frontier_left} deferred",
            "  by hop: " + ", ".join(f"h{k}={v}" for k, v in self.by_hop().items()),
            "  top relations: " + ", ".join(
                f"{k}({v})" for k, v in list(self.by_predicate().items())[:6]
            ),
            f"  stopped: {self.stop_reason.value}"
            + (f" — {self.stop_note}" if self.stop_note else ""),
        ]
        if self.budget.exploration_quota:
            lines.append(
                f"  exploration quota {self.budget.exploration_quota:.0%}, "
                f"spent {self.quota_spent:.0%}"
            )
        if hubs := self.hubs_admitted():
            lines.append(f"  hubs admitted: {hubs[:6]}")
        if probs := self.problems():
            lines.append("  problems:")
            lines += [f"    - {p}" for p in probs]
        return "\n".join(lines)


def relevance_after(
    current: float, predicate: str, budget: ExpansionBudget, degree: int | None = None
) -> float:
    """Relevance a neighbour inherits across one edge.

    Three factors, each correcting a different failure of a plain hop count: the class of
    relation (co-citation carries nothing, isoform identity carries almost everything), the
    per-hop decay, and a penalty for passing through a hub.
    """
    cls = class_of(predicate)
    if not cls.propagates:
        return 0.0
    r = current * cls.transmission * budget.decay
    if degree and degree > budget.hub_degree:
        # Divide by how far past the hub threshold the intermediate is. A node joined to
        # everything tells you almost nothing about any particular thing.
        r /= 1.0 + (degree / budget.hub_degree)
    return max(0.0, min(1.0, r))
