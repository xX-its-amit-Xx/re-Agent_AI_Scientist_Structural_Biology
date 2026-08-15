---
name: explain-significance
description: >-
  Write the context layer that makes a finding usable: why it is true, what it means
  to a non-specialist and to a medicinal chemist and to a modeller, and what decision
  it changes downstream. Also writes the reasoning trace — the options an agent
  weighed, why it rejected each alternative, and the sources that informed the
  judgement. Use whenever a stage has facts but has not yet said what they mean, when
  a report reads as opaque, or when a validator rejects a plain-language register.
  Trigger on: "what does this mean", "explain the significance", "why does this
  matter", "make this readable", "for a layman", "why did the agent decide",
  "show the reasoning", or /explain-significance.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
---

# Explain significance

A cited fact is checkable. It is not yet *usable*. Two things stand between the two,
and both are contract fields rather than good intentions:

**Interpretation** — outward-facing. Why the fact is true, what it means to each kind
of reader, and which downstream decision it changes.

**Reasoning trace** — inward-facing. Which options the agent weighed, why it rejected
each one, and what informed the judgement.

Without the first, a report is a list of assertions nobody can act on. Without the
second, it is a set of conclusions nobody can audit. A reader should finish a stage
report able to say *what was found, why it matters, what it changes, and how the agent
got there* — and that should be true whether they are a structural biologist or have
never heard of a binding pocket.

## Guard rails

- **The layperson register is required and mechanically checked.** Undefined jargon in
  it is a validation error, not a style note. "Write for a layperson" as an
  instruction reliably produces jargon in a friendlier tone; the check is what makes it
  real. Define the term in the glossary or rewrite without it.
- **Never let the plain register be a shorter version of the expert one.** It is a
  *different* explanation, usually built around what the thing does rather than what
  it is called.
- **An implication must take a side.** `direction` has to say what the finding argues
  FOR or AGAINST. "This is relevant to template selection" changes nothing; "argues
  FOR including non-family promiscuous proteins, because they share the adaptable-pocket
  problem" does.
- **Every implication needs `if_wrong`.** What breaks downstream if the interpretation
  is mistaken. This is the field that makes an implication reviewable instead of merely
  confident, and it is the one people skip.
- **A reasoning step that weighed one option is a default, not a decision.** Say so via
  `no_alternative_because`. Dressing defaults up as decisions turns the trace into
  post-hoc justification, which is worse than no trace because it looks rigorous.
- **Every rejected option needs `rejected_because`.** An unexplained rejection cannot
  be told apart from never having looked.
- **`informed_by` is not the same as a finding's `evidence`.** Evidence supports a
  *claim*; `informed_by` records what shaped a *choice*. A paper can be the reason you
  picked an approach without being evidence for any fact in the report.
- **Do not interpret an illustrative number.** If the value is a placeholder, the
  interpretation is about the relationship, not the magnitude — and it should say so.

## Writing for each audience

These are registers, not difficulty levels. Flattening them into one "expert" voice
loses the more useful half, because a structural biologist and a medicinal chemist
looking at the same shared motif genuinely see different things.

| Register | What this reader wants to know |
|---|---|
| `LAYPERSON` | What is this thing, what does it do, and why does it change what we do next? |
| `MEDICINAL_CHEMIST` | What does it imply for chemistry — which groups matter, will SAR transfer, where is the selectivity risk? |
| `STRUCTURAL_BIOLOGIST` | What does it say about the fold, the pocket, the interactions, the conformational question? |
| `ML_PRACTITIONER` | What does it change about training data, features, splits, or which model to trust? |
| `CLINICIAN` | What would this mean in a patient — exposure, interactions, liabilities? |

### The plain register, concretely

Three moves do most of the work.

**Say what it does, not what it is called.** Not "PXR is a nuclear receptor" but "PXR
is a protein that notices foreign chemicals and responds by switching on the liver's
clean-up machinery."

**Name the consequence in the same breath as the fact.** A layperson has no way to
judge whether a fact is important; that judgement is precisely what you are supplying.

**Use an analogy only if it survives scrutiny.** A binding pocket is usefully a lock,
because the shape genuinely decides what fits. Protein folding is *not* usefully
origami, because nothing about the paper-folding intuition transfers. A bad analogy is
worse than none — the reader remembers the analogy and forgets the fact.

Worked examples of all three, including the ones that fail, are in
[audience-registers.md](reference/audience-registers.md).

## The kind of context this project keeps asking for

Three recurring questions, with where the answers belong.

**"What is significant about this functional group or motif?"** The group's *role*, not
its name: what it does chemically, what it tends to bind, and therefore what its
presence predicts. A carbonyl that can accept a hydrogen bond next to a polar pocket
residue is a specific, checkable claim about why two molecules behave alike.
[chemical-significance.md](reference/chemical-significance.md) has a reference table of
common groups and ring systems with what each contributes and what it costs.

**"What does it mean that this is a nuclear receptor / a promiscuous target / a
xenobiotic handler?"** A class membership is a compressed prediction about behaviour.
Unpack it: a nuclear receptor means a molecule binding it changes gene expression,
which means effects are indirect and delayed, which means a potency number does not
translate straightforwardly into an effect. Put the unpacking in the glossary once and
the consequence in the interpretation.

**"How does this change the modelling downstream?"** This is what `implications` are
for, and it is the field most often left vague. Name the stage, the decision, the
direction, and the failure mode. See
[downstream-implications.md](reference/downstream-implications.md) for the mapping from
common Stage 1 findings to the Stage 2 and Stage 3 decisions they bear on.

## The glossary

Define a term **once per run**, on `ModelReport.glossary`, and every finding's plain
register may then use it — the renderer makes it hoverable everywhere it appears,
including inside the expert registers, which is where a non-specialist reading across
most needs it.

A good entry has three parts: what it is in plain words, why a reader of *this* report
needs it, and optionally an analogy. The second part is the one that gets skipped and
the one that makes the glossary worth reading rather than a dictionary.

## Writing the reasoning trace

Record a step when there was a real choice, at the moment you make it. Reconstructing
a trace afterwards produces justification rather than history, and the difference shows.

For each step: the question, the options actually on the table, which you chose, why,
and what informed it. Then two fields that are easy to skip and worth more than the
rest:

- **`revisit_if`** — the observation that should reopen this. A decision with no
  reopening condition survives long after its reason has expired.
- **`confidence_then`** — how sure you were *at the time*. Honest hindsight is not the
  point; the point is that a reader can see which conclusions rested on a shaky call.

Link steps to what they produced via `produced_findings`. That is what lets the
provenance figure trace a source through a decision to a finding to the stage it bears
on, and it is the cheapest way to make an analysis auditable.

Record `open_decisions` for anything deliberately deferred, so a reader can tell a
decision that was made from one that was postponed.

## Checking your work

```bash
reagent report validate --strict reports/<run>/<stage>/report.json
```

Strict mode fails on: a missing `plain_summary`, undefined jargon in any plain
register, a plain register averaging over ~32 words per sentence, and the usual visual
and handoff gaps. It also reports, as notes rather than failures:

- findings with no interpretation,
- interpreted findings with no implications — candidate trivia,
- which stages the report claims to bear on,
- which audience registers are actually covered.

That last one is the quickest health check. A report whose findings all speak only to
`ml_practitioner` has not done this work, whatever its `plain_summary` says.

## Anti-patterns

- **Jargon with a friendly tone.** "The LBD is quite promiscuous, meaning it exhibits
  polypharmacology" explains nothing. The validator catches this specific failure.
- **Restating the statement as the interpretation.** If the plain register is the
  finding with shorter words, no interpretation has happened. The test is whether it
  answers *so what*.
- **Implications that name a topic instead of a decision.** "Relevant to Stage 3" is
  not an implication.
- **A trace written at the end.** It will read as justification, because it will be.
- **Interpreting a placeholder as though it were measured.** Check for
  `illustrative: true` on any graph edge before building an interpretation on its value.
- **One analogy stretched across a whole report.** Analogies are load-bearing for one
  concept each. Reusing one past its precondition is how a reader ends up confidently
  wrong.

## References

- [audience-registers.md](reference/audience-registers.md) — worked examples per register, including analogies that fail and why
- [chemical-significance.md](reference/chemical-significance.md) — functional groups, ring systems, and target classes: what each contributes and what it costs
- [downstream-implications.md](reference/downstream-implications.md) — which Stage 1 findings bear on which Stage 2 and Stage 3 decisions
