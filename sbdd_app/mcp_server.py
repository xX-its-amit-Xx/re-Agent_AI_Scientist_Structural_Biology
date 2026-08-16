"""SBDD pipeline MCP server.

Exposes tools to build a per-project knowledge graph (Literature Review tab),
drop arbitrary artifacts into a scratch feed (Playground tab), and write
staged reports (Reports tab). All state is written to
projects/<slug>/state.json via state_store.py. After every mutation this
process best-effort POSTs to the local web server so the browser tab
updates live (SSE) - if the web server isn't running, the POST just fails
silently and the browser will pick up the change next time it polls/loads.
"""
from typing import Optional

import time
import urllib.request
import urllib.error
import json as _json

import state_store as store
import generate_report as _report
import tamarind_client as _tamarind

from mcp.server import MCPServer

WEB_BASE_URL = "http://127.0.0.1:8420"
WEB_NOTIFY_URL = f"{WEB_BASE_URL}/internal/notify"

mcp = MCPServer(
    name="sbdd-pipeline",
    instructions=(
        "Tools for the structure-based drug design pipeline app. "
        "Use create_project to start a new target (e.g. PXR, CYP3A4). "
        "Use kg_add_node/kg_add_edge to build the Literature Review knowledge "
        "graph. Use playground_add_text/playground_add_image for anything "
        "generated ad hoc (figures, PyMOL renders, pulled papers) that should "
        "show up in the Playground tab. Use stage_* tools to drive the 4-stage "
        "report (Literature Review, Biochem Exploration, Applying Biological "
        "Prior, Optimizations) shown in the Reports tab."
    ),
)


def _notify(slug: str) -> None:
    try:
        req = urllib.request.Request(
            WEB_NOTIFY_URL,
            data=_json.dumps({"project": slug}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=0.5)
    except Exception:
        pass


def _regen_report(slug: str) -> None:
    """Re-render the report PDF and push it live - called after every stage
    mutation so the embedded PDF in the Reports tab always reflects current
    progress, without the agent needing to remember a separate generate_report
    call. Best-effort: a report-generation hiccup shouldn't break the actual
    stage tool call that triggered it."""
    try:
        _report.generate(slug)
    except Exception:
        pass
    _notify(slug)


@mcp.tool()
def list_projects() -> list[dict]:
    """List existing projects (slug + display name)."""
    return store.list_projects()


@mcp.tool()
def create_project(name: str) -> dict:
    """Create (or fetch, if it already exists) a project by display name, e.g. 'PXR'."""
    st = store.create_project(name)
    _notify(st["slug"])
    return {"slug": st["slug"], "name": st["name"]}


@mcp.tool()
def kg_add_node(
    project: str,
    node_id: str,
    node_type: str,
    label: str,
    summary: str,
    source_url: Optional[str] = None,
    source_note: Optional[str] = None,
) -> str:
    """Add/update a node in the project's Literature Review knowledge graph.

    node_type should be one of: Concept, Method, Paper, Protein, Compound.
    Provide source_url when you have a real citation; otherwise provide
    source_note explaining it's general knowledge - never fabricate a URL.
    """
    store.kg_add_node(store.slugify(project), node_id, node_type, label, summary, source_url, source_note)
    _notify(store.slugify(project))
    return f"added node {node_id}"


@mcp.tool()
def kg_add_edge(project: str, source: str, relation: str, target: str, note: str = "") -> str:
    """Add a directed edge between two existing node ids in the knowledge graph."""
    store.kg_add_edge(store.slugify(project), source, relation, target, note)
    _notify(store.slugify(project))
    return f"added edge {source} -{relation}-> {target}"


@mcp.tool()
def playground_add_text(project: str, title: str, body: str) -> str:
    """Drop a text/markdown item (e.g. a pulled-paper summary, a note) into the Playground tab."""
    store.playground_add(store.slugify(project), "text", title, body)
    _notify(store.slugify(project))
    return "added"


@mcp.tool()
def playground_add_image(project: str, title: str, file_path: str, caption: str = "", kind: str = "image", section_title: Optional[str] = None) -> str:
    """Copy a local image into the project's assets and drop it into the
    Playground tab, permanently. This is also the promotion step for a
    staging capture: pass the path viewer_capture_preview returned once
    you've actually looked at it with Read and it looks right.
    kind: 'image' | 'pymol_image'.
    section_title: exact title of a stage_add_section this figure illustrates
    (e.g. "Inactive vs. active pocket comparison") - the report renders it
    directly under that section instead of in the generic Figures block.
    Leave unset for ad hoc images not tied to one report step.
    """
    store.playground_add_image_file(store.slugify(project), title, file_path, caption, kind, section_title)
    _notify(store.slugify(project))
    return "added"


@mcp.tool()
def stage_start(project: str, stage_id: int) -> str:
    """Mark a pipeline stage (1-4) as in_progress."""
    slug = store.slugify(project)
    store.stage_start(slug, stage_id)
    _regen_report(slug)
    return f"stage {stage_id} started"


@mcp.tool()
def stage_add_section(project: str, stage_id: int, title: str, content: str, status: str = "complete") -> str:
    """Add a step/section to the stage report (this is what the embedded PDF
    in the Reports tab renders). status: 'complete' | 'incomplete' - use
    'incomplete' for a placeholder/in-progress step (renders with a red
    INCOMPLETE pill and a "not finished yet" note in the PDF), then call
    stage_set_section_status once it's actually done. Regenerates the report
    PDF automatically."""
    slug = store.slugify(project)
    store.stage_add_section(slug, stage_id, title, content, status)
    _regen_report(slug)
    return "section added"


@mcp.tool()
def viewer_load(project: str, pdb_id: Optional[str] = None, url: Optional[str] = None, format: str = "pdb") -> str:
    """Load a structure into the live 3D viewer (Structure tab). Give either a
    4-character pdb_id (fetched from RCSB directly in the browser) or a url to
    a structure file. Clears any prior viewer state first."""
    slug = store.slugify(project)
    store.viewer_reset(slug)
    store.viewer_command(slug, "load", {"pdb_id": pdb_id, "url": url, "format": format})
    _notify(slug)
    return f"loading {pdb_id or url}"


@mcp.tool()
def viewer_style(project: str, selector: dict, style: dict) -> str:
    """Apply a 3Dmol.js style to atoms matching selector.

    selector: AtomSelectionSpec, e.g. {"resi": "356,200"}, {"chain": "A"},
    {"resn": "HOH", "invert": true}.
    style: StyleSpec, e.g. {"cartoon": {"color": "spectrum"}},
    {"stick": {"colorscheme": "orangeCarbon"}}, {"sphere": {"scale": 0.3}}.
    """
    slug = store.slugify(project)
    store.viewer_command(slug, "style", {"selector": selector, "style": style})
    _notify(slug)
    return "style applied"


@mcp.tool()
def viewer_surface(project: str, selector: dict, opacity: float = 0.7, color: Optional[str] = None) -> str:
    """Add a VDW surface over atoms matching selector (e.g. a pocket)."""
    slug = store.slugify(project)
    store.viewer_command(slug, "surface", {"selector": selector, "opacity": opacity, "color": color})
    _notify(slug)
    return "surface added"


@mcp.tool()
def viewer_zoom(project: str, selector: Optional[dict] = None) -> str:
    """Zoom/frame the camera on atoms matching selector (omit for whole structure)."""
    slug = store.slugify(project)
    store.viewer_command(slug, "zoom", {"selector": selector or {}})
    _notify(slug)
    return "zoomed"


@mcp.tool()
def viewer_label(project: str, selector: dict, text: str) -> str:
    """Add a text label anchored at the first atom matching selector."""
    slug = store.slugify(project)
    store.viewer_command(slug, "label", {"selector": selector, "text": text})
    _notify(slug)
    return "label added"


@mcp.tool()
def viewer_spin(project: str, on: bool = True, axis: str = "y") -> str:
    """Start/stop a slow auto-rotate of the viewer about an axis ('x'|'y'|'z')."""
    slug = store.slugify(project)
    store.viewer_command(slug, "spin", {"on": on, "axis": axis})
    _notify(slug)
    return "spin toggled"


@mcp.tool()
def viewer_capture_preview(project: str, timeout_s: float = 15.0) -> str:
    """Grab whatever the live 3D viewer currently shows into a PRIVATE staging
    folder (projects/<slug>/staging/) and return the absolute file path - use
    the Read tool on that path to actually look at the image before deciding
    anything. This is the review step: call it, look at what came back, and if
    the framing/coloring/zoom isn't right, adjust with viewer_style/viewer_zoom/
    etc. and call it again. Nothing here touches the Playground tab or the
    report - it's scratch space, call it as many times as you need. Once a
    capture actually looks right, promote it with playground_add_image
    (project, title, file_path=<the path this returned>, caption). Requires
    the web app open in a browser tab on this project - the browser does the
    actual rendering/capture."""
    slug = store.slugify(project)
    try:
        req = urllib.request.Request(
            f"{WEB_BASE_URL}/api/projects/{slug}/viewer/capture_preview",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        resp = urllib.request.urlopen(req, timeout=3)
        request_id = _json.loads(resp.read())["request_id"]
    except (urllib.error.URLError, OSError) as e:
        return f"could not reach web app at {WEB_BASE_URL} - is it running? ({e})"

    deadline = time.time() + timeout_s
    status_url = f"{WEB_BASE_URL}/api/projects/{slug}/viewer/capture_preview/{request_id}"
    while time.time() < deadline:
        time.sleep(0.5)
        status = _json.loads(urllib.request.urlopen(status_url, timeout=3).read())
        if status.get("status") == "done":
            return f"preview saved: {status['path']} - use Read on this path to look at it before promoting"
    return "timed out waiting for the browser tab to render/capture - is the app open and on this project's Structure tab?"


@mcp.tool()
def viewer_snapshot(project: str, title: str = "Structure snapshot", caption: str = "", timeout_s: float = 15.0) -> str:
    """Capture whatever the live 3D viewer currently shows straight to the
    Playground tab, permanently, no review step. Prefer viewer_capture_preview
    (check the image with Read, THEN playground_add_image to commit) for
    anything going into a report - use this only for quick throwaway captures
    where framing doesn't matter. Requires the web app open in a browser tab."""
    slug = store.slugify(project)
    try:
        req = urllib.request.Request(
            f"{WEB_BASE_URL}/api/projects/{slug}/viewer/snapshot",
            data=_json.dumps({"title": title, "caption": caption}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        resp = urllib.request.urlopen(req, timeout=3)
        request_id = _json.loads(resp.read())["request_id"]
    except (urllib.error.URLError, OSError) as e:
        return f"could not reach web app at {WEB_BASE_URL} - is it running? ({e})"

    deadline = time.time() + timeout_s
    status_url = f"{WEB_BASE_URL}/api/projects/{slug}/viewer/snapshot/{request_id}"
    while time.time() < deadline:
        time.sleep(0.5)
        status = _json.loads(urllib.request.urlopen(status_url, timeout=3).read())
        if status.get("status") == "done":
            return f"snapshot saved to playground: {status['asset']}"
    return "timed out waiting for the browser tab to render/upload the snapshot - is the app open and on this project?"


@mcp.tool()
def viewer_reset(project: str) -> str:
    """Clear the live viewer back to empty."""
    slug = store.slugify(project)
    store.viewer_reset(slug)
    _notify(slug)
    return "viewer reset"


@mcp.tool()
def stage_set_section_status(project: str, stage_id: int, index: int, status: str) -> str:
    """Flip a step/section's status - 'complete' or 'incomplete'. index is
    0-based, matching the order sections were added in (Step 1 in the report
    = index 0). Regenerates the report PDF automatically, so this is how
    "Step 3: incomplete" turns into "Step 3: complete" once that analysis is
    actually done."""
    slug = store.slugify(project)
    store.stage_set_section_status(slug, stage_id, index, status)
    _regen_report(slug)
    return f"section {index} set to {status}"


@mcp.tool()
def stage_complete(project: str, stage_id: int) -> str:
    """Mark a pipeline stage as done. Only stage 2 (Biochem Exploration) is
    in scope right now - see memory/sbdd_app_stage2_scope.md."""
    slug = store.slugify(project)
    store.stage_complete(slug, stage_id)
    _regen_report(slug)
    return f"stage {stage_id} complete"


@mcp.tool()
def generate_report(project: str) -> str:
    """Render a real Stage 2 report PDF from this project's actual state -
    real stage sections (stage_add_section), real figures (playground images),
    real KG citations. Nothing is fabricated; if a project has little content
    yet, the report says so rather than inventing numbers. This is for the
    user to review sample-report quality, not a final deliverable format.
    Writes projects/<slug>/report.html and report.pdf, returns the PDF path."""
    slug = store.slugify(project)
    try:
        pdf_path = _report.generate(slug)
    except Exception as e:
        return f"report generation failed: {e}"
    _notify(slug)
    return f"report generated: {pdf_path}"


@mcp.tool()
def md_submit(
    project: str,
    pdb_id: Optional[str] = None,
    protein_file_path: Optional[str] = None,
    ligand_file_path: Optional[str] = None,
    force_field: str = "amber99sb",
    simulation_time_ns: float = 1.0,
    water_model: str = "tip3p",
    box_type: str = "cubic",
    salt: float = 0.15,
    temp: float = 300.0,
    pressure: float = 1.0,
    save_freq_ps: float = 10.0,
    nvt_time_ns: float = 0.05,
    npt_time_ns: float = 0.05,
    traj_format: str = "xtc",
    num_replicas: int = 1,
    job_name: Optional[str] = None,
    dry_run: bool = False,
) -> str:
    """Submit a real GROMACS molecular dynamics run via the Tamarind Bio API
    (real MD, not a mock - this answers "what is the dynamics of the
    pocket?", Stage 2 question 2). Give either pdb_id (fetched server-side
    from RCSB - simplest, protein-only) or protein_file_path (a local PDB
    file, uploaded automatically). Add ligand_file_path (local SDF) to run
    protein-ligand instead of protein-only - note Tamarind's protein-ligand
    mode always needs an uploaded protein file, not a bare pdb_id, so if you
    only gave pdb_id in that case this fetches it from RCSB and uploads it
    for you.

    dry_run=True validates the payload for free via Tamarind's own
    /validate-job and returns the normalized settings WITHOUT spending
    credits or touching project state - use this to sanity-check parameters
    first. dry_run=False actually submits (real cost) and adds an
    'incomplete' step to the Stage 2 report tracking the run; call
    md_check_status later with the returned job name to see progress, which
    marks that step complete and appends the result link once done."""
    slug = store.slugify(project)
    is_ligand = bool(ligand_file_path)

    try:
        if is_ligand:
            protein_ref = _tamarind.upload_file(protein_file_path) if protein_file_path else None
            if not protein_ref:
                if not pdb_id:
                    return "protein-ligand runs need protein_file_path or pdb_id (Tamarind has no fetch-by-ID option for protein-ligand, so a pdb_id here gets fetched from RCSB and uploaded on your behalf)"
                import tempfile
                import urllib.request as _urlreq
                pdb_text = _urlreq.urlopen(f"https://files.rcsb.org/download/{pdb_id.upper()}.pdb", timeout=30).read()
                with tempfile.NamedTemporaryFile(suffix=f"_{pdb_id.upper()}.pdb", delete=False) as f:
                    f.write(pdb_text)
                    tmp_path = f.name
                protein_ref = _tamarind.upload_file(tmp_path)
            ligand_ref = _tamarind.upload_file(ligand_file_path)
            settings = {"systemType": "protein-ligand", "proteinFile": protein_ref, "ligandFile": ligand_ref}
        elif protein_file_path:
            protein_ref = _tamarind.upload_file(protein_file_path)
            settings = {"systemType": "protein", "uploadType": "upload", "pdbFile": protein_ref}
        elif pdb_id:
            settings = {"systemType": "protein", "uploadType": "fetch", "pdbID": pdb_id.upper()}
        else:
            return "need one of: pdb_id, protein_file_path"

        settings.update({
            "forceField": force_field,
            "boxType": box_type,
            "waterModel": water_model,
            "salt": salt,
            "temp": temp,
            "pressure": pressure,
            "saveFreq": save_freq_ps,
            "NVTEquilibrationTime": nvt_time_ns,
            "NPTEquilibrationTime": npt_time_ns,
            "simulationTime": simulation_time_ns,
            "trajFormat": traj_format,
            "numReplicas": num_replicas,
        })

        validation = _tamarind.validate_job("gromacs", settings)
        if not validation.get("valid"):
            return f"validation failed: {validation}"
        if dry_run:
            return f"dry run OK, would submit with: {validation['normalized']}"

        name = job_name or f"{slug}-md-{int(time.time())}"
        _tamarind.submit_job(name, "gromacs", validation["normalized"])
    except Exception as e:
        return f"MD submission failed: {e}"

    st = store.stage_add_section(
        slug, 2, f"MD simulation - {name}",
        f"GROMACS run submitted via Tamarind Bio ({settings.get('systemType')}, "
        f"{simulation_time_ns} ns production, {force_field}). Job name: {name}. "
        f"Call md_check_status(project, \"{name}\") to check progress.",
        status="incomplete",
    )
    stage2 = next(s for s in st["stages"] if s["id"] == 2)
    section_index = len(stage2["sections"]) - 1
    store.md_job_add(slug, name, "gromacs", validation["normalized"], section_index)
    _regen_report(slug)
    return f"submitted job '{name}' (real cost incurred) - poll with md_check_status"


@mcp.tool()
def md_check_status(project: str, job_name: str) -> str:
    """Check a Tamarind MD job's status. When it flips to Complete, this
    marks the corresponding Stage 2 step complete and appends the result
    download link to it, then regenerates the report."""
    slug = store.slugify(project)
    try:
        job = _tamarind.get_job(job_name)
    except Exception as e:
        return f"status check failed: {e}"
    if not job:
        return f"no such job '{job_name}' (check the exact name from md_submit's return value)"

    status = job.get("JobStatus", "Unknown")
    result_url = None
    if status == "Complete":
        try:
            result_url = _tamarind.get_result(job_name)
        except TimeoutError:
            pass  # job compute finished but result zip still aggregating - status stays Complete, no link yet
        except Exception:
            pass

    rec = store.md_job_update(slug, job_name, status, result_url)
    if status == "Complete" and rec is not None:
        extra = f"Result: {result_url}" if result_url else "Compute finished, result archive still being assembled - re-check shortly."
        store.stage_finish_section(slug, 2, rec["section_index"], extra)
        _regen_report(slug)
    else:
        _notify(slug)
    return f"job '{job_name}': {status}" + (f", result: {result_url}" if result_url else "")


@mcp.tool()
def md_list_jobs(project: str) -> list:
    """List MD jobs submitted for this project (name, status, when submitted)."""
    st = store.load_state(store.slugify(project))
    return st.get("md_jobs", [])


if __name__ == "__main__":
    mcp.run(transport="stdio")
