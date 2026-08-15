"""Build and render a complete Stage 1 Model Report over the demo graph.

Run after `seed_demo_graph.py`:
    python examples/seed_demo_report.py

This exists to prove the whole chain end to end — graph, figure, contract, HTML —
and to give teammates a worked example of a report that passes strict validation.

The findings below describe what the demo *fixture* actually contains, including
that its similarity scores are placeholders. A demo report that overstated its own
fixture would be a poor advertisement for a project whose main claim is that claims
should be checkable.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from reagent.contracts import (  # noqa: E402
    AgentIdentity,
    Artifact,
    Confidence,
    Evidence,
    Finding,
    FindingKind,
    Handoff,
    InputRef,
    MethodStep,
    ModelReport,
    ProblemSpec,
    SourceType,
    Stage,
    VizBundle,
)
from reagent.kg import KGStore  # noqa: E402
from reagent.reports import render as render_report  # noqa: E402
from reagent.viz import heatmap, ranked_bar  # noqa: E402
from reagent.viz import render as render_graph  # noqa: E402

RUN = "demo"
FIG = "docs/figures"


def ev(locator: str, title: str | None = None, year: int | None = None) -> Evidence:
    return Evidence(source_type=SourceType.PAPER, locator=locator, title=title, year=year)


def main() -> int:
    spec = ProblemSpec.load(REPO / "reports" / RUN / "problem.json")
    store = KGStore(REPO / "kg" / "demo")
    stats = store.stats()
    target = spec.primary_target.id

    # -- the figure ----------------------------------------------------------
    fig_path, viz = render_graph(
        store, target, spec.axes, REPO / "docs" / "figures" / "demo_kg.html",
        title="Target neighbourhood across the declared axes",
        subtitle=("Demo fixture: identifiers are real; similarity scores are "
                  "illustrative placeholders shown at 'speculative' confidence."),
        max_depth=2, repo_root=REPO,
    )

    # -- what the graph actually says ---------------------------------------
    fold = store.along_axis(target, spec.axis("fold"), limit=5)
    promis = store.along_axis(target, spec.axis("promiscuity"), limit=5)
    nr_members = store.family_members("family:nuclear-receptor")

    # -- axis-agreement heatmap ---------------------------------------------
    # The figure that shows whether the axes agree. Unpopulated axes render as
    # hatched cells rather than zeros, so the gaps read as gaps.
    hood = store.neighborhood(target, spec.axes, per_axis_limit=40)
    neighbours: list[str] = []
    for rows in hood.values():
        for r in rows:
            if r["other_type"] == "Protein" and r["other"] not in neighbours:
                neighbours.append(r["other"])
    neighbours = neighbours[:12]
    label_of = {r["other"]: r["other_label"] for rows in hood.values() for r in rows}

    axis_names = [a.name for a in spec.axes]
    matrix: list[list[float | None]] = []
    for nid in neighbours:
        row: list[float | None] = []
        for a in spec.axes:
            hit = next((r for r in hood[a.name] if r["other"] == nid), None)
            row.append(float(hit["attrs"].get(a.score_key)) if hit and
                       isinstance(hit["attrs"].get(a.score_key), (int, float)) else None)
        matrix.append(row)

    _, heat_viz = heatmap(
        [label_of.get(n, n) for n in neighbours], axis_names, matrix,
        REPO / FIG / "demo_axis_agreement.svg",
        viz_id="V-HEAT-01",
        title="Axis agreement across the target's neighbours",
        question="Do the similarity axes agree about which entities are close to the target?",
        takeaway=(
            "Fold and sequence rank the same neighbours similarly, while the pocket, "
            "motif and compound axes are entirely unmeasured — the hatched columns are "
            "the work Stage 1 has not done yet."
        ),
        reads_from=["kg/demo/nodes.jsonl", "kg/demo/edges.jsonl"],
        value_label="normalised score",
        covers_metrics=["n_fold_neighbours"],
        repo_root=REPO,
    )

    # -- citation coverage per predicate ------------------------------------
    cov = store.query(
        """
        SELECT predicate,
               ROUND(CAST(SUM(CASE WHEN n_evidence > 0 THEN 1 ELSE 0 END) AS REAL)
                     / COUNT(*), 3) AS cited_fraction
        FROM edges GROUP BY predicate ORDER BY cited_fraction DESC
        """
    )
    _, bar_viz = ranked_bar(
        [r["predicate"] for r in cov], [r["cited_fraction"] for r in cov],
        REPO / FIG / "demo_citation_coverage.svg",
        viz_id="V-BAR-01",
        title="Citation coverage by predicate",
        question="Which kinds of assertion in this graph are backed by a citation?",
        takeaway=(
            "Composition and interaction edges are fully cited; the similarity edges are "
            "uncited because they are placeholders, which is exactly the pattern a real "
            "harvest must not show."
        ),
        reads_from=["kg/demo/edges.jsonl"],
        value_label="fraction of edges with at least one citation",
        covers_metrics=["cited_edge_fraction", "n_family_members"],
        highlight=[i for i, r in enumerate(cov) if r["cited_fraction"] == 0.0],
        repo_root=REPO,
    )

    findings = [
        Finding(
            id="F-CONSTRAINT-01",
            kind=FindingKind.CONSTRAINT,
            statement=(
                "Every quantitative edge in this fixture is a placeholder, flagged "
                "illustrative=True and written at speculative confidence. No number here "
                "may be used as a prior until the corresponding tool has actually run."
            ),
            confidence=Confidence.ESTABLISHED,
            evidence=[
                Evidence(source_type=SourceType.COMPUTATION,
                         locator="examples/seed_demo_graph.py",
                         title="the fixture that generated this graph"),
                Evidence(source_type=SourceType.COMPUTATION,
                         locator="kg/demo/edges.jsonl",
                         title="every scored edge carries illustrative=True"),
            ],
            data={"n_illustrative_edges": sum(
                1 for e in store.iter_edges() if e.attrs.get("illustrative"))},
        ),
        Finding(
            id="F-FAMILY-01",
            kind=FindingKind.OBSERVATION,
            statement=(
                f"The target sits in a receptor family with {len(nr_members)} members "
                "represented in this fixture, spanning receptors with very unequal "
                "structural coverage."
            ),
            confidence=Confidence.ESTABLISHED,
            evidence=[
                ev("pmc:PMC9563780", "PXR ligand-binding pocket architecture", 2022),
                ev("pmc:PMC8864553", "Promiscuity of the PXR ligand-binding domain", 2022),
            ],
            data={"n_family_members": len(nr_members)},
            kg_nodes=["family:nuclear-receptor"],
        ),
        Finding(
            id="F-PROMISC-01",
            kind=FindingKind.PRIOR,
            statement=(
                "The most promiscuous neighbours are xenobiotic-handling enzymes and "
                "transporters outside the target's own family, which makes them candidate "
                "transfer sources on the basis of a shared structural problem — a large, "
                "adaptable pocket — rather than a shared fold."
            ),
            confidence=Confidence.TENTATIVE,
            evidence=[ev("pmc:PMC8864553",
                         "Promiscuity of the PXR ligand-binding domain", 2022)],
            data={
                "top_promiscuous_neighbours": [r["other_label"] for r in promis[:4]],
                "valid_for": "targets with a large, chemically permissive pocket",
                "invalid_for": (
                    "targets with a small, shape-selective pocket, where breadth of "
                    "binding is not the shared feature"
                ),
            },
            kg_nodes=[r["other"] for r in promis[:4]],
        ),
        Finding(
            id="F-NEG-01",
            kind=FindingKind.NEGATIVE,
            statement=(
                "Five of the seven declared similarity axes are empty in this fixture. "
                "Sequence and fold carry placeholder edges; pocket, motif, and compound "
                "have none at all, so no downstream stage may treat this graph as a "
                "characterisation of the target."
            ),
            confidence=Confidence.SUPPORTED,
            evidence=[Evidence(source_type=SourceType.COMPUTATION,
                               locator="kg/demo/edges.jsonl",
                               title="edges_by_predicate from KGStore.stats()")],
            data={
                "populated_axes": sorted(
                    a.name for a in spec.axes
                    if store.along_axis(target, a, limit=1)
                ),
                "empty_axes": sorted(
                    a.name for a in spec.axes
                    if not store.along_axis(target, a, limit=1)
                ),
            },
        ),
        Finding(
            id="F-DESIGN-01",
            kind=FindingKind.DESIGN_CHOICE,
            statement=(
                "Each similarity axis writes its own predicate rather than a generic "
                "SIMILAR_TO edge, so a downstream stage can ask for fold neighbours that "
                "are not family members — a query a single similarity relation cannot "
                "express."
            ),
            confidence=Confidence.SUPPORTED,
            data={"predicates_used": sorted(stats["edges_by_predicate"])},
        ),
        Finding(
            id="F-RISK-01",
            kind=FindingKind.RISK,
            statement=(
                f"Only {stats['cited_edge_fraction']:.0%} of edges carry a citation. The "
                "uncited remainder are the placeholder similarity edges, which is expected "
                "here, but the same figure on a real harvest would mean the stage asserted "
                "more than it read."
            ),
            confidence=Confidence.SUPPORTED,
            evidence=[Evidence(source_type=SourceType.COMPUTATION,
                               locator="kg/demo/kg.sqlite",
                               title="cited_edge_fraction from KGStore.stats()")],
            data={"cited_edge_fraction": stats["cited_edge_fraction"]},
        ),
    ]

    report = ModelReport(
        report_id=f"stage1-{RUN}",
        run_id=RUN,
        stage=Stage.LITERATURE,
        title="Stage 1 demo — target neighbourhood on a fixture graph",
        produced_by=AgentIdentity(model="claude-fable-5", skill="target-neighborhood",
                                  human_owner="amit"),
        objective=(
            "Demonstrate the Stage 1 contract end to end on a fixture: build a "
            "multi-axis neighbourhood, render it, and report honestly on what the graph "
            "does and does not contain."
        ),
        executive_summary=(
            f"Built a {stats['n_nodes']}-node, {stats['n_edges']}-edge fixture graph around "
            f"the target and rendered it as a self-contained interactive ego view. Two of "
            f"seven declared similarity axes are populated, both with illustrative "
            f"placeholder scores rather than measurements, so this report demonstrates the "
            f"machinery rather than characterising the target. The promiscuity axis is the "
            f"interesting one even in fixture form: its top neighbours sit outside the "
            f"target's family, which is where non-obvious transfer sources live."
        ),
        inputs=[
            InputRef(kind="report", locator=f"reports/{RUN}/problem.json",
                     note="ProblemSpec: target, domain, metric, and the declared axes"),
            InputRef(kind="kg", locator="kg/demo/nodes.jsonl",
                     note="fixture graph seeded by examples/seed_demo_graph.py"),
        ],
        methods=[
            MethodStep(skill="target-neighborhood", tool="KGStore.neighborhood",
                       summary="Queried each declared axis for the target's neighbours",
                       params={"axes": [a.name for a in spec.axes], "per_axis_limit": 25}),
            MethodStep(skill="kg-visualize", tool="cytoscape.js (inlined)",
                       summary="Rendered a two-hop ego view with per-axis edge encoding",
                       params={"max_depth": 2, "max_fanout": 30,
                               "n_elements": viz.n_elements}),
            MethodStep(skill="target-neighborhood", tool="foldseek",
                       summary="Fold search — NOT RUN in this fixture",
                       failed=True,
                       failure_note=("Not executed. Fold edges here are placeholders; "
                                     "this row exists so the omission is visible in the "
                                     "report rather than implied by its absence.")),
        ],
        findings=findings,
        artifacts=[
            Artifact(path="kg/demo/nodes.jsonl", kind="kg-nodes",
                     description="Graph nodes, one JSON object per line").stamp(REPO),
            Artifact(path="kg/demo/edges.jsonl", kind="kg-edges",
                     description="Graph edges with provenance and evidence").stamp(REPO),
            Artifact(path="docs/figures/demo_kg.html", kind="figure",
                     description="Self-contained interactive ego view").stamp(REPO),
            Artifact(path="docs/figures/demo_axis_agreement.svg", kind="figure",
                     description="Axis-agreement heatmap; hatched cells are unmeasured"
                     ).stamp(REPO),
            Artifact(path="docs/figures/demo_citation_coverage.svg", kind="figure",
                     description="Citation coverage per predicate").stamp(REPO),
        ],
        # Reading order tells the story: the neighbourhood first, then whether the
        # axes agree about it, then how much of it is actually cited.
        visuals=VizBundle(
            stage=Stage.LITERATURE.value,
            visualizations=[viz, heat_viz, bar_viz],
            reading_order=[viz.id, heat_viz.id, bar_viz.id],
        ),
        metrics={
            "n_nodes": stats["n_nodes"],
            "n_edges": stats["n_edges"],
            "cited_edge_fraction": stats["cited_edge_fraction"],
            "n_family_members": len(nr_members),
            "n_fold_neighbours": len(fold),
        },
        limitations=[
            "Every similarity score is an illustrative placeholder, not a measurement.",
            "Five of seven declared axes are unpopulated: pocket, motif, and compound "
            "have no edges; promiscuity and family carry only asserted membership.",
            "No domain-shift measurement was performed, because the fixture has no test "
            "compound set — that measurement is Stage 1's most decision-relevant output "
            "and its absence here is the largest gap.",
            "One characteristic Stage 1 figure is still missing: a provenance chain "
            "tracing a claim through its evidence to its sources. `reagent report "
            "validate --strict` therefore fails this report, correctly.",
        ],
        open_questions=[
            "Do the fold and pocket axes agree for this target, or does high fold "
            "similarity coexist with dissimilar pockets?",
            "Which promiscuous non-family neighbours have co-crystal structures usable as "
            "templates, and is templating permitted by the challenge rules?",
            "What is the chemotype distance between the test compounds and every known "
            "ligand of the target, and is that distribution bimodal?",
        ],
        handoff=Handoff(
            to_stage=Stage.BIOCHEM,
            ready=False,
            payload={
                "target": target,
                "neighbours_by_axis": {
                    "fold": [r["other"] for r in fold],
                    "promiscuity": [r["other"] for r in promis],
                },
                "family_corpus": [r["id"] for r in nr_members],
                "pocket_anchors": [
                    n.id for n in store.iter_nodes()
                    if n.id.startswith("residue:")
                ],
                "priors": [{
                    "claim": "Promiscuous non-family proteins are candidate transfer sources.",
                    "valid_for": "targets with a large, chemically permissive pocket",
                    "invalid_for": "targets with a small, shape-selective pocket",
                }],
            },
            recommended_actions=[
                "Treat the pocket-lining residues in the payload as a starting hypothesis "
                "and rank them by recurrence across the family corpus, not by proximity.",
                "Run the interaction profilers in pairs and report their concordance; a "
                "single profiler recovers only part of the canonical contact set.",
            ],
            blocking_unknowns=[
                "No measured similarity scores exist yet, so template ranking is not "
                "possible from this graph.",
                "No dataset pointers have been harvested, so there is nothing for "
                "data-materialize to fetch.",
            ],
        ),
    )

    report_path = report.write(REPO / "reports" / RUN / Stage.LITERATURE.value / "report.json")
    html = render_report(report, REPO / "docs" / "reports" / f"{report.report_id}.html",
                         repo_root=REPO)

    print(f"graph  : {stats['n_nodes']} nodes, {stats['n_edges']} edges")
    print(f"figure : {fig_path.relative_to(REPO)} ({fig_path.stat().st_size / 1024:.0f} KB)")
    print(f"report : {report_path.relative_to(REPO)}")
    print(f"html   : {html.relative_to(REPO)} ({html.stat().st_size / 1024:.0f} KB)")
    print(f"gaps   : {report.visual_gaps()}")
    print(f"unviz  : {report.unvisualized_metrics()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
