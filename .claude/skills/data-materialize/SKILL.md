---
name: data-materialize
description: >-
  Turn Dataset pointers in the knowledge graph into actual local files, on demand.
  Queries the graph for datasets matching a question, builds a costed fetch plan,
  surfaces anything gated or oversized for approval, then downloads, checksums,
  and caches — writing the retrieval provenance back onto the graph node.
  Use when a stage needs the bytes rather than the metadata, typically at the start
  of biochemical analysis.
  Trigger on: "download the data", "fetch the datasets", "pull that data locally",
  "materialize", "I need the actual numbers", or /data-materialize.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, WebFetch
---

# Data materialize

Stage 1 wrote down *where* every dataset lives. This skill fetches the few that a
question actually needs. The split exists because a broad discovery sweep finds
hundreds of candidates and downloading them all would cost tens of gigabytes to
answer questions about three — and because fetching is the step that fails, so it
should fail one node at a time rather than aborting a harvest.

## Guard rails

- **Never fetch without a stated purpose.** `FetchPlan.purpose` is required and
  must name the question the data answers. "Might be useful" is how a cache becomes
  50 GB of files nobody opened.
- **Cost the plan and show it before downloading.** Print `FetchPlan.summary()`.
  If it exceeds `max_total_bytes`, stop and ask rather than trimming silently.
- **Surface gated datasets, never skip them quietly.** `FetchPlan.blocked()` lists
  the ones needing registration, an API key, or an application. Report them with
  their `fetch_hint` so a human can act. A silently-omitted dataset reads as
  "no data exists", which is a different and wrong conclusion.
- **Checksum and timestamp everything.** Write `sha256`, `retrieved_utc`, and
  `local_path` back onto the graph node. A URL alone is not provenance: the file
  behind it can change, and later you will need to know what was actually analysed.
- **Record failures as data.** A dead link gets `fetch_error` set on the node, not
  a silent retry loop. The next agent needs to know the link is dead.
- **Never commit fetched data.** `data/cache/` is gitignored. The graph is the
  index; the cache is disposable and rebuildable.
- **Check the licence before use, not after.** `Access.RESTRICTED` means read the
  terms and probably stop. Record the decision either way.

## Workflow

### Step 1 — Ask the graph, do not grep the filesystem

The whole point of Stage 1's data layer is that this is a query:

```python
store.query("""
    SELECT DISTINCT n.id, n.label, n.attrs_json
    FROM edges e
    JOIN nodes n ON n.id = e.dst AND n.type = 'Dataset'
    WHERE e.predicate = 'HAS_DATA' AND e.src IN (%s)
""" % ",".join("?" * len(entity_ids)), entity_ids)
```

Then filter in Python on the `DataRef` fields — `measures`, `access`, `size_bytes`,
`licence` — because those are what decide whether a dataset is worth fetching:

```python
from reagent.contracts import DataRef, MeasurementKind
refs = [DataRef.from_node_attrs(json.loads(r["attrs_json"])) for r in rows]
wanted = [r for r in refs
          if r.answers(MeasurementKind.BINDING_AFFINITY) and r.is_fetchable
          and (r.size_bytes or 0) < 500_000_000]
```

### Step 2 — Build and review the plan

```python
from reagent.contracts import FetchPlan
plan = FetchPlan(
    run_id=RUN, requested_by="pocket-anatomy",
    purpose="Map ligand functional groups onto pocket residues across the receptor family.",
    datasets=wanted, max_total_bytes=5_000_000_000,
)
print(plan.summary())
if not plan.within_budget():
    raise SystemExit("over budget — narrow the query or raise the cap deliberately")
```

### Step 3 — Fetch, verify, cache

Into `data/cache/<sanitised-dataset-id>/`. For each dataset: follow
`download_url` if present, else `url`; honour `fetch_hint` for anything needing an
API call or a key from the environment; verify the payload looks like its declared
`fmt` before trusting it — an HTML error page saved as `.csv` is the classic
silent failure, and it will parse as a one-column dataframe rather than raising.

Rate-limit politely and cache aggressively: never re-fetch a dataset whose
`sha256` already matches.

### Step 4 — Write provenance back to the graph

Update the `Dataset` node's attrs with `local_path`, `sha256`, `retrieved_utc`, or
`fetch_error`. Emit this as a normal `GraphDelta` so the update is append-only and
attributable like everything else.

### Step 5 — Report

`data.fetch_report` with: how many were requested, fetched, gated, and failed;
total bytes; and the per-dataset outcome. Put `n_fetched`, `n_failed`,
`n_gated`, and `total_bytes` in the Model Report `metrics`.

## Reading the data once it is local

Datasets from different sources will not share a schema — that is normal and it is
the consuming stage's job to harmonise. Two rules that save time:

- **Map every identifier back to a graph node id** before analysing. A CSV with a
  `target` column of gene symbols must be resolved to accessions, or you will
  silently join on the wrong protein.
- **Record the harmonisation as code, not as a one-off notebook cell.** The next
  dataset will need the same mapping, and an undocumented join is unreproducible.

## Anti-patterns

- **Fetching everything Stage 1 found.** That defeats the entire lazy design.
- **Fetching before the question is sharp.** The query is the cheap part; do it
  well and fetch three files instead of three hundred.
- **Trusting a file because it downloaded.** Verify format, row count against
  `n_records`, and that the entities you expected are present.
- **Leaving `retrieved_utc` unset.** The contract rejects a `local_path` without
  it, precisely because an unstamped cache file cannot be used as provenance.
