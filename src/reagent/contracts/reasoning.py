"""Reasoning traces — how the agent got to a conclusion, and what it rejected.

Three different things get confused if they share one field, so this project keeps
them apart:

``MethodStep``      what was *run*      (foldseek, 1 call, 40 s, $0)
``Finding``         what was *concluded* (with evidence that the claim is true)
``ReasoningStep``   how the agent *decided*  (options weighed, sources consulted, why)

The third is the one usually missing, and its absence is why an AI-generated analysis
is hard to trust even when every claim is cited. A citation shows a statement is
supported. It does not show why *this* statement was made rather than another, what
alternatives were considered, or which source actually moved the judgement.

So a ``ReasoningStep`` records the decision, the options, the reason, and — separately
from the evidence backing any claim — the sources that **informed the judgement**.
That distinction matters: a paper can be the reason you chose an approach without
being evidence for any particular fact in the report.

The guard that makes this real rather than decorative: **a step that weighed only one
option is not a decision**, it is a default, and must say so explicitly. Recording
defaults as decisions is how a reasoning trace becomes a post-hoc justification.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, Field, model_validator

from .evidence import Confidence, Evidence


class StepKind(str, Enum):
    SCOPE = "scope"                # what question are we answering
    METHOD_CHOICE = "method_choice"  # which tool or approach
    PARAMETER_CHOICE = "parameter_choice"
    INTERPRETATION = "interpretation"  # what the result means
    INCLUSION = "inclusion"        # what to keep or discard
    PRIORITISATION = "prioritisation"  # what to do first, what to skip
    ABANDONMENT = "abandonment"    # stopping a line of work
    ESCALATION = "escalation"      # handing a decision to a human


class Option(BaseModel):
    """One alternative that was actually on the table."""

    name: str = Field(..., min_length=3)
    summary: str | None = Field(
        default=None, description="What taking this option would have meant."
    )
    rejected_because: str | None = Field(
        default=None,
        description=(
            "Why this was not chosen. Required for every option except the chosen one "
            "— an unexplained rejection is indistinguishable from not having looked."
        ),
    )
    cost: str | None = Field(
        default=None, description="Effort, money, or credits this would have taken."
    )


class ReasoningStep(BaseModel):
    """One decision the agent made, with its alternatives and its sources."""

    id: str = Field(..., description="Stable within a report, e.g. 'R-03'.")
    kind: StepKind
    question: str = Field(
        ...,
        min_length=15,
        description="The decision faced, as a question. 'Which similarity axis to run first?'",
    )
    options: list[Option] = Field(
        default_factory=list,
        description="Alternatives genuinely considered. Two or more, or say why not.",
    )
    # `because` precedes `chose` deliberately, and this is the one ordering in the whole
    # schema layer that is load-bearing for accuracy rather than for readability. Under
    # constrained decoding the field order *is* the generation order, so emitting the
    # choice first makes the justification a rationalisation of a commitment already made.
    # Tam et al. (EMNLP 2024) traced exactly this pattern — answer-before-reason in 100% of
    # JSON-mode responses — to a GSM8K drop from 86.51% to 23.44% for one model. See
    # `reagent.contracts.ordering`, which pins this pair so a reorder fails CI.
    because: str = Field(
        ...,
        min_length=25,
        description=(
            "The reasoning, worked through BEFORE naming the choice. What made this the "
            "right call given what was known at the time — not a restatement of the option."
        ),
    )
    chose: str = Field(
        ...,
        min_length=3,
        description=(
            "The option taken, following from the reasoning above. Must match one of "
            "`options` by name when options exist."
        ),
    )
    informed_by: list[Evidence] = Field(
        default_factory=list,
        description=(
            "Sources that shaped this JUDGEMENT — a paper, a benchmark, a prior report, "
            "a reference doc, a computation. Distinct from a Finding's evidence, which "
            "supports a claim rather than a choice. This is the citeable trail behind "
            "the reasoning itself."
        ),
    )
    confidence_then: Confidence = Field(
        default=Confidence.TENTATIVE,
        description="How sure the agent was when deciding. Honest hindsight is not the point.",
    )
    revisit_if: str | None = Field(
        default=None,
        description=(
            "The observation that should reopen this. A decision with no reopening "
            "condition tends to survive long after its reason has expired."
        ),
    )
    no_alternative_because: str | None = Field(
        default=None,
        description=(
            "Required when fewer than two options were weighed: say why there was no "
            "real choice (only one tool available, forced by the contract, and so on). "
            "This keeps genuine defaults from being dressed up as decisions."
        ),
    )
    produced_findings: list[str] = Field(
        default_factory=list, description="Finding ids this step led to."
    )
    produced_artifacts: list[str] = Field(
        default_factory=list, description="Repo-relative paths this step produced."
    )
    superseded_by: str | None = Field(
        default=None, description="A later step id that reversed this one."
    )
    at_utc: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def _a_decision_needs_alternatives(self) -> ReasoningStep:
        real = [o for o in self.options if o.name.strip()]
        if len(real) < 2 and not self.no_alternative_because:
            raise ValueError(
                f"reasoning step {self.id} weighed {len(real)} option(s). Either record "
                "the alternatives you actually considered, or set "
                "`no_alternative_because` to say why there was no choice. A default "
                "recorded as a decision turns the trace into post-hoc justification."
            )
        if real:
            names = {o.name.strip().lower() for o in real}
            if self.chose.strip().lower() not in names:
                raise ValueError(
                    f"reasoning step {self.id} chose {self.chose!r}, which is not among "
                    f"its options {sorted(names)}. Add it as an option or fix the name."
                )
            for o in real:
                if o.name.strip().lower() != self.chose.strip().lower() and not o.rejected_because:
                    raise ValueError(
                        f"reasoning step {self.id}: option {o.name!r} was not chosen but "
                        "gives no `rejected_because`. An unexplained rejection cannot be "
                        "told apart from never having looked at it."
                    )
        return self

    @property
    def rejected(self) -> list[Option]:
        return [
            o for o in self.options
            if o.name.strip().lower() != self.chose.strip().lower()
        ]

    def cited_sources(self) -> list[str]:
        return [e.locator for e in self.informed_by]


class ReasoningTrace(BaseModel):
    """The ordered set of decisions behind a stage, and the questions still open."""

    steps: list[ReasoningStep] = Field(default_factory=list)
    open_decisions: list[str] = Field(
        default_factory=list,
        description="Decisions deliberately deferred, so a reader knows they are pending.",
    )

    @model_validator(mode="after")
    def _ids_unique_and_supersedes_resolve(self) -> ReasoningTrace:
        seen: set[str] = set()
        for s in self.steps:
            if s.id in seen:
                raise ValueError(f"duplicate reasoning step id: {s.id}")
            seen.add(s.id)
        for s in self.steps:
            if s.superseded_by and s.superseded_by not in seen:
                raise ValueError(
                    f"step {s.id} claims to be superseded by {s.superseded_by}, which is "
                    "not in this trace"
                )
        return self

    def all_sources(self) -> list[str]:
        """Every source that informed any decision, deduplicated and sorted.

        This is the answer to "where did the agent's thinking come from" — separate
        from the bibliography of claim-supporting evidence.
        """
        out: set[str] = set()
        for s in self.steps:
            out.update(s.cited_sources())
        return sorted(out)

    def uncited_steps(self) -> list[str]:
        """Decisions taken with no source at all. Sometimes legitimate; always worth seeing."""
        return [s.id for s in self.steps if not s.informed_by]

    def defaults(self) -> list[str]:
        """Steps that were defaults rather than decisions."""
        return [s.id for s in self.steps if s.no_alternative_because]

    def reversals(self) -> list[tuple[str, str]]:
        return [(s.id, s.superseded_by) for s in self.steps if s.superseded_by]

    def for_finding(self, finding_id: str) -> list[ReasoningStep]:
        """Which decisions produced a given finding — the chain a reader can audit."""
        return [s for s in self.steps if finding_id in s.produced_findings]

    def orphan_findings(self, finding_ids: list[str]) -> list[str]:
        """Findings no recorded decision produced.

        Not an error — many findings are direct readings rather than judgement calls —
        but a report where *most* findings are orphans has an unrecorded reasoning path.
        """
        claimed: set[str] = set()
        for s in self.steps:
            claimed.update(s.produced_findings)
        return [f for f in finding_ids if f not in claimed]

    def summary(self) -> str:
        lines = [f"{len(self.steps)} recorded decisions"]
        if d := self.defaults():
            lines.append(f"  {len(d)} were defaults rather than choices: {d}")
        if u := self.uncited_steps():
            lines.append(f"  {len(u)} cite no source: {u}")
        if r := self.reversals():
            lines.append(f"  {len(r)} reversed later: {r}")
        if self.open_decisions:
            lines.append(f"  {len(self.open_decisions)} deliberately still open")
        lines.append(f"  {len(self.all_sources())} distinct sources informed the reasoning")
        return "\n".join(lines)
