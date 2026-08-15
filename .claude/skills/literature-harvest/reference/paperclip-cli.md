# Paperclip CLI reference (verified 2026-08-15)

Empirically established against the live tool. Where the built-in `--help` and
reality disagree, reality is recorded here. Re-verify before trusting anything
marked **quirk**.

## The five facts that break naive scripts

1. **There is no local `paperclip` binary.** `which paperclip` → not found.
   Paperclip is reachable *only* through the MCP tool
   `mcp__claude_ai_Paperclip_for_literature_search__paperclip`, which takes a
   single `command` string with **no `paperclip` prefix**:
   `search -s pmc "query" -n 5`. Never drive it from Bash.
2. **`--json` does not exist. `--save-as NAME` is the JSON switch.** Adding
   `--save-as` to a result-producing command flips output from human prose to one
   raw JSON object. **quirk:** `lookup --json` is documented but emits prose.
3. **Carry the `s_`/`m_` result IDs between calls, never the alias.** Server-side
   result IDs persist across MCP calls; the human aliases from `--save-as` do
   **not** — `refine --from my_alias` fails on the very next call.
4. **Patents are not available.** `patents` appears in the `-s/--source` help
   string but returns `Patents sources are not available.` Do not build a patent
   path through Paperclip; use WebSearch against Google Patents / Espacenet
   instead. Clinical trials and FDA regulatory documents *are* available.
5. **`config`, `login`, and `generate-search-config` are blocked over MCP**
   (`'config' is not available over MCP`). Assume anything auth- or
   local-file-shaped is unavailable.

## Corpora and scoping

```
ls /
papers/     3.4M+ scientific papers     -s papers | -s pmc,biorxiv,medrxiv,arxiv
fda/        217K+ FDA regulatory docs   -s fda | fda/us | fda/jp | fda/eu
trials/     110K+ clinical trials       -s trials | trials/us | trials/cn | trials/jp | trials/eu
proteins/   574K+ protein entries       -s proteins  (alias -s uniprot)
```

Also: `-s abstracts` (broader, no full text), `-s clipboard[/folder]`, and
`/trials/intl` (adds WHO ICTRP, 1.08M+). Sources comma-mix: `-s pmc,clipboard`.

**Before any `-s proteins` work you must run `paperclip skill proteins`.** Protein
search matches gene names aggressively and returns junk otherwise — searching
"pregnane X receptor" returned a *Drosophila virus* protein because its gene is
named `X`.

## Search

`search --help` fails without a source. Use `search -s pmc --help`.

```
search [OPTIONS] QUERY
  -n/--limit N            max results (default 100)
  -e/--exact              exact phrase
  -r/--regex              regex across all papers
  -a/--author  -t/--title
  --since 7d|30d|6m|1y    recency
  --sort relevance|date
  --journal NAME  --year Y  --year-min Y  --year-max Y
  --ranking hybrid|bm25|vector|analogical
  --min-embedding-similarity F   --min-bm25-score F
  --bool                  boolean expression; REQUIRES --ranking bm25
  --full-text             match phrases against body, not just title
  --has-full-text         require indexed body content
  --article-type TYPE     (undocumented but works)
  --exclude-article-type TYPE   --exclude-source  --exclude-journal  --exclude-year
  --has-section NAME  --without-section NAME
  -m/--mode any|all|50%|75%
  --save-as NAME          <-- THE JSON SWITCH
```

**Determinism contract that matters for reproducibility:** hybrid search draws
from the same 100 candidates for every `-n` up to 100, so `-n 8` is a stable
prefix of `-n 50`. **`-n > 100` expands the pool and reorders earlier results.**
Keep `-n <= 100` if a run must be reproducible.

**quirks:**
- `--quiet` does not minimise output.
- `-c/--count` does not count-only; it returns full results.
- `--bool` `NOT "review"` matches *phrase text*, not the article-type field, so
  reviews still come back. Use `--exclude-article-type review-article`.
- `--sort date` overwhelms relevance badly — a dated PXR query returned two 2026
  papers about ribosome assembly with zero topical relevance. Prefer
  `--year-min` over `--sort date`.

## Reading a document

There is **no `read` command**. Use POSIX-ish verbs on the virtual filesystem.

```
ls   /papers/PMC12690452/     -> meta.json  content.lines  sections/  supplements/  figures/
head -6 /papers/PMC12690452/content.lines
cat  /papers/PMC12690452/meta.json
grep -n -C 2 "aromatic" /papers/PMC12690452/content.lines
```

**Line numbers are the citation anchor.** `content.lines` emits an `L<n>:` prefix
per line; cite as `#L45` or `#L45-L52`. This is how a Stage-1 finding points at
the exact span that supports it — put it in the Evidence locator:
`pmc:PMC12690452#L45-L52`.

`sections/` holds per-section `.lines` files named from the real headings
(`Abstract.lines`, `RESULTS.lines`, `STAR★METHODS.lines`, `References.lines`, …),
which lets you scope extraction to Methods or Results and skip the intro.

ID prefixes: `PMC…` (PubMed Central), `bio_…` (bioRxiv), `med_…` (medRxiv),
`arx_…` (arXiv), `fda_…`, `tri_…`, bare accession for proteins (`P04637`).

**By DOI:** no direct path. `lookup doi 10.1016/j.str.2025.09.011` → returns the
PMC ID, then `cat /papers/PMC…/meta.json`.

`grep` flags: `-i -n -c -v -o -w -l -h`, `-m NUM` (**match limit — `-n` is line
numbers, not a limit**), `-e PATTERN` (repeatable), `-A/-B/-C NUM`, `--bool`,
`--from s_ID`, `--block-type`, `--section`. Corpus-wide grep is time-bounded and
**non-deterministic when truncated** (`hit the per-shard match cap`).

## The extraction engine: `map --output-schema`

This is the primitive that turns literature into graph deltas, and the reason
Stage 1 is tractable at all. It fans out over a result set and forces each worker
to emit schema-valid JSON.

```
map --from s_ID [OPTIONS] "extraction prompt"
  --worker quick-reader | eligibility-screen | structured-extraction | exhaustive-extraction
  --output-schema '<Draft 2020-12 JSON Schema>'   # strict; validated per paper
  --claim-schema  '<schema>'                      # per-claim, for exhaustive
  -j/--max-concurrent N     default 32, server cap 256
  -n/--limit N  --offset N
  --resume MAP_ID [--retry-failed]   --cancel MAP_ID
  --repo NAME
```

Validation happens at the tool layer: one correction attempt on invalid output,
then that paper is marked failed. So a tight schema costs you coverage but buys
you clean data — set `additionalProperties: false` and make every field
explicitly nullable rather than optional.

Write the prompt **field by field**. A vague prompt with a strict schema produces
confidently-wrong values, which is worse than a failure.

`reduce --from m_ID [--strategy summarize|table|themes|consensus|extract] [--columns a,b,c] "q"`
aggregates a map's output.

Set algebra over result sets, all cheap: `refine --from s_ID <flags>`,
`merge s_ID1 s_ID2`, `intersect`, `subtract`.

## What is NOT usable over MCP

- `results <ID> --save <path>` reports success but the file is unreachable
  (`Unknown root: /tmp`). `--export-bundle /.gxl/…` → `Permission denied`.
  **Treat both as unusable — parse the `--save-as` JSON instead.**
- Shell `for`/`while` loops and `xargs` are unsupported in the sandbox. Blocked:
  `rm, curl, wget, ssh, sudo`. Allowed: `cd ls cat head tail grep sed awk sort cut tr jq search scan`.

## `sql`

SELECT-only, **15 s timeout, 200-row cap**, and it sees **only titles and
abstracts — never body text**. Use `grep` for body mentions.

The `--help` schema and the `skill` doc disagree; the **skill doc's columns are
the ones that work**: `documents(id, title, doi, authors, source, abstract_text,
pub_date, journal_title, article_type, pmid, keywords, categories, pub_year)`.

Useful for cheap landscape counts before spending on extraction:

```
sql "SELECT pub_year, COUNT(*) n FROM documents
     WHERE title ILIKE '%pregnane X receptor%' GROUP BY pub_year ORDER BY pub_year DESC LIMIT 10"
```

## Routines

`routines list | search | show | enable | disable | route | run`. A remote-loaded
guided-workflow system; phases are fetched into context on demand.

**As of verification, no routines are enabled on this account** — `routines list`
shows `paperclip-meta-analysis` as `[available]`, not `[enabled]`, and
`routines route "…"` returns `No enabled routine matched this intent.`
Consequently `paperclip skill` appends **no trigger registry**, so there are no
trigger phrases to script against yet. Re-check with `routines list` before
assuming.

If enabled, `paperclip-meta-analysis` runs a 12-phase systematic review targeting
50-100 effect sizes with `AskUserQuestion` gates — relevant if Stage 1 ever needs
a quantitative synthesis rather than a graph.

## Result record shapes

Papers (`-s pmc`): `document_id, source, score, backend, article_type, pub_year,
pmc_id, title, journal_title, doi, authors, tldr, pub_date, abstract_snippet`.
`score` is `null` under default hybrid ranking, populated under `--ranking bm25`.

**quirk:** with `-s papers` the `source` field is wrongly set to the journal name.
Prefer explicit `-s pmc,biorxiv,medrxiv,arxiv` if you key off `source`.

Trials: `document_id, identifier` (NCT…), `title, source_type, section_name,
snippet, score, tradename`.

FDA: adds `abstract, generic_name, therapeutic_area, document_type_detail`;
`identifier` is the application number (`ANDA064150`, `NDA050705`).

Proteins: `document_id, accession, title, protein_name, gene_name, organism,
sequence_length`.

## Limits

| Limit | Value |
|---|---|
| `sql` | SELECT only, 15 s, 200 rows |
| `search -n` | default 100; ≤100 deterministic, >100 reorders |
| `lookup -n` | default 25 |
| `map -j` | default 32, server cap 256 |
| `citation-explorer --limit` | default 200 citing works per provider |
| corpus `grep` | time-bounded, per-shard match cap |
| `results --list` | last 20 result sets |
| clipboard | 200 MB/file, 2,000 pages/PDF, 10,000 docs, 10 GB total |

No documented request-rate limit or daily quota.

## Minimal reproducible recipe

```
search -s pmc "<query>" -n 50 --has-full-text --year-min 2015 --save-as q1
   -> parse JSON, keep results_id s_XXXX
refine --from s_XXXX --exclude-article-type review-article --save-as q2
   -> keep the new s_YYYY
map --from s_YYYY --worker structured-extraction \
    --output-schema '{"type":"object","additionalProperties":false,
        "required":["assertions"],"properties":{"assertions":{"type":"array","items":{...}}}}' \
    "<field-by-field extraction instructions>"
cat  /papers/<ID>/meta.json                       # citation metadata
grep -n -C 2 "<term>" /papers/<ID>/content.lines  # line-pinned evidence for L<n> cites
```
