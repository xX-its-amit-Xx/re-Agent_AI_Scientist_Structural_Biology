# The strategy ladder

Seven rungs. Each round of a sweep should climb one, because `strategies_tried` counts distinct
strategies and a saturation claim needs at least two. More importantly: repeating a query and
getting the same answer measures the query, not the literature.

Rungs 5 and 6 are the ones that get skipped and the ones that pay.

---

## 1. The obvious query, in our vocabulary

Say what you want in the terms this project uses. Fast, and establishes the baseline the rest of
the ladder is measured against.

Record it verbatim in `ChannelYield.queries`. A sweep that cannot be replayed cannot be extended
by the next run, which then redoes rung 1 instead of starting at rung 3.

## 2. The same question in the field's other dialects

Including the dialect that *predates* the current term. Term drift over a decade is severe:

| Now | Also / formerly |
|---|---|
| cryptic pocket | transient pocket, hidden site, occluded in apo |
| conformational ensemble | multiple-copy refinement, alternate conformers, structural heterogeneity |
| foundation model | pretrained representation, transfer learning, self-supervised encoder |
| co-folding | complex prediction, holo prediction, joint modelling |
| promiscuous binding | polypharmacology, cross-reactivity, broad specificity, multi-target |
| adaptable pocket | induced fit, plastic site, conformational selection |
| domain shift | covariate shift, dataset bias, out-of-distribution, train/test mismatch |

Pull synonym lists from an ontology rather than inventing them: MeSH, InterPro, GO, ChEBI. One
API call turns one query into eight, and it is the direct countermeasure to
`NeglectReason.VOCABULARY_MISMATCH`.

## 3. Structured query instead of text

If the axis has a native index, use its fields rather than its free text. Precision jumps and
the failure mode changes — which is what makes it a genuinely different strategy rather than a
rephrasing.

| Axis | Index | Query by |
|---|---|---|
| fold | RCSB Search API, Foldseek | sequence, assembly, ligand, resolution |
| sequence | UniProt, MMseqs2 | accession, family, taxonomy |
| pocket | pocket-comparison tools | site geometry |
| chemotype | ChEMBL, PubChem | target, activity type, scaffold |
| pathway | Reactome, KEGG | participant, event, hierarchy level |
| partners | STRING, IntAct | interactor, detection method, confidence |
| expression | HPA, GTEx | tissue, specificity class |
| promiscuity | ChEMBL | distinct-ligand counts, screening breadth |

For `analogous_cascade_role` there is no index. That axis lives on rungs 2, 5, and 6, and will
usually finish `truncated` rather than `saturated` — record that honestly rather than claiming an
exhaustion the method cannot deliver.

## 4. Citation traversal from the best hit so far

Both directions, from whichever source has proved most relevant.

**Backward** — its reference list, prioritising the methods section. Those references were
actually used; the introduction's are ceremonial.

**Forward** — who cites it. Finds the work that built on it and, more valuably, the work that
says it does not work.

This is the first rung that is not a *pull* channel, so it is the first that can return work
whose vocabulary we never guessed. A sweep with no traversal rung has an unmeasured blind spot
exactly where terminology differs from ours, and `SearchLedger.problems()` says so.

## 5. The negative form

Who reports this failing, or reports no relationship?

```
"failed to"          "no significant"        "did not improve"
"unable to reproduce"  "contrary to"         "we abandoned"
"worse than"         "no correlation"        "did not transfer"
"limitations of"     "caveat"                "unexpectedly"
```

Two reasons this rung is disproportionately valuable.

**Negative results are systematically under-cited** and often unpublishable, so they are absent
from any citation-ranked result — the failure mode `NeglectReason.NEGATIVE_RESULT` exists for.

**For pipeline design they are the most decision-relevant findings available.** "Method X fails
on adaptable pockets" eliminates a branch; "Method X works on rigid pockets" does not tell you
what to do about yours. A `FAILS_ON` edge is worth more than three `OUTPERFORMS` edges.

Look in the grey channels here — GitHub issues, competition post-mortems, discussion sections of
positive papers, theses. That is where negative results actually live.

## 6. Adjacent-field query

Who outside this field has the same *structural problem*?

Not the same subject — the same problem shape. An adaptable binding site is a
docking-to-a-moving-target problem, and that problem is worked on in materials science
(adsorption onto flexible frameworks), in bacterial multidrug resistance, and in olfaction.
Strip the biology from the problem statement, search on what is left, then check whether the
method transfers.

Coordinate with `cross-domain-analogy` rather than duplicating it: that skill generates
mechanisms to try, this rung looks for *literature* in adjacent fields on the same axis. If a
mechanism comes back, record `DiscoveryChannel.ANALOGY_TRANSFER` and remember the resulting
source is grounded even though the analogy is not.

## 7. Hand to `neglected-literature`

Spend the axis's exploration quota. Recency-adjusted candidates, high-quality-citer candidates,
sleeping beauties, non-English work, theses, prematurely abandoned methods, and graph-gap
candidates for this specific axis.

This rung is where the axis's `known_gaps` get written, because it is the rung that makes the
edges of the search visible.

---

## Sequencing

Rungs 1–3 are cheap and should always run. Rung 4 is cheap and skipped anyway; make it
mandatory. Rungs 5–7 cost real effort, and that is what the exploration quota is for.

Do not climb monotonically if the axis argues otherwise. A well-indexed axis like `fold` may
saturate on rungs 1, 3, 4 and never need 2. A reasoning-bound axis like
`analogous_cascade_role` starts at 2 and lives on 5–6. **What matters is two distinct
strategies and a flattened tail, not the order.**

## Recording

Each rung is a `SweepRound`:

```python
SweepRound(
    n_queries=6,
    n_candidates=41,
    n_new=9,
    strategy="rung 4: forward citation traversal from the two highest-TM hits, "
             "filtered to papers with a methods-section mention",
)
```

`strategy` must say how the round differed from the last. Identical strings collapse in
`strategies_tried`, and a saturation claim resting on one distinct strategy is rejected — which
is the intended outcome, because that claim was about the query.
