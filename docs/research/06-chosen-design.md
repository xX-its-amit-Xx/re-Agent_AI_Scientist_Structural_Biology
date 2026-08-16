# The chosen design

**A stigmergic blackboard over a provenanced knowledge graph, with a hand-authored
pipeline skeleton, grounded verification as the admission gate, and a single writer per
register.**

In the enumeration's terms: a compound organisation (T42) whose constituents are
**T29 skeleton + T5 fan-out + T18/T17 shared-artifact coordination + T21/T48 write
semantics + T25 grounded verification + T16 tournament ranking + single-writer synthesis**,
carried on a **T20 typed-state / T31 actor** implementation.

## The one-sentence justification

Every other topology asks agents to *agree*; this one arranges for them to be **unable to
see each other**, and then adjudicates their disagreements against sources — because the
measured evidence is that visibility between agents correlates their errors and discussion
makes aggregation worse, not better.

## The pipeline

**Stage A — Harvest.** A deterministic dispatcher fans out stateless retrieval workers
(T5 + T4), one per source or query facet. Each returns structured candidate records, never
prose. Operate deliberately at high recall and low precision, because that is the correct
operating point when a verification filter follows.

**Stop by coverage, not by confidence.** Fit an exponential discovery curve online and stop
on saturation; estimate absolute coverage by two-source capture–recapture against an
independent search method; report **WSS@95**. Never use model self-confidence as the
stopping signal — models conform most when uncertain.

Cajal asked this exact question in 1897 and his answer is the one we implement: exhaust the
bibliography where you can, so that you do not neglect *"las verdaderas lagunas del tema"*,
the real gaps; but where you cannot, proceed anyway, because *"it is worth a thousand times
more to risk repeating discoveries than to renounce all attempt at experimental inquiry."*

**Stage B — Extract. This is the load-bearing decision.** Schema-forced extraction workers,
each of which sees **only its own source document and the schema**. No worker sees any other
worker's output. No worker sees the graph's unverified layer.

That single restriction is where independence comes from, and it is why this stage is worth
more than the rest of the architecture combined.

Emit **claims with context, not bare triples**, with **negation and hedging as required
fields** — a documented blind spot of existing extraction systems. Ground every entity to an
identifier (97–100 % grounding accuracy with schema forcing, against 3 % raw). Attach
**span-level anchors**. Write to a **staging area, never directly to the main graph**. Apply
merge-on-write to suppress the redundant-work failure that was measured on real blackboard
systems.

And calibrate trust asymmetrically: **trust nodes far more than edges.** Relation extraction
sits around F 0.44 with recall near 0.3, and most errors are in the predicate rather than
the entity.

**Stage C — Verify and admit.** A grounded verifier gates admission by asking one question:
*does the cited span support this claim?* This is the single critique pattern with robust
positive evidence, and it has an operating point in our exact setting — 70.0 % support found
for real edges, **83.4 % of injected false edges correctly rejected**.

Label every admitted claim epistemically — supported, refuted, underpowered, invalid —
because in science "not tested" and "not significant" are different facts and collapsing
them is a category error every downstream stage inherits.

**Run contradiction detection before or atomically with near-duplicate suppression.** A dedup
gate placed first was observed silently discarding contradictory writes before the
contradiction detector could see them. Those disagreements are the most valuable content in
the graph.

**Stage D — Resolve and link.** Entity resolution as an explicit stage, not a side effect.
Append-only with **temporal supersession** — never overwrite a claim, supersede it and keep
the lineage. This is Luhmann's discipline, and his reason holds: errors are "revised by later
entries but not eliminated". A signed append-only log (T48) for the certified layer.

**Stage E — Critique and prioritise.** Rank by Elo tournament with non-destructive evolution
(T16): new candidates compete, they do not replace. This is the compute-allocation dial.

Invoke debate in **exactly one** situation: two source-privileged extractors genuinely
conflict, and a judge *without* source access adjudicates (T15). Never debate to "improve
reasoning".

**Stage F — Synthesise and explain.** One writer over the certified subgraph. **Do not
parallelise writing** — parallel section-writing produces disjoint reports.

Our multi-register requirement is met by **multiple independent single-writer passes over the
same certified subgraph**, each re-citing from the graph, rather than by one pass plus
rewrites. Every register is then independently auditable and the levels cannot silently
drift apart.

**Control discipline throughout.** Keep the orchestrator **deliberately stupid** — a
deterministic dispatcher over a work queue, plus a two-ledger progress record (facts
partitioned into verified / to-look-up / to-derive / **educated guesses**, and a progress
ledger with a stall counter). Removing those ledgers cost 31 % in the system where they were
measured. Subagent returns capped at structured output, never raw transcripts: selective
shared memory scored 96 % task completion against **71 % for passing full history.** Every
compaction emits a derivation edge to what it replaced, or the audit trail dies at the first
compaction boundary.

## Why this rather than the runner-up

**It is the only topology that gets independence by construction.** Deliberation does not
merely fail to add accuracy — it destroys correct answers that a cheaper aggregation would
have kept. Debate degraded majority-vote accuracy in **10 of 10** model configurations on
CommonsenseQA, worst case −12.0 points (Wynn, Satija & Hadfield, ICML MAS Workshop 2025,
arXiv:2509.05396). In up to **86.36%** of cases where an agent started with the correct
answer, debate never reached it, and the rate of abandoning a correct position correlates with
a sycophancy score at **r = 0.902** (Yao et al., arXiv:2509.23055). Votes are never
independent in either regime: **92.36%** capitulation to a stronger peer, versus a **~47/53
coin flip** between comparable models (Xiong et al., Findings of EMNLP 2023, arXiv:2305.11595).
Frontier models average **47.2%** conformity under induced self-doubt, and it is removing the
*last dissenting peer* that causes the jump — 32.6% → 69.9% (Weng, Chen & Wang, ICLR 2025,
arXiv:2501.13381). Cross-family heterogeneity bought **+0.07 points** at a strong-prompt
operating point: 6 agents across 3 model families scored 78.66 against a best single agent's
78.59 (Wang et al., ACL 2024, Table 3). Personas do not help — 162 roles across four model
families and 2,410 questions produced no improvement (Zheng et al., Findings of EMNLP 2024,
arXiv:2311.10054), though note that paper measures single-agent accuracy and not error
correlation, so "personas do not decorrelate" remains an extrapolation from it.

Prompt discipline cannot fix a structural problem. Structural blindness can.

> **This paragraph was rewritten after an audit.** It previously rested on four figures —
> 0.43–0.44 of the independence gain, r ≈ 0.77, 0.68 → 0.40, and 83.43% versus 76.11% — **none
> of which could be sourced, and one of which meant the opposite of the claim.** See
> [`00-provenance-audit.md`](00-provenance-audit.md) C2. The conclusion did not change; it was
> resting on the weakest props available to it.

**It is the only topology that gets provenance by construction.** The spread across
architectures is 19 attributability points, retrofitting recovers less than half, and
**citation precision correlates with perceived utility at r = −0.96** — the objectives are
measurably opposed, so provenance must be the write format rather than a later stage.

**It exploits the one structural advantage our problem has.** Almost every multi-agent
negative result reduces to "no sound verifier". We have one nearly free: the source text.

**The one head-to-head measurement favours it** — blackboard 37.53 % against master-slave
32.16 % — and the stated reason is the one that matters at scale: the coordinator stops
needing to know every worker's capabilities.

**Its cost profile is the best available.** Passing refined artifacts rather than dialogue
turns quadratic context growth into linear; structured returns compress worker output by an
order of magnitude or more; sparse coordination costs 29–53 % less than dense at
equal-or-better accuracy.

**The runner-up** is orchestrator–worker with synchronous subagents and structured returns
(T8 + T11 + T5), with the graph as a write-only sink. It is the best-documented topology in
existence, wins decisively on citation association, and could be built in weeks. It is second
because it is master-slave — inheriting the limitation the blackboard measurement beats — and
because the graph becomes a by-product rather than the substrate, which is precisely where
provenance-by-construction comes from.

**If we build the runner-up first, three things come along regardless**, because none is
topology-dependent: schema-forced extraction with grounding and span anchors, a grounded
verification gate, and single-writer synthesis.

## What this changes about what is already built

Most of the existing scaffold survives, and two things do not.

**Confirmed by the research, already implemented.** The `Evidence` locator requirement and
line-level anchoring is Locke's edition-fingerprint-plus-locus, in 1686 form. Append-only
JSONL with supersession is Luhmann's discipline. `FindingKind.NEGATIVE` is Faraday's
paragraph-addressed failure record — and his 1845 retrieval of a 1821 failure *by paragraph
number* is the best documented evidence that this pays. The `illustrative: true` flag is
Boyle's circumstantial reporting. `Proposal.kill_criterion` is a registered report.
`AnalogyCard.structural_precondition` is Gentner's structure-mapping requirement, which the
analogical-transfer literature says is exactly the thing that determines whether transfer
works.

**Change 1: the cross-domain analogy engine must not use an assigned critic.** Its current
design has scouts proposing and a review step disposing. The evidence is unambiguous that
**assigned dissent produces cognitive bolstering of the initial view** — it makes the
proposer more confident — and that authentic minority dissent from a genuinely different
position is superior to all forms of devil's advocate. The fix is to decorrelate the critic
by *model and corpus*, not by prompt: the agent that challenges a proposal should be reading
different sources than the agent that made it.

**Change 2, and this one is uncomfortable: the interpretive layer I just built is at risk of
being exactly the thing the evidence says fails.** Three findings converge on it.

Roscoe & Chi (2007) found that explainers exhibit *"a pervasive knowledge-telling bias… even
when trained, focus more on delivering knowledge rather than developing it"* — so an
explain-significance stage will default to fluent restatement unless the task structure
forbids it. An LLM judge preferred the *worse* chemistry system on fluency grounds. And
citation precision correlates with perceived utility at r = −0.96.

**Together those say: a well-written explanation is weak evidence of understanding, and
optimising for readability actively trades against attributability.**

Three specific consequences, all implementable:

- **Adopt Feynman's actual test, which is mechanical.** Not "explain it simply" but *"without
  using the new word which you have just learned, rephrase what you have just learned in your
  own language"* — **jargon ablation**. Our `undefined_jargon` check is already half of this;
  the other half is scoring the restatement for *mechanism* rather than fluency.
- **Require knowledge-building, not knowledge-telling.** An interpretation should have to
  state a prediction, a boundary condition, or a reconciliation. An explanation fully entailed
  by the retrieved text has demonstrated nothing. This is what `Implication.if_wrong` and
  `mechanism` are for, and they should be checked against that standard rather than for
  presence.
- **Do not treat the rendered graph as the intervention.** Nesbit & Adesope's 2010 review is
  direct: constructing concept maps beat texts and outlines, but **studying pre-built maps
  showed no detectable effect.** Our headline deliverable is a graph handed to a reader, which
  is the arm of that comparison that did not work. The interactive MCP path — where the reader
  *queries*, *compares*, and *traverses* — is doing the work here, not the static figure. That
  is an argument for weighting the MCP over the report render, and it inverts my earlier
  emphasis.

**Change 3: the popularity-lock-in risk needs a counter-force, not a note.** Stigmergy in
scholarly recommenders is documented to produce a *tyranny of popularity*. A graph that
decides what to read next by looking at itself converges on the literature's existing hubs.
Three mitigations, all cheap: sample exploration paths with **randomised waypoints rather
than shortest paths**; hold a **non-negotiable exploration quota** of harvest budget spent on
low-degree regions; and **decay unverified nodes** so unsupported material cannot accumulate
into a false hub. This is the pheromone-evaporation lesson — the amplification that produces
coordination also produces premature convergence, and it requires an explicit counter-force
by design.

And Uzzi's finding sets the target ratio: the highest-impact work is a **conventional core
with an atypical tail**, roughly doubling the odds of high impact. Not maximised novelty.
That ratio should be a tunable parameter, not an emergent property.

## The build order

The evidence does not support jumping to the ambitious architecture. Cost differs by nearly
two orders of magnitude at similar accuracy; agent benchmarks are pervasively
non-reproducible; a temperature-warming retry loop matches elaborate scaffolds on HumanEval —
*"'State-of-the-art' agent architectures for HumanEval do not outperform simple baselines"*
(Kapoor, Stroebl, Siegel, Nadgir & Narayanan, arXiv:2407.01502), who also note that nobody
compares against retry, warming or escalation baselines at all.

**Verification comes first, and this is a change from the earlier ordering.** It was step 4.
The evidence for it is now the strongest in the folder: a dedicated **Inspector agent recovered
up to 96.4%** of the errors introduced by a faulty agent, out-performing every topology change
the authors measured (Huang et al., arXiv:2408.00989), and MAST's largest single intervention
gain was **+15.6% from adding an objective-verification step** (Cemri et al., arXiv:2503.13657
v3). MAST's whole verification category — incorrect verification 9.10%, no or incomplete
verification 8.20%, premature termination 6.20% — is verification failure. Nothing in topology
buys returns of that size.

1. **Adopt the schema, verification, provenance and stopping machinery first.** None of it is
   topology-dependent, all of it is where defensibility comes from, and it is where the
   measured returns are largest.
2. **Build T1 and T8, instrument them, and make them the baseline that must be beaten.**
3. **Migrate the extraction stage only** to the stigmergic blackboard, because that is where
   independence and provenance are won. Measure.
4. **Migrate remaining coordination only if the measurement justifies it.**

> **The gain-decomposition claim was withdrawn.** This section previously asserted *"roughly
> 6 points from prompts, 3 from topology, 2 from workflow prompts — architecture is about a
> quarter of the story."* Unsourced; see [`00-provenance-audit.md`](00-provenance-audit.md) C7.
> The real picture is messier and points the same way: on one system a prompt change gave
> **+5.0 points (significant)** while a topology change gave **+0.75 (Wilcoxon p = 0.4, not
> significant)**; on another, topology (+15.6) beat prompts (+9.4). Measured on failure-mode
> counts rather than task success, MAST concludes topology changes are the more effective of
> the two. **Which lever dominates depends on the system and the backbone, and neither
> reliably wins** — so do not lead with topology, but do not claim a ratio either.
>
> The extreme case: tuning one prompt parameter — how strongly agents are told to agree —
> moved a debate protocol **from worst to best performing** (Smit et al., ICML 2024,
> arXiv:2311.17371), which means published debate results are not really measuring debate.

## What to instrument

Deliberately *not* aggregate answer quality — that is the metric correlating at −0.96 with
citation precision.

- **per-claim source support rate**
- **false-edge rejection rate** against a deliberately injected negative set; 83.4 % is the
  reference point
- **coverage** against a capture–recapture estimate, and **WSS@95**
- **cost per certified claim**
- **pairwise error correlation between workers** — the number that tells us whether the
  independence discipline is actually holding, and which nobody in the multi-agent literature
  measures
- **DCR, the oracle gap** — the fraction of items where *some* worker had it right and the
  system did not output it. Borrowed from Yao et al. (arXiv:2509.23055), where it reached
  86.36% for decentralised debate. More actionable than error correlation because it names a
  specific recoverable loss rather than a property of a distribution, and it is the same
  quantity `neglected-literature` measures one level up: the difference between what was
  findable and what was reported.
- **step repetition and termination-unawareness rates.** Together **28.1%** of measured
  multi-agent failures (15.7% and 12.4%, MAST v3) and previously unaddressed here. The fixes
  are an idempotency rule keyed on the work item and a hard per-worker step budget — the
  latter now enforced by `AxisSweep`'s round accounting.

The last three are the diagnostics that distinguish this design from a story about this
design.

Worth claiming explicitly: **schema-forced extraction eliminates a whole failure category by
construction.** MASLab found **79.66%** of one framework's failures on GPQA-Diamond were format
errors rather than wrong answers (Ye et al., arXiv:2505.16988). That is free here. The
countervailing cost is field order — see `reagent.contracts.ordering`, which pins reasoning
fields before conclusion fields because generation order is where schema forcing *does* cost
accuracy.

## Conditions that should make us revisit

- If **pairwise worker error correlation stays high** despite the isolation discipline, the
  structural argument has failed and the blackboard is buying nothing over T8.
- If the **verifier's false-edge rejection rate falls below roughly 0.7**, verification is no
  longer a sound gate and the whole admission model needs rethinking, since the design assumes
  the verifier is the reliable component.
- If **the exploration quota consistently produces nothing usable**, the lock-in mitigation
  is pure cost and should be reduced rather than defended.
- If the **problem becomes well understood and stops changing**, Erman's warning applies
  directly: a blackboard is scaffolding, and *"once developed and understood, the application
  can be reimplemented without the blackboard structure."* At that point the correct move is
  to collapse to T8 or T29 and delete the machinery.

## Honest risks

**The topology is close to unvalidated for LLM agents.** Stigmergic coordination has almost
no LLM-era literature. The defence is that the architecture decomposes into components that
are each independently measured — retrieve-then-read, schema-forced grounding, source-grounded
edge verification, blackboard coordination, structured returns, single-writer synthesis. We
are assembling measured parts, not betting on an unmeasured whole. That should be stated
plainly rather than glossed.

**The shared medium is a shared attack surface.** Poisoned content persisted beyond its
originating conversation in 40.5 % of one test set, and injected content hijacked importance
scoring to raise its own retrieval scores. Compromised agents are invisible to capability
benchmarks. Mitigation: scoped writes with recorded writer identity, a hard partition between
draft and certified layers, and monitoring at the claim level rather than the aggregate score.

**Relation extraction is the weak link and will remain so.** F ≈ 0.44, recall ≈ 0.3, most
errors in the predicate. Every downstream consumer must treat edges as *claims with
confidence*, never as facts — which the contracts already enforce, and which is now
justified rather than merely cautious.

**Blackboard control complexity is the classical failure.** The mitigation is licensed by the
measurement: the centralised meta-controller was *not* the bottleneck; contention and
redundant work were. So keep control dumb and deterministic, engineer merge-on-write and
duplicate suppression, and spend the model budget on extraction and verification rather than
on scheduling.

**And the selection-on-the-dependent-variable caveat applies to the whole exercise.** The
organisational literature studied survivors. Janelia was built by intersecting the features
of three successes; the failures sharing those features were never counted. Two of the three
canonical laboratories were monopoly-funded. This design is informed by that record, not
validated by it.
