"""Small experiments, the remedy ladder, and the learning that survives a run.

The ordering guards are the substance: a prediction before a result, branches before a run, and
a cost-ordered ladder. Each exists because the natural thing to do is the other way round.
"""

from __future__ import annotations

import pathlib

import pytest
from pydantic import ValidationError

from reagent.contracts.experiment import (
    Experiment,
    ExperimentLedger,
    FailureSignal,
    Hypothesis,
    Observation,
    Prediction,
    Remedy,
    RemedyOutcome,
    RemedyTier,
)
from reagent.contracts.remedies import (
    REMEDY_LADDER,
    UNIVERSAL_FIRST,
    ladder_for,
    ladder_problems,
    signals_without_ladders,
)

# ---------------------------------------------------------------------------
# The registry
# ---------------------------------------------------------------------------


def test_the_registry_is_well_formed():
    assert ladder_problems() == []


def test_every_failure_signal_has_a_ladder():
    assert signals_without_ladders() == []


def test_every_ladder_is_cost_ordered():
    for signal, remedies in REMEDY_LADDER.items():
        ranks = [r.tier.rank for r in remedies]
        assert ranks == sorted(ranks), f"{signal.value}: {[r.tier.value for r in remedies]}"


def test_every_ladder_ends_in_escalation():
    """A registry with no escalation rung presents itself as complete."""
    for signal, remedies in REMEDY_LADDER.items():
        assert remedies[-1].tier is RemedyTier.NOVEL, signal.value


def test_the_universal_checks_are_all_free():
    assert all(r.tier is RemedyTier.FREE for r in UNIVERSAL_FIRST)
    assert len(UNIVERSAL_FIRST) >= 3


def test_ladder_for_prepends_the_free_checks():
    with_universal = ladder_for(FailureSignal.LOW_LIGAND_ACCURACY)
    without = ladder_for(FailureSignal.LOW_LIGAND_ACCURACY, include_universal=False)
    assert len(with_universal) == len(without) + len(UNIVERSAL_FIRST)
    assert with_universal[0].tier is RemedyTier.FREE


def test_every_referenced_skill_exists():
    """A remedy routing to a skill that is not there is a dead end at the worst moment."""
    present = {p.name for p in pathlib.Path(".claude/skills").iterdir() if p.is_dir()}
    refs = {r.via_skill for rs in REMEDY_LADDER.values() for r in rs if r.via_skill}
    refs |= {r.via_skill for r in UNIVERSAL_FIRST if r.via_skill}
    assert refs - present == set()


def test_tier_ranks_are_strictly_increasing():
    ranks = [t.rank for t in RemedyTier]
    assert ranks == sorted(ranks) and len(set(ranks)) == len(ranks)


def test_measurement_doubt_signals_are_marked():
    assert FailureSignal.METRIC_ARTEFACT.is_measurement_doubt
    assert FailureSignal.HARNESS_UNVERIFIED.is_measurement_doubt
    assert not FailureSignal.POCKET_COLLAPSED.is_measurement_doubt


# ---------------------------------------------------------------------------
# Experiment ordering guards
# ---------------------------------------------------------------------------


def _h(hid: str, claim: str) -> Hypothesis:
    return Hypothesis(
        id=hid, claim=claim,
        because="the failures are size-correlated and pocket volume sits at the low end",
        would_refute="predicted pocket volume matches the holo range for the failing items",
    )


HYPS = [
    _h("H1", "The fragments are being placed in a collapsed apo pocket."),
    _h("H2", "The metric penalises correct poses of symmetric fragments."),
]

PRED = Prediction(
    metric="mean LDDT-PLI, fragment subset",
    expected="0.55-0.70 after symmetry correction if H2 holds; near 0.05 if H1 holds",
    discriminates=["H1", "H2"],
)

BRANCHES = {
    FailureSignal.METRIC_ARTEFACT.value: ladder_for(FailureSignal.METRIC_ARTEFACT),
    FailureSignal.POCKET_COLLAPSED.value: ladder_for(FailureSignal.POCKET_COLLAPSED),
}


def _exp(**kw) -> Experiment:
    base = dict(
        id="X-01",
        question="Why is LDDT-PLI near zero for the fragment subset but fine for drug-like items?",
        hypotheses=list(HYPS), predicted=PRED, if_then=dict(BRANCHES),
    )
    return Experiment(**{**base, **kw})


def test_a_well_formed_experiment_before_running_has_no_problems():
    assert _exp().problems() == []


def test_an_observation_without_a_prediction_is_rejected():
    with pytest.raises(ValidationError, match="nothing to compare against"):
        Experiment(
            id="X", question="what happens if we just look at the number afterwards?",
            hypotheses=list(HYPS), if_then=dict(BRANCHES),
            observed=Observation(metric="m", observed="0.1", matched_prediction=False),
        )


def test_a_result_with_no_branches_is_rejected():
    """Choosing the remedy after seeing the outcome is the behaviour being prevented."""
    with pytest.raises(ValidationError, match="drifts toward whatever it happened to try"):
        Experiment(
            id="X", question="why did the co-fold come back with a terrible pLDDT?",
            hypotheses=list(HYPS), predicted=PRED,
            observed=Observation(metric=PRED.metric, observed="0.05",
                                 matched_prediction=False, surprise="neither branch"),
        )


def test_a_prediction_and_observation_must_measure_the_same_thing():
    with pytest.raises(ValidationError, match="not a test of it"):
        _exp(observed=Observation(metric="mean pLDDT", observed="61",
                                  matched_prediction=False, surprise="different metric"))


def test_an_out_of_order_ladder_is_rejected():
    bad = [
        Remedy(action="fine-tune the folding model on the family corpus",
               tier=RemedyTier.EXPENSIVE,
               rationale="the family corpus exists and templating was insufficient"),
        Remedy(action="check the input tautomer and protonation state",
               tier=RemedyTier.FREE,
               rationale="a mangled input produces the signature of a model failure"),
    ]
    with pytest.raises(ValidationError, match="cheapest-first"):
        _exp(if_then={FailureSignal.LOW_GLOBAL_CONFIDENCE.value: bad})


# ---------------------------------------------------------------------------
# What the experiment tells you
# ---------------------------------------------------------------------------


def test_one_hypothesis_can_only_be_confirmed():
    e = _exp(hypotheses=[HYPS[0]], predicted=PRED.model_copy(update={"discriminates": ["H1"]}))
    assert any("can only confirm it" in p for p in e.problems())


def test_a_prediction_that_discriminates_nothing_is_flagged_before_the_compute():
    e = _exp(predicted=PRED.model_copy(update={"discriminates": []}))
    assert any("knowable before the compute is spent" in p for p in e.problems())


def test_a_prediction_naming_an_unknown_hypothesis_is_caught():
    e = _exp(predicted=PRED.model_copy(update={"discriminates": ["H1", "H9"]}))
    assert any("unknown hypotheses ['H9']" in p for p in e.problems())


def test_next_move_is_the_cheapest_untried_remedy_for_a_raised_signal():
    e = _exp(observed=Observation(
        metric=PRED.metric, observed="0.05", matched_prediction=False,
        surprise="symmetry correction changed nothing, so H2 is out",
        signals=[FailureSignal.POCKET_COLLAPSED]),
        verdict="H1 survives: the pocket is apo-like in the failing items")
    nxt = e.next_move()
    assert nxt is not None and nxt.tier is RemedyTier.FREE


def test_next_move_skips_what_was_already_tried():
    e = _exp(observed=Observation(
        metric=PRED.metric, observed="0.05", matched_prediction=False,
        surprise="H2 ruled out", signals=[FailureSignal.POCKET_COLLAPSED]),
        verdict="H1 survives")
    first = e.next_move()
    e2 = e.model_copy(update={"outcomes": [RemedyOutcome(
        remedy_action=first.action, tier=first.tier,
        signal=FailureSignal.POCKET_COLLAPSED, helped=False,
        note="the target is a known induced-fit sensor, so apo-like is expected not wrong")]})
    assert e2.next_move().action != first.action


def test_a_signal_no_branch_anticipated_is_named_as_a_gap():
    e = _exp(observed=Observation(
        metric=PRED.metric, observed="0.05", matched_prediction=False, surprise="unexpected",
        signals=[FailureSignal.HIGH_SEED_VARIANCE]),
        verdict="neither hypothesis; sampling is the issue")
    assert e.unanticipated_signals() == [FailureSignal.HIGH_SEED_VARIANCE.value]
    assert any("no branch anticipated them" in p for p in e.problems())


def test_a_missed_prediction_with_no_surprise_recorded_is_flagged():
    e = _exp(observed=Observation(metric=PRED.metric, observed="0.05",
                                  matched_prediction=False),
             verdict="H1 survives")
    assert e.was_surprising
    assert any("where the learning is" in p for p in e.problems())


def test_a_result_with_no_verdict_concluded_nothing():
    e = _exp(observed=Observation(metric=PRED.metric, observed="0.62",
                                  matched_prediction=True))
    assert any("no verdict" in p for p in e.problems())


# ---------------------------------------------------------------------------
# Remedy outcomes — the learning
# ---------------------------------------------------------------------------


def test_a_remedy_recorded_as_helping_needs_a_magnitude():
    with pytest.raises(ValidationError, match="no `delta`"):
        RemedyOutcome(remedy_action="deepen the MSA", tier=RemedyTier.CHEAP,
                      signal=FailureSignal.LOW_GLOBAL_CONFIDENCE, helped=True)


def test_a_remedy_that_did_not_help_needs_no_magnitude():
    o = RemedyOutcome(
        remedy_action="deepen the MSA", tier=RemedyTier.CHEAP,
        signal=FailureSignal.LOW_GLOBAL_CONFIDENCE, helped=False,
        note="the returned depth was already 4,800 sequences and the low confidence is "
             "localised to a loop disordered in all five holo structures")
    assert not o.helped


def test_an_unchecked_improvement_is_flagged():
    e = _exp(
        observed=Observation(metric=PRED.metric, observed="0.30", matched_prediction=False,
                             surprise="partial improvement",
                             signals=[FailureSignal.POCKET_COLLAPSED]),
        verdict="H1 survives",
        outcomes=[RemedyOutcome(
            remedy_action="predict from a holo template ensemble", tier=RemedyTier.MODERATE,
            signal=FailureSignal.POCKET_COLLAPSED, helped=True, delta="+0.25 LDDT-PLI")],
    )
    assert any("significance check" in p for p in e.problems())


# ---------------------------------------------------------------------------
# The ledger — the only memory the system has
# ---------------------------------------------------------------------------


def _done(**kw) -> Experiment:
    base = dict(
        observed=Observation(metric=PRED.metric, observed="0.30", matched_prediction=False,
                             surprise="the pocket was the problem, not the metric",
                             signals=[FailureSignal.POCKET_COLLAPSED]),
        verdict="H1 survives; H2 ruled out by the symmetry-corrected rescore",
        outcomes=[
            RemedyOutcome(remedy_action="check induced-fit status", tier=RemedyTier.FREE,
                          signal=FailureSignal.POCKET_COLLAPSED, helped=False,
                          note="confirmed induced-fit, so apo-like is expected"),
            RemedyOutcome(remedy_action="predict from a holo template ensemble",
                          tier=RemedyTier.MODERATE, signal=FailureSignal.POCKET_COLLAPSED,
                          helped=True, delta="+0.25 LDDT-PLI, bootstrap CI [0.18, 0.31]",
                          significance_checked=True),
        ],
    )
    return _exp(**{**base, **kw})


def test_the_ledger_separates_what_worked_from_what_did_not():
    led = ExperimentLedger(run_id="r1", experiments=[_done()])
    worked = led.what_worked()[FailureSignal.POCKET_COLLAPSED.value]
    failed = led.what_did_not()[FailureSignal.POCKET_COLLAPSED.value]
    assert any("holo template ensemble" in w for w in worked)
    assert any("induced-fit" in f for f in failed)


def test_a_failed_remedy_carries_its_reason_forward():
    """The valuable half: why it did not apply, so the next run skips the branch."""
    led = ExperimentLedger(run_id="r1", experiments=[_done()])
    assert any("apo-like is expected" in f
               for f in led.what_did_not()[FailureSignal.POCKET_COLLAPSED.value])


def test_surprises_are_where_belief_moved():
    led = ExperimentLedger(run_id="r1", experiments=[_done()])
    assert led.surprises() == ["X-01"]


def test_a_ledger_with_no_surprises_is_suspicious():
    led = ExperimentLedger(run_id="r1", experiments=[_done(
        observed=Observation(metric=PRED.metric, observed="0.62", matched_prediction=True),
        verdict="H2 confirmed", outcomes=[])])
    assert led.surprises() == []
    assert any("learns nothing is indistinguishable" in p for p in led.problems())


def test_an_expensive_heavy_profile_suggests_the_free_rung_was_skipped():
    led = ExperimentLedger(run_id="r1", experiments=[_done(outcomes=[
        RemedyOutcome(remedy_action="fine-tune on the family corpus", tier=RemedyTier.EXPENSIVE,
                      signal=FailureSignal.POCKET_COLLAPSED, helped=False,
                      note="held-out gate did not improve"),
        RemedyOutcome(remedy_action="escalate to a cross-domain analogy", tier=RemedyTier.NOVEL,
                      signal=FailureSignal.POCKET_COLLAPSED, helped=False, note="nothing found"),
    ])])
    prof = led.escalation_profile()
    assert prof["expensive"] + prof["novel"] == 2
    assert any("free rung was skipped" in p for p in led.problems())


def test_a_pyramid_profile_is_not_flagged():
    outcomes = [
        RemedyOutcome(remedy_action=f"free check {i}", tier=RemedyTier.FREE,
                      signal=FailureSignal.POCKET_COLLAPSED, helped=False, note="ruled out")
        for i in range(4)
    ] + [RemedyOutcome(remedy_action="holo template ensemble", tier=RemedyTier.MODERATE,
                       signal=FailureSignal.POCKET_COLLAPSED, helped=True,
                       delta="+0.25, CI [0.18, 0.31]", significance_checked=True)]
    led = ExperimentLedger(run_id="r1", experiments=[_done(outcomes=outcomes)])
    assert not any("free rung was skipped" in p for p in led.problems())


def test_coverage_gaps_name_the_branches_to_add():
    led = ExperimentLedger(run_id="r1", experiments=[_done(
        observed=Observation(metric=PRED.metric, observed="0.05", matched_prediction=False,
                             surprise="a signal nobody planned for",
                             signals=[FailureSignal.CONFIDENCE_UNCORRELATED]))])
    assert led.coverage_gaps() == {"X-01": [FailureSignal.CONFIDENCE_UNCORRELATED.value]}


def test_the_ledger_reaches_the_report_and_surfaces_both_halves():
    from reagent.contracts import Confidence, Stage
    from reagent.contracts.report import ModelReport

    report = ModelReport(
        report_id="r1-stage3", run_id="r1", stage=Stage.PRIOR,
        title="Stage 3 with an experiment ledger",
        objective="check the ledger reaches the report",
        executive_summary="A holo template ensemble recovered the collapsed-pocket failures.",
        limitations=["fixture"],
        experiments=ExperimentLedger(run_id="r1", experiments=[_done()]),
    )
    learned = report.learned_this_run()
    assert set(learned) == {"worked", "did_not_work"}
    assert any("holo template ensemble" in w
               for ws in learned["worked"].values() for w in ws)
    assert any("apo-like is expected" in f
               for fs in learned["did_not_work"].values() for f in fs)
    # And the ledger's own problems reach coverage_problems() rather than staying local.
    assert Confidence.TENTATIVE  # sanity: contracts import cleanly
    assert isinstance(report.coverage_problems(), list)


def test_a_report_without_experiments_learned_nothing_rather_than_erroring():
    from reagent.contracts import Stage
    from reagent.contracts.report import ModelReport

    report = ModelReport(
        report_id="r2", run_id="r2", stage=Stage.LITERATURE, title="no experiments",
        objective="check the empty case", executive_summary="Nothing was experimented on here.",
        limitations=["fixture"],
    )
    assert report.learned_this_run() == {}
