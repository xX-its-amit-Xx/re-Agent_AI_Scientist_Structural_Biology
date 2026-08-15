# Domain shift

The gap between what is known and what must be predicted. Measuring it is the
single highest-value thing Stage 1 does, and in the reference case it reorganised
the entire pipeline. The authors of that entry said, in their own retrospective,
that they should have spent 70 % of ideation on the test-set distribution rather
than on methods. This document is how to spend it.

The claim this document defends: **a prior has a domain of validity, and a prior
handed downstream without its domain of validity is worse than no prior at all.**
Not less useful — worse. A signal that helps one subpopulation and hurts another,
delivered unlabelled, causes the consumer to apply it uniformly and lose points on
the half it hurts, while believing it is helping.

## Step 1 — define the two sets precisely

You need two populations and one similarity function.

- **The reference set** is what is known: the ligands in the harvested corpus, the
  compounds a model was trained on, the assay conditions that produced the
  training labels — whatever the prior you are about to hand over was derived
  from. Write down which one, because "known" is ambiguous and the answer changes
  by a lot depending on the choice. The training set of a public model and the set
  of co-crystallised ligands of your target are very different reference sets.
- **The test set** is `ProblemSpec.test_items` — the things you must produce
  predictions for. Read it from the spec; never enumerate it by hand.
- **The similarity function** is one of the axis methods in
  [axis-methods.md](axis-methods.md), with its parameters pinned. Morgan radius 2
  at 2048 bits for compounds, TM-score for folds, PS-score for pockets. The
  parameters are part of the measurement.

If the reference set is ambiguous, compute the distribution against each candidate
reference set separately and report all of them. Discovering that the test items
are close to the public training data but far from the target's own known ligands
is itself a finding, and averaging the two would erase it.

## Step 2 — compute the nearest-neighbour distribution

For each test item, its similarity to its single most similar reference item. That
scalar per test item is the distribution you report.

```python
import numpy as np
from rdkit import Chem, DataStructs
from rdkit.Chem import rdFingerprintGenerator

gen = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=2048)


def fingerprints(smiles: list[str]) -> tuple[list, list[int]]:
    """Returns (fingerprints, indices of inputs that parsed). Never silently drop rows."""
    fps, ok = [], []
    for i, s in enumerate(smiles):
        m = Chem.MolFromSmiles(s)
        if m is None:
            continue
        fps.append(gen.GetFingerprint(m))
        ok.append(i)
    return fps, ok


def nn_similarity(test_smiles: list[str], reference_smiles: list[str]) -> np.ndarray:
    """Max Tanimoto from each test item to any reference item. One value per test item."""
    test_fps, _ = fingerprints(test_smiles)
    ref_fps, _ = fingerprints(reference_smiles)
    if not ref_fps:
        raise ValueError("empty reference set — the domain shift is undefined, not zero")
    return np.array(
        [max(DataStructs.BulkTanimotoSimilarity(fp, ref_fps)) for fp in test_fps]
    )


def report_distribution(nn: np.ndarray) -> dict:
    """The numbers that go in the report. Note what is absent: no bare mean."""
    qs = [0, 5, 10, 25, 50, 75, 90, 95, 100]
    return {
        "n": int(nn.size),
        "quantiles": {f"p{q}": round(float(np.percentile(nn, q)), 4) for q in qs},
        "mean": round(float(nn.mean()), 4),          # reported ONLY alongside the quantiles
        "std": round(float(nn.std(ddof=1)), 4),
        "frac_below_0_3": round(float((nn < 0.3).mean()), 4),
        "frac_below_0_4": round(float((nn < 0.4).mean()), 4),
        "frac_above_0_7": round(float((nn > 0.7).mean()), 4),
    }
```

The same code shape works for any axis: replace the similarity function with
TM-score against a template library, or pocket PS-score, or assay-condition
overlap. The structure of the measurement — nearest neighbour per test item,
reported as a distribution — is axis-independent.

Two variants worth also computing, because they answer different questions:

- **k-th nearest neighbour** (k = 5) instead of the first. A test item with one
  close reference neighbour and no others is in a very different position from one
  sitting inside a dense cluster, and the first-nearest-neighbour value cannot tell
  them apart.
- **Reverse coverage**: for each reference item, how many test items have it as
  their nearest neighbour. If 200 test items all point at three reference items,
  your effective reference set is three items, however large the corpus.

## Step 3 — never report the mean alone; the bimodality is the finding

A mean nearest-neighbour similarity of 0.45 is consistent with two completely
different worlds: every test item sits at 0.45 (uniform moderate shift, one
pipeline can serve the set), or half sit at 0.7 and half at 0.2 (two populations,
and no single pipeline serves both). The second is far more common in practice,
and the mean is precisely the statistic that hides it.

So: report the quantiles, plot the distribution, and test for multimodality
explicitly.

```python
import numpy as np
from sklearn.mixture import GaussianMixture


def bimodality_evidence(nn: np.ndarray, random_state: int = 0) -> dict:
    """Three independent readings. Agreement across them is what justifies a split."""
    x = nn.reshape(-1, 1)

    # 1. Model selection: does a two-component mixture beat one component on BIC?
    #    A BIC improvement of ~10 or more is conventionally treated as strong.
    bics = {}
    fits = {}
    for k in (1, 2, 3):
        gm = GaussianMixture(n_components=k, random_state=random_state, n_init=10).fit(x)
        bics[k] = float(gm.bic(x))
        fits[k] = gm
    best_k = min(bics, key=bics.get)

    # 2. Shape statistics. Negative excess kurtosis with low skew is the signature
    #    of a flat or two-humped distribution rather than a single peak.
    from scipy.stats import kurtosis, skew
    shape = {"skew": float(skew(nn)), "excess_kurtosis": float(kurtosis(nn, fisher=True))}

    # 3. The gap: the widest empty interval in the middle 80 % of the data. A clear
    #    valley in the histogram shows up here as a large gap.
    s = np.sort(nn)
    lo, hi = np.percentile(s, 10), np.percentile(s, 90)
    mid = s[(s >= lo) & (s <= hi)]
    gaps = np.diff(mid)
    widest = float(gaps.max()) if gaps.size else 0.0
    gap_at = float(mid[int(gaps.argmax())]) if gaps.size else float("nan")

    out = {
        "bic": bics,
        "best_n_components": int(best_k),
        "bic_gain_1_to_2": round(bics[1] - bics[2], 2),
        "shape": shape,
        "widest_interior_gap": round(widest, 4),
        "gap_location": round(gap_at, 4),
    }
    if best_k >= 2:
        gm = fits[best_k]
        order = np.argsort(gm.means_.ravel())
        out["components"] = [
            {
                "mean": round(float(gm.means_.ravel()[i]), 4),
                "sd": round(float(np.sqrt(gm.covariances_.ravel()[i])), 4),
                "weight": round(float(gm.weights_[i]), 4),
            }
            for i in order
        ]
    return out
```

Hartigan's dip test is the purpose-built statistic for unimodality and is worth
running if you have it available (the `diptest` package provides it); it returns a
p-value against the null of unimodality. It is not in the standard scientific
Python stack, so the three readings above are the portable substitute. **Do not
declare bimodality on a single statistic.** Declare it when the histogram shows
it, the two-component mixture wins on BIC, and the subpopulations turn out to
correspond to something real — which is the next step.

## Step 4 — test whether the subpopulations are a real thing

A statistical split is a curiosity. A split that aligns with a physicochemical or
experimental property is a mechanism, and only the second justifies designing two
pipelines.

So take the split point the mixture suggests, partition the test items, and test
every property you have against the partition.

```python
import numpy as np
from scipy.stats import mannwhitneyu
from rdkit.Chem import Descriptors, rdMolDescriptors


def properties(mol) -> dict:
    return {
        "mw": Descriptors.MolWt(mol),
        "heavy_atoms": mol.GetNumHeavyAtoms(),
        "rot_bonds": rdMolDescriptors.CalcNumRotatableBonds(mol),
        "logp": Descriptors.MolLogP(mol),
        "tpsa": Descriptors.TPSA(mol),
        "rings": rdMolDescriptors.CalcNumRings(mol),
        "hbd": rdMolDescriptors.CalcNumHBD(mol),
        "hba": rdMolDescriptors.CalcNumHBA(mol),
        "fsp3": rdMolDescriptors.CalcFractionCSP3(mol),
    }


def test_partition(props: list[dict], labels: np.ndarray) -> dict:
    """Mann-Whitney U per property, plus a rank-biserial effect size.

    The p-value tells you the split is not noise; the effect size tells you whether
    it matters. Report both, and remember you are running ~9 tests — apply a
    Bonferroni or Benjamini-Hochberg correction before calling anything significant.
    """
    out = {}
    keys = props[0].keys()
    for k in keys:
        a = np.array([p[k] for p, m in zip(props, labels) if m])
        b = np.array([p[k] for p, m in zip(props, labels) if not m])
        if a.size < 3 or b.size < 3:
            continue
        u, p = mannwhitneyu(a, b, alternative="two-sided")
        rank_biserial = 2.0 * u / (a.size * b.size) - 1.0     # -1 .. +1
        out[k] = {
            "median_low_similarity_group": round(float(np.median(a)), 3),
            "median_high_similarity_group": round(float(np.median(b)), 3),
            "p_value": float(p),
            "effect_size_rank_biserial": round(float(rank_biserial), 3),
        }
    return out
```

If the low-similarity subpopulation is systematically smaller, less flexible, and
has fewer rings than the high-similarity one, you have not found a statistical
artefact — you have found that part of your test set is fragments and part is
drug-like molecules, and those are two different prediction problems. That is
exactly what happened in the reference case, where the operational definition of
"drug-like" ended up being molecular weight at or above 330, or five or more
rotatable bonds, or 24 or more heavy atoms, splitting the 184-item test set into
76 crystallographic fragments and 108 drug-like analogues.

Also check for the non-chemical partitions, because they are easy to miss:
experimental method (soak versus co-crystallisation), assay type, deposition date,
source laboratory. A domain shift that turns out to be "everything after 2023 came
from a different lab" is still a domain shift.

## Step 5 — measure whether the prior actually inverts

This is where the reference case earned its lesson, and it is worth stating in
full because the pattern generalises.

The test set contained 76 fragments from crystallographic soaks and 108 drug-like
analogues. The fragments had Morgan radius-2 Tanimoto below 0.3 to *every* known
holo ligand of the target, and frequently engaged **zero** of the canonical pocket
anchor residues that every published description of that pocket emphasises. Any
signal trained on drug-like binders — meaning any signal whose reference set was
the drug-like half of chemical space — **inverted sign** on the fragments: it did
not merely become uninformative, it became anti-correlated with the truth, so
following it was worse than choosing at random.

That was confirmed **four independent ways**, with four different model families
and four different training corpora: a per-family multilayer perceptron, a
convolutional neural network pose scorer, a gradient-boosted model trained on a
public structure-affinity set, and a pretrained molecular representation model
fine-tuned on a bioactivity database. Four architectures, four datasets, one
result. That is what makes it a property of the domain shift rather than a bug in
one model.

Two further pieces of evidence from the same repository, both of which are
symptoms of the same underlying split: crystal-anchor priors worked on the
drug-like half and failed on the fragments, and per-model scores ran around 0.46
on drug-like items versus 0.55 to 0.57 on fragments — so the two halves were not
even equally hard, and the points were on the drug-like side.

How to run this test yourself, when you have any ground truth at all:

```python
from scipy.stats import spearmanr


def prior_validity_by_subpopulation(scores: np.ndarray, truth: np.ndarray,
                                    subpop: np.ndarray) -> dict:
    """Spearman correlation of the prior against the truth, within each subpopulation.

    `scores` is the prior's output, `truth` the ground-truth quality, `subpop` a
    label array. The finding is not the overall rho — it is the per-subpopulation
    rho, and specifically whether the SIGN differs.
    """
    out = {}
    for label in np.unique(subpop):
        m = subpop == label
        if m.sum() < 8:
            out[str(label)] = {"n": int(m.sum()), "note": "too few items to correlate"}
            continue
        rho, p = spearmanr(scores[m], truth[m])
        out[str(label)] = {"n": int(m.sum()), "spearman_rho": round(float(rho), 4),
                           "p_value": float(p)}
    rhos = [v.get("spearman_rho") for v in out.values() if v.get("spearman_rho") is not None]
    out["_sign_inversion"] = bool(len(rhos) >= 2 and min(rhos) < -0.05 < 0.05 < max(rhos))
    return out
```

An overall correlation near zero is the *signature* of a sign inversion, not
evidence of a useless prior. Two subpopulations with equal and opposite
correlations average to nothing. So whenever an aggregate correlation comes back
near zero, split it before concluding anything — the prior may be strongly
informative in both halves, in opposite directions, and therefore highly usable
once labelled.

If you have no ground truth for either subpopulation, you cannot run this test.
Then the honest output is a `RISK` finding naming the untested subpopulation, not a
`PRIOR` finding with a guessed domain of validity.

## Step 6 — state the domain of validity in the Finding

`FindingKind.PRIOR` requires at least one `Evidence` (see `Finding._enforce_grounding`
in `reagent/contracts/report.py`), and a domain-shift measurement you ran yourself
is `SourceType.COMPUTATION` with a repo-relative path as the locator. Put the
validity domain in the `statement`, not only in `data`, because the statement is
what a human reads and the whole failure mode here is a consumer applying a prior
outside its range.

```python
from reagent.contracts import Confidence, Evidence, Finding, FindingKind, SourceType

Finding(
    id="F-LIT-021",
    kind=FindingKind.PRIOR,
    statement=(
        "Similarity-to-known-ligand scores are usable for ranking on the drug-like "
        "subpopulation (n=108, nearest-neighbour Tanimoto median 0.52) but INVERT "
        "SIGN on the fragment subpopulation (n=76, nearest-neighbour Tanimoto below "
        "0.3 against every reference ligand). Apply per subpopulation; applying it "
        "uniformly scores worse than not applying it at all."
    ),
    confidence=Confidence.SUPPORTED,
    evidence=[
        Evidence(
            source_type=SourceType.COMPUTATION,
            locator="reports/<run-id>/stage1/domain_shift/nn_tanimoto.json",
            excerpt="p50=0.22 (fragments) vs p50=0.52 (drug-like); BIC gain 1->2 = 41.7",
        ),
    ],
    data={
        # The machine-readable half. A downstream stage must be able to act on this
        # without parsing the statement prose.
        "valid_for": {"subpopulation": "drug_like", "n": 108,
                      "definition": "MW>=330 or rot_bonds>=5 or heavy_atoms>=24"},
        "invalid_for": {"subpopulation": "fragment", "n": 76,
                        "definition": "not drug_like", "observed_effect": "sign inversion"},
        "similarity_metric": {"name": "morgan_tanimoto", "radius": 2, "fp_size": 2048},
        "reference_set": "70 holo entries of the target receptor, additive-filtered",
        "confirmations": 1,      # raise this only for genuinely independent confirmations
    },
    kg_nodes=["uniprot:O75469"],
    tags=["domain-shift", "prior", "subpopulation"],
)
```

Confidence calibration for this kind of finding: a single computation of your own
supports `SUPPORTED`, not `ESTABLISHED`. `ESTABLISHED` requires two independent
grounded sources with distinct locators, at least one of them reviewed or from a
structured database — four independent model families reaching the same conclusion,
as in the reference case, does qualify, provided you cite four distinct locators
rather than one summary file.

Propagate the same structure into the handoff, where the SKILL.md contract already
reserves the fields:

```json
"subpopulations": {
  "fragment":  {"n": 76,  "nn_similarity_median": 0.22, "definition": "..."},
  "drug_like": {"n": 108, "nn_similarity_median": 0.52, "definition": "..."}
},
"priors": [
  {"claim": "...", "valid_for": "drug_like", "invalid_for": "fragment",
   "measured_by": "reports/<run-id>/stage1/domain_shift/nn_tanimoto.json"}
]
```

And if the axis itself has a limited domain of validity, put it in the
`AxisSpec.notes` of the domain profile as well — `AXIS_REGISTRY_NOTE` step 4
requires exactly this, and Stage 1 is required to propagate it into the prior it
hands Stage 3.

## Figures to produce

Every figure must declare the question it answers, per the `Visualization`
contract. Four figures cover this analysis.

1. **Nearest-neighbour similarity histogram with the split marked.** Question:
   "how far do the items we must predict sit from anything we know?" One panel,
   overlaid kernel density estimate, a vertical line at the mixture's split point,
   and the two subpopulation counts annotated. Use a rug plot underneath rather
   than relying on bin choice — bin width can manufacture or hide a valley, so a
   histogram alone is not sufficient evidence of bimodality and the rug shows the
   raw values.
2. **Empirical cumulative distribution function**, same data. Question: "what
   fraction of the test set is below any given similarity threshold?" This is the
   bin-width-free companion to the histogram and the figure to trust when the two
   disagree. Mark the 0.3 and 0.4 thresholds.
3. **Test-by-reference similarity heatmap**, test items on rows ordered by their
   nearest-neighbour similarity, reference items on columns ordered by cluster.
   Question: "is the coverage uniform, or does everything point at a few reference
   items?" Blocks of dark rows are the underserved subpopulation, made visible.
   The SKILL.md requires a heatmap for the domain-shift finding, and this is it.
4. **Similarity versus the discriminating property**, a scatter with the two
   subpopulations coloured. Question: "does the similarity split correspond to a
   physical property, or is it an artefact of the metric?" This is the figure that
   converts a statistical split into a mechanism, and the one a sceptical reader
   will ask for.

If you also ran the prior-validity test, add a fifth: per-subpopulation
correlation between the prior and the truth, as a slope chart or a paired bar with
zero clearly marked, so the sign change is visible rather than inferred. A sign
inversion described in prose gets discounted; a sign inversion shown as two bars
on opposite sides of zero does not.

## Anti-patterns

- **Reporting a mean similarity.** Distributions decide pipelines; means hide
  bimodality, which is the thing you most need to see.
- **Assuming the target's known ligands represent the test items.** Check it. In
  the reference case they did not, and everything followed from that.
- **Declaring bimodality from one statistic**, or from a histogram at one bin
  width. Require agreement between the shape of the distribution, a model-selection
  criterion, and an interpretable property split.
- **Concluding a prior is useless from a near-zero aggregate correlation.** That
  is the signature of a sign inversion. Split, then conclude.
- **Reporting the domain shift and then not acting on it.** The measurement exists
  so Stage 3 designs against the partition. A subpopulation split that appears in
  the report but not in `handoff.payload.subpopulations` has not been delivered.
- **Treating the fragment-versus-drug-like split as a general law.** It is the
  reference case's split. Yours may be by assay, by organism, by deposition era,
  or absent entirely. Measure it; do not assume it.
