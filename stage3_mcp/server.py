#!/usr/bin/env python
"""MCP server over a Stage 3 run: the pool, the signals, and the selection.

A CSV answers the questions its author thought to ask. A reader always has
others -- *why did this item get that pose, what else was in its pool, which
signal made the call, would a different signal have changed it.* Those are
lookups, not analyses, and serving them turns a static run into something an
agent can interrogate while reasoning about the next one.

Zero dependencies beyond the venv: stdio JSON-RPC, hand-rolled, same shape as the
rest of the repo's tooling.

### The tool boundary is the leak boundary

Ground-truth-derived numbers exist in a run (`eval/results/<run>_truth.csv`) and
they are **not served**. `pool_summary` reports the oracle gap because that is a
diagnosis about the pipeline, and `candidates` reports native signals because a
selector may see those -- but no tool returns a per-candidate true score, because
an agent that can ask "which candidate is actually best" can select on the answer,
and the resulting leak is invisible in the final score. See `leak-containment`.

    .venv/bin/python stage3_mcp/server.py --list-tools
    .venv/bin/python stage3_mcp/server.py            # stdio, for an MCP client
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "eval" / "results"
RUNS = ROOT / "runs"

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "pxr-stage3", "version": "0.1.0"}

# Columns that carry a true score. Never leave this process.
TRUTH_COLUMNS = {"LDDT-PLI", "BiSyRMSD", "LDDT-LP", "scored", "oracle", "realised"}


def _read_csv(path: Path) -> list[dict[str, Any]]:
    import csv

    if not path.exists():
        return []
    with path.open(newline="") as fh:
        return list(csv.DictReader(fh))


def _strip_truth(rows: list[dict]) -> list[dict]:
    """Drop ground-truth columns on the way out, whatever produced them."""
    return [{k: v for k, v in r.items() if k not in TRUTH_COLUMNS} for r in rows]


# ---------------------------------------------------------------- tools


def list_runs() -> dict:
    """Every run on disk, with how far each got."""
    out = []
    for d in sorted(RUNS.iterdir()) if RUNS.is_dir() else []:
        jobs_path = d / "jobs.json"
        if not jobs_path.exists():
            continue
        jobs = json.loads(jobs_path.read_text())
        status: dict[str, int] = {}
        for j in jobs:
            status[j.get("status", "pending")] = status.get(j.get("status", "pending"), 0) + 1
        out.append({
            "run_id": d.name,
            "jobs": len(jobs),
            "status": status,
            "models": sorted({j["model"] for j in jobs}),
            "items": len({j["structure_id"] for j in jobs}),
            "has_selection": (d / "selection.csv").exists(),
            "has_descriptors": (d / "descriptors.csv").exists(),
        })
    return {"runs": out}


def pool_summary(run_id: str) -> dict:
    """Oracle gap, best@k, model correlation and coverage for a run."""
    p = RESULTS / f"{run_id}_pool.json"
    if not p.exists():
        return {"error": f"no pool summary for {run_id!r}; run eval/pool.py --run-id {run_id}"}
    d = json.loads(p.read_text())
    gap, oracle = d.get("gap"), d.get("oracle")
    d["verdict"] = (
        "unknown" if gap is None or oracle is None
        else "selection-limited — the ceiling is far above what is realised; work on the picker"
        if abs(gap) > 0.1 * max(abs(oracle), 1e-9)
        else "generation-limited — the picker is near the ceiling; widen the pool"
    )
    return d


def candidates(run_id: str, structure_id: str | None = None) -> dict:
    """Every candidate for a run or one item, with native signals. No true scores."""
    rows = _read_csv(RESULTS / f"{run_id}_candidates.csv")
    if not rows:
        return {"error": f"no candidate table for {run_id!r}; run eval/pool.py --run-id {run_id}"}
    if structure_id:
        rows = [r for r in rows if r.get("structure_id") == structure_id]
    return {"run_id": run_id, "n": len(rows), "candidates": _strip_truth(rows)}


def selection(run_id: str, structure_id: str | None = None) -> dict:
    """What was chosen per item, by which model, on which signal, and why."""
    rows = _read_csv(RUNS / run_id / "selection.csv")
    if not rows:
        return {"error": f"no selection for {run_id!r}; run stages/selection.py --run-id {run_id}"}
    if structure_id:
        rows = [r for r in rows if r.get("structure_id") == structure_id]
    by_model: dict[str, int] = {}
    for r in rows:
        by_model[r["model"]] = by_model.get(r["model"], 0) + 1
    return {"run_id": run_id, "n": len(rows), "by_model": by_model, "selection": _strip_truth(rows)}


def signal_report(run_id: str) -> dict:
    """Discrimination per signal, the negative control, and the rescue sweep."""
    p = RESULTS / f"{run_id}_sweep.json"
    if not p.exists():
        return {"error": f"no sweep for {run_id!r}; run eval/sweep.py --run-id {run_id}"}
    d = json.loads(p.read_text())
    ctrl = (d.get("negative_control") or {}).get("auc")
    d["control_verdict"] = (
        "absent" if ctrl is None
        else "OK — near chance, harness behaving" if 0.35 <= ctrl <= 0.65
        else "SUSPECT — control discriminates; investigate before trusting any row"
    )
    return d


def explain_item(run_id: str, structure_id: str) -> dict:
    """Everything about one item: its pool, its signals, and the pick made.

    The question a reader actually has when a single target looks wrong.
    """
    cands = [r for r in _read_csv(RESULTS / f"{run_id}_candidates.csv")
             if r.get("structure_id") == structure_id]
    sel = [r for r in _read_csv(RUNS / run_id / "selection.csv")
           if r.get("structure_id") == structure_id]
    desc = [r for r in _read_csv(RUNS / run_id / "descriptors.csv")
            if r.get("structure_id") == structure_id]
    if not cands and not sel:
        return {"error": f"{structure_id!r} not found in run {run_id!r}"}
    return {
        "run_id": run_id,
        "structure_id": structure_id,
        "pool_size": len(cands),
        "models": sorted({c["model"] for c in cands}),
        "candidates": _strip_truth(cands),
        "descriptors": _strip_truth(desc),
        "chosen": _strip_truth(sel)[0] if sel else None,
    }


def template_set() -> dict:
    """The selected receptor templates and the conformational clusters they span."""
    p = ROOT / "manifest" / "template_set.json"
    if not p.exists():
        return {"error": "no template set; run stages/templates.py"}
    d = json.loads(p.read_text())
    d["members"] = _read_csv(ROOT / "manifest" / "template_set.csv")
    return d


TOOLS = {
    "list_runs": (list_runs, "List Stage 3 runs on disk and how far each got.", {}),
    "pool_summary": (pool_summary, "Oracle gap, best@k, correlation and coverage for a run.",
                     {"run_id": {"type": "string"}}),
    "candidates": (candidates, "Candidates and their native confidence signals.",
                   {"run_id": {"type": "string"}, "structure_id": {"type": "string"}}),
    "selection": (selection, "The chosen candidate per item, with the reason.",
                  {"run_id": {"type": "string"}, "structure_id": {"type": "string"}}),
    "signal_report": (signal_report, "Signal discrimination, negative control, rescue sweep.",
                      {"run_id": {"type": "string"}}),
    "explain_item": (explain_item, "Full pool, signals and pick for one item.",
                     {"run_id": {"type": "string"}, "structure_id": {"type": "string"}}),
    "template_set": (template_set, "Selected receptor templates and their clusters.", {}),
}

REQUIRED = {
    "pool_summary": ["run_id"], "candidates": ["run_id"], "selection": ["run_id"],
    "signal_report": ["run_id"], "explain_item": ["run_id", "structure_id"],
}


def tool_schemas() -> list[dict]:
    return [
        {
            "name": name,
            "description": desc,
            "inputSchema": {"type": "object", "properties": props,
                            "required": REQUIRED.get(name, [])},
        }
        for name, (_, desc, props) in TOOLS.items()
    ]


def handle(req: dict) -> dict | None:
    method, rid = req.get("method"), req.get("id")

    if method == "initialize":
        return {"jsonrpc": "2.0", "id": rid, "result": {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": SERVER_INFO,
        }}
    if method in ("notifications/initialized", "initialized"):
        return None  # a notification has no id and takes no reply
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": rid, "result": {"tools": tool_schemas()}}
    if method == "tools/call":
        params = req.get("params") or {}
        name = params.get("name")
        if name not in TOOLS:
            return {"jsonrpc": "2.0", "id": rid,
                    "error": {"code": -32601, "message": f"unknown tool {name!r}"}}
        fn = TOOLS[name][0]
        try:
            result = fn(**(params.get("arguments") or {}))
        except TypeError as e:
            return {"jsonrpc": "2.0", "id": rid,
                    "error": {"code": -32602, "message": f"bad arguments: {e}"}}
        except Exception as e:  # a tool failure is a result, not a transport error
            result = {"error": f"{type(e).__name__}: {e}"}
        return {"jsonrpc": "2.0", "id": rid, "result": {
            "content": [{"type": "text", "text": json.dumps(result, indent=2, default=str)}]
        }}
    return {"jsonrpc": "2.0", "id": rid,
            "error": {"code": -32601, "message": f"unknown method {method!r}"}}


def main() -> int:
    if "--list-tools" in sys.argv:
        for t in tool_schemas():
            req = ", ".join(t["inputSchema"]["required"]) or "-"
            print(f"{t['name']:16s} ({req:24s}) {t['description']}")
        return 0

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        resp = handle(req)
        if resp is not None:
            print(json.dumps(resp), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
