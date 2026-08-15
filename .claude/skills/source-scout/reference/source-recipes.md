# Source recipes — endpoints, query syntax, and what to extract

Concrete recipes for each source class the scout sweeps. Every entry gives the
endpoint or query syntax, which fields map onto which `DataRef` fields, and the
characteristic pitfall of that source.

**Verification status.** API surfaces move. Where an endpoint is marked *verify
before relying on this*, treat the shape as a starting point and confirm against the
provider's current documentation before building a fetch path on it. Nothing in
this file should be trusted as live without a request that returns 200.

## The extraction discipline

Every recipe ends in the same place: a `DataRef` written into a `Dataset` node.
Before the per-source detail, here is what each `DataRef` field is *for*, because
scouts routinely fill the easy ones and skip the two that make the graph useful.

| Field | Where it comes from | Why it matters |
|---|---|---|
| `id` | `<source>:<accession>` — the validator rejects an id with no colon | Namespacing is what stops a Zenodo record and a Figshare article colliding |
| `url` | the landing page, always resolvable | This is what a human opens |
| `download_url` | the direct file link when it differs | Saves the next agent a scrape |
| `measures` | read the description; empty means "we could not tell", not "nothing" | Decides whether the dataset can answer a question at all |
| `n_records`, `size_bytes` | file listings, dataset viewers, record metadata | `FetchPlan` cannot cost a sweep without these, and `unknown_size_count()` exists because they are so often missing |
| `entities` | the hardest field, and the one that makes the dataset findable | Without it the graph can say "data exists somewhere" but not "data exists for this pair" |
| `columns` | file previews, dataset viewer APIs, README tables, the paper's methods | Turns "there might be data" into "there is data with these fields" |
| `access`, `licence` | terms pages, record metadata, repository defaults | `is_fetchable` is computed from `access`; a restricted dataset still deserves a node |
| `fetch_hint` | write it now, while you know it | The validator **requires** it for `api_key`, `registration`, and `request` access |
| `source_locator` | where we learned the dataset exists | The provenance chain back to the paper or issue that mentioned it |

Two of these are worth the extra minutes every time. `entities` is what the
downstream query actually filters on, and `columns` is what tells a later stage
whether the file contains the readout it needs. A node with a URL and nothing else
is barely better than a bookmark.

---

## Patents

Patents contain compound series, assay conditions, and measured activity data that
were never published anywhere else, because filing is compulsory for protection and
publishing is not. They are the highest-yield underused source in this whole file.

**Paperclip cannot search patents.** This is verified against the live tool: the
`patents` value appears in Paperclip's `-s/--source` help string but the tool
returns `Patents sources are not available.` Do not build a patent path through
Paperclip. Patents must go through `WebSearch`, `WebFetch`, or a patent office API.

### Google Patents

There is no supported public search API. Search through `WebSearch` and read
through `WebFetch`.

```
WebSearch: site:patents.google.com <target name> <assay type> IC50
WebSearch: site:patents.google.com "<compound scaffold>" "pregnane X receptor"
WebSearch: site:patents.google.com <assignee> <target> after:2018
```

Landing page for one document, which `WebFetch` renders usefully because Google
Patents serves the full text as HTML:

```
https://patents.google.com/patent/US11123456B2/en
https://patents.google.com/patent/WO2019123456A1/en
```

A results page can also be fetched directly, and the query syntax is visible in the
URL, which makes it composable:

```
https://patents.google.com/?q=(%22nuclear+receptor%22)&q=IC50&after=priority:20180101
```

Google also publishes a bulk patent corpus as a BigQuery public dataset under the
`patents-public-data` project, which is the right tool for a systematic sweep
rather than a targeted lookup. *Verify the dataset and table names before relying on
this*; they have been reorganised more than once.

Avoid the undocumented `xhr/query` endpoint that the site's own front end calls. It
is not a published interface, it changes without notice, and using it programmatically
is a poor bet.

### Espacenet and the EPO Open Patent Services

Espacenet's web interface accepts a structured query in the URL:

```
https://worldwide.espacenet.com/patent/search?q=ti%3D%22nuclear%20receptor%22%20AND%20ab%3DIC50
```

The programmatic route is the EPO's Open Patent Services, a REST API with OAuth2
and a free tier. *Verify the version path — it has been 3.1, 3.2, and later — and
the current quota before relying on this.*

```bash
# Token: Basic auth with your consumer key and secret
curl -s -X POST https://ops.epo.org/3.2/auth/accesstoken \
  -u "$EPO_KEY:$EPO_SECRET" \
  -d grant_type=client_credentials

# Search, CQL in the q parameter
curl -s -H "Authorization: Bearer $TOKEN" \
  'https://ops.epo.org/3.2/rest-services/published-data/search?q=ta%3D%22pregnane%20X%22&Range=1-25'
```

CQL field codes worth knowing: `ti` title, `ab` abstract, `ta` title or abstract,
`txt` full text where available, `pa` applicant, `in` inventor, `pn` publication
number, `ap` application number, `pr` priority, `ipc` and `cpc` classification, `pd`
publication date. Boolean operators and proximity operators are supported.

### Lens.org

Lens exposes a patent search API at `https://api.lens.org/patent/search` taking a
POST body and a Bearer token, but the token requires an approved institutional or
paid arrangement. *Verify access before planning around it.* The web interface is
usable without it and is good at family and citation views.

### Where the data actually is, inside a patent

This is the part that gets missed. A patent has three regions and they are not
equally useful.

- **The claims** define legal scope. They contain Markush structures — a scaffold
  with enumerated variable positions — and almost no data. Reading claims to find
  measurements is wasted effort, and treating a Markush claim as a compound list
  will produce a combinatorial explosion of molecules that were never made.
- **The specification** contains the background, the general method, and the
  assay protocol. This is where buffer composition, cell line, incubation time, and
  readout are stated, often in more operational detail than a paper's methods
  section, because the patent must enable a skilled reader to reproduce it.
- **The Examples section** is where the measurements are. Look for headings
  "Examples", "Experimental", "Biological Examples", "Assay Results", and for
  numbered tables. Individual compounds are reported by example number with
  measured values, frequently as activity bands ("A: less than 10 nM; B: 10 to 100
  nM") rather than point values. That banding is still data and is worth recording.

Record patents as `SourceType.PATENT` with the publication number as the
`Evidence.locator` — for example `US11123456B2`, not a URL, because the number is
stable and the URL is not.

**Characteristic pitfalls.**

- **Family duplication.** The same disclosure is published as a WO application, then
  as regional and national filings, each with its own number. Counting these as
  independent sources inflates apparent support enormously. Deduplicate by simple
  family (the DOCDB family) before treating patents as independent evidence, and
  note in the `Evidence` which family member you actually read.
- **Activity bands, not values.** Extracting "A" from a banded table into a numeric
  affinity field is a fabrication. Record the band verbatim in the excerpt and put
  the interpretation in `notes`.
- **Selective reporting.** A patent reports the compounds that support the claims.
  The absence of a compound from the Examples is not a negative result.
- **No structured identifiers.** Compounds appear as names, example numbers, or
  drawn structures, not as database identifiers. Mapping them into `entities`
  requires name resolution, and the honest answer is often to record the example
  number and note that the mapping is unresolved.

---

## GitHub and GitLab

Repositories contain the parameters that papers omit, and issue trackers contain
the honest limitations section. A closed issue titled "fails silently on inputs
with more than one chain" is frequently the only public record of a failure mode.

### REST search endpoints

Base `https://api.github.com`. Send these headers on every call:

```
Accept: application/vnd.github+json
Authorization: Bearer $GITHUB_TOKEN
X-GitHub-Api-Version: 2022-11-28
```

```bash
# Repositories
curl -s -H "Authorization: Bearer $GITHUB_TOKEN" \
  'https://api.github.com/search/repositories?q=cofolding+pose+language:python&sort=stars&per_page=50'

# Code inside files — requires authentication, and searches default branches only
curl -s -H "Authorization: Bearer $GITHUB_TOKEN" \
  'https://api.github.com/search/code?q=lddt_pli+in:file+extension:py'

# Issues and pull requests
curl -s -H "Authorization: Bearer $GITHUB_TOKEN" \
  'https://api.github.com/search/issues?q=repo:owner/name+state:closed+%22does+not+converge%22'

# A repository's file tree, to find data/ without cloning
curl -s -H "Authorization: Bearer $GITHUB_TOKEN" \
  'https://api.github.com/repos/owner/name/git/trees/main?recursive=1'

# Releases, which is where large assets usually live
curl -s 'https://api.github.com/repos/owner/name/releases'
```

*Verify before relying on this:* GitHub has been migrating issue search toward a
newer "advanced search" surface and has deprecation notices on parts of
`/search/issues`; the code search endpoint has never covered everything the web UI
covers. When the API result looks thin, check the web UI for the same query before
concluding nothing exists.

Useful qualifiers across all three search endpoints: `repo:owner/name`,
`org:`, `user:`, `language:`, `path:`, `filename:`, `extension:`, `in:file`,
`in:path`, `size:`, `state:open|closed`, `label:`, `author:`, `created:>2024-01-01`,
`updated:>2025-01-01`, `is:issue`, `is:pr`, `stars:>50`, `fork:true`.

Rate limits are tight on search — roughly 30 requests per minute authenticated and
10 unauthenticated, against a separate budget from the core API. Read
`X-RateLimit-Remaining` and back off rather than retrying blind.

### Search strategy

Search **code and issues, not just repositories**. Repository search finds projects
whose README mentions your term; code search finds the file where a parameter was
actually set, and issue search finds where it broke. In practice the ordering that
works is: find candidate repositories by topic, then search issues within them for
the failure vocabulary — "does not", "fails", "silently", "workaround",
"deprecated", "known limitation", "not supported".

Also check, per repository: the releases page for data assets, `.github/workflows`
for what the maintainers actually test, and the git history of the config or default
parameters, because a silently changed default has broken real pipelines and the
commit message is the only record.

### Extraction

| `DataRef` field | Source |
|---|---|
| `id` | `github:owner/repo#path/to/file.csv` |
| `url` | the blob page, `https://github.com/owner/repo/blob/<sha>/<path>` — pin the commit sha, not `main` |
| `download_url` | `https://raw.githubusercontent.com/owner/repo/<sha>/<path>`, or the release asset URL |
| `size_bytes` | the tree API's `size` field, or the release asset's `size` |
| `columns` | fetch the first few kilobytes of a CSV with a Range request and read the header |
| `licence` | the repository `LICENSE` file, **not** the language of the README |
| `access` | `open` for a public repo; `api_key` if you needed a token, with the token env var in `fetch_hint` |

**Characteristic pitfalls.**

- **`main` is not a version.** A URL pointing at a branch resolves to different bytes
  next week. Pin the commit sha in both `url` and `download_url`. This is the same
  chain-of-custody requirement that puts `sha256` on a materialised `DataRef`.
- **A README is a claim, not a measurement.** A repository asserting
  state-of-the-art performance has asserted it. Look for the eval script, the
  held-out split definition, and the command that reproduces the number. If they are
  absent, record that absence — see [grey-evidence.md](grey-evidence.md).
- **Repository licence does not always cover the data.** A permissively licensed
  codebase can contain a `data/` directory that was redistributed without rights.
  Check for a separate data licence or a provenance note, and default to
  `Access.UNKNOWN` with a note rather than assuming.
- **Large files may be Git LFS pointers.** A 132-byte file that looks like your
  dataset is an LFS pointer, and the raw URL returns the pointer, not the content.

---

## Zenodo

The default deposit target for European-funded work and for conference artefacts.
Everything gets a DOI, which makes it citable and makes fabricated Zenodo DOIs
unusually dangerous — see the verification section.

```bash
# Search. `q` accepts an Elasticsearch-style query string.
curl -s 'https://zenodo.org/api/records?q=%22pregnane%20X%20receptor%22&size=25&page=1&sort=bestmatch'

# Restrict to datasets
curl -s 'https://zenodo.org/api/records?q=binding+affinity&type=dataset&size=50'

# One record
curl -s 'https://zenodo.org/api/records/1234567'
```

Useful parameters: `q`, `size`, `page`, `sort` (`bestmatch`, `mostrecent`),
`type` (`dataset`, `software`, `publication`, `poster`, `presentation`),
`communities`, `all_versions`. A personal access token can be passed as
`access_token` or as a Bearer header, and raises rate limits.

*Verify before relying on this:* Zenodo migrated to InvenioRDM, and the record JSON
shape changed in that move — in particular how files and licence metadata are
nested. Fetch one record and inspect it before writing a parser.

Fields to extract: `doi` and `links.self_html` for identity and landing page;
`title`; `metadata.description` for `measures`; the file entries for `key`, `size`,
`checksum`, and a direct download link; `metadata.license` for `licence`;
`metadata.related_identifiers` for the paper this supplements, which becomes
`source_locator` and a `DERIVED_FROM` edge; `metadata.version` and
`conceptdoi`, because the concept DOI resolves to the latest version and a
version DOI pins one.

**Characteristic pitfalls.**

- **Concept DOI versus version DOI.** The concept DOI always points at the newest
  version, so a `DataRef` built on it is not reproducible. Record the version DOI in
  `id` and mention the concept DOI in `notes`.
- **Zip archives hide their contents.** A single 4 GB `archive` entry tells you
  nothing about `columns` or `n_records`. Look for a manifest, a README file
  deposited alongside, or the associated paper's supplementary description before
  giving up. Set `fmt` to `ARCHIVE` and say in `notes` what you could not determine.
- **Anyone can deposit anything.** A Zenodo record is not peer reviewed and carries
  no quality guarantee. It is `SourceType.DATASET`, which is *not* classified as grey
  by the contract, so be correspondingly careful about what you claim it supports.

---

## Figshare

Similar role to Zenodo, heavier on publisher-hosted supplementary material — many
journals deposit article supplements to Figshare automatically, so this is where a
paper's real data table often lives.

```bash
# Search is a POST
curl -s -X POST 'https://api.figshare.com/v2/articles/search' \
  -H 'Content-Type: application/json' \
  -d '{"search_for": "nuclear receptor binding affinity", "page_size": 100, "item_type": 3}'

# One article, including its file list
curl -s 'https://api.figshare.com/v2/articles/12345678'
curl -s 'https://api.figshare.com/v2/articles/12345678/files'
```

*Verify before relying on this:* the `item_type` numeric codes (dataset, figure,
software, and so on) and the exact search body fields should be checked against the
current Figshare API documentation.

Fields to extract: `doi`, `title`, `url_public_html` for the landing page,
`description` for `measures`, `license.name` and `license.url` for `licence`, and
per file `name`, `size`, `computed_md5`, and `download_url`. The `computed_md5` is
worth recording in `notes` because it lets a later fetch verify integrity before
the file is used, which is the same function `sha256` serves after materialisation.

**Characteristic pitfalls.**

- **Publisher supplements are frequently Excel workbooks** with merged cells,
  multiple sheets, footnotes in data rows, and units embedded in header text. Set
  `fmt` to `OTHER`, and do not promise `columns` you have not seen.
- **The article record and the file record disagree on size.** Trust the files
  endpoint.
- **Embargoes.** An article can be listed with its files withheld until a date.
  That is `Access.REQUEST` or `Access.RESTRICTED` depending on the terms, and it
  needs a `fetch_hint` recording the embargo date.

Two adjacent repositories, both worth a query and neither worth a full recipe:
**OSF** at `https://api.osf.io/v2/nodes/?filter[title]=<term>`, which is strong on
preregistrations and project-level material, and **Dryad** at
`https://datadryad.org/api/v2/search?q=<term>`, which is strong on data underlying
journal articles because several journals mandate deposit there. *Verify both
endpoints before relying on them.*

---

## HuggingFace

Model checkpoints, precomputed prediction sets, and increasingly the curated splits
for benchmark tasks. Its unique value for us is that someone else's model *outputs*
are often deposited here, and a set of predictions is a legitimate
`MeasurementKind.PREDICTION` dataset.

An MCP connector is available in this environment — `hub_repo_search` and
`hub_repo_details` — and is the path of least resistance. The HTTP API is the
fallback and is needed for the parts the connector does not cover.

```bash
# Datasets and models
curl -s 'https://huggingface.co/api/datasets?search=protein+ligand&limit=50&full=true&sort=downloads&direction=-1'
curl -s 'https://huggingface.co/api/models?search=cofolding&limit=50'

# One repository's metadata, including cardData and the file list
curl -s 'https://huggingface.co/api/datasets/<owner>/<name>'

# File tree without cloning
curl -s 'https://huggingface.co/api/datasets/<owner>/<name>/tree/main'

# Direct file download
# https://huggingface.co/datasets/<owner>/<name>/resolve/main/<path>
```

The highest-value trick here is the **dataset viewer**, which returns the schema and
a few rows without downloading anything. That gives you `columns` and often
`n_records` for free, which is precisely the metadata that makes a `Dataset` node
useful. The viewer has been served both from `datasets-server.huggingface.co` and
from paths under `huggingface.co/api/datasets/...`; *verify the current host and
path before relying on this*, then use it on every tabular dataset you record.

Fields to extract: `id` as `hf:<owner>/<name>`; `cardData` for licence, task tags,
and any declared splits; `siblings` or the tree for file names and sizes;
`downloads` and `likes` as weak popularity signals; `gated` and `private`, which
determine `access`. A gated dataset is `Access.REGISTRATION` and the `fetch_hint`
must say what has to be accepted and which environment variable holds the token —
typically `HF_TOKEN` — because the validator rejects gated access with no hint.

**Characteristic pitfalls.**

- **Provenance is often absent.** Many datasets are re-uploads of someone else's
  data with no attribution and sometimes with silent filtering applied. Read the
  dataset card for a source statement, and if there is none, say so in `notes`
  rather than recording the uploader as the origin.
- **The same benchmark exists in a dozen slightly different copies**, with
  different splits, different deduplication, and different column names. Recording
  one without noting which variant it is guarantees a later comparison against a
  differently-split copy.
- **A model card's reported numbers are claims.** Same rule as a GitHub README.
- **Licence fields are frequently wrong or absent**, and a permissive tag on a
  re-upload does not launder the original terms.

---

## Kaggle and benchmark competitions

Old competitions are an underrated source of three things: a curated split with a
defined evaluation, a leaderboard that bounds what is achievable, and the winners'
write-ups, which are unusually candid about what did not work. The discussion forum
is frequently more valuable than the data.

The CLI is the practical interface. Authentication is a `kaggle.json` token in
`~/.kaggle/` or the `KAGGLE_USERNAME` and `KAGGLE_KEY` environment variables.

```bash
kaggle competitions list -s "molecul" --sort-by latestDeadline
kaggle competitions files -c <competition-slug>
kaggle competitions leaderboard -c <competition-slug> --show

kaggle datasets list -s "binding affinity" --file-type csv --sort-by votes
kaggle datasets files -d <owner>/<slug>
kaggle datasets metadata -d <owner>/<slug> -p ./meta/

kaggle kernels list --competition <competition-slug> --sort-by voteCount
```

The underlying HTTP API is at `https://www.kaggle.com/api/v1/`; *verify paths before
relying on it directly* — the CLI is the supported surface and tracks changes.

The **discussion forum is not exposed by the API**. Reach it with search:

```
WebSearch: site:kaggle.com/competitions/<slug>/discussion "what didn't work"
WebSearch: site:kaggle.com/competitions/<slug>/discussion solution write-up
WebSearch: site:kaggle.com/code <slug> 1st place
```

Also worth sweeping beyond Kaggle: the CASP and CAPRI assessment papers, CACHE
challenge results, the Critical Assessment of Massive Data Analysis challenges,
OpenReview-hosted competition tracks, and Codabench or EvalAI-hosted benchmarks. The
assessors' papers for these are reviewed literature and belong to
`literature-harvest`; the leaderboards and participant write-ups are this skill's
territory.

Extraction: `id` as `kaggle:<competition-slug>` or `kaggle:<owner>/<dataset-slug>`;
`access` is `Access.REGISTRATION` for datasets and also for competition data, which
additionally requires accepting the competition rules in a browser before the CLI
will download — record that explicitly in `fetch_hint`, because it is a step no API
call can perform. Record the metric and the top score in `notes`; a leaderboard top
score is a `BENCHMARK` finding and a number a later stage must beat.

**Characteristic pitfalls.**

- **Competition licences frequently forbid use outside the competition.** This is
  the most common `Access.RESTRICTED` case in practice. Record the node anyway: it
  documents that the data exists and why we did not use it, which stops
  rediscovery.
- **Leaderboard scores are not comparable across competitions**, and public and
  private leaderboard scores differ, sometimes dramatically. Say which one you
  recorded.
- **A competition split is tuned to the competition.** Reusing it as a held-out set
  for a different question imports whatever leakage the organisers tolerated.
- **Notebooks rot.** A top solution notebook from four years ago pins library
  versions that no longer install. Its value is the described method, not the code.

---

## Structured activity databases

These are the sources that yield actual numbers, and they should be queried
*before* the grey sweep, because they change what you are looking for. They are
`SourceType.DATABASE` in the contract, which is not grey, so they are the sources
that can lift a finding to `established` alongside a paper.

### ChEMBL

Base `https://www.ebi.ac.uk/chembl/api/data/`. Django-style filters with double
underscores, `format=json`, `limit` capped at 1000, `offset` for paging, and a
`page_meta.next` link in each response. An MCP connector for ChEMBL is also
available in this environment.

```bash
# Find the target
curl -s 'https://www.ebi.ac.uk/chembl/api/data/target/search?q=pregnane+X+receptor&format=json'

# Activities for a target, filtered to real potency measurements
curl -s 'https://www.ebi.ac.uk/chembl/api/data/activity?target_chembl_id=CHEMBL3401&standard_type__in=IC50,Ki,Kd,EC50&limit=1000&format=json'

# Only reasonably potent, assay type B for binding
curl -s 'https://www.ebi.ac.uk/chembl/api/data/activity?target_chembl_id=CHEMBL3401&pchembl_value__gte=5&assay_type=B&limit=1000&format=json'

# Chemistry search
curl -s 'https://www.ebi.ac.uk/chembl/api/data/similarity/CC(=O)Oc1ccccc1C(=O)O/70?format=json'
curl -s 'https://www.ebi.ac.uk/chembl/api/data/substructure/c1ccc2[nH]ccc2c1?format=json'
```

Fields to pull into `columns` and to read per row: `molecule_chembl_id`,
`canonical_smiles`, `target_chembl_id`, `assay_chembl_id`, `document_chembl_id`,
`standard_type`, `standard_relation`, `standard_value`, `standard_units`,
`pchembl_value`, `activity_comment`, `data_validity_comment`,
`potential_duplicate`, `assay_type`, `bao_label`.

**Characteristic pitfalls.** The `standard_relation` field carries censoring — a
value with relation `>` means the compound was inactive up to that concentration,
and treating it as a measurement inverts its meaning. `data_validity_comment` flags
values ChEMBL itself considers suspect (outside typical range, potential
transcription error) and should be read, not dropped. `potential_duplicate` marks
rows extracted from the same underlying experiment reported twice. Multiple
activities per compound-target pair from the same `document_chembl_id` are not
independent replicates. And `assay_type` matters enormously: a functional cell-based
readout and a direct binding measurement are different `MeasurementKind` values and
should not be pooled.

### BindingDB

Focused specifically on measured binding affinities with their experimental
conditions, and it includes data curated out of patents, which makes it partially
complementary to ChEMBL rather than a subset.

Bulk download of the full dataset as a TSV inside a zip is the reliable path, from
the downloads page at `https://www.bindingdb.org/rwd/bind/downloads`. There is also
a RESTful service under `https://bindingdb.org/axis2/services/BDBService/` with
operations to retrieve ligands by UniProt accession and targets by compound,
returning XML. *Verify both the downloads path and the REST operation names before
relying on them* — this API is long-standing but its documented paths have moved,
and the current list is published on BindingDB's own API page.

**Characteristic pitfalls.** Affinity values are strings and carry inequality
prefixes such as `>10000`, so numeric parsing must handle them rather than
coercing. The same measurement appears under several affinity types (Ki, Kd, IC50)
for the same pair from different papers, and averaging across types is not
meaningful. Assay temperature and pH are recorded when known and are frequently the
explanation for two papers disagreeing.

### PubChem

Broadest coverage, weakest curation. Best used for compound identity resolution and
for finding that a bioassay exists at all.

PUG-REST composes as `<input>/<operation>/<output>`:

```bash
curl -s 'https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/rifampicin/property/MolecularWeight,XLogP/JSON'
curl -s 'https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/135398735/assaysummary/CSV'
curl -s 'https://pubchem.ncbi.nlm.nih.gov/rest/pug/assay/aid/1234/description/JSON'
curl -s 'https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/smiles/CCO/cids/JSON'
```

PUG-View returns the annotated, human-facing record including cross-references:
`https://pubchem.ncbi.nlm.nih.gov/rest/pug_view/data/compound/<cid>/JSON`.

Respect the documented rate limits — on the order of five requests per second and a
few hundred per minute, with a total request-time budget — and use the FTP bulk
files for anything systematic rather than hammering the API.

*Verify before relying on this:* the SMILES-related property names were revised
recently, with `CanonicalSMILES` giving way to newer property names. Request the
full property list for one compound and read the keys before hardcoding them.

**Characteristic pitfalls.** PubChem aggregates depositor-supplied data with no
harmonisation, so the same compound has many CIDs across salt forms,
stereoisomers, and tautomers, and a name lookup may return the wrong one. Assay
"active" and "inactive" flags are depositor calls made against depositor-chosen
thresholds and are not comparable across assays. High-throughput screen results
dominate by volume and are single-point measurements, not potencies.

### Open Targets

A GraphQL API aggregating target-disease association evidence, plus known drugs and
tractability assessments.

```bash
curl -s -X POST 'https://api.platform.opentargets.org/api/v4/graphql' \
  -H 'Content-Type: application/json' \
  -d '{"query": "{ target(ensemblId: \"ENSG00000144852\") { approvedSymbol knownDrugs { rows { drug { name } phase mechanismOfAction } } } }"}'
```

A browser-based GraphQL playground is served at the same path with `/browser`
appended, and it is the fastest way to discover the schema. Bulk data is published
as Parquet. An MCP connector is available in this environment. *Verify the API
version in the path — it has incremented — before relying on it.*

**Characteristic pitfalls.** Association scores are aggregations over heterogeneous
evidence types with a weighting scheme, so they are model outputs and not
measurements; recording one as `MeasurementKind.BINDING_AFFINITY` would be simply
wrong, and `PREDICTION` is closer. The evidence underlying a score frequently traces
back to a single paper, so two Open Targets scores are not independent sources.

### PDBe-KB, PDBe, and RCSB

For structural coverage, ligand binding sites aggregated across all structures of a
protein, and the entry-level metadata that a template search needs.

PDBe's aggregated API, under `https://www.ebi.ac.uk/pdbe/graph-api/`, has endpoints
keyed by UniProt accession that return annotations aggregated over every structure
of that protein — including ligand binding sites and interface residues. The
per-entry REST API under `https://www.ebi.ac.uk/pdbe/api/` returns entry summaries,
molecule lists, and ligand monomers for a PDB identifier. The human-facing
aggregated view is at `https://www.ebi.ac.uk/pdbe/pdbe-kb/proteins/<accession>`.
*Verify the specific graph-api endpoint paths before relying on them* — the set of
available endpoints has grown and been reorganised, and the documentation index is
the authority.

RCSB is the other half, and its search interface is what a corpus-assembly query
actually runs against:

```bash
# Search API v2 takes a JSON query, POST or URL-encoded in a `json` parameter
curl -s -X POST 'https://search.rcsb.org/rcsbsearch/v2/query' \
  -H 'Content-Type: application/json' -d @query.json

# Entry-level structured data
curl -s 'https://data.rcsb.org/rest/v1/core/entry/6P5A'

# GraphQL, for per-entry chemical components in one round trip
curl -s -X POST 'https://data.rcsb.org/graphql' -H 'Content-Type: application/json' -d @gql.json
```

The reference case study built its whole structural corpus this way: a Search API v2
query for a Pfam family combined with a non-polymer-entity-count constraint, then a
GraphQL pass over each hit's chemical components, bucketed against a hand-curated
exclusion list of waters, ions, buffers, cryoprotectants, and detergents. That
exclusion list is the part nobody publishes and the part that decides whether the
corpus is usable.

**Characteristic pitfalls.** A structure with a bound non-polymer entity is not a
structure with a bound *ligand of interest* — most non-polymer entities in the PDB
are crystallisation additives, and without an exclusion list a query for
"ligand-bound" returns mostly sulfate and glycerol. UniProt-to-PDB residue
numbering does not align, and using author numbering where the API returns UniProt
numbering silently shifts every residue index. Alternate conformations and partial
occupancy are common in exactly the flexible regions one cares about.

Adjacent and worth one query: **UniProt** at
`https://rest.uniprot.org/uniprotkb/search?query=<q>&fields=accession,protein_name,sequence&format=tsv&size=500`,
which is the canonical source for the accession that everything else keys on.

---

## Blogs, Substack, forums, and conference material

This is where negative results and practitioner defaults live. It is also where
fabrication risk is highest, because these sources have no identifier scheme. The
citation discipline for them is the subject of
[grey-evidence.md](grey-evidence.md); this section is only about finding them.

### Search patterns that work

The productive move is to search for the vocabulary of failure rather than the
vocabulary of the method, because a post that says a method worked is marketing and
a post that says it did not is evidence.

```
WebSearch: "<method name>" ("we tried" OR "didn't work" OR "did not work")
WebSearch: "<method name>" ("lessons learned" OR postmortem OR "what went wrong")
WebSearch: "<method name>" ("in practice" OR "in production") limitations
WebSearch: "<tool name>" default ("we set" OR "we used") <parameter name>
WebSearch: site:substack.com "<method name>"
WebSearch: site:*.github.io "<method name>" benchmark
WebSearch: site:linkedin.com/posts "<method name>"
WebSearch: site:news.ycombinator.com "<tool name>"
```

Domain-specific forums are worth naming because generic search misses them:
Biostars and SEQanswers for bioinformatics, the RDKit and Open Babel mailing list
archives for cheminformatics, the OpenMM and PyTorch discussion forums for
simulation and training, Stack Overflow for tooling, and a project's own GitHub
Discussions tab, which is separate from Issues and is not covered by the issues
search endpoint.

### Conference material

Talks and posters run twelve to eighteen months ahead of the corresponding paper,
and sometimes the paper never appears.

- **OpenReview** hosts reviews and rebuttals as well as papers, and the rebuttals
  contain the ablations the camera-ready version dropped. It has a REST API — the
  version 2 surface is under `https://api2.openreview.net/notes` and the older
  version 1 under `https://api.openreview.net/notes`; *verify which applies to the
  venue you want*. `site:openreview.net <term>` via WebSearch is the reliable
  fallback.
- **Proceedings sites** are directly searchable and fetchable:
  `site:proceedings.mlr.press`, `site:proceedings.neurips.cc`,
  `site:aclanthology.org`.
- **Posters and slides** are usually PDFs on a personal or lab site:
  `filetype:pdf "<method>" poster <year>`, or a search for the conference
  abbreviation plus the author name. Some conferences deposit posters to Zenodo, so
  a Zenodo query with `type=poster` is worth one call.
- **Recordings** on YouTube or SlidesLive, findable by session title. A talk is
  `SourceType.TALK`, and the locator needs a timestamp — see
  [grey-evidence.md](grey-evidence.md).
- **Abstract books** for domain conferences are often a single large PDF, poorly
  indexed by search engines but full-text searchable once fetched. If you know the
  conference, fetch the abstract book directly rather than searching for its
  contents.

### Tool documentation and release notes

The lowest-glamour, highest-reliability grey source. A changelog entry recording
that a default changed in version 2.1 is a precise, dated, attributable fact, and a
silently changed default has broken real pipelines. Read the changelog, the
migration guide, and the "known limitations" section of the docs for every tool the
pipeline depends on, and record what you find as `SourceType.DOCS` with the version
number in the locator.

---

## Verifying that a URL resolves

**This section exists because a fabricated DOI is the most likely failure mode of
this entire skill.** A scout under pressure to produce output will emit a
plausible-looking Zenodo DOI, and a plausible Zenodo DOI is trivially constructed,
because the format is `10.5281/zenodo.<record-id>` and the record identifier is just
a number. The same is true of arXiv identifiers, PubMed identifiers, and PDB codes.
Every one of these is guessable, and some guesses resolve.

**Verify before writing the node, not after.** A node written and then checked is a
node that spent time in the graph while wrong, and downstream agents read the graph.

### Step one: does the URL return a success status

```bash
# HEAD, following redirects, reporting the final status and final URL
curl -sSIL -o /dev/null -w '%{http_code} %{url_effective}\n' "$URL"

# Some servers reject HEAD. Fall back to a one-byte ranged GET.
curl -sSL -r 0-0 -o /dev/null -w '%{http_code} %{url_effective}\n' "$URL"
```

Read the *final* URL, not just the status. A 200 after a redirect to a search page,
a login wall, or a "record not found" page is a 200 for a page that does not contain
your dataset. Repository software very often serves a styled 200 for a missing
record rather than a 404.

### Step two: does the identifier resolve to what was claimed

This is the step that catches fabrication, and skipping it is why fabricated
locators survive. A DOI that resolves is not a DOI that resolves *to the claimed
work*.

```bash
# Any DOI: the handle system's own resolver, which returns the target URL as JSON
curl -s "https://doi.org/api/handles/10.5281/zenodo.1234567"

# Journal and conference DOIs, with title and authors
curl -s "https://api.crossref.org/works/10.1145/1571941.1572114"

# Data DOIs — Zenodo, Figshare, Dryad — with title and metadata
curl -s "https://api.datacite.org/dois/10.5281/zenodo.1234567"
```

Then **compare the returned title against the title the scout claimed.** If they do
not match, the identifier was guessed and it happened to land on a real record,
which is a worse outcome than a 404: a 404 announces itself, and a mismatched
resolution looks like a verified citation forever. Treat a title mismatch as a
fabrication and discard the entire card or `DataRef`, not just the identifier —
whatever process produced the number produced the surrounding claims too.

The same title-match check applies to PubMed identifiers, arXiv identifiers, PDB
codes, ChEMBL identifiers, and patent publication numbers. Every one of them is a
short string in a dense identifier space.

### Step three: record failures rather than deleting them

```python
ref = DataRef(
    id="zenodo:10.5281/zenodo.1234567",
    title="<the title as claimed>",
    url="https://zenodo.org/records/1234567",
    access=Access.UNKNOWN,
    discovered_by="source-scout/zenodo",
    fetch_error="404 at 2026-08-15; identifier does not resolve via DataCite",
    notes="Reported by a scout; treated as unverified. Do not retry.",
)
```

A dead link recorded with `fetch_error` set costs one node and saves the next agent
the same discovery pass. A dead link silently dropped guarantees rediscovery. This
is the same asymmetry that makes `pairs_with_no_data` a required metric in the
Model Report: an absence you wrote down is information, and an absence you did not
is nothing.

Count these. `n_dead_links` belongs in the report's `metrics`, and a scout whose
returns include several fabricated identifiers should have its whole batch
re-checked rather than partially salvaged.

### A batch check before the graph write

Run every candidate through one pass before any of them become nodes.

```bash
while IFS=$'\t' read -r id url; do
  code=$(curl -sSIL -o /dev/null -w '%{http_code}' --max-time 20 "$url" 2>/dev/null || echo "ERR")
  final=$(curl -sSIL -o /dev/null -w '%{url_effective}' --max-time 20 "$url" 2>/dev/null || echo "-")
  printf '%s\t%s\t%s\t%s\n' "$id" "$code" "$url" "$final"
done < candidates.tsv
```

Then read the `final` column by eye. Automated status checking catches 404s;
only reading the final URLs catches the redirect-to-login and
redirect-to-search-page cases, which are the common ones.

### Two rules that follow

- **Never construct an identifier from a pattern.** If you have a record number,
  you may build the URL. If you have only a title, search for it; do not guess the
  number. This applies with particular force to Zenodo and arXiv, whose identifier
  spaces are dense enough that guesses resolve.
- **`Evidence.locator` must be the thing you actually resolved.** If you read a
  patent as a WO publication, cite the WO number, not the US family member you did
  not open. If you read a preprint, cite the preprint, not the journal version you
  assume exists.
