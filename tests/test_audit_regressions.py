"""Regressions for the doc-vs-code gaps found by the reference-doc audit.

Each test here corresponds to a claim the documentation made that the code did not
actually enforce. Keeping them as tests is what stops the docs drifting ahead of the
implementation again.
"""

from __future__ import annotations

import re

import pytest
from pydantic import ValidationError

from reagent.contracts import (
    Access,
    Confidence,
    DataFormat,
    DataRef,
    Edge,
    Evidence,
    FetchPlan,
    Finding,
    FindingKind,
    GraphDelta,
    MeasurementKind,
    ModelReport,
    Node,
    NodeType,
    Predicate,
    SourceType,
    Stage,
)
from reagent.kg import KGStore

from .test_contracts import _protein, a_proposal, paper_evidence


def test_every_predicate_has_declared_endpoint_types():
    """A predicate missing from PREDICATE_DOMAINS silently loses type checking.

    This test is why a new predicate must be added to both places at once, rather
    than discovering months later that a Compound got attached to a Family.
    """
    from reagent.contracts.kg import unconstrained_predicates

    missing = unconstrained_predicates()
    assert missing == [], (
        "these predicates have no entry in PREDICATE_DOMAINS, so their edges are "
        f"never type-checked: {missing}"
    )


def test_every_profile_axis_predicate_is_constrained():
    """Domain profiles may only declare axes whose predicates are type-checked."""
    from reagent.contracts.kg import PREDICATE_DOMAINS
    from reagent.domains import PROFILES

    declared = {a.predicate for axes in PROFILES.values() for a in axes}
    constrained = {p.value for p in PREDICATE_DOMAINS}
    assert declared <= constrained, (
        f"unconstrained axis predicates: {sorted(declared - constrained)}"
    )


def test_profile_axes_declare_an_achievable_score_range():
    """An axis whose score cannot reach its declared range misleads the renderer."""
    from reagent.domains import PROFILES

    for domain, axes in PROFILES.items():
        for a in axes:
            lo, hi = a.score_range
            assert hi > lo, f"{domain.value}/{a.name} has an empty score_range"
            # Any axis whose natural output is unbounded must say how it is normalised,
            # or two runs produce incomparable graphs.
            if (lo, hi) == (0.0, 1.0) and a.score_key in {"breadth_score"}:
                assert a.notes and "normalis" in a.notes.lower(), (
                    f"{a.name} declares 0-1 but its methods yield unbounded counts; "
                    "notes must name the transform"
                )


def test_write_jsonl_refuses_an_invalid_delta(tmp_path):
    """The source of truth must not accept a dangling edge."""
    delta = GraphDelta(
        run_id="r",
        asserted_by="t",
        nodes=[_protein("uniprot:A", "A")],
        edges=[
            Edge(src="uniprot:A", predicate=Predicate.SIMILAR_FOLD_TO,
                 dst="uniprot:GONE", asserted_by="t")
        ],
    )
    with pytest.raises(ValueError, match="refusing to write an invalid GraphDelta"):
        delta.write_jsonl(tmp_path)
    assert not (tmp_path / "edges.jsonl").exists(), "nothing may be written on rejection"


def test_type_check_sees_already_stored_nodes(tmp_path):
    """An incremental delta attaching to existing nodes must still be type-checked."""
    store = KGStore(tmp_path / "kg")
    store.merge(GraphDelta(run_id="r1", asserted_by="t", nodes=[
        _protein("uniprot:A", "A"),
        Node(id="family:X", type=NodeType.FAMILY, label="X", asserted_by="t"),
    ]))
    # family:X exists only in the store, so this used to pass unchecked.
    bad = GraphDelta(run_id="r2", asserted_by="t", nodes=[], edges=[
        Edge(src="family:X", predicate=Predicate.SIMILAR_FOLD_TO, dst="uniprot:A",
             asserted_by="t")
    ])
    problems = store.merge(bad)
    assert any("cannot start at a Family" in p for p in problems)


def test_mutates_must_name_something_specific():
    with pytest.raises(ValidationError, match="names nothing specific"):
        a_proposal(id="P-vague", mutates="the whole pipeline")
    with pytest.raises(ValidationError, match="names nothing specific"):
        a_proposal(id="P-vague2", mutates="everything")
    assert a_proposal(id="P-ok", mutates="the z-score step in confidence-selection")


def test_grey_literature_cannot_establish_a_finding():
    grey = [
        Evidence(source_type=SourceType.BLOG, locator="https://example.org/post-a"),
        Evidence(source_type=SourceType.SOCIAL, locator="https://example.org/post-b"),
    ]
    with pytest.raises(ValidationError, match="grey literature alone"):
        Finding(id="F-g", kind=FindingKind.OBSERVATION,
                statement="A tool silently fails on a class of input.",
                confidence=Confidence.ESTABLISHED, evidence=grey)

    # Two grey sources are fine at 'supported' — grey evidence is still evidence,
    # and is often the only record of a negative result.
    ok = Finding(id="F-g2", kind=FindingKind.OBSERVATION,
                 statement="A tool silently fails on a class of input.",
                 confidence=Confidence.SUPPORTED, evidence=grey)
    assert ok.confidence is Confidence.SUPPORTED

    # Grey plus a reviewed source can reach 'established'.
    assert Finding(id="F-g3", kind=FindingKind.OBSERVATION,
                   statement="A tool silently fails on a class of input.",
                   confidence=Confidence.ESTABLISHED, evidence=[*grey, paper_evidence()])


def test_grey_and_grounded_classification():
    assert SourceType.BLOG.is_grounded and SourceType.BLOG.is_grey
    assert SourceType.PAPER.is_grounded and not SourceType.PAPER.is_grey
    assert not SourceType.ANALOGY.is_grounded
    assert not SourceType.EXPERT_PRIOR.is_grounded


def test_dataref_gated_access_needs_a_fetch_hint():
    with pytest.raises(ValidationError, match="no fetch_hint"):
        DataRef(id="kaggle:some-comp", title="A competition", url="https://example.org",
                access=Access.REGISTRATION, discovered_by="source-scout")

    ok = DataRef(
        id="kaggle:some-comp", title="A competition", url="https://example.org",
        access=Access.REGISTRATION, fetch_hint="kaggle competitions download -c some-comp",
        measures=[MeasurementKind.BINDING_AFFINITY], fmt=DataFormat.CSV,
        entities={"targets": ["uniprot:O75469"]}, discovered_by="source-scout",
    )
    assert ok.covers("uniprot:O75469")
    assert ok.answers(MeasurementKind.BINDING_AFFINITY)
    assert not ok.is_materialised
    assert not ok.is_fetchable, "a registration wall needs a human"


def test_dataref_local_path_requires_a_timestamp():
    with pytest.raises(ValidationError, match="no retrieved_utc"):
        DataRef(id="zenodo:10.5281/zenodo.1", title="t", url="https://example.org",
                discovered_by="s", local_path="data/cache/x.csv")


def test_dataref_id_must_be_namespaced():
    with pytest.raises(ValidationError, match="namespaced"):
        DataRef(id="just-a-name", title="t", url="https://example.org", discovered_by="s")


def test_fetch_plan_surfaces_blocked_and_budget():
    open_ds = DataRef(id="zenodo:10.5281/zenodo.1", title="open", url="https://example.org",
                      access=Access.OPEN, size_bytes=1_000, discovered_by="s")
    gated = DataRef(id="kaggle:c", title="gated", url="https://example.org",
                    access=Access.REQUEST, fetch_hint="email the authors",
                    size_bytes=2_000, discovered_by="s")
    plan = FetchPlan(run_id="r", requested_by="pocket-anatomy",
                     purpose="Map ligand functional groups onto pocket residues.",
                     datasets=[open_ds, gated], max_total_bytes=1_500)
    assert [d.id for d in plan.blocked()] == ["kaggle:c"]
    assert plan.total_bytes() == 3_000
    assert not plan.within_budget()
    assert "OVER BUDGET" in plan.summary()
    assert "email the authors" in plan.summary(), "a gated dataset must surface its hint"


def test_report_scaffold_is_invalid_until_edited():
    """A scaffold that validated immediately would let a stage ship an empty report."""
    from reagent.reports.scaffold import new_report

    r = new_report(Stage.LITERATURE, "run-x", owner="amit")
    assert "TODO" in r.executive_summary
    assert r.handoff is not None and not r.handoff.ready
    assert any("TODO" in lim for lim in r.limitations)


def test_report_renders_self_contained_html_with_inline_citations(tmp_path):
    from reagent.reports import render as render_report

    report = ModelReport(
        report_id="r1", run_id="r", stage=Stage.LITERATURE, title="T",
        objective="Characterise the target neighbourhood.",
        executive_summary="A summary long enough to satisfy the minimum length rule here.",
        findings=[
            Finding(id="F-1", kind=FindingKind.OBSERVATION,
                    statement="The closest fold neighbour scores 0.86.",
                    confidence=Confidence.SUPPORTED, evidence=[paper_evidence()]),
            Finding(id="F-2", kind=FindingKind.NEGATIVE,
                    statement="Sequence identity did not predict pocket similarity here.",
                    confidence=Confidence.TENTATIVE, evidence=[paper_evidence("pmid:1")]),
        ],
        metrics={"n_fold_neighbours": 2},
        limitations=["Only one axis was populated."],
    )
    out = render_report(report, tmp_path / "r.html", repo_root=tmp_path)
    html = out.read_text(encoding="utf-8")

    assert "10.1016/j.str.2025.09.011" in html, "citations belong inline, not in a bibliography"
    assert "https://doi.org/10.1016" in html, "resolvable locators become links"
    assert "negative result" in html, "negative findings must be visible, not hidden"

    # The publish target blocks every remote host, so the only permissible external
    # references are the citation hyperlinks themselves.
    allowed = ("doi.org", "pubmed.ncbi", "ncbi.nlm.nih.gov", "rcsb.org", "uniprot.org",
               "ebi.ac.uk", "clinicaltrials.gov", "arxiv.org")
    externals = re.findall(r'(?:src|href)="(https?://[^"]*)"', html)
    bad = [u for u in externals if not any(a in u for a in allowed)]
    assert not bad, f"unexpected external resource request: {bad}"
    assert 'src="http' not in html, "no external script or image sources"
