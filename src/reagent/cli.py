"""The `reagent` command — the seam between an agent and the typed layer.

Everything here is a thin wrapper over the contracts. Kept thin on purpose: an
agent that can call `reagent report validate` gets a mechanical yes/no, which is
worth far more than a prose opinion about whether a report looks complete.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from reagent import __version__
from reagent.contracts import (
    Confidence,
    Decision,
    DecisionLedger,
    Domain,
    ModelReport,
    ProblemSpec,
    ProposalSet,
    TargetEntity,
    TaskType,
    Verdict,
    render_triage_markdown,
)
from reagent.domains import profile_for, registered_domains
from reagent.kg import KGStore

LEDGER = Path("decisions/ledger.jsonl")


def _ok(msg: str) -> None:
    print(f"  ok    {msg}")


def _err(msg: str) -> None:
    print(f"  FAIL  {msg}")


# --------------------------------------------------------------------------
# problem
# --------------------------------------------------------------------------


def cmd_problem_new(args: argparse.Namespace) -> int:
    run_id = args.run_id or f"{args.name.lower().replace(' ', '-')[:24]}-{datetime.now(UTC):%Y%m%d}"
    try:
        domain = Domain(args.domain)
        task = TaskType(args.task)
    except ValueError as exc:
        _err(f"{exc}\n  domains: {registered_domains()}\n  tasks: {[t.value for t in TaskType]}")
        return 2

    spec = ProblemSpec(
        run_id=run_id,
        name=args.name,
        domain=domain,
        task_type=task,
        targets=[TargetEntity(id=args.target, kind=args.target_kind, label=args.target_label or args.target)],
        metric={
            "name": args.metric or "TBD",
            "direction": "maximize",
            "definition": args.metric_def or "TO BE FILLED IN — every stage optimises against this.",
        },
        axes=profile_for(domain, task),
    )
    out = Path("reports") / run_id / "problem.json"
    spec.write(out)
    print(f"wrote {out}")
    print(f"  run_id: {run_id}")
    print(f"  axes:   {[a.name for a in spec.axes]}")
    if not args.metric:
        print("\n  NOTE: the metric is unset. Fill it in before running any stage —")
        print("  every downstream decision optimises against it and guessing wastes the run.")
    return 0


def cmd_problem_show(args: argparse.Namespace) -> int:
    spec = ProblemSpec.load(Path(args.path))
    print(f"{spec.name}  [{spec.domain.value} / {spec.task_type.value}]  run={spec.run_id}")
    print(f"  target: {spec.primary_target.id} ({spec.primary_target.label})")
    print(f"  metric: {spec.metric.name} ({spec.metric.direction.value}) on {spec.metric.eval_set or '?'}")
    if spec.metric.known_caveats:
        print("  metric caveats:")
        for c in spec.metric.known_caveats:
            print(f"    - {c}")
    print("  axes:")
    for a in spec.axes:
        req = "required" if a.required else "optional"
        print(f"    {a.name:<14} {a.predicate:<24} {a.score_key:<20} {req}")
    if spec.withheld:
        print(f"  withheld: {', '.join(spec.withheld)}")
    return 0


# --------------------------------------------------------------------------
# report
# --------------------------------------------------------------------------


def cmd_report_validate(args: argparse.Namespace) -> int:
    path = Path(args.path)
    try:
        report = ModelReport.load(path)
    except Exception as exc:
        _err(f"{path} is not a valid ModelReport:\n{exc}")
        return 1

    print(f"{path}  [{report.stage.value}]  {report.title}")
    _ok(f"schema {report.schema_version}, {len(report.findings)} findings, "
        f"{len(report.artifacts)} artifacts")

    failures = 0

    grounded = report.grounded_findings()
    if len(grounded) < len(report.findings):
        n = len(report.findings) - len(grounded)
        print(f"  note  {n} findings have no grounded evidence (fine for design choices)")

    gaps = report.visual_gaps()
    if gaps:
        msg = f"missing characteristic visuals: {gaps}"
        if args.strict:
            _err(msg)
            failures += 1
        else:
            print(f"  warn  {msg}")
    else:
        _ok("visuals cover this stage's characteristic figures")

    unviz = report.unvisualized_metrics()
    if unviz:
        msg = f"metrics with no figure reading them: {unviz}"
        if args.strict:
            _err(msg)
            failures += 1
        else:
            print(f"  warn  {msg}")

    if report.handoff is None:
        msg = "no handoff — the next stage has no contract to build against"
        if args.strict:
            _err(msg)
            failures += 1
        else:
            print(f"  warn  {msg}")
    elif not report.handoff.ready:
        print(f"  note  handoff marked NOT ready: {report.handoff.blocking_unknowns}")

    if not report.limitations:
        msg = "no limitations recorded — every real stage has some"
        if args.strict:
            _err(msg)
            failures += 1
        else:
            print(f"  warn  {msg}")

    cost = report.total_cost_usd()
    if cost:
        _ok(f"recorded spend ${cost:.2f}")

    print("PASS" if failures == 0 else f"FAIL ({failures} strict violations)")
    return 1 if failures else 0


# --------------------------------------------------------------------------
# kg
# --------------------------------------------------------------------------


def cmd_kg_stats(args: argparse.Namespace) -> int:
    store = KGStore(args.kg)
    stats = store.stats()
    print(json.dumps(stats, indent=2))
    frac = stats["cited_edge_fraction"]
    if stats["n_edges"] and frac < 0.6:
        print(f"\n  warn  only {frac:.0%} of edges carry a citation — the harvest asserted")
        print("        more than it read. Aim above 0.6 before handing off.")
    return 0


def cmd_kg_audit(args: argparse.Namespace) -> int:
    store = KGStore(args.kg)
    bad = store.unsupported_edges(Confidence.SUPPORTED)
    if not bad:
        _ok("every edge claiming >= supported carries at least one citation")
        return 0
    _err(f"{len(bad)} edges claim >= supported with no citation:")
    for r in bad[:25]:
        print(f"    {r['src']} -{r['predicate']}-> {r['dst']}  ({r['asserted_by']})")
    if len(bad) > 25:
        print(f"    ... and {len(bad) - 25} more")
    return 1


def cmd_kg_query(args: argparse.Namespace) -> int:
    store = KGStore(args.kg)
    rows = store.query(args.sql)
    print(json.dumps(rows, indent=2, default=str))
    print(f"\n{len(rows)} rows", file=sys.stderr)
    return 0


def cmd_viz_kg(args: argparse.Namespace) -> int:
    from reagent.viz import render

    store = KGStore(args.kg)
    axes = []
    if args.problem:
        axes = ProblemSpec.load(Path(args.problem)).axes
    out = Path(args.out)
    try:
        path, viz = render(
            store, args.focal, axes, out,
            title=args.title or f"Neighbourhood of {args.focal}",
            max_depth=args.depth, max_fanout=args.fanout,
        )
    except (KeyError, FileNotFoundError) as exc:
        _err(str(exc))
        return 1
    print(f"wrote {path}  ({path.stat().st_size / 1024:.0f} KB, {viz.n_elements} elements)")
    print(f"  {viz.takeaway}")
    return 0


# --------------------------------------------------------------------------
# skills
# --------------------------------------------------------------------------


def cmd_viz_obsidian(args: argparse.Namespace) -> int:
    from reagent.viz import export_obsidian

    store = KGStore(args.kg)
    summary = export_obsidian(
        store, Path(args.out), focal=args.focal,
        include_evidence_edges=args.include_evidence,
    )
    print(f"wrote vault: {summary['vault']}")
    print(f"  {summary['nodes_written']} notes, {summary['edges_written']} edges")
    print("\n  Reminder: Obsidian cannot encode edge weight — this is a reading")
    print("  interface. Use `reagent viz kg` for the weighted figure.")
    print("  Teammates need the Extended Graph and Dataview plugins for coloured edges.")
    return 0


def cmd_skills_index(args: argparse.Namespace) -> int:
    from reagent.skills import build_registry

    registry, problems = build_registry(Path(args.dir), Path(args.out))
    print(f"wrote {args.out}: {registry['n_skills']} skills")
    for stage, names in registry["by_stage"].items():
        print(f"  {stage:<18} {len(names)}")
    if problems:
        print(f"\n{len(problems)} problems:")
        for p in problems:
            print(f"  - {p}")
        return 1
    _ok("no problems")
    return 0


def cmd_skills_list(args: argparse.Namespace) -> int:
    from reagent.skills import build_registry, format_list

    registry, _ = build_registry(Path(args.dir), Path(args.out))
    print(format_list(registry, args.stage))
    return 0


def cmd_skills_check(args: argparse.Namespace) -> int:
    from reagent.skills import build_registry, check_handoffs

    registry, problems = build_registry(Path(args.dir), Path(args.out))
    flow = check_handoffs(registry)
    for p in problems:
        _err(p)
    for p in flow:
        print(f"  warn  {p}")
    if not problems and not flow:
        _ok(f"{registry['n_skills']} skills, metadata and declared data flow are consistent")
        return 0
    print(f"\n{len(problems)} errors, {len(flow)} flow warnings")
    return 1 if problems else 0


# --------------------------------------------------------------------------
# proposals / decisions
# --------------------------------------------------------------------------


def cmd_triage(args: argparse.Namespace) -> int:
    pset = ProposalSet.load(Path(args.path))
    ledger = DecisionLedger(Path(args.ledger))
    md = render_triage_markdown(pset, ledger)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(md, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(md)
    pending = ledger.pending(pset.proposals)
    print(f"\n{len(pending)} of {len(pset.proposals)} awaiting a verdict", file=sys.stderr)
    return 0


def cmd_decide(args: argparse.Namespace) -> int:
    ledger = DecisionLedger(Path(args.ledger))
    verdict = {"accept": Verdict.ACCEPTED, "reject": Verdict.REJECTED,
               "defer": Verdict.DEFERRED, "info": Verdict.NEEDS_INFO}[args.verdict]
    existing = ledger.current().get(args.proposal_id)
    n = len(list(ledger)) + 1
    d = Decision(
        id=f"D-{n:03d}", proposal_id=args.proposal_id, verdict=verdict,
        decided_by=args.by, rationale=args.message,
        supersedes=existing.id if existing else None,
    )
    ledger.append(d)
    print(f"{d.id}: {args.proposal_id} -> {verdict.value} ({args.by})")
    if existing:
        print(f"  supersedes {existing.id} ({existing.verdict.value})")
    return 0


def cmd_decide_status(args: argparse.Namespace) -> int:
    ledger = DecisionLedger(Path(args.ledger))
    if args.proposal_id:
        v = ledger.verdict_for(args.proposal_id)
        print(f"{args.proposal_id}: {v.value if v else 'pending'}")
        return 0 if v is Verdict.ACCEPTED else 1
    cur = ledger.current()
    if not cur:
        print("no decisions recorded")
        return 0
    for pid, d in sorted(cur.items()):
        print(f"  {pid:<10} {d.verdict.value:<10} {d.decided_by:<10} {d.rationale[:56]}")
    return 0


# --------------------------------------------------------------------------
# assets
# --------------------------------------------------------------------------


def cmd_assets_fetch(args: argparse.Namespace) -> int:
    """Vendor the third-party JS the renderer inlines."""
    import urllib.request

    targets = {
        "assets/vendor/cytoscape.min.js":
            "https://cdn.jsdelivr.net/npm/cytoscape@3.34.1/dist/cytoscape.min.js",
    }
    rc = 0
    for rel, url in targets.items():
        p = Path(rel)
        if p.is_file() and not args.force:
            _ok(f"{rel} present ({p.stat().st_size // 1024} KB)")
            continue
        p.parent.mkdir(parents=True, exist_ok=True)
        try:
            with urllib.request.urlopen(url, timeout=90) as resp:
                p.write_bytes(resp.read())
            _ok(f"fetched {rel} ({p.stat().st_size // 1024} KB)")
        except Exception as exc:
            _err(f"could not fetch {url}: {exc}")
            rc = 1
    return rc


# --------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="reagent", description=__doc__.splitlines()[0])
    p.add_argument("--version", action="version", version=f"reagent {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    # problem
    pr = sub.add_parser("problem", help="create or inspect a ProblemSpec").add_subparsers(
        dest="sub", required=True)
    n = pr.add_parser("new", help="scaffold a ProblemSpec")
    n.add_argument("--name", required=True)
    n.add_argument("--domain", required=True, help=f"one of {registered_domains()}")
    n.add_argument("--task", required=True)
    n.add_argument("--target", required=True, help="namespaced id, e.g. uniprot:O75469")
    n.add_argument("--target-kind", default="protein")
    n.add_argument("--target-label", default=None)
    n.add_argument("--metric", default=None)
    n.add_argument("--metric-def", default=None)
    n.add_argument("--run-id", default=None)
    n.set_defaults(func=cmd_problem_new)
    s = pr.add_parser("show")
    s.add_argument("path")
    s.set_defaults(func=cmd_problem_show)

    # report
    rp = sub.add_parser("report", help="validate a Model Report").add_subparsers(
        dest="sub", required=True)
    v = rp.add_parser("validate")
    v.add_argument("path")
    v.add_argument("--strict", action="store_true",
                   help="promote visual/handoff/limitation warnings to failures (use in CI)")
    v.set_defaults(func=cmd_report_validate)

    # kg
    kg = sub.add_parser("kg", help="knowledge graph").add_subparsers(dest="sub", required=True)
    for name, fn, helptext in (
        ("stats", cmd_kg_stats, "node/edge counts and citation coverage"),
        ("audit", cmd_kg_audit, "find edges claiming confidence they cannot support"),
    ):
        c = kg.add_parser(name, help=helptext)
        c.add_argument("--kg", default="kg")
        c.set_defaults(func=fn)
    q = kg.add_parser("query", help="run a SELECT against the graph")
    q.add_argument("sql")
    q.add_argument("--kg", default="kg")
    q.set_defaults(func=cmd_kg_query)

    # viz
    vz = sub.add_parser("viz", help="render figures").add_subparsers(dest="sub", required=True)
    g = vz.add_parser("kg", help="self-contained interactive ego view")
    g.add_argument("--focal", required=True)
    g.add_argument("--kg", default="kg")
    g.add_argument("--problem", default=None, help="ProblemSpec, so axes drive edge width")
    g.add_argument("--out", default="docs/figures/kg.html")
    g.add_argument("--depth", type=int, default=2)
    g.add_argument("--fanout", type=int, default=30)
    g.add_argument("--title", default=None)
    g.set_defaults(func=cmd_viz_kg)
    ob = vz.add_parser("obsidian", help="export a browsable vault (secondary view, no edge weights)")
    ob.add_argument("--kg", default="kg")
    ob.add_argument("--out", default="docs/vault")
    ob.add_argument("--focal", default=None)
    ob.add_argument("--include-evidence", action="store_true",
                    help="include SUPPORTED_BY etc; they will swamp the backlink panel")
    ob.set_defaults(func=cmd_viz_obsidian)

    # skills
    sk = sub.add_parser("skills", help="the skill registry").add_subparsers(dest="sub", required=True)
    for name, fn, helptext in (
        ("index", cmd_skills_index, "regenerate registry.json from SKILL.md + meta.json"),
        ("check", cmd_skills_check, "lint metadata and the declared data flow between stages"),
    ):
        c = sk.add_parser(name, help=helptext)
        c.add_argument("--dir", default=".claude/skills")
        c.add_argument("--out", default="skills/registry.json")
        c.set_defaults(func=fn)
    lst = sk.add_parser("list", help="human-readable roster")
    lst.add_argument("--stage", default=None)
    lst.add_argument("--dir", default=".claude/skills")
    lst.add_argument("--out", default="skills/registry.json")
    lst.set_defaults(func=cmd_skills_list)

    # triage / decide
    t = sub.add_parser("triage", help="render the proposal triage sheet for a human")
    t.add_argument("path")
    t.add_argument("--ledger", default=str(LEDGER))
    t.add_argument("--out", default=None)
    t.set_defaults(func=cmd_triage)

    d = sub.add_parser("decide", help="record a verdict on a proposal (append-only)")
    dsub = d.add_subparsers(dest="sub")
    st = dsub.add_parser("status", help="show effective verdicts")
    st.add_argument("proposal_id", nargs="?", default=None)
    st.add_argument("--ledger", default=str(LEDGER))
    st.set_defaults(func=cmd_decide_status)
    d.add_argument("proposal_id", nargs="?")
    d.add_argument("verdict", nargs="?", choices=["accept", "reject", "defer", "info"])
    d.add_argument("-m", "--message", default="", help="why. Future-you will want this.")
    d.add_argument("--by", default="human", help="who decided")
    d.add_argument("--ledger", default=str(LEDGER))
    d.set_defaults(func=cmd_decide)

    # assets
    a = sub.add_parser("assets", help="vendored third-party files").add_subparsers(
        dest="sub", required=True)
    af = a.add_parser("fetch", help="download the JS the renderer inlines")
    af.add_argument("--force", action="store_true")
    af.set_defaults(func=cmd_assets_fetch)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.cmd == "decide" and getattr(args, "func", None) is cmd_decide:
        if not args.proposal_id or not args.verdict:
            print("usage: reagent decide <proposal-id> accept|reject|defer|info -m 'why'")
            print("       reagent decide status [proposal-id]")
            return 2
        if not args.message:
            print("a decision needs a rationale: pass -m 'why'")
            return 2
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
