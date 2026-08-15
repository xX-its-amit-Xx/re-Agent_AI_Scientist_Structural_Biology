# Audience registers: the same finding, written four ways

A register is not a difficulty level. When a structural biologist, a medicinal chemist
and a modeller read the same finding, they are each looking for a different verb: one
wants to know what to measure next, one wants to know what to make next, one wants to
know what to train on next. Writing one "expert" sentence and shortening it for the
`LAYPERSON` register produces four copies of the least useful of the four.

This file is worked examples. Six findings from different corners of the project, each
written out in all four required registers, then a judgement table on analogies, then
the three moves that make a plain register work, then a self-check.

## What is actually enforced, and what is only good practice

Worth knowing before you write, because the guard rails in the SKILL are stricter than
the code in some places and the code is stricter in others.

Enforced when an `Interpretation` is constructed:

- `for_audience` must contain `Audience.LAYPERSON`, and that entry must be at least 40
  characters. A missing or stub plain register raises immediately.
- Every `Implication` needs `for_stage`, `decision` (at least 10 characters),
  `direction` (at least 15), and `if_wrong` (at least 15). `if_wrong` is a required
  field, not a convention — you cannot construct an implication without it.
- `direction` is run through a keyword check for words that take a side: `for `,
  `against`, `toward`, `away`, `increase`, `decrease`, `prefer`, `avoid`, `include`,
  `exclude`, `raise`, `lower`, `support`, `argue`. Be honest about what this catches: it
  is a substring test, so "Relevant for template selection" passes it while changing
  nothing. Passing the check is not the same as taking a side.
- `GlossaryTerm.plain` and `GlossaryTerm.why_it_matters` must each be at least 20
  characters.

Enforced only when the report-level validator runs, via
`Interpretation.check_plain_language()`:

- Undefined jargon in the plain register. The method *returns* problems rather than
  raising them, so that the run-wide `Glossary` can be attached before judging. An
  `Interpretation` built in isolation will happily hold a plain register full of jargon;
  the failure surfaces at `reagent report validate --strict`.
- Mean sentence length above 32 words in the plain register. The error message tells you
  to aim under 25, which is the number to actually write to.

Not enforced anywhere, so it is on you:

- Jargon inside a `GlossaryTerm.plain` definition. Nothing checks that you defined a
  term without using three more.
- Jargon in the expert registers. That is deliberate — they are allowed it — but the
  renderer makes glossary terms hoverable inside them too, which is exactly where a
  non-specialist reading across most needs the help.
- Whether `for_stage` names a real stage. It is a free string, so a typo produces an
  implication addressed to nobody.

Two mechanics of the jargon checker are worth exploiting rather than fighting. Defined
terms are blanked out longest-first before matching, so a glossary entry for
"ligand-binding domain" also satisfies the bare "domain" inside it. And `aliases` count
as definitions, which is how the demo glossary makes "fold", "shared fold" and "same
fold" all legal in one entry. Ten ordinary English words — including *fold*, *domain*,
*residue*, *template*, *seed*, *ensemble*, *buried* and *affinity* — are only flagged in
technical collocations, so "the way the protein folds" passes and "a shared fold" does
not.

---

## Example 1 — a protein similarity claim

**Finding.** The target's nearest neighbour by pocket-lining similarity is a liver
drug-metabolising enzyme from an unrelated protein family. Its nearest neighbour by
sequence identity is a family member whose pocket is substantially smaller.

**`LAYPERSON`**
> Proteins can be related in more than one way. The protein we must predict for has a
> close relative on paper, with a similar chemical sequence, but that relative has a
> much tighter cavity, so the two do not accept the same molecules. The protein whose
> cavity is genuinely most alike is a liver enzyme from an unrelated family. If we want
> a known structure to borrow a starting shape from, the liver enzyme is the better
> guide, even though a family tree would never have suggested it.

**`MEDICINAL_CHEMIST`**
> The selectivity risk sits outside the receptor family. An off-target panel chosen by
> sequence homology will test the wrong proteins; the compounds most likely to
> cross-react are the ones that fit a large, adaptable pocket, which is what the
> non-family neighbour has and what the close paralog does not.

**`STRUCTURAL_BIOLOGIST`**
> Pocket-lining similarity and fold similarity dissociate here. That argues for ranking
> template candidates on pocket descriptors rather than on sequence identity or
> TM-score, and for treating the paralog's smaller pocket as a different conformational
> problem rather than a closer one.

**`ML_PRACTITIONER`**
> A corpus assembled by family membership is not the corpus that shares the difficulty.
> Weight by measured pocket breadth as well as by taxonomy, and note that a
> family-based validation split will hold out the cases you care least about.

**`CLINICIAN`** (optional, but there is something real to say here)
> The protein our target most resembles in the pocket is a liver drug-metabolising
> enzyme, so a compound designed against the target carries a raised prior probability
> of also inhibiting or inducing that enzyme. That is a drug-drug interaction question
> rather than a selectivity question, and it is cheap to ask early.

**What makes each register different.** The plain register has to establish that
"related" is ambiguous before the finding means anything; that framing is the whole
explanation and the expert registers get it for free. The chemist's register converts the
fact into an experiment to run — a different off-target panel. The structural
biologist's converts it into a ranking criterion. The modeller's converts it into corpus
weighting and a warning about split design. None of these is a simplification of
another; they name four different actions.

---

## Example 2 — a compound scaffold claim

**Finding.** Most of the drug-like half of the test set shares a single Murcko scaffold
with varied substitution; the remainder spreads thinly over many scaffolds with no more
than a few members each.

**`LAYPERSON`**
> Most of the larger molecules we must predict for are built on the same central
> framework, with different decorations attached around it. The rest are all different
> from one another. That matters because anything we learn from one member of the big
> group probably carries over to the others, so getting that group right is worth far
> more than getting any single molecule right. The thinly spread remainder has to be
> handled one at a time, and it is where a mistake will go unnoticed.

**`MEDICINAL_CHEMIST`**
> One congeneric series dominates the drug-like half, so structure-activity trends
> within it should transfer and a single binding hypothesis covers most of the set. The
> singletons are where a wrong hypothesis is caught by nothing else; review those by eye
> rather than by analogy to the majority.

**`STRUCTURAL_BIOLOGIST`**
> A dominant scaffold means the pocket is being probed repeatedly by one geometry, so
> the interaction map derived from these complexes is densely sampled but narrow. Expect
> the singletons to engage a different subset of pocket residues, and do not assume the
> recurring anchor set generalises to them.

**`ML_PRACTITIONER`**
> A random split leaks: the dominant scaffold appears on both sides and the validation
> score reads as generalisation when it is memorisation. Split by scaffold, and report
> the singleton subpopulation separately, because that is where the variance lives and
> where an average will hide a regression.

**What makes each register different.** The plain register has to supply the *weighting*
— that the big group is worth more than the singletons — because a non-specialist has no
way to judge that from the counts. The chemist hears a transferability claim. The
structural biologist hears a sampling-bias warning about their own interaction map. The
modeller hears a split-design instruction. Same census, four consequences.

---

## Example 3 — a negative result

**Finding.** Selecting the candidate that several generators agree on did not beat
selecting by a single generator's own confidence, and was slightly worse.

**`LAYPERSON`**
> We tried picking the answer that several different prediction programs agreed on,
> expecting agreement to be a sign of being right. It was not. The programs make the
> same kinds of mistake as each other, so when they agree they are often agreeing on a
> mistake, and the agreement adds no information. Letting each program judge its own
> work, in its own units, worked better. This is a result and not a failed attempt: it
> tells us where not to spend the next month.

**`MEDICINAL_CHEMIST`**
> The pose several models agree on is not the pose most likely to be right, so do not
> use agreement as a plausibility filter when triaging geometry. Judge each pose against
> the pocket chemistry directly, and treat cross-model agreement as a fact about the
> models rather than about the molecule.

**`STRUCTURAL_BIOLOGIST`**
> This is correlated error, not independent measurement. Agreement between two models
> trained on overlapping structural data carries far less information than agreement
> between two independent experiments, and reading it as a consensus of observations is
> a category error.

**`ML_PRACTITIONER`**
> Errors across generators are correlated, so consensus adds no independent signal and
> can be actively harmful. Keep the pool wide for coverage, select within model on that
> model's native signal, then z-score across models — and require any learned selector
> to beat that baseline on held-out data before it is adopted.

**What makes each register different.** The plain register has to defend the *status* of
a negative result, because the natural lay reading of "it did not work" is "we failed".
The chemist gets a heuristic withdrawn from their bench practice. The structural
biologist gets the epistemics named. The modeller gets a baseline and an adoption gate.
Note that only the plain register spends a sentence on the mechanism — that shared
training data implies shared mistakes — because the experts already have it.

---

## Example 4 — a metric caveat

**Finding.** One of the secondary metrics the scoring harness reports is statistically
decoupled from the metric the challenge is graded on; a third metric tracks the graded
one closely.

**`LAYPERSON`**
> The tool we use to check our work reports several different scores. Only one of them is
> the score we are graded on. Another moves almost independently of it, so improving that
> one tells us nothing, and chasing it would send us in the wrong direction for weeks. A
> third moves in step with the graded score and is safe to watch when the graded one is
> slow to compute. Knowing which is which is the difference between real progress and a
> month of pleasant numbers.

**`MEDICINAL_CHEMIST`**
> If someone tells you a pose improved after an edit, ask which number they read. The
> protein-only quality number can rise while the protein-ligand contact quality — the
> graded one, and the one that reflects whether the molecule is in the right place —
> falls.

**`STRUCTURAL_BIOLOGIST`**
> The decoupled metric scores the receptor and the tracking one scores the ligand in
> place, which is why they behave differently. Any accuracy check here must be
> symmetry-corrected and in-place, and must not superpose the candidate onto the
> reference as a side effect, or a correctly shaped molecule in entirely the wrong site
> scores as a success.

**`ML_PRACTITIONER`**
> Measure the correlation between every proxy and the target metric on your own data
> before using the proxy for model selection or early stopping. Keep the decoupled
> metric in the harness as a deliberate negative control: if it starts tracking, the
> harness is wrong, not the method.

**What makes each register different.** The plain register is the only one that has to
explain why a laboratory would have more than one score at all, and it carries the cost
in time rather than in statistics. The chemist gets a question to ask in a meeting. The
structural biologist gets the physical reason the metrics diverge, which is what lets
them predict the next such case. The modeller gets an instrumentation rule.

---

## Example 5 — a data-availability gap

**Finding.** The largest matched dataset for the assay endpoint exists, but is published
only as aggregated summary values behind a registration wall; per-compound values are
not distributed.

**`LAYPERSON`**
> The biggest useful collection of measurements for this question does exist, but only as
> averages, and only to people who register for access. Averages cannot be used the way
> we need to use them, because we need each compound's own value to learn from and to
> check against. So the data is visible but not usable, which is a different situation
> from the data not existing. Someone should ask the depositors for the underlying
> values. Until then we should say plainly that this gap is about access, not about
> science.

**`MEDICINAL_CHEMIST`**
> You cannot reconstruct a structure-activity table from group means, so any trend quoted
> from this source is a trend between series averages rather than between compounds.
> Hypothesis-generating only; do not design against it.

**`STRUCTURAL_BIOLOGIST`**
> There is no way to pair a summary value with a specific structure, so this source
> cannot contribute to any structure-activity or pocket-occupancy analysis. For our
> purposes it is bibliographic rather than experimental.

**`ML_PRACTITIONER`**
> Record it as a `DataRef` with a `fetch_hint` naming the registration wall, and do not
> let the availability matrix render it as present. An imputed per-compound value derived
> from a group mean leaks group identity into the features and will inflate any
> within-group validation score.

**What makes each register different.** The plain register's whole job is to hold apart
two things that look identical from outside — an absent dataset and an inaccessible one —
which is the same distinction the negative-result contract makes about unrun checks. The
chemist gets a permission level for the data. The structural biologist gets it
reclassified out of their evidence base. The modeller gets a concrete leakage mechanism
and a contract field to fill in.

---

## Example 6 — a modelling design choice

**Finding.** Selection is treated as a separate, revisable stage from generation, and no
candidate is discarded at the moment it is produced.

**`LAYPERSON`**
> We keep every answer each program produces, even the ones we are fairly sure are
> wrong, and we choose between them in a later, separate step. Storage is cheap and
> judgement is not. When we later find a better way to choose, we can redo the choosing
> over everything we already made, instead of making it all again. Throwing an answer
> away at the moment it is produced quietly makes that improvement impossible, and
> nothing later would tell us we had lost it.

**`MEDICINAL_CHEMIST`**
> If you reject a pose on chemical grounds, log the rejection rather than deleting the
> pose. A pose that looks strained under one protonation assumption may be the right one
> under another, and the review is far cheaper to redo than the generation.

**`STRUCTURAL_BIOLOGIST`**
> Keeping the whole pool preserves whatever alternative conformers the generators
> happened to produce, which is often the only record of receptor plasticity these
> models give you. A pruned pool cannot be re-examined when the dynamics analysis says a
> second state matters.

**`ML_PRACTITIONER`**
> Generation and selection have different cost curves and different iteration speeds.
> Persisting the full pool with per-candidate provenance makes selection an offline
> experiment you can re-run in minutes, which is what lets you sweep the rescue count
> rather than guess it.

**What makes each register different.** A design choice has no natural plain-language
form, so the plain register has to invent one: it explains the choice as a bet about
future improvement, and names the failure mode as silent. The chemist's version applies
the same principle to their own reviewing habit. The structural biologist's identifies
what specifically would be lost. The modeller's names the capability that the choice
buys. Notice that all four are about the *reason*, not the mechanism — a design finding
is interpreted by justifying it.

---

## Analogies that work and analogies that fail

An analogy survives if the **mechanism** transfers. It fails if only the **image**
transfers, however apt the picture. The practical test has three steps: state in one
sentence which mechanism you intend to carry across; ask what a reader would predict
about a genuinely new case using only the analogy; if that prediction is wrong, the
analogy is wrong. Then state the boundary — the point at which it stops holding — because
almost every surviving analogy has one, and naming it is what stops a reader
over-extending it.

| Analogy | Verdict, and exactly why |
|---|---|
| A binding pocket is a lock, and the molecule is the key. | **Survives.** The transferable mechanism is real: complementary geometry admits one shape and excludes others, so shape genuinely decides what fits. Boundary: locks do not reshape themselves. The moment you need induced fit or a plastic pocket, the analogy is not merely incomplete but actively misleading, so say which of the two you are using it for. |
| Protein folding is like origami. | **Fails.** The image is right and the mechanism is entirely wrong. Origami is an externally imposed sequence of deliberate creases toward a chosen shape; folding is a spontaneous search over an energy landscape with no folder, no plan, and no target drawing. A reader given this analogy will believe there is a folder, and will be unable to predict misfolding, chaperones, or why the same chain sometimes settles somewhere else. |
| A pocket that must accept many unrelated molecules is like a cargo hold that must carry objects of unknown shape. | **Survives, and does real work.** The mechanism transfers exactly: a container required to accept unknown contents is selected for adjustable volume rather than precise shape. That is why unrelated proteins with the same job converge on similar pocket properties without sharing ancestry, which is a prediction the analogy actually gets right. |
| A model's confidence score is like a weather forecast's chance of rain. | **Survives.** Three things transfer: a confident answer can still be wrong, a well-calibrated number is right about as often as it claims, and two forecasters using different scales must be put on a common footing before their numbers are compared. That last one makes z-scoring across models feel inevitable rather than arbitrary, which is the sign of a good analogy. |
| Fine-tuning a model is like teaching it a new language. | **Fails.** It implies a separate competence acquired alongside the old one, whereas fine-tuning moves the same parameters and can destroy prior ability. The reader is left unable to anticipate the one phenomenon they most need to expect, which is that the model gets worse at what it used to do. |
| A knowledge graph is like a family tree. | **Survives only for one page, then fails.** Transferable: named entities, typed and named relationships, traversal in hops. Not transferable: a family tree carries one relation type with a single consistent direction, whereas the point of our graph is that it holds several incommensurable relations at once. Use it to introduce nodes and edges; drop it before you discuss similarity axes, or the reader will assume the axes are comparable. |
| DNA is like a blueprint. | **Fails.** A blueprint is a scale drawing read by a builder against a plan, so the mechanism is representational, top-down, and has a position-for-position correspondence with the finished building. Genetic information is executed locally with no reader, no plan, and no such correspondence. The analogy leaves the reader looking for the architect. |
| A transporter is like a revolving door. | **Survives, with a stated boundary.** Transferable and genuinely predictive: things cross one at a time, in a direction, at a limited rate, and the door can be jammed by something that fits but does not pass — which is exactly how competitive inhibition of a transporter behaves, and saturation follows straight from it. Boundary: a revolving door is pushed by the person going through, so it says nothing about active transport's energetics. |
| The oracle gap is the difference between the best answer in the room and the answer the teacher calls on. | **Survives.** It separates whether the knowledge is present from whether the picking procedure finds it, which is precisely the decision the number exists to inform, and it predicts the right action: if the room knows the answer, fix the calling procedure rather than the room. |
| A scoring metric is like a ruler. | **Fails here specifically.** A ruler measures one quantity monotonically and two rulers agree. Our metrics disagree with one another and each rewards something different, so the analogy makes "which metric" sound like a question of units when it is a question about the definition of success. It would survive in a context where only one metric existed, which is the tell that a failing analogy is often a context error rather than a bad picture. |
| Docking is like trying keys in a lock until one turns. | **Half survives, and the halves must be stated.** Transferable: it is a search over placements, scored by how well each fits. Not transferable: a real lock gives an unambiguous yes, whereas a docking score is a noisy estimate that ranks poorly. Use it to say what docking *does*; never to imply the score tells you which pose is right. |
| A promiscuous protein is like a person with poor taste. | **Fails, and is worth including as the failure mode of tone.** It is memorable, mildly funny, and carries no mechanism at all — nothing about taste predicts a large flexible cavity, convergence across unrelated families, or anything else. A reader remembers the joke and loses the fact, which is the specific harm a bad analogy does. |

## The three moves that make a plain register work

### Move 1 — Say what it does, not what it is called

**Before.** "PXR is a nuclear receptor with a promiscuous ligand-binding domain."

This also fails mechanically: `nuclear receptor`, `promiscuous` and `ligand-binding
domain` are all in the lexicon, so three separate jargon hits before the sentence has told
anyone anything. (Verified against `undefined_jargon` with an empty glossary, which is
what the checker reports.)

**After.** "This protein's job is to notice foreign chemicals and, when it finds one,
switch on the liver's clean-up machinery. It is unusually indiscriminate about what
counts as a foreign chemical, which is exactly what makes predicting what it will grab
hard."

The naming is not omitted, it is deferred: the glossary carries "nuclear receptor" and
"promiscuous" once for the run, and the renderer makes them hoverable wherever they
appear afterwards.

### Move 2 — Name the consequence in the same breath as the fact

A non-specialist has no way to judge whether a fact is important. Supplying that
judgement is the work; withholding it and hoping the reader infers it is the most common
way a plain register ends up useless while looking fine.

**Before.** "The pocket volume varies by roughly a factor of two across the known
structures."

**After.** "The cavity is not one fixed shape. Across the known structures it ranges
from roomy to nearly twice as roomy. So there is no single correct shape to aim at, and
a prediction that commits to one will be wrong for some molecules by construction. What
we have to decide is which shape to target, not whether there is more than one."

Four sentences averaging about fifteen words. The "before" is one sentence of thirteen
words that passes both mechanical checks and communicates nothing.

### Move 3 — Use an analogy only if it survives scrutiny

**Before.** "Choosing one answer from the pool is like picking the sharpest photograph
from a burst."

It fails on the mechanism. Sharpness is directly visible and is itself the quality you
want; confidence is an estimate of a quality you cannot see. The analogy quietly promises
that looking harder is enough, which is the opposite of the finding that every clever
selector lost to a simple one.

**After.** "Each program also reports how sure it is, the way a forecast reports a chance
of rain. A high number is not a guarantee, and two programs' numbers are not on the same
scale. So before comparing them we rescale each program's numbers against its own track
record, and only then ask which program is most confident about this particular
molecule."

## Self-check before submitting

Run these four in order. Three of them the validator cannot do for you.

1. **Read the plain register aloud.** If it sounds like you are explaining something to a
   colleague rather than to a stranger, it is not done. This catches more than any other
   check, and it is the one habit worth building.
2. **Would a stranger know why it matters?** Not what it says — why it matters. If the
   answer is only in the expert registers, you have written a summary, not an
   interpretation. The test in the SKILL is whether it answers *so what*.
3. **Is every technical term either absent or in the glossary?** Check the ordinary-looking
   words too: *fold*, *domain*, *residue*, *template*, *seed*, *ensemble*, *buried*,
   *affinity*, *series* and *motif* are all flagged in their technical uses. Where you do
   want the term, define it once on `ModelReport.glossary` with its plural and its
   common aliases, and it is legal everywhere for the rest of the run.
4. **Is the average sentence under 25 words?** The validator fails above 32, but one
   runaway sentence can drag an otherwise plain paragraph over, and a paragraph that
   averages 30 is unpleasant long before it is illegal.

Then, for each implication: does `direction` say what it argues FOR or AGAINST in words a
reviewer could disagree with, and does `if_wrong` name a failure downstream rather than
restate the finding? The keyword check will pass a `direction` that names a topic. You are
the only thing that will not.

Finally:

```bash
reagent report validate --strict reports/<run>/<stage>/report.json
```

Strict mode also reports, as notes rather than failures, which audience registers the
report actually covers. A report whose findings all speak only to `ml_practitioner` has
not done this work, whatever its `plain_summary` says.
