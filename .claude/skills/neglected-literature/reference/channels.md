# Discovery channels: where to look, and what each index misses

`DiscoveryChannel` splits into **pull** (we described what we wanted), **traversal** (the
literature's own structure led us there), **inference** (nothing pointed at it; we deduced it
should exist), and **outside the indexed record**.

The split is load-bearing. Pull channels can only return work whose vocabulary we already
guessed — that is their structural blind spot, and no amount of query refinement fixes it,
because refinement operates inside the same vocabulary. Traversal channels do not share that
limitation, which is why `SearchLedger.problems()` fails a search with no traversal channel.

---

## Pull channels

### `keyword_search`

**Paperclip** is the primary full-text tool. Two verified facts that contradict its own help
text, both from testing:

- **It cannot search patents.** The help text implies otherwise. Patents go through a separate
  channel — Google Patents, Espacenet, or Lens.org.
- **`--save-as` is the JSON output switch, not `--json`.**

Run `paperclip skill` first to load current documentation and the routine registry, then
`paperclip routines route "<intent>"` if a trigger matches. Full CLI notes live in
`literature-harvest/reference/paperclip-cli.md`.

Supplement with **Europe PMC** (full text, good API, includes preprints) and **PubMed**
(abstracts, MeSH terms). Europe PMC's full-text search finds method details that abstract-only
indexes cannot, and method details are usually what we want.

### `semantic_search`

Embedding similarity over titles and abstracts. Catches paraphrase, misses vocabulary that is
rare in the training corpus — so it partly addresses `vocabulary_mismatch` and partly inherits
it. Useful as a *second* channel for coverage estimation because its errors differ from
keyword search, but it is still a pull channel and pairing the two for capture-recapture is
the mistake `channels_are_mechanically_different` exists to catch.

### `structured_query`

The axis's native index, queried by field rather than by text. Far higher precision than any
text search when the axis has one:

| Axis | Index | Query handle |
|---|---|---|
| fold / structure | RCSB Search API | sequence, assembly, ligand, resolution, method |
| sequence | UniProt, MMseqs2, Foldseek | accession, family, taxonomy |
| chemotype | ChEMBL, PubChem | target, activity type, assay, scaffold |
| pathway | Reactome, KEGG, WikiPathways | participant, event, hierarchy |
| partners | STRING, IntAct, BioGRID | interactor, detection method, score |
| expression | Human Protein Atlas, GTEx, Expression Atlas | tissue, specificity |
| bibliometrics | OpenAlex, Semantic Scholar | citations, venue, year, concepts, referenced works |

**OpenAlex is the workhorse for this skill.** Free, no key required, and exposes citation
counts, per-year curves, referenced works, citing works, venue, and concept tags — which is
exactly the set needed to evidence `too_recent`, `high_quality_citers`, `sleeping_beauty`, and
`small_field`. Semantic Scholar's API adds influential-citation flags and TLDRs.

### `ontology_expansion`

Take the concept, not the phrase, and pull its synonym list: MeSH for biomedical terms,
InterPro and Pfam for domains, GO for processes, ChEBI for chemistry, UBERON for anatomy.
This is the direct countermeasure to `vocabulary_mismatch`, and it is cheap — one API call
turns one query into eight.

---

## Traversal channels

These find what pull channels structurally cannot, and in complex-evidence reviews they
account for most of the sources actually used (Greenhalgh & Peacock 2005, BMJ — verify the
exact split before quoting numbers). Methodology for doing it systematically: Wohlin (2014),
*Guidelines for snowballing in systematic literature studies*, EASE.

### `backward_snowball`

Read the reference list of every strongly relevant paper. Cheap, high yield, and the single
most under-used channel. Prioritise references cited in the *methods* section — those are the
ones actually used, as opposed to the introduction's ceremonial citations.

### `forward_snowball`

Who cites this? OpenAlex `cited_by`. Finds the work that built on it, including the *prince*
that awakened a sleeping beauty. Also finds the paper that says it does not work, which is the
higher-value direction and the one nobody checks.

### `co_citation`

Papers frequently cited *alongside* a known-relevant one. Surfaces the implicit reading list
of a subfield — the set of papers practitioners treat as a unit — without needing to know its
name.

### `author_trail`

Other work by an author of a strongly relevant paper. The direct countermeasure to
`low_amplification`: if one paper from a small group is excellent, read their others. Also
finds the thesis that the paper was extracted from, which usually contains the negative results
the paper dropped.

### `venue_sweep`

Scan a whole journal issue or proceedings volume. Feels crude and works, because it is the only
channel with no relevance filter at all — and therefore the only one that cannot inherit the
biases of a relevance signal. Best used on a workshop proceedings in an adjacent field.

---

## Inference channels

### `graph_gap`

Two-hop paths in our own KG with no direct edge. See
[graph-gap-queries.md](graph-gap-queries.md). The only channel that can surface a connection
no paper has stated.

### `analogy_transfer`

A cross-domain mechanism from `cross-domain-analogy` suggests where to look. Record the analogy
as the reason, and remember the resulting source is grounded even though the analogy is not —
the analogy motivated the search, it does not support the claim.

---

## Outside the indexed record

### `grey_channel`

Repos, blogs, Substack, LinkedIn, forums, competition write-ups, issue trackers. Owned by
`source-scout`; route there rather than duplicating it. Relevant here because **grey channels
are where negative results live**, and negative results are the most systematically missing
category in the indexed record.

For GitHub specifically: search issues and discussions, not just code. `"does not work"`,
`"fails on"`, and `"regression"` in an issue tracker is primary evidence about a tool's real
behaviour, and often the only public record of it.

### `regional_index`

SciELO, J-STAGE, KCI, CNKI, African Journals Online, plus national thesis portals. Translate
the *terms*, not the query. Records `language_barrier`.

### `repository`

Institutional repositories, ProQuest, national thesis portals, Zenodo, OSF, figshare. Theses
are underrated: they carry the failed experiments and the parameter sweeps that the derived
paper omitted for length, which is precisely the material a pipeline designer needs.

### `human_pointer`

A person told us. Record it — it is legitimate evidence with a real provenance, it maps to
`SourceType.EXPERT_PRIOR`, and it is honest about how much of any real literature search comes
from someone saying "you should read X". Note that it is *ungrounded* in the contract's sense
until the underlying source is retrieved and read.

---

## Choosing the pair for coverage estimation

The estimate needs two channels whose errors are as uncorrelated as possible. Best pairs:

| Pair | Why it works |
|---|---|
| `keyword_search` × `backward_snowball` | one is vocabulary-bound, the other is not |
| `structured_query` × `forward_snowball` | one is field-bound, the other follows use |
| `ontology_expansion` × `author_trail` | one varies terms, the other varies people |

Worst pairs — all flagged by `channels_are_mechanically_different`:

- `keyword_search` × `semantic_search` — both pull, both vocabulary-bound
- `keyword_search` × `ontology_expansion` — the second is a superset of the first
- any channel × itself with different queries — that is one channel
