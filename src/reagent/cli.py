"""The `reagent` command — the seam between an agent and the typed layer.

Everything here is a thin wrapper over the contracts. Kept thin on purpose: an
agent that can call `reagent report validate` gets a mechanical yes/no, which is
worth far more than a prose opinion about whether a report looks complete.
"""

from __future__ import annotations

import argparse
import json
import os
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

    # -- the interpretive layer: can a non-specialist use this report? ----
    if not report.plain_summary:
        msg = (
            "no plain_summary — a reader outside the field has no way in. Write the "
            "outcome again with no undefined jargon."
        )
        if args.strict:
            _err(msg)
            failures += 1
        else:
            print(f"  warn  {msg}")

    if lang := report.plain_language_problems():
        for p in lang:
            if args.strict:
                _err(p)
                failures += 1
            else:
                print(f"  warn  {p}")
    elif report.plain_summary:
        gloss = report.effective_glossary()
        _ok(f"plain language checks out ({len(gloss.terms)} glossary terms defined)")

    if telling := report.knowledge_telling_findings():
        msg = (
            f"{len(telling)} interpretations restate rather than explain "
            f"({sorted(telling)[:5]}). An explanation entailed by the source text has "
            "demonstrated nothing — require a mechanism, a prediction, or a boundary."
        )
        if args.strict:
            _err(msg)
            failures += 1
        else:
            print(f"  warn  {msg}")
        for fid, probs in sorted(telling.items())[:3]:
            for pr in probs:
                print(f"        {fid}: {pr}")

    # -- progressive disclosure: can a reader drill in? -------------------
    if fu := report.follow_up_problems():
        for p in fu:
            if args.strict:
                _err(p)
                failures += 1
            else:
                print(f"  warn  {p}")
    elif depths := report.disclosure_depth():
        _ok(
            f"follow-up trees on {len(depths)} sections, max depth "
            f"{max(depths.values())}, no dead ends"
        )
    if bare := report.findings_without_follow_ups():
        print(
            f"  note  {len(bare)} decision-bearing findings a reader cannot drill into: "
            f"{bare[:6]}"
        )

    # -- coverage: what did the search not reach? -------------------------
    if covp := report.coverage_problems():
        for p in covp:
            if args.strict:
                _err(p)
                failures += 1
            else:
                print(f"  warn  {p}")
    if mix := report.discovery_channel_mix():
        _ok("channel mix: " + ", ".join(f"{k} {v:.0%}" for k, v in list(mix.items())[:5]))
    if report.search is None and report.stage.value in {
        "stage0_scouting", "stage1_literature",
    }:
        msg = (
            "no search ledger on a retrieval stage, so 'we searched thoroughly' is an "
            "assertion rather than a report. A missing source leaves no trace in the "
            "citations, which is why the shape of the search has to be recorded."
        )
        if args.strict:
            _err(msg)
            failures += 1
        else:
            print(f"  warn  {msg}")
    if neg := report.neglected_sources():
        _ok(
            f"{len(neg)} under-attended sources recovered "
            f"({sorted({r for _, rs in neg for r in rs})})"
        )

    if uninterp := report.uninterpreted_findings():
        print(f"  note  {len(uninterp)} findings have no interpretation: {uninterp[:6]}")
    if trivia := report.findings_without_implications():
        print(
            f"  note  {len(trivia)} interpreted findings change nothing downstream "
            f"(candidate trivia): {trivia[:6]}"
        )
    if by_stage := report.implications_by_stage():
        _ok("bears on " + ", ".join(f"{s} ({len(v)})" for s, v in sorted(by_stage.items())))
    if cov := report.audience_coverage():
        _ok("audiences addressed: " + ", ".join(f"{k} ({v})" for k, v in cov.items()))

    cost = report.total_cost_usd()
    if cost:
        _ok(f"recorded spend ${cost:.2f}")

    print("PASS" if failures == 0 else f"FAIL ({failures} strict violations)")
    return 1 if failures else 0


def cmd_report_new(args: argparse.Namespace) -> int:
    from reagent.contracts import Stage
    from reagent.reports.scaffold import write_scaffold

    try:
        stage = Stage(args.stage)
    except ValueError:
        _err(f"unknown stage {args.stage!r}; one of {[s.value for s in Stage]}")
        return 2
    spec = None
    spec_path = Path("reports") / args.run_id / "problem.json"
    if spec_path.is_file():
        spec = ProblemSpec.load(spec_path)
    path = write_scaffold(stage, args.run_id, title=args.title, owner=args.owner, spec=spec)
    print(f"wrote {path}")
    print("  This scaffold is intentionally INVALID until you edit it — every")
    print("  required field holds a TODO. Run `reagent report validate` as you go.")
    return 0


def cmd_report_render(args: argparse.Namespace) -> int:
    from reagent.reports import render as render_report

    try:
        report = ModelReport.load(Path(args.path))
    except Exception as exc:
        _err(f"{args.path} is not a valid ModelReport:\n{exc}")
        return 1
    out = Path(args.out) if args.out else Path("docs/reports") / f"{report.report_id}.html"
    path = render_report(report, out)
    print(f"wrote {path}  ({path.stat().st_size / 1024:.0f} KB)")
    if gaps := report.visual_gaps():
        print(f"  warn  missing characteristic figures: {gaps}")
    return 0


# --------------------------------------------------------------------------
# kg
# --------------------------------------------------------------------------


def cmd_axes_checklist(args: argparse.Namespace) -> int:
    """Print the property checklist for a domain, with each item's question."""
    from reagent.contracts.axes import CHECKLISTS, checklist_for
    from reagent.contracts.problem import Domain

    try:
        domain = Domain(args.domain)
    except ValueError:
        _err(f"unknown domain {args.domain!r}; one of {[d.value for d in Domain]}")
        return 1

    items = checklist_for(domain)
    registered = domain in CHECKLISTS
    print(f"{domain.value}: {len(items)} checklist items")
    if not registered:
        print(
            "  note  this domain has no registered checklist, so it falls back to the "
            "largest one. That is deliberate: an unregistered domain should make the "
            "coverage gate harder to pass, not trivially passable."
        )
    for k in items:
        print(f"\n  {k.value}")
        print(f"    {k.question}")
    return 0


def cmd_axes_derive(args: argparse.Namespace) -> int:
    """Check a report's axis derivation against its domain checklist."""
    try:
        report = ModelReport.load(Path(args.report))
    except Exception as exc:
        _err(f"{args.report} is not a valid ModelReport:\n{exc}")
        return 1

    if report.sweep is None:
        _err(
            "report has no `sweep`, so there is no axis derivation to check. Run "
            "target-properties first — accepting the ProblemSpec's axis list as final is "
            "the failure this command exists to catch."
        )
        return 1

    print(report.sweep.derivation.summary())
    problems = report.sweep.derivation.problems()
    if problems and args.strict:
        print(f"FAIL ({len(problems)} problems)")
        return 1
    print("PASS" if not problems else f"WARN ({len(problems)} problems)")
    return 0


def cmd_axes_sweep_status(args: argparse.Namespace) -> int:
    """Per-axis exhaustion status: the curve, the state, and every open lead."""
    try:
        report = ModelReport.load(Path(args.report))
    except Exception as exc:
        _err(f"{args.report} is not a valid ModelReport:\n{exc}")
        return 1

    if report.sweep is None:
        _err("report has no `sweep` — nothing to report on")
        return 1

    print(report.sweep.summary())
    problems = report.sweep.problems()
    if leads := report.sweep.open_leads():
        print(f"\n{len(leads)} axes stopped short and are worth resuming: {leads}")
    if problems and args.strict:
        print(f"FAIL ({len(problems)} problems)")
        return 1
    print("PASS" if not problems else f"WARN ({len(problems)} problems)")
    return 0


#: The credentials this project can use. Names and purposes only — never values.
#:
#: Everything here is optional by default, because the pipeline should degrade rather than
#: refuse: with no compute credentials Stages 0-2 still run end to end, and that is a useful
#: system. Mark a secret required only when a stage genuinely cannot proceed without it.
_DEFAULT_SECRETS = [
    ("MODAL_TOKEN_ID", "Serverless GPU compute — co-folding and any long unattended run.",
     "run `modal token new`, which writes both halves", ["docking", "md", "cofold"],
     "workspace-scoped, not account-wide"),
    ("MODAL_TOKEN_SECRET", "The secret half of the Modal token pair.",
     "run `modal token new`", ["docking", "md", "cofold"], "workspace-scoped"),
    ("TAMARIND_API_KEY", "Hosted docking and molecular dynamics.",
     "your Tamarind account settings", ["docking", "md"], "read+submit only if offered"),
    ("ANTHROPIC_API_KEY", "Running the pipeline's own agents outside a Claude Code session.",
     "https://console.anthropic.com/settings/keys", [], "a project-scoped key"),
    ("HF_TOKEN", "Pulling gated model weights and datasets.",
     "https://huggingface.co/settings/tokens", [], "read-only"),
    ("GITHUB_TOKEN", "Searching code and issues past the anonymous rate limit.",
     "https://github.com/settings/tokens", [], "public_repo read only — no write scopes"),
]


def cmd_init(args: argparse.Namespace) -> int:
    """Probe the machine, write the secrets template, and report what is blocking.

    Deliberately does three things and no more. It never asks for a secret value, never writes
    one, and never reads `.env` — the agent writes the *names* and the user fills the values
    through a channel the agent does not observe. That is the only measure here that is
    structural rather than a mitigation, so it is the one the design leans on.
    """
    from reagent.contracts.environment import (
        ComputeKind,
        ComputeTarget,
        DownloadPolicy,
        Onboarding,
        SecretSpec,
        SecretVault,
        StorageMount,
        StoragePlan,
        StorageTier,
        probe_free_gb,
        probe_resources,
    )

    repo = Path.cwd()
    gitignore = (repo / ".gitignore").read_text(encoding="utf-8") if (
        repo / ".gitignore").is_file() else ""

    vault = SecretVault(
        specs=[
            SecretSpec(name=n, purpose=p, obtain_from=o, required_for=r, scope_note=s,
                       optional=True)
            for n, p, o, r, s in _DEFAULT_SECRETS
        ],
        gitignored=".env" in gitignore,
        agent_read_denied=args.deny_read,
    )

    hot = args.hot or ("C:/Temp" if Path("C:/Temp").is_dir() else str(repo / ".scratch"))
    mounts = [
        StorageMount(path=hot, tier=StorageTier.HOT, free_gb=probe_free_gb(hot),
                     network_backed=False, note="scratch and anything in a compute loop"),
        StorageMount(path=str(repo), tier=StorageTier.WORKING, free_gb=probe_free_gb(str(repo)),
                     network_backed=False, note="the repo and current artifacts"),
    ]
    if args.cold:
        mounts.append(StorageMount(
            path=args.cold, tier=StorageTier.COLD, free_gb=probe_free_gb(args.cold),
            network_backed=args.cold_is_network,
            note="archive and large inputs read occasionally"))

    onboarding = Onboarding(
        vault=vault,
        storage=StoragePlan(mounts=mounts, lazy_fetch=True),
        resources=probe_resources(hot),
        downloads=DownloadPolicy(destination_tier=StorageTier.COLD if args.cold
                                 else StorageTier.WORKING),
        compute=[ComputeTarget(name="local", kind=ComputeKind.LOCAL,
                               cpus=os.cpu_count(), verified=True)],
        problem_spec_path=args.problem,
        data_refs=list(args.data or []),
    )

    tpl = repo / vault.template_path
    if tpl.exists() and not args.force:
        print(f"  note  {vault.template_path} exists; not overwriting (use --force)")
    else:
        tpl.write_text(vault.template(), encoding="utf-8", newline="")
        _ok(f"wrote {vault.template_path} — {len(vault.specs)} names, no values")

    print()
    print(onboarding.summary())
    print()
    print("Next, in this order:")
    print(f"  1. cp {vault.template_path} .env   and fill in only what you need")
    print("     The agent wrote the names. Do not paste a value into the chat — it would enter")
    print("     the agent's context, and a credential in a transcript has to be rotated.")
    for flow in onboarding.auth_flows:
        print(f"  2. {flow.instruction}")
    if not onboarding.problem_spec_path:
        print("  3. reagent problem new --out reports/<run>/problem.json")
    if not onboarding.data_refs:
        print("  4. declare training and test data with --data, or harvest it in Stage 1")

    blocking = onboarding.blocking()
    if blocking:
        print()
        _err(f"not ready: {len(blocking)} blocking item(s)")
        return 1 if args.strict else 0
    print()
    _ok("ready to start")
    return 0


def cmd_verify_pool(args: argparse.Namespace) -> int:
    """How large a candidate pool a verifier of measured soundness can support.

    Exists because the instinct — generate many, the filter sorts it out — is measurably
    wrong: selection saturates long before coverage does, and the false-positive rate rises
    with N because difficulty is bimodal.
    """
    from reagent.contracts.verification import VerifierCalibration

    cal = VerifierCalibration(
        verifier=args.verifier,
        n_true_claims=args.true_claims, n_true_admitted=args.true_admitted,
        n_false_claims=args.false_claims, n_false_admitted=args.false_admitted,
    )
    print(cal.summary())
    for cost in (1.0, 2.0, 4.0, 10.0):
        k = cal.optimal_pool_size(cost)
        shown = "unbounded (scale on budget)" if k is None else str(k)
        print(f"  false-positive cost {cost:>5.1f}x -> pool guide {shown}")
    problems = cal.problems()
    for p in problems:
        _err(p) if args.strict else print(f"  warn  {p}")
    if cal.soundness is not None and cal.soundness >= 1.0:
        print(
            "  note  soundness measured at exactly 1.0. Treat with suspicion — it usually "
            "means too few or too-easy falsehoods were injected, not that none get through."
        )
    print("PASS" if not (problems and args.strict) else f"FAIL ({len(problems)} problems)")
    return 1 if (problems and args.strict) else 0


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
    """Exit 0 only when a named proposal is ACCEPTED — this is the gate a skill checks."""
    ledger = DecisionLedger(Path(args.ledger))
    if args.proposal_id:
        v = ledger.verdict_for(args.proposal_id)
        print(f"{args.proposal_id}: {v.value if v else 'pending — no verdict recorded'}")
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
    rn = rp.add_parser("new", help="scaffold a report skeleton (intentionally invalid until edited)")
    rn.add_argument("--stage", required=True)
    rn.add_argument("--run-id", required=True)
    rn.add_argument("--title", default=None)
    rn.add_argument("--owner", default=None)
    rn.set_defaults(func=cmd_report_new)
    rr = rp.add_parser("render", help="render a report to self-contained HTML")
    rr.add_argument("path")
    rr.add_argument("-o", "--out", default=None)
    rr.set_defaults(func=cmd_report_render)

    # axes — derive the search axes from the target, then check they were worked
    ax = sub.add_parser(
        "axes",
        help="property checklist, axis derivation, and per-axis exhaustion status",
    ).add_subparsers(dest="sub", required=True)
    ac = ax.add_parser("checklist", help="the property checklist for a domain, with questions")
    ac.add_argument("--domain", default="structural_biology")
    ac.set_defaults(func=cmd_axes_checklist)
    ad = ax.add_parser("derive", help="check a report's axis derivation against the checklist")
    ad.add_argument("--report", required=True)
    ad.add_argument("--strict", action="store_true")
    ad.set_defaults(func=cmd_axes_derive)
    asw = ax.add_parser("sweep-status", help="per-axis discovery curves, states, and open leads")
    asw.add_argument("--report", required=True)
    asw.add_argument("--strict", action="store_true")
    asw.set_defaults(func=cmd_axes_sweep_status)

    # init — the front door. Probes the machine, writes the secrets TEMPLATE, and says what
    # is blocking. Never asks for, writes, or reads a secret value.
    ini = sub.add_parser(
        "init",
        help="set up this environment: probe resources, write .env.template, report what blocks",
    )
    ini.add_argument("--hot", default=None,
                     help="fast local scratch path (default C:/Temp or ./.scratch)")
    ini.add_argument("--cold", default=None,
                     help="archive path for large or finished data, e.g. O:/rclone-offload")
    ini.add_argument("--cold-is-network", action="store_true",
                     help="mark cold storage as network-backed, so nothing hot is placed there")
    ini.add_argument("--problem", default=None, help="path to a ProblemSpec JSON")
    ini.add_argument("--data", action="append", default=None,
                     help="a training/test dataset id or path; repeatable")
    ini.add_argument("--deny-read", action="store_true",
                     help="assert the agent's tool permissions deny reading .env")
    ini.add_argument("--force", action="store_true", help="overwrite .env.template")
    ini.add_argument("--strict", action="store_true", help="exit non-zero if not ready")
    ini.set_defaults(func=cmd_init)

    # verify — the highest-return component, so it gets its own accounting
    vf = sub.add_parser(
        "verify", help="verifier calibration and what it implies about pool size"
    ).add_subparsers(dest="sub", required=True)
    vp = vf.add_parser(
        "pool", help="how many candidates a verifier of this soundness can support"
    )
    vp.add_argument("--verifier", default="verifier")
    vp.add_argument("--true-claims", type=int, required=True)
    vp.add_argument("--true-admitted", type=int, required=True)
    vp.add_argument("--false-claims", type=int, required=True,
                    help="injected falsehoods; zero means soundness is unmeasured")
    vp.add_argument("--false-admitted", type=int, required=True)
    vp.add_argument("--strict", action="store_true")
    vp.set_defaults(func=cmd_verify_pool)

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

    # `decide` and `decisions` are separate top-level commands rather than
    # `decide status`: argparse cannot tell a subcommand name from a positional
    # proposal id, so `decide P-001 accept` was being parsed as an unknown
    # subcommand and failing outright.
    d = sub.add_parser("decide", help="record a verdict on a proposal (append-only)")
    d.add_argument("proposal_id")
    d.add_argument("verdict", choices=["accept", "reject", "defer", "info"])
    d.add_argument("-m", "--message", default="", help="why. Future-you will want this.")
    d.add_argument("--by", default="human", help="who decided")
    d.add_argument("--ledger", default=str(LEDGER))
    d.set_defaults(func=cmd_decide)

    st = sub.add_parser(
        "decisions",
        help="show effective verdicts; exits 0 only if a named proposal is accepted",
    )
    st.add_argument("proposal_id", nargs="?", default=None)
    st.add_argument("--ledger", default=str(LEDGER))
    st.set_defaults(func=cmd_decide_status)

    # assets
    a = sub.add_parser("assets", help="vendored third-party files").add_subparsers(
        dest="sub", required=True)
    af = a.add_parser("fetch", help="download the JS the renderer inlines")
    af.add_argument("--force", action="store_true")
    af.set_defaults(func=cmd_assets_fetch)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    # A verdict with no reason is worthless six weeks later, so require one here
    # rather than accepting an empty string into the immutable ledger.
    if args.cmd == "decide" and not args.message.strip():
        print("a decision needs a rationale: pass -m 'why'")
        print("usage: reagent decide <proposal-id> accept|reject|defer|info -m 'why'")
        print("       reagent decisions [proposal-id]")
        return 2
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
