# The discover-now, fetch-later contract

Stage 1 records **where data lives**. A later stage downloads the few files it
actually needs. This document explains the split, the contract that encodes it,
and how each side holds up its end.

## Why not just download everything

Four reasons, in descending order of importance.

**Most of what discovery finds is never read.** A broad sweep across ChEMBL,
BindingDB, Zenodo, HuggingFace, GitHub, and old competition pages will surface
hundreds of candidate datasets for a moderately studied target. Perhaps five get
opened. Downloading all of them costs tens of gigabytes and hours of wall-clock to
answer questions about a handful, and on a machine where the working disk is
already near-full that cost is not abstract.

**The metadata is what supports graph reasoning.** The questions Stage 1 exists to
answer are answerable without the bytes: *Has anything been measured between this
chemotype and this receptor? Is there a co-crystal for this homolog? Does an
enrichment dataset exist for this library?* Those are metadata queries. Fetching
the file adds nothing to them, and the fetch cannot begin until the query has
already told you which file to want.

**Fetch is the step that fails.** Dead links, moved repositories, silently changed
files, registration walls, licence gates, rate limits. If discovery and fetch are
one operation, a broken link aborts a harvest. Separated, a broken link degrades
exactly one node — and the graph records the breakage, so the next agent does not
repeat the attempt.

**Provenance gets better, not worse.** A URL is not provenance for anything
mutable: the file behind it can change without notice. `retrieved_utc` plus a
`sha256` over the materialised copy pins exactly what was analysed. Deferring the
fetch to the moment of use means the recorded hash belongs to the version that
actually informed a conclusion.

## The contract

`reagent.contracts.data.DataRef` is the pointer. Its fields divide cleanly into
three groups, and which group a field belongs to tells you who writes it.

**Written at discovery, by `source-scout`.** Identity (`id`, `title`, `url`,
`download_url`); content description (`measures`, `fmt`, `n_records`,
`size_bytes`, `entities`, `columns`); usability (`access`, `licence`,
`fetch_hint`); and provenance (`discovered_by`, `source_locator`).

**Written at materialisation, by `data-materialize`.** `local_path`, `sha256`,
`retrieved_utc`, or on failure `fetch_error`.

**Never written.** The data itself. It lives in `data/cache/`, which is
gitignored. The graph is the index; the cache is disposable and rebuildable.

Two validators enforce the parts people skip:

- A `DataRef` whose `access` requires registration, an API key, or an application
  **must** carry a `fetch_hint`. Recording how to get in, while you are looking at
  the page that told you, costs seconds. Rediscovering it later costs the same
  work twice.
- A `DataRef` claiming a `local_path` **must** have a `retrieved_utc`. A cached
  file with no retrieval timestamp cannot function as provenance, so the contract
  refuses to pretend otherwise.

## The two fields that decide whether this works

Everything else is bookkeeping. These two are the ones that make a dataset
*findable by a question* rather than by a keyword.

### `entities`

Graph node ids the dataset covers, keyed by role:

```python
entities={
    "targets":   ["uniprot:O75469", "uniprot:Q14994"],
    "compounds": ["chembl:CHEMBL432657", "chembl:CHEMBL374478"],
    "assays":    ["assay:chembl:CHEMBL1613777"],
}
```

This is what turns "there might be data somewhere" into "there is data covering
*this* pair". It is also what lets the biochem stage ask its real question — which
is never "find me PXR data" but something closer to *give me every dataset
covering a compound in this chemotype cluster and a receptor in this family,
measuring binding affinity, open-access, under 500 MB*.

Populating it means resolving whatever identifiers the source uses onto our
namespaced node ids. That mapping is the work, and doing it at discovery time is
much cheaper than doing it after a download, when you have a dataframe full of
gene symbols and no idea which paralog is meant.

### `columns`

The field names, when they are discoverable without downloading — and they usually
are, from a dataset card, a README, a data dictionary, or the first few lines
served by a range request. Knowing that a table has `smiles`, `target_uniprot`,
`activity_type`, `value_nM` tells a downstream agent whether the file can answer
its question. Knowing only that the file is 4 MB of CSV does not.

## How a later stage materialises

The consuming stage queries the graph, filters on `DataRef` fields, builds a
costed `FetchPlan`, and only then downloads.

```python
from reagent.contracts import DataRef, FetchPlan, MeasurementKind

rows = store.query("""
    SELECT DISTINCT n.id, n.attrs_json
    FROM edges e JOIN nodes n ON n.id = e.dst AND n.type = 'Dataset'
    WHERE e.predicate = 'HAS_DATA' AND e.src = ?
""", (target_id,))

refs = [DataRef.from_node_attrs(json.loads(r["attrs_json"])) for r in rows]
wanted = [r for r in refs
          if r.answers(MeasurementKind.BINDING_AFFINITY)
          and r.is_fetchable
          and (r.size_bytes or 0) < 500_000_000]

plan = FetchPlan(
    run_id=RUN, requested_by="pocket-anatomy",
    purpose="Map ligand functional groups onto pocket residues across the family.",
    datasets=wanted, max_total_bytes=5_000_000_000,
)
print(plan.summary())        # shows total size, gated items, and budget status
```

`FetchPlan.purpose` is required and must name the question the data answers. This
is not ceremony: "might be useful" is precisely how a cache becomes fifty
gigabytes of files nobody opened. `FetchPlan.blocked()` lists the datasets needing
human action, with their hints, so they are surfaced rather than silently dropped —
a quietly omitted dataset reads as "no data exists", which is a different and
wrong conclusion.

## The graph edges that make it queryable

Four predicates carry the data layer. All are in the `DATA` or `EVIDENCE` visual
family and hidden by default in the renderer, because every entity has data
pointers and showing them all buries the science.

| Predicate | From | To | Answers |
|---|---|---|---|
| `HAS_DATA` | Protein / Compound / Assay | Dataset | "Where can I get numbers for this entity?" |
| `DATASET_COVERS` | Dataset | any entity | "What is inside this deposit?" |
| `MEASURED_BETWEEN` | Assay | the pair it measures | "What has been measured between this compound and this target?" |
| `DERIVED_FROM` | Dataset | Dataset or Paper | "Where did this deposit come from?" |

`HAS_DATA` and `DATASET_COVERS` are deliberately reciprocal rather than one
directed edge. Both directions get asked: an agent starting from a compound wants
its datasets, and an agent starting from a promising dataset wants to know what
else is in it and therefore what else it could answer.

`MEASURED_BETWEEN` is the one worth being careful about, because it is the edge
that supports the question the biochem stage actually asks. An `Assay` node with
`MEASURED_BETWEEN` edges to a compound and a target, plus a `HAS_DATA` edge to the
dataset holding the numbers, means a single join returns "the measurement exists,
here is what it measured, and here is where to get it".

## What good looks like

A `Dataset` node that a downstream agent can act on without any further discovery:

```python
DataRef(
    id="zenodo:10.5281/zenodo.XXXXXXX",
    title="Binding affinities for a nuclear-receptor ligand series",
    url="https://zenodo.org/records/XXXXXXX",
    download_url="https://zenodo.org/records/XXXXXXX/files/affinities.csv",
    measures=[MeasurementKind.BINDING_AFFINITY],
    fmt=DataFormat.CSV,
    n_records=1842,
    size_bytes=4_100_000,
    entities={"targets": ["uniprot:O75469"], "compounds": ["chembl:CHEMBL432657"]},
    columns=["smiles", "target_uniprot", "activity_type", "value_nM", "assay_id"],
    access=Access.OPEN,
    licence="CC BY 4.0",
    discovered_by="source-scout/zenodo",
    source_locator="pmc:PMC12690452#L512",
)
```

Note `source_locator`: the line in the paper that mentioned the deposit. That is
what lets someone check that this dataset is the one the paper meant, rather than a
similarly-named deposit by a different group.

## Failure modes, and what to do about them

**A fabricated identifier.** The most likely and most damaging failure of the
discovery step, because a plausible Zenodo DOI or GitHub path looks exactly like a
real one. **Verify that every URL resolves before writing the node.** If it does
not, still write the node, with `fetch_error` set — a recorded dead end is more
useful than a silent omission.

**An HTML error page saved as `.csv`.** The classic silent fetch failure: it
downloads, it has a `.csv` extension, and it parses as a single-column dataframe
rather than raising. Verify the payload matches its declared `fmt`, and check the
row count against `n_records`, before trusting a file.

**Joining on the wrong entity.** A table with a `target` column of gene symbols
will join happily and wrongly against the wrong paralog. Map every identifier back
to a graph node id before analysing, and write that mapping as reusable code
rather than a one-off cell.

**Fetching before the question is sharp.** The query is the cheap part. Spend the
effort there and download three files instead of three hundred.

**Recording a licence and then ignoring it.** `Access.RESTRICTED` means read the
terms and probably stop. Record the decision either way, so the next person does
not have to make it again.
