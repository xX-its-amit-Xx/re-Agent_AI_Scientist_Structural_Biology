# The option space: every orchestration topology considered

This is the enumeration. It is written so that **disagreeing with the chosen design means
pointing at a specific row.**

Cost is relative to one well-prompted single agent. *Error propagation* and *provenance* are
graded **A** (best) to **E** (worst). *Fit* is fit to a literature → knowledge-graph →
synthesis pipeline specifically, not in general. Evidence labels follow
[`04`](04-agent-architectures.md).

## Reading the table

Three columns decide almost everything for us, and they are not the ones usually optimised.

**Error propagation** matters because our output is a knowledge graph that later stages
treat as fact. One agent's fabrication becoming another's premise is not a quality problem,
it is a correctness problem, and the correlated-error ceiling (same-model ensembles realise
the withdrawn independence figures are corrected in 00-provenance-audit.md C2) means we
cannot prompt our way out of it.

**Provenance** matters because retrofitting recovers less than half of what building it in
achieves, and because citation precision correlates with perceived utility at **r = −0.96**.
Optimising for a good-looking answer actively degrades attributability. So provenance has to
be the write format.

**Cost** matters because agent architectures differ by nearly two orders of magnitude at
substantially similar accuracy, and because roughly a quarter of achievable gain comes from
topology at all.

## Single-agent and degenerate baselines

| # | Topology | Mechanism | Cost | Err | Prov | Failure mode | Fit |
|---|---|---|---|---|---|---|---|
| T1 | Single agent, ReAct loop | none | 1× | B | B | context exhaustion; context rot | **mandatory baseline** |
| T2 | Long context only, no retrieval | none | 2–10× | — | **E** | silent refusal, task-switch, reversion to parametric memory | exclude |
| T3 | Fixed prompt chain | program order | k× | D | A | brittle; downstream never challenges upstream | deterministic stages only |
| T4 | Router / classifier front door | classification | 1.2–2× | B | B | misclassification is unrecoverable | cheap triage |

**T1 is not optional.** It is the thing every other option must beat, and the baseline
literature says simple scaffolds match elaborate ones more often than the field admits.

**T2 is excluded on auditability alone**, independent of accuracy. A synthesis whose sources
are inside the context window rather than named in the output cannot be checked.

## Parallel and ensemble topologies

| # | Topology | Mechanism | Cost | Err | Prov | Failure mode | Fit |
|---|---|---|---|---|---|---|---|
| T5 | Parallel fan-out (sectioning) | partition + merge | n× | **A** | **A** | duplicate work; coverage gaps | **core: harvest and extract** |
| T6 | Parallel voting / self-consistency | aggregation | n× (K ≤ 5–10) | B | B | converges confidently on the wrong mode | use, diversity-selected |
| T7 | Mixture-of-agents | layered proposer → aggregator | ~18 generations | C | D | verbosity rewarded; latency | weak; keep only the heterogeneity |

**T5 is the workhorse** and it is the only topology that gets independence *for free*: if
each worker is given a disjoint partition and cannot see the others' output, the diversity
term in γ² = ε − δ stays positive by construction rather than by instruction.

**T6 is worth having but must be diversity-selected.** The specific correlation figures here
were withdrawn — see 00-provenance-audit.md C2. What is sourced: 6 agents across 3 model
families bought +0.07 points over the best single agent at a strong-prompt operating point
(Wang et al., ACL 2024, Table 3), and adding one weaker model to two stronger ones *cost*
accuracy (Wynn et al., arXiv:2509.05396). Diversity that spans a capability gap imports the
weak model's errors rather than decorrelating the strong one's. Placeholder ratio was 0.68 to
0.40, so if you can afford heterogeneous models, that is where the money goes.

## Orchestrator-centred topologies

| # | Topology | Mechanism | Cost | Err | Prov | Failure mode | Fit |
|---|---|---|---|---|---|---|---|
| T8 | Orchestrator–worker, synchronous | delegation + synthesis | **~3.75×** | B | B | synchronous blocking; vague briefs | **runner-up** |
| T9 | Orchestrator–worker, async queue | task queue + shared memory | tunable | B | B | queue starvation; policy complexity | **strong** |
| T10 | Hierarchical, multi-level | nested delegation | very high | B | C→D | telephone game; provenance collapse | only if breadth forces it |
| T11 | Agents-as-tools | tool-call invocation | **cheapest MAS** | B | A | manager context becomes the bottleneck | **strong for bounded subtasks** |
| T12 | Handoff / swarm | control transfer | highest tokens | D | D | logical drift; nobody owns the answer | exclude |

**T8 is the best-documented multi-agent topology in existence** and the honest runner-up.
Its own authors name the limitation: subagents run synchronously, so the lead cannot steer
them, they cannot coordinate, and the system blocks on the slowest one.

**T10 degrades provenance at each hop**, which is disqualifying for us rather than merely
costly.

**T12 is excluded**: highest token growth, worst error class, poorest provenance, and the
documented source of the logical drift that costs multi-agent systems their consistency
advantage.

## Debate and critique topologies

| # | Topology | Mechanism | Cost | Err | Prov | Failure mode | Fit |
|---|---|---|---|---|---|---|---|
| T13 | All-to-all debate | consensus | 6–20× | **E** | D | conformity, sycophancy, persuasive error | **exclude** |
| T14 | Sparse debate | consensus over sparse graph | 29–53 % < T13 | C | D | attenuated versions of the same pathologies | only if debating at all |
| T15 | Asymmetric-information debate | source-privileged debaters, naive judge | 2× + judge | B | **A** | judge self-preference for its own backbone | **narrow, correct use of debate** |
| T24 | Intrinsic generator–critic | self-critique, no external signal | 3–10× | **E** | D | breaks correct answers | **exclude** |
| T25 | Generator + grounded verifier | check claim against cited source | 2–3× | **A** | **A** | verifier quality is the ceiling | **highest-value component** |
| T26 | Process-supervised verification | step-level judgements | very high | A | A | reward-model out-of-distribution failure; label cost | take the insight, not the model |
| T27 | LLM-as-judge gate | preference scoring | 1× | C→E | — | inverts on fluent-but-ungrounded output | triage only |

This block contains the sharpest split in the whole enumeration.

**T13 and T24 are the two most commonly shipped patterns and the two with evidence against
them.** Debate does not merely fail to pay for itself — it **destroys correct answers a
cheaper aggregation would have kept**: 10 of 10 configurations degraded on CommonsenseQA,
worst case -12.0 points (Wynn et al., arXiv:2509.05396); up to 86.36% of correct starts lost
(Yao et al., arXiv:2509.23055). Under a unified re-implementation, no multi-agent method beat
plain self-consistency on Qwen-2.5-72B, which had the best average rank of twelve methods
(Ye et al., MASLab, arXiv:2505.16988). The withdrawn 83.0/88.2 pair is in 00-provenance-audit.md C3.
Self-critique without external signal *degrades* accuracy (95.5 % → 89.0 %). Both are
excluded, and it is worth being explicit that excluding them is a finding, not a
simplification.

**T15 is the one debate configuration that survives**, and its structure is exactly the
dismantled Vatican procedure: written objections, written answers, adjudication by someone
who cannot simply look up the answer.

**T25 is where the value is.** Our problem has a nearly free sound verifier — the source
text — which is precisely what almost every multi-agent negative result lacks. The reference
operating point is 70.0 % support found for real edges and **83.4 % of injected false edges
correctly rejected.**

**T27 is dangerous as a gate.** An LLM judge picked the worse chemistry system on fluency
grounds while four expert chemists picked the better one. Use it to triage, never to admit.

## Shared-artifact topologies

| # | Topology | Mechanism | Cost | Err | Prov | Failure mode | Fit |
|---|---|---|---|---|---|---|---|
| T17 | Blackboard + volunteering | post need → workers self-select | moderate | **A** | **A** | control complexity; lock contention; redundant work | **core** |
| T18 | Stigmergic contribution to the graph | read schema + sources, write claims | low per worker | **A** | **A** | **popularity lock-in**; a bad schema locks in | **recommended substrate** |
| T19 | Shared message pool + subscription | publish/subscribe by role | moderate | B | A | pool schema couples everyone | strong |
| T20 | Typed shared state + reducers | declared merge semantics | low | B | A | schema rigidity; silent reducer bugs | **implementation layer** |
| T21 | Governed shared memory | append-only, temporal supersession | low per op | **A** | **A** | dedup-before-contradiction race | **adopt the primitives** |
| T48 | Ledger-state stigmergy | append-only signed log | low + infra | **A** | **A** | retracted material accumulates; deletion is hard | **certified layer** |

**This is the block the chosen design is built from**, and the reason is structural rather
than empirical: a worker that reads *only its source document and the schema* cannot
converge on another worker's error, because it cannot see it. Independence stops being a
discipline and becomes a property of the wiring.

**T18's failure mode is the most serious risk in the whole design**, and it has a citation in
our exact domain: stigmergy in scholarly recommenders produces a *tyranny of popularity*, in
which the trace left by past work biases future work toward what is already well connected.
That is the opposite of what an AI scientist is for. Mitigations are in
[`06`](06-chosen-design.md) and they are not optional.

**T21 contributes one specific ordering constraint** that is easy to get wrong: run
contradiction detection *before or atomically with* near-duplicate suppression. A dedup gate
placed first was found silently rejecting contradictory writes before the contradiction
detector could see them.

## Allocation and market topologies

| # | Topology | Mechanism | Cost | Err | Prov | Failure mode | Fit |
|---|---|---|---|---|---|---|---|
| T22 | Contract Net | announce / bid / award | O(n) messages | B | A | LLMs mis-price their own work | unnecessary |
| T23/T44 | Market / auction | pricing | mechanism cost | — | A | **collusion (measured)**; instability | dominated by T16 |
| T16 | Elo tournament + evolution | pairwise comparison, non-destructive | tunable | B | A | comparator bias; non-transitivity | **core: prioritisation** |
| T47 | DCOP | distributed constraint optimisation | exponential | — | **A** | needs honest numeric utilities | framing only |

**T22 is unnecessary because our allocation problem is the easy one.** Single-task,
single-agent, instantaneous assignment is polynomial and solved in under a millisecond at our
scale; greedy online assignment is provably near-best without a model of future tasks. **Take
Smith's slot design rather than his protocol** — task abstraction, eligibility, bid
specification and expiration are exactly the four fields a good subagent brief needs.

**T16 replaces the market.** Pairwise comparison with non-destructive evolution — new
candidates *compete* rather than replace — gives a compute-steering dial without requiring
anyone to price anything in absolute terms.

**T47 is kept as a framing.** It is the one formalism with real guarantees, and the fact that
the LLM agent literature never uses it as a baseline is a genuine gap.

## Search, planning, and pipeline topologies

| # | Topology | Mechanism | Cost | Err | Prov | Failure mode | Fit |
|---|---|---|---|---|---|---|---|
| T28 | Tree / graph search over hypotheses | branch, evaluate, prune | ~1.6–5× | B | **A** | needs a cheap sound evaluator | hypothesis stage |
| T29 | HTN skeleton, LLM fills | method library + symbolic checker | low runtime | **A** | **A** | incomplete relative to the library | **pipeline skeleton** |
| T30 | Assembly line of specialists | fixed role sequence | ~23K tokens/unit | **D** | B | early errors never revisited | deterministic stages only |
| T31 | Actor model / pub-sub | async typed events | low | B | A | non-deterministic interleavings | **transport layer** |
| T32 | Recursive inner loops | nested planning | depth-multiplicative | A | **A** | unbounded recursion | **adopt, depth-capped** |

**T29 is the right shape for the part of our pipeline that is genuinely known.** The stages
(harvest → extract → verify → resolve → rank → synthesise) are fixed; the judgement lives
inside them. And the evidence is unambiguous about the division of labour: **LLMs cannot
author hierarchical domains** — about 1 % syntactic validity — but LLM-proposes /
symbolic-checker-guarantees maintains provable soundness. **Author the skeleton by hand; let
the model fill it.**

**T32 damps rather than amplifies**, because an inner loop's retrieval noise never reaches
the outer context. Adopt with a hard depth cap.

## Adaptive and learned topologies

| # | Topology | Mechanism | Cost | Err | Prov | Failure mode | Fit |
|---|---|---|---|---|---|---|---|
| T33 | Learned or searched topology | search / GNN / RL over graphs | search cost, then savings | B | B | overfits the benchmark | premature |
| T34 | Self-evolving topology at inference | runtime meta-decisions | + meta | ? | **E** | non-reproducible structure | **exclude** |

**T33 is premature, on its own evidence.** Topology is worth roughly 3 points of an 11-point
decomposition while prompts are worth about 8. Optimise prompts and schemas first.

**T34 is excluded on auditability grounds.** A system whose structure changes per run cannot
produce a reproducible provenance trail, and reproducibility is the product here.

## Organisational topologies from the classical taxonomy

Included because enumerating the poor options is the point, and because several are what a
project drifts into by default.

| # | Topology | Mechanism | Failure mode (source's words) | Fit |
|---|---|---|---|---|
| T35 | Federation / brokers | capability advertisement | **"intermediaries become bottlenecks"** | external tools only |
| T36 | Congregation | persistent capability pools | **"sets may be overly restrictive"** | **default worker pools** |
| T37 | Coalition | dynamic goal-directed groups | **"short term benefits may not outweigh organization construction costs"** | poor |
| T38 | Team | joint commitment | **"increased communication"**; mutual visibility correlates errors | poor except the T15 panel |
| T39 | Holarchy | nested autonomous wholes | **"lack of predictable performance"** | = T32, use T32 |
| T40 | Matrix | multiple managers | **"potential for conflicts"** | poor |
| T41 | Society | open norms, public services | agents need norm machinery | out of scope |
| T42 | Compound | several styles concurrently | **"drawbacks of several organizational styles"** | **what we will build — count both sides** |
| T43 | Network / adhocracy | none explicit | **does not scale (predicted 2004)** | **the drift state; exclude as a target** |
| T46 | Blackboard + market | workspace + incentives | unvalidated | watch |

**T35 is right for third-party tools and wrong as an internal model.** PubMed, PDB, ChEMBL
and a co-folding service are exactly what a broker is for; our own extraction workers are
not.

**T40 is poor for a specific reason**: LLM agents handle conflicting authority badly, and
"failed to follow task requirements" is already about 11 % of observed multi-agent failures
with a *single* authority.

**T42 is what we are actually building, and the honest thing is to count the drawbacks as
well as the benefits.** [`06`](06-chosen-design.md) names each constituent's failure mode
rather than only its contribution.

**T43 deserves the last word in this section.** It is what most current LLM agent frameworks
implement by default, it was described in 2004, and its scaling limit was predicted then.
It is not a design; it is what you get when you do not choose one.

## Explicitly excluded, with reasons

| # | Topology | Why excluded |
|---|---|---|
| T2 | Long-context-only synthesis | unauditable regardless of accuracy |
| T12 | Handoff swarm for pipeline work | worst on tokens, error propagation, and provenance simultaneously |
| T13 | All-to-all debate for verification | loses compute-matched; maximally violates independence; widest adversarial spread |
| T24 | Intrinsic self-critique loops | most clearly refuted pattern in the literature; degrades accuracy |
| T34 | Self-evolving topology | non-reproducible structure |
| T43 | Network / adhocracy | the default drift state; predicted not to scale |
| T49 | Subsumption-style layered control | no world model, no explanation; arbitration does not scale (Kirsh); zero LLM-era revival |
| T50 | Society-of-mind personas / multi-persona prompting | **personas do not decorrelate** — 162 roles, four model families, 2,410 questions, no improvement; the reported effect is capability-gated to the largest models |

**One idea is retained from T49 despite the exclusion:** a bottom layer that always returns a
shallow-but-cited answer, which higher layers suppress when they succeed. That is a
graceful-degradation guarantee, and the continuous-flow property is a genuinely good
guardrail pattern — an override that lapses unless re-asserted.

**T50's exclusion is worth dwelling on**, because multi-persona prompting is the cheapest
thing in this document and therefore the most tempting. It does not work. Decorrelate by
model, corpus, and objective — never by instruction. This is the same finding as the human
literature's *authentic dissent beats assigned devil's advocate*, arrived at independently.

## What the enumeration converges on

Reading down the *error propagation* and *provenance* columns, the same six rows carry
grade **A** in both: **T5, T17, T18, T21, T25, T29** — with **T48** joining on provenance and
**T32** on damping. Those are, respectively, disjoint fan-out, blackboard volunteering,
stigmergic contribution, governed append-only memory, grounded verification, and an
HTN-style hand-authored skeleton.

That is not a coincidence and it is not a preference. **Every one of them earns its grade the
same way: by making a worker structurally unable to see something.** Fan-out partitions the
input. The blackboard stages writes so a worker never reads unverified peer output. Grounded
verification checks against a source rather than against another model. The hand-authored
skeleton removes the topology from the model's discretion.

The topologies that score badly on those two columns nearly all fail for the mirror-image
reason: they give agents *more* visibility of each other, on the theory that discussion
improves judgement. The measured result is that it does the opposite.
