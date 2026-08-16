---
name: progressive-disclosure
description: >-
  Make a report readable by one reader who knows the field and another who knows nothing,
  without writing it twice. Anticipates the questions each claim provokes and answers them
  in nested dropdowns up to five levels deep, so a reader keeps opening until they reach
  something they already know. Enforces the completeness rule: an answer may use an
  unexplained term only if a child follow-up explains that term. Use when a report reads
  as opaque, when the plain register is fighting the expert one, or before publishing any
  report a non-specialist will read. Trigger on: "too much jargon", "make it readable",
  "educational", "anticipate questions", "dropdowns", "explain deeper", "follow-up
  questions", "for someone with no background", or /progressive-disclosure.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
---

# Progressive disclosure

There is no single depth at which a medicinal chemist and a software engineer both want to
read the same report. Writing for "an intelligent non-specialist" splits the difference and
serves neither: too slow for one, still opaque to the other.

So depth becomes the *reader's* choice. The top level stays short enough to skim. Every term
or claim a reader might not accept at face value carries a nested disclosure holding the
answer, five levels deep — far enough that someone starting with no background can keep
opening until they hit familiar ground.

## The completeness rule

**An answer may use an unexplained term only if a child follow-up explains that term.**
Recursively. The tree is finished exactly when every unexplained term either appears in the
glossary or is the subject of a child.

This is what converts *"write for a layman"* — an instruction that reliably produces jargon
in a friendlier register — into a mechanical property of a data structure. It also
guarantees the reader's click always lands somewhere: no dead ends, no term that stops the
trail.

`FollowUpTree.dead_ends()` returns every place the trail runs out, with the question it ran
out under. Empty means the tree is complete for a reader who knows nothing.

**The corollary is a hard cap.** If jargon must be explained by a child and children bottom
out at level five, the deepest level cannot introduce new jargon at all. That is not a
limitation of the format — it is what "keep opening until you reach something you know"
requires in order to terminate. Level 5 answers must be written in plain words or in glossary
terms, full stop.

## Structure

```
lede                                  ← what a reader gets if they open nothing
├─ What is a nuclear receptor?        ← what_is    (L1)
│  └─ What does "ligand-activated" mean?           (L2)
│     └─ Why does that make timing indirect?       (L3)
├─ Why does promiscuity make this hard?  ← why     (L1)
│  ├─ What is an adaptable pocket?                 (L2)
│  └─ How do we know this one is adaptable?        (L2)
│     └─ What does an ensemble of structures show? (L3)
└─ What does this change downstream?  ← so_what    (L1)
```

`lede` must stand alone. It is what most readers will actually read, so it is the one place
jargon costs the most — and the validator checks it hardest.

`FollowUpKind` fixes the reading order: **definitions first**, because you cannot evaluate a
claim whose words you do not have; **objections last**, because they presume the claim. The
order is `what_is → why → how_known → how_measured → so_what → what_if_wrong → alternative
→ objection`, and `sorted_children()` applies it so authors do not have to.

## Guard rails

- **Every question ends in "?".** A heading invites skimming; a question invites an answer,
  and the reader clicks because they recognise their own question in it. Enforced.
- **A child may not repeat its parent's question.** Otherwise opening it returns the reader
  to where they already were. Enforced.
- **Depth is the mechanism for detail, not length.** Word budgets by level (60 / 90 / 120 /
  150 / 200) are advisory, but an answer 50% over budget gets flagged: push the elaboration
  into a child rather than making the reader read past it.
- **`so_what` is required at the top level.** A tree that explains a claim without saying what
  it changes is knowledge-telling — fluent restatement, the documented default failure of any
  explainer. `so_what` is what makes it knowledge-building.
- **At least one of `what_is` or `why` at the top level.** Those are the questions a reader
  actually has first. Starting at `so_what` assumes they already accepted the claim.
- **More than one level, or the tree anticipated nothing.** A flat tree answers the reader's
  first question and none of the questions its own answers provoke. `depth() < 2` is flagged.
- **Seven top-level branches maximum.** Past that the reader scans a menu instead of
  recognising their question. Group under fewer parents.
- **`defines` is how a debt gets discharged.** A `what_is` child that defines "apo" lets its
  parent and every sibling below use the term freely. A term defined by a *cousin* does not
  count — nothing leads the reader there.

## Writing answers

**Answer the question that was asked.** The commonest failure is answering the adjacent
question the author found more interesting.

**Say what it does before what it is called.** "A protein that notices foreign chemicals and
switches on the liver's clean-up machinery" beats "a ligand-activated transcription factor",
and the second belongs in the child that defines the term.

**Put the consequence in the same breath as the fact.** A reader who needed this disclosure
has no way to judge whether a fact matters. Supplying that judgement *is* the answer.

**Use an analogy only if it survives scrutiny.** A binding pocket is usefully a lock, because
shape genuinely decides what fits. Protein folding is not usefully origami, because nothing
from paper-folding transfers. A bad analogy is worse than none — the reader keeps the analogy
and loses the fact.

**Let a `how_known` branch carry the evidence.** Citations inline make the top level
unreadable; citations one click down make it auditable. This is the practical answer to the
tension between readability and attributability, which are measurably opposed objectives.

## Which findings need a tree

Every `prior`, `design_choice`, `negative_result` and `constraint` — the kinds a downstream
stage acts on. `findings_without_follow_ups()` lists the ones missing it. Those findings are
asking to be taken on trust, which is the opposite of the point of this project.

Observations usually do not need one. If an observation provokes questions, it is probably a
prior in disguise.

Also give the *report* a tree, for questions about the run rather than about one finding: why
this approach, what would have changed the answer, what is still open.

## Checking

```bash
reagent report validate --strict reports/<run>/<stage>/report.json
```

`follow_up_problems()` reports dead ends, over-budget answers, missing `so_what`, flat trees,
and depth violations. `disclosure_depth()` gives the deepest level per finding — a report
of all-depth-1 trees has the feature without the benefit.

## Anti-patterns

- **Dropdowns as a filing cabinet.** Hiding text the reader needs is not disclosure. The lede
  must be sufficient on its own; children are for going *deeper*, never for what was cut.
- **A tree that is all breadth.** Twelve top-level questions and no children means twelve
  first questions were anticipated and no second ones.
- **Jargon at level 5.** There is nowhere left to click. Gloss it or rewrite.
- **The plain register as a shorter expert register.** It is a *different* explanation, usually
  built around what the thing does rather than what it is called.
- **Answers that restate the question.** Rejected by the validator, and the commonest way a
  tree looks complete while explaining nothing.
- **Writing the tree from the report instead of from a reader.** Ask what someone would
  actually stop at. The terms an author no longer notices are exactly the ones that stop people.

## References

- [question-catalogue.md](reference/question-catalogue.md) — the questions readers actually ask of each finding kind, per audience, as a starting checklist
- [worked-tree.md](reference/worked-tree.md) — one finding taken to depth 5, with the failed first draft and what each revision fixed
- [rendering.md](reference/rendering.md) — nested `<details>` markup, keyboard and screen-reader behaviour, deep-linking to a branch, and print fallback
