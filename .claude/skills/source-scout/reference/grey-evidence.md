# Grey evidence — using unreviewed sources defensibly

Grey literature is everything with no peer review and no formal publication: lab
blogs, Substack posts, LinkedIn and forum threads, GitHub issues, tool
documentation, conference talks, competition write-ups. This file is about using it
without either overclaiming or throwing it away, both of which are common and both
of which lose real information.

## Why it matters

The peer-reviewed record is a biased sample of what is known, biased in a specific
and predictable direction: it omits the things that are not publishable. Four
categories in particular exist almost exclusively in grey sources.

**Negative results.** A method that did not work is rarely a paper. It is a
paragraph in a blog post, a closed GitHub issue, a reply in a discussion thread, or
a slide in a talk that never became a publication. This matters more than any other
category for our purposes, because the reference case study's most valuable output
was its list of eight refuted approaches, and that list appears in no paper. The
contract makes the dependency explicit: `FindingKind.NEGATIVE` requires at least one
`Evidence`, and the evidence for a negative result is usually grey. If we cannot
cite grey sources properly, we cannot record negative findings at all.

**Parameter choices and practitioner defaults.** Papers report that a method was
used; the repository, the issue thread, or the release notes report the learning
rate, the number of seeds, the cutoff, and the reason. A silently changed default in
a tool's minor release has broken real pipelines, and the changelog is the only
record of it.

**Failure modes as encountered rather than as anticipated.** A paper's limitations
section lists the limitations the authors thought of. An issue tracker lists the
ones users hit. These are different sets, and the second is more useful.

**Work in progress and results ahead of publication.** Conference talks and posters
run twelve to eighteen months ahead of the corresponding paper, and some never
become one at all. A leaderboard is a dated, public, verifiable measurement that
frequently predates any description of the method that produced it.

Discarding grey sources on principle therefore does not make a knowledge graph more
rigorous. It makes it systematically optimistic, because the reviewed record
over-represents things that worked.

## What the contract actually says

Precision here matters, because both overclaiming and over-restricting come from
misremembering the rule.

`SourceType.is_grey` is true for exactly five values: `BLOG`, `SOCIAL`, `DOCS`,
`TALK`, and `COMPETITION`.

`SourceType.is_grounded` is true for everything **except** `ANALOGY` and
`EXPERT_PRIOR`. Grey sources are therefore **grounded**. A GitHub issue reporting
that a tool silently fails on a class of input is real evidence about the world, and
the contract treats it as such. What is not grounded is a mechanism borrowed from
another field, or a teammate's hunch — those are ungrounded regardless of how
confident anyone is.

The consequences, as the `Finding` validator enforces them:

- **Grey evidence can support a finding at `tentative` or `supported` with no
  additional source.** Cite it freely at those levels. This is the normal case and
  it needs no ceremony.
- **`Confidence.ESTABLISHED` requires at least two distinct grounded locators**, and
  additionally rejects the case where *every* grounded source is grey. The error
  message says the rest: grey sources are legitimate evidence, but `established`
  needs at least one reviewed or structured-database source, and `supported` is the
  correct level otherwise.
- **A finding that cites sources but no grounded source is capped at
  `speculative`.** This is the anti-laundering rule, and it is aimed at analogies
  wearing a citation, not at grey literature.
- **A finding with no evidence at all** is a different thing — the agent's own
  reasoning — and is permitted up to `supported` for the kinds that do not require
  citations. `OBSERVATION`, `BENCHMARK`, `NEGATIVE`, and `PRIOR` all require
  evidence; `DESIGN_CHOICE`, `RISK`, `HYPOTHESIS`, and `CONSTRAINT` do not.

### The gap the contract does not close

`CODE_REPO`, `DATASET`, `PREPRINT`, `PATENT`, and `THESIS` are **not** classified as
grey. That is defensible for each individually — a patent is examined, a preprint is
a complete manuscript, a dataset deposit has a DOI — but it means the validator will
accept `established` on the strength of two GitHub repositories, and two GitHub
repositories are not two independent reviewed sources.

Do not route around the spirit of the rule by reaching for a non-grey source type
that happens to fit. In particular, a repository whose only support for a claim is
its own README should be judged as grey even though `CODE_REPO` is not, because a
README is a claim by its author in exactly the way a blog post is. The distinction
that matters is not the platform, it is whether the source contains a measurement
someone else could check — which is the subject of the next section.

`COMPUTATION` is also not grey, and that is the useful end of this asymmetry: a
result we produced ourselves, with a repo-relative path to the artefact that
produced it, is a grounded non-grey source. That makes cheap local reproduction the
strongest available route from a grey claim to an `established` finding, and it is
often cheaper than finding a paper.

## Claim versus measurement

This is the single most useful distinction to hold while reading grey sources, and
it cuts across source types rather than aligning with them.

A **claim** is an assertion about a result. "Our model achieves state-of-the-art
performance on complex prediction." "Consensus scoring improves pose selection."
"This is 3x faster." The reader cannot check it. The evidence for it is the author's
word, and its strength is bounded by the author's track record and their incentives.

A **measurement** is a stated quantity, produced by a stated procedure, on stated
inputs, that another party could in principle reproduce or at least dispute
specifically. "On the 2024 held-out split of N=180 complexes, median ligand RMSD was
2.3 Ångström using the evaluation script at this commit." A measurement can be
wrong, and that is the point — it is specific enough to be wrong in an identifiable
way.

Grey sources contain both, in the same paragraph, and the discipline is to record
which is which. A blog post reporting "we ran this on our internal set of 400
compounds and the correlation was 0.62" is a measurement from a grey source and is
strong evidence at `supported`. The same post's opening line, "this is the best
approach available", is a claim and supports nothing.

Three tests for whether you are looking at a measurement:

1. **Is there an N?** A number with no sample size attached is a claim. This kills
   more grey benchmark assertions than any other test.
2. **Is the evaluation set named and separable from the training set?** "On our
   test set" is not a named set. "On the CASP16 targets" is.
3. **Could a hostile reader identify the specific step to attack?** If the answer is
   "the whole thing is unspecified", it is a claim.

Record the distinction in the `Finding`. A measurement from a grey source is an
`OBSERVATION` or a `BENCHMARK`. A claim from a grey source, if it is worth recording
at all, is a `HYPOTHESIS` — and the excerpt should make clear it is the author's
assertion, not a result.

## How to cite each grey source type

The requirement is that a reader six months later can find the exact thing you read
and see whether you represented it fairly. That needs four elements in every case:
**who**, **when**, **the exact claim in their words**, and **a durable pointer**.

Two general rules first.

**Put the verbatim span in `Evidence.excerpt` and never paraphrase there.** The
field's description is explicit about this: paraphrase belongs in the finding's
statement, and the excerpt exists so a reader can check the paraphrase. For grey
sources the excerpt is doing more work than usual, because it may be the only
surviving copy of the text — grey sources get edited and deleted, and papers do not.

**Archive it, and record the archive.** Take a snapshot before you write the node.

```bash
# Trigger a Wayback Machine capture
curl -sSL -o /dev/null -w '%{http_code} %{url_effective}\n' "https://web.archive.org/save/$URL"

# Check what snapshots already exist
curl -s "https://archive.org/wayback/available?url=$URL"
```

`archive.today` is a reasonable fallback. Some platforms — LinkedIn in particular,
and Substack behind a subscriber wall — block archivers, and then the verbatim
excerpt plus the access date genuinely is the record. Say so in `notes` rather than
leaving the reader to discover that the link is dead and the text is gone.

### A lab blog or company engineering post

`SourceType.BLOG`. Locator: the canonical post URL including the path, not the blog
home page and not a tag or category listing. Record the author as named on the post,
the publication date as stated, and the archive URL.

```python
Evidence(
    source_type=SourceType.BLOG,
    locator="https://example-lab.github.io/posts/2025-03-11-cofold-seeds/",
    title="Why we stopped increasing seed counts past twenty — <Author Name>, 11 Mar 2025",
    excerpt="Past about twenty seeds per target we saw no further improvement in "
            "the best-of-pool RMSD on our 60-complex internal set; the curve is flat "
            "from 20 to 80.",
    year=2025,
)
```

Note what the `title` field is being used for: `Evidence` has no author or date
field, so author and date go into `title`, which is the only free-text identity
field available. Do this consistently — author name followed by the date — because
it is what makes the ledger of evidence readable and it is what a reviewer scans.
Put the archive URL in the finding's `data` payload or in the node's notes.

If the post is undated, which is common on personal sites, say so explicitly rather
than guessing, and record the date you accessed it. An undated grey source is
substantially weaker because you cannot tell what it was responding to.

### A Substack post

`SourceType.BLOG`. Substack post URLs are stable and include a slug, so the
canonical URL is a good locator. Two Substack-specific cautions: posts behind a paid
wall cannot be verified by anyone without a subscription, which should be noted; and
Substack authors edit published posts without a visible revision history, so the
archive snapshot is doing real work here.

### A LinkedIn or X post

`SourceType.SOCIAL`. This is the weakest source class and needs the most careful
handling, because it is the easiest to misrepresent and the hardest to verify later.

Cite it as evidence about **what one named person claimed on one specific day**, and
write the finding's statement in that form. Not "co-folding models fail on
macrocycles" but "<Name>, a maintainer of <tool>, stated in a LinkedIn post on 4
February 2026 that their group observes systematic failures on macrocyclic ligands".
The second is defensible and checkable; the first launders one person's remark into a
fact about the world, which the guard rail in the skill file forbids in exactly
those terms.

Locator: the permalink to the individual post, never the author's profile. LinkedIn
post permalinks are long and ugly and that is fine. If you can only find the post
through a search snippet and cannot open the post itself, you have not read the
source and must not cite it — record it as a lead in `open_questions` instead.

### A forum thread

`SourceType.SOCIAL`, or `DOCS` if it is a project's own discussion board and the
answer is from a maintainer.

Locator: the deep link to the **specific post or reply**, not the thread root.
Almost every forum supports this — a `#post-12345` anchor, a `/posts/<id>` path, a
permalink option in the post menu. A thread root as a locator sends the reader to a
forty-reply thread to find one sentence.

Record who said it and what standing they have, because on a forum that is the whole
difference between sources. A tool's maintainer saying the tool does not support
something is close to authoritative. An anonymous user saying it is a report worth
following up. Both are citable; they are not equivalent, and the `title` field
should say which you have.

### A GitHub issue, pull request, or discussion

`SourceType.DOCS`. This is the highest-quality grey source class we routinely use,
because issues are dated, attributed, threaded, rarely deleted, and often contain a
reproduction case, which is to say a measurement.

Locator: the issue URL with the comment anchor if the relevant statement is in a
comment rather than the body.

```python
Evidence(
    source_type=SourceType.DOCS,
    locator="https://github.com/owner/repo/issues/412#issuecomment-1234567890",
    title="Maintainer <Name> confirms ligand bond orders are inferred from geometry, 8 Jan 2026",
    excerpt="Yes — if CONECT records are absent we fall back to distance-based bond "
            "perception, which is why your aromatic rings come back as single bonds.",
    year=2026,
)
```

Record the issue's **state and resolution**, because they change what it means. An
open issue with no maintainer response is an unconfirmed report. A closed issue with
a fix is a documented and repaired bug, and the version it was fixed in is the fact
you actually need. A closed-as-not-planned issue is a documented limitation, and
those are frequently the most valuable of all — a maintainer explaining why
something will not be supported is the honest limitations section.

### Tool documentation and release notes

`SourceType.DOCS`. Locator must pin the **version**, because documentation without a
version is not a citation — the page will describe different behaviour next release.
Prefer a versioned documentation URL where one exists, or a changelog entry, or a
tagged file in the repository. Record the version number in the `title`.

This is the one grey class where the source is close to authoritative on its own
subject, because a project's own release notes are the definitive record of what
that project changed.

### A conference talk, poster, or recorded seminar

`SourceType.TALK`. Locator: whatever durable pointer exists, in this order of
preference — a deposited poster or slide deck with a DOI, a recording URL with a
timestamp, the conference programme entry with session and abstract number.

For a recording, **include the timestamp**, because a reader is otherwise asked to
watch forty minutes to check one sentence. Most video platforms accept a start
parameter in the URL. For a poster, note whether you read the poster itself or only
its abstract in the programme, since abstracts routinely promise results the poster
does not show.

Talks age unusually badly as evidence, in a specific way: a result presented as
preliminary in a talk may have been revised or withdrawn before the paper. Record
whether the presenter framed it as preliminary, and treat an eighteen-month-old talk
with no corresponding publication as a signal in itself.

### A competition write-up or leaderboard

`SourceType.COMPETITION`. This class is grey by the contract, which is correct — the
write-ups are unreviewed — but it contains some of the best measurements available,
because the evaluation was run by a third party on a held-out set that the
participant did not control. That combination is rarer than peer review.

Locator: the specific discussion post or notebook URL, plus the competition slug.
Record the metric name, whether it is the public or private leaderboard, and the
date, since leaderboards move. Record the rank *and* the score, since a rank with no
score is uninterpretable across competitions.

## Corroborating a grey claim

When a grey claim matters enough to build on, promote it. There are four routes, in
increasing order of cost and of strength.

**Find the structured measurement it implies.** A blog post asserting that a
compound class binds a target implies rows in an activity database. Query ChEMBL,
BindingDB, or PubChem for the pair. If the measurement is there, the finding now
rests on a `DATABASE` source and the blog post becomes a pointer that led you to it
— which is what `source_locator` is for. This is the cheapest route and it works
surprisingly often, because grey authors frequently describe public data without
citing it.

**Find the reviewed paper.** Hand the claim to `literature-harvest` in the target
field's own vocabulary rather than the blogger's. Three outcomes, all useful: a
paper says the same thing, and you have `established`; a paper says the opposite,
and you have a `CONTRADICTED_BY` edge and a much more interesting finding than you
started with; nothing exists, and the grey source is the only record, which is
itself worth stating in the report because it bounds how much weight the pipeline
can put on it.

**Find a second independent grey source.** This does not reach `established` — the
validator explicitly rejects all-grey support at that level — but it moves a claim
from `tentative` to `supported` and is worth having. The word doing the work is
*independent*. Two blog posts, one of which links to the other, are one source. Two
people reporting the same failure in the same issue thread after reading each other
are one source. Check for a citation trail before treating them as two.

**Reproduce it ourselves.** The strongest route, and often the cheapest of the four
when the claim is about a tool's behaviour rather than about biology. A local check
becomes `SourceType.COMPUTATION`, with a repo-relative path to the artefact as its
locator, and `COMPUTATION` is grounded and not grey — so one grey source plus one
cheap reproduction satisfies the `established` requirement legitimately, not as a
loophole. If a grey source says a tool silently mis-parses an input, running it on
that input costs minutes and produces a citable artefact.

Whichever route, **keep the grey source in the evidence list.** It is what told us
where to look, and removing it once a better source is found erases the discovery
path and makes the graph's provenance a fiction.

## Red flags

Signals that a grey source is a claim dressed as a measurement. None is
disqualifying on its own; two or more together mean the source supports nothing
above `tentative`, and should probably be recorded as a `HYPOTHESIS` rather than an
`OBSERVATION`.

**An unattributed benchmark claim.** A number with no stated evaluation set, no
sample size, and no procedure. "Achieves 0.89 accuracy" with nothing else on the
page. There is nothing here to check, and the number's precision is doing rhetorical
work that its provenance does not support.

**No evaluation split, or a split that cannot be separated from training.** "On our
test set" where the test set is unnamed and undescribed. This is the most common
defect in grey benchmark claims and the most consequential, because the difference
between a real held-out split and a random split of a redundant corpus is usually
the entire reported improvement.

**Marketing register.** "Revolutionary", "state of the art", "unprecedented
accuracy", "10x faster" with no baseline named. Register is a genuine signal, not a
matter of taste: prose written to persuade rather than to inform correlates strongly
with claims that do not survive checking. Note in particular an unnamed baseline —
"10x faster" than *what*, configured *how*, is the whole question, and its absence is
rarely accidental.

**A README asserting state of the art with no eval script.** The specific test: is
there a command in the repository that reproduces the claimed number, and is the
held-out split defined in a file rather than in prose? If not, record the absence
explicitly, because "we looked for an eval script and there is none" is a finding.
This is the case where the contract's non-grey classification of `CODE_REPO` is
misleading, and where you should judge the source as grey regardless.

**No version numbers.** A claim about a tool's behaviour with no version is not
checkable, because the behaviour may have changed. This applies to the tool under
discussion and to its dependencies.

**A vendor benchmarking its own product against competitors it configured.** The
comparison is not necessarily wrong, but the configuration of the competitor is the
one thing the author had both the ability and the incentive to get wrong. Look for
whether the competitor's own recommended settings were used, and whether the
comparison was reviewed by anyone from the other side.

**A figure with no axis labels, no units, or no error bars**, especially where the
claimed effect is small. Related: a claimed improvement with no indication of run-to-
run variance in a pipeline that involves random seeds.

**A single cherry-picked example presented as a result.** One dramatic before-and-
after case. The reference case study contains the cautionary instance: an
agentic ligand re-drawing step produced one visually convincing repair and, over the
full set, moved a structure from 3.88 to 24.63 Ångström error. A single example
selected after the fact carries no information about the distribution.

**Edited or deleted without notice.** If the archive snapshot differs materially
from the live page, that is worth recording. A grey source that has been silently
revised should be cited at the snapshot, with a note.

**A secondary source presented as primary.** A blog post summarising a paper is not
evidence about the biology; it is evidence about what the blogger understood. Cite
the paper. The same applies to a post summarising another post, and to a thread reply
restating the thread's first message.

**Confident prose with no first-person experimental content.** "Co-folding models
struggle with induced fit." Possibly true, and this author has not shown that they
know it. The tell is the absence of any sentence beginning "we ran", "we observed",
or "in our set".

## What the report must say

The Model Report's `metrics` and `limitations` are where grey reliance becomes
visible rather than buried, and the skill file requires a source-type breakdown
figure for exactly this reason: a knowledge graph resting mostly on blog posts is a
real risk, and it should be legible at a glance rather than discoverable only by
auditing every node.

State plainly, in `limitations`, which findings rest on grey sources alone and what
would be needed to raise them. That sentence is what lets a downstream stage decide
how much weight to put on a prior, and it is the difference between a graph that
knows what it does not know and one that merely looks confident.
