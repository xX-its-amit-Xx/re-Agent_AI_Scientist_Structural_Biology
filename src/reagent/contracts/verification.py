"""Adversarial verification, and the two statistics that bound it.

Verification is the highest-return component in this pipeline, and the evidence for that is
not close. A dedicated inspector agent recovered up to **96.4%** of errors introduced by a
faulty agent, out-performing every topology change the same authors measured (Huang et al.,
arXiv:2408.00989). MAST's single largest intervention gain was **+15.6% from adding an
objective-verification step**, and its whole verification category — incorrect verification
9.10%, no or incomplete verification 8.20%, premature termination 6.20% — is verification
failure (Cemri et al., arXiv:2503.13657 v3).

Three findings shape how it must be done, and the first was a surprise.

**Framing beats freshness.** We assumed a fresh-context critic was the main lever. On staged
adversarial code review, a *full-context* protocol closed only **50%** of the attack gap —
*"ruling out context fragmentation as the sole explanation"* — while **reframing the reviewer
as an adversarial pentester cut evasion to 3.0-17.6%**, and an open-weight model under that
framing detected **88.4% of attacks at a 4.6% false-positive rate** (arXiv:2605.03952).
Context isolation is still worth having; it is not the biggest lever. Ask the verifier to
*find the reason this fails*, not to *check whether it holds*.

**The author's confidence is contagious, and stating it up front is the worst case.**
Sycophancy appears in **58.19%** of challenge cases, and **preemptive** rebuttals produce
*more* of it (61.75%) than in-context ones (56.52%) (arXiv:2502.08177). Both humans and
preference models *"prefer convincingly-written sycophantic responses over correct ones a
non-negligible fraction of the time"* (arXiv:2310.13548). So a claim goes to the verifier as a
bare proposition: no hedges, no confidence label, no author.

**Self-verification is net-harmful and the deficit is localised.** GPT-4 self-critique on
GSM8K fell 95.5% → 89.0% across two rounds, with correct→incorrect changes outnumbering the
reverse (arXiv:2310.01798), and an LLM self-critic scored *below no critic at all* on two of
three planning domains — 5%→3% and 16%→2% — because it rejects correct answers at a 95.8%
false-negative rate (arXiv:2402.08115). But the deficit is in **finding** the error, not fixing
it: GPT-4 locates a mistake in only 39.47% of faulty traces, and gains +23.5 to +43.9 points
once told where (arXiv:2311.08516). So spend the verification budget on *localisation*, and
never let the author be its own verifier.

The two statistics
------------------
``soundness`` and ``completeness`` make the verifier itself measurable rather than assumed.
A verifier calibrated on real unit tests admitted **25% of incorrect solutions** at perfect
completeness, and the authors' warning generalises exactly to us: *"the gaps we identify would
have been invisible if we had used HumanEval and MBPP both as verifiers and as benchmarks"*
(arXiv:2411.17501).

``all_wrong_rate`` (beta) is the one that bounds the whole design. Across 67 models the observed
all-wrong rate was **0.052** against **0.023** predicted from marginals plus pairwise
correlations — a ~2.5x underpricing of the tail — **and it is proven that average pairwise
error correlation rho cannot identify beta**: error laws with identical marginals and identical
pairwise correlations can have different all-wrong rates (arXiv:2606.27288). Since accuracy is
bounded by 1 - beta for any policy that returns one worker's answer, beta is the number that limits
us and rho is merely the number that is easy to compute. Report both.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator

from reagent.contracts.evidence import Evidence


class VerifierStance(str, Enum):
    """How the verifier was asked to approach the claim.

    Not cosmetic. The measured spread between a neutral check and an adversarial one is
    larger than the spread between shared and isolated context, so this field records the
    lever that matters most.
    """

    ADVERSARIAL = "adversarial"
    """Find the reason this claim fails. The default, and the measured best."""

    NEUTRAL = "neutral"
    """Check whether it holds. Weaker, and permitted only with a stated reason."""

    CONFIRMATORY = "confirmatory"
    """Find support for it. Included so that it can be named and rejected — this stance
    measures the verifier's agreeableness, not the claim."""

    @property
    def is_acceptable(self) -> bool:
        return self is not VerifierStance.CONFIRMATORY


class GroundingKind(str, Enum):
    """What actually established the claim.

    The distinction is measured, not conceptual. Evidence tools *"systematically induce
    severe overconfidence due to inherent noise in retrieved information, while verification
    tools… can ground reasoning through deterministic feedback and mitigate miscalibration"*
    (arXiv:2601.07264). Expected calibration error rose with evidence-tool use
    (0.879 → 0.901 → 0.948) and *fell* with verification-tool use (0.971 → 0.913 → 0.890).

    **This pipeline is retrieval-heavy and verification-light, which is the bad half of that
    asymmetry.** Tagging every admitted claim with its grounding kind is what makes the
    imbalance visible, and `mix()` reports it.
    """

    COMPUTATION = "computation"      # we ran something deterministic and checked the output
    STRUCTURED_LOOKUP = "structured_lookup"  # resolved an identifier in an authoritative DB
    RETRIEVAL = "retrieval"          # read it in a source
    CONSENSUS = "consensus"          # several workers agreed. Weakest; see below.
    ASSERTION = "assertion"          # the model said so

    @property
    def is_verification_grounded(self) -> bool:
        """Whether a deterministic check, rather than a report, established it."""
        return self in {GroundingKind.COMPUTATION, GroundingKind.STRUCTURED_LOOKUP}

    @property
    def note(self) -> str:
        return {
            "computation": "Deterministic and re-runnable. Prefer this wherever a claim "
                           "admits it — a count, an identifier resolution, a geometry.",
            "structured_lookup": "Authoritative and re-checkable, though the database can "
                                 "be wrong in ways no amount of re-reading detects.",
            "retrieval": "A report of what a source says. Induces overconfidence; the "
                         "excerpt is what makes it checkable.",
            "consensus": "Agreement is not correctness. Debate degraded majority-vote "
                         "accuracy in 10 of 10 configurations tested, and in up to 86% of "
                         "cases where a worker started correct the group never got there.",
            "assertion": "Ungrounded. Legitimate for a design choice, never for an "
                         "observation about the world.",
        }[self.value]


class Verdict(BaseModel):
    """One verifier's judgement on one claim.

    ``because`` precedes ``refuted`` deliberately — see `reagent.contracts.ordering`. A
    verdict generated before its reasoning is a coin flip with a justification attached.
    """

    claim_id: str
    verifier: str = Field(..., min_length=1, description="Worker id, distinct from the author.")
    author: str | None = Field(
        default=None,
        description="Who made the claim. Recorded so self-verification can be detected.",
    )
    stance: VerifierStance = VerifierStance.ADVERSARIAL
    saw_author_confidence: bool = Field(
        default=False,
        description=(
            "Whether the verifier was shown the author's confidence. Should be False. "
            "Stating confidence up front produces *more* sycophancy than encountering it "
            "mid-conversation, so the preemptive case is the one to avoid."
        ),
    )
    saw_author_trace: bool = Field(
        default=False,
        description=(
            "Whether the verifier saw how the author got there. Usually False — but note "
            "that context isolation is the smaller lever, and full context closed only "
            "half the gap that adversarial framing closed."
        ),
    )

    # Reasoning first, verdict second.
    because: str = Field(
        ..., min_length=25,
        description="The specific reason, worked through before the verdict is named. For a "
                    "refutation, point at what fails: a missing span, a wrong identifier, an "
                    "inference the source does not license.",
    )
    refuted: bool = Field(..., description="Whether the claim failed. Follows from `because`.")
    localised_to: str | None = Field(
        default=None,
        description=(
            "Where exactly it fails — the span, field, step, or number. This is the field "
            "worth paying for: models locate a mistake in under 40% of faulty traces, but "
            "correct it reliably once told where."
        ),
    )
    grounding: GroundingKind = GroundingKind.RETRIEVAL
    evidence: list[Evidence] = Field(default_factory=list)
    stance_reason: str | None = Field(
        default=None, description="Required when stance is not adversarial."
    )

    @model_validator(mode="after")
    def _no_self_verification(self) -> Verdict:
        if self.author and self.author == self.verifier:
            raise ValueError(
                f"{self.verifier!r} cannot verify its own claim {self.claim_id!r}. Intrinsic "
                "self-critique is net-harmful without an external signal — GPT-4 fell from "
                "95.5% to 89.0% on GSM8K across two self-correction rounds, and a self-critic "
                "scored below no critic at all on two of three planning domains."
            )
        return self

    @model_validator(mode="after")
    def _confirmatory_stance_is_rejected(self) -> Verdict:
        if not self.stance.is_acceptable:
            raise ValueError(
                f"stance {self.stance.value!r} on {self.claim_id!r} asks the verifier to find "
                "support, which measures its agreeableness rather than the claim. Use "
                "'adversarial'."
            )
        if self.stance is not VerifierStance.ADVERSARIAL and not (self.stance_reason or "").strip():
            raise ValueError(
                f"stance {self.stance.value!r} on {self.claim_id!r} needs `stance_reason`. "
                "Adversarial framing is the measured default — reframing a reviewer "
                "adversarially cut evasion to 3-18% where full context closed only half the "
                "gap — so a weaker stance is a decision, not a default."
            )
        return self

    @model_validator(mode="after")
    def _refutation_is_specific(self) -> Verdict:
        if self.refuted and not (self.localised_to or "").strip():
            raise ValueError(
                f"refuted claim {self.claim_id!r} has no `localised_to`. An unlocalised "
                "refutation cannot be acted on, and localisation is the part verifiers are "
                "measurably bad at — so it is the part worth requiring."
            )
        return self

    @property
    def is_clean(self) -> bool:
        """Whether this verdict was produced under the conditions we consider valid."""
        return (
            self.stance is VerifierStance.ADVERSARIAL
            and not self.saw_author_confidence
            and (self.author is None or self.author != self.verifier)
        )


class VerifierCalibration(BaseModel):
    """How good the verifier is, measured rather than assumed.

    Estimated by feeding it a set of claims with known status — including **deliberately
    falsified ones**. That is a mechanism with no human analogue: you cannot repeatedly feed
    a human reviewer fabricated claims to calibrate them, at any price. An agent verifier can
    be re-calibrated on every run for the cost of a few extra calls.
    """

    verifier: str
    n_true_claims: int = Field(..., ge=0)
    n_true_admitted: int = Field(..., ge=0, description="True claims correctly admitted.")
    n_false_claims: int = Field(..., ge=0, description="Injected falsehoods.")
    n_false_admitted: int = Field(..., ge=0, description="Injected falsehoods it let through.")
    as_of: str | None = Field(default=None, description="Run id this calibration came from.")

    @model_validator(mode="after")
    def _counts_are_possible(self) -> VerifierCalibration:
        if self.n_true_admitted > self.n_true_claims:
            raise ValueError("admitted more true claims than were presented")
        if self.n_false_admitted > self.n_false_claims:
            raise ValueError("admitted more falsehoods than were injected")
        return self

    @property
    def completeness(self) -> float | None:
        """Fraction of true claims admitted. High is easy; it is not the interesting one."""
        if not self.n_true_claims:
            return None
        return self.n_true_admitted / self.n_true_claims

    @property
    def soundness(self) -> float | None:
        """Fraction of falsehoods correctly rejected. **The number that decides how far N
        can be scaled**, and the one nobody measures."""
        if not self.n_false_claims:
            return None
        return 1.0 - (self.n_false_admitted / self.n_false_claims)

    def optimal_pool_size(self, false_positive_cost: float = 4.0) -> int | None:
        """Roughly how many candidates it is worth generating before the filter.

        The reasoning behind the shape rather than the exact constant: a verifier with
        soundness s admits a false candidate with probability (1-s) per draw, so the expected
        number of admitted falsehoods grows with the pool while coverage gains flatten. When
        a false positive costs ``false_positive_cost`` times what a miss does, the optimum is
        small — measured at K <= 5 for every model tested at a cost ratio of 4, and **K = 0**
        at a ratio of 10, *"effectively making them useless"* (arXiv:2411.17501).

        Returned as an order-of-magnitude guide, not a computed optimum. The honest use is:
        if this says 3, do not generate 100 and trust the filter.
        """
        s = self.soundness
        if s is None:
            return None
        if s >= 1.0:
            return None  # a sound verifier imposes no ceiling; scale on budget instead
        # Expected admitted falsehoods per candidate is (1-s); stop when their weighted cost
        # exceeds one unit of expected gain.
        k = int(1.0 / max(1e-9, (1.0 - s) * false_positive_cost))
        return max(0, k)

    def problems(self) -> list[str]:
        out: list[str] = []
        if not self.n_false_claims:
            out.append(
                f"{self.verifier}: no falsehoods were injected, so soundness is unmeasured. "
                "Using the same set as both verifier and benchmark hides exactly the gap "
                "that matters — a verifier can look perfect while admitting a quarter of "
                "wrong answers."
            )
        if (s := self.soundness) is not None and s < 0.7:
            out.append(
                f"{self.verifier}: soundness {s:.0%} — it admits {1 - s:.0%} of falsehoods. "
                "Scaling the candidate pool past a handful will add more accepted errors "
                "than accepted truths."
            )
        if (c := self.completeness) is not None and c < 0.8:
            out.append(
                f"{self.verifier}: completeness {c:.0%} — it rejects {1 - c:.0%} of true "
                "claims. Over-rejection is the documented failure mode of LLM verifiers "
                "(false-negative rates above 95% on some planning tasks), and it is why a "
                "self-critic can score below no critic at all."
            )
        return out

    def summary(self) -> str:
        c, s = self.completeness, self.soundness
        bits = [f"verifier {self.verifier}"]
        if c is not None:
            bits.append(f"completeness {c:.0%}")
        if s is not None:
            bits.append(f"soundness {s:.0%}")
        if (k := self.optimal_pool_size()) is not None:
            bits.append(f"pool guide ~{k}")
        return " · ".join(bits)


class WorkerAgreement(BaseModel):
    """Error correlation across workers, reported as both rho and beta.

    ``all_wrong_rate`` is the load-bearing one. It is *proven* that average pairwise
    correlation cannot identify it — two error laws with identical marginals and identical
    pairwise correlations can have different all-wrong rates — and accuracy is bounded by
    1 - beta for any policy that returns one worker's answer. Measured beta ran ~2.5x above
    what marginals plus pairwise correlations predicted (arXiv:2606.27288).

    So a design that reports rho alone is reporting the number that is easy to compute rather
    than the number that limits it.
    """

    n_items: int = Field(..., gt=0, description="Items every worker was asked about.")
    n_workers: int = Field(..., ge=2)
    n_all_wrong: int = Field(
        ..., ge=0, description="Items on which *every* worker was wrong. The ceiling."
    )
    n_any_right: int = Field(
        ..., ge=0, description="Items on which at least one worker was right."
    )
    n_system_right: int = Field(
        ..., ge=0, description="Items the system actually got right after aggregation."
    )
    mean_pairwise_rho: float | None = Field(
        default=None, ge=-1.0, le=1.0,
        description="Reported for continuity. Insufficient on its own — see the docstring.",
    )
    worker_family: str | None = Field(
        default=None,
        description=(
            "Model family shared by the workers, if any. Within-family error correlation "
            "measured ~0.67 against ~0.53 cross-family in two independent studies."
        ),
    )

    @model_validator(mode="after")
    def _counts_are_consistent(self) -> WorkerAgreement:
        if self.n_all_wrong + self.n_any_right != self.n_items:
            raise ValueError(
                f"n_all_wrong ({self.n_all_wrong}) + n_any_right ({self.n_any_right}) must "
                f"equal n_items ({self.n_items})"
            )
        if self.n_system_right > self.n_any_right:
            raise ValueError(
                f"the system got {self.n_system_right} right but only {self.n_any_right} "
                "items had any worker right — a system cannot output what no worker found"
            )
        return self

    @property
    def all_wrong_rate(self) -> float:
        """beta. Accuracy is bounded above by 1 - beta."""
        return self.n_all_wrong / self.n_items

    @property
    def accuracy_ceiling(self) -> float:
        return 1.0 - self.all_wrong_rate

    @property
    def oracle_gap(self) -> float:
        """DCR: items some worker had right that the system did not output.

        The most actionable single number in the whole instrumentation set, because unlike a
        correlation it names a specific recoverable loss. It reached 86.36% for decentralised
        debate in the study that introduced it, and it is the same quantity
        ``neglected-literature`` measures one level up — the difference between what was
        findable and what was reported.
        """
        if not self.n_any_right:
            return 0.0
        return (self.n_any_right - self.n_system_right) / self.n_any_right

    def problems(self) -> list[str]:
        out: list[str] = []
        if self.oracle_gap > 0.15:
            out.append(
                f"oracle gap {self.oracle_gap:.0%}: on {self.n_any_right - self.n_system_right} "
                "items a worker had the right answer and the system did not output it. That "
                "is aggregation loss, not a capability limit, and it is recoverable."
            )
        if self.all_wrong_rate > 0.1:
            out.append(
                f"all-wrong rate {self.all_wrong_rate:.1%} caps accuracy at "
                f"{self.accuracy_ceiling:.1%} however good the aggregation gets. More workers "
                "of the same kind will not move it — decorrelate the inputs instead."
            )
        if self.mean_pairwise_rho is not None and self.mean_pairwise_rho > 0.6:
            out.append(
                f"mean pairwise error correlation {self.mean_pairwise_rho:.2f} is in the "
                "within-family range (~0.67), so these workers are closer to one worker than "
                "to {n} independent ones".format(n=self.n_workers)
            )
        if self.worker_family and self.n_workers > 2:
            out.append(
                f"all {self.n_workers} workers share the {self.worker_family} family. "
                "Cross-family diversity roughly halves error correlation, but note the "
                "ceiling: heterogeneity bought +0.07 points in one compute-matched test, and "
                "adding a *weaker* model costs accuracy rather than adding diversity."
            )
        return out

    def summary(self) -> str:
        lines = [
            f"{self.n_workers} workers over {self.n_items} items",
            f"  all-wrong rate (beta): {self.all_wrong_rate:.1%}  -> accuracy ceiling "
            f"{self.accuracy_ceiling:.1%}",
            f"  oracle gap (DCR):      {self.oracle_gap:.1%}",
        ]
        if self.mean_pairwise_rho is not None:
            lines.append(f"  mean pairwise rho:     {self.mean_pairwise_rho:.2f} (insufficient alone)")
        if probs := self.problems():
            lines.append("  problems:")
            lines += [f"    - {p}" for p in probs]
        return "\n".join(lines)


def grounding_mix(verdicts: list[Verdict]) -> dict[str, float]:
    """Share of verdicts by grounding kind.

    Read it as a balance check. A pipeline whose claims are almost all `retrieval` is on the
    overconfidence-inducing side of a measured asymmetry, and the fix is to route claims that
    admit a deterministic check — a count, an identifier resolution, a geometry — to a tool
    instead of to a source.
    """
    if not verdicts:
        return {}
    counts: dict[str, int] = {}
    for v in verdicts:
        counts[v.grounding.value] = counts.get(v.grounding.value, 0) + 1
    total = len(verdicts)
    return {k: round(n / total, 3) for k, n in sorted(counts.items(), key=lambda kv: -kv[1])}


def verification_problems(verdicts: list[Verdict]) -> list[str]:
    """Ways a batch of verdicts was not produced under valid conditions."""
    out: list[str] = []
    if not verdicts:
        return ["no verdicts recorded — nothing was verified"]

    if leaked := [v.claim_id for v in verdicts if v.saw_author_confidence]:
        out.append(
            f"{len(leaked)} verdicts saw the author's confidence ({leaked[:5]}). Stating "
            "confidence up front produces more sycophancy than encountering it mid-stream, "
            "so this is the worst version of the exposure."
        )
    if soft := [v.claim_id for v in verdicts if v.stance is not VerifierStance.ADVERSARIAL]:
        out.append(
            f"{len(soft)} verdicts used a non-adversarial stance ({soft[:5]}). Framing is the "
            "larger measured lever — larger than context isolation — so a neutral check is "
            "leaving most of the available gain on the table."
        )
    mix = grounding_mix(verdicts)
    if mix.get("consensus", 0) > 0.1:
        out.append(
            f"{mix['consensus']:.0%} of verdicts rest on worker agreement. Agreement is not "
            "correctness: debate degraded majority-vote accuracy in 10 of 10 configurations "
            "tested, and confidence rises as deliberation proceeds regardless of whether "
            "accuracy does."
        )
    if mix.get("retrieval", 0) > 0.85:
        out.append(
            f"{mix['retrieval']:.0%} of verdicts are retrieval-grounded and almost none are "
            "computation-grounded. Retrieval systematically induces overconfidence while "
            "deterministic checks reduce it, so this is the unfavourable half of a measured "
            "asymmetry. Route checkable claims to a tool."
        )
    if unloc := [v.claim_id for v in verdicts if v.refuted and not v.localised_to]:
        out.append(f"{len(unloc)} refutations are not localised ({unloc[:5]})")
    return out
