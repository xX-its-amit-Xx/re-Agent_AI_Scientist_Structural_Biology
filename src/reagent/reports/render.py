"""Render a Model Report to a self-contained HTML page.

The goal is a page a judge or a teammate can read cold and come away knowing what
was done, what was found, how strongly it is supported, and what is still unknown —
without opening a JSON file or a terminal.

Three things drive the design:

**Evidence is inline, not in a bibliography.** Every finding shows its own
citations, source types, and confidence badge right there. Making a reader scroll to
check a claim means they will not check it, and unchecked claims are the failure
mode this whole project is built against.

**Figures carry their question and takeaway.** The `Visualization` contract already
requires both, so the renderer prints them as the figure's caption. A reader should
be able to tell what a figure is *for* before deciding whether to study it.

**Negative results and limitations get equal billing.** They are sorted alongside
positive findings rather than exiled to a footer, because in pipeline design the
refuted approaches are usually the more valuable half of the report.

Interactive figures are embedded as `<iframe srcdoc>` so the whole page stays one
self-contained file with no external requests — required by the publish target.
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any

from reagent.contracts import (
    Confidence,
    Finding,
    FindingKind,
    MethodStep,
    ModelReport,
    SourceType,
    VizMedium,
)

CONF_ORDER = {
    Confidence.ESTABLISHED: 0,
    Confidence.SUPPORTED: 1,
    Confidence.TENTATIVE: 2,
    Confidence.SPECULATIVE: 3,
}

CONF_COLOR = {
    Confidence.ESTABLISHED: "#1a7f4f",
    Confidence.SUPPORTED: "#2f6fb0",
    Confidence.TENTATIVE: "#b07d2f",
    Confidence.SPECULATIVE: "#8a5cb0",
}

KIND_LABEL = {
    FindingKind.OBSERVATION: "observation",
    FindingKind.HYPOTHESIS: "hypothesis",
    FindingKind.PRIOR: "prior",
    FindingKind.CONSTRAINT: "constraint",
    FindingKind.BENCHMARK: "benchmark",
    FindingKind.NEGATIVE: "negative result",
    FindingKind.DESIGN_CHOICE: "design choice",
    FindingKind.RISK: "risk",
}

#: Reading order for findings. Constraints first because they bound everything
#: else; negative results high because they are the most easily overlooked and the
#: most expensive to rediscover.
KIND_ORDER = [
    FindingKind.CONSTRAINT,
    FindingKind.BENCHMARK,
    FindingKind.OBSERVATION,
    FindingKind.NEGATIVE,
    FindingKind.PRIOR,
    FindingKind.DESIGN_CHOICE,
    FindingKind.HYPOTHESIS,
    FindingKind.RISK,
]


def _e(s: Any) -> str:
    return html.escape(str(s), quote=True)


def _locator_url(locator: str) -> str | None:
    """Best-effort resolvable link. Returns None rather than guessing wrongly."""
    lo = locator.strip()
    low = lo.lower()
    if low.startswith(("http://", "https://")):
        return lo
    for prefix, tmpl in (
        ("doi:", "https://doi.org/{}"),
        ("pmid:", "https://pubmed.ncbi.nlm.nih.gov/{}/"),
        ("pmc:", "https://www.ncbi.nlm.nih.gov/pmc/articles/{}/"),
        ("pdb:", "https://www.rcsb.org/structure/{}"),
        ("uniprot:", "https://www.uniprot.org/uniprotkb/{}/entry"),
        ("chembl:", "https://www.ebi.ac.uk/chembl/compound_report_card/{}/"),
        ("nct:", "https://clinicaltrials.gov/study/{}"),
        ("arxiv:", "https://arxiv.org/abs/{}"),
        ("zenodo:", "https://doi.org/{}"),
    ):
        if low.startswith(prefix):
            # Strip any line-anchor suffix (#L45-L52) — it is for humans, not the URL.
            acc = lo[len(prefix):].split("#", 1)[0]
            return tmpl.format(acc) if acc else None
    return None


def _evidence_html(f: Finding) -> str:
    if not f.evidence:
        return '<div class="ev none">No citation — asserted by the agent.</div>'
    parts = []
    for ev in f.evidence:
        url = _locator_url(ev.locator)
        loc = _e(ev.locator)
        link = f'<a href="{_e(url)}" target="_blank" rel="noopener">{loc}</a>' if url else f"<code>{loc}</code>"
        grey = " grey" if ev.source_type.is_grey else ""
        ungrounded = " ungrounded" if not ev.source_type.is_grounded else ""
        bits = [f'<span class="stype{grey}{ungrounded}">{_e(ev.source_type.value)}</span>', link]
        if ev.title:
            bits.append(f'<span class="evtitle">{_e(ev.title)}</span>')
        if ev.year:
            bits.append(f'<span class="evyear">{ev.year}</span>')
        if ev.source_domain:
            bits.append(f'<span class="evdomain">from {_e(ev.source_domain)}</span>')
        row = " ".join(bits)
        if ev.excerpt:
            row += f'<blockquote>{_e(ev.excerpt)}</blockquote>'
        parts.append(f"<li>{row}</li>")
    return f'<ul class="ev">{"".join(parts)}</ul>'


AUDIENCE_LABEL = {
    "layperson": "In plain terms",
    "medicinal_chemist": "For a medicinal chemist",
    "structural_biologist": "For a structural biologist",
    "ml_practitioner": "For a modeller",
    "clinician": "For a clinician",
}

#: Reading order for audience registers: plain first, because the point of the layered
#: view is that the non-specialist path is the default one.
AUDIENCE_ORDER = ["layperson", "medicinal_chemist", "structural_biologist",
                  "ml_practitioner", "clinician"]

STRENGTH_COLOR = {
    "decisive": "#8a3d2f", "strong": "#b0562f",
    "suggestive": "#2f6fb0", "weak": "#5c5c5c",
}


def _link_glossary(text: str, terms: dict[str, Any]) -> str:
    """Wrap known glossary terms in a hoverable span.

    Longest term first so "ligand-binding domain" wins over "domain", and each term is
    linked only on its first appearance — marking every instance turns the paragraph
    into a field of underlines and stops being helpful.
    """
    escaped = _e(text)
    used: set[str] = set()
    for term in sorted(terms, key=len, reverse=True):
        if term in used:
            continue
        pattern = re.compile(rf"\b({re.escape(_e(term))})\b", re.I)
        g = terms[term]
        tip = _e(g.plain + (f" — {g.why_it_matters}" if g.why_it_matters else ""))

        def repl(m: re.Match, _tip=tip) -> str:
            return f'<span class="gl" data-tip="{_tip}">{m.group(1)}</span>'

        new, n = pattern.subn(repl, escaped, count=1)
        if n:
            escaped = new
            used.add(term)
    return escaped


def _interpretation_html(f: Finding, terms: dict[str, Any]) -> str:
    it = f.interpretation
    if it is None:
        return (
            '<div class="nointerp">Not interpreted — this finding records a fact but '
            "does not say what it means or what it changes.</div>"
        )

    blocks = []
    for key in AUDIENCE_ORDER:
        aud = next((a for a in it.for_audience if a.value == key), None)
        if aud is None:
            continue
        text = it.for_audience[aud]
        # Link the glossary in EVERY register, not only the plain one. The plain
        # register is written to avoid jargon, so it has little to link; the expert
        # registers are exactly where a non-specialist reading across needs the
        # definitions, which is the point of having the toggle at all.
        body = _link_glossary(text, terms)
        blocks.append(
            f'<div class="aud" data-aud="{key}">'
            f'<span class="audlab">{_e(AUDIENCE_LABEL.get(key, key))}</span>'
            f"<p>{body}</p></div>"
        )

    mech = ""
    if it.mechanism:
        mech = (
            '<div class="mech"><span class="audlab">Why</span>'
            f"<p>{_link_glossary(it.mechanism, terms)}</p></div>"
        )
    analogy = ""
    if it.analogy:
        analogy = f'<div class="analogy"><b>Like this:</b> {_e(it.analogy)}</div>'
    caveat = ""
    if it.caveat_for_reader:
        caveat = (
            '<div class="readercav"><b>Easy to misread:</b> '
            f"{_e(it.caveat_for_reader)}</div>"
        )

    imps = ""
    if it.implications:
        rows = []
        for imp in it.implications:
            col = STRENGTH_COLOR.get(imp.strength.value, "#5c5c5c")
            rows.append(
                '<li class="imp">'
                f'<span class="istage">{_e(imp.for_stage)}</span>'
                f'<span class="istr" style="--c:{col}">{_e(imp.strength.value)}</span>'
                f'<div class="idec">{_e(imp.decision)}</div>'
                f'<div class="idir">{_e(imp.direction)}</div>'
                f'<div class="iwrong"><b>If this is wrong:</b> {_e(imp.if_wrong)}</div>'
                "</li>"
            )
        imps = (
            '<div class="imps"><span class="audlab">What it changes downstream</span>'
            f'<ul>{"".join(rows)}</ul></div>'
        )

    return f'<div class="interp">{mech}{"".join(blocks)}{analogy}{caveat}{imps}</div>'


#: Kind -> CSS class on the disclosure, so the left rule carries the question type.
_FU_CLASS = {
    "what_is": "fu-what-is", "why": "fu-why", "how_known": "fu-how-known",
    "how_measured": "fu-how-known", "so_what": "fu-so-what",
    "what_if_wrong": "fu-what-if", "alternative": "fu-alt", "objection": "fu-objection",
}


def _followup_html(node: Any, terms: dict[str, Any], base_id: str, level: int = 1) -> str:
    """One disclosure and its descendants.

    Children are nested *inside* ``.fu-answer`` rather than as siblings of it: a screen
    reader announces a sibling as a peer of the answer instead of as a sub-question, and
    the indent that carries the hierarchy is lost.
    """
    kids = node.sorted_children()
    inner = "".join(
        _followup_html(k, terms, f"{base_id}-{i}", level + 1)
        for i, k in enumerate(kids, 1)
    )
    count = (
        f' <span class="fu-count">{len(kids)} more</span>' if kids else ""
    )
    cls = _FU_CLASS.get(node.kind.value, "fu-why")
    return (
        f'<details class="fu {cls}" id="{_e(base_id)}">'
        f"<summary>{_e(node.question)}{count}</summary>"
        f'<div class="fu-answer"><p>{_link_glossary(node.answer, terms)}</p>{inner}</div>'
        "</details>"
    )


def _followup_tree_html(tree: Any, terms: dict[str, Any], prefix: str) -> str:
    if tree is None:
        return ""
    branches = "".join(
        _followup_html(b, terms, f"fu-{prefix}-{i}", 1)
        for i, b in enumerate(tree.sorted_branches(), 1)
    )
    return (
        '<div class="fu-tree">'
        f'<p class="fu-lede">{_link_glossary(tree.lede, terms)}</p>'
        f"{branches}</div>"
    )


def _followup_index_html(report: ModelReport, terms: dict[str, Any]) -> str:
    """Flat, visually hidden copy of every question and answer.

    Browsers do not search inside a closed ``<details>``, so without this a reader using
    find-in-page cannot reach a definition that exists one click down. ``aria-hidden``
    because a screen reader already reaches the content through the tree, and announcing
    all of it twice is worse than not having the index.
    """
    rows: list[str] = []
    trees = [("report", report.follow_ups)] + [
        (f.id, f.follow_ups) for f in report.findings if f.follow_ups
    ]
    for owner, tree in trees:
        if tree is None:
            continue
        for branch in tree.sorted_branches():
            for _level, node in branch.walk():
                rows.append(
                    f"<p>{_e(owner)}: {_e(node.question)} {_e(node.answer)}</p>"
                )
    if not rows:
        return ""
    return f'<div class="fu-index" aria-hidden="true">{"".join(rows)}</div>'


def _finding_html(f: Finding, terms: dict[str, Any]) -> str:
    color = CONF_COLOR[f.confidence]
    data = ""
    if f.data:
        data = (
            '<details class="data"><summary>structured payload</summary>'
            f'<pre>{_e(json.dumps(f.data, indent=2, default=str))}</pre></details>'
        )
    nodes = ""
    if f.kg_nodes:
        nodes = (
            '<div class="kgn">graph nodes: '
            + ", ".join(f"<code>{_e(n)}</code>" for n in f.kg_nodes)
            + "</div>"
        )
    tags = "".join(f'<span class="tag">{_e(t)}</span>' for t in f.tags)
    neg = " negative" if f.kind is FindingKind.NEGATIVE else ""
    stages = ""
    if f.interpretation and f.interpretation.implications:
        stages = "".join(
            f'<span class="chip">{_e(s)}</span>'
            for s in f.interpretation.stages_affected()
        )
    return f"""
<article class="finding{neg}">
  <header>
    <span class="fid">{_e(f.id)}</span>
    <span class="kind">{_e(KIND_LABEL.get(f.kind, f.kind.value))}</span>
    <span class="conf" style="--c:{color}">{_e(f.confidence.value)}</span>
    {tags}{stages}
  </header>
  <p class="stmt">{_e(f.statement)}</p>
  {_interpretation_html(f, terms)}
  {_followup_tree_html(f.follow_ups, terms, f.id)}
  <details class="ev-wrap"><summary>evidence</summary>{_evidence_html(f)}{nodes}{data}</details>
</article>"""


def _viz_html(v: Any, repo_root: Path) -> str:
    """Embed a figure. Interactive HTML goes in an iframe srcdoc to stay self-contained."""
    body = ""
    p = repo_root / v.path
    if v.medium is VizMedium.HTML_SELF_CONTAINED and p.is_file():
        inner = p.read_text(encoding="utf-8")
        body = f'<iframe srcdoc="{html.escape(inner, quote=True)}" loading="lazy"></iframe>'
    elif v.medium is VizMedium.SVG and p.is_file():
        body = f'<div class="svgwrap">{p.read_text(encoding="utf-8")}</div>'
    elif v.medium is VizMedium.PNG and p.is_file():
        import base64

        b64 = base64.b64encode(p.read_bytes()).decode()
        body = f'<img src="data:image/png;base64,{b64}" alt="{_e(v.alt_text)}">'
    elif v.medium is VizMedium.MERMAID and p.is_file():
        body = f'<pre class="mermaid">{_e(p.read_text(encoding="utf-8"))}</pre>'
    elif v.medium is VizMedium.MARKDOWN_TABLE and p.is_file():
        body = f'<pre class="mdtable">{_e(p.read_text(encoding="utf-8"))}</pre>'
    else:
        body = (
            f'<div class="missing">Figure file not found at <code>{_e(v.path)}</code>. '
            "The report references it but it was not produced or not committed.</div>"
        )

    enc = "".join(
        f"<tr><td>{_e(k)}</td><td>{_e(val)}</td></tr>" for k, val in sorted(v.encoding.items())
    )
    legend = ""
    for cm in v.color_maps:
        swatches = "".join(
            f'<span class="sw"><i style="background:{_e(c)}"></i>{_e(name)}</span>'
            for name, c in cm.mapping.items()
        )
        second = (
            f' <span class="second">+ {_e(cm.secondary_channel)} as a redundant channel</span>'
            if cm.secondary_channel else ""
        )
        legend += f'<div class="legend"><b>{_e(cm.channel)}</b> = {_e(cm.data_field)}{second}<div>{swatches}</div></div>'

    return f"""
<figure class="viz" id="{_e(v.id)}">
  <figcaption>
    <div class="q">{_e(v.question)}</div>
    <div class="t">{_e(v.takeaway)}</div>
  </figcaption>
  {body}
  {legend}
  <details class="meta">
    <summary>how to read this figure</summary>
    <p class="alt">{_e(v.alt_text)}</p>
    <table class="enc"><thead><tr><th>visual channel</th><th>data field</th></tr></thead>
      <tbody>{enc}</tbody></table>
    <p class="src">Drawn from {", ".join(f"<code>{_e(s)}</code>" for s in v.reads_from)}
      · {v.n_elements or "?"} elements · <code>{_e(v.path)}</code></p>
  </details>
</figure>"""


def render(report: ModelReport, out_path: Path, repo_root: Path | None = None) -> Path:
    """Write the report as one self-contained HTML file."""
    repo_root = Path(repo_root or Path.cwd())

    findings = sorted(
        report.findings,
        key=lambda f: (
            KIND_ORDER.index(f.kind) if f.kind in KIND_ORDER else 99,
            CONF_ORDER[f.confidence],
            f.id,
        ),
    )
    gloss = report.effective_glossary()
    terms = {t.term: t for t in gloss.terms}
    findings_html = "".join(_finding_html(f, terms) for f in findings) or (
        '<p class="empty">No findings. See limitations below for why.</p>'
    )

    plain_html = ""
    if report.plain_summary:
        plain_html = (
            '<section class="plainbox"><h3>What this means, without the jargon</h3>'
            f"<p>{_link_glossary(report.plain_summary, terms)}</p>"
            # The report-level tree sits with the plain summary rather than at the end,
            # because the reader who needs it is the reader who is still here.
            f"{_followup_tree_html(report.follow_ups, terms, 'report')}</section>"
        )

    glossary_html = ""
    if gloss.terms:
        rows = []
        for t in sorted(gloss.terms, key=lambda x: x.term.lower()):
            extra = f'<div class="gan">{_e(t.analogy)}</div>' if t.analogy else ""
            rows.append(
                f'<div class="gterm"><b>{_e(t.term)}</b>'
                + (f' <span class="k">({", ".join(_e(a) for a in t.aliases)})</span>'
                   if t.aliases else "")
                + f"<div>{_e(t.plain)}</div>"
                f'<div class="k">Why it matters here: {_e(t.why_it_matters)}</div>'
                f"{extra}</div>"
            )
        glossary_html = (
            f'<h2>Glossary <span class="k">({len(gloss.terms)} terms)</span></h2>'
            f'<div class="glossary">{"".join(rows)}</div>'
        )

    # How the agent decided. Distinct from "what was run" (methods) and from
    # "what was concluded" (findings): this is the audit trail for the judgement.
    reasoning_html = ""
    trace = report.reasoning
    if trace.steps:
        blocks = []
        for st in trace.steps:
            opts = ""
            if st.rejected:
                opts = "".join(
                    f'<li><b>{_e(o.name)}</b> — rejected: {_e(o.rejected_because)}'
                    + (f' <span class="k">(cost: {_e(o.cost)})</span>' if o.cost else "")
                    + "</li>"
                    for o in st.rejected
                )
                opts = f'<div class="rej"><span class="audlab">Considered and rejected</span><ul>{opts}</ul></div>'
            srcs = ""
            if st.informed_by:
                items = []
                for ev in st.informed_by:
                    url = _locator_url(ev.locator)
                    loc = _e(ev.locator)
                    link = (f'<a href="{_e(url)}" target="_blank" rel="noopener">{loc}</a>'
                            if url else f"<code>{loc}</code>")
                    items.append(
                        f'<li><span class="stype">{_e(ev.source_type.value)}</span> {link}'
                        + (f" — {_e(ev.title)}" if ev.title else "") + "</li>"
                    )
                srcs = (
                    '<div class="rsrc"><span class="audlab">What informed this</span>'
                    f'<ul>{"".join(items)}</ul></div>'
                )
            else:
                srcs = ('<div class="rsrc k">No source cited for this judgement.</div>')
            produced = ""
            if st.produced_findings:
                produced = (
                    '<div class="k">Led to: '
                    + ", ".join(f"<code>{_e(x)}</code>" for x in st.produced_findings)
                    + "</div>"
                )
            flags = ""
            if st.no_alternative_because:
                flags += ('<span class="dflt">default, not a choice</span>')
            if st.superseded_by:
                flags += f'<span class="rev">later reversed by {_e(st.superseded_by)}</span>'
            revisit = (
                f'<div class="k"><b>Revisit if:</b> {_e(st.revisit_if)}</div>'
                if st.revisit_if else ""
            )
            blocks.append(f"""
<article class="rstep">
  <header><span class="fid">{_e(st.id)}</span>
    <span class="kind">{_e(st.kind.value)}</span>
    <span class="conf" style="--c:{CONF_COLOR[st.confidence_then]}">{_e(st.confidence_then.value)} at the time</span>
    {flags}</header>
  <p class="rq">{_e(st.question)}</p>
  <div class="rchose"><b>Chose:</b> {_e(st.chose)}</div>
  <p class="rwhy">{_e(st.because)}</p>
  {opts}{srcs}{produced}{revisit}
</article>""")

        gaps = report.reasoning_gaps()
        gap_html = ""
        if gaps:
            gap_html = '<div class="warn">' + "<br>".join(_e(g) for g in gaps) + "</div>"
        src_list = trace.all_sources()
        srcs_html = ""
        if src_list:
            items = []
            for loc in src_list:
                url = _locator_url(loc)
                link = (
                    f'<a href="{_e(url)}" target="_blank" rel="noopener">{_e(loc)}</a>'
                    if url else f"<code>{_e(loc)}</code>"
                )
                items.append(f"<li>{link}</li>")
            srcs_html = (
                f'<h3>Everything that informed the reasoning <span class="k">'
                f'({len(src_list)} sources)</span></h3>'
                f'<ul class="allsrc">{"".join(items)}</ul>'
            )
        reasoning_html = (
            "<h2>How this was decided</h2>"
            '<div class="meta-line">' + _e(trace.summary().replace("\n", " · ")) + "</div>"
            + gap_html
            + "".join(blocks)
            + ('<div class="opendec"><b>Deliberately still open:</b><ul>'
               + "".join(f"<li>{_e(o)}</li>" for o in trace.open_decisions)
               + "</ul></div>" if trace.open_decisions else "")
            + srcs_html
        )

    # What this report asks of each downstream stage — the section a stage owner
    # should read instead of the whole thing.
    asks_html = ""
    if by_stage := report.implications_by_stage():
        blocks = []
        for stage, items in sorted(by_stage.items()):
            lis = "".join(
                f"<li><code>{_e(fid)}</code> {_e(dec)}</li>" for fid, dec in items
            )
            blocks.append(f'<div class="ask"><b>{_e(stage)}</b><ul>{lis}</ul></div>')
        asks_html = (
            "<h2>What this asks of the next stages</h2>"
            f'<div class="asks">{"".join(blocks)}</div>'
        )

    viz_html = ""
    if report.visuals:
        viz_html = "".join(_viz_html(v, repo_root) for v in report.visuals.ordered())
    else:
        viz_html = (
            '<p class="empty">This stage produced no figures. That is a gap: a stage '
            "that cannot show its result cannot be checked.</p>"
        )

    metrics_html = "".join(
        f"<div class=\"metric\"><span class=\"mv\">{_e(v)}</span>"
        f"<span class=\"mk\">{_e(k.replace('_', ' '))}</span></div>"
        for k, v in report.metrics.items()
    )

    # Built with a helper rather than one nested f-string: nesting quotes and
    # backslashes inside an f-string only parses on Python 3.12+, and pyproject
    # supports 3.11.
    def _method_row(m: MethodStep) -> str:
        note = f'<div class="fn">{_e(m.failure_note)}</div>' if m.failure_note else ""
        cost = f"${m.cost_usd:.2f}" if m.cost_usd else "—"
        credits = f' <span class="cred">{_e(m.credits)}</span>' if m.credits else ""
        cls = "failed" if m.failed else ""
        return (
            f'<tr class="{cls}">'
            f"<td><code>{_e(m.skill)}</code></td><td>{_e(m.tool or '—')}</td>"
            f"<td>{_e(m.summary)}{note}</td>"
            f"<td>{m.n_calls}</td>"
            f"<td>{cost}{credits}</td></tr>"
        )

    methods_html = "".join(_method_row(m) for m in report.methods)

    def _bullets(items: list[str], empty: str) -> str:
        if not items:
            return f'<p class="empty">{_e(empty)}</p>'
        return "<ul>" + "".join(f"<li>{_e(i)}</li>" for i in items) + "</ul>"

    inputs_html = "".join(
        f"<li><span class=\"stype\">{_e(i.kind)}</span> <code>{_e(i.locator)}</code>"
        f"{f' — {_e(i.note)}' if i.note else ''}</li>"
        for i in report.inputs
    )

    handoff_html = '<p class="empty">No handoff recorded — the next stage has no contract to build against.</p>'
    if report.handoff:
        h = report.handoff
        badge = "ready" if h.ready else "NOT ready"
        handoff_html = f"""
      <div class="handoff {'ready' if h.ready else 'notready'}">
        <div class="hh">to <b>{_e(h.to_stage.value)}</b> · <span class="badge">{badge}</span></div>
        {('<h4>Recommended actions</h4>' + _bullets(h.recommended_actions, '')) if h.recommended_actions else ''}
        {('<h4>Blocking unknowns</h4>' + _bullets(h.blocking_unknowns, '')) if h.blocking_unknowns else ''}
        <details><summary>machine-readable payload</summary>
          <pre>{_e(json.dumps(h.payload, indent=2, default=str))}</pre></details>
      </div>"""

    gaps = report.visual_gaps()
    gaps_html = ""
    if gaps:
        gaps_html = (
            '<div class="warn">Missing characteristic figures for this stage: '
            + ", ".join(f"<code>{_e(g)}</code>" for g in gaps)
            + ". <code>reagent report validate --strict</code> would fail this.</div>"
        )

    n_by_conf = {c.value: sum(1 for f in report.findings if f.confidence is c) for c in Confidence}
    grey_only = sum(
        1 for f in report.findings
        if f.evidence and all(e.source_type.is_grey for e in f.evidence
                              if e.source_type.is_grounded)
        and any(e.source_type.is_grounded for e in f.evidence)
    )
    analogy_derived = sum(
        1 for f in report.findings
        if any(e.source_type is SourceType.ANALOGY for e in f.evidence)
    )

    doc = _TEMPLATE
    for key, val in {
        "__TITLE__": _e(report.title),
        "__STAGE__": _e(report.stage.value),
        "__RUNID__": _e(report.run_id),
        "__REPORTID__": _e(report.report_id),
        "__DATE__": report.created_utc.strftime("%Y-%m-%d %H:%M UTC"),
        "__MODEL__": _e(report.produced_by.model),
        "__OWNER__": _e(report.produced_by.human_owner or "unassigned"),
        "__SUMMARY__": _e(report.executive_summary),
        "__PLAIN__": plain_html,
        "__GLOSSARY__": glossary_html,
        "__FUINDEX__": _followup_index_html(report, terms),
        "__ASKS__": asks_html,
        "__REASONING__": reasoning_html,
        "__OBJECTIVE__": _e(report.objective),
        "__METRICS__": metrics_html or '<p class="empty">No headline metrics recorded.</p>',
        "__VIZ__": viz_html,
        "__VIZGAPS__": gaps_html,
        "__FINDINGS__": findings_html,
        "__NFINDINGS__": str(len(report.findings)),
        "__CONFMIX__": " · ".join(f"{v} {k}" for k, v in n_by_conf.items() if v),
        "__GREYONLY__": (
            f'<div class="note">{grey_only} finding(s) rest only on grey literature.</div>'
            if grey_only else ""
        ),
        "__ANALOGY__": (
            f'<div class="note">{analogy_derived} finding(s) derive from a cross-domain '
            "analogy and are capped at speculative by contract.</div>"
            if analogy_derived else ""
        ),
        "__METHODS__": methods_html or '<tr><td colspan="5" class="empty">No methods recorded.</td></tr>',
        "__COST__": f"${report.total_cost_usd():.2f}" if report.total_cost_usd() else "$0.00",
        "__INPUTS__": f"<ul class=\"inputs\">{inputs_html}</ul>" if inputs_html else '<p class="empty">No declared inputs.</p>',
        "__HANDOFF__": handoff_html,
        "__LIMITS__": _bullets(report.limitations, "None recorded — every real stage has some."),
        "__OPENQ__": _bullets(report.open_questions, "None recorded."),
    }.items():
        doc = doc.replace(key, val)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as fh:
        fh.write(doc)
    return out_path


_TEMPLATE = r"""<title>__TITLE__</title>
<style>
  :root {
    --bg:#fbfbfa; --panel:#fff; --ink:#1a1a1a; --muted:#5c5c5c; --line:#e2e2de;
    --accent:#0072B2; --warn:#b0562f; --neg:#8a3d2f; --code:#f4f4f2;
  }
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) {
      --bg:#16171a; --panel:#1e2024; --ink:#e8e8e6; --muted:#9a9a96; --line:#32343a;
      --accent:#56B4E9; --warn:#e0a080; --neg:#e08a7a; --code:#24262b;
    }
  }
  :root[data-theme="dark"] {
    --bg:#16171a; --panel:#1e2024; --ink:#e8e8e6; --muted:#9a9a96; --line:#32343a;
    --accent:#56B4E9; --warn:#e0a080; --neg:#e08a7a; --code:#24262b;
  }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--ink); font:15px/1.65 -apple-system,
         BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; }
  .wrap { max-width:informal; max-width:60rem; margin:0 auto; padding:2rem 1.25rem 5rem; }
  h1 { font-size:1.7rem; line-height:1.25; margin:0 0 .3rem; letter-spacing:-.015em; }
  h2 { font-size:1.05rem; text-transform:uppercase; letter-spacing:.07em; color:var(--muted);
       margin:2.6rem 0 .9rem; padding-bottom:.4rem; border-bottom:1px solid var(--line); }
  h4 { font-size:.85rem; text-transform:uppercase; letter-spacing:.05em; color:var(--muted);
       margin:1rem 0 .3rem; }
  code { background:var(--code); padding:.1em .35em; border-radius:3px; font-size:.87em;
         word-break:break-word; }
  pre { background:var(--code); padding:.8rem; border-radius:6px; overflow-x:auto; font-size:.8rem; }
  a { color:var(--accent); }
  .meta-line { color:var(--muted); font-size:.87rem; }
  .lede { font-size:1.1rem; line-height:1.6; margin:1.2rem 0; }
  .obj { color:var(--muted); font-size:.92rem; border-left:3px solid var(--line);
         padding-left:.9rem; margin:1rem 0 0; }
  .empty { color:var(--muted); font-style:italic; font-size:.9rem; }
  .note { color:var(--muted); font-size:.85rem; margin:.4rem 0; }
  .warn { background:color-mix(in srgb, var(--warn) 12%, transparent); border-left:3px solid var(--warn);
          padding:.7rem .9rem; border-radius:4px; font-size:.88rem; margin:1rem 0; }

  .metrics { display:flex; flex-wrap:wrap; gap:.7rem; }
  .metric { background:var(--panel); border:1px solid var(--line); border-radius:7px;
            padding:.7rem .95rem; min-width:8rem; }
  .mv { display:block; font-size:1.35rem; font-weight:600; letter-spacing:-.02em; }
  .mk { display:block; font-size:.76rem; color:var(--muted); text-transform:uppercase;
        letter-spacing:.04em; }

  .finding { background:var(--panel); border:1px solid var(--line); border-left:3px solid var(--line);
             border-radius:7px; padding:.9rem 1.1rem; margin:.8rem 0; }
  .finding.negative { border-left-color:var(--neg); }
  .finding header { display:flex; flex-wrap:wrap; gap:.5rem; align-items:center;
                    font-size:.75rem; margin-bottom:.5rem; }
  .fid { font-family:ui-monospace,monospace; color:var(--muted); }
  .kind { text-transform:uppercase; letter-spacing:.05em; color:var(--muted); }
  .conf { color:#fff; background:var(--c); padding:.1rem .45rem; border-radius:10px;
          text-transform:uppercase; letter-spacing:.04em; font-weight:600; font-size:.68rem; }
  .tag { background:var(--code); color:var(--muted); padding:.1rem .45rem; border-radius:10px; }
  .stmt { margin:.2rem 0 .7rem; }
  ul.ev { list-style:none; margin:.4rem 0 0; padding:0; font-size:.84rem; }
  ul.ev li { padding:.22rem 0; border-top:1px dashed var(--line); }
  .ev.none { color:var(--muted); font-size:.84rem; font-style:italic; }
  .stype { background:var(--code); color:var(--muted); padding:.05rem .4rem; border-radius:3px;
           font-size:.72rem; text-transform:uppercase; letter-spacing:.03em; }
  .stype.grey { background:color-mix(in srgb, var(--warn) 18%, transparent); }
  .stype.ungrounded { background:color-mix(in srgb, #8a5cb0 22%, transparent); }
  .evtitle { color:var(--muted); }
  .evyear { color:var(--muted); font-variant-numeric:tabular-nums; }
  .evdomain { color:var(--muted); font-style:italic; }
  blockquote { margin:.3rem 0 .1rem; padding-left:.7rem; border-left:2px solid var(--line);
               color:var(--muted); font-size:.92em; }
  .kgn { font-size:.78rem; color:var(--muted); margin-top:.45rem; }
  details.data summary, details.meta summary { cursor:pointer; font-size:.8rem;
               color:var(--muted); margin-top:.5rem; }

  figure.viz { margin:1.4rem 0 2rem; background:var(--panel); border:1px solid var(--line);
               border-radius:8px; padding:1rem; }
  figure.viz figcaption { margin-bottom:.8rem; }
  figure.viz .q { font-weight:600; }
  figure.viz .t { color:var(--muted); font-size:.92rem; margin-top:.2rem; }
  figure.viz iframe { width:100%; height:min(76vh,640px); border:1px solid var(--line);
                      border-radius:6px; background:var(--bg); }
  figure.viz img, .svgwrap { max-width:100%; border-radius:6px; }
  .missing { color:var(--warn); font-size:.88rem; padding:1.4rem; text-align:center;
             border:1px dashed var(--line); border-radius:6px; }
  .legend { margin-top:.7rem; font-size:.8rem; color:var(--muted); }
  .legend .sw { display:inline-flex; align-items:center; gap:.3rem; margin:.2rem .7rem .2rem 0; }
  .legend .sw i { width:.85rem; height:.35rem; border-radius:2px; display:inline-block; }
  .second { font-style:italic; }
  table.enc, table.methods { width:100%; border-collapse:collapse; font-size:.84rem; }
  table.enc th, table.enc td, table.methods th, table.methods td {
      text-align:left; padding:.35rem .5rem; border-bottom:1px solid var(--line); }
  table.methods th { color:var(--muted); font-size:.74rem; text-transform:uppercase;
      letter-spacing:.04em; font-weight:600; }
  tr.failed { color:var(--warn); }
  .fn { font-size:.8rem; font-style:italic; }
  .cred { background:var(--code); padding:.05rem .35rem; border-radius:3px; font-size:.72rem; }
  .scroll { overflow-x:auto; }

  .handoff { background:var(--panel); border:1px solid var(--line); border-radius:7px;
             padding:.9rem 1.1rem; }
  .handoff.notready { border-left:3px solid var(--warn); }
  .handoff.ready { border-left:3px solid #1a7f4f; }
  .hh { font-size:.9rem; margin-bottom:.3rem; }
  .badge { font-size:.7rem; text-transform:uppercase; letter-spacing:.05em;
           background:var(--code); padding:.1rem .45rem; border-radius:10px; }
  ul.inputs { list-style:none; padding:0; font-size:.85rem; }
  ul.inputs li { padding:.2rem 0; }
  footer { margin-top:3rem; padding-top:1rem; border-top:1px solid var(--line);
           color:var(--muted); font-size:.8rem; }

  /* ---- the interpretive layer ---- */
  .audbar { display:flex; gap:.4rem; flex-wrap:wrap; align-items:center;
            margin:1.2rem 0 .4rem; }
  .audbtn { font:inherit; font-size:.78rem; padding:.25rem .6rem; cursor:pointer;
            border:1px solid var(--line); background:var(--panel); color:var(--muted);
            border-radius:99px; }
  .audbtn:hover { border-color:var(--accent); }
  .audbtn.on { background:var(--accent); color:#fff; border-color:var(--accent); }
  .k { color:var(--muted); font-size:.85em; }

  .plainbox { background:var(--panel); border:1px solid var(--line);
              border-left:3px solid var(--accent); border-radius:7px;
              padding:.9rem 1.1rem; margin:1rem 0; }
  .plainbox h3 { margin:0 0 .4rem; font-size:.8rem; text-transform:uppercase;
                 letter-spacing:.06em; color:var(--muted); }
  .plainbox p { margin:0; font-size:1.02rem; }

  .interp { margin:.6rem 0 .2rem; }
  .aud, .mech { margin:.55rem 0; padding-left:.75rem;
                border-left:2px solid var(--line); }
  .aud p, .mech p { margin:.15rem 0; }
  .audlab { display:block; font-size:.7rem; text-transform:uppercase;
            letter-spacing:.06em; color:var(--muted); font-weight:600; }
  .mech { border-left-color:var(--accent); }
  .analogy, .readercav { font-size:.9rem; margin:.45rem 0; padding:.4rem .6rem;
                         background:var(--code); border-radius:5px; }
  .readercav { border-left:2px solid var(--warn); }
  .nointerp { color:var(--muted); font-size:.85rem; font-style:italic; margin:.4rem 0; }

  .gl { border-bottom:1px dotted var(--accent); cursor:help; }
  #gtip { position:fixed; z-index:40; display:none; max-width:320px;
          background:var(--panel); border:1px solid var(--line); border-radius:6px;
          padding:.55rem .7rem; font-size:.85rem; line-height:1.45;
          box-shadow:0 6px 22px rgba(0,0,0,.18); pointer-events:none; }

  .imps ul, .rej ul, .rsrc ul { list-style:none; padding:0; margin:.3rem 0 0; }
  .imp { border-top:1px dashed var(--line); padding:.45rem 0; font-size:.9rem; }
  .istage { font-family:ui-monospace,monospace; font-size:.75rem;
            background:var(--code); padding:.05rem .35rem; border-radius:3px; }
  .istr { font-size:.68rem; text-transform:uppercase; letter-spacing:.04em;
          color:#fff; background:var(--c); padding:.05rem .4rem; border-radius:10px;
          margin-left:.35rem; }
  .idec { font-weight:600; margin-top:.2rem; }
  .idir { margin-top:.1rem; }
  .iwrong { color:var(--muted); font-size:.85em; margin-top:.15rem; }
  .chip { font-family:ui-monospace,monospace; font-size:.68rem; background:var(--code);
          color:var(--muted); padding:.05rem .35rem; border-radius:3px; }

  .asks { display:flex; flex-wrap:wrap; gap:.7rem; }
  .ask { flex:1 1 15rem; background:var(--panel); border:1px solid var(--line);
         border-radius:7px; padding:.7rem .9rem; font-size:.9rem; }
  .ask ul { margin:.3rem 0 0; padding-left:1.1rem; }

  .glossary { display:flex; flex-wrap:wrap; gap:.7rem; }
  .gterm { flex:1 1 17rem; background:var(--panel); border:1px solid var(--line);
           border-radius:7px; padding:.7rem .9rem; font-size:.9rem; }
  .gan { margin-top:.3rem; font-style:italic; color:var(--muted); font-size:.88em; }

  /* ---- the reasoning trace ---- */
  .rstep { background:var(--panel); border:1px solid var(--line);
           border-left:3px solid var(--muted); border-radius:7px;
           padding:.8rem 1rem; margin:.7rem 0; }
  .rstep header { display:flex; flex-wrap:wrap; gap:.45rem; align-items:center;
                  font-size:.72rem; margin-bottom:.4rem; }
  .rq { font-weight:600; margin:.15rem 0; }
  .rchose { font-size:.92rem; margin:.25rem 0; }
  .rwhy { margin:.2rem 0 .4rem; }
  .rej, .rsrc { margin:.45rem 0; padding-left:.75rem;
                border-left:2px solid var(--line); font-size:.88rem; }
  .rej li, .rsrc li { padding:.15rem 0; }
  .dflt, .rev { font-size:.68rem; text-transform:uppercase; letter-spacing:.04em;
                background:var(--code); color:var(--warn); padding:.05rem .4rem;
                border-radius:10px; }
  .opendec { background:var(--panel); border:1px solid var(--line);
             border-left:3px solid var(--warn); border-radius:7px;
             padding:.7rem .9rem; margin:.8rem 0; font-size:.9rem; }
  ul.allsrc { columns:2; column-gap:1.4rem; font-size:.85rem; padding-left:1.1rem; }
  @media (max-width:640px) { ul.allsrc { columns:1; } }
  details.ev-wrap summary { cursor:pointer; font-size:.78rem; color:var(--muted);
                            margin-top:.5rem; text-transform:uppercase;
                            letter-spacing:.05em; }

  /* -- progressive disclosure ------------------------------------------
     Native <details>, no JavaScript: the tree works with scripting off, which
     the publish target effectively requires and which keeps the report from
     being sometimes-unreadable. */
  .fu-tree { margin:.7rem 0 .2rem; }
  .fu-lede { margin:.2rem 0 .6rem; }
  .fu { border-left:2px solid var(--line); padding-left:.7rem; margin:.35rem 0; }
  .fu > summary { cursor:pointer; font-weight:500; font-size:.9rem;
                  list-style:none; padding:.1rem 0; }
  /* The UA disclosure marker is inconsistent across browsers and cannot be
     positioned reliably, so it is removed and replaced. */
  .fu > summary::-webkit-details-marker { display:none; }
  .fu > summary::before { content:"\25B8\00a0"; color:var(--muted); }
  .fu[open] > summary::before { content:"\25BE\00a0"; }
  .fu > summary:hover { color:var(--accent); }
  .fu-answer { padding:.25rem 0 .1rem; font-size:.92rem; }
  .fu-answer > p { margin:.2rem 0 .45rem; }
  .fu-count { font-size:.7rem; color:var(--muted); font-weight:400; }
  /* Cumulative indent is capped by keeping the per-level padding small; past
     level 3 the rule colour and marker carry depth instead, because 5 levels of
     generous indent squeezes the text column badly on a narrow viewport. */
  .fu .fu .fu .fu { padding-left:.45rem; }
  .fu-what-is   { border-left-color:#56B4E9; }
  .fu-why       { border-left-color:#0072B2; }
  .fu-how-known { border-left-color:#A6A6A6; }
  .fu-so-what   { border-left-color:#009E73; }
  .fu-what-if   { border-left-color:#E69F00; }
  .fu-alt       { border-left-color:#CC79A7; }
  .fu-objection { border-left-color:#D55E00; }
  /* Reachable by find-in-page and by text extraction; hidden from sight and
     from screen readers, which already reach the content through the tree. */
  .fu-index { position:absolute; width:1px; height:1px; overflow:hidden;
              clip:rect(0 0 0 0); white-space:nowrap; }
  @media print {
    .fu { break-inside:avoid; }
    /* The UA stylesheet hides a closed disclosure's contents, so !important is
       doing real work here. A printed collapsed disclosure is a question with no
       answer, which is worse than no disclosure at all. */
    .fu > .fu-answer { display:block !important; }
    .fu > summary::before { content:""; }
    .fu-index { display:none; }
  }
</style>

<div class="wrap">
  <h1>__TITLE__</h1>
  <div class="meta-line">
    <b>__STAGE__</b> · run <code>__RUNID__</code> · report <code>__REPORTID__</code><br>
    __DATE__ · produced by __MODEL__ · owner: __OWNER__
  </div>

  <div class="audbar">
    <span class="k">Read as:</span>
    <button class="audbtn on" data-set="layperson">Non-specialist</button>
    <button class="audbtn" data-set="medicinal_chemist">Medicinal chemist</button>
    <button class="audbtn" data-set="structural_biologist">Structural biologist</button>
    <button class="audbtn" data-set="ml_practitioner">Modeller</button>
    <button class="audbtn" data-set="all">All</button>
  </div>

  <p class="lede">__SUMMARY__</p>
  __PLAIN__
  <p class="obj"><b>Objective.</b> __OBJECTIVE__</p>

  <h2>Headline numbers</h2>
  <div class="metrics">__METRICS__</div>

  <h2>What this stage shows</h2>
  __VIZGAPS__
  __VIZ__

  <h2>Findings</h2>
  <div class="meta-line">__NFINDINGS__ findings — __CONFMIX__</div>
  __GREYONLY__
  __ANALOGY__
  __FINDINGS__

  <h2>Limitations</h2>
  __LIMITS__

  <h2>Open questions</h2>
  __OPENQ__

  __REASONING__

  __ASKS__

  <h2>Handoff</h2>
  __HANDOFF__

  <h2>What was run</h2>
  <div class="scroll">
    <table class="methods">
      <thead><tr><th>skill</th><th>tool</th><th>summary</th><th>calls</th><th>cost</th></tr></thead>
      <tbody>__METHODS__</tbody>
    </table>
  </div>
  <div class="meta-line" style="margin-top:.5rem">Total recorded spend: <b>__COST__</b></div>

  <h2>Inputs consumed</h2>
  __INPUTS__

  __GLOSSARY__
  __FUINDEX__

  <footer>
    Generated by <code>reagent report render</code>. Every finding carries its own
    citations so a claim can be checked where it is made, its interpretation for each
    audience, and what it changes downstream. "How this was decided" is the separate
    audit trail for the agent's judgement — the options it weighed, what it rejected,
    and which sources informed the choice. Cross-domain analogies are marked and capped
    at speculative confidence by contract; grey literature is marked and cannot alone
    support an "established" claim.
  </footer>
</div>
<div id="gtip"></div>

<script>
// Audience toggle. The layperson register is the default view, because the point of
// the layered write-up is that the non-specialist path is the one you land on.
const bar = document.querySelector(".audbar");
function setAudience(which) {
  document.querySelectorAll(".audbtn").forEach(b =>
    b.classList.toggle("on", b.dataset.set === which));
  document.querySelectorAll(".aud").forEach(el => {
    el.style.display = (which === "all" || el.dataset.aud === which) ? "" : "none";
  });
  // If a finding has nothing for the chosen audience, fall back to plain rather than
  // showing an empty card.
  document.querySelectorAll(".interp").forEach(box => {
    const visible = [...box.querySelectorAll(".aud")].some(e => e.style.display !== "none");
    if (!visible) {
      const lay = box.querySelector('.aud[data-aud="layperson"]');
      if (lay) lay.style.display = "";
    }
  });
}
bar?.addEventListener("click", e => {
  const b = e.target.closest(".audbtn");
  if (b) setAudience(b.dataset.set);
});
setAudience("layperson");

// Glossary tooltips.
const gtip = document.getElementById("gtip");
document.addEventListener("mouseover", e => {
  const g = e.target.closest(".gl");
  if (!g) return;
  gtip.textContent = g.dataset.tip;
  gtip.style.display = "block";
  const r = g.getBoundingClientRect();
  gtip.style.left = Math.min(r.left, window.innerWidth - 340) + "px";
  gtip.style.top = (r.bottom + 8) + "px";
});
document.addEventListener("mouseout", e => {
  if (e.target.closest(".gl")) gtip.style.display = "none";
});
</script>
"""
