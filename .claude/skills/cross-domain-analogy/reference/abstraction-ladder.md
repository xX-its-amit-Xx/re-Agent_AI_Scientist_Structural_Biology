# The abstraction ladder — worked examples

Abstraction is the core discipline of this skill. A scout returns a practice as
practitioners in some field state it; nothing transfers until that practice has
been rewritten as a mechanism with no source-domain nouns in it, and until the
condition that mechanism requires has been checked against the problem in front of
us.

This file works that step through eight examples so the shape is unmistakable.
Three of them fail, which is the normal and desired outcome.

## The four rungs

| Rung | What it is | Where it goes |
|---|---|---|
| 1 | The practice as a practitioner in the source domain states it, in their vocabulary | `AnalogyCard.source_practice`, and the reason it works goes in `why_it_works_there` |
| 2 | The abstracted mechanism, with every source-domain noun deleted, including the *because* | `AnalogyCard.mechanism` |
| 3 | The structural precondition — what must be true of *any* problem for the mechanism to help | `AnalogyCard.structural_precondition` |
| 4 | Whether that precondition holds for our actual problem, with specifics, and the verdict | **Not a card field.** It is the Step 3 grounding note, and it lives in the `Finding` or the `Proposal.rationale` |

Rung 4 deliberately sits outside the card. The card is domain-neutral and reusable
across runs; the grounding check is specific to one problem and one moment. Keeping
them separate is what lets a card that failed for one problem be picked up again
for a different one, and it is why `AnalogyCard` has no verdict field.

Rungs 2 and 3 are where the discipline bites. Two rules:

- **Rung 2 must contain a causal claim.** "Combining ordinal ranks is more robust
  than combining raw scores" is a description. "…because ranks discard the
  miscalibration that makes scores incomparable" is a mechanism. Without the
  *because* you cannot derive rung 3, and you will end up guessing at the
  precondition rather than deducing it.
- **Rung 3 must be capable of failing.** If you cannot name a plausible problem
  that the precondition excludes, you have written a truism, not a precondition.
  Test it: state a problem where the mechanism would obviously not help, and check
  that your rung 3 excludes it. If it does not, rung 3 is too weak.

## The example problems

The examples below are checked against three concrete problems, so that the same
ladder can be seen passing on one and failing on another. The system is
target- and domain-agnostic, and the third problem exists to make that visible.

**Problem A — blind pose selection.** Predict a bound complex for each of 184
protein-ligand pairs. Six co-folding generators have produced a pool of candidate
poses across multiple seeds. Each generator emits its own confidence on its own
scale. No ground truth exists on the test items; a local holdout of 53
crystallographically solved complexes is available. The generators are trained on
overlapping public structural data and their errors are known to be correlated.
The test set is bimodal: 76 crystallographic fragments with very low chemical
similarity to any known ligand for this target, and 108 larger drug-like
molecules. This is the reference exemplar; see
`../../ai-scientist/reference/pxr-case-study.md`.

**Problem B — the scarce evaluation channel.** The only unbiased score comes from
a remote evaluation server that accepts roughly one submission every four hours,
inside a thirty-day window. An incumbent submission holds the current best score.
The public standing displays the most recently submitted entry rather than the best
one, so a bad submission actively destroys standing.

**Problem C — an out-of-distribution property regression.** Predict a measured
molecular property for a set of compounds. The available assay corpus is
concentrated in one chemotype; the compounds we must predict for sit largely in a
second chemotype with low structural similarity to the first. A model fitted on
the corpus is observed to reverse the sign of its structure-property relationship
on the second chemotype.

---

## Ladder 1 — Reciprocal rank fusion (information retrieval)

**Rung 1, the practice as stated.** When several retrieval systems have each
returned a ranked list for the same query, do not average their relevance scores.
Instead, give each document a score equal to the sum over systems of one divided by
a constant plus its rank in that system's list, and re-rank on that sum. This
consistently outperforms score-based fusion on shared-task benchmarks, because
retrieval systems have wildly different score distributions and a well-calibrated
system's scores get swamped by a badly-scaled one's.

**Rung 2, the abstracted mechanism.** When several scorers rank the same candidate
set on non-commensurable scales, combining their ordinal ranks is more robust than
combining their raw scores, because ranks discard the miscalibration that makes
scores incomparable while retaining the ordering information that is common to
them. Aggregating across scorers then averages away the part of each scorer's error
that is idiosyncratic to it.

**Rung 3, the structural precondition.** Multiple scorers must rank a shared
candidate set; their score scales must be miscalibrated relative to each other, so
that there is something for the rank transform to discard; and their errors must be
at least partly independent, so that aggregation cancels error rather than
reinforcing it.

**Rung 4, does it hold for Problem A.** The first two conditions hold cleanly: six
generators score a shared pool per item, and their confidences are on
incompatible scales — an interface predicted-TM value, a predicted distance error,
and a pocket-restricted predicted aligned error are not the same quantity. The
third condition **fails**. The generators are trained on heavily overlapping
public structural data and make the same mistakes on the same items; agreement
among them is evidence that a shared bias is operating, not that the answer is
right. In the reference case this was measured rather than assumed: consensus,
medoid, Borda, and rank-fusion selectors all regressed against the simpler
alternative, and consensus was actively harmful.

**Verdict: precondition fails on error independence. Do not transfer.** Record it
as a rejected proposal with the failure named, because "we tried rank fusion and it
was worse than doing nothing" is a `NEGATIVE` finding worth keeping, and it stops
the next run rediscovering it.

**Why this failure is the most instructive one in the file.** Two of the three
preconditions held, and the mechanism is genuinely excellent in its home domain.
Nothing about the card was wrong. It failed because the *third* condition is the
one that scouts routinely omit, and it is omitted precisely because in retrieval it
is nearly always satisfied — independently built search engines really do fail
differently. A precondition that is invisible in the source domain because it is
always true there is exactly the precondition that kills the transfer.

---

## Ladder 2 — Cross-sectional standardisation of factor scores (quantitative finance)

**Rung 1, the practice as stated.** Before combining several predictive signals
into one ranking of a universe of assets, standardise each signal
cross-sectionally: for each signal, compute its mean and standard deviation across
all assets at that moment, and replace each raw value with its deviation from that
mean in units of that standard deviation. Only then compare or combine. Raw signal
values carry each signal's own arbitrary units and its own drifting level, and
comparing them directly means the signal with the widest spread dominates for no
reason connected to its skill.

**Rung 2, the abstracted mechanism.** When several producers each score the same
population of items on their own arbitrary scale, comparing scores *across*
producers is meaningless until each producer's scores have been re-expressed
relative to that producer's own distribution over the population. Standardising
each producer's scores across the shared population removes the producer's
arbitrary location and scale while preserving how unusual a given item is *for that
producer*, which is the only part of the score that carries cross-producer
information.

**Rung 3, the structural precondition.** Each producer must score the *same*
population of items, so that a common reference distribution exists per producer;
that population must be large enough to estimate a location and a scale per
producer with tolerable error; and the comparison actually required must be across
producers rather than within one.

**Rung 4, does it hold for Problem A.** All three hold. Every generator produces a
best-sample confidence for all 184 items, giving each a full 184-point
distribution over the shared population, which is ample for a mean and a standard
deviation. And the decision genuinely is a cross-producer one — for each item,
which generator's candidate do we take — so the incomparability is on the critical
path rather than incidental. Notice also what this mechanism does *not* require:
because the standardised scores are used to pick a single producer per item, by
taking the largest standardised value, and not to average producers together,
error independence is irrelevant here. That is the entire difference from Ladder 1.

**Verdict: precondition holds. Transfer.** In the reference case this single change
moved the primary metric from 0.4996 to 0.5472, the largest single improvement in
the project.

**The pedagogical pair.** Ladders 1 and 2 come from adjacent domains, operate on
identical inputs, and differ only in whether they combine producers or choose
between them. Combining requires independent errors; choosing does not. A scout
that returns both, and a reviewer who does not notice the distinction, will reject
both or accept both, and either is wrong. This is the level of care rung 3 has to
be written with.

---

## Ladder 3 — Acceptance sampling with a rejection band (manufacturing quality control)

**Rung 1, the practice as stated.** Do not ship a production lot on the basis of
having built it carefully. Draw a sample, measure it against a pre-published
acceptance criterion with defined producer and consumer risk, and reject the lot if
the sample fails, without argument or rework-on-the-spot. The criterion is fixed
before the lot is inspected precisely so that a marginal lot cannot be talked
through by whoever is under schedule pressure.

**Rung 2, the abstracted mechanism.** When commitment to an outcome is scarce or
irreversible, and a cheap measurement is available before commitment that is
correlated with the outcome, a threshold on the cheap measurement fixed *in advance
of seeing the candidate* converts a judgement call under pressure into an
arithmetic check. Fixing the threshold in advance is the load-bearing part: it
removes the decision from the moment at which motivated reasoning is strongest.

**Rung 3, the structural precondition.** Commitment must be scarce or
irreversible, so that a wasted commitment has real cost. A measurement must be
computable on a candidate before committing it. That measurement must have a
demonstrated relationship to the outcome, established on prior candidates rather
than assumed, so that a threshold can be placed non-arbitrarily.

**Rung 4, does it hold for Problem B.** Yes, on all three. Commitment is scarce at
roughly one scored submission per four hours and effectively irreversible because
the public standing tracks the latest entry. Several quantities are computable
offline on a candidate before submission: whether it passes format and ligand-graph
validation, how far it diverges from the incumbent, and how it scores against the
local holdout. And the relationship to the outcome was demonstrated rather than
assumed — in the reference case, every candidate that diverged from the incumbent
by more than about 30 per cent of its items scored below 0.47, which is what
licensed a band rather than a guess.

**Verdict: precondition holds. Transfer.** The reference implementation was a
three-gate pre-flight test: zero format and connectivity errors, divergence from
the incumbent inside a 5 to 30 per cent band, and local holdout error under a fixed
threshold with at least three of four confidence signals concurring. It rejected 13
candidates. In two consecutive iteration blocks, zero of twelve candidates passed
all three gates, which is the gate working rather than the gate failing.

**The dependency worth naming.** The third precondition is not satisfiable on
attempt one. The band came from the history of prior candidates and their scores,
so the mechanism cannot be installed before some history exists. That is a real
limitation of the transfer, and it is exactly what the reference project's authors
identified in hindsight: the gate should have been codified at the second
iteration rather than the third, because the history needed to set it already
existed by then and eleven submission slots were spent before it was. When a
precondition is "we must have accumulated evidence of a relationship", the proposal
should say how few observations are enough, and should ship a provisional band with
a stated plan to tighten it.

---

## Ladder 4 — Reliability diagrams and the calibration/discrimination split (weather forecasting)

**Rung 1, the practice as stated.** Do not evaluate a probabilistic forecast by a
single accuracy number. Bin the forecasts by their stated probability, and for each
bin plot the observed frequency of the event against the stated probability. A
forecast system that says 70 per cent and is right 70 per cent of the time is
calibrated; one that is wrong in a consistent direction is miscalibrated and can be
repaired by post-processing without touching the model. Discrimination — whether
the forecast separates events from non-events at all — is a different property, is
measured separately, and cannot be repaired by post-processing.

**Rung 2, the abstracted mechanism.** A stated confidence has two independent
defects. It can be systematically shifted or compressed relative to the truth,
which is a defect of the mapping from internal signal to reported number and is
repairable by learning that mapping from outcomes. Or it can fail to order items by
their actual quality at all, which is a defect of the underlying signal and is not
repairable by any transformation of it. Separating the two tells you whether to
recalibrate or to replace, and the diagnostic requires grouping items by their
stated confidence and comparing each group's stated level to its realised outcome
rate.

**Rung 3, the structural precondition.** Confidences must be stated on a scale
whose values are claims about outcomes, so that a comparison to realised frequency
is meaningful. Outcomes must be observed for a set of items drawn the same way as
the items of interest. And that set must be large enough to populate several
confidence bins with enough items each that the observed rate in a bin is not
dominated by sampling noise — a few dozen items across the whole range is not
enough for any bin.

**Rung 4, does it hold for Problem A.** Partially, and the part that fails is
decisive. The first condition is already shaky: a generator's interface confidence
is an internal quality signal, not a stated probability that any defined event will
occur, so "is it calibrated" is not quite a well-posed question without first
choosing an event to calibrate against. The second condition holds only on the
local holdout, and there with a caveat — the holdout is 53 solved complexes drawn
from historical crystallography, and the test set is bimodal with 76 fragments that
are chemically unlike anything in it, so the holdout is not drawn the same way as
the items of interest. The third condition **fails outright**. Fifty-three items do
not populate a reliability diagram; split into even five bins that is about ten
items per bin, and the observed rate in a ten-item bin has a standard error large
enough to swallow any miscalibration worth correcting. In the reference case the
consequence was visible independently: on the 35-structure version of the holdout
all methods clustered inside 0.05 Ångström, the noise floor, while the real metric
spanned a five times wider range.

**Verdict: precondition fails on sample size. Do not transfer as a calibration
procedure.** What survives is the *conceptual* split — asking of each confidence
signal whether its problem is ordering or level — because that question can be
asked without a reliability diagram, and asking it is free. Record that as a
design-choice finding rather than a proposal.

**Why this failure is easy to miss.** Nothing about Problem A is structurally
alien to the mechanism. It has confidences, it has a holdout with outcomes, and the
data shape looks exactly like what the mechanism consumes. The transfer fails on a
*quantity* rather than on a kind, and quantity failures do not announce themselves.
A precondition that says "outcomes must be observed" would have passed this card
through. The precondition has to say how many.

---

## Ladder 5 — Limiting similarity and response diversity (ecology)

**Rung 1, the practice as stated.** Two species that use resources in the same way
cannot stably coexist; the more similar they are, the more strongly they compete
and the less the community gains from having both. Communities are robust not
because they contain many members that perform the same function, but because they
contain members that perform that function and fail under *different* conditions.
Redundancy in function with diversity in response is what buffers a community
against a perturbation.

**Rung 2, the abstracted mechanism.** When adding a member to a collection under a
size budget, the value of the addition is set by what it covers that the existing
members do not, and not by how good it is on average. Two strong members that fail
on the same inputs contribute roughly as much as one; a weaker member that fails on
different inputs raises the collection's coverage on exactly the inputs where the
collection is currently failing. Selecting additions by marginal complementarity
therefore dominates selecting them by individual quality once the collection is
past its first member.

**Rung 3, the structural precondition.** The collection must have a real size or
cost budget, so that additions compete. Its value must be a function of coverage
over a set of inputs rather than of average member quality, which requires that
some downstream step be able to *use* the best member per input rather than the
average. And a measurable dissimilarity between members must exist that actually
predicts failing on different inputs, rather than merely predicting being different.

**Rung 4, does it hold for Problem A.** Yes. The budget is real: each generator
costs compute and credits, and the pool cannot be widened indefinitely. The value
of the pool is genuinely a coverage function, because a selection step chooses one
candidate per item, so a candidate that is excellent on one item and terrible
elsewhere still contributes its full value on that item — this is exactly what an
oracle-gap measurement quantifies, and in the reference case the pool's achievable
ceiling was far better than any single generator realised. The third condition is
the one to verify rather than assume, and it can be verified directly: measure
per-item error correlation between generators on the holdout, and prefer the
generator whose errors correlate least with the incumbent set rather than the one
with the best average.

**Verdict: precondition holds. Transfer.** The reference case's two effective
levers were both instances of it: widen the pool with generators that fail
differently, and overwrite only the lowest-confidence tail of items with a
decorrelated generator's output. The tail rescue swept over how many items to
overwrite and peaked at eight of 184, with more or fewer both worse — which is the
mechanism's own logic, since past the point where the incumbent is actually failing
you are replacing good answers with worse ones.

**Note the boundary with Ladder 1.** Diversity here is used to *widen* and to
*substitute per item*, never to *vote*. Both uses of diversity come from the same
observation that members fail differently, but voting additionally requires that
the failures cancel when averaged, and substitution does not. Use cross-member
diversity to widen coverage; do not use it to vote.

---

## Ladder 6 — Stabilised approach criteria and the go-around (aviation safety)

**Rung 1, the practice as stated.** An approach must satisfy a defined set of
criteria — on the correct path, at the correct speed, correctly configured — by a
specified gate on the way down. If any criterion is unmet at the gate, the crew
executes a go-around. The decision is pre-committed, it is not a judgement call at
the moment, it is explicitly blameless, and the consequences of the abandon are
accepted in advance. Attempting to salvage an unstable approach is a leading
contributory factor in approach-and-landing accidents, and the countermeasure is to
have already decided.

**Rung 2, the abstracted mechanism.** Committing, in advance and in writing, both
to the observation that will cause an attempt to be abandoned *and* to the
downstream consequences of that abandonment, removes the abandonment decision from
the moment at which sunk cost and schedule pressure are strongest. Pre-committing
the consequence, not just the test, is the part that carries the weight: a test
whose failure leaves the response open to negotiation gets negotiated.

**Rung 3, the structural precondition.** There must be a point past which
continuing is substantially more costly than stopping. A criterion observable
*before* that point must exist. And there must be a real tendency to salvage —
which is to say, the effort must have accumulated cost, and the person deciding
must be the person who spent it. Without that tendency the pre-commitment costs
paperwork and buys nothing.

**Rung 4, does it hold for Problems A and B.** Yes, and unusually strongly,
because the third condition is what makes it bite and it is fully satisfied — an
agent or a researcher who has spent hours building a signal is exactly the party
least able to abandon it neutrally. The reference case's implementation went beyond
a single kill criterion to a *transitive* one, committed before the test was run:
if a cheap strain-based scoring signal failed local validation, then a much more
expensive quantum-chemical version of the same idea was cancelled unbuilt. The
cheap version failed, the expensive project was cancelled without a new argument,
and roughly fourteen development hours were saved. Pre-registering the cascade is
what made the cancellation automatic rather than contentious.

**Verdict: precondition holds. Transfer.** This is why `Proposal.kill_criterion` is
a required field in the contract rather than a suggestion, and why the field
description insists on specificity. A proposal should also state which *other*
proposals its failure kills, in the `kill_criterion` text, because that is the part
that actually saves time.

**The calibration caveat from the domain map applies.** Aviation buys safety with
throughput because its failure mode is catastrophic. Ours mostly is not. Do not
import the ceremony — the checklists, the sign-offs, the two-person rule — for
decisions that are cheap and reversible. Import it for the ones that are genuinely
irreversible: a consumed submission slot, a standing that displays the latest entry
rather than the best, a fine-tune that overwrites a checkpoint.

---

## Ladder 7 — Chain of custody (forensic science)

**Rung 1, the practice as stated.** Physical evidence is accompanied by an unbroken
documented record of every person who handled it, when, and what they did. A gap in
the record makes the evidence inadmissible even when there is no reason to think
the sample was altered, because the *possibility* of alteration cannot be excluded
and the burden is on the party offering it. The record is created at collection
time, not reconstructed later.

**Rung 2, the abstracted mechanism.** When a conclusion depends on an artefact that
has passed through several transformations by several actors, the conclusion's
trustworthiness is bounded by the completeness of the record of those
transformations, independently of whether any of them actually went wrong. Recording
provenance at the moment of each transformation, rather than reconstructing it
afterwards, is the only version that works, because reconstruction cannot
distinguish a step that was done correctly from one that was merely remembered as
having been done correctly.

**Rung 3, the structural precondition.** The artefact must pass through multiple
transformations, plausibly by different actors or at different times. There must be
a foreseeable later question of the form "is this result attributable to that
input". And the cost of recording at each step must be lower than the cost of the
later dispute — which is where this fails, for a one-step throwaway analysis.

**Rung 4, does it hold for Problems A, B, and C.** Yes for all three, and the
condition that decides it is the second. These pipelines have many hands: several
generators, a selection step, a refinement step, a submission step, and in Problem
C a corpus assembly step with per-entry weights. The later question is not
hypothetical — in the reference case, the same input was reprocessed after a
validator change and produced a different output, and without a record of which
copy of the input each result came from that discrepancy is unresolvable. The third
condition holds because the recording cost is a hash and a timestamp.

**Verdict: precondition holds. Transfer.** It has already been transferred into
this repository's contracts, which is worth noting because it is a case where the
right response to a good card is "we do this, and here is where" rather than a new
proposal. `Evidence.locator` is required and must be resolvable. `DataRef` carries
`sha256` and `retrieved_utc`, and the validator refuses a `local_path` without a
`retrieved_utc`, which is the no-gap-in-the-record rule stated in code. The
`DecisionLedger` is append-only, and changing a verdict requires a new `Decision`
with `supersedes` set rather than an edit. `Decision.decided_by` must be non-blank,
which is the requirement that every handling step name its actor.

**The corollary that gets skipped.** Chain of custody also implies the *inverse*
duty: recording the breaks. A dead download link is a break in the chain, and
`DataRef.fetch_error` exists so that the break is on the record rather than being
silently absent. A missing node and a node that records its own failure are very
different for the next agent.

---

## Ladder 8 — Item response theory (psychometrics)

**Rung 1, the practice as stated.** Given a matrix of respondents by test items,
with each cell recording whether that respondent got that item right, jointly
estimate a difficulty parameter for each item and an ability parameter for each
respondent. This separates the two, so that a respondent who attempted only hard
items is not penalised and an item that only strong respondents reached is not
mistaken for an easy one. The estimates support adaptive testing, in which the next
item presented is the one that carries the most information about the current
ability estimate.

**Rung 2, the abstracted mechanism.** When a set of scorers each produce
observations on a set of items, and the observed quantity is a graded outcome
generated by an interaction between a per-scorer latent quality and a per-item
latent difficulty, both sets of latent quantities can be recovered jointly from the
observation matrix even when it is incomplete. Recovering them separates "this
scorer is good" from "this item is easy", which no marginal average can do.

**Rung 3, the structural precondition.** There must be an *observed graded
outcome* per scorer-item pair — something that was right or wrong, or scored on a
scale by an external standard — because the latent quantities are identified only
through their effect on that outcome. The observation matrix must overlap enough
across scorers and items to link them. And the response process must be at least
approximately monotone in the latent quality, so that a higher latent value makes a
better outcome more likely.

**Rung 4, does it hold for Problem A.** The second condition holds beautifully —
six generators by 184 items is a fully crossed matrix, far better linkage than most
real test data. The third is plausible. The first **fails**, and it is fatal. What
each generator emits per item is its *own confidence*, which is a self-report and
not an outcome. There is no external grading of whether the generator got that item
right, because that is precisely the ground truth we do not have. Fitting an item
response model to a matrix of self-reported confidences will converge and will
produce per-generator and per-item parameters, and those parameters will describe
the joint structure of the generators' *self-assessments* and nothing about
correctness. If all six generators are confidently wrong on the same item — which
is the correlated-error situation we already know obtains here — the model will
score that item as easy.

**Verdict: precondition fails on the absence of an anchoring observation. Do not
transfer.** The variant that would work is to fit the model on the 53-structure
holdout, where a graded outcome does exist, and carry the item parameters across —
but that reintroduces the Ladder 4 problem, because 53 items cannot support
per-item difficulty parameters for six scorers, and it additionally requires that
the holdout items be exchangeable with the test items, which the bimodal test set
explicitly violates.

**Why this failure is the most seductive of the three.** The data *shape* is
exactly right. A full scorers-by-items matrix of numbers is what the method
consumes, the software will accept it, the fit will converge, and the output will be
interpretable-looking parameters. Nothing will error. The precondition that fails
is semantic rather than structural — what the numbers in the cells *mean* — and no
amount of staring at the matrix reveals it. When a mechanism requires a particular
*kind* of observation, rung 3 must say what kind, not merely that observations are
required.

---

## Surface-resemblance traps

A metaphor is a claim that two things are alike. A mechanism is a claim that
something happens *because* of a stated structural feature. Metaphors are cheap to
generate, they feel productive, and they survive review because nobody can say
exactly what is wrong with them. These are the recurring ones.

**Folding.** "Proteins fold, origami folds, so origami crease patterns are a prior
for structure prediction." The shared word denotes a shared visual outcome, not a
shared process. Origami crease patterns are designed backwards from a target shape
by a designer with global knowledge; a chain finds a conformation forwards from
local interactions with no global knowledge. There is no mechanism because there is
no *because*.

**Portfolio diversification without decorrelation.** "Diversify the model ensemble,
like a portfolio." Diversification in finance reduces variance strictly to the
extent that returns are less than perfectly correlated, and the whole content of
the idea is in the correlation structure. Dropping the correlation and keeping the
word "diversify" produces a recommendation to add more of the same thing. This is
Ladder 1's failure with the causal clause deleted, which is what makes it
undetectable — the deletion is the trap.

**Immune-system language.** "Build an immune system for the pipeline: it learns to
recognise bad poses." The immune system's actual mechanisms — clonal selection
under proliferation, somatic hypermutation, negative selection against self during
development — each require machinery we do not have and generations we cannot run.
What is being borrowed is the *feeling* of adaptive defence.

**Evolution as a synonym for iteration.** "Let the candidates evolve." Evolution
requires heritable variation, differential reproduction driven by a selection
criterion, and enough rounds for the differential to compound. Calling three rounds
of manual tweaking "evolution" imports the word and none of the machinery. Test:
name the population, the heritable representation, the variation operator, the
selection criterion, and the number of generations. If any is missing there is no
mechanism.

**Entropy, resonance, phase transition, emergence.** Physics vocabulary applied by
analogy. Each has a precise technical meaning that carries real machinery, and each
is used far more often in the loose sense than the precise one. Test: can the
quantity be computed? If nobody can say what the entropy is *of*, over what
distribution, the word is decoration.

**Wisdom of crowds.** "Average the models — crowds are wise." The classical result
requires independent judgements from members with individually better-than-chance
accuracy, and it fails outright under correlated judgement, which is why the
literature on it spends most of its length on independence. The phrase has entirely
shed that condition in ordinary use.

**Annealing.** "Anneal the search: start hot, cool down." This one is halfway
legitimate — simulated annealing is a real algorithm with a real convergence
argument, and it transfers. But the *word* is often used for any schedule that
decreases something over time, with no acceptance criterion, no temperature, and no
proposal distribution. Test: is there an acceptance rule that sometimes accepts a
worse state? If not, it is a decaying learning rate wearing a costume, which is
fine but should be described as what it is.

**Market efficiency.** "If that signal worked, someone would already be using it."
The efficiency argument requires many competing participants with an incentive to
find and exploit the signal, and a mechanism by which their exploitation removes
it. In a research field with a few dozen groups and no arbitrage mechanism, the
premise fails and the conclusion — that unexploited signals cannot exist — is
simply false. This trap is unusual in that it argues *against* doing something, so
it never gets challenged.

### How to spot one in four questions

Apply these to rung 2 before doing anything else with a card.

1. **Delete every noun specific to the source domain. Is there a sentence left with
   a subject that does something?** If deleting the source nouns leaves "when
   things are similar, combining them helps", there was never a mechanism. This is
   the test the contract gestures at by rejecting a `mechanism` that merely
   restates the `source_practice`, and the contract's own check is a weak
   string-equality guard, so the real enforcement is this one, done by you.

2. **Does rung 2 contain a "because" that names a structural feature?** Not
   "because it works better", which is a result, and not "because it is more
   robust", which is a restatement. It must name the feature of the situation that
   makes the mechanism operate, in terms that could be true or false of some other
   situation.

3. **Can you write a rung 3 that some plausible problem fails?** Write the
   precondition, then name a problem it excludes. If nothing is excluded, you have
   a truism. Note that this test also catches the *opposite* error, a precondition
   so specific that it merely redescribes the source domain.

4. **Does the source domain have a way of knowing this practice works, and does
   `why_it_works_there` cite it?** A practice from a field with no measurable
   outcome was selected for being teachable, not for working. This is not
   disqualifying — process practices from design have been tested elsewhere — but
   it moves the burden of evidence onto the transfer, and the proposal's prediction
   and kill criterion have to carry it.

A card that survives all four still owes rung 4, and rung 4 is where most
survivors die. Roughly seven in ten discarded across rungs 2 through 4 is a healthy
rate. A pass that discards nothing has not checked anything.
