# Failure-mode catalogue for computational prediction pipelines

A starter catalogue, organised so you can find yours from the symptom rather than
from the name. It is deliberately not specific to structure prediction: the same
modes appear in ADMET regression, DNA-encoded-library hit-finding, and binder
design, and the entries say where. Where a number appears, it is a real measured
number from the reference case study
(`.claude/skills/ai-scientist/reference/pxr-case-study.md`) rather than an
illustration. Where no number appears, the honest instruction is to measure it
yourself.

Each entry has the same six parts. **Symptom** is what you observe, and it comes
first because that is how you will arrive here. **Mechanism** is why it happens,
which is what determines whether a mitigation can work at all. **Who suffers**
names the method classes, so you can check your own pipeline. **Mitigations** are
ordered by cost. **Residual risk** is what remains after mitigation, because every
one of these is reduced rather than removed.

Add to this file rather than rediscovering: a `MethodCard` failure mode with a
null `catalogue_ref` is an instruction to write a new entry here.

---

## Find yours from the symptom

| What you observe | Entry |
|---|---|
| Aggregate score fine, one subpopulation much worse, and a prior that helps one hurts the other | [A1](#a1-subpopulation-sign-inversion) |
| Benchmark performance good, our performance much worse, no bug found | [A2](#a2-train-and-test-distribution-shift) |
| Local validation competitive, blind score below the unlearned baseline | [A3](#a3-label-starved-supervised-component), [C1](#c1-overfitting-to-a-small-validation-set) |
| "Cleaning up" the reference data made everything worse | [A4](#a4-ground-truth-artifacts-and-the-urge-to-clean-them) |
| A model is suspiciously good on old items and ordinary on new ones | [A5](#a5-temporal-leakage-through-the-training-cutoff) |
| Big candidate pool, good achievable best, mediocre realised score, and nothing you try to fix it helps | [B1](#b1-the-selection-wall) |
| Consensus, voting, or averaging scores worse than picking one model | [B2](#b2-correlated-errors-across-ensemble-members) |
| Cross-model comparison picks the same model almost every time, or picks nonsense | [B3](#b3-non-commensurable-scores-across-models) |
| Pool ceiling improves when you add candidates, realised score does not move | [B4](#b4-oracle-reachable-but-unselectable-candidates) |
| A fix helps at a small dose and hurts at a large one | [B5](#b5-over-application-of-a-corrective) |
| Refinement improves geometry and does not improve the score | [B6](#b6-local-refinement-cannot-repair-a-global-error) |
| An agent or generative step produced a confident, catastrophic output | [B7](#b7-generative-and-agentic-hallucination) |
| A method fails to improve when the task gets easier | [C1](#c1-overfitting-to-a-small-validation-set) |
| Every method scores the same locally, but the leaderboard spreads them out | [C2](#c2-validation-noise-floor-and-non-monotonicity-with-the-real-metric) |
| The proxy you rank by does not move with the score you are graded on | [C3](#c3-decoupled-proxy-metric) |
| Someone is beating you with something that is not a better prediction | [C4](#c4-metric-structure-and-metric-gaming) |
| Confident predictions are wrong at the same rate as unconfident ones | [C5](#c5-confidence-miscalibration) |
| An intervention has a good average and terrifying individual cases | [C6](#c6-high-variance-intervention-judged-on-its-mean) |
| A submission scored zero, or far below its own local evaluation | [D1](#d1-format-and-connectivity-failures-that-score-zero) |
| Your standing got worse after a submission that was not worse | [D2](#d2-leaderboard-mechanics) |
| Ran out of submissions before the good ideas were tested | [D3](#d3-submission-budget-exhausted-on-untested-candidates) |
| Weeks spent on infrastructure that never produced an output | [D4](#d4-infrastructure-activation-lag) |
| Lots of method exploration, and the test set is still not characterised | [D5](#d5-effort-misallocated-away-from-the-test-set) |

## Ranked by how much of the metric they cost

Sorted by observed or structural severity, which is the sort order the skill asks
for. The first three can zero a submission or invert a ranking outright; the rest
cost fractions of the metric.

| Rank | Entry | Observed cost |
|---|---|---|
| 1 | D1 format and connectivity | Total. In the case study a connectivity failure scored that compound **0** and added a 20 Å RMSD penalty |
| 2 | D2 leaderboard mechanics | Total, and self-inflicted. Competitor teams fell from 0.5521 to 0.4727, rank 2 to rank 18 |
| 3 | A1 subpopulation sign inversion | Inverts the sign of a prior on part of the test set; in the case study, confirmed four times independently |
| 4 | B1 the selection wall | The whole gap between pool ceiling and realised score, which was the largest single quantity in the case study |
| 5 | A3 label-starved supervised component | 0.4762 against a 0.5640 achieved without learning, rank 32 against rank 2 |
| 6 | C1 overfitting to a small validation set | One method fell from first to last when the validation set grew from 35 to 53 items |
| 7 | B2 correlated errors in consensus | Consensus, medoid, Borda and reciprocal-rank fusion all regressed against a plain argmax |
| 8 | D3 submission budget exhaustion | 11 wasted submission slots, 8 of which one pre-flight gate would have caught |
| 9 | B5 over-application of a corrective | 0.5640 at 8 swaps against 0.5587 at 20 |
| 10 | C6 high-variance intervention | 2.251 Å against 2.230 Å, so 0.020 worse on the mean with large individual swings |

---

# A. Data and distribution failures

## A1. Subpopulation sign inversion

**Symptom.** Aggregate performance looks acceptable. Broken down by
subpopulation, one slice is much worse than another, and — the diagnostic
signature — a prior, feature, or auxiliary model that *helps* on one slice
*hurts* on the other. Adding what everyone agrees is domain knowledge makes the
overall score go down.

**Mechanism.** The test set contains two or more populations that were not drawn
from the same distribution, and every learned or curated signal was fitted to one
of them. The signal is not weak on the other population; it is anti-correlated,
because the structure it encodes genuinely does not hold there. This is worse than
absent knowledge, since an anti-correlated feature with high confidence actively
moves predictions in the wrong direction.

**Who suffers.** Anything carrying a prior fitted to a reference distribution:
template transfer, pharmacophore and anchor constraints, learned scoring
functions, pretrained property models, transfer learning of any kind. In the
reference case study the test set was 76 PanDDA fragment soaks plus 108 drug-like
analogs, and the fragments had Morgan-radius-2 Tanimoto below 0.3 to *every* known
holo ligand for the target while often engaging **zero** canonical pocket anchors.
Any drug-like-trained signal inverted sign on them, confirmed four times
independently with a per-family multilayer perceptron, a gnina convolutional
network, a PDBbind-trained XGBoost model, and a ChEMBL-trained Uni-Mol model.
Crystal anchor priors showed the same split: fine on drug-like, failing on the
fragments.

Outside structure prediction the shape recurs exactly. In ADMET, a model fitted to
a company's historical chemical series inverts on a new series. In DEL-ML,
enrichment features learned on one library topology mislead on another. In binder
design, developability heuristics derived from approved antibodies mislead on
non-antibody scaffolds.

**Mitigations, cheapest first.**
1. **Characterise the test set into subpopulations before choosing methods.** This
   is the cheapest and highest-return action available in Stage 0. The case study's
   authors put it as spending 70 percent of ideation on the test-set distribution
   rather than on methods.
2. **Report every metric per subpopulation, never only in aggregate.** In the case
   study, per-model scores were about 0.46 on the drug-like half and about 0.55 to
   0.57 on the fragment half. An aggregate number conceals a spread larger than the
   margin that decided the standings.
3. **Attach a domain of validity to every prior you hand downstream**, and make it
   a required field rather than a footnote. `AxisSpec.notes` in
   `src/reagent/contracts/problem.py` exists for this, and its documentation
   instructs Stage 1 to propagate an axis that inverts sign on a subpopulation.
4. **Route by subpopulation instead of averaging over it.** Two pipelines with a
   detector in front beats one pipeline with a compromised prior, whenever the
   subpopulation is detectable from the inputs alone.

**Residual risk.** Detecting the subpopulation at prediction time may itself be
unreliable, and a routing mistake applies the wrong prior with full confidence.
There may also be a third population you have not noticed; the two you found were
the two that were labelled.

## A2. Train and test distribution shift

**Symptom.** A method's published benchmark number is much better than what you
get, and no bug explains the difference. Reproducing the benchmark exactly works;
running on your data does not.

**Mechanism.** The published number was measured on a population resembling the
training distribution. Yours is not that population. Nothing is broken; the number
was never a prediction about your case. Distinguish this from A1: A1 is a shift
*within* your test set, A2 is a shift between the method's world and yours.

**Who suffers.** Every pretrained model, which now means most of the pipeline.
Also every benchmark-derived `must_beat` baseline you inherit, which is why Stage 0
is required to fix baselines rather than copy them.

**Mitigations.**
1. **Measure the shift instead of asserting it.** For the axes your problem
   declares, compute the similarity distribution between your test items and the
   method's training set, when the training set is known. This is what Stage 1's
   neighbourhood machinery exists to produce.
2. **Re-establish the baseline locally.** A trivial baseline you ran yourself
   beats a state-of-the-art number you read. Both belong in the report, labelled.
3. **Close the shift with data, when data is the lever.** The case study's
   4-stage curriculum fine-tune escalated specificity while decreasing learning
   rate: drug-like compounds for 2000 steps at 3e-4, then promiscuous target
   classes for 1500 at 1e-4, then all 1,264 nuclear-receptor ligand-binding
   domains with the target up-weighted threefold and two relatives twofold for 800
   steps at 5e-5, then the 70 target holo structures for 350 steps at 2e-5, with
   the interface loss weight rising from 1.0 to 3.0.
4. **Recognise when the gap is not closeable by method.** The case study's entry
   scored 0.5640 and the winner 0.5725, a gap of 0.0085, and the winner's advantage
   was a federated fine-tune on four pharma companies' proprietary crystals.
   Distinguishing a gap closeable by cleverness from one closeable only by data is
   itself a Stage 0 deliverable, and getting it wrong wastes the entire project.

**Residual risk.** Fine-tuning towards your distribution moves the model away from
somewhere else, which is A1 waiting to happen if your test set is heterogeneous.
And you can only measure shift against training sets that were disclosed.

## A3. Label-starved supervised component

**Symptom.** A learned component looks competitive or better in local
cross-validation, then scores below the unlearned baseline it was meant to
replace. Adding regularisation, changing the model family, and tuning
hyperparameters all fail to close the gap.

**Mechanism.** The number of free parameters, or more precisely the effective
capacity of the model family combined with the number of comparisons you made
while developing it, exceeds what a few dozen labels can constrain. The fitted
model encodes the validation set, and there is no regularisation strength that
recovers a signal which was never resolvable at that sample size. Development
itself leaks: every architecture you tried and rejected on the same 50 items spent
some of their information content.

**Who suffers.** Learned re-scorers, learned selectors, learned calibrators, small
fine-tunes, and any per-target model in a domain where labels are experimental and
therefore scarce. In the case study, an XGBoost LambdaMART pose re-scorer with 37
features, trained on 35 to 53 holo structures, scored **0.4762** and placed rank
32 of about 50 — the project's worst submission, against 0.5640 and rank 2 for an
approach that learned nothing at all.

**Mitigations.**
1. **Count your labels before designing the component.** Tens of labels supports
   choosing among a handful of pre-specified alternatives, and nothing more.
2. **Use the unlearned baseline, which needs zero labels.** In the case study that
   was each model's own native confidence, z-scored. It won.
3. **If you must learn, learn one parameter.** A single threshold or a single
   blending weight fitted on 50 items is defensible; 37 features are not.
4. **Pre-register the comparison.** Decide the evaluation and the acceptance
   criterion before fitting, so the count of comparisons you made stays honest.

**Residual risk.** The temptation returns every time the label set grows a little,
and growth from 35 to 53 was not remotely enough. Nobody has published the label
count at which a learned selector overtakes a native-confidence baseline for this
class of problem, so treat the crossover as unknown rather than as nearby.

## A4. Ground-truth artifacts and the urge to clean them

**Symptom.** You notice that the reference data violates a physical or statistical
expectation, correct it, and every downstream metric gets worse — monotonically,
not noisily.

**Mechanism.** The apparent artifact is real signal. The reference data was
produced under conditions that genuinely differ from your idealisation, and your
correction is imposing the idealisation on top of a measurement that was already
right. In the case study, relaxing the ligand alone with the MMFF force field —
including relaxing the *ground truth* structures — monotonically hurt, because the
bound conformer is legitimately strained. The strain was not error; it was the
binding event.

**Who suffers.** Any physics-based or rules-based post-processing step: force-field
relaxation, geometry idealisation, protonation-state normalisation, tautomer
canonicalisation. In property prediction the same mode appears as outlier removal
and unit normalisation across assay protocols that are not actually
interconvertible.

**Mitigations.**
1. **Test the correction on the ground truth first.** If applying it to known-correct
   data degrades the metric, the correction is wrong and no amount of tuning saves
   it. This is a cheap, decisive test, and it is exactly what the case study ran.
2. **Ask what the reference measurement actually measured** before deciding it is
   noisy. A strained conformer, an unusual protonation state, and an assay outlier
   are all sometimes the finding rather than the flaw.
3. **Make corrections opt-in per item and gate them on ground truth**, so that the
   cases where they help are adopted and the rest are not. See C6.

**Residual risk.** Some artifacts are real artifacts, and refusing to clean
anything is its own failure. The distinguishing test is whether the correction
degrades known-good data.

## A5. Temporal leakage through the training cutoff

**Symptom.** A model performs conspicuously well on items resembling publicly
deposited data and ordinarily on genuinely new items. Its benchmark numbers are
excellent and its prospective performance is not.

**Mechanism.** The evaluation items, or close relatives of them, were in the
training data. A test set assembled from a public repository before a model's
training cutoff measures retrieval, not prediction. This is not usually fraud; it
is the default outcome of benchmarking a model whose training corpus was scraped
from the same repository the benchmark came from.

**Who suffers.** Every pretrained model evaluated retrospectively. It is the
reason blind challenges and prospective validation are worth disproportionately
more than benchmark numbers, and the reason `performance[].protocol` in the
`MethodCard` schema has a required `ground_truth_leakage_risk` field.

**Mitigations.**
1. **Record the model's training cutoff and the deposition dates of the evaluation
   items.** If you cannot establish either, write that down; unknown is the answer
   and it is informative.
2. **Prefer a temporal split over a random split, and a blind challenge result
   over both.**
3. **When carding a method, write the leakage risk into the card even when you
   cannot quantify it.** A later reader can then discount the number
   appropriately instead of trusting it.

**Residual risk.** Near-duplicates evade date-based filtering, and "close
relative" is defined by a similarity measure you also chose. Leakage through a
relative is undetectable without the training set.

---

# B. Generation, selection, and ensembling failures

## B1. The selection wall

**Symptom.** Your candidate pool contains excellent answers — the best-achievable
score over the pool is far better than what you submit — and every attempt to
choose better fails. Learned selectors, agentic selectors, consensus, and clever
heuristics all score at or below the simplest possible rule.

**Mechanism.** Choosing the right candidate requires information that correlates
with correctness, and with a fixed pool and no ground truth you do not have any
such information beyond what the generators already gave you. Plausibility is not
the target: a candidate can be chemically reasonable, physically valid, and
internally consistent while being the wrong answer. The case study's formulation
is worth memorising verbatim: **"Chemically plausible is not native."** The wall is
not a tuning problem; it is an information-theoretic ceiling on selection given
what you know.

**Who suffers.** Every pipeline whose architecture is generate-then-select, which
after the last few years is most of them: pose selection from a co-folding pool,
compound triage from a generative library, variant ranking, design filtering.

**Mitigations.** Note that the first two accept the wall rather than attacking it,
and those are the two that worked.
1. **Widen the pool.** Diversity in the pool raises the ceiling without requiring
   better selection, and it is the lever most likely to pay. The case study ran six
   co-folders and reached a pool ceiling of roughly 1.08 Å median RMSD, far better
   than any single model realised.
2. **Rescue the failure tail with a decorrelated generator.** Do not try to score
   the tail better; replace it. Overwriting the 8 lowest-confidence items with a
   different model's output moved the score from 0.5472 to 0.5640, and one rescued
   item went from 0.123 to 0.919.
3. **Normalise before comparing.** See B3: the one selection change that worked was
   z-scoring each model's confidence within that model before comparing across
   models, worth 0.0476.
4. **Do not build a learned selector without hundreds of labels.** See A3.
5. **Spend the effort on generation instead.** See `generation-vs-selection.md` for
   the diagnostic that tells you which regime you are in, and note that the wall is
   what makes that diagnostic decisive rather than academic.

**Residual risk.** The wall is a property of your information, so it moves only
when new information arrives — an experimental measurement, a physical constraint
that genuinely discriminates, a signal from outside the generators. Widening the
pool raises the ceiling and thereby *increases* the unrealised gap, which looks
like regress on the diagnostic while being progress on the score.

## B2. Correlated errors across ensemble members

**Symptom.** Consensus scoring, voting, medoid selection, rank fusion, or simple
averaging performs worse than picking one member. Worse, the ensemble is most
confident exactly where it is wrong.

**Mechanism.** Ensemble arguments assume member errors are close to independent.
Modern models in one domain are trained on the same public data, with related
architectures, and often share pretrained components, so their errors are strongly
correlated. Agreement then measures shared inductive bias rather than
correctness. Concretely: if members' errors have pairwise correlation rho, the
variance of their mean falls only to a fraction `(1 + (m-1)·rho) / m` of the
single-member variance, which for high rho barely falls at all. And consensus does
something actively harmful that averaging does not: by selecting the modal
candidate, it systematically discards the one diverse member that was right,
which is precisely the member you assembled the ensemble to obtain.

**Who suffers.** Consensus docking, consensus scoring, ensemble QSAR by voting,
multi-model rank fusion, medoid or centroid selection, and any use of
inter-model agreement as a confidence proxy. In the case study, consensus, medoid,
Borda count, and reciprocal-rank fusion were all tried and all regressed against
a plain z-scored native-confidence argmax. An independent literature review had
already reached the same conclusion before the experiments confirmed it: on
co-folding pose pools, native-confidence ranking and cross-model consensus largely
do not beat random, and consensus can be *actively harmful* because agreeing
models share correlated errors.

**Mitigations.**
1. **Measure the error correlation before ensembling.** If member errors correlate
   strongly on a validation set, voting cannot help and you can stop.
2. **Use diversity to cover, not to vote.** This is the productive inversion. The
   case study used six models to widen the pool and to rescue the tail, and never
   to agree. That is the same diversity spent on a mechanism that benefits from it.
3. **Prefer within-member selection followed by across-member arbitration** to
   pooled voting: pick each model's best sample by its own confidence, then choose
   among models on a normalised scale.
4. **If you must combine, weight by decorrelation rather than by performance.** A
   weaker member with independent errors is worth more than a strong duplicate.

**Residual risk.** Error correlation is estimated on a validation set, and the
subpopulations where members diverge most are usually the ones the validation set
under-samples. Measured decorrelation is optimistic.

## B3. Non-commensurable scores across models

**Symptom.** Comparing candidates across models by their confidence scores selects
one model nearly always, or selects apparently arbitrary items. The chosen items
are not the ones a human inspecting the pool would choose.

**Mechanism.** Confidence outputs from different models are not on a shared scale.
Different heads, different training objectives, different calibration, sometimes
different sign conventions. Comparing them directly compares the models'
score distributions, not the candidates' quality, so the model with the most
generous scale wins by default.

**Who suffers.** Any cross-model selection step, and any pipeline mixing a
predicted-error metric with a predicted-quality metric without harmonising sign
and scale.

**Mitigations.**
1. **Select within each model using that model's own native confidence**, which is
   the signal that head was trained to produce. The case study's mapping was
   AlphaFold3 `iptm`, Boltz-2 negated `complex_ipde`, OpenFold3 negated mean
   predicted alignment error over the pocket-and-ligand block, and Chai-1 `iptm`.
   Note that two of the four required a sign flip.
2. **Then z-score each model's per-item best scores across all test items and take
   the per-item argmax of the z-score.** This is the entire trick, and in the case
   study it moved the score from 0.4996 to 0.5472, a gain of 0.0476 that came from
   normalisation alone with no new model and no new candidates.
3. **Sanity-check the resulting per-model selection counts.** If one model is
   chosen for nearly every item, the normalisation has not worked.

**Residual risk.** Z-scoring uses the test set itself as the normalisation
population, so it assumes the test set is large enough for a stable mean and
standard deviation, and it makes each item's selection weakly dependent on the
others. With a small test set this is fragile, and nobody has established where
the floor is.

## B4. Oracle-reachable but unselectable candidates

**Symptom.** You add a candidate-generation trick, the pool's best-achievable
score improves measurably, and the realised score does not move at all.

**Mechanism.** The new candidates are only reachable by a selector that does not
exist. Recombining parts of candidates is the classic case: the pool now contains
better answers, but the selector operates on whole candidates by a confidence
signal that recombined candidates do not carry, so it can never return them. The
oracle improved and your access to the oracle did not.

**Who suffers.** Genetic and crossover-based generation, fragment recombination,
hybrid or patched outputs, any pipeline that widens the pool by combination rather
than by sampling. In the case study a genetic anchor-and-tail crossover raised the
oracle while no selector could find the hybrid, and it is described there as a
pure selection-wall casualty.

**Mitigations.**
1. **Always report the oracle and the realised score together.** An oracle-only
   improvement is not an improvement, and this failure mode is invisible if you
   report the ceiling alone.
2. **Design the selector and the generator together.** If a generation trick
   produces candidates carrying no usable confidence signal, either give them one
   or do not generate them.
3. **Prefer widening the pool by sampling the existing generators more**, since
   those candidates arrive with a native confidence attached.

**Residual risk.** The recombined candidates may genuinely be the best available
answers, so this mode represents a real ceiling you are choosing not to reach.
Record it as an open question rather than a closed one.

## B5. Over-application of a corrective

**Symptom.** An intervention helps at a small dose and hurts at a large one. The
dose-response curve has an interior optimum, and the naive assumption that more is
better puts you past it.

**Mechanism.** The intervention has a benefit concentrated on a small
subpopulation and a cost spread across everything else. Applied narrowly, the
benefit dominates; applied broadly, the cost does. The subpopulation is real but
small, and the boundary is not sharp, so extending the intervention past it
replaces good answers with worse ones.

**Who suffers.** Any tail-targeted correction: rescue swaps, fallback models,
outlier re-prediction, aggressive filters, confidence-thresholded overrides. In the
case study the number of lowest-confidence items overwritten with a different
model's pose swept as follows.

| Items swapped | 4 | **8** | 12 | 20 |
|---|---|---|---|---|
| Score | 0.5578 | **0.5640** | 0.5629 | 0.5587 |

The optimum is interior, the curve is flat near it, and the 20-swap value of
0.5587 is worse than the 4-swap value. "Rescue the tail" is correct; "rescue
generously" is not.

**Mitigations.**
1. **Sweep the dose, always. Never assume monotonicity.**
2. **Choose the dose on the flat part of the curve rather than at the argmax**, since
   the argmax over a noisy sweep is partly noise. Between 8 and 12 the difference is
   0.0011, which is far smaller than the differences that separate approaches.
3. **Prefer selecting the intervention set by a criterion rather than by a count**,
   when a criterion is available, because a count does not transfer to a new test
   set and a threshold sometimes does.

**Residual risk.** The dose was tuned without ground truth on the real metric, and
that tuning consumed submissions. It is a hyperparameter fitted to the leaderboard,
which means it is fitted to a sample.

## B6. Local refinement cannot repair a global error

**Symptom.** A refinement step improves every local quality measure — geometry,
strain, clash count, internal consistency — and does not improve the score.
Sometimes the local measures improve while the score degrades.

**Mechanism.** Refinement searches a local neighbourhood. If the candidate is in
the wrong basin, the nearest local optimum is a better-formed version of the wrong
answer. In the case study, local molecular-dynamics refinement with OpenMM could
not recover a 2 Å translation, and a 2 Å translation is exactly the scale of error
that decides the metric.

**Who suffers.** Energy minimisation, restrained molecular dynamics, local
docking, iterative local search, and any "polish the answer" step. The analogous
mode in property prediction is calibration: recalibrating a model whose ranking is
wrong produces well-calibrated wrong predictions.

**Mitigations.**
1. **Ask what the error scale is before choosing a refinement radius.** If typical
   errors exceed the search radius, refinement is the wrong tool and the right one
   is regeneration or replacement.
2. **Fix placement before polishing geometry**, and treat the two as separate
   pipeline steps with separate evaluation.
3. **Gate refinement on ground truth per item and adopt it only where it helps.**
   See C6.

**Residual risk.** Refinement can still be worth running for the subset already in
the right basin, and separating that subset requires the confidence signal that
B1 says you do not have.

## B7. Generative and agentic hallucination

**Symptom.** A generative or agent-driven step returns an output that is
confidently formatted, internally coherent, and catastrophically wrong — much
worse than the input it was asked to improve.

**Mechanism.** A generative model asked to produce a plausible object optimises
plausibility under its own distribution, which is not the same as validity under
the domain's constraints, and the failure has no natural upper bound. Unlike a
numerical method, there is nothing in the mechanism that limits how wrong the
output can be. In the case study, agentic ligand re-drawing took one item from
3.88 Å to **24.63 Å**, and the write-up flags it as a hard lesson for anyone
building an AI scientist — which is to say, for this project.

**Who suffers.** Any agent-in-the-loop editing step, any generative repair or
in-painting step, any language-model-mediated transformation of a structured
artifact. Applies squarely to this repository's own design.

**Mitigations.**
1. **Never let a generative step write the final artifact unchecked.** Validate the
   output against hard constraints and reject rather than accept-with-warning.
2. **Bound the edit.** Constrain the output to a small distance from the input and
   reject anything outside the bound, which converts an unbounded failure into a
   no-op.
3. **Compare against the unedited input on ground truth** and adopt the edit only
   where it wins.
4. **Prefer selection over generation for agents.** An agent choosing among valid
   candidates cannot produce a 24 Å error; an agent producing candidates can.

**Residual risk.** A bounded edit can still be wrong within its bound, and the
validator only catches violations you thought to encode.

---

# C. Validation, metric, and confidence failures

## C1. Overfitting to a small validation set

**Symptom.** A method leads on local validation and does not lead on the real
metric. The sharpest diagnostic: **when the task gets easier, the method fails to
improve while everything else does.**

**Mechanism.** Selection pressure applied through a small validation set fits the
set rather than the task, and the fitting happens through your development
decisions even when no parameters are trained. Each comparison you made on those
items spent some of their information. A method that has absorbed the validation
set's idiosyncrasies has nothing left to gain when the items become easier,
because its apparent performance was coming from the idiosyncrasies rather than
from the signal.

**Who suffers.** Every choice made by local validation, including choices that
feel like engineering rather than modelling: thresholds, which model to trust,
which post-processing to enable.

**Mitigations.**
1. **Expand the validation set and re-rank.** This is the diagnostic, and it is
   cheap. When the case study grew its validation set from 35 to 53 holo
   structures, every method gained about +0.020 on the local proxy **except**
   pLDDT-based selection, which gained +0.0015 and fell from first place to last.
   Same methods, same poses, easier set, inverted ranking.
2. **Build the expanded validation set early.** The case study's authors list this
   as one of four things they would do differently.
3. **Count the comparisons you have made against a validation set** and treat the
   set as spent once that count is large relative to its size.
4. **Prefer methods with fewer decisions fitted to the validation set**, all else
   equal. The winning selector had roughly one.

**Residual risk.** The expanded set is still small and still yours. Expansion
detects overfitting to the *old* set; it does not prevent overfitting to the new
one, and you will now start fitting to the new one.

## C2. Validation noise floor and non-monotonicity with the real metric

**Symptom.** All your candidate methods score within a hair of each other locally,
so you cannot rank them — and yet the real metric separates them clearly. Or the
ordering is simply different.

**Mechanism.** A small validation set has a noise floor set by its size and
composition, and differences smaller than that floor are unmeasurable there. When
the real metric has more resolving power, local validation is not a weak version
of it but an uninformative one, and reading a ranking off differences below the
noise floor is reading noise. In the case study, all methods clustered within
0.05 Å on the 35-structure set — explicitly identified as that set's noise floor —
while the leaderboard spanned a range five times wider. The conclusion recorded
there is blunt: trust the real metric over a tiny local ground truth.

**Who suffers.** Any project with scarce ground truth, which includes essentially
every prospective challenge and every early-stage internal project.

**Mitigations.**
1. **Estimate the noise floor before using the set to decide anything.** Bootstrap
   the validation metric and look at the spread. If your candidate differences are
   inside it, the set cannot answer your question and you must stop using it as if
   it can.
2. **Use local validation as a falsification gate, not a ranking device.** It is
   excellent at "this is broken" and useless at "this is 0.003 better". The case
   study's local ground-truth gate killed 8 approaches before any of them consumed
   a submission slot, which is the correct use.
3. **Add an independent corroborating signal rather than a finer local one.** The
   case study required at least 3 of 4 confidence signals to support a candidate
   alongside a local RMSD threshold of 2.15 Å.

**Residual risk.** Deferring to the real metric costs submissions, and submissions
are usually the scarcest resource. That tension is what the pre-flight gate in D3
is designed to manage.

## C3. Decoupled proxy metric

**Symptom.** You rank or gate by a convenient secondary metric, and it does not
move with the score you are graded on. Improvements in the proxy do not appear in
the result.

**Mechanism.** The proxy measures a different quantity that happens to be
correlated in the population where someone first checked, and not in yours. Two
metrics computed on the same objects are not thereby measuring the same thing. The
case study measured this directly across 18 submissions: LDDT-LP, a protein-only
variant, had Spearman correlation of about **+0.01** with the graded LDDT-PLI,
which is to say none at all, and the recorded instruction is to never rank by it.
The same exercise found BiSyRMSD tracking the graded metric at about **+0.94**,
making it a safe corroborating column.

**Who suffers.** Every pipeline that gates on something cheaper than the real
metric, which is every pipeline, because the real metric usually requires the
answer.

**Mitigations.**
1. **Measure the rank correlation between every proxy and the real metric, on your
   own submissions, as soon as you have three or four.** This is a small
   computation that changes what you optimise.
2. **Record known caveats where the next stage will read them.**
   `Metric.known_caveats` and `Metric.proxy_metrics` in
   `src/reagent/contracts/problem.py` exist for exactly this, and the field
   documentation names a decoupled secondary metric as the motivating example.
3. **Keep a corroborating proxy with measured high correlation, and use it as a
   second opinion rather than as a substitute.**

**Residual risk.** The correlation is measured on the submissions you happened to
make, which are not a random sample of pipelines, and a proxy can be well
correlated overall while decoupling on the subpopulation that matters.

## C4. Metric structure and metric gaming

**Symptom.** A competitor's score is not explained by the quality of their
predictions. Or your own score responds to changes that cannot plausibly have
improved the science.

**Mechanism.** Every metric is a specific computation with specific behaviour at
its edges, and that behaviour is exploitable. Common structures worth checking
deliberately: how missing or unparseable outputs are scored, whether the metric
saturates, whether it averages per item or per group, how ties are broken, whether
the aggregate is a mean or a median or a bootstrap, and whether the metric rewards
a safe answer everywhere over a mix of excellent and terrible answers. A metric
averaging per item over a heterogeneous test set rewards the majority
subpopulation, so effort allocation follows the composition rather than the
science. In the case study the graded metric was bootstrap-averaged over 1000
resamples with half the items live and half held out, and the drug-like half — 108
of 184 items, or about 87 items by the stated drug-like definition of molecular
weight at least 330 or at least 5 rotatable bonds or at least 24 heavy atoms — was
where the points were.

The skill's guidance is not to refuse this analysis but to do it deliberately:
metrics have exploitable structure, so scout how the metric has been gamed and
then decide consciously how far to go.

**Who suffers.** Everyone, and the honest participants most, since they are the
ones not checking.

**Mitigations.**
1. **Reimplement the metric locally from its definition.** `Metric.definition` is
   required to be precise enough to reimplement, for this reason.
2. **Compute the metric's sensitivity to each subpopulation** and allocate effort
   by expected metric gain rather than by scientific interest.
3. **Check the degenerate cases explicitly**: what does the metric give for an
   empty output, a duplicated output, a maximally safe output?
4. **Decide the line and write it into the report.** An exploit that improves the
   score without improving the prediction is a finding either way; whether you use
   it is a judgement that belongs in the decision ledger, not in a commit message.

**Residual risk.** Organisers change metrics and validators between rounds, and a
pipeline tuned to metric structure is tuned to a moving target.

## C5. Confidence miscalibration

**Symptom.** High-confidence predictions are wrong about as often as
low-confidence ones, so confidence cannot be used for triage. Or confidence is
usefully calibrated on most items and inverted on a subset.

**Mechanism.** A confidence head is trained to predict its own model's error
distribution on its own training distribution. Off that distribution it reports
high confidence for the wrong reason, and the error is not random: it is
systematically high where the model is systematically wrong, because both come
from the same misplaced inductive bias. This interacts with A1 directly, since the
subpopulation where the prior inverts is also where confidence lies.

**Who suffers.** Predicted-error heads, predicted-alignment-error and interface
scores, model-reported uncertainties, conformal wrappers fitted on the wrong
population, and every triage or abstention rule built on them.

**Mitigations.**
1. **Plot realised accuracy against reported confidence on your validation set, per
   subpopulation.** A single aggregate calibration curve hides an inversion on a
   minority population.
2. **Use confidence for the task it is adequate for.** In the case study, native
   confidence was not good enough to rank reliably — the literature review
   concluded it largely does not beat random on co-folding pools — but it was good
   enough to *identify a tail*, and identifying the tail was worth 0.0168 through
   the rescue mechanism. Calibration adequate for detection is a lower bar than
   calibration adequate for ranking, and asking only for what you need is often the
   difference between a usable signal and an unusable one.
3. **Normalise across models before comparing confidences.** See B3.
4. **Do not recalibrate on tens of items.** See A3.

**Residual risk.** A confidence signal good enough for detection still mis-orders
within the tail, so which items get rescued is partly arbitrary, and the tail
boundary is a tuned hyperparameter with the properties described in B5.

## C6. High-variance intervention judged on its mean

**Symptom.** An intervention's average effect is roughly neutral, and its
per-item effects are enormous in both directions. Whether you adopt it looks like
a coin flip depending on which validation subset you happened to look at.

**Mechanism.** The intervention is correct in some regime and destructive in
another, and the mean over a mixed set averages those into something
uninformative. Judging by the mean discards the actionable structure, which is
that the intervention is a good idea *conditionally*.

**Who suffers.** Physics-based gating, strain and energy filters, aggressive
post-processing, any rule that overrides a prediction. In the case study, MMFF
strain gating scored 2.251 Å for the `blend_top3` variant against 2.230 Å for the
plain interface-error baseline, which is 0.020 *worse* — and the write-up records
the distribution behind that mean: large wins on 4 holo structures and
catastrophic losses on 3. The mean says "neutral to slightly bad"; the distribution
says "there is a real effect here and you cannot tell which side you are on".

**Mitigations.**
1. **Always look at the per-item distribution of an intervention's effect, not just
   its mean.** This costs one plot and changes decisions.
2. **Look for a covariate that separates the wins from the losses.** If one exists,
   the intervention becomes a conditional rule and its expected value goes
   positive. If none exists after honest searching, the variance is the finding.
3. **Pre-commit the rejection rule and its consequences.** The case study
   committed in advance that if MMFF strain gating failed validation, a dependent
   DFT-torsion-prior project would be cancelled unbuilt. It failed, the dependent
   project was cancelled, and 14 development hours were saved without a fresh
   argument. This is why `Proposal.kill_criterion` is a required field in this
   project's contract.

**Residual risk.** With a small validation set, the search for a separating
covariate is itself an overfitting opportunity, and a covariate found on 7 items
means nothing.

---

# D. Mechanical and operational failures

These are not modelling failures, and they have decided real leaderboards. They
belong in the report as `FindingKind.CONSTRAINT`, and the skill's anti-pattern
list names ignoring them explicitly.

## D1. Format and connectivity failures that score zero

**Symptom.** A submission scores far below its local evaluation, or an individual
item scores zero, and the predictions themselves are fine.

**Mechanism.** The scoring server rejected or misparsed the output. In the
reference case study the requirements were exact and unforgiving: submit a zip of
184 PDB files, the ligand residue name must be exactly `LIG`, and the
RDKit-parsed ligand graph must match the expected SMILES. A connectivity failure
scored that compound **0** and added a 20 Å RMSD penalty. Bond inference from 3D
geometry is the specific trap, because a server that infers connectivity
geometrically will get it wrong on a pose that is slightly distorted — so the pose
being imperfect causes the parse to fail, which converts a small geometric error
into a total loss.

**Who suffers.** Every submission-based pipeline. The cost is unbounded relative to
any modelling improvement: a single zeroed item on a 184-item average costs more
than most method changes gain.

**Mitigations.**
1. **Validate every artifact mechanically before submitting, and require zero
   errors rather than few.** The case study ran format and SMILES-graph validation
   on every submission and required zero errors.
2. **Remove the server's need to infer.** They injected CONECT records into all 184
   PDB files so the server would read bonds from explicit topology rather than from
   3D geometry. This converts a geometry-dependent parse into a deterministic one
   and is the single highest-return line of code in the whole pipeline.
3. **Round-trip your own output through the same parser the server uses**, and
   compare the parsed object against the specification rather than against your
   intent.
4. **Keep a substitution path for items the server has confirmed it cannot score.**
   The case study swapped 3 server-confirmed scoring-fail ligands.

**Residual risk.** The server's parser is not your parser, and the specification is
not the implementation. Only a real submission proves scoreability, which makes
this a reason to spend an early submission slot on a validation submission.

## D2. Leaderboard mechanics

**Symptom.** Your standing gets worse after a submission that was not worse, or
you discover that the number displayed is not the number you thought.

**Mechanism.** Leaderboards implement a specific policy about which of your
submissions counts, and the policy is frequently "the most recent" rather than
"the best". Under that policy an exploratory submission overwrites a good result,
and the loss is permanent. In the case study the leaderboard displayed the most
recent submission rather than the best, and **three competitor teams destroyed
their own standings this way**, the worst falling from 0.5521 to 0.4727 and from
rank 2 to rank 18. That is a larger swing than any method change in the entire
project, achieved by a submission.

**Who suffers.** Everyone who did not read the rules with this specific question
in mind. It is pure downside: there is no scientific benefit to being surprised by
it.

**Mitigations.**
1. **Determine the display and tie-breaking policy explicitly, before the first
   submission, and write it into `ProblemSpec.output_contract`.**
2. **If the policy is most-recent, build a submission ladder with a deadline guard**
   so the final state is your best result rather than your latest experiment. The
   case study built exactly that, plus two redundant operating-system-level restore
   tasks specifically against this failure.
3. **Never spend the last available slot on an experiment.** Reserve it to restore
   the incumbent.

**Residual risk.** Automated restores can themselves fail, which is why the case
study used two redundant ones. And a deadline in a different timezone than you
assumed removes the guard entirely.

## D3. Submission budget exhausted on untested candidates

**Symptom.** The submission budget runs out before the promising ideas have been
tested, and in retrospect most spent slots were on candidates you could have
rejected locally.

**Mechanism.** Submissions are a rationed resource — one per four hours in the case
study — and without an admission test every idea consumes one. Local validation
cannot rank finely enough to substitute (C2), so the temptation is to submit and
find out, which spends the scarcest resource on the least informative question.

**Who suffers.** Every rate-limited or attempt-limited evaluation, which includes
challenges, wet-lab validation cycles, and anything requiring human review.

**Mitigations.** The case study's three-gate pre-registered admission test is the
transferable machinery here, and nothing reached the server without passing all
three.

1. **Connectivity and format**: zero validator errors. See D1.
2. **Divergence band against the incumbent, between 5 and 30 percent.** Below 5
   percent the candidate is sub-noise and wastes a slot; above 30 percent is the
   empirically identified "anchor-disaster band", where every candidate they
   measured — at 94.6, 99.5, 95.7, 88.6 and 86.4 percent divergence — scored below
   0.47. This gate alone rejected 13 candidates and is described as the novel,
   highest-yield one. The general principle transfers even where the specific
   percentages do not: **a candidate that differs enormously from a good incumbent
   is far more likely to be broken than brilliant**, and that asymmetry is
   measurable on your own submission history.
3. **Local ground-truth agreement**: RMSD at or below 2.15 Å on the 53-holo
   validation set, with at least 3 of 4 confidence signals supporting.

The outcome is worth stating plainly because it looks like failure and is not: **0
of 12 candidates passed all three gates in iterations 3 through 6.** That is the
gate working. The retrospective cost of not having it: 11 wasted submission slots,
8 of which the divergence gate alone would have caught, and the authors' first
listed regret is codifying the gate by iteration 2 rather than iteration 3.

Alongside the gate, run a falsification harness with pre-committed transitive
rejection: the case study's local ground-truth gate killed 8 approaches before any
consumed a slot, and rejection consequences were committed in advance so that a
failed prerequisite cancelled its dependent project without a new argument.

**Residual risk.** A gate calibrated on your own history can reject the one
genuinely novel candidate, and the divergence band in particular is a
correlational rule with no causal guarantee. Record the rejections so the gate can
be audited later, which is also what makes it improvable.

## D4. Infrastructure activation lag

**Symptom.** Substantial time spent on compute infrastructure, external resources,
or access requests, with no output that reached the pipeline.

**Mechanism.** Getting an external resource productive has a lead time that is
independent of how much effort you put in, and if that lead time exceeds the
project window the effort has zero expected value regardless of the resource's
quality. In the case study, 80 hours went into external notebook attempts and **0
of 8 reached a submittable output**, against an activation lag estimated at about
12 weeks and a project window of 30 days.

**Who suffers.** Any time-boxed project reaching for new compute, new data access,
new collaborations, or new tooling. It is the operational analogue of choosing a
method you cannot cost.

**Mitigations.**
1. **Estimate activation lag before capability.** A resource that cannot activate
   inside the window is not a candidate, however good it is. This is the same
   discipline as `MethodCard.verdict` requiring a cost.
2. **Timebox the attempt and pre-commit to abandoning it**, with the kill criterion
   written down before starting.
3. **Prefer the resource already working.** For this project's environment that
   means the already-configured cluster access over a hosted notebook that must be
   provisioned, and it means preferring the free-tier path in Stage 0.

**Residual risk.** Sometimes the unavailable resource is the only route to the
result, and the correct response is to change the plan rather than to keep trying
the door. That decision belongs in the ledger.

## D5. Effort misallocated away from the test set

**Symptom.** A long list of methods explored, and nobody can state the composition
of the test set, its subpopulations, or which subpopulation carries the points.

**Mechanism.** Method exploration is legible, generates visible activity, and feels
like progress. Characterising the test set is neither, and it is where the leverage
is, because every decision downstream is conditioned on it. The case study's
fourth and strongest recorded regret is to have spent too little ideation on the
test-set distribution, stated as a target of **70 percent** of ideation on the
distribution rather than on methods.

The connection to everything above is direct: A1, A2, C1, C2 and C4 are all
failures that test-set characterisation prevents or detects, and they occupy five
of the top seven rows of the cost table.

**Who suffers.** Every project, and this stage most, since Stage 0 is where the
allocation is set.

**Mitigations.**
1. **Write the subpopulation breakdown before the method landscape.** Sizes,
   defining criteria, and the expected metric contribution of each.
2. **Compute the per-subpopulation metric sensitivity** so you know where a point
   of improvement is worth most.
3. **Make it a deliverable rather than a preliminary**, in
   `ProblemSpec.test_items.subpopulations`, whose field documentation says
   directly that Stage 0 should characterise subpopulations because a prior that
   helps one can hurt another.
4. **End the scouting pass on a branch decision, not a survey.** Twenty methods
   with no branch structure is a reading list, and the useful artifact answers the
   question "given what our test set actually contains, which branch am I on?"

**Residual risk.** The characterisation is only as good as what the organisers
disclosed, and some structure only becomes visible after the first results come
back. Plan to revise it.

---

## Recording these in the report and the graph

Every entry you instantiate for your own problem becomes report content, and the
mapping is fixed so that Stage 3 can consume it without interpretation.

- An observed failure of a method becomes a `Finding` of kind
  `NEGATIVE`, with `Evidence` for where you observed it, plus a
  `Predicate.FAILS_ON` edge from the `Method` node.
- A failure you have not observed but expect becomes `FindingKind.RISK`. Risks may
  be asserted by the agent without citation; negative results may not, and the
  validator enforces the difference.
- A mechanical requirement from the D group becomes `FindingKind.CONSTRAINT` and
  belongs in `ProblemSpec.output_contract` as well, because Stage 4 will read it
  there.
- The catalogue table sorted by metric cost goes in `handoff.payload.failure_modes`.
  This is the deliverable Stage 3 designs against and, per the skill, the one
  teammates actually reread.

Two notes on confidence. A failure mode observed once, by you, on your own data is
`supported` and not `established`, however vivid it was. And most of the entries
above are supported by a single competition post-mortem, which
`src/reagent/contracts/report.py` classifies as grey — real evidence, frequently
the only public record of a negative result, and insufficient alone for
`established`. Cite the case study honestly at `supported` rather than promoting
it, and upgrade only when a second independent grounded source appears.
