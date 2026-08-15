"""MCP tools for the interpretive and reasoning layers.

Separate module from ``tools.py`` because these answer a different class of question.
``tools.py`` answers *what does the graph contain*; these answer *what does it mean*
and *how did the agent get here*. Importing this module registers the tools via the
shared ``@tool`` decorator.

The reason these exist as tools rather than only as report sections: a reader's follow-up
question is almost never "show me the report again". It is "what does that mean", "why
did you choose that", or "what is this word" — and each of those should be one call.
"""

from __future__ import annotations

from pathlib import Path

from reagent.contracts import ModelReport
from reagent.mcp.tools import STR, _obj, tool


@tool(
    "explain_finding",
    "Explain what a finding means: the mechanism behind it, a version written for each "
    "kind of reader including a non-specialist, and what decision it changes downstream. "
    "Use when a claim is understood but its significance is not, or when asked to "
    "explain something for a layperson.",
    _obj({"path": {**STR, "description": "Report path from report_list"},
          "finding_id": {**STR, "description": "e.g. F-PROMISC-01. Omit to list what is available."},
          "audience": {"type": "string",
                       "enum": ["layperson", "medicinal_chemist", "structural_biologist",
                                "ml_practitioner", "clinician", "all"],
                       "description": "Which register to return. Default all."}},
         ["path"]),
)
def explain_finding(path: str, finding_id: str | None = None, audience: str = "all") -> str:
    r = ModelReport.load(Path(path))
    if finding_id is None:
        lines = [f"{len(r.findings)} findings in {r.report_id}:"]
        for f in r.findings:
            mark = "interpreted" if f.interpretation else "NOT interpreted"
            lines.append(f"  {f.id} [{f.kind.value}] {mark} - {f.statement[:88]}")
        lines.append("")
        lines.append("Call again with a finding_id for the full explanation.")
        return "\n".join(lines)

    f = next((x for x in r.findings if x.id == finding_id), None)
    if f is None:
        return (
            f"No finding {finding_id!r} in {r.report_id}. "
            f"Available: {[x.id for x in r.findings]}"
        )
    if f.interpretation is None:
        return (
            f"{f.id} [{f.kind.value}, {f.confidence.value}]\n  {f.statement}\n\n"
            "This finding has NO interpretation, so the report does not say what it "
            "means or what it changes. Treat the statement as a bare fact and do not "
            "infer significance the report did not claim."
        )

    it = f.interpretation
    out = [f"{f.id} [{f.kind.value}, {f.confidence.value}]", f"  {f.statement}", ""]
    if it.mechanism:
        out += ["WHY IT IS SO", f"  {it.mechanism}", ""]

    wanted = None if audience == "all" else audience
    out.append("WHAT IT MEANS")
    shown = 0
    for aud, text in it.for_audience.items():
        if wanted and aud.value != wanted:
            continue
        out += [f"  [{aud.value}]", f"    {text}"]
        shown += 1
    if shown == 0:
        lay = next((t for a, t in it.for_audience.items() if a.value == "layperson"), None)
        out += [
            f"  (no {audience} register on this finding; showing the plain one)",
            f"    {lay}",
        ]
    out.append("")

    if it.analogy:
        out += ["ANALOGY", f"  {it.analogy}", ""]
    if it.caveat_for_reader:
        out += ["EASY TO MISREAD", f"  {it.caveat_for_reader}", ""]

    if it.implications:
        out.append("WHAT IT CHANGES DOWNSTREAM")
        for imp in it.implications:
            out += [
                f"  [{imp.for_stage}] {imp.strength.value}",
                f"    decision:  {imp.decision}",
                f"    direction: {imp.direction}",
                f"    if wrong:  {imp.if_wrong}",
            ]
        out.append("")
    else:
        out += [
            "This finding names no downstream implication, so on the report's own terms "
            "it changes nothing. Treat it as context, not as a reason to act.",
            "",
        ]

    gloss = r.effective_glossary()
    haystack = " ".join(it.for_audience.values()).lower()
    used = [t for t in gloss.terms if t.term.lower() in haystack]
    if used:
        out.append("TERMS USED")
        for t in used[:6]:
            out.append(f"  {t.term}: {t.plain}")
        out.append("")

    steps = r.reasoning.for_finding(f.id)
    if steps:
        out.append(
            f"Produced by decision(s) {[s.id for s in steps]} - call `trace_decision` "
            "to see the options weighed and the sources used."
        )
    return "\n".join(out)


@tool(
    "trace_decision",
    "Show how the agent decided: the question it faced, the alternatives it weighed, why "
    "it rejected each one, what informed the judgement, and what the decision produced. "
    "Use to audit the reasoning rather than only the conclusions.",
    _obj({"path": {**STR, "description": "Report path from report_list"},
          "step_id": {**STR, "description": "e.g. R-02. Omit for the whole trace."},
          "finding_id": {**STR, "description": "Alternatively, trace backwards from a finding."}},
         ["path"]),
)
def trace_decision(
    path: str, step_id: str | None = None, finding_id: str | None = None
) -> str:
    r = ModelReport.load(Path(path))
    tr = r.reasoning
    if not tr.steps:
        return (
            f"{r.report_id} records no reasoning steps, so how it reached its conclusions "
            "is not documented. The findings may still be cited, but the choices behind "
            "them are not auditable."
        )

    if finding_id:
        steps = tr.for_finding(finding_id)
        if not steps:
            traced = sorted({x for s in tr.steps for x in s.produced_findings})
            return (
                f"No recorded decision produced {finding_id}. That is not necessarily "
                "wrong - many findings are direct readings rather than judgement calls. "
                f"Findings with a recorded decision: {traced}"
            )
    elif step_id:
        steps = [s for s in tr.steps if s.id == step_id]
        if not steps:
            return f"No step {step_id!r}. Available: {[s.id for s in tr.steps]}"
    else:
        steps = tr.steps

    out = [tr.summary(), ""]
    for s in steps:
        flags = []
        if s.no_alternative_because:
            flags.append("DEFAULT, not a choice")
        if s.superseded_by:
            flags.append(f"later reversed by {s.superseded_by}")
        header = f"{s.id} [{s.kind.value}]"
        if flags:
            header += "  " + " | ".join(flags)
        out += [
            header,
            f"  question: {s.question}",
            f"  chose:    {s.chose}",
            f"  because:  {s.because}",
            f"  confidence at the time: {s.confidence_then.value}",
        ]
        if s.no_alternative_because:
            out.append(f"  no alternative because: {s.no_alternative_because}")
        for o in s.rejected:
            line = f"  rejected {o.name!r}: {o.rejected_because}"
            if o.cost:
                line += f"  (cost: {o.cost})"
            out.append(line)
        if s.informed_by:
            out.append("  informed by:")
            for ev in s.informed_by:
                line = f"    [{ev.source_type.value}] {ev.locator}"
                if ev.title:
                    line += f" - {ev.title}"
                out.append(line)
        else:
            out.append("  informed by: nothing cited for this judgement")
        if s.revisit_if:
            out.append(f"  revisit if: {s.revisit_if}")
        if s.produced_findings:
            out.append(f"  produced: {s.produced_findings}")
        out.append("")

    if not step_id and not finding_id:
        if tr.open_decisions:
            out.append("Deliberately still open:")
            out += [f"  - {o}" for o in tr.open_decisions]
            out.append("")
        srcs = tr.all_sources()
        out.append(f"Everything that informed the reasoning ({len(srcs)} sources):")
        out += [f"  {s}" for s in srcs]
    return "\n".join(out)


@tool(
    "glossary",
    "Look up a term, or list every term this report defines, in plain language with why "
    "it matters here. Use when a report uses a word the reader may not know.",
    _obj({"path": {**STR, "description": "Report path from report_list"},
          "term": {**STR, "description": "Term to look up. Omit to list all."}},
         ["path"]),
)
def glossary(path: str, term: str | None = None) -> str:
    r = ModelReport.load(Path(path))
    g = r.effective_glossary()
    if not g.terms:
        return (
            f"{r.report_id} defines no glossary terms. Any jargon in it is therefore "
            "unexplained, which `reagent report validate --strict` would flag."
        )
    if term:
        t = g.get(term)
        if t is None:
            return f"No entry for {term!r}. Defined: {sorted(x.term for x in g.terms)}"
        out = [t.term + (f"  (also: {', '.join(t.aliases)})" if t.aliases else "")]
        out += [f"  {t.plain}", f"  Why it matters here: {t.why_it_matters}"]
        if t.analogy:
            out.append(f"  Like this: {t.analogy}")
        return "\n".join(out)

    out = [f"{len(g.terms)} terms defined in {r.report_id}:"]
    for t in sorted(g.terms, key=lambda x: x.term.lower()):
        out.append(f"  {t.term}: {t.plain}")
    return "\n".join(out)


@tool(
    "plain_summary",
    "Give the report's outcome in plain language with no undefined jargon, plus what it "
    "asks of each downstream stage and what it could not do. The best first call on an "
    "unfamiliar report, and the right one when a non-specialist needs the result.",
    _obj({"path": {**STR, "description": "Report path from report_list"}}, ["path"]),
)
def plain_summary(path: str) -> str:
    r = ModelReport.load(Path(path))
    out = [f"{r.title}  [{r.stage.value}]", ""]
    if r.plain_summary:
        out += [r.plain_summary, ""]
    else:
        out += [
            "This report has no plain-language summary, so it offers no non-specialist "
            "entry point. The technical summary follows; relay it with care.",
            "",
            r.executive_summary,
            "",
        ]

    if by_stage := r.implications_by_stage():
        out.append("What it asks of the next stages:")
        for stage, items in sorted(by_stage.items()):
            out.append(f"  {stage}:")
            for fid, dec in items:
                out.append(f"    - {dec}  ({fid})")
        out.append("")

    if r.limitations:
        out.append("What it could not do:")
        out += [f"  - {x}" for x in r.limitations]
        out.append("")

    if probs := r.plain_language_problems():
        out.append("Readability problems the validator flags:")
        out += [f"  - {p}" for p in probs]
        out.append("")

    if cov := r.audience_coverage():
        out.append(
            "Audience registers present: "
            + ", ".join(f"{k} ({v} findings)" for k, v in cov.items())
        )
    return "\n".join(out)
