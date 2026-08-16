"""Generate a real (not dummy) Stage 2 report from a project's live state.

Unlike sbdd_kg/report_template_dummy.html (hand-written placeholder numbers,
built to show the intended FORMAT), this only ever renders what's actually
in state.json - real stage sections, real playground figures, real KG
citations. Nothing here is invented. If a project has no stage-2 content
yet, the report says so rather than fabricating filler.

Scoped to Stage 2 (Biochem Exploration) only - see
memory/sbdd_app_stage2_scope.md. state_store already filters stages down to
just id==2, so this only ever has one stage to render.

Usage: python3 generate_report.py <project-slug>
"""
import html
import subprocess
import sys
import time
from pathlib import Path

import state_store as store

CSS = """
@page {
  size: letter;
  margin: 20mm 18mm 22mm;
  @bottom-left { content: "Generated from live project state - Stage 2 (Biochem Exploration) only"; font-size: 8pt; color: #999; }
  @bottom-right { content: "Page " counter(page) " of " counter(pages); font-size: 8pt; color: #999; }
}
* { box-sizing: border-box; }
body { font-family: Georgia, "Times New Roman", serif; font-size: 10.5pt; line-height: 1.5; color: #1c1c1c; margin: 0; }
.sans { font-family: -apple-system, "Segoe UI", Arial, sans-serif; }
.banner {
  background: #2a2f39; color: #f4f2ec; padding: 8px 14px;
  font-family: -apple-system, "Segoe UI", Arial, sans-serif; font-size: 9.5pt;
  letter-spacing: 0.03em; text-transform: uppercase; margin-bottom: 18px;
}
header.doc-header { border-bottom: 2.5px solid #1c1c1c; padding-bottom: 12px; margin-bottom: 22px; }
header.doc-header h1 { font-size: 22pt; margin: 0 0 6px; }
header.doc-header .meta {
  font-family: -apple-system, "Segoe UI", Arial, sans-serif; font-size: 9pt; color: #555;
  display: flex; gap: 18px; flex-wrap: wrap;
}
header.doc-header .meta strong { color: #1c1c1c; }
section { margin-bottom: 26px; page-break-inside: avoid; }
section.allow-break { page-break-inside: auto; }
h2 {
  font-size: 13.5pt; margin: 0 0 10px; padding-bottom: 4px; border-bottom: 1px solid #c9c4b6;
  display: flex; align-items: baseline; gap: 8px;
}
h2 .num { font-family: ui-monospace, "SF Mono", Consolas, monospace; font-size: 10pt; color: #b8862f; font-weight: normal; }
p { margin: 0 0 8px; }
ul.tight { margin: 4px 0; padding-left: 18px; }
ul.tight li { margin-bottom: 4px; }
.section-overview {
  font-style: italic; color: #4a4738; font-family: -apple-system, "Segoe UI", Arial, sans-serif;
  font-size: 9.5pt; margin: -4px 0 14px;
}
.figure-block { margin: 8px 0 10px; }
.figure-block img { max-width: 100%; display: block; border: 1px solid #d9d4c6; }
.figure-caption { font-family: -apple-system, "Segoe UI", Arial, sans-serif; font-size: 8pt; color: #555; margin-top: 4px; }
.figure-caption strong { color: #1c1c1c; }
.empty-note {
  font-family: -apple-system, "Segoe UI", Arial, sans-serif; font-size: 9pt; color: #918c7b;
  border: 1.5px dashed #b3ad9c; background: #f7f6f2; padding: 10px 12px;
}
.source-url { word-break: break-all; }
.pill {
  display: inline-block; font-family: -apple-system, "Segoe UI", Arial, sans-serif;
  font-size: 7.5pt; text-transform: uppercase; letter-spacing: 0.04em;
  padding: 1.5px 8px; border-radius: 999px; color: #fff; font-weight: 600;
}
.pill.complete { background: #3f8f83; }
.pill.incomplete { background: #b0503f; }
.progress-summary {
  font-family: -apple-system, "Segoe UI", Arial, sans-serif; font-size: 9pt; color: #555;
  border: 1px solid #d9d4c6; background: #f7f6f2; padding: 8px 12px; margin: -4px 0 18px;
  display: flex; align-items: center; gap: 10px;
}
.progress-summary b { color: #1c1c1c; }
.progress-summary span { display: inline-flex; align-items: center; gap: 6px; }
"""


def _esc(s: str) -> str:
    return html.escape(s or "")


def _progress_strip(sections: list) -> str:
    if not sections:
        return ""
    items = "".join(
        f'<span>Step {i}<span class="pill {sec.get("status", "complete")}">{sec.get("status", "complete")}</span></span>'
        for i, sec in enumerate(sections, start=1)
    )
    return f'<div class="progress-summary">{items}</div>'


def _paragraphs(text: str) -> str:
    return "".join(f"<p>{_esc(p)}</p>" for p in text.split("\n") if p.strip())


def render_html(st: dict) -> str:
    stage2 = next((s for s in st["stages"] if s["id"] == 2), None)
    sections = stage2["sections"] if stage2 else []
    figures = [it for it in st["playground"] if it.get("asset") and it["kind"] in ("image", "pymol_image", "viewer_snapshot")]
    figures = list(reversed(figures))  # playground is newest-first; report reads oldest-first
    nodes = st["literature"]["nodes"]

    protein_node = next((n for n in nodes if n["type"] == "Protein"), None)
    n_complete = sum(1 for sec in sections if sec.get("status", "complete") == "complete")
    overview = (
        f"{len(sections)} step(s) tracked ({n_complete} complete, {len(sections) - n_complete} incomplete), "
        f"{len(figures)} figure(s) captured so far for {_esc(st['name'])}, Stage 2 (Biochem Exploration)."
    )

    body = []

    if protein_node:
        body.append(f"""
<section>
  <h2><span class="num">00</span> Target</h2>
  <p class="section-overview">{_esc(protein_node['summary'])}</p>
</section>""")

    def _figure_html(it, i):
        rel = it["asset"].split("/", 1)[1]  # "<slug>/assets/x.png" -> "assets/x.png", relative to report.html
        caption = f"<strong>Figure {i} — {_esc(it['title'])}</strong>"
        if it.get("body"):
            caption += f" — {_esc(it['body'])}"
        return f"""
<div class="figure-block">
  <img src="{rel}" alt="{_esc(it['title'])}" />
  <div class="figure-caption">{caption}</div>
</div>"""

    # Figures carry an optional section_title (set at capture time via
    # playground_add_image) linking them to the report step they illustrate -
    # those render directly under that step instead of in a lump at the
    # bottom. Older/untagged figures fall through to the generic Figures block.
    fig_num = {"n": 0}

    def _figures_for(title):
        chunks = []
        for it in figures:
            if it.get("section_title") == title:
                fig_num["n"] += 1
                chunks.append(_figure_html(it, fig_num["n"]))
        return "".join(chunks)

    if sections:
        for i, sec in enumerate(sections, start=1):
            status = sec.get("status", "complete")  # sections predating this field are treated as done
            sec_figs = _figures_for(sec["title"])
            body.append(f"""
<section class="allow-break">
  <h2><span class="num">Step {i}</span> {_esc(sec['title'])} <span class="pill {status}">{status}</span></h2>
  {_paragraphs(sec['content']) if status == "complete" else '<div class="empty-note">Not finished yet - this step has a placeholder entry but no confirmed findings.</div>' + _paragraphs(sec['content'])}
  {sec_figs}
</section>""")
    else:
        body.append("""
<section>
  <h2><span class="num">Step 1</span> Biochem Exploration <span class="pill incomplete">incomplete</span></h2>
  <div class="empty-note">No steps recorded yet - call stage_add_section to add findings.</div>
</section>""")

    section_titles = {s["title"] for s in sections}
    unlinked = [it for it in figures if it.get("section_title") not in section_titles]
    if unlinked:
        fig_html = []
        for it in unlinked:
            fig_num["n"] += 1
            fig_html.append(_figure_html(it, fig_num["n"]))
        body.append(f"""
<section class="allow-break">
  <h2><span class="num">F</span> Figures</h2>
  {"".join(fig_html)}
</section>""")

    if nodes:
        cite_html = []
        for n in nodes:
            src = f'<a class="source-url" href="{_esc(n["source_url"])}">{_esc(n["source_url"])}</a>' if n.get("source_url") \
                else f'<em>{_esc(n.get("source_note") or "general knowledge, no single source")}</em>'
            cite_html.append(f"<li><strong>{_esc(n['label'])}</strong> ({_esc(n['type'])}) &mdash; {src}</li>")
        body.append(f"""
<section class="allow-break">
  <h2><span class="num">L</span> Literature / Citations</h2>
  <ul class="tight">{"".join(cite_html)}</ul>
</section>""")

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>{_esc(st['name'])} — Stage 2 Report</title>
<style>{CSS}</style>
</head>
<body>
<div class="banner">Sample report generated {time.strftime('%Y-%m-%d %H:%M')} from live project state — Stage 2 (Biochem Exploration) only</div>
<header class="doc-header">
  <h1>{_esc(st['name'])} — Biochem Exploration Report</h1>
  <div class="meta">
    <span><strong>Stage:</strong> 2 — Biochem Exploration{f" ({_esc(stage2['owner'])})" if stage2 else ""}</span>
    <span><strong>Status:</strong> {_esc(stage2['status']).replace('_', ' ') if stage2 else 'n/a'}</span>
    <span><strong>Generated:</strong> {time.strftime('%Y-%m-%d %H:%M')}</span>
  </div>
</header>
{_progress_strip(sections)}
<section>
  <p class="section-overview">{overview}</p>
</section>
{"".join(body)}
</body>
</html>
"""


def generate(slug: str) -> Path:
    st = store.load_state(slug)
    html_str = render_html(st)
    pdir = store.project_dir(slug)
    html_path = pdir / "report.html"
    html_path.write_text(html_str)
    pdf_path = pdir / "report.pdf"
    subprocess.run([
        "google-chrome", "--headless", "--disable-gpu", "--no-sandbox",
        "--no-pdf-header-footer", f"--print-to-pdf={pdf_path}",
        f"file://{html_path}",
    ], check=True, capture_output=True)
    store.set_report_generated(slug)
    return pdf_path


if __name__ == "__main__":
    out = generate(sys.argv[1])
    print(out)
