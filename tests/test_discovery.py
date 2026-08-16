"""Coverage accounting, neglect claims, axis derivation, and progressive disclosure.

The common theme: each test pins a check that exists because a plausible-looking report could
otherwise pass while hiding the thing it was supposed to surface.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from reagent.contracts.axes import (
    CHECKLISTS,
    AxisDerivation,
    AxisSweep,
    MetaProperty,
    NeighborhoodSweep,
    PropertyKind,
    SweepRound,
    checklist_for,
)
from reagent.contracts.discovery import (
    AttentionProfile,
    ChannelYield,
    CoverageEstimate,
    DiscoveryChannel,
    NeglectReason,
    SearchLedger,
)
from reagent.contracts.evidence import Evidence, SourceType
from reagent.contracts.followup import MAX_DEPTH, FollowUp, FollowUpKind, FollowUpTree
from reagent.contracts.problem import Domain

# ---------------------------------------------------------------------------
# Neglect claims must be evidenced, not narrated
# ---------------------------------------------------------------------------


def test_bibliometric_neglect_reason_without_a_signal_is_rejected():
    """"Few citations but ahead of its time" fits every paper; the profile is the check."""
    with pytest.raises(ValidationError, match="without a supporting signal"):
        Evidence(
            source_type=SourceType.PAPER,
            locator="doi:10.0000/fake",
            neglect=[NeglectReason.HIGH_QUALITY_CITERS],
        )


def test_high_quality_citers_needs_named_citers():
    prof = AttentionProfile(n_citations=3, year=2019, as_of_year=2026)
    with pytest.raises(ValidationError):
        Evidence(
            source_type=SourceType.PAPER, locator="doi:x",
            neglect=[NeglectReason.HIGH_QUALITY_CITERS], attention=prof,
        )
    ok = Evidence(
        source_type=SourceType.PAPER, locator="doi:x",
        neglect=[NeglectReason.HIGH_QUALITY_CITERS],
        attention=prof.model_copy(update={"notable_citers": ["doi:seminal"]}),
    )
    assert ok.is_neglected


def test_too_recent_is_bounded_by_actual_age():
    old = AttentionProfile(n_citations=2, year=2015, as_of_year=2026)
    assert not old.supports(NeglectReason.TOO_RECENT)
    with pytest.raises(ValidationError):
        Evidence(source_type=SourceType.PAPER, locator="doi:x",
                 neglect=[NeglectReason.TOO_RECENT], attention=old)

    fresh = AttentionProfile(n_citations=0, year=2025, as_of_year=2026)
    assert fresh.supports(NeglectReason.TOO_RECENT)


def test_prose_only_reasons_require_written_justification():
    """No citation datum can establish that something was prematurely abandoned."""
    with pytest.raises(ValidationError, match="neglect_justification"):
        Evidence(
            source_type=SourceType.PAPER, locator="doi:x",
            neglect=[NeglectReason.PREMATURELY_ABANDONED],
            attention=AttentionProfile(n_citations=40, year=2009, as_of_year=2026),
        )
    ok = Evidence(
        source_type=SourceType.PAPER, locator="doi:x",
        neglect=[NeglectReason.PREMATURELY_ABANDONED],
        attention=AttentionProfile(n_citations=40, year=2009, as_of_year=2026),
        neglect_justification=(
            "Dismissed in a 2011 review for requiring more holo structures than existed; "
            "the PDB now holds 6x as many for this family, so the stated objection expired."
        ),
    )
    assert NeglectReason.PREMATURELY_ABANDONED in ok.neglect


def test_sleeping_beauty_needs_dormancy_and_a_trend():
    flat = AttentionProfile(n_citations=5, year=2005, as_of_year=2026, dormancy_years=12)
    assert not flat.supports(NeglectReason.SLEEPING_BEAUTY)  # dormant but never woke
    woke = flat.model_copy(update={"citation_trend": "flat to 2020, 6x since 2023"})
    assert woke.supports(NeglectReason.SLEEPING_BEAUTY)


def test_citations_per_year_does_not_divide_by_zero():
    p = AttentionProfile(n_citations=4, year=2026, as_of_year=2026)
    assert p.age_years == 0
    assert p.citations_per_year == 4.0


# ---------------------------------------------------------------------------
# Coverage estimation
# ---------------------------------------------------------------------------


def test_chapman_estimate_and_coverage():
    est = CoverageEstimate(
        channel_a=DiscoveryChannel.KEYWORD_SEARCH,
        channel_b=DiscoveryChannel.BACKWARD_SNOWBALL,
        n_a=40, n_b=25, n_both=12, n_total_observed=53,
    )
    # ((41 * 26) / 13) - 1 == 81
    assert est.estimated_population == pytest.approx(81.0)
    assert est.coverage == pytest.approx(53 / 81)
    assert est.channels_are_mechanically_different


def test_zero_overlap_gives_no_estimate_and_says_why():
    est = CoverageEstimate(
        channel_a=DiscoveryChannel.KEYWORD_SEARCH,
        channel_b=DiscoveryChannel.VENUE_SWEEP,
        n_a=10, n_b=8, n_both=0, n_total_observed=18,
    )
    assert est.estimated_population is None
    assert est.coverage is None
    # Disjoint channels are informative, not merely missing data.
    assert "larger" in est.summary()


def test_impossible_overlap_is_rejected():
    with pytest.raises(ValidationError, match="arithmetically impossible"):
        CoverageEstimate(
            channel_a=DiscoveryChannel.KEYWORD_SEARCH,
            channel_b=DiscoveryChannel.BACKWARD_SNOWBALL,
            n_a=5, n_b=4, n_both=6, n_total_observed=9,
        )


def test_total_observed_below_largest_channel_is_rejected():
    with pytest.raises(ValidationError, match="below the larger channel"):
        CoverageEstimate(
            channel_a=DiscoveryChannel.KEYWORD_SEARCH,
            channel_b=DiscoveryChannel.BACKWARD_SNOWBALL,
            n_a=40, n_b=10, n_both=5, n_total_observed=30,
        )


def test_two_pull_channels_are_flagged_as_an_optimistic_pair():
    est = CoverageEstimate(
        channel_a=DiscoveryChannel.KEYWORD_SEARCH,
        channel_b=DiscoveryChannel.SEMANTIC_SEARCH,
        n_a=30, n_b=28, n_both=25, n_total_observed=33,
    )
    assert not est.channels_are_mechanically_different
    assert "optimistic" in est.summary()


def test_pull_and_traversal_classification():
    assert DiscoveryChannel.KEYWORD_SEARCH.is_pull
    assert not DiscoveryChannel.KEYWORD_SEARCH.is_traversal
    assert DiscoveryChannel.FORWARD_SNOWBALL.is_traversal
    assert not DiscoveryChannel.GRAPH_GAP.is_pull


# ---------------------------------------------------------------------------
# Channel yields and the ledger
# ---------------------------------------------------------------------------


def test_admitted_cannot_exceed_retrieved():
    with pytest.raises(ValidationError, match="exceeds retrieved"):
        ChannelYield(channel=DiscoveryChannel.KEYWORD_SEARCH,
                     n_retrieved=5, n_admitted=9)


def test_unique_cannot_exceed_admitted():
    with pytest.raises(ValidationError, match="uniquely found and not admitted"):
        ChannelYield(channel=DiscoveryChannel.KEYWORD_SEARCH,
                     n_retrieved=20, n_admitted=4, n_unique=7)


def _pull_only_ledger() -> SearchLedger:
    return SearchLedger(
        run_id="t",
        channels=[
            ChannelYield(channel=DiscoveryChannel.KEYWORD_SEARCH,
                         n_retrieved=100, n_admitted=45, n_unique=40),
            ChannelYield(channel=DiscoveryChannel.SEMANTIC_SEARCH,
                         n_retrieved=60, n_admitted=5, n_unique=0),
        ],
        exploration_quota=0.2, exploration_spent=0.02,
    )


def test_ledger_flags_the_full_set_of_characteristic_failures():
    probs = " | ".join(_pull_only_ledger().problems())
    assert "no traversal channel" in probs      # pull channels can only return known vocabulary
    assert "single channel" in probs            # 90% from one channel
    assert "semantic_search" in probs           # volume with no unique finds
    assert "no coverage estimate" in probs
    assert "quota" in probs
    assert "no known gaps" in probs
    assert "no stated reason for stopping" in probs


def test_ledger_with_no_channels_says_it_is_unauditable():
    assert SearchLedger(run_id="t").problems() == [
        "no channels recorded — the search is unauditable"
    ]


def test_every_coverage_estimate_being_pull_pull_is_flagged():
    led = SearchLedger(
        run_id="t",
        channels=[
            ChannelYield(channel=DiscoveryChannel.KEYWORD_SEARCH,
                         n_retrieved=50, n_admitted=20, n_unique=15),
            ChannelYield(channel=DiscoveryChannel.BACKWARD_SNOWBALL,
                         n_retrieved=20, n_admitted=15, n_unique=10),
        ],
        coverage=[CoverageEstimate(
            channel_a=DiscoveryChannel.KEYWORD_SEARCH,
            channel_b=DiscoveryChannel.SEMANTIC_SEARCH,
            n_a=20, n_b=18, n_both=16, n_total_observed=22)],
        saturation_note="curve flat over rounds 3-5",
        known_gaps=["no patents"],
    )
    assert any("overstates coverage" in p for p in led.problems())


def test_channel_mix_sums_to_one():
    led = _pull_only_ledger()
    assert sum(led.channel_mix().values()) == pytest.approx(1.0, abs=0.01)
    assert led.redundant_channels() == ["semantic_search"]


def test_demo_ledger_is_exemplary():
    """The reference fixture must pass, since teammates copy it."""
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "examples"))
    from demo_search import demo_ledger

    assert demo_ledger("demo").problems() == []


# ---------------------------------------------------------------------------
# Axis derivation: the coverage gate
# ---------------------------------------------------------------------------


def _prop(kind: PropertyKind, preds: list[str] | None = None) -> MetaProperty:
    return MetaProperty(
        kind=kind, value="something specific about the target",
        implies_predicates=preds if preds is not None else ["SIMILAR_FOLD_TO"],
        why_it_connects=(
            "both share a pocket whose helix-12 position reports occupancy, so a pose "
            "misplacing it is wrong in the same way for each"
        ),
    )


def test_why_it_connects_may_not_restate_the_property():
    with pytest.raises(ValidationError, match="restates the property"):
        MetaProperty(
            kind=PropertyKind.FAMILY_MEMBERSHIP,
            value="both are nuclear receptors",
            implies_predicates=["MEMBER_OF_FAMILY"],
            why_it_connects="both are nuclear receptors",
        )


def test_uncovered_checklist_items_are_reported():
    d = AxisDerivation(
        run_id="t", domain=Domain.DEL_ML, target_id="chembl:X",
        considered=[_prop(PropertyKind.SCAFFOLD_CLASS, ["SHARES_SCAFFOLD"])],
        derived_axes=["scaffold"],
    )
    gaps = d.uncovered_kinds()
    assert PropertyKind.LIBRARY_DESIGN.value in gaps
    assert len(gaps) == len(CHECKLISTS[Domain.DEL_ML]) - 1
    assert any("neither used nor dismissed" in p for p in d.problems())


def test_full_coverage_by_use_or_dismissal_passes_the_gate():
    kinds = CHECKLISTS[Domain.CHEMINFORMATICS]
    d = AxisDerivation(
        run_id="t", domain=Domain.CHEMINFORMATICS, target_id="chembl:X",
        considered=[_prop(kinds[0], ["SHARES_SCAFFOLD"])],
        dismissed={
            k.value: "no assay data exists for this collection, so the dimension is moot here"
            for k in kinds[1:]
        },
        derived_axes=["scaffold"],
    )
    assert d.uncovered_kinds() == []
    assert d.problems() == []


def test_property_wired_to_no_predicate_is_the_failure_not_a_partial_success():
    d = AxisDerivation(
        run_id="t", domain=Domain.CHEMINFORMATICS, target_id="chembl:X",
        considered=[_prop(PropertyKind.SCAFFOLD_CLASS, [])],
    )
    assert d.unused_properties() == [PropertyKind.SCAFFOLD_CLASS.value]
    assert any("wired to no predicate" in p for p in d.problems())


def test_lazy_dismissals_are_caught():
    d = AxisDerivation(
        run_id="t", domain=Domain.DEL_ML, target_id="chembl:X",
        dismissed={"library_design": "not relevant", "physchem_regime": "n/a"},
    )
    assert set(d.lazy_dismissals()) == {"library_design", "physchem_regime"}


def test_typoed_dismissal_key_covers_nothing_and_is_named():
    d = AxisDerivation(
        run_id="t", domain=Domain.DEL_ML, target_id="chembl:X",
        dismissed={"libary_design": "the collection has no published build plan at all"},
    )
    assert d.unknown_kinds() == ["libary_design"]
    assert PropertyKind.LIBRARY_DESIGN.value in d.uncovered_kinds()
    assert any("not checklist items" in p for p in d.problems())


def test_unregistered_domain_falls_back_to_the_largest_checklist():
    assert checklist_for(Domain.GENOMICS) == CHECKLISTS[Domain.STRUCTURAL_BIOLOGY]


def test_every_property_kind_has_a_question():
    for k in PropertyKind:
        assert k.question.endswith("?")


def test_analogous_cascade_role_is_on_the_structural_biology_checklist():
    """The item agents reliably skip; if it leaves the checklist the gate stops catching it."""
    assert PropertyKind.ANALOGOUS_CASCADE_ROLE in CHECKLISTS[Domain.STRUCTURAL_BIOLOGY]


# ---------------------------------------------------------------------------
# Axis sweeps: the stopping rule
# ---------------------------------------------------------------------------


def _round(new: int, strategy: str) -> SweepRound:
    return SweepRound(n_queries=4, n_candidates=new + 3, n_new=new, strategy=strategy)


def _sweep(**kw) -> AxisSweep:
    base = dict(
        axis="pathway", worker="w1",
        question="Which pathways contain the target, and who else is in them?",
        predicate="IN_PATHWAY", n_admitted=5,
    )
    return AxisSweep(**{**base, **kw})


def test_saturation_needs_three_rounds():
    s = _sweep(rounds=[_round(10, "keyword"), _round(1, "structured")], saturated=True)
    assert any("at least three points" in p for p in s.problems())


def test_saturation_is_rejected_while_the_curve_still_climbs():
    s = _sweep(
        rounds=[_round(2, "keyword"), _round(3, "structured"), _round(9, "traversal")],
        saturated=True,
    )
    assert s.tail_yield == pytest.approx(12 / 14)
    assert any("still climbing" in p for p in s.problems())


def test_saturation_on_one_strategy_measures_the_query():
    s = _sweep(
        rounds=[_round(20, "keyword"), _round(1, "keyword"), _round(0, "keyword")],
        saturated=True,
    )
    assert s.strategies_tried == 1
    assert any("one distinct strategy" in p for p in s.problems())


def test_a_genuinely_saturated_sweep_passes():
    s = _sweep(
        rounds=[_round(20, "keyword"), _round(6, "structured"),
                _round(1, "backward traversal"), _round(0, "negative form")],
        saturated=True, n_admitted=20,
    )
    assert s.tail_yield == pytest.approx(1 / 27)
    assert s.problems() == []
    assert len(s.curve()) == 4


def test_saturated_and_truncated_together_is_a_validation_error():
    with pytest.raises(ValidationError, match="did not exhaust its axis"):
        _sweep(rounds=[_round(3, "keyword")], saturated=True, truncated_because="budget")


def test_a_sweep_with_no_end_state_is_reported_as_unknown():
    s = _sweep(rounds=[_round(5, "keyword")])
    assert any("neither saturated nor truncated" in p for p in s.problems())


def test_candidates_admitted_none_must_be_explained():
    s = _sweep(rounds=[_round(9, "keyword")], n_admitted=0, truncated_because="budget cap")
    assert any("admitted none" in p for p in s.problems())


def test_new_cannot_exceed_candidates():
    with pytest.raises(ValidationError, match="exceeds n_candidates"):
        SweepRound(n_queries=1, n_candidates=3, n_new=5, strategy="keyword pass")


def test_unswept_axes_are_worse_than_underived_ones():
    d = AxisDerivation(
        run_id="t", domain=Domain.CHEMINFORMATICS, target_id="x:1",
        derived_axes=["scaffold", "assay", "physchem"],
    )
    ns = NeighborhoodSweep(
        run_id="t", target_id="x:1", derivation=d,
        sweeps=[_sweep(axis="scaffold", truncated_because="budget",
                       rounds=[_round(4, "keyword")])],
    )
    assert ns.unswept_axes() == ["assay", "physchem"]
    assert any("never swept" in p for p in ns.problems())
    assert ns.open_leads() == ["scaffold"]


def test_one_worker_holding_many_axes_is_flagged():
    d = AxisDerivation(run_id="t", domain=Domain.CHEMINFORMATICS, target_id="x:1")
    ns = NeighborhoodSweep(
        run_id="t", target_id="x:1", derivation=d,
        sweeps=[
            _sweep(axis=a, worker="solo", negative_result="searched, nothing there",
                   n_admitted=0, rounds=[_round(0, f"pass {a}")])
            for a in ("a", "b", "c")
        ],
    )
    assert ns.overloaded_workers() == {"solo": ["a", "b", "c"]}
    assert any("quietly reprioritises" in p for p in ns.problems())


def test_two_axes_per_worker_is_tolerated():
    d = AxisDerivation(run_id="t", domain=Domain.CHEMINFORMATICS, target_id="x:1")
    ns = NeighborhoodSweep(
        run_id="t", target_id="x:1", derivation=d,
        sweeps=[
            _sweep(axis=a, worker="pair", negative_result="searched, nothing there",
                   n_admitted=0, rounds=[_round(0, f"pass {a}")])
            for a in ("a", "b")
        ],
    )
    assert not any("reprioritises" in p for p in ns.problems())


# ---------------------------------------------------------------------------
# Progressive disclosure
# ---------------------------------------------------------------------------


def test_a_follow_up_must_be_phrased_as_a_question():
    with pytest.raises(ValidationError, match="end with"):
        FollowUp(question="Background on pockets", answer="A pocket is a dent on the surface.")


def test_an_answer_may_not_restate_its_question():
    with pytest.raises(ValidationError, match="restates the question"):
        FollowUp(question="What is a pocket?", answer="What is a pocket")


def test_a_child_may_not_repeat_its_parents_question():
    kid = FollowUp(question="Why does it matter?", answer="Because the shape decides what fits.")
    with pytest.raises(ValidationError, match="returns the reader to where they already are"):
        FollowUp(question="Why does it matter?",
                 answer="Because the shape of the site decides which molecules fit inside.",
                 children=[kid])


def test_unexplained_jargon_with_no_child_to_click_is_a_dead_end():
    tree = FollowUpTree(
        lede="This is a plain sentence about shapes and how they fit together in practice.",
        branches=[
            FollowUp(question="Why is this hard?",
                     answer="The apo conformer differs from the holo one, so a pharmacophore "
                            "derived from either is wrong.",
                     kind=FollowUpKind.WHY),
            FollowUp(question="What does it change?",
                     answer="It argues for using several reference shapes rather than one.",
                     kind=FollowUpKind.SO_WHAT),
        ],
    )
    dead = tree.dead_ends(set())
    assert dead and "apo" in dead[0][1]


def test_a_child_that_defines_the_term_discharges_the_debt():
    tree = FollowUpTree(
        lede="This is a plain sentence about shapes and how they fit together in practice.",
        branches=[
            FollowUp(
                question="Why is this hard?",
                answer="The apo shape differs from the holo shape, so either one alone misleads.",
                kind=FollowUpKind.WHY,
                children=[FollowUp(
                    question="What do apo and holo mean?",
                    answer="Apo means nothing is bound; holo means something is.",
                    kind=FollowUpKind.WHAT_IS,
                    defines=["apo", "holo"],
                )],
            ),
            FollowUp(question="What does it change?",
                     answer="It argues for several reference shapes rather than one.",
                     kind=FollowUpKind.SO_WHAT),
        ],
    )
    assert tree.dead_ends(set()) == []


def test_a_cousin_definition_does_not_count():
    """Nothing leads the reader from one branch to a definition in another."""
    tree = FollowUpTree(
        lede="A plain sentence about shapes and how they fit together, with no special terms.",
        branches=[
            FollowUp(question="What does apo mean?",
                     answer="It means nothing is bound to the protein.",
                     kind=FollowUpKind.WHAT_IS, defines=["apo"]),
            FollowUp(question="What does this change?",
                     answer="An apo structure alone cannot show how the site adapts.",
                     kind=FollowUpKind.SO_WHAT),
        ],
    )
    dead = tree.dead_ends(set())
    assert dead and "apo" in dead[0][1]


def test_missing_so_what_is_knowledge_telling():
    tree = FollowUpTree(
        lede="A plain sentence with no special terms at all, just ordinary words in order.",
        branches=[FollowUp(question="What is this?", answer="A description of a thing.",
                           kind=FollowUpKind.WHAT_IS)],
    )
    probs = " | ".join(tree.problems(set()))
    assert "so_what" in probs
    assert "one level deep" in probs


def test_a_tree_with_no_branches_says_the_reader_has_nowhere_to_go():
    tree = FollowUpTree(lede="A claim stated plainly, with nothing at all to expand on it.")
    assert any("nowhere to go" in p for p in tree.problems(set()))


def test_too_many_top_level_branches_becomes_a_menu():
    tree = FollowUpTree(
        lede="A plain sentence with no special terms at all, just ordinary words in order.",
        branches=[
            FollowUp(question=f"Question number {i}?", answer=f"An answer to number {i}.",
                     kind=FollowUpKind.SO_WHAT if i == 0 else FollowUpKind.WHAT_IS)
            for i in range(9)
        ],
    )
    assert any("scans a menu" in p for p in tree.problems(set()))


def test_depth_beyond_the_contract_is_reported():
    node = FollowUp(question="Deepest question?", answer="The plainest possible answer here.")
    for i in range(MAX_DEPTH + 1):
        node = FollowUp(question=f"Level {i} question?",
                        answer=f"A plain answer at level {i} of the tree.",
                        children=[node])
    assert any("exceeds the" in p for p in node.problems(set(), level=1))


def test_children_are_ordered_definitions_first_objections_last():
    parent = FollowUp(
        question="Why does this hold?", answer="Because the shape decides what fits inside.",
        children=[
            FollowUp(question="Could it be wrong?", answer="Yes, if the shape is not fixed.",
                     kind=FollowUpKind.OBJECTION),
            FollowUp(question="What is a shape here?", answer="The outline of the empty space.",
                     kind=FollowUpKind.WHAT_IS),
            FollowUp(question="What does it change?", answer="Which reference we start from.",
                     kind=FollowUpKind.SO_WHAT),
        ],
    )
    assert [k.kind.value for k in parent.sorted_children()] == [
        "what_is", "so_what", "objection"
    ]


def test_walk_and_depth_profile_agree():
    tree = FollowUpTree(
        lede="A plain sentence with no special terms at all, just ordinary words in order.",
        branches=[
            FollowUp(
                question="What is it?", answer="An ordinary thing described plainly.",
                kind=FollowUpKind.WHAT_IS,
                children=[FollowUp(question="And what does that mean?",
                                   answer="It means what the words say.")],
            ),
            FollowUp(question="What does it change?", answer="Nothing much at all.",
                     kind=FollowUpKind.SO_WHAT),
        ],
    )
    assert tree.depth() == 2
    assert tree.count() == 3
    assert tree.depth_profile() == {1: 2, 2: 1}


def test_demo_follow_up_trees_have_no_dead_ends():
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "examples"))
    from demo_context import GLOSSARY
    from demo_followups import follow_ups, report_tree

    defined = GLOSSARY.defined()
    for tree in [report_tree(), *follow_ups().values()]:
        assert tree.problems(defined) == []
