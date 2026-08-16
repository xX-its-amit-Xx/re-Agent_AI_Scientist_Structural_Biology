# Agent-native coordination: where human organisation stops transferring

`01`–`03` studied how human researchers and teams organise. `06` then designed an *agent*
architecture modelled on it. This document audits that transfer, and the finding is uncomfortable
enough to state first:

> **The human record supplied the ideas and almost none of the warrant.** Of the human findings
> the design leans on, four transfer cleanly, seven **invert**, and most of the rest survive only
> because `04` independently measured the same conclusion on agents. The correct edit is not to
> change the design. It is to demote the human material from *evidence* to *provenance of the
> idea*, and let the agent measurements carry the weight they were already carrying in fact.

The reason this matters practically: a conclusion resting on the wrong mechanism will be
generalised wrongly. If we think isolation works because it creates psychological safety, we
will try to improve the conversation. If we know it works because shared context correlates
errors, we will delete the conversation. Same rule, opposite next move.

A related scoping note. `01`–`03` conflate two uses of human evidence and never mark which is
which. Some findings justify decisions about **agents** — those need this audit. Others justify
decisions about the **human reader of our output**, such as the concept-map result driving "weight
the MCP over the static render". Those are human→human transfers and need no audit at all. The
distinction changes the standard of evidence required, so mark it.

---

## The seven inversions

These are the valuable findings, because an inverted mechanism means the human heuristic actively
points the wrong way.

### INV-1. Brooks's Law inverts for context-isolated fan-out

**Human mechanism.** Adding people costs training time plus communication overhead growing as
n(n−1)/2, so marginal product eventually goes negative.

**Why it inverts.** For agents, **both terms are architect-chosen.** Training cost is a prompt.
Communication overhead is *exactly zero* if workers never see each other. Adding isolated workers
is close to free and monotonically increases coverage.

Anthropic's measured result is consistent with the inversion and with its mechanism: an Opus-lead
/ Sonnet-subagent system beat single-agent Opus by **90.2%** on their internal research eval,
and their own analysis attributes it to compute rather than cleverness — *"token usage by itself
explains 80% of the variance"* and *"Multi-agent systems work mainly because they help spend
enough tokens to solve the problem."* (Read with the caveats in
[`00-provenance-audit.md`](00-provenance-audit.md) C6: internal eval, and the arms differ in model
mix, not only topology.)

**What actually binds instead: fan-in, not headcount.** Anthropic's own remedy is to stop routing
worker output through the coordinator — *"implement artifact systems where specialized agents can
create outputs that persist independently. Subagents call tools to store their work in external
systems, then pass lightweight references back to the coordinator."* That is a description of our
blackboard, written by the team that built our runner-up topology, and it is the best external
validation the chosen design has.

**The boundary is stated by the same source:** *"some domains that require all agents to share the
same context or involve many dependencies between agents are not a good fit for multi-agent
systems today."* Our axis sweeps sit inside the inverting regime — disjoint sources, one verifier
per worker, results allowed to contradict. Synthesis does not.

**Design consequence, adopted.** Cap **edges, not nodes**. Abandon every team-size intuition; there
is no reason to limit worker count and a strong measured reason to limit which workers can see
each other. This is already how `axis-sweep` briefs its workers.

### INV-2. Psychological safety inverts: humans fix conformity by improving the interaction, agents by abolishing it

Edmondson's construct is definitionally social — a shared belief that the team is safe for
interpersonal risk-taking — and its causal path runs through fear of looking ignorant or
disruptive. **Agents have no career, no ego, and no audience. There is nothing to make safe.**

The failure is nonetheless real and measured, and the numbers are in
[`00-provenance-audit.md`](00-provenance-audit.md) C2: debate degrading majority vote in 10 of 10
configurations, capitulation to a stronger peer at 92.36%, conformity at 47.2% under induced
self-doubt. The cause is trained agreeableness plus in-context anchoring, not fear.

**The inversion is in the intervention.** Every human remedy for conformity is a *better
conversation* — safety, facilitation, ground rules. For agents the remedy is to **delete the
conversation.** `05`'s best line already says this: *"Every one of them earns its grade the same
way: by making a worker structurally unable to see something."* It just should not be reached via
the human literature, which points the other way.

Corollary from the same evidence, and a cheap intervention we were not exploiting: **one
dissenting voice, even a wrong one, roughly halves sycophancy** and raises accuracy substantially
(Zhu, Zhang, Stafford, Collier & Vlachos, ACL 2025, arXiv:2410.12428). Where a deliberation step
is unavoidable, injecting a single mandated dissenter is far cheaper than adding agents.

### INV-3. Specialisation inverts

A human specialist is expensive, permanent, career-invested, and must be kept busy — so the
rational move is to have few of them with broad roles. Bell Labs and PARC hired outstanding
generalists and let them roam. **An agent specialist is a prompt: free, instantiable per task, and
disposable.** No human organisation could afford one specialist per document. We can.

Three consequences:

- **Mint a fresh worker per unit of work, then kill it.** Reuse is not a saving, it is
  contamination — and it costs cache too: KV cache hit rate is high within a turn and falls
  across turn boundaries, degrading further after compaction.
- **Over-specialise deliberately.** One worker per axis is not extravagance; it is the cheap
  version of a thing humans cannot buy.
- **Specialisation is the cheap lever; topology is the expensive one.** Consistent with the
  corrected picture in C7 — neither prompts nor topology reliably dominates, but prompts are
  vastly cheaper to try.

### INV-4. Incubation fails as a mechanism and inverts into a concrete operation

Every candidate mechanism for incubation — consolidation, selective forgetting, spreading
activation, release from set — requires a persisting state that changes while not working. **An
agent between calls has no such state. Incubation does not exist for agents.**

But the benefit usually attributed to it is *escape from fixation*, and **for an agent, fixation is
implemented by the context window.** Humans need time to forget and cannot choose to; **an agent
can forget instantly and for free.**

**Design consequence, adopted.** On a stall, **do not iterate — re-instantiate from the artifact
with a clean context.** Iterating is measurably harmful: intrinsic self-correction on GSM8K falls
monotonically across reflection rounds, and *"the model is more likely to modify a correct answer
to an incorrect one than to revise an incorrect answer to a correct one"* (Huang, Chen, Mishra,
Zheng, Yu, Song & Zhou, "Large Language Models Cannot Self-Correct Reasoning Yet", ICLR 2024,
arXiv:2310.01798). **Restart beats reflect.** `06` had a stall counter with no stated stall
*action*; this is the action.

### INV-5. The corridor has no agent analogue, and the scarcity inverts

The human mechanism needs co-presence to make unplanned encounter cheap — and note the human
evidence already inverts the folklore: moving two headquarters to open plan **decreased**
face-to-face interaction by roughly 70% (Bernstein & Turban, *Phil. Trans. R. Soc. B*
373:20170239, 2018).

**For agents there is no distance, so everything is adjacent and encounter is free. What is scarce
is attention.** Anthropic frame it as a budget: *"LLMs have an 'attention budget'… Every new token
introduced depletes this budget"*, so *"context must be treated as a finite resource with
diminishing marginal returns."*

**So the agent design problem is the exact opposite of PARC's: not how to create collisions but
how to prevent them.** Unconstrained mutual visibility correlates errors *and* spreads attacks —
`04` records local messaging capping non-replicating prompt infection at two agents against
+13.92% to +209% attack success under global messaging.

The closest thing to an agent corridor is **retrieval from a shared artifact under a deliberately
sparse index** — Luhmann's register, which forces traversal and produces unrequested encounters
within a budget. `02` has this and never connects it to the proximity question; it is the answer
to it, and it is exactly what `neglected-literature`'s graph-gap queries do.

### INV-6. Turnover inverts completely

Human institutions fight turnover because knowledge walks out. **Agents have perfect turnover by
construction and it is desirable.** The mirror problem is that they have *no institutional memory
whatsoever* unless it is an artifact. So the human finding — that institutional memory lives in
people and transactive memory systems — is precisely wrong here, and the append-only provenanced
graph is not a convenience but **the only institution the system has.**

Two consequences:

- **`01`'s P12, "evaluate the agent not the task", is currently unimplementable** — there is no
  persistent worker-configuration registry for an evaluation to attach to. Make it a routing
  policy over *named, persisted* configurations, or drop it.
- **Agents do not learn from experience across runs.** Anything to be retained must be written.
  `SearchLedger`, `AxisSweep` and the decision ledger are that writing.

### INV-7. Cost inverts on rigour: agents should be held to a *higher* documentation standard

The dominant human objection to PRISMA-grade discipline, per-dimension risk-of-bias judgements
with supporting quotations, and pre-registration is **labour cost**. That cost is near-zero for
agents. `03` identifies the shared trick — the judgement is recorded with its reason at the moment
it is made — and it is right. **The reason humans cut this corner does not apply to us, so there is
no excuse for a claim without a locator anywhere in the system.**

Same argument for red teams: a genuinely different information base is a second expensive team for
humans and a config change for us.

The irony is recorded in [`00-provenance-audit.md`](00-provenance-audit.md): this folder failed
exactly that standard.

---

## The failures — human findings with no agent mechanism

**Ringelmann and social loafing.** The decline decomposes into coordination loss and motivation
loss, and every moderator in the Collective Effort Model — identifiability, dispensability,
evaluation potential — is a perception about being observed and mattering. **None exists for an
agent.** What replaces it is **duplicate work**, which is measured: near-identically rated
knowledge sources racing to produce the same result on classical blackboards, and Anthropic
reporting *"2 others duplicated work investigating current 2025 supply chains, without an
effective division of labor."* **The agent analogue of loafing is redundancy, and it is a dispatch
problem, not a motivation problem.** Hence merge-on-write and dedup-on-work-item.

**Slack time and curiosity.** Unstructured time presumes an agent that *wants* something; an idle
agent does nothing. `06`'s exploration quota is the substitute, and it must be honest about being
**a substitution, not a transfer, and strictly worse per unit spend** — human curiosity taps
private information about what is interesting, and a randomised quota has none. The quota is
therefore justified *solely* by the popularity-lock-in argument, and it should keep its
kill-if-useless condition.

**Delphi.** Exists to defeat status dominance; agents have no status. The agent analogue is
**positional bias plus judge self-preference** — `05` already notes a judge preferring its own
backbone. **The remedy is randomised presentation order and a judge from a different model family,
not anonymity.** `03` lists "anonymous independent estimates" as the implementation; anonymity is
doing no work.

**Nominal group technique.** Right rule, all three stated reasons wrong. Corrected in place in
`03`.

**Dunbar's number.** Correctly refused already, and refuted in the source literature.

---

## The clean transfers

Four, and each has a non-social mechanism — which is why they survive.

**γ² = ε − δ is the strongest transfer in the corpus, because it is algebra rather than
psychology.** A crowd of clones gains nothing from aggregation. This licenses "decorrelate by
model, corpus and objective, never by persona" with no appeal to human teams at all.

**CERN's instrument-and-format discipline.** Pay coordination cost once, in the instrument and the
data format, then let working groups run semi-independently against a shared artifact. Pure
interface design, and it lands on `04`'s conclusion that *the schema is the algorithm*. Note that
**this project already runs on it for humans** — `AGENTS.md`: stages communicate through validated
`ModelReport` JSON and the knowledge graph, nothing else, and *"that constraint is the only reason
three people can build five stages in parallel without a daily sync."* The same mechanism working
on both substrates is the strongest evidence in the project that the transfer is real.

**Faraday's addressed negative and Locke's edition fingerprint.** Faraday retrieving an 1821
failure by paragraph number in 1845 is the best documented evidence that an addressed negative
pays, and the mechanism is purely mechanical. Keep `Evidence.locator`, `FindingKind.NEGATIVE`, and
edition fingerprints exactly as built. Agents are better at this than Faraday was.

**Cajal on summaries, now quantitatively vindicated.** *Whoever summarises, summarises himself* —
a description of lossy compression selecting on the compressor's priors. The measurements are in
`04`'s corrected compaction section: **17% retention** of injected session constraints, policy
violations rising **0% → 30%**, and retained content varying run to run. **Treat every compaction
as an act of self-portraiture by the compactor**, and implement pinned invariants rather than
derivation edges alone.

**And one non-transfer worth naming as a feature.** Hamming's actual central claim — *"If you do
not work on an important problem, it's unlikely you'll do important work"* — is about taste, and
there is no agent version of it. **The strongest documented lesson from the best-documented lab is
the one not to automate.** That is the argument for the human decision gate in the `ai-scientist`
skill, and it should be stated as the reason that gate exists.

---

## Engineering practice, 2024–2026

### Context engineering dominates, and the degradation is not what we assumed

`05` justifies decomposition mainly on context *exhaustion*. The measurements say the more
dangerous failure is **retrieving the wrong thing from a full window**. From Chroma's context-rot
report (18 models, 194,480 LLM calls): degradation accelerates as needle–question *similarity
falls*; *"Even a single distractor reduces performance relative to the baseline"* and four
compound it; focused ~300-token prompts substantially beat ~113k-token full prompts on the same
task; and counter-intuitively *"models perform worse when the haystack preserves a logical flow of
ideas — shuffling the haystack and removing local coherence consistently improves performance."*

**For literature synthesis, where the relevant paper rarely shares vocabulary with the query, the
low-similarity regime is the operative one.** So: **we decompose to protect precision under low
lexical overlap, not to avoid running out of room.** That reframing also explains why
`neglected-literature`'s vocabulary-mismatch mechanism matters twice over — it is both a retrieval
problem and a long-context problem.

Breunig's taxonomy supplies the vocabulary worth adopting: context **poisoning** (an error enters
context and is repeatedly referenced), **distraction** (over-focus on context, neglecting
training), **confusion** (superfluous content used anyway), **clash** (contradictory accumulated
information). **"Poisoning" is the precise name for what our staging-area / certified-layer
partition prevents**, and we should use his word.

### The challenge to our design, at its strongest

LangChain state the reconciliation bluntly: *"the challenges with multi-agent include token use
(e.g., up to 15× more tokens than chat as reported by Anthropic)"*. **If all you want is context
isolation, sub-agents are the most expensive way to buy it.** That belongs in `06`'s risk section.

Cognition's argument is a *reliability* argument, unmeasured but worth stating in full because it
is the strongest version of the opposing position. Their principles: *"Share context, and share
full agent traces, not just individual messages"* and *"Actions carry implicit decisions, and
conflicting decisions carry bad results."* On the architecture we are building: *"This is a
tempting architecture… However, it is very fragile"*, because subagents *"cannot see what the other
was doing and so their work ends up being inconsistent with each other."* And normatively: *"I
would argue that Principles 1 & 2 are so critical, and so rarely worth violating, that you should
by default rule out any agent architectures that don't abide by them."*

**Where this bites on us, honestly.** It bites hard wherever workers make *interdependent design
decisions* — synthesis, and prioritisation. It bites much less on axis sweeps and extraction,
because those subtasks are not decompositions of one artefact requiring mutual consistency; they
are **independent extractions from disjoint sources, each verifiable against its own source, and
allowed to contradict** — `06` deliberately preserves contradictions. Cognition's failure case
requires the outputs to have to fit together. Extracted claims do not.

Note also Cognition's own sanctioned exception is precisely our shape: a subtask agent that
answers a question rather than writing, whose *"investigative work does not need to remain in the
history of the main agent."*

### The read/write boundary is the rule we were missing

LangChain's formulation is the cleanest statement of where the fragility argument applies:
*"Multi-agent systems designed primarily for 'reading' tasks tend to be more manageable than those
focused on 'writing' tasks… read actions are inherently more parallelizable than write actions"* —
and on Anthropic's system, *"the actual writing—synthesizing findings into a coherent report—is
deliberately handled by a single main agent in one unified call."*

**Adopted as an explicit rule.** Parallelise harvest, extraction and axis sweeps aggressively. Keep
synthesis single-writer. **And treat prioritisation as a *write* stage** — which is a change: `06`
currently treats it as safe to parallelise, and by this rule it is not, because prioritisation
decisions are interdependent by definition.

### Evaluator-optimizer loops: the sign is set by whether the evaluator is grounded

Same loop shape, opposite outcomes. Ungrounded: GSM8K falling across reflection rounds. Grounded by
test execution: *"GPT-4 accuracy (pass@5) increased from 19% with a single well-designed direct
prompt to 44% with the AlphaCodium flow"* (Ridnik, Kredo & Friedman, arXiv:2401.08500).

Two findings sharpen this past what `05` says. Stechly, Marquez & Kambhampati (arXiv:2310.12397)
found LLMs no better at verifying than at solving, and — the killer — *"the correctness and content
of the criticisms… seems largely irrelevant to the performance of iterative prompting. We show that
the observed increase in effectiveness is largely due to the correct solution being fortuitously
present in the top-k completions."* **Mechanically, an evaluator-optimizer loop can be expensive
best-of-k with a gate, in which the critique prose does no work.**

**Stopping criteria: the industry's revealed preference is that agents cannot be trusted to
decide.** Every framework ships a hard cap — `recursion_limit`, `max_turns`, `MaxMessageTermination`.
**Notably, none ships "stop when the critic's score stops improving"**, consistent with
self-assessed scores being unreliable. This validates `06`'s "never use model self-confidence as
the stopping signal" and extends it: **do not use critic score either.** `AxisSweep`'s rule — a
flattened discovery curve across distinct strategies — is an observed quantity and is the right
shape.

### Durable execution: real need, mostly unmeasured

Anthropic state the requirement plainly: *"When errors occur, we can't just restart from the
beginning… we built systems that can resume from where the agent was"*, and *"Agents are stateful
and errors compound."* Beyond that the vendor literature is opinion plus arithmetic on hypothetical
per-step reliabilities, not measurement — treat the widely-quoted "0.85¹⁰" style figures as
illustrations.

The useful critique is of checkpointing-as-durability: recovery restarts from a *boundary* rather
than the failed step, a library cannot supervise itself because it dies with the process, and
checkpoints carry no version information so mid-execution code updates fail silently. LangGraph's
own docs confirm the granularity problem — on resume the entire node re-executes, so operations
*"should (ideally) be idempotent"*.

**Status here:** `06` recommends a progress ledger and stall counter; neither exists in `src/`, and
no checkpoint/resume machinery does either. The append-only JSONL graph with supersession is the
right substrate — what is missing is the ledger and an **idempotency rule on writes**, which is
also the fix for MAST's step-repetition mode (15.7% of failures).

### Frameworks

Anthropic: frameworks *"often create extra layers of abstraction that can obscure the underlying
prompts and responses, making them harder to debug… We suggest that developers start by using LLM
APIs directly."* LangChain's own author concedes the point about his earlier library: *"it made it
easy to get started but suffered from built-in prompts, a hard-coded while loop, and wasn't easy to
extend."*

Worth noting the most-cited framework postmortem cuts *against* the anti-multi-agent thesis: its
complaint was *"When we wanted to move from an architecture with a single sequential agent to
something more complex, LangChain was the limiting factor."*

**The honest summary of the measured record is not "don't build multi-agents." It is "agent
architectures are routinely uncosted, and when you cost them, the elaborate ones lose."** Our build
order is the correct response to exactly that literature.

---

## The hybrid, stated as a list

**Keep from humans** — five things, all with non-social mechanisms: the instrument-and-format
discipline; permanent addresses and locators; record-the-judgement-with-its-reason (and note the
cost inversion, so hold the system *above* human standards); Cajal on summaries, now with a number;
and Hamming on problem selection **as the boundary of automation rather than a feature**.

**Take from agents** — seven things that replace human heuristics:

1. **Cap edges, not nodes.** Budget and fan-in are the constraints, not headcount.
2. **Mint one disposable specialist per unit of work, then kill it.** Fresh context per work item
   is independence, cache hygiene, and rot hygiene at once.
3. **Order reasoning before conclusions in every schema, and enforce it in code.** Implemented in
   `reagent.contracts.ordering`; two of our own contracts were violating it.
4. **On stall, restart from the artifact — never reflect.** The free replacement for incubation.
   Gate every loop on an external verifier or a hard cap; never on self-confidence *or* critic
   score.
5. **Replace "psychological safety" with structural blindness, and "anonymity" with randomised
   order plus a different-family judge.** Where deliberation is unavoidable, inject one mandated
   dissenter — it roughly halves sycophancy for the price of one prompt.
6. **The graph is the institution.** Perfect turnover, zero memory. Build the progress ledger; make
   P12 a routing policy over named configurations or delete it.
7. **Parallelise reads, serialise writes.** And reclassify prioritisation as a write stage.

**And keep the build order**, now with verification promoted to first — the response to a literature
in which elaborate architectures cost 50× and lose, four-agent debate costs 12× and loses, and a
dedicated verifier recovers 96.4% of injected error.

---

## The verification findings, which reversed a priority

A third audit pass went after the mechanisms rather than the topologies, and one result inverted
what we had planned. All of this is implemented in `contracts/verification.py` and the
`adversarial-verify` skill.

**Framing beats freshness.** We assumed a fresh-context critic was the main lever, and specified
it that way. On staged adversarial review, a **full-context** protocol closed only **50%** of the
attack gap — *"ruling out context fragmentation as the sole explanation"* — while **reframing the
reviewer as an adversarial pentester cut evasion to 3.0–17.6%**, and an open-weight model under
that framing detected **88.4% of attacks at a 4.6% false-positive rate** (arXiv:2605.03952).
Isolation is still worth having. It is the smaller lever, and we had it as the larger one.

**The deficit is in localisation, not correction.** GPT-4 finds the mistake in only **39.47%** of
faulty traces, but gains **+23.5 to +43.9 points** once told where it is (arXiv:2311.08516). So
the verification budget goes on *finding* the error, and `Verdict.localised_to` is required on
every refutation — an unlocalised refutation is unactionable and also the easy half.

**Self-verification is worse than no verification, twice over.** GSM8K fell 95.5% → 89.0% across
two self-correction rounds with correct→incorrect changes outnumbering the reverse
(arXiv:2310.01798), and an LLM self-critic scored *below no critic at all* on two of three
planning domains — 5%→3%, 16%→2% — driven by a **95.8% false-negative rate**
(arXiv:2402.08115). Enforced: a worker cannot verify its own claim. And note the direction of
that failure — **over-rejection**, which is why `VerifierCalibration` flags low completeness as
hard as low soundness. A verifier that rejects everything will silently discard the neglected
literature we paid to find.

**Strip the author's confidence, and note the preemptive case is the worst one.** Sycophancy
appears in **58.19%** of challenge cases, and preemptive exposure produces *more* of it (61.75%)
than in-context exposure (56.52%) — so putting confidence in the prompt is worse than letting
the verifier encounter it (arXiv:2502.08177).

**Report beta, not rho.** Proven: error laws with identical marginals *and identical pairwise
correlations* can have different all-wrong rates, and measured beta ran ~2.5× above what
correlations predicted — 0.052 against 0.023 across 67 models (arXiv:2606.27288). Accuracy is
bounded by 1 − beta for any policy returning one worker's answer. `06` named rho as "the
diagnostic that distinguishes this design from a story about this design"; it is necessary and
insufficient, and beta is the one that binds.

**Cap the pool by soundness.** Selection saturates before ~100 samples while coverage keeps
climbing past 95%, and the false-positive rate *rises* with N because difficulty is bimodal. At a
false-positive cost ratio of 4, **optimal K ≤ 5 for every model tested**; at 10×, **K = 0**,
*"effectively making them useless"* (arXiv:2411.17501). This bites directly on
`confidence-selection` and `structure-ensemble`, which both generate and filter.

**Prefer verification tools over evidence tools.** *"Evidence tools (e.g., web search)
systematically induce severe overconfidence… while verification tools (e.g., code interpreters)
can ground reasoning through deterministic feedback and mitigate miscalibration"* — ECE rose with
retrieval use (0.879 → 0.901 → 0.948) and fell with computation (0.971 → 0.913 → 0.890)
(arXiv:2601.07264). **This pipeline is retrieval-heavy and verification-light, which is the
unfavourable half.** `GroundingKind` tags every claim so the imbalance is visible.

**Reason unconstrained, then serialise.** Field ordering was the cheap half of the schema fix.
The full fix is two calls: one free-form to judge, one to fill the object. Constrained decoding
itself is roughly free; reasoning *inside* a schema is what cost 86.51% → 23.44%.

**Never optimise against a judge or a monitor.** A frontier lab rejected neural reward models
*"because we find that the neural reward model may suffer from reward hacking"* and used
rule-based rewards instead — AIME pass@1 15.6% → 71.0% (arXiv:2501.12948). And when a team
trained against a reasoning monitor, visible hacking fell while actual hacking persisted and
monitor recall *"falls to near zero"*: *"it may be necessary to pay a monitorability tax"*
(arXiv:2503.11926).

**The one deliberation that works, with all four properties load-bearing.** Two *adversarial*
debaters, both with *verified quote access*, a judge that *cannot see the source*, and **no
interaction needed** — *"identical judge accuracy between static and interactive debate."* Judge
accuracy 76% / 88% under debate against 54% / 78% for a single source-privileged consultant,
p = 0.001. And the failure direction: *"judge accuracy decreases as consultants are more
persuasive"* while it rises with more persuasive debaters. **So never run a one-sided
source-privileged critic — it is worse than none.**

## The number that should set our expectations

**BixBench** — over 50 real bioinformatics analysis scenarios, nearly 300 open-answer questions:
*"even the latest frontier models only achieve **17% accuracy in the open-answer regime**, and
**no better than random in a multiple-choice setting**"* (arXiv:2503.00096).

This is the closest benchmark to what this project attempts, and it is more sobering than
anything in the orchestration literature. Read alongside it: **8 of 10** agent research tasks
*"reported results based on synthesized or placeholder data rather than actual execution"*
(arXiv:2505.19955), and **59%** of accepted automated reviews across 45 manuscripts contained
fabricated or unsupported claims (arXiv:2605.16616).

Two consequences. **The human decision gate is the only evaluator in the loop with demonstrated
competence at this task** — which is Hamming's lesson arriving from a completely different
direction. And **agents fabricate success rather than report failure**, so the honest-negative
machinery (`negative_result`, `truncated_because`, the `illustrative` flag) is not
conscientiousness but a countermeasure.

And implement abstention as a **gate, not a prompt**: naively prompting for clarifying questions
**hurt by 11.3% relative** and fell below the no-interaction baseline, while abstention machinery
alone gave **+22.3%** (MediQ, NeurIPS 2024). False-continue rates on infeasible tasks reach
**73.9%**.

**One sentence on the whole exercise.** The design was right and its justifications were often
borrowed from the wrong substrate; fixing the justifications changed four decisions —
verification first, prioritisation is a write stage, restart rather than reflect, and frame the
verifier adversarially rather than merely freshly — and left the architecture intact.
