"""Binder census, canonical binding mode, bounded expansion, and the family tiering.

The guards here defend two specific claims from being made carelessly: *"this is everything that
binds the target"* and *"this is the binding mode it was built for"*. The first is polluted by
buffer, the second is often false, and both look fine when wrong.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from reagent.contracts.biology import (
    ALWAYS_ARTEFACT,
    CONTEXT_DEPENDENT,
    Binder,
    BinderCensus,
    BinderClass,
    BindingModeReference,
    artefact_status,
)
from reagent.contracts.expansion import (
    Admission,
    Deferred,
    ExpansionBudget,
    ExpansionRun,
    RelationClass,
    StopReason,
    class_of,
    relevance_after,
    unclassified_predicates,
)
from reagent.contracts.kg import (
    FAMILY_COLOR,
    FAMILY_TIER,
    PREDICATE_DOMAINS,
    PREDICATE_FAMILY,
    FamilyTier,
    NodeType,
    Predicate,
    PredicateFamily,
    color_collisions,
    default_tiers_for,
    families_in,
)

# ---------------------------------------------------------------------------
# Artefact filtering — the thing that pollutes a census
# ---------------------------------------------------------------------------


def test_the_usual_suspects_are_artefacts():
    for code in ("GOL", "EDO", "SO4", "DMS", "PEG", "IMD", "MPD", "TRS", "ACT"):
        assert artefact_status(code) == "artefact", code


def test_metals_and_lipids_are_context_dependent_not_artefacts():
    for code in ("ZN", "MG", "NAG", "HEM", "OLA", "PLM", "ATP"):
        assert artefact_status(code) == "context_dependent", code


def test_a_real_ligand_code_is_a_candidate():
    assert artefact_status("HYF") == "candidate_binder"
    assert artefact_status("hyf") == "candidate_binder"   # case-insensitive


def test_the_two_lists_do_not_overlap():
    """A code cannot be both always-artefact and context-dependent."""
    assert frozenset() == ALWAYS_ARTEFACT & CONTEXT_DEPENDENT


def test_atom_count_would_not_have_caught_glycerol():
    """Why the list exists rather than a size threshold.

    Glycerol has six heavy atoms and passes the same filter a real fragment passes, while
    sulfate has five and fails it — exactly backwards from useful, since both are artefacts.
    """
    assert artefact_status("GOL") == "artefact"     # 6 heavy atoms, would pass n_atoms >= 6
    assert artefact_status("SO4") == "artefact"     # 5 heavy atoms, would fail it


# ---------------------------------------------------------------------------
# Binder classification
# ---------------------------------------------------------------------------


REASON = "co-crystallised in five independent entries at full occupancy with an assay-confirmed EC50"


def test_a_context_dependent_code_needs_real_reasoning():
    with pytest.raises(ValidationError, match="context-dependent"):
        Binder(id="pdb-ligand:ZN", label="zinc", binder_class=BinderClass.COFACTOR,
               het_code="ZN", classified_because="it is a cofactor")


def test_real_reasoning_for_a_metal_is_accepted():
    b = Binder(
        id="pdb-ligand:ZN", label="zinc", binder_class=BinderClass.COFACTOR, het_code="ZN",
        classified_because=(
            "tetrahedrally coordinated by Cys23, Cys26, His41 and Cys44, all conserved across "
            "the family corpus, at full occupancy in three space groups"
        ),
    )
    assert b.binder_class.informs_intended_mode


def test_a_candidate_binder_needs_no_extended_reasoning():
    """The strict check applies only where auto-classification would be wrong."""
    b = Binder(id="chembl:X", label="SR12813", binder_class=BinderClass.TOOL_COMPOUND,
               het_code="HYF", classified_because="a published chemical probe for this receptor")
    assert b.binder_class.informs_druggability


def test_class_partitions_evidence_kind():
    intended = {c for c in BinderClass if c.informs_intended_mode}
    drugg = {c for c in BinderClass if c.informs_druggability}
    assert intended and drugg
    assert not intended & drugg
    assert not any(c.is_usable_evidence for c in
                   (BinderClass.CRYSTALLIZATION_ARTEFACT, BinderClass.UNKNOWN))


def test_is_artefact_by_code_is_independent_of_the_claimed_class():
    b = Binder(id="pdb-ligand:GOL", label="glycerol", binder_class=BinderClass.FRAGMENT,
               het_code="GOL", classified_because="looked like a fragment hit in the density")
    assert b.is_artefact_by_code


# ---------------------------------------------------------------------------
# The binding mode, which may not exist
# ---------------------------------------------------------------------------


NO_MODE_WHY = (
    "A xenobiotic sensor selected for breadth: recognising chemicals the organism has not "
    "encountered is the function, so no single endogenous pose can be a reference."
)


def test_an_undefined_mode_is_a_legitimate_answer():
    m = BindingModeReference(target_id="uniprot:O75469", is_defined=False, why=NO_MODE_WHY)
    assert not m.is_defined
    assert m.anchor_policy == "additive"


def test_required_anchors_with_no_defined_mode_is_rejected():
    """The specific error that inverted a prior on the fragment half of a real test set."""
    with pytest.raises(ValidationError, match="inverted an anchor-based prior"):
        BindingModeReference(target_id="uniprot:O75469", is_defined=False, why=NO_MODE_WHY,
                             anchor_policy="required")


def test_a_defined_mode_must_name_a_pose():
    with pytest.raises(ValidationError, match="names no reference binder or structure"):
        BindingModeReference(
            target_id="uniprot:P11473", is_defined=True,
            why="calcitriol is the established physiological ligand for this receptor",
        )


def test_a_defined_mode_with_a_pose_passes():
    m = BindingModeReference(
        target_id="uniprot:P11473", is_defined=True,
        reference_binders=["chembl:CHEMBL846"], reference_structures=["pdb:1DB1"],
        anchor_residues=["Ser237", "Arg274"],
        why="calcitriol is the established physiological ligand and its complex is resolved",
    )
    assert m.is_defined


def test_required_anchors_need_more_than_a_sentence():
    with pytest.raises(ValidationError, match="need an argument"):
        BindingModeReference(
            target_id="uniprot:P11473", is_defined=True,
            reference_binders=["chembl:CHEMBL846"], anchor_policy="required",
            why="calcitriol is the physiological ligand",
        )


def test_required_anchors_with_a_real_argument_pass():
    m = BindingModeReference(
        target_id="uniprot:P11473", is_defined=True,
        reference_binders=["chembl:CHEMBL846"], anchor_policy="required",
        why=(
            "calcitriol is the established physiological ligand; all 48 holo structures engage "
            "both anchor residues, the fragment screen produced no binder that omits them, and "
            "no allosteric or covalent ligand is known for this receptor, so every "
            "subpopulation in the test set engages them"
        ),
    )
    assert m.anchor_policy == "required"


# ---------------------------------------------------------------------------
# The census
# ---------------------------------------------------------------------------


def _binder(cid: str, cls: BinderClass, het: str | None = None) -> Binder:
    return Binder(id=cid, label=cid.split(":")[-1], binder_class=cls, het_code=het,
                  classified_because=REASON)


def _census(**kw) -> BinderCensus:
    base = dict(
        target_id="uniprot:O75469",
        mode=BindingModeReference(target_id="uniprot:O75469", is_defined=False, why=NO_MODE_WHY),
        binders=[
            _binder("chembl:A", BinderClass.OFF_TARGET_DRUG),
            _binder("chembl:B", BinderClass.TOOL_COMPOUND),
            _binder("pdb-ligand:GOL", BinderClass.CRYSTALLIZATION_ARTEFACT, "GOL"),
        ],
        n_structures_searched=5, screening_breadth=2400,
        sources=["rcsb", "chembl"],
    )
    return BinderCensus(**{**base, **kw})


def test_a_well_formed_census_passes():
    c = _census()
    assert len(c.usable()) == 2
    assert len(c.artefacts()) == 1
    assert c.problems() == []


def test_an_artefact_code_classified_as_a_binder_is_caught_arithmetically():
    c = _census(binders=[
        _binder("chembl:A", BinderClass.OFF_TARGET_DRUG),
        _binder("pdb-ligand:GOL", BinderClass.FRAGMENT, "GOL"),
    ])
    assert c.misclassified_artefacts() == ["pdb-ligand:GOL (GOL)"]
    assert any("always-artefact code" in p for p in c.problems())


def test_unclassified_codes_make_the_total_meaningless():
    c = _census(unclassified=["XYZ", "QQQ"])
    assert any("never decided about" in p for p in c.problems())


def test_a_single_source_census_is_a_systematic_subset():
    c = _census(sources=["rcsb"])
    assert any("one source" in p for p in c.problems())


def test_no_sources_at_all_is_worse():
    c = _census(sources=[])
    assert any("no sources recorded" in p for p in c.problems())


def test_a_count_without_a_denominator_is_flagged():
    c = _census(
        screening_breadth=None,
        binders=[_binder(f"chembl:{i}", BinderClass.OFF_TARGET_DRUG) for i in range(8)],
    )
    assert c.hit_rate is None
    assert any("screening_breadth" in p for p in c.problems())


def test_hit_rate_is_the_comparable_number():
    c = _census(screening_breadth=1000)
    assert c.hit_rate == pytest.approx(2 / 1000)


def test_a_defined_mode_resting_on_drugs_alone_is_flagged():
    c = _census(mode=BindingModeReference(
        target_id="uniprot:O75469", is_defined=True, reference_binders=["chembl:A"],
        why="the best-characterised agonist is treated as the reference for this receptor",
    ))
    assert c.canonical() == []
    assert any("tell you what chemistry achieved" in p for p in c.problems())


def test_one_structure_is_not_the_pockets_grammar():
    c = _census(n_structures_searched=1)
    assert any("pocket's grammar" in p for p in c.problems())


def test_an_empty_census_says_so():
    c = _census(binders=[])
    assert c.problems() == ["uniprot:O75469: empty census"]


# ---------------------------------------------------------------------------
# Bounded expansion
# ---------------------------------------------------------------------------


def test_every_predicate_has_a_transmission_class():
    assert unclassified_predicates([p.value for p in Predicate]) == []


def test_bibliographic_and_methodological_do_not_propagate():
    b = ExpansionBudget()
    assert relevance_after(1.0, "SUPPORTED_BY", b) == 0.0
    assert relevance_after(1.0, "EVALUATED_ON", b) == 0.0
    assert class_of("SUPPORTED_BY") is RelationClass.BIBLIOGRAPHIC
    assert class_of("USED_IN") is RelationClass.METHODOLOGICAL


def test_relevance_ordering_follows_relation_class():
    b = ExpansionBudget()
    identity = relevance_after(1.0, "HAS_ISOFORM", b)
    physical = relevance_after(1.0, "BINDS", b)
    functional = relevance_after(1.0, "IN_PATHWAY", b)
    contextual = relevance_after(1.0, "EXPRESSED_IN", b)
    assert identity > physical > functional > contextual > 0


def test_a_hub_intermediate_is_penalised_hard():
    b = ExpansionBudget()
    through_hub = relevance_after(1.0, "BINDS", b, degree=300)
    through_normal = relevance_after(1.0, "BINDS", b, degree=10)
    assert through_hub < through_normal / 4


def test_an_unmapped_predicate_falls_back_to_middling():
    assert class_of("SOME_NEW_PREDICATE") is RelationClass.FUNCTIONAL


def test_a_budget_whose_last_hop_is_dead_is_rejected():
    with pytest.raises(ValidationError, match="dead budget"):
        ExpansionBudget(max_hops=5, decay=0.3, relevance_floor=0.05)


def test_a_coherent_budget_passes():
    b = ExpansionBudget(max_hops=3, decay=0.45, relevance_floor=0.05)
    assert b.decay ** (b.max_hops - 1) >= b.relevance_floor


def _run(**kw) -> ExpansionRun:
    base = dict(
        run_id="r1", focal="uniprot:O75469", budget=ExpansionBudget(max_nodes=10),
        admitted=[
            Admission(node_id="uniprot:O75469", hop=0, relevance=1.0, via_predicate="focal"),
            Admission(node_id="uniprot:P08684", hop=1, relevance=0.4,
                      via_predicate="MODULATES", via_node="uniprot:O75469", degree=12),
            Admission(node_id="uniprot:P11712", hop=1, relevance=0.36,
                      via_predicate="PROMISCUOUS_WITH", via_node="uniprot:O75469", degree=8,
                      admitted_by="quota"),
            Admission(node_id="gene:CYP3A4", hop=2, relevance=0.2,
                      via_predicate="TRANSCRIPTIONALLY_ACTIVATES", via_node="uniprot:P08684",
                      degree=5, admitted_by="quota"),
        ],
        deferred=[Deferred(node_id="uniprot:P10635", hop=2, relevance=0.11,
                           via_predicate="SHARES_TARGET_WITH", reason="node_budget")],
        stop_reason=StopReason.NODE_BUDGET, n_visited=61,
        stop_note="raising to 40 would reach the CYP substrate set",
    )
    return ExpansionRun(**{**base, **kw})


def test_a_well_formed_run_passes():
    r = _run()
    assert r.by_hop() == {0: 1, 1: 2, 2: 1}
    assert r.problems() == []


def test_provenance_answers_why_a_node_is_here():
    a = _run().provenance_of("gene:CYP3A4")
    assert a is not None
    assert a.via_predicate == "TRANSCRIPTIONALLY_ACTIVATES"
    assert a.via_node == "uniprot:P08684"


def test_a_budget_stop_with_no_deferred_frontier_is_flagged():
    r = _run(deferred=[])
    assert any("indistinguishable from a finished walk" in p for p in r.problems())


def test_claiming_saturation_with_a_large_frontier_is_flagged():
    r = _run(
        stop_reason=StopReason.SATURATED, stop_note=None,
        deferred=[Deferred(node_id=f"uniprot:X{i}", hop=2, relevance=0.1,
                           via_predicate="INTERACTS_WITH", reason="floor") for i in range(30)],
    )
    assert any("budget stop wearing the wrong label" in p for p in r.problems())


def test_saturation_is_the_only_reason_that_closes_a_region():
    assert not StopReason.SATURATED.leaves_open_leads
    for other in (StopReason.NODE_BUDGET, StopReason.HOP_BUDGET, StopReason.RELEVANCE_FLOOR,
                  StopReason.TIME_BUDGET, StopReason.QUOTA_EXHAUSTED):
        assert other.leaves_open_leads


def test_one_predicate_swallowing_the_walk_is_flagged():
    r = _run(admitted=[
        Admission(node_id="uniprot:O75469", hop=0, relevance=1.0, via_predicate="focal"),
        *[Admission(node_id=f"uniprot:P{i}", hop=1, relevance=0.3,
                    via_predicate="INTERACTS_WITH", via_node="uniprot:O75469", degree=5,
                    admitted_by="quota")
          for i in range(9)],
    ])
    assert any("one predicate" in p for p in r.problems())


def test_hub_heavy_admissions_are_flagged():
    r = _run(admitted=[
        Admission(node_id="uniprot:O75469", hop=0, relevance=1.0, via_predicate="focal"),
        Admission(node_id="uniprot:P0CG48", hop=1, relevance=0.2, via_predicate="INTERACTS_WITH",
                  via_node="uniprot:O75469", degree=900, admitted_by="quota"),
        Admission(node_id="uniprot:P04637", hop=1, relevance=0.2, via_predicate="IN_PATHWAY",
                  via_node="uniprot:O75469", degree=700, admitted_by="quota"),
    ])
    assert len(r.hubs_admitted()) == 2
    assert any("connected to everything" in p for p in r.problems())


def test_an_untraceable_admission_cannot_be_undone():
    r = _run(admitted=[
        Admission(node_id="uniprot:O75469", hop=0, relevance=1.0, via_predicate="focal"),
        Admission(node_id="uniprot:P08684", hop=1, relevance=0.4, via_predicate="MODULATES",
                  admitted_by="quota"),
    ])
    assert any("cannot be explained or undone" in p for p in r.problems())


def test_an_underspent_quota_is_flagged():
    r = _run(
        budget=ExpansionBudget(max_nodes=100, exploration_quota=0.3),
        deferred=[Deferred(node_id="x:1", hop=2, relevance=0.1, via_predicate="BINDS",
                           reason="node_budget")],
    )
    assert r.quota_spent < 0.3
    assert any("exploration quota" in p for p in r.problems())


def test_a_budget_stop_needs_a_stop_note():
    r = _run(stop_note=None)
    assert any("stop_note" in p for p in r.problems())


# ---------------------------------------------------------------------------
# Family tiering — the structural fix for a growing vocabulary
# ---------------------------------------------------------------------------


def test_every_family_has_a_tier_and_a_colour():
    for f in PredicateFamily:
        assert f in FAMILY_TIER, f.value
        assert f in FAMILY_COLOR, f.value


def test_every_predicate_has_a_family_and_endpoint_types():
    for p in Predicate:
        assert p in PREDICATE_FAMILY, p.value
        assert p in PREDICATE_DOMAINS, p.value


def test_no_two_families_share_a_colour_within_a_tier():
    """Reused hues across tiers are the design; reused inside a tier is a bug."""
    assert color_collisions() == {}


def test_colours_are_deliberately_reused_across_tiers():
    """If this ever becomes false the palette has silently gone back to one-hue-per-family,
    which does not scale and is the thing tiering replaced."""
    by_colour: dict[str, set[str]] = {}
    for fam, colour in FAMILY_COLOR.items():
        by_colour.setdefault(colour, set()).add(FAMILY_TIER[fam].value)
    assert any(len(tiers) > 1 for tiers in by_colour.values())


def test_no_tier_needs_more_than_four_hues_at_once():
    for tier in FamilyTier:
        assert len(families_in(tier)) <= 4, tier.value


def test_tiers_partition_the_families():
    covered = [f for t in FamilyTier for f in families_in(t)]
    assert sorted(f.value for f in covered) == sorted(f.value for f in PredicateFamily)


def test_default_tiers_differ_by_focal_type():
    """Landing on a compound should open the clinical tier; a pocket should open physical."""
    assert FamilyTier.CLINICAL in default_tiers_for(NodeType.COMPOUND.value)
    assert FamilyTier.PHYSICAL in default_tiers_for(NodeType.POCKET.value)
    assert FamilyTier.REGULATORY in default_tiers_for(NodeType.GENE.value)


def test_an_unknown_focal_type_gets_a_sane_fallback():
    tiers = default_tiers_for("SomethingNew")
    assert tiers and FamilyTier.MOLECULAR in tiers


def test_every_tier_states_the_question_it_answers():
    for t in FamilyTier:
        assert t.question.endswith("?")


def test_the_new_biology_node_types_exist():
    for nt in (NodeType.GENE, NodeType.RNA, NodeType.VARIANT):
        assert nt.value in {n.value for n in NodeType}
