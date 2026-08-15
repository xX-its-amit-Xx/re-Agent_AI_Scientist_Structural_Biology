---
name: source-scout
description: >-
  Find what the papers do not contain. Sweeps patents, preprints, blog posts,
  Substack, LinkedIn and forum threads, GitHub repositories, Zenodo and Figshare
  deposits, HuggingFace datasets, and old Kaggle or benchmark competitions, then
  records each find as a graph node — datasets as metadata-plus-URL pointers that
  a later stage materialises only if it needs the bytes.
  Use alongside literature-harvest whenever coverage matters, when a needed dataset
  might exist somewhere unindexed, or when the peer-reviewed record is thin.
  Trigger on: "find the data", "is there a dataset", "search GitHub", "patents",
  "grey literature", "Kaggle", "Zenodo", "what else is out there",
  or /source-scout.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, Agent, WebSearch, WebFetch, Skill
---

# Source scout

Peer-reviewed literature is a biased sample of what is known. It systematically
omits negative results, parameter choices, engineering detail, and — most
importantly for us — **the data itself**. This skill covers the rest of the
record.

It pairs with `literature-harvest`: that skill owns the indexed full-text corpora
through Paperclip, this one owns everything Paperclip cannot see.

## Guard rails

- **Paperclip cannot search patents** despite what its help text says. Use
  WebSearch against Google Patents, Espacenet, or Lens.org and record findings as
  `SourceType.PATENT` with the publication number as the locator.
- **Record datasets, do not download them.** Write a `Dataset` node carrying a
  `DataRef` — URL, format, size, licence, access mode, what it measures, which
  graph entities it covers, and the fetch hint. Materialisation belongs to the
  stage that needs the bytes. See
  [lazy-data.md](reference/lazy-data.md) for why this split matters.
- **Write the `fetch_hint` while you know it.** The API call, the CLI command, the
  env var holding the key. A dataset behind a registration wall with no hint costs
  the next agent the same discovery work you just did, and the contract rejects it.
- **Grey sources are grounded but not sufficient.** A blog post or GitHub issue is
  real evidence — often the *only* record of a failure mode. But
  `Confidence.ESTABLISHED` requires at least one reviewed or structured-database
  source, and the contract enforces it. Cite grey freely at `supported` and below.
- **Attribute and date everything.** A LinkedIn post is evidence about what one
  person claimed on one day. Capture the author, the date, and the exact claim;
  never launder it into an unattributed assertion.
- **Never treat a repository's README as a measurement.** A repo claiming
  state-of-the-art performance is a claim, not a result. Look for the eval script
  and the held-out split, and if they are absent, record that.
- **Respect licences.** Record the licence on every `DataRef`. A dataset we may
  not use is still worth a node with `Access.RESTRICTED` — it stops rediscovery
  and it documents why we did not use it.

## Where to look, and what each source uniquely yields

| Source | Uniquely contains | How to search |
|---|---|---|
| **Patents** (Google Patents, Espacenet, Lens) | industrial methods and compound series never published; assay conditions in examples | WebSearch `site:patents.google.com <target> <assay>`; read the Examples section, that is where the data hides |
| **GitHub / GitLab** | working parameters, real failure modes in issues, unpublished data in `data/` | search code and issues, not just repos; a closed issue is often the honest limitations section |
| **Zenodo / Figshare / OSF / Dryad** | supplementary data for papers, often larger than the paper implies | search by target name, DOI of the paper, and author name |
| **HuggingFace** | model checkpoints and precomputed prediction sets | `hub_repo_search` for datasets and models; check the dataset card for provenance |
| **Kaggle / benchmark competitions** | curated splits, leaderboards, and the winners' write-ups | search competitions by domain; the discussion forum and top solution notebooks are the real prize |
| **Lab blogs / Substack / company engineering posts** | why something was abandoned; practical defaults | WebSearch the method name plus "we tried", "didn't work", "lessons" |
| **LinkedIn / X / forums / Discord recaps** | in-progress work, conference gossip, tool-choice reality | WebSearch by author and method; treat as `SourceType.SOCIAL` and attribute precisely |
| **Tool documentation and release notes** | breaking changes, known limitations, sane defaults | read the changelog; a silently-changed default has broken real pipelines |
| **Conference talks and posters** | results 12+ months ahead of the paper | search the programme and any recording |
| **Structured databases** (ChEMBL, BindingDB, PubChem, PDBe-KB, Open Targets) | the actual measurements, queryable | use the MCP connectors and APIs; these give `Assay` nodes with real numbers |

## Workflow

### Step 1 — Enumerate the entities to scout for

Take the graph's current nodes — the target, its neighbours from
`target-neighborhood`, and the test compounds — and scout **per entity and per
pair**. The high-value query is not "PXR data" but "is there any measurement
between *this compound class* and *this receptor*", because that pair is what the
biochem stage will ask the graph.

### Step 2 — Fan out one subagent per source class

Parallel, one per row of the table above, each returning `DataRef` JSON plus
`Evidence` records. Give every scout the same output schema and tell it that
returning nothing is an acceptable answer — a scout under pressure to produce
will invent a plausible Zenodo DOI.

**Verify every URL resolves before writing the node.** A fabricated DOI is worse
than no node, and this is the most likely failure mode of this entire skill. If a
URL 404s, record it with `fetch_error` set so nobody retries it.

### Step 3 — Build the data layer of the graph

For each dataset found:

```python
from reagent.contracts import Access, DataRef, DataFormat, MeasurementKind, Node, NodeType, Edge, Predicate

ref = DataRef(
    id="zenodo:10.5281/zenodo.XXXXXXX",
    title="...",
    url="https://zenodo.org/records/XXXXXXX",
    measures=[MeasurementKind.BINDING_AFFINITY],
    fmt=DataFormat.CSV,
    n_records=1842,
    size_bytes=4_100_000,
    entities={"targets": ["uniprot:O75469"], "compounds": ["chembl:CHEMBL432657"]},
    columns=["smiles", "target_uniprot", "activity_type", "value_nM"],
    access=Access.OPEN,
    licence="CC BY 4.0",
    discovered_by="source-scout/zenodo",
    source_locator="pmc:PMC12690452#L512",
)
node = Node(id=ref.id, type=NodeType.DATASET, label=ref.title,
            attrs=ref.to_node_attrs(), asserted_by="source-scout")
```

Then wire it up so it is findable:

- `HAS_DATA` from each covered protein/compound/assay **to** the dataset.
- `DATASET_COVERS` from the dataset to every entity it contains.
- `MEASURED_BETWEEN` from an `Assay` node to the pair it measures — this is the
  edge that answers "what has been measured between this compound and this target".
- `DERIVED_FROM` to the paper or parent dataset it came from.
- `SUPPORTED_BY` to the source that told us it exists.

`columns` and `entities` are the fields that make the graph useful without a
download. Fill them even when it takes a little reading — they are the difference
between "there might be data" and "there is data with these fields for this pair".

### Step 4 — Enrich the similarity edges with multiple metrics

An edge between two entities should accumulate **all** the evidence for that
relationship, not one number. `Edge.attrs` is a dict and the store *merges* attrs
when the same triple is asserted twice, so several scouts can each contribute a
metric to the same edge:

```
uniprot:O75469 --SIMILAR_FOLD_TO--> uniprot:Q14994
  attrs: {tm_score: 0.87, rmsd: 1.9, aligned_len: 241, sae_feature_overlap: 0.81,
          shared_pocket_residues: 19, shared_functional_groups: ["carbonyl", "aryl"]}
```

The renderer draws thickness from the axis's declared `score_key`; the rest are
visible on hover and queryable in SQL. So adding metrics costs nothing visually
and makes the graph much richer for the downstream agent. When metrics *disagree*
— high fold similarity, low pocket similarity — that disagreement is a finding.

### Step 5 — Report coverage honestly

The Model Report must state, per entity or pair: what data exists, what is
open-access, what is gated, and **what we looked for and did not find**. The
absence of any measurement between a compound class and the target is one of the
most decision-relevant facts Stage 1 can hand over, and it is invisible unless you
write it down.

Put the counts in `metrics`: `n_datasets_found`, `n_open_access`,
`n_gated`, `n_dead_links`, `pairs_with_no_data`.

## Required visuals

- **Data availability matrix**: entities (or pairs) x measurement kind, cell
  shaded by how many datasets exist and whether they are open. The holes in this
  figure are the point.
- **Source-type breakdown**: how much of what we know comes from reviewed papers
  versus patents, repos, and grey sources. A knowledge graph resting mostly on
  blog posts is a real risk and should be visible, not buried.

## Handoff

`kg.dataset_nodes` and `data.availability` — plus, for the biochem stage, the
resolved query it will actually run:

> "Give me every dataset covering a compound in this chemotype cluster and this
> receptor family, measuring binding affinity, open-access, under 500 MB."

Stage 2 turns that into a `FetchPlan`, reviews the total size, and only then
downloads. See [lazy-data.md](reference/lazy-data.md).

## References

- [lazy-data.md](reference/lazy-data.md) — the discover-now / fetch-later contract, and how Stage 2 materialises
- [source-recipes.md](reference/source-recipes.md) — concrete query templates per source, with API endpoints
- [grey-evidence.md](reference/grey-evidence.md) — how to cite a blog post or a LinkedIn claim defensibly
