# Citation hygiene

What makes a citation checkable. The `Evidence` contract in
`reagent/contracts/report.py` only validates that a locator is non-blank, so
everything below is discipline rather than machinery — and it is the discipline that
decides whether the next agent can verify a claim or has to redo the work. A claim
the next agent cannot check is a claim it has to re-derive, which means an
uncheckable citation costs more than no citation, because it also carries false
assurance.

The test to apply to every locator you write: **could someone who has only this
string, and no access to this conversation, land on the exact assertion?** If the
answer requires them to search, the locator is too weak.

## Locator format per source type

One canonical form per source type. Use the namespaced prefix form; it makes the
locator self-describing and matches the `Node` id conventions in
`reagent/contracts/kg.py`.

| Source | Locator form | Example shape | Notes |
|---|---|---|---|
| Journal article | `doi:<suffix>` | `doi:10.1016/j.str.2025.09.011` | Lower-case the DOI. Do not wrap it in `https://doi.org/`; the resolver is implied. |
| PubMed record | `pmid:<digits>` | `pmid:12345678` | Use when there is no DOI, or alongside one. Digits only. |
| PubMed Central full text | `pmc:PMC<digits>#L<n>-L<m>` | `pmc:PMC12690452#L45-L52` | The line anchor is not optional for a claim extracted from the body. See below. |
| Preprint | `doi:10.1101/<date>.<id>` for bioRxiv/medRxiv; `arxiv:<id>v<n>` | `arxiv:2401.01234v2` | **Always include the version.** Preprints are mutable; an unversioned preprint citation points at a moving target. |
| Structure entry | `pdb:<4-char or extended id>` | `pdb:1M13` | Add the chain and residue when the claim is about a specific site: `pdb:1M13/A/Ser247`. |
| Sequence entry | `uniprot:<accession>` | `uniprot:O75469` | The accession, not the entry name — entry names like `NR1I2_HUMAN` get reassigned, accessions do not. Add `@<release>` if the claim depends on a specific annotation version. |
| Family or domain | `pfam:<accession>`, `interpro:<accession>` | `pfam:PF00104` | |
| Chemistry | `chembl:<id>`, `pdbccd:<comp-id>`, `inchikey:<key>` | `chembl:CHEMBL1200973` | Note the ChEMBL release with the claim when you cite an activity count; counts change every release. |
| Measured activity | `bindingdb:<monomer or assay id>` | | Verify the identifier scheme against the current site before relying on the exact form. |
| Patent | `patent:<publication-number>` | `patent:US10500000B2`, `patent:WO2019123456A1` | The *publication* number with its kind code, never the application number. Add `#claim-7` or `#para-0042` for the specific passage. |
| Clinical trial | `nct:<NCT number>` | `nct:NCT01234567` | Add the section: `nct:NCT01234567#eligibility`. |
| Regulatory document | `fda:<application-number>` | `fda:NDA050705`, `fda:ANDA064150` | Paperclip's FDA records expose the application number as `identifier`. Name the document type too, in `Evidence.title`. |
| Data deposit | `zenodo:10.5281/zenodo.<id>`, `figshare:<doi>`, `hf:<owner>/<name>`, `osf:<id>` | | Zenodo mints a per-version DOI and a concept DOI that always resolves to the latest. **Cite the version DOI.** The concept DOI is not reproducible provenance. |
| Code | `github:<owner>/<repo>@<40-char commit sha>#<path>:L<n>-L<m>` | `github:openmm/openmm@a1b2c3d…#openmm/app/simulation.py:L120-L140` | A commit SHA, never a branch name. See below. |
| Competition or benchmark | `kaggle:<competition-slug>`, `benchmark:<name>/<version>` | | Leaderboards mutate; record the retrieval date in `Evidence.title` or the excerpt. |
| Blog, Substack, company post | `url:<canonical url>` plus author and date in `title` | | Archive it and cite the snapshot; see the grey-literature section. |
| Social post, forum thread | `url:<permalink>` plus author and date in `title` | | Permalink to the individual post, not the thread root, when the claim is one comment. |
| Tool documentation | `docs:<tool>@<version>#<section>` | `docs:foldseek@9.427df8a#easy-search` | Documentation without a version describes a tool you are not running. |
| Talk or poster | `url:<recording or abstract>` plus speaker, venue, date | | Cite the abstract book entry if the recording is not public. |
| Our own computation | repo-relative path to the artifact | `reports/<run-id>/stage1/domain_shift/nn_tanimoto.json` | Must be a path that exists in the repository, and the artifact should be listed in `ModelReport.artifacts` with its sha256. |
| Our own benchmark result | `benchmark:<leaderboard>#submission-<n>` or a repo path | | Include the submission timestamp; leaderboards display the most recent submission, not the best. |

Fill in `Evidence.title` and `Evidence.year` even when the locator is
self-resolving. They cost one line each and they make a report readable without
network access, which is the state a reviewer is usually in.

`Evidence.excerpt` must be **verbatim**. The field's own description says so, and
the reason is that a paraphrase in the excerpt makes the citation uncheckable in
the most insidious way: the reader compares your paraphrase to the source, finds it
broadly consistent, and never notices the number changed. Paraphrase in the
`Finding.statement`; quote in the excerpt.

## The `L<n>` line anchor, and how to build one

Paperclip's `content.lines` files emit an `L<n>:` prefix on every line, and those
line numbers are the citation anchor — the mechanism that makes a Stage 1 finding
point at the exact span supporting it rather than at a whole paper.

The workflow, in full:

```
# 1. Find the span. -n prints line numbers; -C 2 gives you context to check the claim.
grep -n -C 2 "hydrophobic subpocket" /papers/PMC12690452/content.lines

# 2. Read the surrounding lines to confirm the span boundaries.
head -60 /papers/PMC12690452/content.lines

# 3. Scope to a section when you want the claim to come from Methods or Results
#    rather than the introduction's summary of someone else's work.
grep -n "Kd" /papers/PMC12690452/sections/RESULTS.lines
```

Then assemble the locator: the source prefix, the document identifier, `#`, and the
line range.

```
pmc:PMC12690452#L45-L52
bio_2501.01234#L112            # bioRxiv, single line
med_2412.05678#L88-L95         # medRxiv
tri_NCT01234567#L20-L31        # a clinical trial record
fda_NDA050705#L410-L418        # an FDA document
```

Three rules about line anchors:

- **A single line is a legitimate range** — write `#L112`, not `#L112-L112`.
- **The range must contain the claim, not merely be near it.** If the number is on
  line 120 and the assay conditions are on line 118, cite `#L118-L124` so the
  citation supports the whole assertion including its context.
- **Line numbers are stable per document as Paperclip has indexed it, and are not a
  property of the publisher's PDF.** They are reproducible within this tool and
  meaningless outside it, so pair the line-anchored locator with the DOI or PMID
  when the claim is important: two `Evidence` entries, one anchored for checking
  and one canonical for the record. That also helps toward `ESTABLISHED`, which
  counts distinct locators.

Section-scoped extraction is worth the extra call. A claim taken from
`sections/Introduction.lines` is almost always someone else's result being
summarised, which makes it second-hand — the same reason the skill says to search
reviews for orientation and then exclude them from extraction. Extract from
`RESULTS.lines`, `METHODS.lines`, or their real heading spellings so the citation
points at a measurement rather than at a summary of one.

## Why a bare URL is weak provenance for anything mutable

A URL names a location, not a version. For anything that changes, that makes it a
pointer to whatever the resource says *today*, which is not what you read.

- **A GitHub branch URL** (`.../blob/main/train.py#L40`) points at a line number in
  a file that will be edited. Six weeks later line 40 is a different statement, and
  your citation now supports a claim nobody made. A permalink with the full 40-character
  commit SHA (`.../blob/a1b2c3d4e5f6.../train.py#L38-L44`) is immutable, and
  GitHub produces one for you when you press `y` on the file view.
- **A database landing page** shifts under you: ChEMBL activity counts change every
  release, UniProt annotations are revised, RCSB grows weekly. Cite the accession
  and record the release or the access date when the claim is a count or an
  annotation rather than an identity.
- **A leaderboard URL** shows current standings. Record the retrieval timestamp and
  the value you read.
- **A preprint URL without a version** resolves to the latest version, which may
  contradict the one you read. Include `v<n>`.
- **A blog post** can be silently edited or deleted. Archive it.

The general rule: a bare URL is acceptable provenance only for something immutable
by construction (a DOI-minted deposit, a versioned release artifact) or for
something whose mutability does not affect the claim (a project's home page cited
as evidence that the project exists). Everywhere else, pin a version, a commit, a
release, or a snapshot, and record the date you read it.

## Citing grey literature defensibly

`SourceType` deliberately includes `BLOG`, `SOCIAL`, `DOCS`, `TALK`, and
`COMPETITION`, and `SourceType.is_grounded` returns true for all of them. That is
intentional: grey literature is frequently the **only public record of a negative
result, a parameter choice, or a practitioner default**, and a GitHub issue
reporting that a tool silently fails on a class of input is real evidence about the
world. Excluding it loses information that the peer-reviewed record does not
contain.

What makes such a citation defensible:

1. **Name the author.** A claim from a named engineer at a named organisation is
   assessable; "a blog post said" is not. Put the author and affiliation in
   `Evidence.title`.
2. **Date it.** Grey literature has no publication apparatus, so the date is the
   only thing situating it relative to tool versions and to the state of the art.
   Set `Evidence.year`, and put the full date in the title when the claim is
   version-sensitive.
3. **Archive it and cite the snapshot.** Submit the URL to a web archive and cite
   the timestamped snapshot alongside the original:
   `url:https://web.archive.org/web/20260815120000/https://example.com/post`. The
   original URL goes in the title so a reader can see where it came from. Do this at
   harvest time; a link that has already rotted cannot be archived retroactively.
4. **Quote the span verbatim in `excerpt`.** A blog post has no line numbers, so the
   verbatim quotation is the only anchor available. Keep it short and exact.
5. **State what kind of claim it is.** A practitioner's report of *what they
   observed* is stronger grey evidence than their opinion about *why*. Extract the
   observation; treat the explanation as a hypothesis.

For the specific sources:

- **A lab or company engineering blog** is `SourceType.BLOG`. Frequently the only
  record of the default parameter everyone uses.
- **Substack** is `SourceType.BLOG`. Note whether it is behind a paywall in the
  title, because a citation the reader cannot open is only half a citation.
- **LinkedIn or a forum post** is `SourceType.SOCIAL`. Permalink to the individual
  post. These are the weakest sources in the vocabulary and are most defensible when
  the author is reporting first-hand on work they did.
- **Tool documentation, issue trackers, and release notes** are `SourceType.DOCS`,
  and are the *right* source for a claim about what a tool does. Pin the version.
- **A conference talk or poster** is `SourceType.TALK`. Cite the abstract book entry
  when no recording exists, with speaker, venue, and date.
- **A competition writeup or a winning solution thread** is
  `SourceType.COMPETITION`. Often the only place a practical trick is written down —
  and note that competition writeups are self-reported and unreviewed, so treat their
  performance numbers as claims rather than as benchmarks.

## Patents

Patents are `SourceType.PATENT`, which is not grey — it is a formal published
document with an examination record. But they are **not reachable through
Paperclip**: `patents` appears in the source help string and returns "Patents
sources are not available". Use WebSearch against Google Patents or Espacenet, and
record the locator as the publication number with its kind code, plus the specific
claim or paragraph number. A patent cited without a claim number is a citation to a
sixty-page document.

Treat the patent's *examples* as measurements and its *claims* as the legal scope,
which is a different kind of statement. A number in an example is evidence; the
breadth of claim 1 is not evidence about chemistry.

## The confidence rules the validator enforces

`Finding._enforce_grounding` in `reagent/contracts/report.py` rejects, at write
time:

- An `OBSERVATION`, `BENCHMARK`, `NEGATIVE`, or `PRIOR` finding with no `Evidence`
  at all.
- Any finding above `SPECULATIVE` whose cited evidence is *entirely* ungrounded —
  cross-domain analogy or expert prior. That is the anti-laundering rule: an
  analogy wearing a citation is still an analogy.
- `ESTABLISHED` with fewer than **two distinct grounded locators**.
- `ESTABLISHED` where every grounded source is grey. The error message is explicit
  that grey sources are legitimate evidence but that `ESTABLISHED` needs at least
  one reviewed or structured-database source, and that `SUPPORTED` is the right
  level instead.

So the operational rule: **`Confidence.ESTABLISHED` requires at least one reviewed
paper, preprint, patent, trial, regulatory document, thesis, or structured-database
record (`STRUCTURE`, `DATABASE`, `DATASET`, `CODE_REPO`) — never grey literature
alone**, and it requires a second independent source on top. Two blog posts
describing the same practitioner default are `SUPPORTED`, however confident the
posts are. Two blog posts plus one structured-database record can be `ESTABLISHED`.

"Independent" means genuinely independent: two papers from the same group reporting
the same experiment are one source, and a paper plus a review citing that paper are
one source. Distinct locators are necessary but not sufficient, and the validator
can only check the necessary half — the sufficient half is your job.

## A worked pair of Evidence entries

```python
from reagent.contracts import Confidence, Evidence, Finding, FindingKind, SourceType

Finding(
    id="F-LIT-007",
    kind=FindingKind.OBSERVATION,
    statement=(
        "The receptor's ligand-binding pocket is reported at over 1600 cubic angstroms, "
        "which is large for the family and is the structural basis usually offered for "
        "its ligand promiscuity."
    ),
    confidence=Confidence.SUPPORTED,
    evidence=[
        # Line-anchored: this is the one a downstream agent can check mechanically.
        Evidence(
            source_type=SourceType.PAPER,
            locator="pmc:PMC12690452#L45-L52",
            title="<exact article title>",
            year=2024,
            excerpt="<verbatim span copied from lines 45-52>",
        ),
        # Canonical: this is the one that survives outside this tool.
        Evidence(
            source_type=SourceType.STRUCTURE,
            locator="pdb:1M13",
            title="Crystal structure of the ligand-binding domain",
        ),
    ],
    kg_nodes=["uniprot:O75469", "pocket:pdb:1M13/LBD"],
)
```

Two grounded locators, neither grey, so this finding *could* be `ESTABLISHED` — but
only if the two are genuinely independent measurements of the pocket volume rather
than the paper describing that structure. As written they are not independent, and
`SUPPORTED` is the honest level. The validator would accept `ESTABLISHED`; the
judgement is yours, and that asymmetry is exactly why this document exists.

## Audit before handing off

```python
store.unsupported_edges()   # edges asserted at SUPPORTED or above with zero citations
store.stats()               # cited_edge_fraction belongs in the report metrics
```

`cited_edge_fraction` below roughly 0.6 means the harvest asserted more than it
read. Evidence-family edges are hidden by default in the renderer precisely because
there are so many of them, so citing generously costs nothing visually — there is
no reason for an uncited edge to exist above `TENTATIVE`.

Then spot-check. Take five citations at random, resolve each locator, and confirm
that the cited span says what the finding says it says. Record the rate as
`extraction_spot_check_accuracy`. Citation hygiene that is never audited decays
within one run, because the failure is invisible until someone tries to check a
claim and cannot.
