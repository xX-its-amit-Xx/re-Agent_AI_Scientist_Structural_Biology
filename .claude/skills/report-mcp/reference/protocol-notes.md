# The MCP subset this server implements

Written down because the protocol is small enough to implement by hand but has a few
sharp edges that produce failures with no useful error message.

## Transport

Newline-delimited JSON-RPC 2.0 on stdin and stdout. One JSON object per line, no
framing headers, no Content-Length. A client may send a JSON **array** of requests as
a batch, so the read loop handles both.

**stdout is the protocol channel and nothing else may touch it.** This is the single
most common way to break an MCP server: a `print` for debugging, a library that logs
to stdout, a warning from a dependency. The client sees a line that is not valid
JSON-RPC and typically disconnects without saying why. All diagnostics go to stderr.

**Force UTF-8 on the streams.** On Windows stdio defaults to the console codepage
(cp1252 here), and the first character outside Latin-1 raises `UnicodeDecodeError`
**in the client's reader thread**. The traceback therefore points at the client, not
at you, which makes it a genuinely nasty afternoon. `_configure_streams()` calls
`reconfigure(encoding="utf-8", errors="replace")` on all three streams;
`.mcp.json` also sets `PYTHONUTF8=1` as a belt-and-braces measure.

Note that `json.dumps` escapes non-ASCII by default, so stdout would survive without
this. Do not rely on that — it is an implementation detail of the encoder.

## Methods implemented

### `initialize`

Request params carry `protocolVersion`, `clientInfo`, and `capabilities`. The reply:

```json
{
  "protocolVersion": "2025-06-18",
  "capabilities": { "tools": { "listChanged": false } },
  "serverInfo": { "name": "reagent-report", "version": "0.1.0" },
  "instructions": "..."
}
```

Echo back the client's requested version when it is one you support, otherwise
substitute your own. The server accepts `2024-11-05`, `2025-03-26`, and `2025-06-18`.

`instructions` is worth writing carefully. It is prepended to the model's context
and is where you say how the tools compose and what the caveats are. Ours states the
two things a relaying model must not forget: that similarity scores are estimates,
and that graph edges may carry placeholder numbers.

### `notifications/initialized`

A notification: **no `id`, so no reply**. Sending one is a protocol violation. The
read loop checks for a missing `id` and returns `None`, which the writer skips.

The same applies to any other notification, including ones you do not recognise —
unknown *notifications* are silently ignored, while unknown *requests* get a
`-32601` error.

### `tools/list`

```json
{ "tools": [ { "name": "...", "description": "...", "inputSchema": { ... } } ] }
```

`inputSchema` is a JSON Schema object. Set `additionalProperties: false` so a
mis-typed argument name fails loudly at the boundary rather than being silently
dropped and producing a wrong answer from a default.

The `description` is the routing signal — it is what the model reads to decide
whether to call the tool. Write it as a sentence about *what question it answers*,
not a summary of its implementation.

### `tools/call`

```json
{ "name": "compare_structures", "arguments": { "a": "pdb:1M13", "b": "pdb:1OSV" } }
```

Reply:

```json
{ "content": [ { "type": "text", "text": "..." } ], "isError": false }
```

**Tool failures return `isError: true` with the message in `content`, not a JSON-RPC
error.** The distinction matters: a result-with-isError reaches the model, which can
read the message and try something else. A JSON-RPC error is a transport-level
failure and some clients treat it as fatal. Reserve those for malformed requests.

A `TypeError` from calling a tool with wrong arguments gets special handling — the
reply includes the tool's input schema, because that is exactly what the model needs
in order to retry correctly.

### `resources/list` and `prompts/list`

Declared, returning empty arrays. A client that probes them gets a clean empty answer
instead of `method not found`, which some clients treat as a fault even when the
capability was never advertised.

### `ping`

Returns `{}`. Some clients use it as a keepalive.

## Verifying without a client

```bash
python -m reagent.mcp --list-tools
```

Or drive the protocol directly. The useful assertion is on the *count* of replies:

```python
msgs = [initialize, notifications_initialized, tools_list]   # 3 messages
# -> exactly 2 replies. If you get 3, you are answering the notification.
```

## Things that look like bugs and are not

**A tool returning "no such node" rather than raising.** Deliberate: the reply lists
candidate matches so the model can retry. A raised exception would tell it only that
something went wrong.

**`compare_structures` refusing on very dissimilar sequences.** Fewer than three
aligned residue pairs means a sequence-guided superposition genuinely cannot be
computed. Reporting that is correct; inventing a superposition would not be.

**A large response.** `compare_structures` returns a couple of thousand characters
including a pocket-residue table. That is the point — the model needs the specifics
to answer a follow-up without another round trip.

## Things that are bugs

- Anything on stdout that is not a protocol message.
- Replying to a notification.
- Returning a JSON-RPC error for a tool-level failure.
- Dropping the estimate caveat from a structure-comparison response.
- Rendering an `illustrative: true` edge without saying it is a placeholder.
