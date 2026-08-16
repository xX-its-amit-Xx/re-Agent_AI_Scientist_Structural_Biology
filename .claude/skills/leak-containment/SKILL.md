---
name: leak-containment
description: >-
  Keep the answers structurally out of reach of every path that produces or
  chooses a prediction, especially when you hold the labels locally. Defines the
  split, enforces it with capability boundaries rather than intention, and audits
  for the leaks that produce a good score and no real performance. Use when
  ground truth is on disk, when setting up an evaluation, or when a result looks
  too good. Trigger on: "data leakage", "holdout", "did we cheat", "contamination",
  "split policy", "this result looks too good", or /leak-containment.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
---

# Leak containment

A leak is the one pipeline defect with **no external symptom**. Every other bug
makes a number look wrong. A leak makes the number look *right* — better than
right — and the mechanism that would reveal it is the same mechanism it corrupted.

You cannot detect a leak by looking at the score. You have to prevent it
structurally, and audit for it directly.

The risk is highest in exactly the situation that feels safest: **you hold the
labels locally, for legitimate evaluation reasons.** Then nothing but discipline
separates the evaluation path from the prediction path, and discipline is not a
mechanism.

## The four leaks, in order of how often they happen

**1. Direct read.** A generation or selection path opens the labels. Usually
introduced innocently — for a debug print, for a sanity check, for filtering — and
then left in.

**2. Selection on truth.** Choosing which candidate to submit, or which items to
rescue, using the true score. Feels like evaluation and is actually prediction.
This is the most common leak in a generate-and-select pipeline, because the ranking
is right there and it is exactly the number you want.

**3. Tuning on the holdout.** Sweeping configurations, reading holdout numbers, and
adjusting. Each individual look is small; twenty looks is fitting the holdout by
hand. The holdout stops being held out the first time you act on it.

**4. Template or corpus contamination.** An input to the pipeline — a template, a
retrieved exemplar, a fine-tuning corpus — that *is* one of your evaluation items.
This is the subtlest one, because the artifact usually arrives through a legitimate
channel and carries a legitimate provenance.

## Structural prevention

Intention does not scale, and it does not survive a deadline. Make the boundary a
capability.

Grant read access to the labels to **exactly one** component, the one that scores,
and deny it to every path that generates, selects, or ranks.

```yaml
capabilities:
  read_labels:
    paths: [data/ground_truth/**]
    mode: read
    granted_to: [eval]          # and nothing else, ever
    rationale: >
      Scoring requires the references. Granting this to generation or selection
      would let a prediction be chosen using its own answer, and the resulting
      score would be computed from the same files — so the leak would be
      invisible in the number that is supposed to reveal it.

  read_data:
    paths: [data/**]
    mode: read
    deny:  [data/ground_truth/**]   # even the broad grant excludes the answers
```

Note the second block. A broad `data/**` grant that happens to include the labels
is the most common way this boundary is lost, and an explicit deny is what keeps a
convenience grant from silently reopening it.

## The split, and the discipline around it

Define the split **once**, before any results exist, and write it into
`method.split_policy`:

- **Dev** — everything you may look at freely. Sweep here, tune here, iterate here.
- **Holdout** — scored a fixed number of times, ideally once, after configurations
  are frozen.

If the task provides its own split, use it. An externally defined split is not
negotiable after the fact, which is exactly its value; a self-chosen split can
always be re-chosen once you have seen results, and the temptation to do so
arrives precisely when it matters most.

Write down the scoring budget for the holdout as a number, and treat it as spent.
"Once" is a real constraint, not an aspiration.

## Audit

Prevention is not proof. Check directly.

**Path audit.** Grep every generation and selection path for reads of the label
location. Include config files, notebooks, and anything that resolves a path from a
variable. Run it as a test, not once by hand.

**Provenance audit.** For every artifact entering the pipeline as an input —
template, exemplar, retrieved neighbour, training row — check its identity against
the evaluation set. An input that *is* an evaluation item is a leak regardless of
how respectable its source. Match on content, not only on identifier: the same
item under a different id is the case that gets missed.

**Negative-control audit.** A signal known to carry no information should score at
chance. If it does not, something is leaking. `signal-scoping` establishes this
control; keep it in the pipeline permanently, because it is the only continuous
leak detector you have.

**Ablation audit.** Remove the suspect input and re-score. If performance barely
moves, the input was not doing the work you think it was — and if it collapses to
chance, it was doing all of it.

## Workflow

1. Read `problem.spec` for the label location, any task-provided split, and the
   rules about what may inform a prediction.
2. Define the split and the holdout scoring budget. Write `method.split_policy`
   before generating anything.
3. Implement the capability boundary. Verify by attempting a denied read and
   confirming it fails.
4. Read `method.scored_pool` and confirm the scoring path is the only component
   that touched labels to produce it.
5. Run all four audits. Record results in `method.leak_audit`, including the audits
   that found nothing — a clean audit is evidence only if you can show it ran.
6. Re-run the path audit on every change to a generation or selection path.

## When a result looks too good

Treat it as a bug report. In order:

1. Check the negative control. If it is above chance, stop and find the leak.
2. Re-run the path audit against the exact code that produced the result.
3. Check the provenance audit for contamination in the inputs.
4. Ablate the most suspicious input.
5. Only then consider that the result might be real.

The prior on "we did unexpectedly well" is much lower than the prior on "something
leaked", and inverting those priors is how bad results get published.

## Guard rails

- **Grant label access to exactly one component.** Not "one component plus a
  debugging path".
- **Deny explicitly inside broad grants.** A `data/**` read that includes the
  labels is the boundary quietly dissolving.
- **Never select or rescue by true score.** The prediction path may not consult the
  answer, in any form, for any reason.
- **Fix the holdout budget as a number and treat it as spent.** Every extra look is
  a small amount of fitting.
- **Match contamination on content, not just identifier.** The same item under a
  different id is the case that gets through.
- **Keep the negative control in the pipeline forever.** It is the only detector
  that runs continuously.
- **Record clean audits.** An audit nobody can show ran is not evidence.

## Anti-patterns

- **"We will be careful."** Care is not a mechanism, and it is the first thing to
  go under deadline pressure.
- **Reading holdout numbers during development** to see how it is going. That is
  what dev is for.
- **Filtering candidates by true score** before selection, as a "sanity check".
- **Templating or training on an artifact that is an evaluation item**, because it
  arrived through a legitimate channel.
- **Trusting a score to reveal its own leak.** It is computed from the leaked
  files.
- **Auditing once, at the start.** Paths get added; the audit must run on every
  change.
- **Explaining away an above-chance negative control.** There is no benign
  explanation for it.

## Handoff

`method.split_policy` — the split, its provenance, the holdout scoring budget, and
what may legitimately inform a prediction — and `method.leak_audit`, the result of
all four audits with dates and the code state they ran against.

Both are dated evidence, not one-time setup. A policy written before the pipeline
existed and never re-checked describes a system that no longer exists.
