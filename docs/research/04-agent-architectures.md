# Multi-agent architectures: the classical record and the LLM-era evidence

Findings are labelled **[ROBUST]** (multiple independent groups, or analytically forced),
**[SINGLE]** (one paper, unreplicated), or **[VENDOR]** (author has a commercial interest).

## The unifying thesis

Every classical coordination architecture **relocates** the hard design problem rather
than removing it — and each one's primary source says so.

| Architecture | Where the difficulty moves to | The source's own words |
|---|---|---|
| Blackboard | knowledge-source interest specification and shared-representation design | "difficult and computationally inefficient"; the representational balance is "an important aspect of blackboard-application engineering" (Corkill) |
| Contract Net | message slot *content* | "it remains the difficult task of the user to specify the actual content of the slot" (Smith) |
| HTN | the method library | "domain-configurable, in contrast to domain-independent" (Nau) |
| Subsumption | layer decomposition and fixed wiring | layers are "prisoners of their fixed topology connections" (Brooks) |
| Stigmergy | the medium itself | the entire environment-for-MAS research programme exists for this reason |
| Markets | utility estimation | noise "will necessarily limit the efficiency with which coordination can be achieved" (Gerkey & Matarić) |
| Society of Mind | everything | no algorithms, no formalism, no evaluation |

**Whichever topology you choose, the schema is the algorithm.** That is the design brief.

## Corrections to the received account

**The blackboard "central scheduler bottleneck" is the opposite of what was measured
[ROBUST].** Decker, Garvey, Humphrey & Lesser (IJCAI-91) ran blackboard control on a
16-processor machine and found: *"Centralizing the meta-controller that is implemented by
control KSs proved not to be a bottleneck."* The measured problems were **access collisions
and lock contention** on blackboard regions, and **redundant work** — near-identically
rated knowledge sources racing to produce the same result, requiring merge-on-write. They
also report a negative result on porting sequential heuristics to parallel hardware: *"We
did not get as much speedup over the experiment without parallel heuristics as we had
hoped."* So a *dumb centralised dispatcher over a shared artifact* is empirically
defensible; merge-on-write and duplicate suppression are what need engineering.

**Why blackboards actually fell out of favour is not a performance argument.** Corkill
(1991) reports Erman's own conjecture: *"The advantages of blackboard systems do not scale
down to simple problems… A blackboard system is useful for prototyping an application, but,
once developed and understood, the application can be reimplemented without the blackboard
structure."* The remaining reasons are tooling: no frameworks, and every application built
from scratch including the machinery. **The honest verdict is that a blackboard is
scaffolding you can throw away once the problem is understood, and it earns its keep while
the problem is still ill-defined.**

**Blackboard control is already a bidding mechanism.** Corkill: the scheduler *"must be
able to ask for estimates from triggered KSs"*, and each reports, without doing the work,
*"If I am executed, I'll generate contributions of this type, with these qualities, while
expending these resources."* Blackboard scheduling and Contract Net are the same mechanism
differing in who initiates. Corkill also confirms the property that makes it attractive
for heterogeneous LLM workers — a knowledge source is a black box: *"It does not matter if
one KS is a forward-chaining rule-based system, another uses a neural network approach."*
And two design points worth carrying: the blackboard **permits inconsistency by design**
("incompatible alternatives… each available for opportunistic exploration"), and the level
structure exists for **retrieval efficiency**, not elegance ("A specialist should not have
to scan the entire blackboard").

**The cooperative-agent literature defined itself out of the incentive problem.** Smith &
Davis (1981): *"cooperation is viewed in terms of benevolent problem-solving behavior…
rather than frameworks for enforcing cooperation."* The modern twist: **LLM agents are
neither reliably benevolent nor rationally self-interested**, so neither classical
framework fits, which is why incentive compatibility is being reintroduced and why LLM
collusion in double auctions is now measurable.

## Classical architectures, precisely

**Contract Net** is richer than the four-phase caricature: **directed award** (skip
negotiation when the manager knows the right node), **node-available** messages that
*reverse* the protocol under load, interim reports, and refusal-with-justification driving
adaptive re-announcement. Its four announcement slots — task abstraction, eligibility
specification, bid specification, expiration — are each justified by message-volume
reduction. **Smith's own scope limit is the sentence to quote against over-application:**
the protocol suits problems decomposable *"into a set of relatively independent subtasks
with little need for global information or synchronization."* Interdependent tasks are out
of scope by the author's admission — which is exactly where current LLM systems fail. Two
further primary admissions: slot *content* is the user's problem, and value is assumed
**one-dimensional**, which is the cleanest classical citation for the "you must reduce
heterogeneous value to a scalar" critique that also afflicts LLM agent scoring.

**Subsumption**, exactly: **suppression** taps the *input* side and is *substitutive*;
**inhibition** taps the *output* side and is *purely blocking*. Both became
**continuous-flow** in the 1990 revision — *"To maintain inhibition there must be a
continuous flow of messages along the new wire."* **An override that lapses unless
continuously re-asserted is a genuinely useful guardrail pattern.** Brooks names the
weakness himself, and Kirsh (1991) gives the citable scaling argument: *"in [a] complex
desires system it is not possible to rank desires according to a small number of
lexicographically ordered dimensions… Without representation, desires lack the modularity
to be reasoned about."* That is the argument that emergent arbitration does not scale, and
by extension that an agent swarm needs explicit, inspectable coordination state.

**HTN complexity, stated correctly.** Undecidability is via a specific reduction — HTN
planning can encode the intersection problem of two context-free languages. Totally
ordered HTN cannot express undecidable problems. **Task insertion restores decidability**,
and the reason is precise: recursion in the hierarchy stops contributing to the
solution set — so robustness via task insertion is a real expressivity trade. Plan
verification alone is NP-complete even for simple HTN problems.

**And the HTN+LLM result that matters most: LLMs cannot author HTN domains [SINGLE].**
Parsing success around 36 %, but **syntactic validity dropping to about 1 % for
hierarchical models versus about 20 % for classical planning.** Conversely ChatHTN
interleaves symbolic HTN with LLM-generated decompositions while **maintaining provable
soundness**. **The pattern that works is: LLM proposes, symbolic checker guarantees,
successful proposals get cached as methods.**

**Task allocation is easier than the literature implies.** Gerkey & Matarić classify
*problems*, not architectures. Single-task, single-robot, instantaneous assignment
(**ST-SR-IA**) reduces to the optimal assignment problem and is **polynomial**, measured at
under 1 ms for tens of tasks and under 1 s for 300 — "easily fast enough to be used in the
control loop." Its online variant is provably near-best by greedy. The other classes are
strongly NP-hard. Two framings worth importing: the **matroid criterion** (greedy is optimal
exactly when the subset system is a matroid), and **utility noise as an exogenous bound** —
*"the robots' utility estimates will be inexact… These unavoidable characteristics… will
necessarily limit the efficiency with which coordination can be achieved."* **Bid noise is
not a protocol defect; it caps what any allocator can achieve** — which is the correct
answer to "LLMs cannot price their own work."

**Auction theory's central impossibility [ROBUST].** Lehmann, O'Callaghan & Shoham (*JACM*
2002): **truthfulness with a greedy approximation is achievable; truthfulness with
optimality in polynomial time is not**, because VCG's incentive properties depend on exact
optimisation. Long-lived computational economies are also documented to oscillate and
crash.

**Stigmergy, with the right distinctions and the right warning.** Two orthogonal axes.
**Quantitative** stigmergy has a scalar medium (pheromone concentration) giving graded
response; **qualitative** stigmergy has a discrete typed stimulus set, so agents respond to
*which configuration* they find — **a shared document or knowledge graph is qualitative
stigmergy**, a strictly better fit than the pheromone analogy. Separately, **sematectonic**
means the stimulus *is* the work product; **sign-based** means a dedicated marker. A
knowledge graph is almost purely sematectonic.

**And the load-bearing warning is about our exact domain [SINGLE].** Dunivin & Smaldino
(2025) analyse how search algorithms in *scholarly recommenders* work through stigmergy and
produce **popularity lock-in** — a "tyranny of popularity" in which the trace left by past
work biases future work toward what is already well connected. That is the opposite of what
an AI scientist is for. There is also now a formal treatment of **ledger-state stigmergy**:
coordination through append-only verifiable state rather than messaging, which is
structurally the closest published model of agents coordinating through a shared artifact.

**A blackboard is a stigmergic medium with a scheduler bolted on.** The LLM blackboard
papers are, mechanically, engineered qualitative stigmergy. The cost is documented too: a
shared medium is a shared attack surface, and data poisoning is stigmergy weaponised.

**Horling & Lesser's ten-paradigm survey (2004)** remains the best map, and two entries are
prophetic. **"Federation → intermediaries become bottlenecks"** is the exact motivation
given in 2025 for replacing master-slave with a blackboard. **"Market → potential for
collusion, malicious behavior"** is now an empirical finding among communicating LLM
sellers. And their §12 describes a paradigm not in their own table: a *"(sparsely) connected
graph structure, sometimes called a network organization or adhocracy, where agents interact
because of particular role-based requirements but no overarching design principle is
explicitly applied… These approaches can be effective and cost-efficient, but as the
environment scales or the agent population becomes more dynamic a more structured
organization can provide additional framework."* **That is a description of most current
LLM multi-agent frameworks, written in 2004, together with the prediction that it does not
scale.** Their normative conclusion: *"all have some form of organization, although it may
be implicit and informal."*

**The revival is strikingly uneven, and the unevenness is informative.** Blackboard,
Society of Mind, HTN and markets have all been revived by name. **Subsumption has not been
revived at all.** And the *quality* of revival inverts the name recognition: Society of Mind
is cited most and operationalised least — none of the LLM papers implement K-lines, censors,
or difference-engines — while HTN is cited least glamorously and operationalised most
rigorously, with provable soundness.

## The LLM-era evidence that constrains design

**Correlated error is a ceiling, not a nuisance [ROBUST].** Models conform **more** when
uncertain, and deliberation measurably *inverts* the aggregation gain. Prompt discipline
cannot fix this; only structural blindness can.

> **Four numbers withdrawn here — see [`00-provenance-audit.md`](00-provenance-audit.md) C2.**
> This paragraph previously claimed same-model ensembles realise 0.43–0.44 of the independence
> gain, frontier error vectors correlate at r ≈ 0.77, cross-family diversity cuts correlation
> from 0.68 to 0.40, and independent aggregation beats deliberation 83.43% to 76.11%. **None
> could be sourced, and 76.11 appears in a real table meaning the opposite** — it is
> ReConcile's no-demonstration average in Wang et al. (ACL 2024) Table 3, where it sits
> *above* the best single-agent baseline of 74.38.
>
> The conclusion is unchanged and is now carried by sourced evidence:
> - Debate degraded majority-vote accuracy in **10 of 10** model configurations on
>   CommonsenseQA, worst case −12.0 points, with correct→incorrect flips outnumbering the
>   reverse in every round (Wynn, Satija & Hadfield, ICML MAS Workshop 2025, arXiv:2509.05396).
> - Abandoning a correct position correlates with a sycophancy score at **r = 0.902**, and in
>   up to **86.36%** of cases where an agent started correct, debate never reached that answer
>   (Yao et al., arXiv:2509.23055).
> - Deference follows the capability gradient, so votes are never independent: **92.36%**
>   capitulation to a stronger peer, versus a **~47/53 coin flip** between comparable models
>   (Xiong et al., Findings of EMNLP 2023, arXiv:2305.11595).
> - Frontier models average **47.2%** conformity under induced self-doubt, and removing the
>   last dissenting peer causes the jump — 32.6% → 69.9% (Weng, Chen & Wang, ICLR 2025,
>   arXiv:2501.13381).
> - Cross-family heterogeneity bought **+0.07 points**: 6 agents across 3 model families
>   scored 78.66 against a best single agent's 78.59 (Wang et al., ACL 2024, Table 3).

**Intrinsic self-critique is net-harmful without an external signal [ROBUST].** The most
clearly refuted pattern in the literature and one of the most commonly shipped.

**Multi-agent debate fails compute-matched comparison against self-consistency [ROBUST],**
in three independent studies. It also shows the highest error propagation and the widest
adversarial spread of any topology.

**The one debate configuration with strong support is asymmetric [SINGLE].** Source-privileged
debaters, adjudicated by a judge *without* source access.

**Grounded verification is the highest-value component, and it has an operating point in our
exact setting [SINGLE].** Against a knowledge graph, PaperQA3 found supporting evidence for
**70.0 %** of sampled real edges and correctly found none for **83.4 %** of *injected false*
edges. This is the number to instrument against.

**Provenance must be built in, not retrofitted [ROBUST].** Retrieve-then-read scores **65.5**
AIS, post-hoc attribution **55.6**, LLM-as-retriever **46.0**. Retrofitting recovers less
than half of what building it in achieves. Deployed systems are far worse: about **51.5 %**
average citation recall across generative search engines; GPT-4o fabricating **78.7 %** of
computer-science and **94.8 %** of biomedical citations. **And the finding that should
govern the whole design: citation precision correlates with perceived utility at
r = −0.96.** Provenance does not emerge from optimising for answer quality; the objectives
are measurably opposed.

**Order matters in a way that is easy to get wrong [SINGLE].** Run contradiction detection
*before or atomically with* near-duplicate suppression. A synchronous dedup gate was found
silently rejecting contradictory writes before the contradiction detector could see them —
discarding precisely the disagreements you most need.

**Shared state beats passing history [SINGLE].** Selective shared memory 96 % task
completion, no memory 79 %, **full history 71 %**. Passing everything is worse than passing
nothing.

**Message scope caps attack spread [SINGLE].** Restricting visibility from global to local
cut self-replicating prompt infection success by about 20 % and capped non-replicating
infection at two agents, against **+13.92 % to +209 %** attack success under global
messaging.

**Hierarchical aggregation damps where pipelines amplify [SINGLE].** Performance drop under
an injected faulty agent: **hierarchical 5.5%**, linear chain **10.5%**, complete
bidirectional **23.7%** (Huang et al., arXiv:2408.00989). Hierarchy is twice as fault-tolerant
as a chain and four times as tolerant as all-to-all.

**A dedicated verifier beats every topology change measured [SINGLE].** In the same study, an
**Inspector agent recovered up to 96.4%** of the errors introduced by a faulty agent —
out-performing every structural change the authors tried. Independently, MAST's largest single
intervention gain was **+15.6% from adding an objective-verification step**. This is the
strongest evidence in the folder for anything, and it argues for spending the budget on
verification before topology.

> **Correction — see [`00-provenance-audit.md`](00-provenance-audit.md) C1.** The
> fault-tolerance line previously read *"23.6% degradation under injected faults versus 49.8%
> for linear pipelines."* 23.6 was approximately the **all-to-all** figure mislabelled as
> hierarchical, and 49.8 appears nowhere in the source. The direction survives and is much
> stronger than we claimed — which matters because T8 orchestrator–worker *is* hierarchical,
> so the corrected evidence favours the runner-up more than [`06`](06-chosen-design.md) admits.

**Explicit progress state is worth a lot [VENDOR].** A two-ledger design — facts partitioned
into verified / to-look-up / to-derive / **educated guesses**, plus a progress ledger with a
stall counter — was worth **31 %** when removed.

**Architecture is about a quarter of the story [SINGLE].** A decomposition of gains gives
roughly **6 points from prompt optimisation, 3 from topology, 2 from workflow prompts.**

**And the sobering baseline result [ROBUST]:** across agent benchmarks, cost differs by
nearly **two orders of magnitude at substantially similar accuracy**, benchmarks are
pervasively non-reproducible, and a temperature-warming retry loop matches state-of-the-art
scaffolds on HumanEval.

**One head-to-head favours shared-artifact coordination [SINGLE].** Blackboard **37.53 %**
versus master-slave **32.16 %** versus RAG **28.26 %** on KramaBench, with 13–57 % relative
gains across three benchmarks and three model families; a second independent LLM blackboard
system reports best average performance *at fewer tokens*. The stated reason is the one that
matters at scale: the coordinator stops needing to know every worker's capabilities.

**Single-writer synthesis [SINGLE].** Parallel section-writing produced disjoint,
incoherent reports.

**Stopping criteria.** Fit an exponential discovery curve online and stop on saturation
(median τ ≈ 80 papers in one deployed system); estimate absolute coverage by two-source
capture-recapture against an independent search method; report **WSS@95**. **Never use model
self-confidence as the stopping signal** — models conform most when uncertain, and
wrong-but-sure cascades are documented.

**Extraction quality [SINGLE].** Schema-forced extraction with ontology grounding achieves
**97–100 %** grounding accuracy versus **3 %** for a raw LLM. But relation extraction is the
weak link and will remain so: **F ≈ 0.44, recall ≈ 0.3**, negation unhandled, and **most
errors are in the predicate, not the entity.**

## Real AI-for-science systems

Sakana's AI Scientist runs a full pipeline including a review step; the published critiques
concern output quality rather than architecture. Coscientist and ChemCrow demonstrate
tool-mediated autonomy in chemistry. FutureHouse's PaperQA is the most architecturally
relevant: **retrieval-then-cite**, which is the pattern the attribution numbers above
favour. Elicit, Consensus and Undermind publish methodology unevenly, and the independent
comparative evaluations that exist live in library-science venues the computer-science
literature does not cite.

## Gaps in the field worth stating

There is **no compute-matched comparison of shared-artifact versus message-passing
coordination for a knowledge-graph pipeline.** **Nobody measures pairwise error correlation
between agents in a deployed system**, despite it being the quantity that determines whether
the architecture helps at all. Stopping criteria are absent from the major deep-research
survey. And **DCOP, the one formalism with actual guarantees, is never used as a baseline.**

> **Correction — compaction is no longer folklore.** This section previously read *"Context
> compaction is entirely folklore — not one published measurement of compression ratio
> against information retention."* That was defensible when written and is now wrong.
> Retention under agent-trajectory compaction has been measured, and the numbers are worse
> than the folklore assumed: compactors retain only **17% of injected session constraints**
> on average, and policy-violation rates rise from **0% with the policy in full context to
> 30% after compaction** (up to 59% for some model families), with the loss near-binary at
> item level — when a constraint survives, violations stay at zero. Retained content also
> **varies substantially run to run**, so an agent's post-compaction knowledge is not
> reproducible. Counterweight: the loss is a property of ad-hoc summariser prompts rather
> than of compaction itself, since trained compaction improves on no-compaction, and
> compression can *raise* accuracy by removing distractors.
>
> **What this changes for us.** [`06`](06-chosen-design.md) requires that every compaction
> emit a derivation edge to what it replaced. That is necessary and insufficient: the
> derivation edge preserves the *audit trail* while the 17% figure says the *content* is
> gone. Add a **pinned-invariants set** — constraints, identifiers, and decisions that
> compaction may not touch — and prefer selective typed retention over free-form
> summarisation. This is Cajal's point about summaries with a number attached to it.
>
> What remains genuinely unmeasured is a general compression-ratio-versus-retention curve
> for arbitrary agent context.

Two of those are papers that could be written as a by-product of building this.
