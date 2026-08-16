"""Shared state layer for the SBDD pipeline app.

Both the MCP server (mcp_server.py) and the web server (web/app.py) import
this module directly and operate on the same projects/<slug>/state.json
files. No daemon, no locking - single user, sequential tool calls.
"""
import json
import re
import time
import shutil
from pathlib import Path

try:
    import networkx as nx
except ImportError:
    nx = None

ROOT = Path(__file__).parent
PROJECTS_DIR = ROOT / "projects"
PROJECTS_DIR.mkdir(exist_ok=True)

# deliberately NOT under PROJECTS_DIR - web/app.py mounts /assets over the
# whole of PROJECTS_DIR, so anything under it is servable by URL. Staging
# needs to actually be private (agent-only, via the Read tool / filesystem),
# not just unlinked, so it lives in a separate tree entirely.
STAGING_DIR = ROOT / "_staging"
STAGING_DIR.mkdir(exist_ok=True)

# Scoped to Stage 2 only (Biochem Exploration) - S1/S3/S4 are out of scope
# for now, see memory/sbdd_app_stage2_scope.md. Re-add them here if that
# scope changes.
STAGE_TEMPLATE = [
    {
        "id": 2,
        "name": "Biochem Exploration",
        "owner": "Denny",
        "questions": [
            "What are the critical amino acids and their complementary fragments?",
            "What is the dynamics of the pocket?",
        ],
        "tools": ["ChimeraX", "PyMOL"],
    },
]


def slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "project"


def _empty_state(name: str, slug: str) -> dict:
    return {
        "name": name,
        "slug": slug,
        "created": time.time(),
        "literature": {"nodes": [], "edges": []},
        "playground": [],
        "viewer": {"commands": []},
        "stages": [
            {**s, "status": "not_started", "sections": []} for s in STAGE_TEMPLATE
        ],
        "report": None,
        "md_jobs": [],
    }


def project_dir(slug: str) -> Path:
    return PROJECTS_DIR / slug


def assets_dir(slug: str) -> Path:
    d = project_dir(slug) / "assets"
    d.mkdir(parents=True, exist_ok=True)
    return d


def staging_dir(slug: str) -> Path:
    """Private scratch space for figure candidates - the agent captures here,
    looks at what it got with Read, and only promotes the good ones into
    assets_dir (via playground_add_image). Lives outside PROJECTS_DIR/assets
    so it's never reachable through the /assets HTTP mount."""
    d = STAGING_DIR / slug
    d.mkdir(parents=True, exist_ok=True)
    return d


def state_path(slug: str) -> Path:
    return project_dir(slug) / "state.json"


def list_projects() -> list[dict]:
    out = []
    if not PROJECTS_DIR.exists():
        return out
    for d in sorted(PROJECTS_DIR.iterdir()):
        sp = d / "state.json"
        if sp.exists():
            try:
                st = json.loads(sp.read_text())
                out.append({"slug": st["slug"], "name": st["name"]})
            except Exception:
                continue
    return out


def create_project(name: str) -> dict:
    slug = slugify(name)
    project_dir(slug).mkdir(parents=True, exist_ok=True)
    assets_dir(slug)
    sp = state_path(slug)
    if sp.exists():
        return load_state(slug)
    st = _empty_state(name, slug)
    save_state(st)
    return st


def load_state(slug: str) -> dict:
    sp = state_path(slug)
    if not sp.exists():
        raise FileNotFoundError(f"no project '{slug}'")
    st = json.loads(sp.read_text())
    st.setdefault("viewer", {"commands": []})  # older projects predate the viewer tab
    st.setdefault("report", None)  # older projects predate report generation
    st.setdefault("md_jobs", [])  # older projects predate the Tamarind MD integration
    # scope is Stage 2 only for now - drop S1/S3/S4 from projects that were
    # created before this scope decision (their sections, if any, stay on
    # disk untouched, just filtered out of what load_state returns)
    keep_ids = {s["id"] for s in STAGE_TEMPLATE}
    st["stages"] = [s for s in st.get("stages", []) if s["id"] in keep_ids]
    return st


def save_state(st: dict) -> None:
    sp = state_path(st["slug"])
    sp.parent.mkdir(parents=True, exist_ok=True)
    sp.write_text(json.dumps(st, indent=2))


def _recompute_layout(lit: dict) -> None:
    """Fill in x,y (0..1) for every node via spring layout, in place."""
    if nx is None or not lit["nodes"]:
        return
    G = nx.DiGraph()
    for n in lit["nodes"]:
        G.add_node(n["id"])
    for e in lit["edges"]:
        G.add_edge(e["source"], e["target"])
    if G.number_of_nodes() == 0:
        return
    pos = nx.spring_layout(G, seed=11, k=1.6 / max(1, len(G) ** 0.5), iterations=300)
    xs = [p[0] for p in pos.values()]
    ys = [p[1] for p in pos.values()]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    spanx = (maxx - minx) or 1
    spany = (maxy - miny) or 1
    by_id = {n["id"]: n for n in lit["nodes"]}
    for node_id, (x, y) in pos.items():
        by_id[node_id]["x"] = (x - minx) / spanx
        by_id[node_id]["y"] = (y - miny) / spany


def kg_add_node(slug, node_id, node_type, label, summary, source_url=None, source_note=None):
    st = load_state(slug)
    lit = st["literature"]
    lit["nodes"] = [n for n in lit["nodes"] if n["id"] != node_id]
    lit["nodes"].append({
        "id": node_id,
        "type": node_type,
        "label": label,
        "summary": summary,
        "source_url": source_url,
        "source_note": source_note,
    })
    _recompute_layout(lit)
    save_state(st)
    return st


def kg_add_edge(slug, source, relation, target, note=""):
    st = load_state(slug)
    lit = st["literature"]
    lit["edges"].append({"source": source, "relation": relation, "target": target, "note": note})
    _recompute_layout(lit)
    save_state(st)
    return st


def playground_add(slug, kind, title, body="", asset_path=None, request_id=None, section_title=None):
    st = load_state(slug)
    item = {
        "id": f"pg-{int(time.time() * 1000)}",
        "ts": time.time(),
        "kind": kind,  # text | image | pymol_image | viewer_snapshot | note
        "title": title,
        "body": body,
        "asset": asset_path,
        "request_id": request_id,
        "section_title": section_title,  # links this figure to a stage_add_section title, if any
    }
    st["playground"].insert(0, item)
    save_state(st)
    return st


def playground_add_image_file(slug, title, src_file_path, body="", kind="image", section_title=None):
    src = Path(src_file_path)
    if not src.exists():
        raise FileNotFoundError(src_file_path)
    adir = assets_dir(slug)
    dest_name = f"{int(time.time() * 1000)}_{src.name}"
    shutil.copy(src, adir / dest_name)
    return playground_add(slug, kind, title, body, asset_path=f"{slug}/assets/{dest_name}", section_title=section_title)


def stage_start(slug, stage_id):
    st = load_state(slug)
    for s in st["stages"]:
        if s["id"] == stage_id:
            s["status"] = "in_progress"
    save_state(st)
    return st


def stage_complete(slug, stage_id):
    st = load_state(slug)
    for s in st["stages"]:
        if s["id"] == stage_id:
            s["status"] = "done"
    save_state(st)
    return st


def stage_add_section(slug, stage_id, title, content, status="complete"):
    st = load_state(slug)
    for s in st["stages"]:
        if s["id"] == stage_id:
            s["sections"].append({"title": title, "content": content, "ts": time.time(), "status": status})
    save_state(st)
    return st


def stage_set_section_status(slug, stage_id, index, status):
    """Flip a section's complete/incomplete status - this is what makes the
    generated report show "Step N: incomplete" and then later flip to
    complete once the agent actually finishes that piece of analysis."""
    st = load_state(slug)
    for s in st["stages"]:
        if s["id"] == stage_id and 0 <= index < len(s["sections"]):
            s["sections"][index]["status"] = status
    save_state(st)
    return st


def stage_finish_section(slug, stage_id, index, extra_content=""):
    """Mark a section complete and append text to it in one call - used when
    an async job (e.g. Tamarind MD) that started a section as 'incomplete'
    finishes, so the result gets recorded in the same step rather than a
    disconnected new one."""
    st = load_state(slug)
    for s in st["stages"]:
        if s["id"] == stage_id and 0 <= index < len(s["sections"]):
            sec = s["sections"][index]
            if extra_content:
                sec["content"] = (sec["content"] + "\n\n" + extra_content).strip()
            sec["status"] = "complete"
    save_state(st)
    return st


def md_job_add(slug, job_name, job_type, settings, section_index):
    st = load_state(slug)
    st.setdefault("md_jobs", [])
    st["md_jobs"].append({
        "job_name": job_name,
        "type": job_type,
        "settings": settings,
        "submitted_ts": time.time(),
        "section_index": section_index,
        "status": "In Queue",
    })
    save_state(st)
    return st


def md_job_update(slug, job_name, status, result_url=None):
    st = load_state(slug)
    job = None
    for j in st.get("md_jobs", []):
        if j["job_name"] == job_name:
            j["status"] = status
            if result_url:
                j["result_url"] = result_url
            job = j
    save_state(st)
    return job


def viewer_command(slug, op, args):
    """Append one 3Dmol.js command (load/style/surface/zoom/label/spin) to the
    project's viewer log. The browser replays the whole log on each update -
    this is the entire "agent drives the live 3D view" mechanism."""
    st = load_state(slug)
    st["viewer"]["commands"].append({"op": op, "args": args, "ts": time.time()})
    save_state(st)
    return st


def viewer_reset(slug):
    st = load_state(slug)
    st["viewer"] = {"commands": []}
    save_state(st)
    return st


def set_report_generated(slug):
    """Stamp that a report PDF now exists at projects/<slug>/report.pdf (served
    via the existing /assets mount, since it's already under project_dir) -
    the browser uses this to decide whether to show the report preview."""
    st = load_state(slug)
    st["report"] = {"pdf_path": f"{slug}/report.pdf", "generated_ts": time.time()}
    save_state(st)
    return st
