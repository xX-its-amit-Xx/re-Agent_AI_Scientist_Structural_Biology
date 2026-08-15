# Why Stage 0 comes first

The objection is reasonable and you should hear it properly before it is answered.
A challenge has a deadline. Every hour spent reading is an hour not spent building,
the state of the art is knowable from a couple of papers, and the fastest way to
learn what works is to run something and look at the number. Reading is what people
do when they are avoiding the hard part.

The trouble is that this argument assumes the hard part is *building*. In the one
pipeline this project has reverse-engineered end to end, it was not. The hard part
was knowing which of the fifteen things worth building would move the metric, and
that was decidable from evidence before any of them existed.

## The winning idea was architectural, and it was cheap to have

The reference case is a rank-2 of about 50 entry in the OpenADMET PXR blind
structure-prediction challenge, at 0.5640 LDDT-PLI. What produced that score was
not a better predictor. It was three architectural decisions.

Six co-folding models were run to widen the candidate pool, and the pool's
best-achievable result was about 1.08 Å median RMSD, far better than any single
model realised on its own. Then each model's candidates were ranked by that model's
own native confidence, and those confidences were z-scored *within* each model
before being compared across models, because raw confidence scales from different
models are not commensurable. That single change moved the score from 0.4996 to
0.5472 — larger than the entire gap between second place and first. Finally, the
eight lowest-confidence ligands were overwritten with a seventh model's poses,
taking 0.5472 to 0.5640, with one rescue going from 0.123 to 0.919. Swapping twenty
instead of eight scored 0.5587, which is worse; the failure tail was real but
small.

Every one of those three decisions is a statement about the *structure* of the
problem: that generation was not the bottleneck, that confidence scales are
incomparable across models, and that a minority of items fail for reasons a
different generator does not share. None of them required running anything to
formulate. All of them were the kind of thing a scouting pass produces.

And the negative half of that landscape was worth more still. With a fixed pool and
no ground truth to train on, *every* learned, agentic, or consensus selector
regressed against the plain z-scored argmax. Consensus was actively harmful, because
models that agree share correlated errors. A learned pose scorer — an XGBoost
LambdaMART model over 37 features, trained on 35 to 53 ground-truth complexes —
scored 0.4762 and ranked 32nd, the project's worst submission. An independent
literature review inside that same repository had reached the same conclusion
*before* the experiments confirmed it: on co-folding pose pools, native-confidence
ranking and cross-model consensus largely do not beat random. The reading was
available. It was simply done after the building.

That is the shape of the argument. Not "read before you build" as a virtue, but:
the specific thing that won was findable by reading, and several of the things that
lost were pre-announced by the same reading.

## What building first actually cost, in that run

The authors' own retrospective names four things they would do differently, and
three of them are Stage 0 in disguise.

They would **codify the pre-flight submission gate by iteration 2 rather than
iteration 3**. Eleven submission slots were wasted, eight of which a divergence
gate would have caught. That gate is not complicated: reject any candidate whose
predictions diverge from the incumbent by less than 5%, because the difference is
sub-noise and the slot is wasted, or by more than 30%, because every candidate
above that band — at 94.6%, 99.5%, 95.7%, 88.6%, and 86.4% divergence — scored below
0.47. Submissions came at roughly one per four hours. Eleven of them is a day and a
half of the competition, spent to learn something a pre-registered rule stated in
advance.

They would **stop sinking time into external compute**. Eighty hours went into
external notebook and cluster attempts, and zero of eight produced a submittable
output. The reason is structural rather than bad luck: those resources had roughly a
twelve-week activation lag against a thirty-day window. That is a fact about
infrastructure availability, knowable on day one from the same kind of search that
tells you which model checkpoints are downloadable, and it would have redirected
eighty hours into the parts of the pipeline that were actually reachable.

They would **build the expanded validation set earlier**. Growing it from 35 to 53
ground-truth complexes turned out to be an overfit detector: every method gained
about +0.020 on the easier set except pLDDT-based selection, which gained +0.0015
and fell from first to last. Failing to improve when the task gets easier is the
signature of an overfit, and that diagnostic only existed once the validation set
was large enough to have two regimes.

And they would **spend 70% of ideation on the test-set distribution rather than on
methods**. That is the retrospective's own number, and it is the strongest single
statement of what this project's Stage 0 and Stage 1 are for. In that challenge the
test set was 76 crystallographic fragments and 108 drug-like analogs, per-model
scores were roughly 0.46 on the drug-like half against 0.55 to 0.57 on the fragments,
and the fragments had Morgan-r2 Tanimoto below 0.3 to *every* known holo ligand for
the target. Any signal trained on the drug-like half inverted sign on the fragments
— confirmed four times independently, with four different model families. A team
that characterises its test distribution first designs two pipelines. A team that
starts building designs one and discovers the other half the hard way.

## What Stage 0 costs

It costs literature and web access, and nothing else. Stage 0 spends **zero metered
credits** — no Boltz, no Modal, no Tamarind, no AlphaFold3 server time — and this is
a guard rail rather than a habit: the orchestrator estimates cost, writes it into a
proposal, and lets a human approve before Stage 3 burns anything. Stages 0 through 2
are free by construction.

What it does consume is agent time, which is bounded by the fan-out caps (six to
eight concurrent scouts per batch, one per evidence modality or foreign domain), and
one human sitting to read a triage sheet. Against that, set the eleven submission
slots, the eighty hours, and the fourteen development hours saved by a single
pre-registered rejection rule — where the team had committed *in advance* that if a
cheap strain-based signal failed local validation, an expensive follow-on project
was cancelled unbuilt. It failed, and the follow-on died without a further argument.
That is what `Proposal.kill_criterion` being a required field is for: pre-register
the consequence, not just the test.

The honest version of the trade is that Stage 0 does not save time in the first
day. It saves the third week, and it does so by removing work rather than by doing
it faster.

## Stage 0 has two halves and they are not the same activity

The first half, `pipeline-space-scouting`, maps what the field has already done. It
scouts the **problem class**, not the instance, because almost everything useful
about blind co-folding was learned on targets other than the one in front of you.
It separates what is *published* from what is *used*, since papers report bests and
practitioners report defaults, and a method that wins benchmarks but nobody runs is
a signal about cost or fragility. It hunts failure modes explicitly, in limitations
sections, GitHub issues, challenge post-mortems, and the gap between a paper's
benchmark and its leaderboard number, because failure modes are systematically
under-published. And it fixes three numbers: the trivial baseline, the current best,
and the ceiling an oracle would reach over the same candidate pool. The gap between
the first two is the headroom; the gap between the last two tells you whether to
spend the project on generation or on selection, and that one distinction
reorganises the entire pipeline. In the reference case the oracle over the pool was
about 1.08 Å while realised performance was far worse, which said unambiguously:
this is a selection problem, spend everything on the selector.

It also scouts the boring mechanics, because they decide real leaderboards. In that
challenge, a ligand whose parsed connectivity did not match the expected structure
scored zero and took a 20 Å penalty; the fix was injecting CONECT records into all
184 submitted files so the scoring server inferred bonds from topology rather than
geometry. And the leaderboard displayed each team's *most recent* submission rather
than its best, which destroyed three competitors' standings — the worst going from
0.5521 to 0.4727 and from rank 2 to rank 18. None of that is science. All of it is
score, and all of it is findable by reading before you build.

The second half, `cross-domain-analogy`, does something different in kind. The
in-field literature bounds what the field already believes, so going past it
requires a prior from somewhere else: another discipline, a patent, a trade
practice. This half takes the *open gaps* the first half produced — the questions
the in-field literature does not answer — restates each one structurally with the
domain vocabulary stripped out, and sends scouts into fields chosen for structural
affinity to that restatement rather than for novelty. Ranking under uncertainty and
ensemble construction live in quantitative finance. Detection under base-rate
imbalance and adversarial validation live in cybersecurity. Evaluation without
complete labels lives in information retrieval. Small-sample evaluation lives in
sport analytics.

The ordering between the halves is not decorative. Run analogy first and the scouts
free-associate, because they have no gap to search against; you get forty puns
instead of five checkable mechanisms.

## Why the second half needs a human gate

Because the failure mode of creative search is confident nonsense, and the contracts
can only catch some of it.

What the contracts *can* enforce, they do. A cross-domain finding is
`SourceType.ANALOGY`, it must name its `source_domain`, and it can never raise a
finding above `speculative` on its own — an analogy is a reason to run an
experiment, never a result. An `AnalogyCard` whose mechanism merely restates the
source practice is rejected, which is what stops "proteins fold, origami folds" from
entering the system. Every `Analogy` node must carry an `ORIGINATES_IN` edge to the
`Domain` it came from, so creative provenance stays permanently auditable: six
months later you can ask why the pipeline has a particular routing layer and trace
it to a card, a decision, and a person.

What no validator can decide is the only question that matters: **does our problem
actually have the structure this mechanism requires?** `structural_precondition` is
a prose claim about the world, and checking it means holding the mechanism against
this specific problem's evidence. The reference case supplies the exact illustration.
A rank-fusion card from information retrieval is a genuinely good card — the
mechanism is real, the citations are real, and it names its own fragile clause,
which is that the scorers' errors must be at least partly independent. In this
problem that clause failed: consensus across co-folding models was actively harmful
*because* agreeing models share correlated errors. Nothing in the card is wrong.
Nothing in the schema catches it. Only someone holding the card against the problem
catches it, and a 70% discard rate at that step is healthy rather than wasteful.

The second reason for the gate is that unsupervised agents produce physically
confident garbage. In the reference case an agentic ligand-redrawing attempt took
one complex from 3.88 Å to 24.63 Å — the agent generated a pose that was chemically
narratable and physically absurd. That is the strongest available argument for why an
AI scientist proposes and a human disposes, and it is why the orchestrator checks
`reagent decisions <proposal-id>` rather than the conversation before executing
anything creative. The ledger is the authority, it is append-only, and changing your
mind means appending a superseding entry rather than editing the old one — the trail
of reversals is itself evidence about the pipeline.

The third reason is simply that cost and irreversibility are human calls. A proposal
carries an effort estimate, a dollar estimate, the credit pools it would consume,
and whether adopting it forecloses other options. The triage sheet orders proposals
cheapest-and-most-reversible first because that is the order a person can actually
act on. Deciding that a $200 irreversible commitment is worth it is not a decision a
contract can make.

## What a Stage 0 pass must produce before Stage 1 starts

A Stage 0 pass is done when all of the following exist and not before:

- A one-sentence framing of the form *given these inputs, predict this output,
  scored by this metric, where this is withheld* — and the named problem class it
  belongs to, which is what you actually scouted.
- A `Metric` in the `ProblemSpec` with a definition precise enough to reimplement,
  its evaluation set named, and its known caveats populated. If the metric is
  unstated, Stage 0 has not finished, and everything downstream would optimise
  against a guess.
- A characterisation of the test items, including their subpopulations and the
  statistic that separates them. If the distribution is bimodal, that must be stated
  loudly, because one pipeline will not serve both halves.
- The three numbers: trivial baseline, current best, and the oracle ceiling over an
  achievable candidate pool — each with its evaluation set, since a number without
  one is uncomparable. Plus the explicit verdict they imply: is this a generation
  problem or a selection problem?
- A method landscape written as a decision tree over the problem's structure,
  ending on "therefore we are on branch X". Twenty methods with no branch structure
  is a reading list, not scouting.
- A failure-mode catalogue: mode, which methods suffer it, observable symptom,
  known mitigations, residual risk, sorted by how much of the metric it costs. This
  is the table Stage 3 designs against.
- The mechanical output constraints as `FindingKind.CONSTRAINT` findings — file
  format, naming, validators, scoring-server behaviour — because these have decided
  real leaderboards.
- Negative results recorded as `FindingKind.NEGATIVE` findings and `FAILS_ON` edges.
  A stage that reports only wins is under-reporting, and this is the material the
  literature omits.
- `Method` and `PipelineStep` nodes in the graph, each with a `SUPPORTED_BY` edge to
  a `Paper` node. An uncited method node is a bug.
- A `handoff.payload` carrying `recommended_architecture`, `candidate_methods`,
  `must_beat`, `failure_modes`, and `open_gaps` — and the `open_gaps` list is
  load-bearing, since it is the input `cross-domain-analogy` needs.
- A `ProposalSet` where every proposal names what it mutates, predicts something
  falsifiable, states a kill criterion and the metric that decides it, and carries a
  cost; every transferred proposal ships its `AnalogyCard` alongside.
- Recorded verdicts in `decisions/ledger.jsonl` for every proposal you intend to
  act on, each attributable to a named person, and each with a rationale.
- A validated `Stage.SCOUTING` `ModelReport` that passes
  `reagent report validate --strict`, which means it also has its characteristic
  figures — a decision tree of the pipeline-space branch you are on, and a ranked
  bar of the candidates — a figure for every headline metric, a handoff, and
  populated limitations.

If that list looks long, note what is *not* on it: a single line of pipeline code, a
single metered credit, and a single prediction. Stage 0 is where the architecture
gets chosen, and choosing it is the highest-leverage thing available in the whole
run.
