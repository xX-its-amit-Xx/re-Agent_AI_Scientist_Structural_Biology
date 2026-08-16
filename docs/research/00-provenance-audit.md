# Provenance audit of this folder

**Read this before citing any number from `01`–`06`.**

This folder was written to be challengeable by pointing at a specific claim. A later
adversarial audit tried to do exactly that, going back to primary sources, and found that
**several load-bearing numbers could not be sourced, and one meant the opposite of what we
said it meant.**

That is the failure this entire project exists to prevent, occurring in the project's own
documentation. Recording it here rather than quietly editing it is the only response
consistent with what the rest of the repo claims to enforce. The lesson generalises: a
number repeated confidently across four documents acquires an air of authority from the
repetition alone, which is exactly the cumulative-advantage effect `neglected-literature`
is built to counter. It applies to our own prose too.

Two structural problems, stated plainly:

1. **`04`, `05` and `06` contain almost no citations.** A grep for `arxiv|doi|http` across
   `04-agent-architectures.md` returns one hit, an internal markdown link. Every number in
   its "LLM-era evidence that constrains design" section is stated bare. A reader cannot
   check a claim they cannot trace.
2. **Numbers were carried between documents without their sources.** Once `04` stated a
   figure, `05` and `06` cited `04` rather than the paper. The provenance chain we require
   of every `Finding` in a Model Report was not applied to our own research notes.

---

## Corrections

### C1 — Fault-tolerance figures were wrong, and the correction strengthens the conclusion

**`04:210–211` said:** *"Hierarchical aggregation damps where pipelines amplify. 23.6%
degradation under injected faults versus 49.8% for linear pipelines."*

**Actually** (Huang, Zhou, Jin, Zhou, Chen, Wang, Yuan, Lyu & Sap, "On the Resilience of
LLM-Based Multi-Agent Collaboration with Faulty Agents", arXiv:2408.00989), performance drop
under an injected faulty agent:

| Topology | Drop |
|---|---|
| Hierarchical `A→(B↔C)` | **5.5%** |
| Linear / chain `A→B→C` | **10.5%** |
| Complete bidirectional `A↔B↔C` | **23.7%** |

Our 23.6% was approximately the **all-to-all** figure mislabelled as hierarchical, and 49.8%
appears nowhere. The *direction* survives and is much stronger than we claimed — hierarchy is
twice as fault-tolerant as a chain and four times as tolerant as all-to-all.

**Consequence:** since T8 orchestrator–worker *is* hierarchical and T30 assembly-line *is* the
chain we already restrict to deterministic stages, **the corrected evidence favours the
runner-up more than `06` admits.** `06`'s "why not the runner-up" section should say so.

### C2 — The independence argument's four numbers are unsourced, and one is inverted

**`04:166–168`, `05:18`, `05:56–57`, `06:100–101` said:** same-model ensembles realise only
**0.43–0.44** of the independence gain; frontier error vectors correlate at **r ≈ 0.77**;
different model families cut pairwise error correlation from **0.68 to 0.40**; independent
aggregation **83.43%** versus deliberative consensus **76.11%**, below every single-model
baseline.

**Status: none of the four could be sourced.** Worse, **76.11 appears in a real table meaning
the opposite of what we claimed.** In Wang, Wang, Su, Tong & Song, "Rethinking the Bounds of
LLM Reasoning" (ACL 2024, aclanthology.org/2024.acl-long.331), Table 3, 76.11 is ReConcile's
*Direct* (no-demonstration) average across ECQA / GSM8K / FOLIO-wiki — and it sits **above**
the best single-agent Direct baseline of 74.38. There is no 83.43 nearby. Either the figure
came from elsewhere entirely, or it was lifted from this table and re-narrated with an
inverted conclusion.

For `r ≈ 0.77`, the likely intended source is Goel et al., "Great Models Think Alike and this
Undermines AI Oversight" (arXiv:2502.04313), which introduces the CAPA error-consistency
metric and reports that model similarity *increases* with capability. That the paper exists
and supports the *direction* was confirmed; that it contains 0.77 was not.

**These four numbers are hereby withdrawn.** Do not cite them.

**The argument they supported is better evidenced without them**, and this is the important
part — it was resting on the weakest available props:

- **Debate destroys correct answers.** Wynn, Satija & Hadfield, "Talk Isn't Always Cheap"
  (ICML Multi-Agent Systems Workshop 2025, arXiv:2509.05396) measured majority vote before
  and after debate across 10 model configurations. **Debate degraded CommonsenseQA accuracy
  in all 10**, worst case −12.0 points, with correct→incorrect flips outnumbering the reverse
  in every round and setting. Adding one weak model to two strong ones cost points.
- **Capitulation is sycophancy, and it is quantified.** Yao et al., "Peacemaker or
  Troublemaker" (arXiv:2509.23055): the rate of abandoning a correct position correlates with
  a sycophancy score at **r = 0.902**, and in up to **86.36%** of cases where an agent started
  correct, debate failed to reach that answer.
- **Deference follows the capability gradient, so votes are never independent.** Xiong,
  Ding, Cao, Liu & Qin (Findings of EMNLP 2023, arXiv:2305.11595): ChatGPT capitulates to
  GPT-4 on **92.36%** of disagreements, while between comparable models resolution is a
  **~47/53 coin flip**. Neither regime yields an independent vote — unequal pairs produce
  deference, equal pairs produce arbitrary tie-breaks.
- **Conformity is worst exactly when it matters.** Weng, Chen & Wang, "Do as We Do, Not as
  You Think" (ICLR 2025, arXiv:2501.13381): frontier models average **47.2%** conformity when
  self-doubt is induced, and removing the last dissenting peer causes the jump (32.6% → 69.9%).
- **Cross-family heterogeneity did not convert into accuracy** at a strong-prompt operating
  point: 6 agents across 3 model families scored 78.66 against a best single agent's 78.59
  (Wang et al. Table 3). **+0.07 points.**

`06`'s independence argument should be rewritten around these. The conclusion is unchanged.

### C3 — Debate-versus-self-consistency figures are unsourced; real ones exist

**`03:201–202`, `05:96` said:** *"Debate loses to plain self-consistency at matched budget
(83.0% versus 88.2%)."* Direction is right; the figures could not be sourced.

**Replace with** Ye et al., "MASLab" (arXiv:2505.16988) — 20+ methods re-implemented under one
harness, 10 benchmarks, 8 models. On Qwen-2.5-72B, **no multi-agent method beats plain
self-consistency**, which has the best average rank of all twelve methods tested (2.8 ± 1.8).
AutoGen scored 4.5 points *below* a bare single LLM. And Smit, Duckworth, Grinsztajn, Barrett
& Pretorius, "Should we be going MAD?" (ICML 2024, arXiv:2311.17371): *"multi-agent debating
systems, in their current form, do not reliably outperform other proposed prompting
strategies, such as self-consistency"* — with the single agent scoring highest of any system
on GPQA.

### C4 — MAST category percentages are from a figure, not a text, and the version matters

Any citation of MAST as **41.77% / 36.94% / 21.30%** traces to a figure in v1 of Cemri et al.,
"Why Do Multi-Agent LLM Systems Fail?" (arXiv:2503.13657) and is not stated numerically in the
text of either v1 or v3. **Cite v3's mode-level figures instead**, measured over 1,642
annotated traces across 7 frameworks:

- Specification and design: disobey task spec **11.8%**, step repetition **15.7%**, unaware of
  termination conditions **12.4%**, loss of history 2.80%, disobey role spec 1.5%
- Inter-agent misalignment: reasoning–action mismatch **13.2%**, task derailment **7.40%**,
  fail to ask for clarification 6.80%, ignored other agent 1.90%, information withholding
  **0.85%**
- Verification: incorrect verification **9.10%**, no or incomplete verification **8.20%**,
  premature termination **6.20%**

Two things worth noting. **Information withholding at 0.85% and ignored-input at 1.90% are
rare** — our earlier framing treated them as central. The dominant modes are mechanical: step
repetition, reasoning–action mismatch, not knowing when to stop, not following the spec.

MAST's headline claim is quotable and unchanged: *"we conjecture that improvements in the base
model capabilities will be insufficient to address the full MAST"*, and failures *"often stem
from system design issues, not just LLM limitations."*

### C5 — The 15× cost multiplier uses the wrong baseline

`05`'s T8 row prices orchestrator–worker at **~15×**. Anthropic's figure is *"multi-agent
systems use about 15× more tokens than chats"*, and in the same sentence *"agents typically use
about 4× more tokens than chat interactions."* Our T1 baseline is a ReAct **agent**, not a
chat, so the correct multiplier against our own baseline is **≈3.75×**. That materially
changes the economics and makes T8 cheaper relative to the headline than `05` implies.

### C6 — Anthropic's 90.2% must be quoted with its caveats

*"a multi-agent system with Claude Opus 4 as the lead agent and Claude Sonnet 4 subagents
outperformed single-agent Claude Opus 4 by 90.2% on our internal research eval."* Three
caveats travel with it: the eval is internal and its methodology unpublished; the arms differ
in **model mix**, not only topology; and Anthropic themselves attribute the mechanism to
inference compute — *"token usage by itself explains 80% of the variance"* and *"Multi-agent
systems work mainly because they help spend enough tokens to solve the problem."*

**The fair-baseline question is therefore unanswered even by the strongest positive result in
the field.** Kapoor et al., "AI Agents That Matter" (arXiv:2407.01502) make the general
version: *"we are not aware of any papers that compare their proposed agent architectures with
any of the last three of our simple baselines"* (retry, warming, escalation), and *"'State-of-
the-art' agent architectures for HumanEval do not outperform simple baselines."*

### C7 — The prompts-versus-topology split (6 / 3 / 2 points) is unsourced

MAST supplies a real and messier substitute. On AG2/GSM-Plus with GPT-4: prompt improvement
**+5.0 points (significant)**, topology change **+0.75 points (Wilcoxon p = 0.4, not
significant)**. With GPT-4o both reached p = 0.03. On ChatDev/ProgramDev, **topology (+15.6)
beat prompts (+9.4)**. Measured on failure-mode counts rather than task success, MAST concludes
the opposite of the AG2 result: *"topology-based changes are more effective than prompt-based
changes for both systems."*

**So the honest statement is: which lever dominates depends on the system and the backbone,
and neither reliably wins.** Weaker than "topology is a quarter of the story", pointing the
same way: do not lead with topology. Smit et al. is the extreme case — tuning a single prompt
parameter (how strongly agents are told to agree) moved a debate protocol **from worst to best
performing**, which means published debate results are not really measuring debate.

### C8 — Corrections already applied inline

Made in place, each with a marked correction block rather than a silent edit:

- **`01`, Los Alamos** — read plainly it is evidence *against* compartmentalisation, so it must
  not be cited in support of our isolation discipline.
- **`01`, Scannell & Bosley** — a decision-theoretic *simulation*, not a measurement.
  Relabelled. Note it is also not a human-team finding at all, which is why it transfers.
- **`02`, M10 / Uzzi** — the conventional-core/atypical-tail ratio was measured over *published*
  papers, so reading a **generation** policy off it requires the base rate of attempts at each
  novelty level, which the study does not provide. Selection on the dependent variable. Keep
  the ratio as a tunable parameter; drop the claim that Uzzi sets its value.
- **`03`, cognitive bolstering** — attributed to Nemeth et al. 2001; it belongs to a prior study
  they summarise in their introduction. We cited a literature review as a result.
- **`03`, nominal group** — the three named mechanisms (production blocking, evaluation
  apprehension, social loafing) do not apply to agents. Rule survives on a fourth mechanism.
- **`03`, assigned dissent** — *"produces cognitive bolstering, exactly as in the human
  literature"* asserted a mechanism identity that does not exist.
- **`04`, compaction** — *"entirely folklore"* is no longer true; retention is now measured, and
  it is worse than the folklore assumed.

---

## What changes in the design

Four things, all of which make the design better rather than worse:

**Promote verification to the first build step.** Currently step 4 in `06`. The evidence for it
is now the strongest in the folder: Huang et al.'s dedicated **Inspector recovered up to 96.4%**
of errors from an injected faulty agent, out-performing every topology change they measured.
MAST's single largest intervention gain was **+15.6% from adding an objective-verification
step**, and its whole verification category — incorrect verification 9.10%, no or incomplete
verification 8.20%, premature termination 6.20% — is verification failure. Spend here first and
treat topology as secondary.

**Restate the debate exclusion as a correctness argument, not a cost argument.** `05` excludes
T13 partly because it loses at matched compute. The stronger claim, now sourced: **debate
actively destroys correct answers that a cheaper aggregation would have kept** — 10 of 10
configurations degraded, up to 86.36% of correct starts lost.

**Add the two failure modes the design does not address.** Step repetition (**15.7%**) and
termination-unawareness (**12.4%**) together are **28.1%** of measured multi-agent failures, and
`06` addresses neither beyond a stall counter whose 31% value is itself unsourced. Needed: an
idempotency rule keyed on the work item, and a hard per-worker step budget. Note that
schema-forced extraction already handles a third mode by construction — MASLab found **79.66%
of one framework's failures on GPQA-Diamond were format errors** — and we should claim that
benefit explicitly.

**Adopt DCR as an instrumentation metric.** "Fraction of items where some worker had it right
and the system did not output it" is directly portable to our certified graph as an oracle-gap
measure, and it is more actionable than pairwise error correlation because it names a specific
recoverable loss. It also happens to be the same quantity `neglected-literature` cares about,
one level up: the difference between what was findable and what was reported.

---

## Standing rule for this folder

**Every number gets a locator at the point of use.** Author, title, venue, year, arXiv or DOI.
If a number cannot carry one, it does not go in — and if it is already in, it gets withdrawn
here rather than left to be re-cited.

This is the same rule `Evidence.locator` enforces on every claim in a Model Report. The
research notes were exempted by accident, and the exemption cost four numbers and one inverted
conclusion.
