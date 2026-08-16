"""Adversarial verification, verifier calibration, and the statistics that bound the design.

Verification is the highest-return component measured anywhere in the orchestration
literature, so these are the checks most worth having right.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from reagent.contracts.verification import (
    GroundingKind,
    Verdict,
    VerifierCalibration,
    VerifierStance,
    WorkerAgreement,
    grounding_mix,
    verification_problems,
)

BECAUSE = (
    "the cited span reports reduced binding in a rodent orthologue, while the claim asserts "
    "abolished binding in human — a strengthening the source does not license"
)


def _verdict(**kw) -> Verdict:
    base = dict(
        claim_id="C-001", verifier="verify:w1", author="extract:w7",
        because=BECAUSE, refuted=True, localised_to="span 2, 'reduced' vs claimed 'abolished'",
    )
    return Verdict(**{**base, **kw})


# ---------------------------------------------------------------------------
# Who may verify what
# ---------------------------------------------------------------------------


def test_a_worker_cannot_verify_its_own_claim():
    with pytest.raises(ValidationError, match="cannot verify its own claim"):
        _verdict(verifier="w1", author="w1")


def test_verification_by_a_different_worker_is_fine():
    v = _verdict()
    assert v.is_clean


def test_an_anonymous_author_is_permitted():
    """Author may be unknown; what is forbidden is a known author verifying itself."""
    assert _verdict(author=None).is_clean


# ---------------------------------------------------------------------------
# Stance — the larger measured lever
# ---------------------------------------------------------------------------


def test_confirmatory_stance_is_rejected_outright():
    with pytest.raises(ValidationError, match="agreeableness"):
        _verdict(stance=VerifierStance.CONFIRMATORY, stance_reason="wanted support")


def test_neutral_stance_requires_a_written_reason():
    with pytest.raises(ValidationError, match="stance_reason"):
        _verdict(stance=VerifierStance.NEUTRAL)
    ok = _verdict(
        stance=VerifierStance.NEUTRAL,
        stance_reason="claim is a licence check with a single authoritative answer",
    )
    assert not ok.is_clean  # permitted, but not the conditions we consider valid


def test_adversarial_is_the_default():
    assert _verdict().stance is VerifierStance.ADVERSARIAL


def test_seeing_author_confidence_makes_a_verdict_unclean():
    assert not _verdict(saw_author_confidence=True).is_clean


# ---------------------------------------------------------------------------
# Localisation — the part verifiers are measurably worst at
# ---------------------------------------------------------------------------


def test_a_refutation_must_say_where_it_fails():
    with pytest.raises(ValidationError, match="localised_to"):
        _verdict(localised_to=None)


def test_an_admission_needs_no_localisation():
    v = _verdict(
        refuted=False, localised_to=None,
        because="the span states the same claim verbatim for the same construct and species",
    )
    assert not v.refuted


def test_because_precedes_refuted_in_the_schema():
    """Generation order under constrained decoding; see contracts.ordering."""
    order = list(Verdict.model_fields)
    assert order.index("because") < order.index("refuted")


# ---------------------------------------------------------------------------
# Grounding mix — retrieval-heavy is the unfavourable half of an asymmetry
# ---------------------------------------------------------------------------


def test_verification_grounded_kinds():
    assert GroundingKind.COMPUTATION.is_verification_grounded
    assert GroundingKind.STRUCTURED_LOOKUP.is_verification_grounded
    assert not GroundingKind.RETRIEVAL.is_verification_grounded
    assert not GroundingKind.CONSENSUS.is_verification_grounded


def test_grounding_mix_sums_to_one():
    vs = [
        _verdict(claim_id=f"C-{i}", grounding=g)
        for i, g in enumerate(
            [GroundingKind.RETRIEVAL] * 7 + [GroundingKind.COMPUTATION] * 3
        )
    ]
    mix = grounding_mix(vs)
    assert mix == {"retrieval": 0.7, "computation": 0.3}


def test_an_almost_entirely_retrieval_batch_is_flagged():
    vs = [_verdict(claim_id=f"C-{i}") for i in range(20)]
    probs = " | ".join(verification_problems(vs))
    assert "retrieval-grounded" in probs


def test_leaning_on_consensus_is_flagged():
    vs = [_verdict(claim_id=f"C-{i}", grounding=GroundingKind.CONSENSUS) for i in range(3)]
    vs += [_verdict(claim_id=f"D-{i}", grounding=GroundingKind.COMPUTATION) for i in range(7)]
    probs = " | ".join(verification_problems(vs))
    assert "Agreement is not" in probs


def test_leaked_confidence_is_flagged_across_a_batch():
    vs = [_verdict(claim_id="C-1", saw_author_confidence=True), _verdict(claim_id="C-2")]
    assert any("author's confidence" in p for p in verification_problems(vs))


def test_an_empty_batch_says_nothing_was_verified():
    assert verification_problems([]) == ["no verdicts recorded — nothing was verified"]


# ---------------------------------------------------------------------------
# Calibration — soundness is the number nobody measures
# ---------------------------------------------------------------------------


def test_completeness_and_soundness():
    c = VerifierCalibration(
        verifier="v", n_true_claims=120, n_true_admitted=111,
        n_false_claims=40, n_false_admitted=6,
    )
    assert c.completeness == pytest.approx(111 / 120)
    assert c.soundness == pytest.approx(1 - 6 / 40)
    assert c.problems() == []


def test_no_injected_falsehoods_means_soundness_is_unmeasured():
    c = VerifierCalibration(
        verifier="v", n_true_claims=50, n_true_admitted=49,
        n_false_claims=0, n_false_admitted=0,
    )
    assert c.soundness is None
    assert any("no falsehoods were injected" in p for p in c.problems())


def test_low_soundness_is_flagged_with_its_consequence():
    c = VerifierCalibration(
        verifier="v", n_true_claims=50, n_true_admitted=48,
        n_false_claims=40, n_false_admitted=16,   # soundness 0.60
    )
    assert any("admits 40% of falsehoods" in p for p in c.problems())


def test_over_rejection_is_flagged_too():
    """The failure people forget: a verifier that rejects everything is broken, not careful."""
    c = VerifierCalibration(
        verifier="v", n_true_claims=100, n_true_admitted=60,   # completeness 0.60
        n_false_claims=40, n_false_admitted=1,
    )
    assert any("rejects 40% of true claims" in p for p in c.problems())


def test_impossible_calibration_counts_are_rejected():
    with pytest.raises(ValidationError, match="more true claims than were presented"):
        VerifierCalibration(
            verifier="v", n_true_claims=10, n_true_admitted=11,
            n_false_claims=5, n_false_admitted=0,
        )
    with pytest.raises(ValidationError, match="more falsehoods than were injected"):
        VerifierCalibration(
            verifier="v", n_true_claims=10, n_true_admitted=9,
            n_false_claims=5, n_false_admitted=6,
        )


def test_optimal_pool_size_shrinks_as_soundness_falls():
    strong = VerifierCalibration(
        verifier="v", n_true_claims=100, n_true_admitted=95,
        n_false_claims=100, n_false_admitted=2,     # soundness 0.98
    )
    weak = VerifierCalibration(
        verifier="v", n_true_claims=100, n_true_admitted=95,
        n_false_claims=100, n_false_admitted=25,    # soundness 0.75
    )
    assert strong.optimal_pool_size() > weak.optimal_pool_size()


def test_a_perfect_verifier_imposes_no_pool_ceiling():
    c = VerifierCalibration(
        verifier="v", n_true_claims=50, n_true_admitted=50,
        n_false_claims=50, n_false_admitted=0,
    )
    assert c.soundness == 1.0
    assert c.optimal_pool_size() is None


def test_higher_false_positive_cost_shrinks_the_pool():
    c = VerifierCalibration(
        verifier="v", n_true_claims=100, n_true_admitted=95,
        n_false_claims=100, n_false_admitted=10,
    )
    assert c.optimal_pool_size(1.0) > c.optimal_pool_size(10.0)


# ---------------------------------------------------------------------------
# The statistics that bound the design
# ---------------------------------------------------------------------------


def _agree(**kw) -> WorkerAgreement:
    base = dict(
        n_items=240, n_workers=4, n_all_wrong=14, n_any_right=226, n_system_right=205,
    )
    return WorkerAgreement(**{**base, **kw})


def test_beta_bounds_accuracy():
    a = _agree()
    assert a.all_wrong_rate == pytest.approx(14 / 240)
    assert a.accuracy_ceiling == pytest.approx(1 - 14 / 240)


def test_oracle_gap_names_a_recoverable_loss():
    a = _agree()
    assert a.oracle_gap == pytest.approx((226 - 205) / 226)


def test_counts_must_partition_the_items():
    with pytest.raises(ValidationError, match="must equal n_items"):
        _agree(n_all_wrong=10)


def test_the_system_cannot_output_what_no_worker_found():
    with pytest.raises(ValidationError, match="cannot output what no worker found"):
        _agree(n_system_right=230)


def test_a_large_oracle_gap_is_reported_as_aggregation_loss():
    a = _agree(n_system_right=150)   # gap ~34%
    assert any("aggregation loss" in p for p in a.problems())


def test_a_high_all_wrong_rate_says_more_workers_will_not_help():
    a = _agree(n_all_wrong=40, n_any_right=200, n_system_right=195)
    assert any("More workers of the same kind" in p for p in a.problems())


def test_within_family_correlation_is_flagged():
    a = _agree(mean_pairwise_rho=0.71)
    assert any("closer to one worker" in p for p in a.problems())


def test_a_clean_run_reports_nothing_but_the_family_note():
    a = _agree(n_system_right=224, n_all_wrong=4, n_any_right=236,
               mean_pairwise_rho=0.31, worker_family=None)
    assert a.problems() == []


def test_zero_recoverable_items_does_not_divide_by_zero():
    a = WorkerAgreement(
        n_items=10, n_workers=2, n_all_wrong=10, n_any_right=0, n_system_right=0
    )
    assert a.oracle_gap == 0.0
    assert a.accuracy_ceiling == 0.0
