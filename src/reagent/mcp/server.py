"""MCP server making a Model Report and its knowledge graph conversationally queryable.

Run it as:

    python -m reagent.mcp

Why a hand-rolled JSON-RPC loop rather than the official SDK: the MCP wire protocol
is small — ``initialize``, ``tools/list``, ``tools/call``, plus notifications — and
the whole point of this server is that a teammate can point Claude at the repo with
no extra install beyond `pip install -e .`. An SDK dependency that fails to resolve
would defeat that.

Protocol notes that matter for correctness:

* Messages are newline-delimited JSON on stdin/stdout. **Nothing else may ever be
  written to stdout** — a stray ``print`` corrupts the stream and the client drops
  the connection with no useful error. All diagnostics go to stderr.
* Notifications (no ``id``) get no response. Replying to one is a protocol violation.
* A tool that fails should return a result with ``isError: true`` rather than a
  JSON-RPC error, so the model sees the message and can adapt. JSON-RPC errors are
  reserved for malformed requests.
"""

from __future__ import annotations

import contextlib
import json
import sys
import traceback
from collections.abc import Callable
from typing import Any

from reagent.mcp import tools as toolmod
from reagent.mcp import (
    tools_context,  # noqa: F401 — registers its @tool entries
    tools_parts,  # noqa: F401 — registers its @tool entries
)

SERVER_NAME = "reagent-report"
SERVER_VERSION = "0.1.0"
#: Echoed back to the client when it asks for something we do not recognise.
DEFAULT_PROTOCOL = "2025-06-18"
SUPPORTED_PROTOCOLS = {"2024-11-05", "2025-03-26", "2025-06-18"}

INSTRUCTIONS = """\
This server exposes a reagent pipeline run: its Model Reports, its knowledge graph, \
and structure-comparison tooling.

Start with `report_list` and `graph_overview` to see what exists. Use `graph_query` \
or `neighbors` to explore relationships, `explain_edge` to see the evidence behind \
any single assertion, and `compare_structures` to render two proteins side by side \
in 3D with their structural and pocket similarity computed.

Two things to keep in mind when relaying results. Similarity scores from \
`compare_structures` are sequence-guided estimates, not the output of a structural \
aligner, and every response says so — pass that caveat on rather than dropping it. \
And edges in the graph may carry `illustrative: true`, which means the number is a \
placeholder rather than a measurement; never present one as a finding."""


def _configure_streams() -> None:
    """Force UTF-8 on stdio.

    On Windows these default to the console codepage (cp1252), and the first
    non-Latin-1 character in a log line raises UnicodeDecodeError **in the client's
    reader thread**, not ours — so the failure looks like a client bug and is
    miserable to trace. stdout happens to be safe because ``json.dumps`` escapes
    non-ASCII, but relying on that is fragile.
    """
    for stream in (sys.stdout, sys.stderr, sys.stdin):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            # A stream that refuses to reconfigure (already detached, or not a
            # TextIOWrapper) is not fatal; the default encoding may still work.
            with contextlib.suppress(ValueError, OSError):
                reconfigure(encoding="utf-8", errors="replace")


def _log(msg: str) -> None:
    """Diagnostics to stderr only. stdout is the protocol channel."""
    print(f"[{SERVER_NAME}] {msg}", file=sys.stderr, flush=True)


class Server:
    def __init__(self) -> None:
        self.handlers: dict[str, Callable[[dict], Any]] = {
            "initialize": self._initialize,
            "ping": lambda _p: {},
            "tools/list": self._tools_list,
            "tools/call": self._tools_call,
            # Declared with empty results so a client that probes them gets a clean
            # answer instead of "method not found", which some clients treat as fatal.
            "resources/list": lambda _p: {"resources": []},
            "prompts/list": lambda _p: {"prompts": []},
        }
        self.protocol = DEFAULT_PROTOCOL

    # -- protocol methods ------------------------------------------------

    def _initialize(self, params: dict) -> dict:
        asked = params.get("protocolVersion")
        self.protocol = asked if asked in SUPPORTED_PROTOCOLS else DEFAULT_PROTOCOL
        client = (params.get("clientInfo") or {}).get("name", "unknown")
        _log(f"initialize from {client} (protocol {asked} -> {self.protocol})")
        return {
            "protocolVersion": self.protocol,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            "instructions": INSTRUCTIONS,
        }

    def _tools_list(self, _params: dict) -> dict:
        return {"tools": toolmod.tool_schemas()}

    def _tools_call(self, params: dict) -> dict:
        name = params.get("name")
        args = params.get("arguments") or {}
        fn = toolmod.REGISTRY.get(name)
        if fn is None:
            return {
                "isError": True,
                "content": [{
                    "type": "text",
                    "text": (
                        f"No tool named {name!r}. Available: "
                        f"{', '.join(sorted(toolmod.REGISTRY))}"
                    ),
                }],
            }
        try:
            text = fn(**args)
        except TypeError as exc:
            # Almost always a wrong or missing argument; say which, and show the schema.
            schema = next((t for t in toolmod.tool_schemas() if t["name"] == name), {})
            return {
                "isError": True,
                "content": [{
                    "type": "text",
                    "text": (
                        f"{name} was called with arguments it does not accept: {exc}\n\n"
                        f"Expected input schema:\n"
                        f"{json.dumps(schema.get('inputSchema', {}), indent=2)}"
                    ),
                }],
            }
        except Exception as exc:
            _log(f"tool {name} failed: {traceback.format_exc()}")
            return {
                "isError": True,
                "content": [{
                    "type": "text",
                    "text": f"{name} failed: {type(exc).__name__}: {exc}",
                }],
            }
        return {"content": [{"type": "text", "text": text}]}

    # -- transport -------------------------------------------------------

    def handle(self, msg: dict) -> dict | None:
        """Dispatch one message. Returns None for notifications."""
        method = msg.get("method")
        msg_id = msg.get("id")
        is_notification = msg_id is None

        if method is None:
            return None  # a response, not a request; we send none, so ignore it.

        handler = self.handlers.get(method)
        if handler is None:
            if is_notification:
                return None  # unknown notifications are ignored by design
            return {
                "jsonrpc": "2.0", "id": msg_id,
                "error": {"code": -32601, "message": f"method not found: {method}"},
            }

        try:
            result = handler(msg.get("params") or {})
        except Exception as exc:
            _log(f"handler {method} raised: {traceback.format_exc()}")
            if is_notification:
                return None
            return {
                "jsonrpc": "2.0", "id": msg_id,
                "error": {"code": -32603, "message": f"internal error: {exc}"},
            }

        if is_notification:
            return None
        return {"jsonrpc": "2.0", "id": msg_id, "result": result}

    def serve(self, stdin=None, stdout=None) -> int:
        if stdin is None and stdout is None:
            _configure_streams()
        stdin = stdin or sys.stdin
        stdout = stdout or sys.stdout
        _log(f"ready with {len(toolmod.REGISTRY)} tools")
        for line in stdin:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError as exc:
                _log(f"unparseable line ({exc}); ignoring")
                continue
            # A client may batch requests in a JSON array.
            batch = msg if isinstance(msg, list) else [msg]
            for item in batch:
                if not isinstance(item, dict):
                    continue
                reply = self.handle(item)
                if reply is not None:
                    stdout.write(json.dumps(reply) + "\n")
                    stdout.flush()
        _log("stdin closed; exiting")
        return 0


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if "--list-tools" in argv:
        # A cheap way to check the server is wired up without an MCP client.
        for t in toolmod.tool_schemas():
            print(f"{t['name']}\n    {t['description'].splitlines()[0]}")
        return 0
    return Server().serve()


if __name__ == "__main__":
    raise SystemExit(main())
