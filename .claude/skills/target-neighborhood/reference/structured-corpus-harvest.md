# Structured-corpus harvest

How to turn one registry query into a labelled, deduplicated, weighted corpus.
This is the highest-value pattern in Stage 1 because it is the only one whose
output a later stage can *train on*: a reading list cannot be fine-tuned over, a
table of entry identifiers with per-entry sample weights can.

The reference exemplar did this by hand for nuclear receptors and it produced
1,264 labelled ligand-bound entries across 30 receptors from 1,291 raw hits (see
`ai-scientist/reference/pxr-case-study.md`, section 4). Nothing below is specific
to nuclear receptors, to PXR, or to proteins — the same three moves (registry
query, per-entry metadata join, curated exclusion) apply to any registry with an
annotation index and a component-level data API.

Read this alongside [axis-methods.md](axis-methods.md). The family axis is the
usual entry point, but the promiscuity axis harvests the same way with a
different query.

## The shape of the pipeline

Four scripts, four responsibilities, four checkpointed files on disk. Keep them
separate: the exclude-list curation step will be re-run many times and you do not
want to re-hit the search API each time.

1. **Query** the registry for candidate entries. Output: a list of entry IDs.
2. **Enrich** each entry with its chemical components, in chunks, from the data
   API. Output: entry ID to component-list mapping.
3. **Label** each entry as ligand-bound, additive-only, or apo by applying the
   exclude list and the heuristic filters. Output: labelled entries.
4. **Assemble**: intersect with a family or organism mapping, deduplicate, and
   emit per-entry sample weights. Output: the corpus handed to Stage 3.

Write each stage's output as JSON to `reports/<run-id>/stage1/corpus/` and record
each API call as a `MethodStep` with its parameters. A corpus whose query is not
recorded cannot be regenerated when the registry grows.

## Step 1 — RCSB Search API v2

Endpoint: `https://search.rcsb.org/rcsbsearch/v2/query`. Accepts the query as a
URL-encoded `json=` parameter on GET, or as a JSON body on POST. Use POST; the
GET form hits URL-length limits as soon as you add a third clause.

A Pfam-annotation search ANDed with "has at least one non-polymer entity" is the
canonical family-corpus query. The Pfam clause needs **two** terminal nodes, not
one: `rcsb_polymer_entity_annotation.annotation_id` matches the accession, and
`rcsb_polymer_entity_annotation.type` restricts it to the Pfam annotation
namespace. Without the type clause you will also match identically-named
annotations from other sources.

```python
import json
import time

import requests

SEARCH_URL = "https://search.rcsb.org/rcsbsearch/v2/query"


def pfam_holo_query(pfam_accession: str, start: int, rows: int = 100) -> dict:
    """Entries whose polymer entities carry `pfam_accession` AND that contain a ligand."""
    return {
        "query": {
            "type": "group",
            "logical_operator": "and",
            "nodes": [
                {
                    "type": "group",
                    "logical_operator": "and",
                    "nodes": [
                        {
                            "type": "terminal",
                            "service": "text",
                            "parameters": {
                                "attribute": "rcsb_polymer_entity_annotation.type",
                                "operator": "exact_match",
                                "value": "Pfam",
                            },
                        },
                        {
                            "type": "terminal",
                            "service": "text",
                            "parameters": {
                                "attribute": "rcsb_polymer_entity_annotation.annotation_id",
                                "operator": "exact_match",
                                "value": pfam_accession,   # e.g. "PF00104"
                            },
                        },
                    ],
                },
                {
                    "type": "terminal",
                    "service": "text",
                    "parameters": {
                        "attribute": "rcsb_entry_info.nonpolymer_entity_count",
                        "operator": "greater",
                        "value": 0,
                    },
                },
            ],
        },
        "return_type": "entry",
        "request_options": {
            "results_content_type": ["experimental"],
            "paginate": {"start": start, "rows": rows},
            "results_verbosity": "compact",
        },
    }


def search_entries(pfam_accession: str, page: int = 100) -> list[str]:
    """Paginate the whole result set. `total_count` comes back on every page."""
    ids: list[str] = []
    start, total = 0, None
    while total is None or start < total:
        resp = requests.post(
            SEARCH_URL, json=pfam_holo_query(pfam_accession, start, page), timeout=60
        )
        if resp.status_code == 204:      # RCSB returns 204, not an empty 200, for no hits
            break
        resp.raise_for_status()
        payload = resp.json()
        total = payload["total_count"]
        # results_verbosity="compact" makes result_set a list of bare ID strings.
        ids.extend(payload["result_set"])
        start += page
        time.sleep(0.2)                  # be polite; there is no published rate limit
    return ids
```

Notes that matter in practice:

- **`return_type` decides the granularity of the identifiers.** `"entry"` gives
  `1M13`; `"polymer_entity"` gives `1M13_1`; `"assembly"` gives `1M13-1`. Choose
  entry-level for a training corpus and entity-level when a single entry contains
  several distinct proteins and you must know which chain carried the annotation.
- **`results_content_type`** must be `["experimental"]` for a crystallographic
  corpus. Leaving it at the default pulls in computed structure models, which
  have no ligands and will silently inflate your apo bucket.
- **Pagination is required.** The API caps `rows` (100 is safe; larger values are
  accepted but the cap has changed between releases — check `len(result_set)`
  against the `rows` you asked for and treat a short page as authoritative).
- **`return_all_hits: true`** exists in `request_options` and avoids pagination
  entirely, but on a large family it returns a response big enough to be awkward
  and gives you no checkpointing. Paginate.
- Add `"attribute": "rcsb_entry_info.resolution_combined"` with
  `"operator": "less_or_equal"` if you want to gate on resolution at query time.
  Prefer not to: harvest broadly, then use resolution in the *weighting* step so
  the corpus records what it excluded.

Equivalent queries for other axis needs, same shape with a different attribute:

| What you want | Attribute | Operator |
|---|---|---|
| A protein family by InterPro | `rcsb_polymer_entity_annotation.annotation_id` with `type == "InterPro"` | `exact_match` |
| Entries for one UniProt accession | `rcsb_polymer_entity_container_identifiers.reference_sequence_identifiers.database_accession` | `exact_match` |
| One organism | `rcsb_entity_source_organism.taxonomy_lineage.name` | `exact_match` |
| Entries containing a given ligand | `rcsb_nonpolymer_instance_annotation.comp_id` (verify before relying on this — the component-level attribute path has moved between API releases; introspect against a known holo entry first) | `exact_match` |
| A promiscuity-axis target class | full-text `"struct_keywords.pdbx_keywords"` or an EC-number attribute | `contains_words` |

For the promiscuity axis the exemplar ran six such class queries deliberately
(cytochrome P450, kinase, transporter, protease, phosphodiesterase, G-protein
coupled receptor) because the target's pocket was large and adaptable, and the
useful transfer sources shared *that problem* rather than the fold. Whatever the
domain, the promiscuity query is a class query, not a homology query.

## Step 2 — RCSB GraphQL data API for chemical components

Endpoint: `https://data.rcsb.org/graphql`. One request per chunk of entries, not
one per entry: 50 to 100 entry IDs per query is a good size, and 1,300 entries
becomes roughly twenty requests.

```python
GRAPHQL_URL = "https://data.rcsb.org/graphql"

COMP_QUERY = """
query Components($ids: [String!]!) {
  entries(entry_ids: $ids) {
    rcsb_id
    rcsb_entry_info { resolution_combined nonpolymer_entity_count deposited_polymer_monomer_count }
    exptl { method }
    nonpolymer_entities {
      rcsb_nonpolymer_entity_container_identifiers { auth_asym_ids }
      nonpolymer_comp {
        chem_comp { id name formula formula_weight type }
        rcsb_chem_comp_descriptor { InChIKey SMILES_stereo }
      }
    }
  }
}
"""


def fetch_components(entry_ids: list[str], chunk: int = 50) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for i in range(0, len(entry_ids), chunk):
        ids = entry_ids[i : i + chunk]
        resp = requests.post(
            GRAPHQL_URL, json={"query": COMP_QUERY, "variables": {"ids": ids}}, timeout=120
        )
        resp.raise_for_status()
        payload = resp.json()
        if "errors" in payload:
            # GraphQL returns HTTP 200 with an `errors` array. Never trust the status code alone.
            raise RuntimeError(payload["errors"])
        for entry in payload["data"]["entries"] or []:
            comps = []
            for ent in entry.get("nonpolymer_entities") or []:
                cc = (ent.get("nonpolymer_comp") or {}).get("chem_comp") or {}
                desc = (ent.get("nonpolymer_comp") or {}).get("rcsb_chem_comp_descriptor") or {}
                comps.append(
                    {
                        "comp_id": cc.get("id"),
                        "name": cc.get("name"),
                        "mw": cc.get("formula_weight"),
                        "inchikey": desc.get("InChIKey"),
                        "smiles": desc.get("SMILES_stereo"),
                    }
                )
            out[entry["rcsb_id"]] = comps
        time.sleep(0.2)
    return out
```

Two operational cautions. First, GraphQL answers with HTTP 200 and an `errors`
array when a field name is wrong, so a typo looks like an empty result unless you
check explicitly — the code above does. Second, field names in this schema do
change between releases; if a nested field comes back `null` for an entry you
know is holo, introspect the live schema
(`{"query": "{ __type(name: \\"CoreEntry\\") { fields { name } } }"}`) rather than
guessing. Treat every field path in this document as "verify once, then rely on
it for the run" and record the verification date in the `MethodStep`.

The REST alternative, `https://data.rcsb.org/rest/v1/core/entry/{id}`, works but
costs one request per entry and returns far more than you need. Use it only for
spot-checking a single entry by hand.

## Step 3 — the additive-ligand exclude problem

**This is the actual work.** A crystallographic entry's non-polymer components
are whatever was in the drop: the ligand of interest, plus waters, ions, buffer
species, cryoprotectants, polyethylene glycols of assorted lengths, detergents
used for solubilisation, lipids from a mesophase, sugars from glycosylation, and
reducing agents. If you treat "has a non-polymer entity" as "has a ligand", a
large fraction of your ligand-bound corpus will be entries whose only heteroatom
group is glycerol, and a fine-tune weighted over it will learn to place
cryoprotectant.

Curating the exclude list is iterative and it is where the judgement lives. The
reference pipeline's list reached roughly 230 component identifiers. The starter
list below is smaller and deliberately conservative; expect to add another
hundred as you inspect your own family's frequency table.

### Starter exclude list

Tier A — solvent, ions, and unknowns. Safe to exclude in essentially every
context.

```
HOH DOD UNK UNL UNX
NA K LI CS RB MG CA SR BA MN FE FE2 NI CO CU CU1 ZN CD HG AU AG PT PB AL
CL BR IOD NH4 OH SO4 PO4 NO3 CO3 BCT AZI SCN CN
XE KR
```

Tier B — buffers, precipitants, cryoprotectants, and reducing agents. Excluded
for structure-corpus purposes; see the caveat below before excluding them from a
metabolic or enzymological corpus.

```
GOL EDO PEG PGE PG4 P6G 1PE MPD MRD DIO BU1 PDO
DMS EOH MOH IPA ACT ACY FMT CIT TLA TAR SIN MLI OXL
TRS MES EPE IMD CAC URE SPM SPD
DTT BME
```

Tier C — detergents, lipids, and common glycans. Excluded when the question is
"what small molecule occupies the pocket"; **retained** when the target is a
membrane protein whose lipid or detergent occupancy is the biology.

```
BOG LMT LDA BNG OLC OLA PLM MYR STE
NAG NDG NGA BMA MAN GAL GLC BGC FUC SIA
SUC TRE MAL INS
```

That is roughly 80 identifiers. Confidence notes, because this matters more than
completeness: the Tier A entries and the common cryoprotectants and buffers
(`HOH`, `NA`, `CL`, `SO4`, `PO4`, `GOL`, `EDO`, `PEG`, `PGE`, `PG4`, `P6G`,
`1PE`, `MPD`, `MRD`, `DMS`, `TRS`, `MES`, `EPE`, `IMD`, `DTT`, `ACT`, `FMT`,
`CIT`, `URE`, `NAG`, `NDG`, `BMA`, `MAN`, `GAL`, `GLC`, `BGC`, `FUC`, `SIA`,
`SUC`, `BOG`, `LMT`, `SPM`, `SPD`) are ones I am confident about. `LDA`, `BNG`,
`MRD` versus `MPD` stereochemistry, `MLI` versus other malonate forms, `TLA`
versus `TAR` tartrate enantiomers, `CAC`, `BME`, `INS`, and `TRE` are plausible
but **verify each against
`https://data.rcsb.org/rest/v1/core/chemcomp/<COMP_ID>` before relying on
them** — an identifier that does not exist is a silent no-op, while an identifier
that names something *else* silently deletes real ligands.

### What you must not exclude

Cofactors and nucleotides look like additives by frequency but are frequently the
biology: `HEM`, `HEC`, `NAD`, `NAI`, `NAP`, `NDP`, `FAD`, `FMN`, `SAM`, `SAH`,
`ATP`, `ADP`, `AMP`, `GTP`, `GDP`, `ANP`, `PLP`, `COA`, `TPP`, `B12`, `RET`. For
a cytochrome P450 corpus, excluding `HEM` destroys the corpus. Decide per problem
and record the decision in the `MethodStep` parameters, because the next person
to read the corpus cannot infer it.

### Heuristic filters, applied after the exclude list

The exclude list handles known additives. Heuristics catch the unknown ones.

```python
from collections import Counter

MW_MIN = 100.0     # Da; below this almost nothing is a meaningful organic ligand
MW_MAX = 1200.0    # above this you are usually looking at a peptide, glycan chain, or lipid
EXCLUDE: set[str] = set(...)   # the tiers above, as one set


def classify_entry(comps: list[dict], exclude: set[str] = EXCLUDE) -> tuple[str, list[dict]]:
    """Return ('ligand_bound' | 'additive_only' | 'apo', the surviving components)."""
    if not comps:
        return "apo", []
    kept = []
    for c in comps:
        if not c.get("comp_id") or c["comp_id"].upper() in exclude:
            continue
        mw = c.get("mw")
        if mw is None or not (MW_MIN <= float(mw) <= MW_MAX):
            continue
        kept.append(c)
    # Collapse components that are the same chemistry deposited under different ids.
    seen: dict[str, dict] = {}
    for c in kept:
        # InChIKey is the right dedup key; its first block ignores stereochemistry and
        # protonation, which is usually what you want across deposits.
        key = (c.get("inchikey") or c.get("smiles") or c["comp_id"])[:14]
        seen.setdefault(key, c)
    kept = list(seen.values())
    return ("ligand_bound" if kept else "additive_only"), kept
```

Then — and this is the step people skip — **look at the frequency table before
you trust the classification**:

```python
freq = Counter(c["comp_id"] for comps in components.values() for c in comps)
for comp_id, n in freq.most_common(60):
    print(f"{n:5d}  {comp_id:5s}  {names[comp_id]}")
```

Anything appearing in more than about 5 % of entries in a diverse family is
either a cofactor or an additive, and eyeballing the top sixty by hand takes ten
minutes and catches the additive your list was missing. Record the final table as
an `Artifact` so the next run starts from it rather than from this document.

Sanity check the yield. The exemplar went from 1,291 hits to 1,264 labelled
ligand-bound entries, which is a high retention rate because the family is a
ligand-binding-domain family where nearly every deposit has a real ligand. If
your family retains 30 %, that is plausible. If it retains 99 %, your exclude
list is not being applied; if it retains 5 %, you have almost certainly excluded
a cofactor.

## Step 4 — family membership from UniProt and InterPro

The registry query gives you structures. You still need to know *which protein*
each structure is, because per-receptor counts drive the weighting and because
two receptors in the same family are not interchangeable training data.

UniProt, REST, no key required:

```python
# Which PDB entries map to one accession, plus family annotation.
r = requests.get(
    "https://rest.uniprot.org/uniprotkb/search",
    params={
        "query": "family:\"nuclear hormone receptor family\" AND organism_id:9606 AND reviewed:true",
        "fields": "accession,id,protein_name,gene_primary,xref_pdb,xref_pfam,sequence",
        "format": "json",
        "size": 500,
    },
    timeout=60,
)
# Paginate via the RFC 5988 `Link: <...>; rel="next"` response header, not an offset param.
next_url = r.links.get("next", {}).get("url")
```

Restrict to `reviewed:true` unless you specifically want unreviewed entries;
otherwise a family sweep returns thousands of near-identical fragments. The
`xref_pdb` field gives you the accession-to-structure mapping that lets you label
each harvested entry with its receptor, which is exactly what the exemplar's
segment step did for 31 human accessions.

InterPro, for the family and domain hierarchy:

```python
# Every UniProt entry carrying a Pfam domain, paginated.
r = requests.get(
    "https://www.ebi.ac.uk/interpro/api/protein/UniProt/entry/pfam/PF00104/",
    params={"page_size": 200, "reviewed": "true", "taxonomy": 9606},
    timeout=60,
)
payload = r.json()          # {"count": N, "next": url|null, "results": [...]}
```

InterPro's pagination is a `next` URL in the body; follow it until null. InterPro
also gives you the superfamily relationships, which is how you decide what counts
as a "close homolog" for weighting purposes rather than asserting it. In the
exemplar, the close-homolog set (the target plus five related receptors) came to
302 entries out of 1,264 — a distinction worth making because those entries carry
a different sample weight.

## Step 5 — measured activity breadth from ChEMBL and BindingDB

The promiscuity axis needs *measured* breadth, not a literature adjective. Two
free sources.

ChEMBL, via its REST API:

```python
CHEMBL = "https://www.ebi.ac.uk/chembl/api/data"

# 1. Resolve the target. Never skip this: gene-name searching returns homologues
#    from other organisms and protein complexes that merely contain your protein.
r = requests.get(
    f"{CHEMBL}/target.json",
    params={"target_components__accession": "O75469", "limit": 20},
    timeout=60,
)
targets = r.json()["targets"]        # filter to target_type == "SINGLE PROTEIN", organism == Homo sapiens

# 2. Pull measured activities with a real numeric value and a standard unit.
acts, offset = [], 0
while True:
    r = requests.get(
        f"{CHEMBL}/activity.json",
        params={
            "target_chembl_id": "CHEMBL3401",       # from step 1, not hardcoded
            "standard_type__in": "IC50,Ki,Kd,EC50",
            "standard_relation": "=",               # drop '>' / '<' censored values for breadth counting
            "limit": 1000,
            "offset": offset,
        },
        timeout=120,
    )
    page = r.json()
    acts.extend(page["activities"])
    if not page["page_meta"]["next"]:
        break
    offset += 1000
```

Breadth is then a count of **distinct chemotypes**, not of activity rows. Rows
double-count series and reward well-studied targets. Cluster the distinct
`canonical_smiles` by Murcko scaffold or by Butina clustering at a Tanimoto
threshold and count clusters — see [axis-methods.md](axis-methods.md) for the
clustering parameters and for how to normalise the resulting count into the
`breadth_score` range declared on the axis.

BindingDB provides bulk downloads (TSV and SDF) plus a REST interface at
`https://bindingdb.org/rest/`; the exact path spellings there are less stable
than ChEMBL's, so **verify the endpoint before relying on it** and prefer the
bulk file for a one-off harvest. BindingDB's value over ChEMBL is coverage of
thermodynamic constants extracted from crystallography-adjacent literature that
ChEMBL curates less densely. Its cost is more duplication — deduplicate on
`(target, ligand InChIKey, measurement type)` before counting anything.

Record either source as `Evidence(source_type=SourceType.DATABASE,
locator="chembl:CHEMBL3401")` and, if you keep the pulled table, as a `Dataset`
node carrying a `DataRef` with `access=Access.OPEN` and the API call in
`fetch_hint`. Stage 1 records where the data lives; it does not download bulk
files it does not need.

## Step 6 — emitting per-entry sample weights

The corpus is not the deliverable. The corpus **plus weights** is the
deliverable, because Stage 3's curriculum fine-tune consumes
`handoff.payload.corpus_for_finetune.sample_weights`.

The exemplar's scheme, as a worked example: a four-stage curriculum of escalating
specificity and decreasing learning rate — broad drug-like structures (2,000
steps at learning rate 3e-4), then the six promiscuous target classes (1,500 at
1e-4), then all 1,264 family entries with the target receptor up-weighted 3× and
two close homologs 2× (800 at 5e-5), then the 70 target-receptor holo entries
alone (350 at 2e-5), with the interface loss weight rising from 1.0 to 3.0 across
the stages.

Two things generalise from that and one does not. The **stage structure**
generalises: escalate specificity, decay the learning rate, raise the weight on
the loss term you actually care about. The **relative weights** generalise as a
shape: target above close homologs above the rest, with a ratio in the small
single digits. The specific step counts do not generalise at all — they were
tuned against that model and that corpus size, and quoting them as defaults for a
different corpus would be inventing a number.

So emit the weights as a decomposed product, which is auditable, rather than as
an opaque scalar:

```python
def sample_weight(entry: dict, *, target_accession: str, close_homologs: set[str]) -> dict:
    """Decomposed, auditable per-entry weight. Every factor is justified separately."""
    acc = entry["uniprot_accession"]

    # 1. Relatedness to the target: the axis-derived factor.
    if acc == target_accession:
        w_relatedness, why_rel = 3.0, "target receptor"
    elif acc in close_homologs:
        w_relatedness, why_rel = 2.0, "close homolog (same subfamily per InterPro)"
    else:
        w_relatedness, why_rel = 1.0, "same family"

    # 2. Structure quality. Down-weight, never exclude: a 3.2 A holo structure of the
    #    target is still more informative than a 1.4 A structure of a distant relative.
    res = entry.get("resolution_angstrom")
    if res is None:
        w_quality, why_q = 0.75, "resolution unknown (non-crystallographic or unreported)"
    elif res <= 2.0:
        w_quality, why_q = 1.0, "resolution <= 2.0 A"
    elif res <= 2.8:
        w_quality, why_q = 0.85, "resolution 2.0-2.8 A"
    else:
        w_quality, why_q = 0.6, "resolution > 2.8 A"

    # 3. Redundancy. N near-identical deposits of one complex should together count
    #    about as much as one, or the corpus is dominated by whatever was crystallised most.
    n_dupes = entry.get("cluster_size", 1)
    w_redundancy = 1.0 / max(1, n_dupes) ** 0.5     # sqrt, not 1/n: do not erase real replicates

    # 4. Ligand relevance to the test distribution. Only include this factor if you
    #    have MEASURED the similarity (see domain-shift.md). Otherwise leave it at 1.0
    #    and say so — a guessed factor here quietly encodes the bias you are trying to avoid.
    w_ligand = entry.get("ligand_similarity_factor", 1.0)

    w = w_relatedness * w_quality * w_redundancy * w_ligand
    return {
        "entry_id": entry["pdb_id"],
        "weight": round(w, 4),
        "factors": {
            "relatedness": [w_relatedness, why_rel],
            "quality": [w_quality, why_q],
            "redundancy": [round(w_redundancy, 4), f"cluster of {n_dupes}"],
            "ligand_relevance": [w_ligand, entry.get("ligand_similarity_note", "not measured")],
        },
    }
```

Normalise the weights so the mean is 1.0 before handing off, so Stage 3 can swap
weighting schemes without also changing its effective learning rate. Report both
the weight distribution and the *effective sample size*,
`(sum(w))^2 / sum(w^2)` — if 1,264 weighted entries have an effective sample size
of 90, the corpus is much smaller than its row count suggests, and Stage 3 needs
to know that before it chooses a number of training steps.

## Emitting the graph delta

The harvest produces `Structure` nodes, not just identifiers. Mind the predicate
domains in `reagent.contracts.kg.PREDICATE_DOMAINS`:

- `Protein --HAS_STRUCTURE--> Structure` (`pdb:1M13`), one per harvested entry.
- `Protein --MEMBER_OF_FAMILY--> Family` (`family:NR1I`), which is what the
  family axis's declared predicate actually connects. Note that
  `MEMBER_OF_FAMILY` is validated as Protein-to-Family, so it cannot carry the
  structure-level corpus; the corpus rides on `HAS_STRUCTURE` plus
  `CO_CRYSTALLIZED_WITH`.
- `Structure --CO_CRYSTALLIZED_WITH--> Compound` for each surviving component, or
  `Protein --BINDS--> Compound` when you have a measured affinity from ChEMBL or
  BindingDB rather than mere co-crystallisation. Do not conflate the two:
  co-crystallisation is not an affinity, and writing a `BINDS` edge with no
  `affinity_nm` attribute invites a downstream stage to assume one exists.
- `Compound` nodes keyed `inchikey:<key>` when you have the InChIKey and
  `pdbccd:<COMP_ID>` when you only have the component identifier — never both for
  the same chemistry, or the dedup key stops working.

Confidence for these edges is `Confidence.SUPPORTED` with
`Evidence(source_type=SourceType.STRUCTURE, locator="pdb:1M13")`. A registry
record is a solid single grounded source; it becomes `ESTABLISHED` only when a
second independent source (a paper reporting the same complex, a ChEMBL
measurement) is also cited.

## Failure modes seen in practice

- **Treating "has a non-polymer entity" as "has a ligand."** The whole reason
  this document exists.
- **Not paginating**, and silently harvesting only the first 100 entries. Always
  assert that the number of collected identifiers equals `total_count`.
- **Deduplicating on component identifier instead of chemistry.** The same
  molecule appears under different identifiers across deposits, and the same
  identifier appears many times within one entry (several copies in the
  asymmetric unit). Deduplicate on the InChIKey first block, per entry.
- **Excluding a cofactor that is the biology.** Cheap to prevent: print the
  frequency table and read it.
- **Emitting the corpus without weights.** Stage 3 then invents weights, which
  means the weighting decision is made by whoever has the least context.
- **Regenerating a "new" corpus with a slightly different query and comparing
  results across the two.** Pin the query, the exclude list, and the harvest date
  in the `MethodStep`; the registry grows weekly.
