---
name: report-mcp
description: >-
  Make a finished Model Report and its knowledge graph conversationally
  interrogable, by serving them over MCP. Turns a static report into something a
  user can question — explore relationships, check the evidence behind any single
  assertion, and render two proteins side by side in interactive 3D with their
  structural and pocket similarity computed. Use when setting up, extending,
  debugging, or explaining the reagent-report MCP server.
  Trigger on: "MCP", "interactive report", "query the report", "serve the graph",
  "compare two proteins in 3D", "side by side structures", or /report-mcp.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
---

# Report MCP

A Model Report answers the questions its author thought to ask. A reader always has
others — *why is this protein connected to that one? show me them together. is that
number real?* Serving the report and its graph over MCP turns a finished artifact
into something a person can interrogate, which is the difference between a document
and a working instrument.

## Guard rails

- **NEVER write anything to stdout except protocol messages.** A single stray
  `print` corrupts the JSON-RPC stream and the client disconnects with no useful
  error. All diagnostics go to stderr via `_log`.
- **Force UTF-8 on stdio.** On Windows these default to the console codepage, and the
  first non-Latin-1 character raises `UnicodeDecodeError` **in the client's reader
  thread**, so the failure looks like a client bug. `_configure_streams()` handles
  it; do not remove it.
- **Never answer a notification.** A message with no `id` gets no response. Replying
  is a protocol violation.
- **Tool failures return `isError: true`, not a JSON-RPC error.** The model then sees
  the message and can adapt. JSON-RPC errors are for malformed requests only, and a
  client may treat one as fatal.
- **Every response carrying an estimate says so in the same sentence.** If the caveat
  sits in a separate field, the model relaying the answer will drop it. The
  structure-comparison numbers are sequence-guided estimates and every response
  repeats that.
- **Never render a placeholder as a finding.** Graph edges may carry
  `illustrative: true`, meaning the number was never measured. Every tool that
  surfaces such an edge prints a warning on the same line. This is the single most
  important behaviour in the server: an MCP that laundered placeholders into
  confident answers would be worse than no MCP.

## Installing it

`.mcp.json` at the repo root registers the server, so Claude Code picks it up when
started in this directory.

**The command must be the project venv's interpreter, by relative path**
(`.venv/Scripts/python.exe` on Windows, `.venv/bin/python` on macOS and Linux). This
is the one configuration mistake worth spelling out, because its failure mode is
silent: `python` on PATH is often a different interpreter with reagent not installed,
the server never starts, and the client simply shows no tools without saying why.
`uv run` is not a safe substitute — it can resolve to a venv in a parent directory.

Verify independently of any client:

```bash
python -m reagent.mcp --list-tools          # names and one-line descriptions
```

If that works but the client shows nothing, the problem is the command in
`.mcp.json`, not the server.

To drive it by hand, pipe newline-delimited JSON-RPC to stdin:

```bash
printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","clientInfo":{"name":"cli","version":"1"},"capabilities":{}}}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' \
  | python -m reagent.mcp
```

The server runs with the repo as its working directory and finds the graph at `kg/`
or `kg/demo/`. Every tool takes an optional `kg` argument to point elsewhere.

## The tools

| Tool | Answers |
|---|---|
| `report_list` | What runs and reports exist? Start here. |
| `report_read` | What does this report say, with citations? |
| `graph_overview` | What is in the graph, and how much of it is cited? |
| `graph_search` | What is this thing's namespaced id? |
| `neighbors` | What is this entity connected to, and how strongly? |
| `explain_edge` | Why is X connected to Y, and who says so? |
| `graph_query` | Anything else — read-only SQL. |
| `axis_neighborhood` | Where do the similarity axes agree and disagree? |
| `compare_structures` | Show me these two proteins together in 3D. |
| `structure_info` | What is in this structure, and what lines its pocket? |
| `list_figures` | What has already been drawn? |
| `kg_audit` | Can I trust these numbers? |

## What `compare_structures` actually does

This is the tool worth understanding, because it is doing real work rather than
formatting a database row.

1. **Fetches both structures** by graph node id — `pdb:1M13` from RCSB,
   `uniprot:O75469` from AlphaFold DB, or `file:path.pdb`. Cached under
   `data/cache/structures/`, so repeated questions cost nothing.
2. **Aligns their sequences** with Needleman-Wunsch (affine gaps), giving a residue
   correspondence.
3. **Superposes** the matched C-alpha pairs with Kabsch, then iteratively discards
   pairs further apart than 5 Å and re-superposes. Without that trimming a single
   divergent loop drags the whole fit and both the RMSD and the visual overlay
   mislead.
4. **Reports** RMSD over the surviving core, a TM-score, sequence identity, and
   coverage.
5. **Compares the pockets** — the part a biochemist actually wants. It finds every
   residue within 6 Å of *any ligand atom* in each structure (not the ligand
   centroid, which badly under-counts for anything larger than a fragment), maps one
   pocket onto the other through the alignment, and reports which residues
   correspond, which are the same amino acid, and which are unique to each.
6. **Renders an interactive page**: side-by-side with linked cameras, plus a
   superposed overlay. Backbone colour encodes correspondence quality rather than
   identity, because you can already tell the two apart by position.

### The honesty requirement

**This is a sequence-guided superposition, not a structural alignment.** It assumes
the sequence alignment found the right residue correspondence. That assumption is
safe for homologs — the case a receptor-family comparison is almost always in — and
**wrong** for structurally similar proteins with unrelated sequences, because a
sequence alignment cannot find that correspondence at all. Real structural aligners
search over correspondences instead of inheriting one.

So the TM-score is a **lower bound** on what TM-align would report, every result
carries `is_estimate` and a caveat list, and the tool description tells the model to
pass the caveat on. If Foldseek or TM-align is available, prefer it and record which
ran. The point of this implementation is that a comparison is always *possible*, not
that it is authoritative.

Below roughly 20-25 % sequence identity the tool adds a louder caveat, because at
that point the correspondence itself may be wrong rather than merely the fit.

## Worked example

A user reading a Stage 1 report notices the target is linked to another receptor and
asks to see them together. The sequence of calls:

```
neighbors(node_id="uniprot:O75469", predicate="SIMILAR_FOLD_TO")
  -> lists CAR, VDR, FXR ... each flagged ILLUSTRATIVE, so the scores are placeholders

explain_edge(src="uniprot:O75469", predicate="SIMILAR_FOLD_TO", dst="uniprot:Q96RI1")
  -> confirms: no citations, illustrative attrs. The graph does not actually know this.

compare_structures(a="pdb:1M13", b="pdb:1OSV",
                   label_a="PXR (NR1I2)", label_b="FXR (NR1H4)")
  -> measures it for real: TM 0.643, RMSD 2.03 A over 146 residues, 29% identity,
     14 corresponding pocket residues of which 4 are identical, and a 3D page.
```

That progression is the server working as intended: the graph proposes, the
comparison measures, and the audit trail makes clear which is which.

## Adding a tool

Register with the `@tool` decorator in `reagent/mcp/tools.py`, giving a name, a
description written for a model to route on, and a JSON Schema with
`additionalProperties: false`. Then follow the four rules that make a tool usable
rather than merely callable:

- **Return prose with numbers in it**, not raw JSON. A model reads the text and
  relays it; a JSON wall gets summarised badly and the caveats get lost.
- **Suggest the next call.** Ending with the two or three tools that naturally follow
  turns a flat list into a workflow.
- **Fail with the fix.** The model's next action is decided entirely by the error
  text, so name what was wrong and what to try. `neighbors` on an unknown id returns
  candidate matches rather than "not found".
- **Say when a number is a placeholder**, on the same line as the number.

## Debugging

The failure modes, in the order you will meet them:

- **Client shows no tools.** Two causes, in order of likelihood. First, the command
  in `.mcp.json` is not the venv interpreter, so the process dies on
  `ModuleNotFoundError: No module named 'reagent'` before saying anything. Second, a
  stdout violation — something printed outside the protocol. Run
  `python -m reagent.mcp --list-tools` to tell them apart: if that works, it is the
  command; if it fails, it is the code.
- **Client disconnects mid-session.** Look at stderr. An unhandled exception in
  `serve()` rather than in a tool will do this; tools are individually wrapped.
- **`UnicodeDecodeError` in the client.** `_configure_streams()` was removed or the
  environment overrode it. Set `PYTHONUTF8=1`, which `.mcp.json` already does.
- **`compare_structures` cannot fetch.** A UniProt accession with no AlphaFold model
  fails; use an experimental `pdb:` id. A cached file that is empty or truncated will
  parse to zero residues — delete it from `data/cache/structures/` and retry.
- **Superposition raises "too dissimilar".** Fewer than three aligned residue pairs.
  These sequences genuinely cannot be compared this way; that is the correct answer,
  not a bug.

## References

- [protocol-notes.md](reference/protocol-notes.md) — the MCP subset implemented, message shapes, and the mistakes that break a client
