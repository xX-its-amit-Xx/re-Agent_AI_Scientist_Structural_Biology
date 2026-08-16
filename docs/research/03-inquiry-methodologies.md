# Formal methodologies for inquiry, criticism, and evidence synthesis

Evidence chips: **Tested** (controlled or meta-analytic support) · **Mixed** ·
**Untested** (popular but without controlled evidence).

Each method below is given in four fields: what the procedure actually is, what problem it
was invented to solve, what evidence exists, and how it fails.

## Claims that did not survive checking

**The premortem's "30 % improvement" is misattributed (Untested).** Mitchell, Russo &
Pennington's own abstract attributes their effect to outcome *uncertainty*, not to
temporal perspective, and contains no such figure.

**The Vatican's devil's advocate was not abolished in 1983 (Tested against primary text).**
*Divinus Perfectionis Magister* retains a Promotor of the Faith. What was dismantled was
the **adversarial machinery**: written objections, written answers, and advancement gated
on a recorded majority finding that the objections had been met. Those four properties are
the implementable part, and they are more useful than the folklore.

**Sackman's Delphi critique targets the "expert halo effect", not the RAND brand.** His
actual wording: panellists *"bask under the warm glow of a kind of mutual admiration
society… The result is to make no one accountable."* Substitute "an ensemble of models" and
the charge lands unchanged.

**TRIZ's founding patent study is unverifiable in principle (Untested).** No corpus, no
sampling frame, no coding rule — and the patents were selected for the very phenomenon
they supposedly revealed.

**No controlled study shows design thinking improves innovation outcomes (Untested).** A
full sweep returned one controlled evaluation, of *teaching*, with self-report outcomes.

## Hypothesis generation and elimination

**Chamberlin's method of multiple working hypotheses (1890) — Mixed.** *Procedure:*
develop several rival explanations simultaneously and deliberately, so that affection for
any one is diluted. *Solves:* the premature-commitment failure, which Chamberlin describes
as the parental relation a researcher develops toward a single hypothesis. *Fails:*
requires the rivals to be genuinely distinct; a set of near-identical hypotheses gives the
appearance of pluralism with none of the benefit.

**Platt's strong inference (*Science*, 1964) — Mixed.** *Procedure:* devise alternative
hypotheses; devise an experiment whose outcome **excludes** one or more; carry it out
cleanly; recurse. *Solves:* accumulating confirmations that never eliminate anything.
*Evidence:* no controlled test; widely criticised as a description of physics
retrospectively imposed on biology. *Fails:* many important questions have no cheap
excluding experiment, and the method silently deprioritises them.

**Lakatos's research programmes — Untested but structurally useful.** *Procedure:*
distinguish a hard core from a protective belt; judge a programme *progressive* if its
modifications predict novel facts and *degenerating* if they only accommodate known ones.
*Solves:* the "when do I abandon this line of work?" question, which falsificationism
answers badly. This is the best available frame for a stopping rule on a research
direction rather than on a search.

**Popper's falsificationism.** Operationalised in practice mostly as pre-registration and
as the demand that a claim state what would refute it. The *practice* has evidence (see
registered reports below); the philosophy does not need it.

## Structured criticism and adversarial process

**Authentic minority dissent versus assigned devil's advocate — Tested, and decisive.**
Nemeth, Brown & Rogers (2001), *EJSP* 31(6), 707–720: authentic minority dissent was
*"superior to all three forms of 'devil's advocate'"*, measured on quantity and quality of
solutions. *This is the single most important finding in this document for architecture
purposes*, and it is confirmed independently in the organisational literature
([`01`](01-research-organisations.md)) and in the LLM literature below.

> **Attribution correction.** An earlier version of this section credited the
> **cognitive-bolstering** result to this paper. It belongs to a *prior* study that Nemeth
> et al. summarise in their own introduction — *"In a prior study comparing these two
> processes, devil's advocate appeared to foster thinking that was primarily aimed at
> cognitive bolstering of the initial viewpoint"*. We were citing a literature review as a
> result. The 2001 paper's own contribution is the superiority finding quoted above, which
> is what the design should rest on. Nemeth et al.'s more defensible framing for our
> purposes is *"the difficulty in replicating such authenticity through role-playing
> techniques"* — a claim about role-play, which is exactly the agent-relevant one.

**Adversarial collaboration (Kahneman) — Mixed.** *Procedure:* disagreeing parties agree in
advance on an experiment and on what each outcome would mean, then run it jointly.
*Solves:* interminable dispute in which each side reinterprets the other's data.
*Evidence:* documented cases exist and several resolved; also documented cases where the
parties agreed on the data and continued to disagree on the interpretation. *Fails:* needs
both parties to pre-commit, which is exactly what disputants resist.

**Red teaming — Mixed.** Effective when the red team is independently resourced, has a
different information base, and reports outside the chain being tested. Theatrical when it
is the same team wearing a different hat — which is the LLM default.

**Pre-mortem / prospective hindsight — Mixed.** The mechanism that survives is
*asking for the failure story* rather than asking for risks, because it converts an
evaluative task into a generative one. The headline figure is misattributed (above).

**Groupthink (Janis) and what actually prevents it — Mixed.** The intervention with
support is *independent generation before discussion*, not exhortation to dissent.

**Peer review — Mixed, and weaker than assumed.** Poor at detecting error; better at
detecting significance mismatch. The alternatives with real evidence are **registered
reports** (which change what gets published by removing the outcome from the accept
decision) and post-publication review.

## Structured group process

**Delphi — Mixed.** *Procedure:* anonymous independent estimates, controlled feedback of
the distribution, iteration, convergence. *Solves:* dominance by the loudest or
highest-status participant. *Fails:* Sackman's halo critique; and convergence is not
accuracy — an anonymous panel can converge on a shared error, which is the same failure as
model consensus.

**Nominal group technique and the brainstorming literature — Tested.** Independent idea
generation before discussion **reliably beats group brainstorming** on both quantity and
quality; the loss in interacting groups is well established (production blocking,
evaluation apprehension, social loafing).

> **Mechanism correction.** This was previously marked "directly applicable", and the rule
> does transfer — but **none of those three mechanisms applies to an agent.** Production
> blocking is an artefact of only one person being able to speak at a time, and agents run
> in parallel. Evaluation apprehension and social loafing are motivational, and an agent has
> no motivation to lose. The rule survives on a *fourth* mechanism, measured on agents and
> documented in [`04`](04-agent-architectures.md): shared context correlates errors. Generate
> in isolation and combine afterwards — for that reason, not these three.

**Estimate-Talk-Estimate and the wisdom-of-crowds conditions — Tested.** Aggregation helps
when errors are independent and unbiased; it fails under correlated error and information
cascades. The formal statement worth carrying: **γ² = ε − δ** — collective error equals
average individual error minus average diversity, so **a crowd of clones (δ = 0) gets
literally nothing from aggregation.**

**Multiple independent teams on one problem — Tested in the many-analysts literature.**
Different teams given the same data and question produce materially different answers,
which is itself the finding: it quantifies analytic degrees of freedom that a single team
cannot see.

## Evidence synthesis and appraisal

**Systematic review and PRISMA — Tested.** Every stage exists to close a specific
loophole: a pre-specified protocol prevents question drift; documented search strings make
the search reproducible; the flow diagram makes exclusions countable; dual independent
screening reduces missed studies.

**GRADE — Tested, and its evidence is directly load-bearing here.** Certainty is graded
across domains that lower it (risk of bias, imprecision, inconsistency, indirectness,
publication bias) or raise it (large effect, dose-response, plausible confounding in the
wrong direction). **Inter-rater reliability rose from about 0.3 to about 0.7 with the
instrument, improved further with more raters, and did *not* improve with a consensus
rating.** Pooling five independent diagnoses added 22 points in the clinical analogue.
*That is the empirical core of the independence argument.*

**Risk-of-bias tools (Cochrane RoB, ROBINS) — Tested.** The transferable idea is that bias
is assessed *per dimension* with a recorded judgement and a supporting quotation, not as a
single score.

**Living systematic reviews — Mixed.** The relevant mechanism is an explicit update
trigger and a version-stamped conclusion, so a reader knows which evidence base a
statement rests on.

## Invention and design methodology

**TRIZ — Untested.** The contradiction matrix and forty principles are a useful
*ideation prompt list*; the empirical claim behind them is unverifiable in principle.

**C-K theory — Untested but formally interesting.** Models design as alternating expansion
of a concept space and a knowledge space, which is a reasonable formal account of why a
design step can require *acquiring* knowledge rather than applying it.

**Design thinking / double diamond — Untested.** See above. Treat as vocabulary.

**Analogical transfer (Gentner's structure-mapping) — Tested, and it constrains our
cross-domain engine.** Transfer succeeds when the *relational structure* maps, and fails
when only surface features match. Far transfer is rare precisely because surface similarity
drives spontaneous retrieval while relational similarity drives usefulness. The
implementable consequence: force the abstraction step, and check the structural
precondition — which is what our `AnalogyCard` already does.

## Cross-cutting answers

**Separating generation from evaluation is supported; separating them is not enough.** The
brainstorming and nominal-group literature supports independent generation. But GRADE's
result — reliability improves with more raters and *not* with consensus — shows the active
ingredient is **independence**, not merely sequencing.

**What breaks when independence is violated:** the diversity term goes to zero and
aggregation stops buying anything. Under discussion it goes *negative*, because
conformity is not symmetric — participants move toward the confident and the high-status.

**When to stop:** systematic review answers this with saturation and a documented search;
Lakatos answers it for a research direction with progressive-versus-degenerating. Almost
nothing else has an answer.

**Which methods produce an auditable trail as a by-product:** PRISMA, GRADE, risk-of-bias
assessment, registered reports, and the dismantled Vatican procedure. All five share the
same trick — **the judgement is recorded with its reason at the moment it is made**, so the
trail is a by-product of doing the work rather than a separate documentation task.

## What happens when LLM agents play these roles

Every human failure mode reappears, amplified, and the measurements are consistent:

- **Prompted self-critique degrades accuracy** — GPT-4 on GSM8K falls from 95.5 % to
  89.0 % when asked to review its own answer without external signal.
- **Multi-agent debate loses to plain self-consistency at matched budget**, and actively
  destroys correct answers rather than merely failing to add them. See
  [`00-provenance-audit.md`](00-provenance-audit.md) C3 — the figures previously given here
  (83.0% versus 88.2%) were withdrawn as unsourced and replaced with MASLab and Wynn et al.
- **Assigned dissent does not decorrelate**: see the persona result two bullets down. An
  earlier version of this line read *"produces cognitive bolstering, exactly as in the human
  literature"*, which asserted a mechanism identity that does not exist — bolstering is a
  mind becoming more committed to a prior view, and an agent has no attitude to bolster. The
  measured agent finding is about error distributions, not about commitment. **The design
  rule is unchanged and correct; only its justification was wrong.**
- **An LLM judge picked the *worse* chemistry system on fluency grounds** while four expert
  chemists picked the better one.
- **Personas do not decorrelate**: 162 roles across four model families and 2,410
  questions produced no improvement. **Different model families cut pairwise error
  correlation — magnitude withdrawn, see [`00-provenance-audit.md`](00-provenance-audit.md) C2.**

The conclusion is uncomfortable and clear: the interventions that read as "adding rigour"
to an agent system — a critic prompt, a debate round, a persona panel — are the ones with
evidence *against* them. The interventions that work are structural: independence enforced
by construction, and an external signal the critic can check against.

## CASP as the best-engineered instance of all of it

Worth studying as a whole because it implements most of this document at once:
double-blind in *both* directions (assessors do not know submitter identity); prospective
target blinding, so the answer does not exist when the prediction is made; two submission
tiers separating automated servers from human-in-the-loop; assessors barred by policy from
competing; and published evidence that the structure itself drove progress — *"the
second-best method in CASP14 out-performed the best in CASP13."*

## Mapping to a research pipeline

| Methodology | Sub-problem it solves | Implementation as a role or stage | Failure mode |
|---|---|---|---|
| Multiple working hypotheses | premature commitment | generate ≥3 rival explanations per gap before evaluating any | near-identical rivals |
| Strong inference | confirmations that never eliminate | require a discriminating observation per hypothesis | no cheap experiment exists |
| Lakatos | when to abandon a direction | progressive/degenerating judgement on a line of work | requires history to judge |
| Authentic minority dissent | conformity | a *decorrelated second pipeline*, different model and corpus | costs a second pipeline |
| Assigned devil's advocate | — | **do not implement** | bolsters the initial view |
| Adversarial collaboration | interminable dispute | two source-privileged extractors, naive adjudicator | needs pre-commitment |
| Red teaming | blind spots | independently resourced attacker with a different corpus | theatrical if same team |
| Pre-mortem | risk blindness | ask for the failure story, not for risks | headline figure unsupported |
| Nominal group | production blocking | independent generation, then merge | none material |
| Delphi | status dominance | anonymous independent estimates, feedback of distribution | converges on shared error |
| Wisdom of crowds | single-estimate variance | aggregate independent estimates | γ² = ε − δ; clones gain nothing |
| PRISMA | irreproducible search | documented queries, countable exclusions, flow record | bookkeeping cost |
| GRADE | overstated certainty | per-domain certainty with recorded reasons | needs multiple raters |
| Risk-of-bias tools | undifferentiated quality | per-dimension judgement plus quotation | slow |
| Registered reports | outcome-dependent publishing | pre-register the prediction and the kill criterion | none material |
| Structure-mapping | surface analogy | force abstraction, check structural precondition | far transfer is rare |
| CASP design | evaluation capture | blind both directions, bar assessors from competing | needs an institution |
| TRIZ / design thinking | — | ideation vocabulary only | no controlled evidence |

## Remaining gaps

Several closed-access bodies could not be retrieved, including Ladha's correlation bound,
for which no open-access copy appears to exist anywhere. Where a number here is
unverified, it is marked as such rather than smoothed over.
