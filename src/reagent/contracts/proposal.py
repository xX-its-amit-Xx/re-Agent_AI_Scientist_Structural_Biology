"""Proposals, cross-domain analogies, and the human decision ledger.

The failure mode this module exists to prevent: an agent reads about portfolio
diversification, says "we should ensemble our co-folders!", and the team cannot
tell afterwards whether that idea was tested, adopted, or hallucinated.

So every creative suggestion becomes a ``Proposal`` with:
  * a falsifiable prediction,
  * a stated cost and a kill criterion,
  * an explicit ``mutates`` target naming the pipeline step it would change,
and every human accept/deny becomes an immutable ``Decision`` appended to a
ledger. The orchestrator refuses to run a proposal that has no ACCEPTED
decision, which is how "the user can opt to accept or deny" is enforced in code
rather than in a prompt.

An ``AnalogyCard`` is the intermediate object: a mechanism lifted out of a
foreign domain, described in domain-neutral terms *before* anyone tries to map
it onto biology. Forcing that abstraction step is what stops the analogy engine
from producing surface-level puns ("proteins fold, origami folds").
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from .report import Stage

#: Answers to `Proposal.mutates` that name no specific thing to change. A proposal
#: that mutates "everything" cannot be reviewed, costed, or reverted.
#:
#: Defined at module level rather than as a class attribute because pydantic treats
#: a leading-underscore class attribute as a private attribute, which then is not a
#: plain frozenset at validation time.
VAGUE_MUTATES = frozenset({
    "the whole pipeline", "whole pipeline", "the pipeline", "pipeline",
    "everything", "all of it", "the approach", "the method", "the model",
    "tbd", "todo", "n/a", "-",
})


class Novelty(str, Enum):
    ESTABLISHED_PRACTICE = "established_practice"  # everyone in the field does this
    EMERGING = "emerging"                          # in recent papers, not standard
    TRANSFERRED = "transferred"                    # standard elsewhere, new here
    UNPRECEDENTED = "unprecedented"                # we found no prior art anywhere


class AnalogyCard(BaseModel):
    """A mechanism abstracted out of a non-biology domain.

    Write ``mechanism`` so that a reader cannot tell which domain it came from.
    If you can't, you have described a surface resemblance, not a mechanism.
    """

    id: str = Field(..., description="e.g. 'analogy:finance/regime-switching-ensemble'.")
    source_domain: str = Field(..., description="e.g. 'quantitative finance', 'cybersecurity'.")
    source_practice: str = Field(
        ..., description="What practitioners in that domain actually call and do."
    )
    mechanism: str = Field(
        ...,
        min_length=40,
        description=(
            "The transferable principle in domain-neutral language. No nouns "
            "specific to the source domain."
        ),
    )
    why_it_works_there: str = Field(..., min_length=20)
    structural_precondition: str = Field(
        ...,
        min_length=20,
        description=(
            "What must be true of a problem for this mechanism to help. This is "
            "the field that makes the analogy checkable against our problem."
        ),
    )
    citations: list[str] = Field(
        default_factory=list,
        description="Locators from the source domain (papers, patents, docs, books).",
    )
    discovered_by: str = Field(..., description="Scout agent / skill name.")

    @model_validator(mode="after")
    def _mechanism_is_abstract(self) -> AnalogyCard:
        """Reject a mechanism that merely paraphrases the source practice.

        A token-overlap check rather than string equality, because a scout that
        changes three words would sail past an equality test while having done none
        of the abstraction work. This is still a weak guard — a determined
        paraphrase passes — so the real check is the reviewer reading the card. It
        catches the common lazy case, which is the most it should claim to do.
        """
        def tokens(s: str) -> set[str]:
            return {
                w for w in "".join(
                    c.lower() if c.isalnum() else " " for c in s
                ).split()
                if len(w) > 3
            }

        mech, practice = tokens(self.mechanism), tokens(self.source_practice)
        if not practice:
            return self
        overlap = len(mech & practice) / len(practice)
        if overlap > 0.8:
            shared = sorted(mech & practice)
            raise ValueError(
                f"analogy {self.id}: `mechanism` reuses {overlap:.0%} of the words in "
                f"`source_practice` ({shared}), so it is a paraphrase rather than an "
                "abstraction. Rewrite it so a reader cannot tell which domain it came "
                "from — if nothing survives that rewrite, the analogy is a surface "
                "resemblance and will not transfer."
            )
        return self


class Proposal(BaseModel):
    """A concrete, costed, falsifiable change to the pipeline."""

    id: str = Field(..., description="e.g. 'P-014'.")
    title: str
    target_stage: Stage = Field(..., description="Which stage this would change.")
    mutates: str = Field(
        ...,
        description=(
            "The specific pipeline step, skill, or parameter this replaces or adds. "
            "'the whole pipeline' is not an acceptable answer."
        ),
    )
    rationale: str = Field(..., min_length=30)

    # The scientific core. Without these three a proposal is just an opinion.
    prediction: str = Field(
        ...,
        min_length=20,
        description="What we expect to observe if this works, stated so it could be wrong.",
    )
    kill_criterion: str = Field(
        ...,
        min_length=20,
        description="The observation that would make us abandon this. Be specific.",
    )
    measurable_on: str = Field(
        ...,
        description="The metric/benchmark that decides it, e.g. 'LDDT-PLI on held-out 20 ligands'.",
    )

    novelty: Novelty
    derived_from_analogy: str | None = Field(
        default=None, description="AnalogyCard.id, if this came from cross-domain scouting."
    )
    prior_art: list[str] = Field(
        default_factory=list,
        description="Locators showing who tried this. Empty + UNPRECEDENTED must be justified.",
    )

    # Cost, so a human can triage rather than read 40 equally-weighted ideas.
    est_effort_hours: float | None = None
    est_cost_usd: float | None = None
    credits_needed: list[str] = Field(
        default_factory=list, description="e.g. ['boltz', 'modal', 'tamarind']."
    )
    risk: Literal["low", "medium", "high"] = "medium"
    reversible: bool = Field(
        default=True, description="False means adopting this forecloses other options."
    )

    proposed_by: str
    created_utc: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("mutates")
    @classmethod
    def _mutates_is_specific(cls, v: str) -> str:
        cleaned = v.strip().rstrip(".").lower()
        if cleaned in VAGUE_MUTATES or len(cleaned) < 8:
            raise ValueError(
                f"`mutates` is {v!r}, which names nothing specific. Name the pipeline "
                "step, skill, or parameter this replaces or adds — a proposal whose "
                "target is 'the whole pipeline' cannot be reviewed, costed, or reverted."
            )
        return v.strip()

    @model_validator(mode="after")
    def _unprecedented_needs_justification(self) -> Proposal:
        # Claiming no prior art is allowed, but the rationale must then say that a
        # search was actually run — otherwise "unprecedented" just means "I did not look".
        rationale = self.rationale.lower()
        if (
            self.novelty is Novelty.UNPRECEDENTED
            and not self.prior_art
            and "searched" not in rationale
            and "no prior art" not in rationale
        ):
            raise ValueError(
                f"proposal {self.id} claims UNPRECEDENTED with no prior_art — the "
                "rationale must state what search was run to establish that"
            )
        if self.novelty is Novelty.TRANSFERRED and not self.derived_from_analogy:
            raise ValueError(
                f"proposal {self.id} is TRANSFERRED but names no source analogy card"
            )
        return self


class Verdict(str, Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    DEFERRED = "deferred"      # good idea, not this sprint
    NEEDS_INFO = "needs_info"  # blocked on a question


class Decision(BaseModel):
    """An immutable ledger entry. Append only; never edit or delete.

    To change your mind, append a new Decision with ``supersedes`` set. The
    trail of reversals is itself useful evidence about the pipeline.
    """

    id: str = Field(..., description="e.g. 'D-007'.")
    proposal_id: str
    verdict: Verdict
    decided_by: str = Field(..., description="Human name, or 'auto:<rule>' for gated automation.")
    rationale: str = Field(..., min_length=10, description="Why. Future-you will want this.")
    decided_utc: datetime = Field(default_factory=lambda: datetime.now(UTC))
    supersedes: str | None = None
    conditions: list[str] = Field(
        default_factory=list, description="Acceptance conditions, e.g. 'only if cost < $50'."
    )

    @field_validator("decided_by")
    @classmethod
    def _named_decider(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("decisions must be attributable to a person or a named auto-rule")
        return v.strip()


class DecisionLedger:
    """Append-only JSONL ledger with last-write-wins resolution per proposal."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def append(self, decision: Decision) -> Decision:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(decision.model_dump_json(exclude_none=True) + "\n")
        return decision

    def __iter__(self) -> Iterator[Decision]:
        if not self.path.exists():
            return
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                yield Decision.model_validate(json.loads(line))

    def current(self) -> dict[str, Decision]:
        """Effective verdict per proposal, honouring supersedes ordering."""
        latest: dict[str, Decision] = {}
        for d in sorted(self, key=lambda x: x.decided_utc):
            latest[d.proposal_id] = d
        return latest

    def verdict_for(self, proposal_id: str) -> Verdict | None:
        d = self.current().get(proposal_id)
        return d.verdict if d else None

    def is_accepted(self, proposal_id: str) -> bool:
        """The gate the orchestrator calls before executing anything creative."""
        return self.verdict_for(proposal_id) is Verdict.ACCEPTED

    def accepted(self) -> list[Decision]:
        return [d for d in self.current().values() if d.verdict is Verdict.ACCEPTED]

    def pending(self, proposals: list[Proposal]) -> list[Proposal]:
        seen = self.current()
        return [p for p in proposals if p.id not in seen]


class ProposalSet(BaseModel):
    """A batch of proposals presented to the human for triage in one sitting."""

    run_id: str
    generated_by: str
    target_stage: Stage
    proposals: list[Proposal] = Field(default_factory=list)
    analogies: list[AnalogyCard] = Field(default_factory=list)
    created_utc: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def _analogy_refs_resolve(self) -> ProposalSet:
        known = {a.id for a in self.analogies}
        for p in self.proposals:
            if p.derived_from_analogy and p.derived_from_analogy not in known:
                raise ValueError(
                    f"proposal {p.id} references analogy {p.derived_from_analogy!r} "
                    "which is not included in this set — ship the card with the proposal "
                    "so a reviewer can judge the transfer"
                )
        return self

    def triage_order(self) -> list[Proposal]:
        """Cheap-and-reversible first; that is the order a human should read them in."""
        risk_rank = {"low": 0, "medium": 1, "high": 2}
        return sorted(
            self.proposals,
            key=lambda p: (
                risk_rank[p.risk],
                not p.reversible,
                p.est_effort_hours if p.est_effort_hours is not None else 999.0,
            ),
        )

    def write(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2, exclude_none=True) + "\n", encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: Path) -> ProposalSet:
        return cls.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))


def render_triage_markdown(pset: ProposalSet, ledger: DecisionLedger | None = None) -> str:
    """Human-facing triage sheet. This is what the user actually reads to decide."""
    lines = [
        f"# Proposal triage — {pset.target_stage.value}",
        "",
        f"Run `{pset.run_id}` · generated by `{pset.generated_by}` · "
        f"{len(pset.proposals)} proposals from {len(pset.analogies)} analogy cards",
        "",
        "Ordered cheapest-and-most-reversible first. Record verdicts with "
        "`reagent decide <proposal-id> accept|reject|defer -m \"why\"`.",
        "",
    ]
    for p in pset.triage_order():
        state = ledger.verdict_for(p.id).value if ledger and ledger.verdict_for(p.id) else "pending"
        cost = f"${p.est_cost_usd:.0f}" if p.est_cost_usd is not None else "?"
        hours = f"{p.est_effort_hours:g}h" if p.est_effort_hours is not None else "?"
        lines += [
            f"## {p.id} — {p.title}  `[{state}]`",
            "",
            f"- **Changes:** {p.mutates}",
            f"- **Novelty:** {p.novelty.value} · **Risk:** {p.risk} · "
            f"**Reversible:** {'yes' if p.reversible else 'no'} · **Cost:** {cost} / {hours}",
            f"- **Rationale:** {p.rationale}",
            f"- **Prediction:** {p.prediction}",
            f"- **Kill criterion:** {p.kill_criterion}",
            f"- **Decided on:** {p.measurable_on}",
        ]
        if p.derived_from_analogy:
            card = next((a for a in pset.analogies if a.id == p.derived_from_analogy), None)
            if card:
                lines += [
                    f"- **Transferred from {card.source_domain}** "
                    f"({card.source_practice}): {card.mechanism}",
                    f"  - Holds when: {card.structural_precondition}",
                ]
        if p.prior_art:
            lines.append(f"- **Prior art:** {', '.join(p.prior_art)}")
        lines.append("")
    return "\n".join(lines)
