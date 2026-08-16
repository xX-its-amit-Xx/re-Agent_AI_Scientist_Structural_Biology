"""Local web server for the SBDD pipeline app.

Serves the 3-tab UI (Literature Review / Playground / Reports) and pushes
live updates over SSE whenever the MCP server (mcp_server.py, a separate
process) writes new state and hits /internal/notify.

Run: uvicorn web.app:app --port 8420 --reload   (from sbdd_app/)
"""
import asyncio
import base64
import json
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import state_store as store

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

app = FastAPI()

STATIC_DIR = Path(__file__).parent / "static"

_subscribers: dict[str, set[asyncio.Queue]] = {}
_pending_snapshots: dict[str, dict] = {}  # request_id -> {"status": "pending"|"done", "asset": str|None}


def _sub(slug: str) -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue()
    _subscribers.setdefault(slug, set()).add(q)
    return q


def _unsub(slug: str, q: asyncio.Queue) -> None:
    _subscribers.get(slug, set()).discard(q)


async def _publish(slug: str) -> None:
    for q in list(_subscribers.get(slug, set())):
        await q.put({"event": "message", "data": "update"})


async def _publish_event(slug: str, event: str, data: dict) -> None:
    for q in list(_subscribers.get(slug, set())):
        await q.put({"event": event, "data": json.dumps(data)})


@app.get("/api/projects")
def api_list_projects():
    return store.list_projects()


@app.post("/api/projects")
async def api_create_project(req: Request):
    body = await req.json()
    st = store.create_project(body["name"])
    await _publish(st["slug"])
    return {"slug": st["slug"], "name": st["name"]}


@app.get("/api/projects/{slug}/state")
def api_get_state(slug: str):
    try:
        return store.load_state(slug)
    except FileNotFoundError:
        return JSONResponse({"error": "not found"}, status_code=404)


@app.post("/api/projects/{slug}/viewer/load")
async def api_viewer_load(slug: str, req: Request):
    body = await req.json()
    store.viewer_reset(slug)
    store.viewer_command(slug, "load", {"pdb_id": body.get("pdb_id"), "url": body.get("url"), "format": body.get("format", "pdb")})
    await _publish(slug)
    return {"ok": True}


@app.post("/api/projects/{slug}/viewer/reset")
async def api_viewer_reset(slug: str):
    store.viewer_reset(slug)
    await _publish(slug)
    return {"ok": True}


@app.post("/api/projects/{slug}/viewer/snapshot")
async def api_viewer_snapshot(slug: str, req: Request):
    """Ask the (already open) browser tab to capture the live viewer canvas.
    Returns a request_id to poll - the actual PNG only exists once the
    browser has rendered it and POSTed it back to the upload endpoint below."""
    body = await req.json()
    request_id = uuid.uuid4().hex[:12]
    _pending_snapshots[request_id] = {"status": "pending", "asset": None}
    store.viewer_command(slug, "snapshot", {
        "request_id": request_id,
        "title": body.get("title", "Structure snapshot"),
        "caption": body.get("caption", ""),
    })
    await _publish(slug)
    return {"request_id": request_id}


@app.get("/api/projects/{slug}/viewer/snapshot/{request_id}")
def api_viewer_snapshot_status(request_id: str, slug: str):
    return _pending_snapshots.get(request_id, {"status": "unknown"})


@app.post("/api/projects/{slug}/viewer/snapshot/{request_id}/upload")
async def api_viewer_snapshot_upload(slug: str, request_id: str, req: Request):
    # the viewer replays its ENTIRE command history on every reload/tab-switch/
    # project-switch (see replayViewerCommands in app.js) - a "snapshot" command
    # sitting in that history would otherwise re-fire and re-upload every single
    # replay. Dedup on request_id so each snapshot only ever lands once.
    st = store.load_state(slug)
    existing = next((it for it in st["playground"] if it.get("request_id") == request_id), None)
    if existing:
        _pending_snapshots[request_id] = {"status": "done", "asset": existing["asset"]}
        return {"ok": True, "deduped": True}

    body = await req.json()
    header, b64data = body["data_uri"].split(",", 1)
    img_bytes = base64.b64decode(b64data)
    adir = store.assets_dir(slug)
    fname = f"{int(time.time() * 1000)}_snapshot.png"
    (adir / fname).write_bytes(img_bytes)
    asset_path = f"{slug}/assets/{fname}"
    store.playground_add(slug, "viewer_snapshot", body.get("title", "Structure snapshot"), body.get("caption", ""), asset_path=asset_path, request_id=request_id)
    _pending_snapshots[request_id] = {"status": "done", "asset": asset_path}
    await _publish(slug)
    return {"ok": True}


@app.post("/api/projects/{slug}/viewer/capture_preview")
async def api_viewer_capture_preview(slug: str):
    """Ask the live browser tab to grab the CURRENT viewer canvas straight to
    a private staging/ folder - not Playground, not stored as a replayable
    viewer command. Purely ephemeral (pushed over SSE, nothing written to
    state.json), so this can be called as many times as needed while the
    agent is still fiddling with the camera/style and doesn't want every
    attempt permanently logged."""
    request_id = uuid.uuid4().hex[:12]
    _pending_snapshots[request_id] = {"status": "pending", "path": None}
    await _publish_event(slug, "capture", {"request_id": request_id})
    return {"request_id": request_id}


@app.get("/api/projects/{slug}/viewer/capture_preview/{request_id}")
def api_viewer_capture_preview_status(request_id: str, slug: str):
    return _pending_snapshots.get(request_id, {"status": "unknown"})


@app.post("/api/projects/{slug}/viewer/capture_preview/{request_id}/upload")
async def api_viewer_capture_preview_upload(slug: str, request_id: str, req: Request):
    body = await req.json()
    header, b64data = body["data_uri"].split(",", 1)
    img_bytes = base64.b64decode(b64data)
    sdir = store.staging_dir(slug)
    fname = f"preview_{int(time.time() * 1000)}.png"
    fpath = sdir / fname
    fpath.write_bytes(img_bytes)
    _pending_snapshots[request_id] = {"status": "done", "path": str(fpath)}
    return {"ok": True}


@app.get("/api/projects/{slug}/events")
async def api_events(slug: str):
    q = _sub(slug)

    async def gen():
        try:
            yield {"event": "message", "data": "hello"}
            while True:
                item = await q.get()
                yield item
        finally:
            _unsub(slug, q)

    return EventSourceResponse(gen())


@app.post("/internal/notify")
async def internal_notify(req: Request):
    body = await req.json()
    slug = body.get("project")
    if slug:
        await _publish(slug)
    return {"ok": True}


app.mount("/assets", StaticFiles(directory=str(store.PROJECTS_DIR)), name="assets")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def index():
    return FileResponse(str(STATIC_DIR / "index.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8420, reload=True)
