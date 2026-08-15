"""MCP server exposing a pipeline run to a coding agent.

Run with ``python -m reagent.mcp``. Register it in ``.mcp.json`` so Claude Code picks
it up; see ``.claude/skills/report-mcp/SKILL.md``.
"""

from .server import Server, main

__all__ = ["Server", "main"]
