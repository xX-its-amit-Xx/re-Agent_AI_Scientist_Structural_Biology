# Twelve reasons a relevant paper is under-cited

Each has its own detection strategy, its own evidencing signal, and its own way of being
abused. The abuse column matters most: this skill's characteristic failure is rationalising
irrelevance, and each mechanism has a specific shape that failure takes.

A citation-count threshold is not a mechanism and appears nowhere below. It is a filter
widener — it decides what enters the candidate pool, never what leaves it.

---

## 1. `too_recent` — citations have not had time to accrue

**Detect:** age-normalise. `AttentionProfile.citations_per_year` with `as_of_year`, or the
percentile within field *and* year. Under three years old, raw count carries almost no
information about quality.

**Evidence required:** `year` and `as_of_year`, giving `age_years <= 3`.

**Where to look:** bioRxiv, arXiv, ChemRxiv, and the current year's conference proceedings.
Preprints in the last 18 months are systematically absent from any citation-ranked result.

**Abuse:** claiming recency for a five-year-old paper. The validator enforces the window.

**Note:** recency cuts both ways. A recent paper is *unvalidated*, not *undervalued*. Cap
confidence accordingly — a preprint is `SourceType.PREPRINT` and not a peer-reviewed paper.

---

## 2. `small_field` — few possible citers exist

**Detect:** compare within field, never globally. Twenty citations in a subfield producing
forty papers a year is saturation; the same count in machine learning is invisible.

**Evidence required:** `field_size_note` or `field_percentile`.

**Where to look:** specialist journals with small circulations; the *Journal of
Cheminformatics* / *Journal of Molecular Graphics and Modelling* tier rather than *Nature*.

**Abuse:** defining the "field" narrowly enough that any paper is a leader in it. State the
field as a searchable population, not a description.

---

## 3. `high_quality_citers` — few citations, but from work that matters

**Detect:** examine *who* cites it. Three citations from the three papers a subfield is built
on is a categorically different signal from three passing mentions, and citation count cannot
distinguish them. Prestige-propagation over the citation graph formalises this — see Chen,
Xie, Maslov & Redner (2007), *Finding scientific gems with Google's PageRank*, J. Informetrics.

**Evidence required:** `notable_citers` populated with identifiers.

**Where to look:** OpenAlex or Semantic Scholar citation lists. Read the citing sentence, not
just the citing paper: *"we adopt the approach of [X]"* is load-bearing, *"see also [X]"* is not.

**Abuse:** counting any well-cited citer as high-quality. The citer must be *relevant to our
problem*, not merely famous. A 4,000-citation review that lists it in a table is not evidence.

---

## 4. `sleeping_beauty` — dormant, now waking

**Detect:** flat citations for years, then acceleration. The phenomenon was named by van Raan
(2004), *Sleeping Beauties in science*, Scientometrics; Ke, Ferrara, Radicchi & Flammini
(2015), PNAS, give the "beauty coefficient" B as a quantitative measure and show these exist
across all fields. There is usually a *prince* — the paper whose attention revived it.

**Evidence required:** `dormancy_years >= 5` plus `citation_trend` or `awakened_by`.

**Where to look:** citation-by-year curves. Find the prince and read it: it usually explains
what changed, and that explanation is often exactly the fact you needed.

**Abuse:** reading a flat curve as dormancy when it is simply a paper nobody needed. Dormancy
requires the *subsequent acceleration*; without it you have an uncited paper.

---

## 5. `interdisciplinary_orphan` — too far from any field's core

**Detect:** reference list spans distant fields, and neither field's core cites it. Search the
*union* of two literatures for work that references both — a query neither field's own
vocabulary produces.

**Evidence required:** written justification naming the two fields and why each ignores it.

**Where to look:** journals that sit between fields; work by authors who publish in two
disjoint communities. Uzzi, Mukherjee, Stringer & Jones (2013), *Atypical combinations and
scientific impact*, Science, found the highest-impact work pairs a conventional core with an
atypical tail — orphans are candidates for that tail.

**Abuse:** treating "spans two fields" as merit. Most such work is weak in both. The
justification must say what the *combination* buys, not that it exists.

---

## 6. `negative_result` — nulls are systematically under-cited

**Detect:** query explicitly for failure. Nobody cites the paper reporting that a method does
not work, and citation practice favours positive findings (Duyx et al. 2017, *Scientific
citations favor positive results*, J. Clin. Epidemiol.).

**Evidence required:** written justification identifying the null claim.

**Where to look:** the discussion and limitations sections of positive papers; GitHub issues;
competition post-mortems; registered reports; conference posters. **The grey channels are where
negative results actually live**, because they are hard to publish.

Query forms that work: `"failed to"`, `"no significant"`, `"did not improve"`, `"unable to
reproduce"`, `"contrary to"`, `"we abandoned"`, `"worse than the baseline"`.

**Abuse:** none, really. This is the highest-value category for pipeline design and the most
systematically missing. If your ledger has no negative results, the search is incomplete
regardless of what else it found.

---

## 7. `language_barrier` — not in the English-language index

**Detect:** the work exists in a regional index only. Non-English literature is
systematically excluded from reviews and carries findings absent from the English record
(Amano et al. 2021, PLOS Biology, for conservation science; Neimann Rasmussen & Montgomery
2018, Systematic Reviews, on exclusion practice).

**Evidence required:** `language` set to something other than English.

**Where to look:** SciELO (Latin America), J-STAGE (Japan), KCI (Korea), CNKI (China),
African Journals Online, and national theses portals. Translate the query terms rather than
the query — a machine-translated sentence retrieves badly; a translated *term* retrieves well.

**Abuse:** citing a paper you cannot read. If you cannot verify the claim, say so in the
`excerpt` field or do not cite it.

---

## 8. `not_indexed` — outside the bibliographic record

**Detect:** it exists but no index carries it. Theses, technical reports, conference-only
papers, pre-digital literature, internal reports later released.

**Evidence required:** `not_indexed_in` naming the indexes checked.

**Where to look:** institutional repositories, ProQuest and national thesis portals, lab
websites, `site:` searches over university domains, the Internet Archive for dead lab pages.
Route grey channels through `source-scout`; this skill covers the *scholarly-but-unindexed*.

**Abuse:** using "not indexed" for something simply not found. Name the indexes you checked.

---

## 9. `prematurely_abandoned` — dropped for a reason that has expired

**Detect:** heavily cited, then dropped. Find *why* it was abandoned, then check whether the
reason still holds. **Compute cost expires. Data scarcity expires. Implementation difficulty
expires.** A method rejected in 2009 for needing more structures than existed may be the right
method now.

**Evidence required:** written justification naming the original objection and the evidence it
no longer applies.

**Where to look:** the review that dismissed it, and the citation curve's drop point. The
dismissing sentence usually states the objection explicitly — that sentence is the finding.

**Abuse:** assuming abandonment was fashion. Sometimes the method was wrong. The
justification must name the *specific* expired constraint, and "the field moved on" is not one.

**This is the highest-yield mechanism for this project specifically,** because the pipeline
being designed has access to compute and pretrained models that did not exist when much of
the structural-biology methods literature was written.

---

## 10. `low_amplification` — no institutional megaphone

**Detect:** good work from a small group, a non-anglophone institution, or an author with few
papers. Cumulative advantage operates on authors and institutions as much as papers — the
Matthew effect (Merton 1968, Science).

**Evidence required:** written justification. Do **not** filter on venue or institution; that
is the mechanism itself, and applying it while claiming to correct for it is worse than not
trying.

**Where to look:** author-trail traversal from a single good hit. If one paper by an unknown
group is excellent, read their other four.

**Abuse:** this is the vaguest category and the easiest to assert. Prefer a concrete mechanism
from the list above where one applies, and use this only when the work is genuinely good and
genuinely unamplified.

---

## 11. `vocabulary_mismatch` — the same thing in other words

**Detect:** the work exists but uses terms that predate or sidestep the field's current ones.
No keyword query in our vocabulary can return it, and semantic search only partly helps
because embeddings inherit the corpus's own term frequencies.

**Evidence required:** written justification naming the term pair.

**Where to look:** older literature especially. Term drift is severe over a decade — what is
now called a "cryptic pocket" was described as "transient" or "hidden" or "solvent-inaccessible
in the apo form"; "foundation model" was "pretrained representation"; "conformational ensemble"
was "multiple-copy refinement". Look up the *concept* in an ontology (MeSH, InterPro, GO) and
take the synonym list; that is what ontology expansion is for.

**Abuse:** claiming mismatch to justify a loose match. Name both terms and show they denote
the same thing.

---

## 12. `never_stated` — the connection exists in no paper

**Detect:** a graph query, not a search. Swanson (1986), *Undiscovered public knowledge*,
Library Quarterly: A relates to B in one literature, B to C in another, and no paper states
A–C. His fish-oil / Raynaud's and magnesium / migraine cases came from complementary
literatures that did not cite each other.

**Evidence required:** written justification, plus the two-hop path as evidence. Channel is
`graph_gap`.

**Where to look:** our own KG. See [graph-gap-queries.md](graph-gap-queries.md).

**Abuse:** two-hop paths are cheap and mostly meaningless. Rank by how *disjoint* the two
literatures are and how *specific* the intermediate is — a path through a hub like "protein"
is noise, a path through a specific shared cofactor is not. Expect a very low hit rate and
report the ranking, so a reader can see what was filtered.

---

## Using them together

The reasons are not exclusive; a 2019 Japanese-language thesis on an abandoned method is four
of them at once. Record all that apply — each one is a separate reason to believe the low count
is uninformative, and they compound.

What does **not** compound is relevance. Four reasons for under-attention plus no relevance is
still no relevance. Run verification on the claim itself, exactly as for a well-cited source.
