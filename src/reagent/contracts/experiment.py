"""Small experiments: predict, run, and have the next move already chosen.

The capability this exists for: a co-fold comes back with pLDDT in the fifties, or LDDT-PLI
near zero, and the agent has to pivot rather than shrug. What makes pivoting possible is not a
larger model — it is having decided, **before** the run, what each way it could fail would
mean and what to do about each one.

That ordering is the whole design, and it is the same asymmetry that shapes the rest of this
project. An outcome explained after the fact teaches nothing: any result can be rationalised,
and a model asked *"why did this happen?"* will produce a fluent answer whether or not it
knows. An outcome compared against a prediction written down beforehand is **informative
exactly in proportion to how surprising it is** — which is why ``Prediction`` is required
before ``Observation`` may be attached, and why the contract refuses to let a failure mode be
added after the result is in.

Two consequences worth stating because they are easy to get backwards.

**A failed prediction is a success of the method.** The experiment did its job: it moved a
belief. What is wasted is a run whose outcome was compatible with every hypothesis on the
table, and ``Prediction.discriminates`` is what catches that before the compute is spent.

**The first branch is always "is the failure real?"** A bad number can mean a bad model, or it
can mean a bad metric, a wrong reference, a symmetric-ligand RMSD artefact, or an input the
pipeline mangled. Checking the inputs and the harness costs nothing and resolves a large
fraction of apparent failures, which is why ``RemedyTier.FREE`` exists and why the ladder is
ordered by cost rather than by sophistication.

The remedy ladder is a router, not a reimplementation. Most rungs hand off to a skill that
already exists — ``structure-ensemble`` for widening, ``physics-rescoring`` and
``learned-rescoring`` for challenger signals, ``bottleneck-triage`` for whether the problem is
generation or selection at all, ``significance-discipline`` for whether the difference is real.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator

from reagent.contracts.evidence import Evidence


class RemedyTier(str, Enum):
    """What a remedy costs, which is the order to try them in.

    Ordering by cost rather than by plausibility is deliberate. The expensive remedies are the
    interesting ones and the cheap ones resolve most failures, so an agent left to choose
    freely will reach for a fine-tune when the real problem was a tautomer.
    """

    FREE = "free"
    """Costs nothing but a re-read: check the inputs, the metric, the chain selection, the
    protonation state. **Always exhausted first.** A wrong tautomer looks exactly like a model
    failure and is not one."""

    CHEAP = "cheap"
    """Minutes to an hour of the same compute: more seeds, deeper MSA, more recycles, a
    different conformer generator."""

    MODERATE = "moderate"
    """A different method on the same budget: templating from a homologue, pocket restraints,
    physics rescoring, constrained docking."""

    EXPENSIVE = "expensive"
    """Buys a new artifact: fine-tuning, a custom scoring function fit to this pocket, MD
    refinement, free-energy calculation. Route through ``budget-calibration`` first."""

    NOVEL = "novel"
    """No known remedy applies. Escalate to research — adjacent fields, the neglected
    literature, a cross-domain analogy. The honest last rung, and the one that must not be
    reached before the cheap ones have been tried."""

    @property
    def rank(self) -> int:
        return {"free": 0, "cheap": 1, "moderate": 2, "expensive": 3, "novel": 4}[self.value]


class FailureSignal(str, Enum):
    """A diagnostic that says something went wrong, and roughly where.

    Deliberately about *observations* rather than causes. "Low pLDDT in the pocket" is
    something a harness reports; "the MSA was too shallow" is a hypothesis about why, and
    conflating the two is how a remedy gets applied to the wrong problem.
    """

    # -- the model is unsure -------------------------------------------------
    LOW_GLOBAL_CONFIDENCE = "low_global_confidence"       # pLDDT / pTM low overall
    LOW_POCKET_CONFIDENCE = "low_pocket_confidence"       # low pLDDT localised to the site
    LOW_INTERFACE_CONFIDENCE = "low_interface_confidence"  # ipTM / interface PAE poor
    HIGH_DOMAIN_PAE = "high_domain_pae"                   # domain orientation uncertain

    # -- the ligand is wrong ------------------------------------------------
    LOW_LIGAND_ACCURACY = "low_ligand_accuracy"           # LDDT-PLI / pose RMSD poor
    LIGAND_OUTSIDE_POCKET = "ligand_outside_pocket"
    LIGAND_CLASHES = "ligand_clashes"
    WRONG_STEREOCHEMISTRY = "wrong_stereochemistry"
    IMPLAUSIBLE_INTERNAL_GEOMETRY = "implausible_internal_geometry"  # strain, bad torsions

    # -- the protein is wrong -----------------------------------------------
    POCKET_COLLAPSED = "pocket_collapsed"                 # apo-like prediction, no room
    MISSING_REGION = "missing_region"                     # disordered or unmodelled

    # -- the sampling is wrong ----------------------------------------------
    HIGH_SEED_VARIANCE = "high_seed_variance"             # poses disagree across seeds
    CONSISTENT_BUT_WRONG = "consistent_but_wrong"         # agrees across seeds, still wrong

    # -- the selection is wrong, not the pool -------------------------------
    GOOD_POOL_BAD_PICK = "good_pool_bad_pick"             # oracle gap large
    CONFIDENCE_UNCORRELATED = "confidence_uncorrelated"   # signal does not rank quality

    # -- the measurement is wrong -------------------------------------------
    METRIC_ARTEFACT = "metric_artefact"                   # symmetry, wrong reference, units
    HARNESS_UNVERIFIED = "harness_unverified"             # the scorer was never checked

    @property
    def is_measurement_doubt(self) -> bool:
        """Whether the first move is to doubt the number rather than the model."""
        return self in {
            FailureSignal.METRIC_ARTEFACT, FailureSignal.HARNESS_UNVERIFIED,
            FailureSignal.WRONG_STEREOCHEMISTRY,
        }


class Remedy(BaseModel):
    """One thing to try, with what it costs and who does it."""

    action: str = Field(..., min_length=10, description="What to change, concretely.")
    tier: RemedyTier
    via_skill: str | None = Field(
        default=None,
        description=(
            "The skill that owns this action, when one does. Most remedies are a route to "
            "existing machinery rather than new work — structure-ensemble for widening, "
            "physics-rescoring for a challenger signal, bottleneck-triage for whether the "
            "problem is generation or selection at all."
        ),
    )
    rationale: str = Field(
        ..., min_length=20,
        description="Why this addresses *this* signal. Not why it is generally good practice.",
    )
    expected_effect: str | None = Field(
        default=None,
        description=(
            "What should change if the diagnosis was right, and by roughly how much. Written "
            "before trying it, so the remedy is itself a small experiment."
        ),
    )
    cost_note: str | None = None


class Hypothesis(BaseModel):
    """A candidate explanation for a failure, or a proposition worth testing.

    ``would_refute`` is required. A hypothesis with nothing that would refute it is a
    preference, and an experiment run against it cannot come out either way.
    """

    id: str
    claim: str = Field(..., min_length=15)
    because: str = Field(
        ..., min_length=20, description="What makes this plausible, given what is observed."
    )
    would_refute: str = Field(
        ..., min_length=15,
        description="The observation that would rule this out. Required, and the point.",
    )
    prior: str = Field(
        default="plausible",
        description="How likely this seems before testing: likely / plausible / long-shot.",
    )
    evidence: list[Evidence] = Field(default_factory=list)


class Prediction(BaseModel):
    """What we expect to see, written before the run.

    ``discriminates`` is the field that stops a wasted experiment. If the predicted outcome is
    compatible with every hypothesis on the table, running it costs compute and moves no
    belief — and that is knowable in advance, which is exactly when it is worth knowing.
    """

    metric: str = Field(..., description="What will be measured, e.g. 'mean LDDT-PLI'.")
    expected: str = Field(
        ..., min_length=3,
        description="The expected value or range. A number or an interval, not a direction.",
    )
    threshold: str | None = Field(
        default=None, description="What counts as success, if that differs from the expectation."
    )
    discriminates: list[str] = Field(
        default_factory=list,
        description=(
            "Hypothesis ids this outcome would tell apart. Empty means the experiment cannot "
            "distinguish anything, which is worth knowing before spending the compute."
        ),
    )
    confidence_then: str = Field(
        default="tentative",
        description="How sure we were at the time. Honest hindsight is not the point.",
    )


class Observation(BaseModel):
    """What actually happened. Attached only after a prediction exists."""

    metric: str
    observed: str = Field(..., min_length=1)
    matched_prediction: bool
    surprise: str | None = Field(
        default=None,
        description=(
            "What was unexpected, when the prediction missed. This is where the learning is — "
            "a matched prediction confirms a belief, a missed one changes it."
        ),
    )
    artifacts: list[str] = Field(default_factory=list)
    signals: list[FailureSignal] = Field(
        default_factory=list, description="Diagnostics the run raised."
    )


class RemedyOutcome(BaseModel):
    """Whether a remedy actually helped. The unit of learning across runs.

    Recorded even when it did not, and *especially* when it did not — a remedy that sounds
    right and does not work is the expensive thing to rediscover, and agents have no memory
    across runs except what is written down.
    """

    remedy_action: str
    tier: RemedyTier
    signal: FailureSignal
    helped: bool
    delta: str | None = Field(
        default=None, description="How much the metric moved, with its noise floor if known."
    )
    note: str | None = Field(
        default=None,
        description="What was learned. For a remedy that failed, why it did not apply here.",
    )
    significance_checked: bool = Field(
        default=False,
        description=(
            "Whether the improvement was tested against the noise floor rather than eyeballed. "
            "An unchecked 'helped' on a small eval set is how a pipeline tunes itself to noise."
        ),
    )

    @model_validator(mode="after")
    def _claimed_help_needs_a_number(self) -> RemedyOutcome:
        if self.helped and not (self.delta or "").strip():
            raise ValueError(
                f"remedy {self.remedy_action[:50]!r} is recorded as helping with no `delta`. "
                "An improvement with no magnitude cannot be compared against the noise floor, "
                "and it will be believed by the next run."
            )
        return self


class Experiment(BaseModel):
    """One cycle: hypotheses, a prediction, the anticipated failures, the result.

    The ordering constraints are the substance:

    * ``predicted`` must exist before ``observed`` may be set.
    * ``if_then`` — the anticipated failure modes and their remedies — must be populated
      before the run, and the validator rejects an experiment that recorded an observation
      with no branches. Choosing a remedy after seeing the result is how a pipeline drifts
      toward whatever it happened to try.
    """

    id: str
    question: str = Field(..., min_length=15, description="What this is trying to find out.")
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    predicted: Prediction | None = None
    if_then: dict[str, list[Remedy]] = Field(
        default_factory=dict,
        description=(
            "FailureSignal value -> the remedies to try, cheapest first. Written before the "
            "run. This is the pivot capability: an agent that already decided what a bad "
            "pLDDT would mean does not have to improvise when it sees one."
        ),
    )
    cost_estimate: str | None = None
    observed: Observation | None = None
    outcomes: list[RemedyOutcome] = Field(default_factory=list)
    verdict: str | None = Field(
        default=None,
        description="What is now believed, and which hypothesis survived. Written after.",
    )

    # -- ordering guards ---------------------------------------------------

    @model_validator(mode="after")
    def _prediction_precedes_observation(self) -> Experiment:
        if self.observed is not None and self.predicted is None:
            raise ValueError(
                f"experiment {self.id} has an observation and no prediction. An outcome with "
                "nothing to compare against teaches nothing — any result can be rationalised "
                "afterwards, and a model asked why something happened will answer fluently "
                "whether or not it knows."
            )
        return self

    @model_validator(mode="after")
    def _branches_precede_the_result(self) -> Experiment:
        if self.observed is not None and not self.if_then:
            raise ValueError(
                f"experiment {self.id} recorded a result with no `if_then` branches. The "
                "anticipated failure modes are written before the run; choosing a remedy after "
                "seeing the outcome is how a pipeline drifts toward whatever it happened to try."
            )
        return self

    @model_validator(mode="after")
    def _metrics_line_up(self) -> Experiment:
        if self.observed and self.predicted and self.observed.metric != self.predicted.metric:
            raise ValueError(
                f"experiment {self.id} predicted {self.predicted.metric!r} and observed "
                f"{self.observed.metric!r}. Comparing a prediction to a different measurement "
                "is not a test of it."
            )
        return self

    @model_validator(mode="after")
    def _remedies_are_ordered_by_cost(self) -> Experiment:
        for signal, remedies in self.if_then.items():
            ranks = [r.tier.rank for r in remedies]
            if ranks != sorted(ranks):
                order = [r.tier.value for r in remedies]
                raise ValueError(
                    f"experiment {self.id}, signal {signal!r}: remedies are not ordered "
                    f"cheapest-first ({order}). The expensive ones are the interesting ones "
                    "and the cheap ones resolve most failures, so an unordered ladder reaches "
                    "for a fine-tune when the real problem was a tautomer."
                )
        return self

    # -- views -------------------------------------------------------------

    @property
    def was_surprising(self) -> bool:
        return self.observed is not None and not self.observed.matched_prediction

    def remedies_for(self, signal: FailureSignal) -> list[Remedy]:
        return self.if_then.get(signal.value, [])

    def next_move(self) -> Remedy | None:
        """The cheapest untried remedy for a signal the run actually raised."""
        if not self.observed:
            return None
        tried = {o.remedy_action for o in self.outcomes}
        candidates = [
            r
            for sig in self.observed.signals
            for r in self.remedies_for(sig)
            if r.action not in tried
        ]
        return min(candidates, key=lambda r: r.tier.rank) if candidates else None

    def unanticipated_signals(self) -> list[str]:
        """Signals the run raised that no branch covers. Each one is a gap in the plan."""
        if not self.observed:
            return []
        return [s.value for s in self.observed.signals if s.value not in self.if_then]

    def problems(self) -> list[str]:
        out: list[str] = []
        if len(self.hypotheses) < 2 and self.predicted:
            out.append(
                f"{self.id}: {len(self.hypotheses)} hypothesis. With one explanation on the "
                "table the experiment can only confirm it — there is nothing for the result "
                "to discriminate between."
            )
        if self.predicted and not self.predicted.discriminates:
            out.append(
                f"{self.id}: the prediction discriminates between no hypotheses, so whatever "
                "comes back will be compatible with all of them. That is knowable before the "
                "compute is spent, which is when it is worth knowing."
            )
        if self.predicted:
            ids = {h.id for h in self.hypotheses}
            unknown = [h for h in self.predicted.discriminates if h not in ids]
            if unknown:
                out.append(f"{self.id}: prediction names unknown hypotheses {unknown}")
        if gaps := self.unanticipated_signals():
            out.append(
                f"{self.id}: the run raised {gaps} and no branch anticipated them. Not a "
                "failure — it is the list of branches to add before the next run."
            )
        if self.was_surprising and not (self.observed.surprise or "").strip():
            out.append(
                f"{self.id}: the prediction missed and `surprise` is empty. The miss is where "
                "the learning is; a matched prediction confirms a belief and a missed one "
                "changes it."
            )
        if self.observed and not self.verdict:
            out.append(f"{self.id}: has a result and no verdict — nothing was concluded")
        unchecked = [o for o in self.outcomes if o.helped and not o.significance_checked]
        if unchecked:
            out.append(
                f"{self.id}: {len(unchecked)} remedy(ies) recorded as helping without a "
                "significance check. An unchecked improvement on a small eval set is how a "
                "pipeline tunes itself to noise — route through significance-discipline."
            )
        return out

    def summary(self) -> str:
        lines = [f"[{self.id}] {self.question}"]
        for h in self.hypotheses:
            lines.append(f"  H {h.id}: {h.claim[:80]}  (refuted by: {h.would_refute[:50]})")
        if self.predicted:
            lines.append(
                f"  predict {self.predicted.metric} = {self.predicted.expected}"
                f"  discriminates {self.predicted.discriminates}"
            )
        if self.observed:
            mark = "as predicted" if self.observed.matched_prediction else "SURPRISE"
            lines.append(
                f"  observed {self.observed.metric} = {self.observed.observed}  [{mark}]"
            )
            if self.observed.signals:
                lines.append(f"  signals: {[s.value for s in self.observed.signals]}")
            if nxt := self.next_move():
                lines.append(f"  next: [{nxt.tier.value}] {nxt.action[:70]}")
        if self.verdict:
            lines.append(f"  verdict: {self.verdict}")
        if probs := self.problems():
            lines.append("  problems:")
            lines += [f"    - {p}" for p in probs]
        return "\n".join(lines)


class ExperimentLedger(BaseModel):
    """The run's experiments, and what they taught.

    This is the memory. Agents have none across sessions — the only institutional knowledge the
    system has is what got written down — so a remedy that worked, and more importantly one
    that plausibly should have worked and did not, has to live here or be rediscovered at full
    cost.
    """

    run_id: str
    experiments: list[Experiment] = Field(default_factory=list)

    def what_worked(self) -> dict[str, list[str]]:
        """``signal -> remedies that helped``, for the next run to start from."""
        out: dict[str, list[str]] = {}
        for e in self.experiments:
            for o in e.outcomes:
                if o.helped:
                    out.setdefault(o.signal.value, []).append(f"[{o.tier.value}] {o.remedy_action}")
        return out

    def what_did_not(self) -> dict[str, list[str]]:
        """``signal -> remedies that did not help``. The more valuable half.

        A remedy that sounds right and does not work is the expensive thing to rediscover, and
        it is the half nobody records.
        """
        out: dict[str, list[str]] = {}
        for e in self.experiments:
            for o in e.outcomes:
                if not o.helped:
                    note = f"[{o.tier.value}] {o.remedy_action}"
                    if o.note:
                        note += f" — {o.note}"
                    out.setdefault(o.signal.value, []).append(note)
        return out

    def surprises(self) -> list[str]:
        """Experiments whose prediction missed. Where belief actually moved."""
        return [e.id for e in self.experiments if e.was_surprising]

    def coverage_gaps(self) -> dict[str, list[str]]:
        """Signals raised with no branch to handle them, per experiment."""
        return {
            e.id: gaps for e in self.experiments if (gaps := e.unanticipated_signals())
        }

    def escalation_profile(self) -> dict[str, int]:
        """How many remedies were tried at each tier.

        The shape to want is a pyramid: many free, fewer cheap, rare expensive. An
        expensive-heavy profile usually means the free rung was skipped, which is the single
        most common way effort gets wasted here.
        """
        counts: dict[str, int] = {}
        for e in self.experiments:
            for o in e.outcomes:
                counts[o.tier.value] = counts.get(o.tier.value, 0) + 1
        return {t.value: counts.get(t.value, 0) for t in RemedyTier}

    def problems(self) -> list[str]:
        out: list[str] = []
        for e in self.experiments:
            out += e.problems()
        prof = self.escalation_profile()
        cheap = prof["free"] + prof["cheap"]
        dear = prof["expensive"] + prof["novel"]
        if dear and cheap < dear:
            out.append(
                f"{dear} expensive/novel remedies against {cheap} free/cheap ones. The cheap "
                "rungs resolve most failures — a wrong tautomer looks exactly like a model "
                "failure — so this profile suggests the free rung was skipped."
            )
        if self.experiments and not self.surprises():
            out.append(
                "no prediction missed in any experiment. Either the predictions were vague "
                "enough to accommodate anything, or they were written after the fact. Both "
                "are worth checking, because a run that learns nothing is indistinguishable "
                "from a run that got everything right."
            )
        return out

    def summary(self) -> str:
        lines = [
            f"Experiment ledger for {self.run_id}: {len(self.experiments)} experiments, "
            f"{len(self.surprises())} surprises",
            "  escalation: " + ", ".join(f"{k}={v}" for k, v in self.escalation_profile().items()),
        ]
        if worked := self.what_worked():
            lines.append("  worked:")
            lines += [f"    {sig}: {rs}" for sig, rs in sorted(worked.items())]
        if failed := self.what_did_not():
            lines.append("  did NOT work (do not retry blindly):")
            lines += [f"    {sig}: {rs}" for sig, rs in sorted(failed.items())]
        if gaps := self.coverage_gaps():
            lines.append(f"  unanticipated signals: {gaps}")
        if probs := self.problems():
            lines.append("  problems:")
            lines += [f"    - {p}" for p in probs]
        return "\n".join(lines)
