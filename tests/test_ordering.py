"""Schema field order, which is generation order under constrained decoding.

These tests exist because field order in a pydantic model is not cosmetic: it becomes the
JSON-schema property order, which becomes the order a model emits tokens in when the schema
is enforced. Tam et al. (EMNLP 2024 Industry Track) traced an answer-before-reason field
order to a GSM8K drop from 86.51% to 23.44%, with the pattern present in 100% of the
JSON-mode responses they inspected.

Nearly every inter-agent handoff in this pipeline is a schema-forced object, so a reorder
that looks like tidying can quietly turn a reasoning step into a rationalisation step. The
registry is what makes that fail loudly instead.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from reagent.contracts.axes import AxisSweep, MetaProperty, SweepRound
from reagent.contracts.discovery import ChannelYield, CoverageEstimate
from reagent.contracts.followup import FollowUp
from reagent.contracts.interpret import Implication, Interpretation
from reagent.contracts.ordering import ENFORCED_ORDER, audit, candidate_violations, check_order
from reagent.contracts.proposal import AnalogyCard, Proposal
from reagent.contracts.reasoning import ReasoningStep
from reagent.contracts.report import Finding
from reagent.contracts.verification import Verdict, VerifierCalibration, WorkerAgreement

#: Every model an agent fills directly from a schema. Adding one here is how a new handoff
#: gets its field order reviewed rather than assumed.
AGENT_FILLED: list[type[BaseModel]] = [
    ReasoningStep, Finding, Interpretation, Implication,
    MetaProperty, AxisSweep, SweepRound,
    ChannelYield, CoverageEstimate, FollowUp,
    Proposal, AnalogyCard,
    Verdict, VerifierCalibration, WorkerAgreement,
]


def test_no_agent_filled_model_violates_a_registered_ordering():
    violations, _ = audit(*AGENT_FILLED)
    assert violations == [], "\n".join(violations)


def test_reasoning_step_derives_before_it_concludes():
    """The single most important ordering in the codebase."""
    order = list(ReasoningStep.model_fields)
    assert order.index("because") < order.index("chose")


def test_meta_property_states_the_mechanism_before_licensing_predicates():
    order = list(MetaProperty.model_fields)
    assert order.index("why_it_connects") < order.index("implies_predicates")


def test_implication_takes_a_side_before_grading_its_strength():
    order = list(Implication.model_fields)
    assert order.index("direction") < order.index("strength")


def test_every_registry_rule_names_fields_that_exist():
    """A stale rule enforces nothing while looking like it enforces something."""
    by_name = {m.__name__: m for m in AGENT_FILLED}
    stale: list[str] = []
    for model_name, rules in ENFORCED_ORDER.items():
        model = by_name.get(model_name)
        assert model is not None, (
            f"{model_name} has ordering rules but is not in AGENT_FILLED, so nothing "
            "checks it"
        )
        for derivation, conclusion, _why in rules:
            for field in (derivation, conclusion):
                if field not in model.model_fields:
                    stale.append(f"{model_name}.{field}")
    assert stale == [], f"ordering rules naming fields that no longer exist: {stale}"


def test_every_rule_carries_a_reason():
    for model_name, rules in ENFORCED_ORDER.items():
        for derivation, conclusion, why in rules:
            assert len(why) > 60, (
                f"{model_name}: rule {derivation}->{conclusion} has no real justification, "
                "so the next person to reorder the fields has nothing to weigh"
            )


def test_the_checker_actually_catches_a_bad_order():
    """Guard against the check silently passing everything."""

    class Backwards(BaseModel):
        chose: str = "a"
        because: str = "b"

    Backwards.__name__ = "ReasoningStep"  # borrow the registered rule
    problems = check_order(Backwards)
    assert problems and "generated before" in problems[0]


def test_the_checker_reports_a_stale_rule_rather_than_passing_it():
    class Missing(BaseModel):
        something_else: str = "x"

    Missing.__name__ = "ReasoningStep"
    problems = check_order(Missing)
    assert problems and "stale" in problems[0]


def test_candidate_scan_flags_an_unreviewed_derivation_field():
    class Fresh(BaseModel):
        verdict: str = "yes"
        rationale: str = "because of things"

    cands = candidate_violations(Fresh)
    assert cands and "rationale" in cands[0]


def test_candidate_scan_stays_quiet_when_order_is_already_right():
    class Fine(BaseModel):
        rationale: str = "because of things"
        verdict: str = "yes"

    assert candidate_violations(Fine) == []


@pytest.mark.parametrize("model", AGENT_FILLED, ids=lambda m: m.__name__)
def test_candidate_scan_over_agent_filled_models_is_reviewed(model):
    """Advisory scan. A hit is not a failure — it is a prompt to decide, once, whether the
    later field *derives* the conclusion (reorder and register) or merely *supports* it
    (leave it, and say so in the description). This test records that the decision was made.

    Reviewed and deliberately left alone:
      - Finding.evidence after statement/confidence: evidence supports the claim, it does
        not derive it. Forcing citations before the claim asks an agent to assemble support
        for something it has not yet said.
      - AxisSweep.negative_result after saturated: the end-state fields are alternatives to
        each other, not a conclusion and its derivation, and `rounds` already precedes all
        of them.
    """
    reviewed_exceptions = {"Finding", "AxisSweep"}
    cands = candidate_violations(model)
    if model.__name__ in reviewed_exceptions:
        return
    assert cands == [], "\n".join(cands)
