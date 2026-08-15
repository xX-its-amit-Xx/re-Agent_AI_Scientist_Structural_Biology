# Domain map — where to scout, and for what

This is a working map of non-biology fields worth sending a scout into. It exists
to make one decision well: **which domains to fan out to for a given restated
gap.**

## Pick by structural affinity, not by novelty

The temptation is to scout exotic fields because they sound creative. Resist it.
Scouting is cheap per domain but the triage that follows is not, and a domain with
no structural affinity to the restated gap produces cards that all die at the
precondition check. That is wasted reviewer attention, which is the scarcest
resource in this skill.

The correct procedure is mechanical. Take the restated structural gap from Step 1
of the workflow, and identify its **shape** — the two or three abstract features
that make it hard. Then choose domains that have those same features as their
daily working conditions. A field is worth scouting when practitioners there face
your structural problem *every day and get paid for solving it*, because that is
what produces named practices with worked-out failure modes rather than one-off
papers.

Some common shapes and the domains that own them:

| If the restated gap involves… | Scout first |
|---|---|
| ranking or selecting with no ground truth available | information retrieval, quantitative finance, psychometrics |
| combining incommensurable scores from different producers | information retrieval, quantitative finance, weather forecasting |
| a scarce, costly, irreversible evaluation channel | manufacturing quality control, aviation safety, operations research |
| a test population that differs from the training population | epidemiology, cybersecurity, sport analytics |
| deciding what to add to a collection under a size budget | ecology, operations research, information retrieval |
| distinguishing a real effect from an artefact of small samples | sport analytics, experimental physics, psychometrics |
| establishing that a result is attributable to a specific input | law and forensics, metrology, aviation safety |
| a pipeline whose cost depends on choices made much earlier | databases and compilers, operations research |
| bimodal populations where a fix for one half harms the other | epidemiology, ecology, sport analytics |
| calibration: does a stated confidence mean what it says | weather forecasting, psychometrics, quantitative finance |

Two or three domains chosen this way beat ten chosen for colour. If a restated gap
maps onto no domain in this table, the restatement is probably still carrying
domain vocabulary — go back and strip it further before spawning scouts.

## The domains

Each entry gives four things: what the domain is structurally good at, the named
practices a scout should be able to find and name, where to search inside it, and
the characteristic failure mode of transferring *from* that domain. The last field
is the most useful one, because each domain fails in a recognisable way and
knowing the pattern lets you kill a bad card in one line.

---

### Quantitative finance

**Structurally good at.** Making decisions from noisy signals where the truth
arrives late or never, where every participant is trying to extract the same
information, and where a mistake is expensive and measurable. Especially strong on
combining many weak predictors, on distinguishing skill from luck in short
records, and on the failure modes of retrospective evaluation.

**Named practices worth knowing.** Cross-sectional standardisation of factor
scores before combination. Regime detection and regime-switching models. Ensemble
and risk-parity weighting by inverse volatility rather than by expected return.
Walk-forward and purged, embargoed cross-validation for time-ordered data. The
deflated Sharpe ratio and the probability of backtest overfitting. Risk of ruin
and Kelly sizing. Marking to market versus marking to model. The distinction
between an alpha signal and a risk factor.

**Where to search.** The *Journal of Portfolio Management*, *Quantitative
Finance*, the *Journal of Financial Data Science*, and the *Financial Analysts
Journal* for practitioner-facing method papers. SSRN and arXiv q-fin for
preprints. Practitioner books are unusually load-bearing in this field: Grinold
and Kahn on active portfolio management, and López de Prado on machine learning in
finance, are both cited by practitioners as method references rather than as
popularisations. Firm research notes and quant blogs carry defaults that never
reach papers.

**Characteristic transfer failure.** Finance assumes a **stationary-enough process
with a repeated decision** and an eventual, unambiguous profit-and-loss readout.
Many of its most attractive mechanisms silently require both. If our problem is a
one-shot prediction with no repeated draws, anything built on averaging over
realisations or on estimating a covariance from history will not transfer. Also
watch for mechanisms that require a *tradable* action: finance can size a position
continuously, and a great deal of its machinery assumes that partial commitment is
possible when ours is all-or-nothing.

---

### Cybersecurity

**Structurally good at.** Detection when the thing being detected is rare, when an
adversary is actively shaping the input distribution, and when the cost of a false
negative and a false positive differ by orders of magnitude. Also unusually honest
about layered, redundant defence because single controls demonstrably fail.

**Named practices worth knowing.** Adversarial validation — train a classifier to
distinguish the training set from the deployment set, and read its accuracy as a
distribution-shift measurement. Base-rate reasoning and the base-rate fallacy in
alerting. Defence in depth and the notion of a control that fails safe. Canary
tokens and canary deployments. Purple-team exercises and assumed-breach
methodology. Fuzzing and coverage-guided input generation. Threat modelling with
an explicit trust boundary. Detection engineering with the ATT&CK framework as a
shared vocabulary of failure modes.

**Where to search.** USENIX Security, ACM CCS, IEEE Symposium on Security and
Privacy, and NDSS for reviewed work. Black Hat and DEF CON archives for
practitioner material, which is often more mechanistic than the academic
equivalent. Vendor detection-engineering blogs and the MITRE ATT&CK documentation.
Note that a great deal of cybersecurity's real practice lives in blog posts and
conference talks, so cards from this domain will often cite grey sources — that is
acceptable for an `AnalogyCard`, whose citations are locators from the source
domain and are never used as evidence about our problem.

**Characteristic transfer failure.** Cybersecurity presupposes an **adversary**:
an intelligent process that responds to your defence. Mechanisms that exist purely
to defeat adaptation are wasted effort against nature, which does not adapt to our
scoring function. Ask specifically whether the card's mechanism needs an
adversary, or merely needs adversarial *input*. The second transfers; the first
usually does not. A second, subtler failure: security accepts very high false
positive rates because a human triages the alerts, and our pipelines usually have
no such human in the loop.

---

### Ecology and evolutionary biology

This counts as a foreign domain for our purposes even though it is biology, because
its mechanisms are about populations, budgets, and diversity rather than about
molecules, and they abstract cleanly.

**Structurally good at.** Reasoning about diversity as a resource, about why
redundancy is sometimes efficient and sometimes waste, about the trade-off between
specialists and generalists, and about how systems absorb perturbation.

**Named practices worth knowing.** Niche partitioning and the competitive
exclusion principle. Limiting similarity as a criterion for whether a new member
can coexist in a community. Functional redundancy versus response diversity —
having several members that do the same job but fail under different conditions.
The insurance hypothesis and the portfolio effect in metapopulations. Occupancy
and detection modelling, which separates "absent" from "not detected". Rarefaction
and species-accumulation curves for asking whether more sampling would find
anything new. Beta diversity as a measure of how much two assemblages differ.
Invasion dynamics and propagule pressure. Adaptive radiation and the
generalist-specialist trade-off.

**Where to search.** *Ecology*, *Ecology Letters*, *Trends in Ecology and
Evolution*, *Journal of Animal Ecology*, *Methods in Ecology and Evolution* — the
last is explicitly a methods venue and is the highest-yield place to look for
transferable machinery. The R package ecosystem for community ecology (vegan and
its documentation) is effectively a catalogue of named methods with worked
examples.

**Characteristic transfer failure.** Ecological mechanisms usually depend on
**many generations and a selection pressure that operates without our
intervention**. Anything invoking evolution as a process, rather than as a
metaphor for iteration, needs a genuine reproduction-with-variation loop and
enough rounds for it to matter. Our pipelines usually get a handful of iterations.
Also, ecology's diversity results almost always require that the environment vary;
if our evaluation condition is fixed, the insurance value of diversity evaporates
and the specialist wins.

---

### Logistics and operations research

**Structurally good at.** Allocating a scarce resource across competing demands,
finding the constraint that actually determines throughput, and reasoning about
queues and buffers. This is the domain with the strongest formal machinery for
"what should we spend the next unit of budget on".

**Named practices worth knowing.** Theory of constraints and the five focusing
steps, whose central claim is that improving a non-bottleneck step yields nothing.
Little's Law relating work in progress, throughput, and cycle time. Critical path
method and the distinction between float and slack. Newsvendor inventory models
for a single perishable ordering decision under demand uncertainty. Safety stock
and service-level targets. Lagrangian relaxation and column generation as ways to
decompose a hard allocation problem. Multi-armed bandit allocation and the
explore-exploit trade-off. The knapsack framing of budgeted selection. Yield
management and overbooking.

**Where to search.** *Operations Research*, *Management Science*, *Manufacturing
and Service Operations Management*, *Interfaces* (now *INFORMS Journal on Applied
Analytics*) — the last publishes deployed applications with their failure modes,
which is exactly what a scout wants. Goldratt's *The Goal* is the canonical
statement of theory of constraints and is worth naming as a source. INFORMS
conference proceedings.

**Characteristic transfer failure.** Operations research mechanisms typically
require a **quantified objective and quantified constraints**, and they are only as
good as those numbers. A knapsack formulation of "which pipeline changes to fund"
is worthless if the value estimates are made up, and it will look rigorous while
being worthless, which is the dangerous case. Second failure mode: much of this
machinery assumes a *repeated* operating decision with a steady state. A thirty-day
challenge with six iterations has no steady state.

---

### Art, design, and music

**Structurally good at.** Working under hard constraints on purpose, generating
controlled variation on a theme, knowing when to stop revising, and the discipline
of critique. Also the deliberate use of imperfection and asymmetry.

**Named practices worth knowing.** Theme and variation, and its formal cousins in
composition — inversion, augmentation, retrograde. Oblique Strategies as a
structured method for breaking a stuck process by injecting an unrelated
constraint. The design charrette and the parallel-prototypes finding that
generating several alternatives in parallel produces better outcomes than
iterating on one. Critique protocols with separated description, interpretation,
and judgement. Kill-your-darlings editing. Negative space as a first-class design
element. Value studies and thumbnails as cheap low-fidelity commitment tests
before expensive rendering. Jazz's head-solo-head form as constrained
improvisation inside a fixed frame. Wabi-sabi and the deliberate acceptance of
irregularity.

**Where to search.** This domain rewards practitioner sources far more than
journals. Design-studio process writing, *Design Studies* and the Design Research
Society proceedings for the reviewed end, and the human-computer-interaction
literature at CHI where design method meets empirical evaluation — parallel
prototyping in particular has been tested there. Interviews with practitioners,
and technique books, are legitimate sources.

**Characteristic transfer failure.** This is the domain where surface metaphor is
most likely to masquerade as mechanism, and where scouts most often return puns.
The absence of a measurable outcome in the source domain means practices there
were never selected for *working* in any testable sense — they were selected for
being teachable. Demand unusually hard evidence in `why_it_works_there` for cards
from here, and be suspicious of any card whose mechanism cannot be stated without
the words "creative" or "elegant". When a card from this domain does survive, it
is usually about **process structure** (parallel exploration, cheap
low-fidelity tests before expensive commitment, separating generation from
judgement) rather than about aesthetics, and process claims from here have often
been tested elsewhere.

---

### Sport analytics

**Structurally good at.** Evaluating performance from very few observations,
separating a player's contribution from their circumstances, adjusting for
opponent strength, and resisting the narrative explanations that small samples
invite.

**Named practices worth knowing.** Regression to the mean, and shrinkage
estimators that explicitly pull small-sample estimates toward a population prior.
Empirical Bayes rate estimation. Strength-of-schedule and opponent adjustment.
Elo and Glicko rating systems, with Glicko's ratings-deviation term as an explicit
uncertainty tracker. Expected-value models such as expected goals, which replace a
sparse outcome with a denser proxy that has better signal per observation. Plus-
minus and regularised adjusted plus-minus for attributing a team outcome to
individuals. Aging curves and survivorship bias in them. The distinction between
descriptive, predictive, and prescriptive metrics, and the observation that the
best descriptive metric is frequently the worst predictive one.

**Where to search.** The MIT Sloan Sports Analytics Conference proceedings, the
*Journal of Quantitative Analysis in Sports*, and the sabermetrics literature. The
public analytics community produces high-quality method writing on blogs and in
open repositories, and the *Book of Basketball*-style popular sources are not
useful, but the technical blogs are.

**Characteristic transfer failure.** Sport analytics mechanisms almost always
assume **many comparable units observed repeatedly** — many players, many games,
the same rules. Shrinkage needs a population to shrink toward, and it needs the
population to be genuinely exchangeable with the item being estimated. If our
items are heterogeneous in a way that matters, pooling them to form a prior
imports exactly the bias we were trying to avoid. Ask what the population is and
whether it is exchangeable before accepting any shrinkage or rating card.

---

### Manufacturing quality control, reliability, and metrology

**Structurally good at.** Deciding whether to accept a batch without inspecting
all of it, detecting that a process has drifted before the output is out of
specification, propagating tolerances through a multi-stage assembly, and
enumerating failure modes systematically rather than reactively.

**Named practices worth knowing.** Statistical process control with Shewhart
control charts, and the distinction between common-cause and special-cause
variation. Western Electric rules for reading a control chart. Acceptance sampling
plans with defined producer and consumer risk, as codified in ANSI/ASQ Z1.4 and
its military predecessor. Cusum and exponentially weighted moving average charts
for detecting small persistent drifts. Process capability indices. Tolerance
stack-up analysis, both worst-case and root-sum-square. Failure mode and effects
analysis with risk priority numbers. Design of experiments, including fractional
factorial screening designs and Taguchi robust-design methods that optimise for
insensitivity to noise rather than for peak performance. Gauge repeatability and
reproducibility studies, which measure how much of observed variation is the
measuring instrument. Measurement uncertainty budgets and traceable calibration
chains. Poka-yoke, a fixture that makes an error physically impossible rather than
merely discouraged — this project's strict contracts are an instance.

**Where to search.** *Journal of Quality Technology*, *Quality Engineering*,
*Technometrics*, *Reliability Engineering and System Safety*. The ASQ handbook and
the NIST/SEMATECH *e-Handbook of Statistical Methods*, which is freely available
and is effectively a searchable catalogue of these methods with formulas.

**Characteristic transfer failure.** This domain's core machinery needs a
**stable, repeatable process with enough historical output to estimate normal
variation**. A control chart with no in-control baseline is a decoration. If we
are on our sixth attempt at something, we cannot set control limits; we can at
best set a band from the six attempts and label it provisional. Second failure
mode: acceptance sampling assumes the sampled unit is representative of the batch,
which requires that our proxy measurement actually correlate with the outcome we
care about. Verify that correlation before adopting any gate built on it.

---

### Epidemiology and biostatistics

**Structurally good at.** Distinguishing association from causation in
observational data, identifying and correcting for the ways a sample can fail to
represent a population, and designing surveillance that detects a change without
being swamped by noise.

**Named practices worth knowing.** Confounding, mediation, and collider bias, with
directed acyclic graphs as the tool for reasoning about which is which. Selection
bias, including the specific forms — Berkson's bias, immortal time bias,
survivorship bias. Case-control and nested case-control designs, which
deliberately over-sample rare outcomes and correct for it afterwards. The target
trial framework for emulating a randomised comparison from observational data.
Standardisation and reweighting to a reference population, including inverse
probability weighting and propensity scores. Sensitivity analysis and the E-value
as a formal statement of how strong an unmeasured confounder would need to be.
Capture-recapture for estimating what surveillance missed. Sentinel surveillance
and syndromic surveillance. The distinction between transportability and internal
validity, which is the cleanest available framing of "will this prior hold on that
population".

**Where to search.** *American Journal of Epidemiology*, *Epidemiology*,
*International Journal of Epidemiology*, *Statistics in Medicine*. Hernán and
Robins' *Causal Inference: What If* is freely available and is the standard
reference for the target trial and weighting machinery. STROBE and other reporting
checklists are useful as ready-made lists of the things that go wrong.

**Characteristic transfer failure.** Epidemiological methods require that the
confounding structure be **nameable**. Inverse probability weighting corrects for
the variables you measured and thought of; it does nothing for the ones you did
not. A card that promises to remove bias will in practice remove the bias you
could already enumerate, which is often not the bias that is hurting you. Also
watch for mechanisms that need a large sample to estimate a weight or a propensity
score, applied to a problem with dozens of items.

---

### Information retrieval and recommender systems

**Structurally good at.** Ranking a large candidate set against a query,
evaluating a ranking when the relevance labels are incomplete, and combining
several rankers whose scores are not on the same scale. This is the closest
foreign domain to any selection problem, which makes it both the highest-yield and
the easiest to over-fit to.

**Named practices worth knowing.** Reciprocal rank fusion and CombSUM/CombMNZ
score fusion, and the empirical finding that rank-based fusion is more robust than
score-based fusion when score distributions differ. Learning to rank, in its
pointwise, pairwise, and listwise forms, with LambdaMART as the standard strong
baseline. Pooled relevance judgements as used in TREC, and the bias that pooling
introduces against systems that were not in the pool. Normalised discounted
cumulative gain, mean reciprocal rank, and the reasons each is chosen. Cascade
ranking architectures with a cheap recall stage and an expensive precision stage.
Query expansion and pseudo-relevance feedback. Diversification of result lists,
including maximal marginal relevance. Counterfactual and off-policy evaluation
from logged interactions. Cold-start handling.

**Where to search.** SIGIR, CIKM, WSDM, ECIR, and RecSys proceedings; the *ACM
Transactions on Information Systems*. The TREC proceedings are a decades-long
record of what actually worked on shared tasks, including negative results, and
are unusually honest. Manning, Raghavan, and Schütze's *Introduction to
Information Retrieval* is freely available and names most of the classical
machinery.

**Characteristic transfer failure.** Retrieval mechanisms very often require
**partially independent errors across the systems being combined**, and this is
the single most commonly violated precondition in the whole map. Ensembles of
similar models trained on overlapping data have correlated errors, and fusion then
concentrates the shared error instead of cancelling it. In this project's
reference case, cross-model consensus over co-folding pose pools was *actively
harmful* for exactly this reason. A second failure mode: retrieval has many
queries and can tolerate being wrong on some, and its metrics average over them; a
problem where every item is scored and reported may not have that slack.

---

### Law and forensic science

**Structurally good at.** Deciding what counts as evidence, keeping a claim
attributable to its source across many hands, structuring an adversarial test of a
conclusion, and stating burdens of proof at different levels of certainty.

**Named practices worth knowing.** Chain of custody, and the specific idea that a
break in the chain invalidates the evidence regardless of whether the sample is
actually fine. Graduated standards of proof — the balance of probabilities, clear
and convincing evidence, beyond reasonable doubt — as a worked example of tiering
confidence to consequence. The hearsay rule and its exceptions, which is a
formalisation of when a second-hand report is admissible. Daubert and Frye
admissibility standards for expert method, which ask whether a method has a known
error rate and has been subjected to peer review. Blind and sequential-unmasking
protocols in forensic examination, introduced specifically because examiners were
found to be biased by contextual information. Likelihood ratios as the correct way
to report forensic evidence strength, and the prosecutor's fallacy as the standard
way of getting it wrong. Discovery and disclosure obligations, including the duty
to disclose exculpatory material. Redundant independent examination.

**Where to search.** *Science and Justice*, *Forensic Science International*, the
*Journal of Forensic Sciences*, and *Law, Probability and Risk*. The 2009 US
National Research Council report on forensic science and the later PCAST report on
feature-comparison methods are both substantial, freely discussed critiques that
enumerate failure modes explicitly. The Federal Rules of Evidence are short and
readable.

**Characteristic transfer failure.** Legal machinery is optimised for
**adjudicating a dispute between parties with opposed interests**, not for finding
the truth as cheaply as possible. Its procedures deliberately accept large
inefficiencies to guarantee fairness, and importing that cost without the
adversary produces bureaucracy. When a card from this domain survives, it is
usually about **provenance and attribution** rather than about procedure, and
those transfer very well — this project's `Evidence.locator` requirement, the
append-only decision ledger, and the checksum-plus-timestamp rule on materialised
data are all chain-of-custody mechanisms.

---

### Weather and climate forecasting

**Structurally good at.** Producing and evaluating probabilistic forecasts of a
single evolving system, running ensembles to represent uncertainty rather than to
improve a point estimate, and a mature vocabulary for what "well calibrated"
means.

**Named practices worth knowing.** Ensemble prediction with perturbed initial
conditions and with multiple models, and the distinction between the two purposes.
Model output statistics and post-processing to correct systematic model bias
against observations. Reliability diagrams and rank histograms for diagnosing
whether a stated probability matches the observed frequency, and whether an
ensemble is under- or over-dispersed. Proper scoring rules — the Brier score, the
continuous ranked probability score, the logarithmic score — and the decomposition
of a score into reliability, resolution, and uncertainty components. The Murphy
decomposition, which makes it explicit that calibration and discrimination are
separate and separately fixable. Anomaly correlation and skill scores measured
against a defined reference forecast such as climatology or persistence, rather
than in absolute terms. Nowcasting versus forecasting. Analogue forecasting.

**Where to search.** *Monthly Weather Review*, *Weather and Forecasting*,
*Quarterly Journal of the Royal Meteorological Society*, and the *Bulletin of the
American Meteorological Society*. ECMWF technical memoranda and newsletters are
freely available, unusually detailed, and are where operational practice is
documented. Jolliffe and Stephenson's *Forecast Verification* is the standard
reference for the verification machinery.

**Characteristic transfer failure.** Every verification mechanism in this domain
requires **many forecast-observation pairs**. Reliability diagrams need enough
cases to populate each probability bin, and a few dozen items will not do it. The
precondition to check is not "do we have outcomes" but "do we have enough outcomes
per bin", and it fails far more often than scouts expect. Second failure mode: the
skill-score framing requires an agreed reference forecast, and if we cannot name
our climatology we cannot use the machinery.

---

### Psychometrics and educational measurement

**Structurally good at.** Measuring a latent quantity from noisy graded
observations, separating the difficulty of an item from the ability of the
respondent, quantifying how much of a measurement is signal, and adaptively
choosing which observation to make next.

**Named practices worth knowing.** Item response theory, including the Rasch
model, and the joint estimation of item difficulty and respondent ability from an
incomplete crossing of the two. Item information functions and computerised
adaptive testing, which chooses the next item to maximise information about the
current estimate. Classical test theory reliability, and the way reliability
bounds the correlation any measurement can have with anything else. Generalisability
theory, which decomposes variance across facets such as item, rater, and occasion.
Differential item functioning, which detects items that behave differently across
subpopulations even at matched ability. Inter-rater agreement measured with
Cohen's or Fleiss' kappa, and the reasons raw agreement is misleading. Construct
validity, and the standard argument that a measure must be shown to relate to
other measures in the predicted pattern. Anchoring and equating across test forms.

**Where to search.** *Psychometrika*, *Journal of Educational Measurement*,
*Applied Psychological Measurement*, *Educational and Psychological Measurement*.
The *Standards for Educational and Psychological Testing* is the profession's
consensus document on what a defensible measurement claim requires. The R packages
for item response theory and their vignettes are practical entry points.

**Characteristic transfer failure.** Item response theory and its relatives need a
**graded observed response** — something that was right or wrong, or scored on a
scale — for each respondent-item pair. Self-reported confidence is not such a
response, because there is nothing to anchor it against. If the only thing our
"raters" emit is their own certainty, with no observed correctness, the latent
trait is unidentified and the whole apparatus produces numbers that mean nothing.
This failure is easy to miss because the data *shape* looks right: a full matrix of
scorers by items is exactly what item response theory consumes.

---

### Aviation and process safety

**Structurally good at.** Preventing rare catastrophic outcomes in a system where
a single mistake is unrecoverable, deciding in advance when to abandon an attempt,
and learning from incidents at an organisational rather than individual level.

**Named practices worth knowing.** Checklists, and the specific distinction
between a do-list and a read-and-verify list. Stabilised approach criteria and the
go-around: a pre-committed set of conditions that must all hold by a defined gate,
with an automatic and blameless abandon if they do not. The sterile cockpit rule.
Crew resource management, including the explicit obligation of a junior crew member
to challenge a senior one. The Swiss cheese model of accident causation, with
layered defences whose holes must align. Bow-tie analysis linking causes,
a top event, and consequences through barriers. Hazard and operability studies in
process engineering. Confidential, non-punitive incident reporting, of which the
NASA Aviation Safety Reporting System is the canonical instance, plus the
observation that reporting volume collapses when reports are punished. Safety
cases as an explicit written argument that a system is safe enough, with the
evidence attached. Normalisation of deviance.

**Where to search.** The NTSB and AAIB accident report archives, which are
detailed public documents that describe failures mechanistically and are among the
best available examples of causal writing. The FAA and EASA advisory material.
*Safety Science* and *Reliability Engineering and System Safety* for reviewed work.
Nancy Leveson's *Engineering a Safer World* and Sidney Dekker's field guides are
standard references. The Aviation Safety Reporting System database is searchable.

**Characteristic transfer failure.** This domain's mechanisms are calibrated to
outcomes that are **catastrophic and irreversible**, and they buy safety with
throughput. A go-around costs fuel and time and is worth it because the
alternative is a crash. If our failure mode is "one submission scores badly", the
mechanism is over-engineered and will slow us down more than it protects us. The
right question is whether the specific decision under discussion is genuinely
irreversible or merely expensive. Where it *is* irreversible — a submission slot
that cannot be recovered, a leaderboard that displays the most recent rather than
the best entry — these mechanisms transfer with unusual force.

---

### Databases, compilers, and systems performance

**Structurally good at.** Choosing a plan for a computation before running it,
estimating the cost of alternatives from cheap statistics, deciding what to compute
eagerly versus lazily, and locating the actual bottleneck in a multi-stage system
rather than the suspected one.

**Named practices worth knowing.** Cost-based query optimisation, with a cost
model over cardinality estimates, and the well-documented finding that errors in
cardinality estimates dominate optimiser quality. Adaptive and re-optimising
execution, which revises the plan when reality contradicts the estimate. Lazy
evaluation and materialisation policy, and the closely related predicate pushdown
— do the cheap filtering before the expensive operation. Memoisation and result
caching with explicit invalidation. Profiling before optimising, and Amdahl's law
as the formal statement of why optimising a small fraction is pointless. Canary
and blue-green deployment. Differential testing, where two implementations that
should agree are compared to find bugs in both. Property-based testing with
generated inputs and shrinking of failing cases. Fault injection and chaos
engineering. Bloom filters and other cheap probabilistic pre-filters that admit
false positives but never false negatives.

**Where to search.** SIGMOD, VLDB, and the *VLDB Journal*; PLDI and OSDI/SOSP for
compilers and systems. Engineering blogs from database vendors and large
infrastructure teams are the practitioner record and are frequently more specific
than the papers. *ACM Queue* is written for practitioners and names mechanisms
plainly.

**Characteristic transfer failure.** These mechanisms need a **cost model whose
inputs are cheap to estimate and roughly accurate**. Cost-based optimisation
degrades badly when estimates are wrong, and the degradation is not graceful. If
we cannot estimate the cost or the yield of a pipeline branch to within an order of
magnitude, a formal optimiser over those estimates is theatre. The related trap is
that a false-positive-only pre-filter, which is what a Bloom filter is, requires
that false positives be genuinely harmless downstream — check that, because in a
selection pipeline a false positive that reaches the final answer is not harmless.

---

### Experimental physics and astronomy

**Structurally good at.** Extracting a weak signal from a dominant background,
protecting an analysis from the experimenter's own expectations, and stating
systematic uncertainty separately from statistical uncertainty.

**Named practices worth knowing.** Blind analysis: fixing the entire analysis
procedure and cut selection on simulated or scrambled data before looking at the
real result, with unblinding as a one-time irreversible event. Look-elsewhere
correction for having searched many places. Matched filtering, and the general
principle that knowing the shape of the expected signal buys enormous sensitivity.
Control regions and sidebands used to constrain a background from data rather than
from theory. Systematic uncertainty budgets, itemised, with each entry traced to a
specific assumption. Injection-recovery tests, in which a synthetic signal of
known strength is inserted into real data and the pipeline's recovery is measured
end to end. Pre-registration of the analysis and of the discovery threshold.
Standard candles and the calibration ladder.

**Where to search.** The experiment collaborations' own technical notes and
public analysis documentation, which are unusually thorough about method. *Physical
Review D*, the *Astronomical Journal*, and *Monthly Notices of the Royal
Astronomical Society*. Cowan's *Statistical Data Analysis* and the Particle Data
Group's statistics review for the machinery.

**Characteristic transfer failure.** Blind analysis and its relatives require
either a **credible forward simulator** or a region of data known to contain no
signal. Injection-recovery in particular is only as good as the injected signal's
realism, and a synthetic item that differs from a real one in the way that matters
will certify a pipeline that then fails. Ask what the simulator is and where it is
known to be wrong. Where a simulator does exist, injection-recovery is one of the
highest-value mechanisms in this entire map, because it measures the pipeline
end to end rather than measuring components.

---

## Domains that reliably disappoint

Recorded so scouts are not sent there repeatedly.

- **Anything with no measurable outcome in its own domain.** If practitioners
  there cannot tell whether their practice works, `why_it_works_there` will be an
  assertion, and the card cannot be assessed. Art and design are partial
  exceptions, but only for their *process* practices, which have been tested
  elsewhere.
- **Domains whose central mechanism is an incentive.** Auction theory, mechanism
  design, and much of behavioural economics turn on aligning the interests of
  self-interested agents. Our pipeline has no self-interested agents, so these
  cards nearly always fail the precondition check at the same place.
- **Fields whose apparent affinity is purely lexical.** Anything selected because
  it uses the words folding, docking, binding, scoring, or selection in an
  unrelated technical sense. This is how metaphor mining happens.
- **Fields already inside our own citation network.** Machine learning generally,
  cheminformatics, and computational chemistry are not cross-domain scouting
  targets; searching them is `pipeline-space-scouting` and `literature-harvest`,
  and a "transferred" card from them is a prior-art search that was not done.

## Practical notes for running a fan-out

- **Two to four domains per gap.** Enough for a spread of shapes, few enough that
  every returned card gets a real precondition check.
- **Send the same restated gap to every scout, unmodified.** Divergent
  restatements make the returned cards incomparable, and comparability is what
  lets you notice that three domains independently proposed the same mechanism —
  which is the strongest signal this skill produces.
- **Record the domain even when the scout returns nothing.** A `Domain` node with
  no analogies attached documents that the field was searched, which stops a later
  run repeating it. The `ORIGINATES_IN` edge requirement in the graph contract
  means an `Analogy` node cannot exist without its `Domain` node anyway.
- **When two domains propose the same mechanism, that is convergent evidence about
  the mechanism, not about our problem.** It raises the prior that the mechanism is
  real and general. It does nothing whatsoever for the precondition check, and it
  never lifts the finding above `speculative`, because both sources are still
  `SourceType.ANALOGY`.
