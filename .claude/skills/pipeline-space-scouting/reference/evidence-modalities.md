# Evidence modalities — where to search, what each one hides

Running one modality is the main way Stage 0 goes shallow. Each modality surfaces
a different population of methods and systematically suppresses a different one,
so the point of fanning out is not coverage for its own sake: it is that the
thing you most need — the failure mode — lives in exactly the modalities that are
least convenient to search.

Spawn one subagent per modality, in parallel, each returning `MethodCard` JSON
and nothing else (schema in `method-card.md`). Cap concurrency around six to eight.
Every card records which modality produced it in `scout.modality` and the verbatim
query strings in `scout.queries`, so a later pass can diff the landscape instead
of rebuilding it.

## The table, for reference at dispatch time

| Modality | Uniquely surfaces | Systematically hides | Tool | `SourceType` | Card `scout.modality` |
|---|---|---|---|---|---|
| Peer-reviewed literature | validated methods, ablations, negative controls | anything under 12 months old; routine practice | `paperclip` via MCP, `literature-harvest` | `paper` | `peer_reviewed` |
| Preprints | the frontier, 6 to 18 months ahead of journals | whether it replicates | `paperclip -s biorxiv,medrxiv,arxiv` | `preprint` | `preprint` |
| Challenge post-mortems | what actually won, and the mechanical tricks | methods that never entered a challenge | `WebSearch`, `WebFetch` | `competition` | `challenge_postmortem` |
| Code and issue trackers | real failure modes, real defaults, real cost | anything closed-source | `WebSearch`, `WebFetch`, `gh` CLI, `source-scout` | `code_repo`, `documentation` | `code_and_issues` |
| Patents | industrial methods absent from papers | anything filed in the last 18 months | `WebSearch` against Google Patents / Espacenet | `patent` | `patent` |
| Practitioner discussion | what people default to, and what they quietly abandoned | anything not socially discussed | `WebSearch`, `WebFetch`, `source-scout` | `blog`, `social`, `talk` | `practitioner_talk` |
| Benchmark papers | honest head-to-head comparisons on one eval set | methods the benchmark authors could not install | `paperclip`, `WebSearch` | `paper`, `benchmark` | `benchmark_paper` |

Two operational facts govern all of it. Stage 0 is a free-tier stage: literature
and web only, no Boltz, Modal or Tamarind credits. And Paperclip is reachable
**only** through the MCP tool
`mcp__claude_ai_Paperclip_for_literature_search__paperclip`, which takes a single
command string with no `paperclip` prefix; there is no local binary, so never
drive it from Bash. The full verified CLI reference is
`.claude/skills/literature-harvest/reference/paperclip-cli.md`, and everything
below assumes it.

---

## 1. Peer-reviewed literature

**What it uniquely surfaces.** Ablations. This is the only modality that
routinely tells you which component of a method carries the performance, which is
the information you actually need when deciding what to build. Also: negative
controls, statistical treatment, and the limitations section, which is the closest
thing to an honest failure-mode list that a method's own authors will publish.

**Where to look inside a paper.** Not the abstract. The limitations or discussion
section, the ablation table, and the supplementary methods, in that order. The
abstract reports the best number on the best subset; the ablation table reports
which part mattered; the limitations section names the subpopulation where it
breaks.

**Query templates.** Paperclip commands, run through the MCP tool. Remember that
`--save-as NAME` is the JSON switch, that `-n` at or below 100 is deterministic
while above 100 reorders earlier results, and that `--sort date` destroys
relevance badly enough to return topically unrelated papers, so prefer
`--year-min`.

```
# Landscape count first — cheap, titles and abstracts only, 15s / 200-row cap
sql "SELECT pub_year, COUNT(*) n FROM documents
     WHERE title ILIKE '%<problem class>%' GROUP BY pub_year ORDER BY pub_year DESC LIMIT 12"

# The method sweep for a problem class
search -s pmc "<task type> <output type> benchmark comparison" -n 50 \
  --has-full-text --year-min 2019 --exclude-article-type review-article --save-as m1

# Ablations, which is where the transferable knowledge is
search -s pmc "ablation study <method family>" -n 30 --has-full-text --save-as m2

# Limitations, scoped to the section that contains them
search -s pmc "<method family> failure cases" -n 40 --has-section Discussion --save-as m3

# Then pin the evidence to lines, which is what a MethodCard locator needs
grep -n -C 2 "limitation" /papers/<ID>/content.lines
grep -n -C 2 "did not improve" /papers/<ID>/content.lines
grep -n -C 3 "we were unable" /papers/<ID>/content.lines
```

The negative-result phrasings are worth keeping as a fixed list, because authors
do not label them: *did not improve*, *no significant difference*, *failed to
recover*, *we were unable to*, *contrary to expectation*, *only for*, *restricted
to*, *deteriorated*, *at the cost of*.

**Characteristic bias.** Publication bias plus recency lag. Nothing that failed
gets a paper, so the modality is structurally incapable of telling you what does
not work, and it lags the frontier by roughly a year. It also over-represents
methods that were easy to evaluate. A method requiring a proprietary dataset gets
one paper and no follow-ups, so it looks marginal in the literature even when it
is the thing that wins — the reference case study's challenge was won by a
federated fine-tune on four pharma companies' proprietary crystals, an approach
whose advantage is invisible from the published record.

**Confidence ceiling.** A reviewed paper is a grounded, non-grey source, so it can
support `established` when paired with a second independent grounded source.

---

## 2. Preprints

**What it uniquely surfaces.** The current frontier, and the version of a result
before reviewers made the authors soften it. Also the methods that will be
standard by the time your project ends, which matters when the project has a
deadline measured in weeks.

**Query templates.**

```
search -s biorxiv,medrxiv,arxiv "<task type> <method family>" -n 50 --since 6m --save-as p1
search -s arxiv "<method family> <metric name>" -n 40 --year-min 2025 --save-as p2

# The revision history is the signal: a v1 claim weakened in v3 is a finding
cat /papers/bio_<ID>/meta.json
```

For the frontier specifically, also check what the community has said about a
preprint rather than only what it says. Reviewer comments on preprint servers,
and threads discussing a preprint, are where the first independent replication
attempt appears.

**Characteristic bias.** No review, so the error bars are whatever the authors
felt like reporting, and the comparison baselines are chosen by the people being
compared against. Preprints also over-claim novelty, because novelty is what gets
the preprint attention. The skill's anti-pattern applies directly: a month-old
model with no independent evaluation is a risk, not an advantage. Record it, set
`maturity.level` to `announced_only` or `published_no_independent_eval`, and do
not build on it without a fallback.

**Confidence ceiling.** Grounded and non-grey by the contract's classification,
but treat a single preprint as `supported` at most, and `tentative` when the
claim is a headline number with no ablation.

---

## 3. Challenge and competition post-mortems

**What it uniquely surfaces.** The only modality that reports what won under blind
conditions, against a metric nobody could tune on, with mechanical constraints
that actually applied. It is also the only place the following three things are
routinely written down: the submission-format traps, the leaderboard mechanics,
and the approaches that entrants tried and discarded.

This modality is worth more than its share of the effort. The reference case
study is a post-mortem, and almost everything in it — the selection wall, the
correlated-error trap, the rescue-count sweep, the anchor-disaster band, the
leaderboard-shows-your-most-recent-submission trap — appears in no method paper
anywhere.

**Which challenges to sweep.** Anything of the "Critical Assessment" form, plus
the newer community benchmarks:

- **CASP** — protein structure prediction, including the ligand category. The
  assessors' papers, not the abstracts book, are where the honest analysis is.
- **CAPRI** — protein-protein docking and interface prediction. Long history of
  published assessor analyses of *why* groups failed.
- **CACHE** — hit-finding challenges with experimental validation, so the
  post-mortems report prospective rather than retrospective performance.
- **D3R Grand Challenge** — pose and affinity prediction, with per-stage analyses.
- **PoseBusters** — not a challenge but a validity audit, which functions the same
  way: it is the source of the "the pose is confidently wrong in a physically
  impossible way" class of finding.
- **OpenADMET** — property and structure challenges; the source of the reference
  case study.
- **Kaggle and similar** — for property prediction and DEL-ML style problems, the
  winning-solution write-ups thread is the post-mortem, and the "what didn't work"
  section of those posts is the highest-yield paragraph in the modality.
- Also worth a sweep: CAGI (genome interpretation), CAFA (function prediction),
  and any "blind challenge" or "community assessment" phrasing in the target
  domain.

**Query templates.** These are `WebSearch` calls, then `WebFetch` on the hits.

```
WebSearch: "<challenge name> <year> results assessment paper"
WebSearch: "<challenge name> <year> winning solution write-up"
WebSearch: "<challenge name> post-mortem what didn't work"
WebSearch: "<challenge name>" "lessons learned" OR "in hindsight"
WebSearch: "<challenge name> submission format validator error"
WebSearch: "<problem class>" blind challenge assessors analysis failure
WebSearch: site:zenodo.org "<challenge name>" submissions
WebSearch: <challenge name> leaderboard "most recent submission"
```

The last query looks oddly specific and is deliberately so. Leaderboard mechanics
are the cheapest points in any challenge and the least documented. In the
reference case study the leaderboard displayed each team's most recent submission
rather than its best, and three competitor teams destroyed their own standings
that way, the worst falling from 0.5521 to 0.4727 and from rank 2 to rank 18. That
fact is worth more than most method papers and it exists only in this modality.

Paperclip also indexes challenge assessment papers once they are published, so
run the literature sweep for them too:

```
search -s pmc "<challenge name> assessment" -n 30 --has-full-text --save-as c1
search -s pmc "critical assessment <problem class> prediction" -n 30 --save-as c2
```

**Characteristic bias.** Survivor bias among entrants: only groups confident
enough to enter appear, and only those willing to write a post-mortem explain
themselves. Small-sample noise is severe — a rank ordering over 50 entries
separated by hundredths of a metric point is not a reliable ranking of methods,
and in the case study the gap between rank 2 and rank 1 was 0.0085. Post-mortems
also conflate the method with the team's execution, and a post-mortem written by
the winner attributes success to the interesting part rather than the effective
part.

**Confidence ceiling.** `SourceType.COMPETITION` is classified as grey in
`report.py`. It is real evidence and often the only record of a negative result,
but a finding cannot be `established` on grey sources alone; it needs at least one
reviewed or structured-database source alongside. Use `supported`.

---

## 4. Code and issue trackers

**What it uniquely surfaces.** Four things that appear nowhere else. The **actual
default parameters**, which frequently differ from the paper's. The **cost**,
because someone always opens an issue titled "out of memory on a 40GB card". The
**silent failure modes**, because a tool that returns a plausible wrong answer
gets an issue and never gets a paper. And the **maintenance state**, which is a
cost: an abandoned repository charges you a week.

**Where to look, in order.**

1. Closed issues, not open ones. A closed issue with a maintainer's explanation is
   a mechanism; an open issue is a symptom.
2. The test fixtures. What the authors chose to test on tells you what they
   believe the method handles.
3. The commit that fixed a numerical bug. Any result published before it is now
   uncertain, and this is the single most under-appreciated invalidator of
   benchmark numbers.
4. The default config file, compared against the paper's reported settings.
5. Release notes and CHANGELOG for the phrase "fixes" next to anything numerical.

**Query templates.**

```
WebSearch: site:github.com "<method name>" issues "does not work"
WebSearch: site:github.com "<method name>" "out of memory" OR "OOM" GPU
WebSearch: site:github.com "<method name>" "cannot reproduce" paper results
WebSearch: site:github.com "<method name>" issue "silently"
```

With the `gh` CLI, which is available and much better than web search for this:

```bash
gh search repos "<method name>" --limit 20 --json fullName,stargazersCount,pushedAt,licenseInfo
gh search issues "reproduce paper" --repo <owner>/<repo> --state closed --limit 30
gh search issues "wrong OR incorrect OR unphysical" --repo <owner>/<repo> --limit 30
gh api repos/<owner>/<repo> --jq '{pushed_at,open_issues_count,license:.license.spdx_id,archived}'
gh api repos/<owner>/<repo>/releases --jq '.[0:5][] | {tag_name,published_at}'
```

That `gh api` one-liner fills four `MethodCard` fields at once:
`maturity.last_activity`, `maturity.level` if archived, `licence.code_spdx`, and a
maintenance signal for `maturity.adoption_signal`. Run it for every method you
card.

Note that the **weights licence is usually in a different place from the code
licence** — a model card on HuggingFace, a separate terms-of-use file, or a
registration form — and it is usually the blocking one. `hub_repo_details` on the
HuggingFace MCP server resolves this quickly for hosted weights.

**Characteristic bias.** Loud-minority bias: issues are filed by people who hit
problems, so the tracker over-represents failure relative to the true rate, and
you cannot read a failure *frequency* off it. It also has nothing to say about
closed-source or API-only methods, which is precisely where the industrial
methods are. And a quiet tracker is ambiguous: it means either that the tool
works or that nobody uses it, and distinguishing those requires the practitioner
modality.

**Confidence ceiling.** `code_repo` is grounded and not grey;
`documentation`, which covers issue trackers and release notes, is grey. A single
maintainer comment explaining a failure mode is strong evidence for `supported`
and is often the best evidence that will ever exist for that fact.

---

## 5. Patents

**What it uniquely surfaces.** Industrial methods that were never published,
including whole pipelines. Pharmaceutical and biotech companies patent
computational methods they do not write papers about, and a patent's claims
section is a complete-enough method description to reimplement from. Patents also
disclose the **problem** an industrial group thought was worth solving, which is
a signal about where the real difficulties are.

**How to search: not through Paperclip.** This is verified and load-bearing.
`patents` appears in Paperclip's `-s/--source` help string, but the tool returns
`Patents sources are not available.` Do not build a patent path through Paperclip.
Clinical trials and FDA regulatory documents *are* available; patents are not.

Use `WebSearch` and `WebFetch` against Google Patents and Espacenet instead. The
`source-scout` skill also covers patents as part of its grey-literature sweep and
is worth invoking rather than duplicating if a broader non-paper sweep is already
planned.

```
WebSearch: site:patents.google.com "<method family>" "<task type>"
WebSearch: site:patents.google.com <company name> machine learning <output type> prediction
WebSearch: site:worldwide.espacenet.com "<method family>"
WebSearch: "<method family>" patent claims "trained model" <domain term>
WebFetch: https://patents.google.com/?q=<url-encoded+query>&num=50
WebFetch: https://patents.google.com/patent/<publication number>/en
```

Read the **claims** and the **detailed description**, not the abstract, which is
written to be uninformative. The independent claim 1 gives the method's skeleton;
the dependent claims enumerate the variants the applicant thought were worth
protecting, which is a ranked list of what they found mattered. Cite with the
publication number as the locator, for example `patent:US11234567B2`.

**Characteristic bias.** Patents are written to be broad and to be difficult to
read, and they contain no honest evaluation whatsoever: there is no incentive to
report a comparison the applicant loses. Assume every performance number in a
patent is the best case. There is also an 18-month publication delay from filing,
so the modality is not a frontier source. And a patented method may be
unusable regardless of merit, which belongs in the card's `licence` block, not in
its performance discussion.

**Confidence ceiling.** `patent` is grounded and not grey, so it can contribute to
`established`, but a patent supports the claim *that a method exists and has this
shape*, never the claim *that it performs this well*. Card the method; leave
`performance` empty or mark the claim `reported_by: "method_authors"` with the
protocol fields honestly null.

---

## 6. Practitioner discussion

**What it uniquely surfaces.** The gap between published and used, which is the
skill's first guard rail. A method that wins benchmarks and that nobody runs is
telling you something about cost or fragility, and this is the only modality that
distinguishes those two. It is also where abandonment shows up: nobody publishes
"we stopped using X", but people say it.

**Where.** Lab blogs and Substack posts by people who run these pipelines daily;
company engineering blogs; conference talk recordings and posters, where the
Q&A is more informative than the talk; Discord and Slack community recaps;
long-form forum threads; and the "what didn't work for us" section of competition
write-ups, which technically belongs to the post-mortem modality but reads like
this one.

**Query templates.**

```
WebSearch: "<method name>" "in practice" OR "in production" slow OR expensive OR fragile
WebSearch: "we switched from" "<method name>" to
WebSearch: "<method name>" "gave up" OR "stopped using" OR "abandoned"
WebSearch: "<problem class>" "what actually works" blog
WebSearch: "<method name>" review "honest" OR "unimpressed" OR "overhyped"
WebSearch: <conference name> <year> "<problem class>" talk slides
```

The "we switched from X to Y" pattern is the highest-yield single query in this
modality, because it produces a directed comparison made by someone with no stake
in either method, which is the rarest evidence type in the whole landscape.

**Characteristic bias.** No sampling frame at all, so you cannot infer a rate from
it. Strong personality and recency effects, and a heavy skew towards whoever is
loudest in a given community. Vendor content dressed as practitioner content is
common. Treat a single blog post as a hypothesis to check against the code and
benchmark modalities, not as a finding.

**Confidence ceiling.** `blog`, `social` and `talk` are all grey. Perfectly
usable, often the only public record of a practitioner default, and capped: a
finding whose only support is grey sources cannot be `established` no matter how
many blog posts agree, because they are usually not independent.

---

## 7. Benchmark papers

**What it uniquely surfaces.** Head-to-head comparisons run by someone with no
stake in the outcome, on a single eval set, with a single protocol. This is the
only modality that produces numbers you are allowed to subtract, which makes it
the modality that fixes the `must_beat` baselines in the Stage 0 handoff.

It also uniquely surfaces the **installation and reproduction difficulty**
ranking, usually buried in a supplementary note: which methods the benchmark
authors could not get to run, and which ones' published numbers they could not
reproduce. That is a maturity signal available nowhere else.

**Query templates.**

```
search -s pmc "benchmark <problem class> methods comparison" -n 50 \
  --has-full-text --year-min 2020 --save-as b1
search -s pmc "systematic evaluation <method family>" -n 40 --save-as b2
search -s pmc "we could not reproduce" -n 30 --full-text --save-as b3
search -s pmc "<benchmark set name>" -n 50 --has-full-text --save-as b4

WebSearch: "<problem class>" independent benchmark "we evaluated" methods
WebSearch: "<benchmark name>" leaderboard current results
```

Then extract structurally rather than by reading, using the map engine, which is
the primitive that makes this tractable:

```
map --from s_<ID> --worker structured-extraction \
  --output-schema '<the MethodCard schema, or a trimmed performance-only subset>' \
  "<field-by-field extraction instructions>"
```

Write the extraction prompt field by field. A vague prompt with a strict schema
produces confidently-wrong values, which is worse than a failure.

**Characteristic bias.** The benchmark's own composition decides the ranking, and
benchmark authors choose composition. A benchmark set that over-represents easy
cases compresses the differences between methods; one that over-represents a
single subpopulation ranks methods by their performance on that subpopulation and
calls it general performance. Benchmark authors also tune their own method more
carefully than the comparators, even in good faith, simply because they know it
better. And benchmarks age: a set assembled before a model's training cutoff
measures memorisation, not prediction, which belongs in the card's
`protocol.ground_truth_leakage_risk`.

The practical defence is to read the benchmark's composition table before its
results table, and to record the composition in `performance[].eval_set`. In the
reference case study the test set was 76 fragment soaks and 108 drug-like
analogs, per-model scores were about 0.46 on the drug-like half and about 0.55 to
0.57 on the fragment half, and the drug-like half was where the points were. A
benchmark with a different mix of those two populations would have ranked the
same methods differently.

**Confidence ceiling.** A reviewed benchmark paper is the strongest single source
in this stage. Two independent benchmarks agreeing is `established`.

---

## Resolving disagreement between modalities

Modalities will disagree, and the disagreement is informative rather than
annoying: it usually localises the exact condition under which the method breaks.

### The precedence ladder

Highest authority first. This ordering is the skill's rule made explicit: prefer
benchmark and post-mortem sources over method papers when they disagree, because
**a method paper is written by people who want the method to work**.

1. **Our own measurement** on our own data. `SourceType.COMPUTATION` or
   `BENCHMARK`. Beats everything, and is why the falsification harness exists.
2. **A blind challenge result.** Nobody could tune on the held-out metric, and the
   mechanical constraints were real.
3. **An independent benchmark paper.** No stake in the outcome, one protocol
   applied uniformly.
4. **A reproduction attempt**, whether it succeeded or failed, including a "we
   could not reproduce" note in someone else's supplementary material.
5. **The maintainers' own issue tracker**, for claims about behaviour and cost.
   They know, and in a closed issue they will say.
6. **The method paper's ablation table**, which is more trustworthy than its
   headline number because it was constructed to isolate rather than to impress.
7. **The method paper's headline number.**
8. **A patent's performance claim**, or a preprint's headline number with no
   independent evaluation.
9. **Practitioner assertion** with no measurement attached.

### The rules that matter more than the ladder

**A lower rung wins if it is closer to your conditions.** The ladder ranks
evidential authority, not relevance. A practitioner reporting that a method fails
on exactly your subpopulation outranks a benchmark paper that never included that
subpopulation. In the case study, four independent signals — a per-family MLP, a
gnina convolutional network, a PDBbind-trained XGBoost model, and a ChEMBL-trained
Uni-Mol model — all inverted sign on the fragment half of the test set. Every one
of those methods has published benchmark numbers, and every one of those numbers
was irrelevant to what happened on those 76 ligands. Record the *domain of
validity* of a claim, not just the claim.

**Check whether it is a disagreement at all before adjudicating.** Most apparent
conflicts are two different eval sets, and the resolution is not to pick a winner
but to record both claims with their protocols and refuse to subtract them. This
is what `performance[].comparable_to` in the `MethodCard` schema is for. Two
numbers that do not name each other there are not in conflict; they are
unrelated.

**A negative result outranks a positive one at equal authority.** Asymmetric,
deliberately, and for a reason specific to this literature: positive results are
published and negative ones are not, so an observed negative result is drawn from
a far smaller and less filtered pool. When a benchmark paper says a method works
and a post-mortem says it did not, the post-mortem is describing conditions that
the benchmark did not cover, and those conditions are usually the interesting
ones. In the case study, an independent literature review concluded that on
co-folding pose pools, native-confidence ranking and cross-model consensus
largely do not beat random, and that consensus can be actively harmful because
agreeing models share correlated errors. The experiments then confirmed it: every
learned, agentic or consensus selector regressed against a plain z-scored
native-confidence argmax. Two modalities, one conclusion, and it contradicts the
implied claim of every consensus-scoring paper.

**Agreement between non-independent sources is not corroboration.** Three blog
posts citing the same preprint are one source. A benchmark paper reusing another
benchmark's test set is one eval set. The `Finding` validator enforces a weak form
of this by requiring two distinct grounded locators for `established`, but it
cannot detect shared provenance, so you must. When in doubt, ask what would have
to be false for both sources to be wrong together.

**When you cannot resolve it, say so and route it.** An unresolved disagreement is
not a failure of the scouting pass; it is an `open_question`, and open questions
are the input `cross-domain-analogy` needs. Without them that skill
free-associates. Write the disagreement as a question with both positions and the
conditions that would discriminate between them, which also tells Stage 3 what
cheap experiment to run first.

### Recording the resolution

Whatever you conclude, the report has to carry the conflict rather than the
conclusion alone.

- The winning claim becomes a `Finding` with the evidence that won.
- The losing claim becomes a second `Finding`, kind `NEGATIVE` or `RISK`,
  citing its own source, with `confidence` lowered and the discriminating
  condition in `data`.
- If one source contradicts another about a graph-level fact, emit
  `Predicate.CONTRADICTED_BY` to the losing `Paper` node rather than deleting it.
  The graph is append-only and a deleted disagreement is a lost finding.
- Note the conflict in `ModelReport.limitations` if it affects a `must_beat`
  baseline, because Stage 3 will optimise against that number and deserves to
  know it is contested.
