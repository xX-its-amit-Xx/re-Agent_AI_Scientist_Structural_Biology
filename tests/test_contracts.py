"""Contract tests.

Two jobs. First, prove the happy path works end to end, so a teammate can copy a
working example. Second — and more important — prove each guard rail actually
fires, because a validator nobody has seen reject anything is decoration.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from reagent.contracts import (
    AnalogyCard,
    Confidence,
    Decision,
    DecisionLedger,
    Domain,
    Edge,
    Evidence,
    Finding,
    FindingKind,
    GraphDelta,
    Handoff,
    MethodStep,
    ModelReport,
    Node,
    NodeType,
    Novelty,
    Predicate,
    ProblemSpec,
    Proposal,
    ProposalSet,
    SourceType,
    Stage,
    TargetEntity,
    TaskType,
    Verdict,
    Visualization,
    VizBundle,
    VizKind,
    VizMedium,
)
from reagent.contracts.viz import ColorMap
from reagent.domains import profile_for, registered_domains
from reagent.kg.store import KGStore

# --------------------------------------------------------------------------
# ProblemSpec — the agnosticism guarantee
# --------------------------------------------------------------------------


def _metric(**kw):
    from reagent.contracts import Metric

    defaults = dict(
        name="LDDT-PLI",
        definition="OpenStructure ligand_scoring, bootstrap-averaged over 1000 resamples.",
        eval_set="184 blinded compounds, half live / half held out",
    )
    defaults.update(kw)
    return Metric(**defaults)


def structural_spec() -> ProblemSpec:
    return ProblemSpec(
        run_id="test-struct",
        name="Blind complex prediction",
        domain=Domain.STRUCTURAL_BIOLOGY,
        task_type=TaskType.COMPLEX_PREDICTION,
        targets=[
            TargetEntity(
                id="uniprot:O75469", kind="protein", label="PXR (NR1I2)", organism="human"
            )
        ],
        metric=_metric(),
        axes=profile_for(Domain.STRUCTURAL_BIOLOGY, TaskType.COMPLEX_PREDICTION),
    )


def del_spec() -> ProblemSpec:
    """The same machinery on a completely different problem — this is the point."""
    return ProblemSpec(
        run_id="test-del",
        name="DEL hit finding",
        domain=Domain.DEL_ML,
        task_type=TaskType.HIT_IDENTIFICATION,
        targets=[
            TargetEntity(
                id="library:DEL-triazine-3cycle", kind="compound_library", label="Triazine 3-cycle DEL"
            )
        ],
        metric=_metric(
            name="PR-AUC",
            definition="Precision-recall AUC over held-out disynthon enrichment labels.",
            eval_set="held-out disynthons",
        ),
        axes=profile_for(Domain.DEL_ML, TaskType.HIT_IDENTIFICATION),
    )


def test_same_contract_serves_unrelated_domains():
    s, d = structural_spec(), del_spec()
    assert {a.name for a in s.axes} != {a.name for a in d.axes}
    # Neither spec leaks the other's assumptions.
    assert "fold" in {a.name for a in s.axes}
    assert "fold" not in {a.name for a in d.axes}
    assert "building_block" in {a.name for a in d.axes}
    assert s.primary_target.kind == "protein"
    assert d.primary_target.kind == "compound_library"


def test_several_domains_are_registered():
    assert len(registered_domains()) >= 4


def test_axis_must_use_a_known_predicate():
    from reagent.contracts import AxisSpec

    with pytest.raises(ValidationError, match=r"absent from kg\.Predicate"):
        ProblemSpec(
            run_id="x",
            name="bad",
            domain=Domain.OTHER,
            task_type=TaskType.OTHER,
            targets=[TargetEntity(id="thing:1", kind="other", label="t")],
            metric=_metric(),
            axes=[
                AxisSpec(
                    name="vibes",
                    question="Which things feel similar to the target?",
                    predicate="FEELS_LIKE",
                    score_key="vibe",
                )
            ],
        )


def test_target_id_must_be_namespaced():
    with pytest.raises(ValidationError, match="namespaced"):
        TargetEntity(id="O75469", kind="protein", label="PXR")


def test_pose_selection_relaxes_irrelevant_axes():
    axes = profile_for(Domain.STRUCTURAL_BIOLOGY, TaskType.POSE_SELECTION)
    assert not next(a for a in axes if a.name == "compound").required
    # And the default profile is untouched by that mutation.
    fresh = profile_for(Domain.STRUCTURAL_BIOLOGY, TaskType.COMPLEX_PREDICTION)
    assert next(a for a in fresh if a.name == "compound").required


# --------------------------------------------------------------------------
# Findings — evidence and grounding guard rails
# --------------------------------------------------------------------------


def paper_evidence(locator="doi:10.1016/j.str.2025.09.011") -> Evidence:
    return Evidence(
        source_type=SourceType.PAPER,
        locator=locator,
        title="Subtle changes in ligand-receptor interactions",
        year=2025,
    )


def test_observation_requires_evidence():
    with pytest.raises(ValidationError, match="must cite at least one Evidence"):
        Finding(
            id="F-1",
            kind=FindingKind.OBSERVATION,
            statement="The target pocket exceeds 1600 cubic angstroms.",
            confidence=Confidence.SUPPORTED,
        )


def test_design_choice_may_be_asserted_without_evidence():
    f = Finding(
        id="F-2",
        kind=FindingKind.DESIGN_CHOICE,
        statement="Use per-model z-scoring before cross-model comparison.",
        confidence=Confidence.TENTATIVE,
    )
    assert f.evidence == []


def test_analogy_alone_cannot_exceed_speculative():
    analogy = Evidence(
        source_type=SourceType.ANALOGY,
        locator="analogy:finance/regime-switching-ensemble",
        source_domain="quantitative finance",
    )
    with pytest.raises(ValidationError, match="cap it at 'speculative'"):
        Finding(
            id="F-3",
            kind=FindingKind.HYPOTHESIS,
            statement="Switching selector per ligand regime will beat a single selector.",
            confidence=Confidence.SUPPORTED,
            evidence=[analogy],
        )
    # Speculative is fine — the analogy motivates an experiment.
    ok = Finding(
        id="F-4",
        kind=FindingKind.HYPOTHESIS,
        statement="Switching selector per ligand regime will beat a single selector.",
        confidence=Confidence.SPECULATIVE,
        evidence=[analogy],
    )
    assert ok.confidence is Confidence.SPECULATIVE


def test_analogy_evidence_must_name_its_domain():
    with pytest.raises(ValidationError, match="must name its source_domain"):
        Evidence(source_type=SourceType.ANALOGY, locator="analogy:art/pentimento")


def test_established_needs_two_independent_sources():
    with pytest.raises(ValidationError, match="fewer than two independent"):
        Finding(
            id="F-5",
            kind=FindingKind.OBSERVATION,
            statement="Cross-model confidence z-scoring outperforms raw confidence.",
            confidence=Confidence.ESTABLISHED,
            evidence=[paper_evidence()],
        )
    ok = Finding(
        id="F-6",
        kind=FindingKind.OBSERVATION,
        statement="Cross-model confidence z-scoring outperforms raw confidence.",
        confidence=Confidence.ESTABLISHED,
        evidence=[paper_evidence(), paper_evidence("pmid:39999999")],
    )
    assert len(ok.evidence) == 2


def test_blank_locator_rejected():
    with pytest.raises(ValidationError, match="resolvable identifier"):
        Evidence(source_type=SourceType.PAPER, locator="   ")


# --------------------------------------------------------------------------
# Visualization guard rails
# --------------------------------------------------------------------------


def a_viz(**kw) -> Visualization:
    defaults = dict(
        id="V-1",
        kind=VizKind.KG_SUBGRAPH,
        medium=VizMedium.HTML_SELF_CONTAINED,
        title="Target neighbourhood",
        question="Which proteins sit closest to the target on each similarity axis?",
        takeaway="Fold neighbours cluster inside the family; promiscuity neighbours do not.",
        path="docs/figures/kg.html",
        reads_from=["kg/nodes.jsonl", "kg/edges.jsonl"],
        encoding={"node_fill": "node.type", "edge_stroke": "edge.predicate",
                  "edge_width": "attrs.tm_score"},
        alt_text="An ego network with the target at the centre and neighbours in rings.",
        focal_node="uniprot:O75469",
    )
    defaults.update(kw)
    return Visualization(**defaults)


def test_question_must_be_a_question():
    with pytest.raises(ValidationError, match="must be phrased as a question"):
        a_viz(question="This shows the neighbourhood of the target protein.")


def test_takeaway_must_differ_from_question():
    q = "Which proteins sit closest to the target on each similarity axis?"
    with pytest.raises(ValidationError, match="restates `question`"):
        a_viz(question=q, takeaway=q)


def test_ego_network_needs_a_centre():
    with pytest.raises(ValidationError, match="must name its focal_node"):
        a_viz(focal_node=None)


def test_hairball_guard():
    with pytest.raises(ValidationError, match="hairball"):
        a_viz(n_elements=12000)
    assert a_viz(n_elements=12000, params={"clustered": True}).n_elements == 12000


def test_too_many_colors_needs_a_second_channel():
    mapping = {f"PRED_{i}": f"#{i:06x}" for i in range(20)}
    with pytest.raises(ValidationError, match="not discriminable"):
        ColorMap(
            channel="edge_stroke",
            data_field="edge.predicate",
            scale_type="categorical",
            mapping=mapping,
        )
    ok = ColorMap(
        channel="edge_stroke",
        data_field="edge.predicate",
        scale_type="categorical",
        mapping=mapping,
        secondary_channel="edge_dash_pattern",
    )
    assert ok.secondary_channel == "edge_dash_pattern"


def test_reading_order_must_resolve():
    with pytest.raises(ValidationError, match="unknown visualization ids"):
        VizBundle(stage="stage1_literature", visualizations=[a_viz()], reading_order=["V-99"])


# --------------------------------------------------------------------------
# Knowledge graph
# --------------------------------------------------------------------------


def _protein(nid: str, label: str) -> Node:
    return Node(id=nid, type=NodeType.PROTEIN, label=label, asserted_by="test")


def test_graph_delta_catches_dangling_edges():
    delta = GraphDelta(
        run_id="r",
        asserted_by="test",
        nodes=[_protein("uniprot:O75469", "PXR")],
        edges=[
            Edge(
                src="uniprot:O75469",
                predicate=Predicate.SIMILAR_FOLD_TO,
                dst="uniprot:MISSING",
                asserted_by="test",
            )
        ],
    )
    problems = delta.validate_referential_integrity()
    assert any("unknown dst" in p for p in problems)


def test_predicate_domain_enforced():
    delta = GraphDelta(
        run_id="r",
        asserted_by="test",
        nodes=[
            _protein("uniprot:O75469", "PXR"),
            Node(id="chembl:CHEMBL1", type=NodeType.COMPOUND, label="cmpd", asserted_by="test"),
        ],
        edges=[
            # A compound cannot be the target of a fold-similarity edge.
            Edge(
                src="uniprot:O75469",
                predicate=Predicate.SIMILAR_SEQUENCE_TO,
                dst="chembl:CHEMBL1",
                asserted_by="test",
            )
        ],
    )
    problems = delta.validate_referential_integrity()
    assert any("cannot end at a Compound" in p for p in problems)


def test_analogy_node_must_name_its_domain():
    delta = GraphDelta(
        run_id="r",
        asserted_by="test",
        nodes=[
            Node(
                id="analogy:finance/regime-switching",
                type=NodeType.ANALOGY,
                label="Regime-switching ensemble",
                asserted_by="test",
            )
        ],
    )
    problems = delta.validate_referential_integrity()
    assert any("no ORIGINATES_IN edge" in p for p in problems)


def test_node_id_must_be_namespaced():
    with pytest.raises(ValidationError, match="namespaced"):
        Node(id="O75469", type=NodeType.PROTEIN, label="PXR", asserted_by="test")


def test_store_roundtrip_and_axis_query(tmp_path):
    store = KGStore(tmp_path / "kg")
    spec = structural_spec()
    target = spec.primary_target.id

    nodes = [_protein(target, "PXR"), _protein("uniprot:Q14994", "CAR"),
             _protein("uniprot:P37231", "PPARG")]
    edges = [
        Edge(src=target, predicate=Predicate.SIMILAR_FOLD_TO, dst="uniprot:Q14994",
             attrs={"tm_score": 0.86}, confidence=Confidence.SUPPORTED,
             evidence=[paper_evidence()], asserted_by="test"),
        Edge(src=target, predicate=Predicate.SIMILAR_FOLD_TO, dst="uniprot:P37231",
             attrs={"tm_score": 0.61}, confidence=Confidence.TENTATIVE, asserted_by="test"),
    ]
    problems = store.merge(GraphDelta(run_id="r", asserted_by="test", nodes=nodes, edges=edges))
    assert problems == []

    rows = store.along_axis(target, spec.axis("fold"))
    assert [r["dst"] for r in rows] == ["uniprot:Q14994", "uniprot:P37231"]  # sorted by tm_score
    assert rows[0]["attrs"]["tm_score"] == 0.86

    hood = store.neighborhood(target, spec.required_axes())
    assert hood["fold"] and hood["sequence"] == []  # only the fold axis was populated

    stats = store.stats()
    assert stats["n_nodes"] == 3 and stats["n_edges"] == 2

    # The audit query a stage runs before shipping.
    assert store.unsupported_edges(Confidence.SUPPORTED) == []
    assert store.evidence_for(target, Predicate.SIMILAR_FOLD_TO, "uniprot:Q14994")


def test_store_rejects_write_queries(tmp_path):
    store = KGStore(tmp_path / "kg")
    store.merge(GraphDelta(run_id="r", asserted_by="t", nodes=[_protein("uniprot:A", "A")]))
    with pytest.raises(ValueError, match="SELECT/WITH"):
        store.query("DELETE FROM nodes")


def test_duplicate_triple_keeps_highest_confidence_and_merges_attrs(tmp_path):
    store = KGStore(tmp_path / "kg")
    nodes = [_protein("uniprot:A", "A"), _protein("uniprot:B", "B")]
    store.merge(GraphDelta(run_id="r1", asserted_by="agent1", nodes=nodes, edges=[
        Edge(src="uniprot:A", predicate=Predicate.SIMILAR_FOLD_TO, dst="uniprot:B",
             attrs={"tm_score": 0.5}, confidence=Confidence.TENTATIVE, asserted_by="agent1")
    ]))
    store.merge(GraphDelta(run_id="r2", asserted_by="agent2", nodes=[], edges=[
        Edge(src="uniprot:A", predicate=Predicate.SIMILAR_FOLD_TO, dst="uniprot:B",
             attrs={"rmsd": 1.2}, confidence=Confidence.ESTABLISHED,
             evidence=[paper_evidence(), paper_evidence("pmid:1")], asserted_by="agent2")
    ]), strict=False)

    rows = store.query("SELECT confidence, attrs_json FROM edges")
    assert len(rows) == 1, "the same triple asserted twice must collapse to one edge"
    assert rows[0]["confidence"] == "established"
    assert "tm_score" in rows[0]["attrs_json"] and "rmsd" in rows[0]["attrs_json"]


# --------------------------------------------------------------------------
# Proposals and the decision gate
# --------------------------------------------------------------------------


def an_analogy() -> AnalogyCard:
    return AnalogyCard(
        id="analogy:finance/regime-switching-ensemble",
        source_domain="quantitative finance",
        source_practice="regime-switching model selection in volatility forecasting",
        mechanism=(
            "When a population contains distinct sub-regimes, a single global predictor is "
            "dominated by a router that detects the regime and dispatches to a specialist."
        ),
        why_it_works_there="Volatility clusters, so one model cannot fit calm and crisis alike.",
        structural_precondition=(
            "The item population must split into sub-populations on which different "
            "predictors have different, identifiable error profiles."
        ),
        discovered_by="cross-domain-analogy",
    )


def a_proposal(**kw) -> Proposal:
    defaults = dict(
        id="P-1",
        title="Route ligands to a specialist model by subpopulation",
        target_stage=Stage.PRIOR,
        mutates="the cross-model selection step in structure-ensemble",
        rationale=(
            "The test set splits into fragments and drug-like analogs with different error "
            "profiles, so one selector is likely dominated by a router."
        ),
        prediction="Per-subpopulation selection beats global selection on the held-out split.",
        kill_criterion="If routed selection does not beat global selection by 0.005, abandon it.",
        measurable_on="LDDT-PLI on the held-out half",
        novelty=Novelty.TRANSFERRED,
        derived_from_analogy="analogy:finance/regime-switching-ensemble",
        est_effort_hours=6,
        risk="low",
        proposed_by="cross-domain-analogy",
    )
    defaults.update(kw)
    return Proposal(**defaults)


def test_transferred_proposal_must_cite_its_analogy():
    with pytest.raises(ValidationError, match="names no source analogy"):
        a_proposal(derived_from_analogy=None)


def test_unprecedented_claim_needs_a_recorded_search():
    with pytest.raises(ValidationError, match="must state what search was run"):
        a_proposal(
            id="P-2",
            novelty=Novelty.UNPRECEDENTED,
            derived_from_analogy=None,
            rationale="This is a completely new idea that nobody has ever thought of before.",
        )
    ok = a_proposal(
        id="P-3",
        novelty=Novelty.UNPRECEDENTED,
        derived_from_analogy=None,
        rationale=(
            "We searched PMC, bioRxiv and the challenge post-mortems and found no prior art "
            "for this specific combination."
        ),
    )
    assert ok.novelty is Novelty.UNPRECEDENTED


def test_proposal_set_requires_the_analogy_card_to_travel_with_it():
    with pytest.raises(ValidationError, match="ship the card with the proposal"):
        ProposalSet(
            run_id="r", generated_by="cross-domain-analogy", target_stage=Stage.PRIOR,
            proposals=[a_proposal()], analogies=[],
        )


def test_triage_order_is_cheap_and_reversible_first():
    pset = ProposalSet(
        run_id="r", generated_by="x", target_stage=Stage.PRIOR,
        analogies=[an_analogy()],
        proposals=[
            a_proposal(id="P-risky", risk="high", est_effort_hours=40, reversible=False),
            a_proposal(id="P-cheap", risk="low", est_effort_hours=2),
        ],
    )
    assert [p.id for p in pset.triage_order()] == ["P-cheap", "P-risky"]


def test_ledger_gates_execution(tmp_path):
    ledger = DecisionLedger(tmp_path / "ledger.jsonl")
    assert not ledger.is_accepted("P-1"), "nothing runs before a human says so"

    ledger.append(Decision(id="D-1", proposal_id="P-1", verdict=Verdict.REJECTED,
                           decided_by="Amit", rationale="Too early; no subpopulation labels yet."))
    assert ledger.verdict_for("P-1") is Verdict.REJECTED
    assert not ledger.is_accepted("P-1")

    # Changing your mind is an append, never an edit.
    ledger.append(Decision(id="D-2", proposal_id="P-1", verdict=Verdict.ACCEPTED,
                           decided_by="Amit", rationale="Labels landed in Stage 1.",
                           supersedes="D-1"))
    assert ledger.is_accepted("P-1")
    assert len(list(ledger)) == 2, "the reversal trail must survive"


def test_decision_must_be_attributable(tmp_path):
    with pytest.raises(ValidationError, match="attributable"):
        Decision(id="D", proposal_id="P", verdict=Verdict.ACCEPTED, decided_by="  ",
                 rationale="looks good")


def test_mechanism_must_be_abstracted():
    # Verbatim restatement.
    with pytest.raises(ValidationError, match="paraphrase rather than an abstraction"):
        AnalogyCard(
            id="analogy:art/collage",
            source_domain="visual art",
            source_practice="combining fragments of different images into one composition",
            mechanism="combining fragments of different images into one composition",
            why_it_works_there="It creates novel juxtapositions.",
            structural_precondition="The problem must involve combining parts into a whole.",
            discovered_by="test",
        )
    # A light paraphrase must also fail — this is what string equality missed.
    with pytest.raises(ValidationError, match="paraphrase rather than an abstraction"):
        AnalogyCard(
            id="analogy:art/collage2",
            source_domain="visual art",
            source_practice="combining fragments of different images into one composition",
            mechanism=(
                "the practice of combining fragments taken from different images "
                "together into a single composition"
            ),
            why_it_works_there="It creates novel juxtapositions.",
            structural_precondition="The problem must involve combining parts into a whole.",
            discovered_by="test",
        )
    # A genuine abstraction passes: no noun from the source domain survives.
    ok = AnalogyCard(
        id="analogy:art/collage3",
        source_domain="visual art",
        source_practice="combining fragments of different images into one composition",
        mechanism=(
            "Assembling a whole from parts drawn out of unrelated wholes preserves "
            "properties of each part while creating relationships that none of the "
            "originals contained."
        ),
        why_it_works_there="It creates novel juxtapositions.",
        structural_precondition=(
            "The parts must retain meaning when removed from their original context."
        ),
        discovered_by="test",
    )
    assert ok.id.endswith("collage3")


# --------------------------------------------------------------------------
# ModelReport end to end
# --------------------------------------------------------------------------


def test_full_report_roundtrip(tmp_path):
    spec = structural_spec()
    report = ModelReport(
        report_id="stage1-test",
        run_id=spec.run_id,
        stage=Stage.LITERATURE,
        title="Target neighbourhood across six axes",
        objective="Characterise what the target resembles on every declared similarity axis.",
        executive_summary=(
            "Built a 3-node graph as a smoke test; the fold axis is populated and the "
            "remaining axes are empty pending the real harvest."
        ),
        methods=[MethodStep(skill="protein-neighborhood", tool="foldseek",
                            summary="Fold search against the PDB", n_calls=1)],
        findings=[
            Finding(id="F-1", kind=FindingKind.OBSERVATION,
                    statement="The closest fold neighbour scores TM 0.86.",
                    confidence=Confidence.SUPPORTED, evidence=[paper_evidence()],
                    kg_nodes=["uniprot:Q14994"]),
        ],
        visuals=VizBundle(stage=Stage.LITERATURE.value, visualizations=[a_viz()]),
        metrics={"n_fold_neighbours": 2},
        handoff=Handoff(to_stage=Stage.BIOCHEM, ready=True,
                        payload={"neighbours": ["uniprot:Q14994"]},
                        recommended_actions=["Compare pocket residues across fold neighbours."]),
        limitations=["Only the fold axis was populated in this smoke test."],
    )

    path = report.write(tmp_path / "report.json")
    reloaded = ModelReport.load(path)
    assert reloaded.stage is Stage.LITERATURE
    assert reloaded.grounded_findings()
    assert reloaded.visuals is not None

    # The advisory visual-gap check should flag the figures this stage did not draw.
    gaps = reloaded.visual_gaps()
    assert "heatmap" in gaps and "provenance_chain" in gaps
    assert "kg_subgraph" not in gaps


def test_empty_report_must_explain_itself():
    with pytest.raises(ValidationError, match="populate `limitations`"):
        ModelReport(
            report_id="r", run_id="r", stage=Stage.LITERATURE, title="Nothing found",
            objective="Find neighbours of the target.",
            executive_summary="We did not find anything at all in this run, unfortunately.",
        )


def test_duplicate_finding_ids_rejected():
    f = Finding(id="F-1", kind=FindingKind.DESIGN_CHOICE,
                statement="Do the thing that we decided to do.", confidence=Confidence.TENTATIVE)
    with pytest.raises(ValidationError, match="duplicate finding id"):
        ModelReport(
            report_id="r", run_id="r", stage=Stage.LITERATURE, title="t",
            objective="Find neighbours of the target.",
            executive_summary="A summary long enough to satisfy the minimum length rule.",
            findings=[f, f.model_copy()],
        )
