# What readers actually ask

A starting checklist, not a template. The point is to anticipate the question *this* reader has
of *this* claim; the value of a catalogue is that it stops you from anticipating only the
questions you find interesting.

The most useful diagnostic when writing a tree: **the terms an author no longer notices are
exactly the ones that stop other people.** If you cannot find anything to define, you have lost
the ability to see your own jargon, and the validator's dead-end list is a better guide than your
intuition at that point.

---

## By finding kind

### `observation` — a fact read out of a source
1. What is *<term>*? (`what_is`)
2. How do we know this — who measured it, and how? (`how_known`)
3. Is this specific to our target or generally true? (`why`)
4. What would make this wrong? (`what_if_wrong`)

Observations often need no tree. If one provokes real questions, it is probably a `prior` in
disguise, and reclassifying it is usually the right fix.

### `prior` — a constraint to inject into modelling
1. What is *<term>*? (`what_is`)
2. Why does this constrain the model rather than just describe the target? (`why`)
3. What happens if we ignore it? (`so_what`)
4. How confident is this, and on what evidence? (`how_known`)
5. Under what conditions does it stop holding? (`what_if_wrong`) ← **the one that gets skipped**
6. Could something else explain the same evidence? (`alternative`)

Item 5 is the domain of validity. A prior applied outside it is how a pipeline regresses while
appearing better-informed, and it is the single highest-value branch in the whole catalogue.

### `design_choice` — a decision about how to build
1. What were the alternatives? (`alternative`)
2. Why this one? (`why`)
3. What does it cost — what does it give up? (`what_if_wrong`)
4. What would make us change it? (`what_if_wrong`)
5. Who else has done it this way, and what happened? (`how_known`)

### `negative_result` — something that does not work
1. What exactly was tried? (`how_measured`)
2. How do we know it failed rather than being run wrong? (`how_known`) ← **the reasonable objection**
3. Does this rule out the whole approach or one variant? (`why`)
4. What does it mean for our plan? (`so_what`)

Item 2 is the objection a specialist will raise immediately, and answering it pre-emptively is
what makes a negative result credible rather than an admission.

### `constraint` — a hard limit
1. Where does the limit come from — physics, data, budget, licence? (`why`)
2. Is it absolute or a threshold? (`how_measured`)
3. What does it forbid? (`so_what`)
4. What would relax it? (`what_if_wrong`)

### `hypothesis` — a testable proposition
1. What would confirm it? (`how_measured`)
2. What would refute it? (`what_if_wrong`)
3. Why is it worth testing rather than assuming? (`why`)
4. What does it predict that we do not already believe? (`so_what`)

Item 4 is the knowledge-building test. A hypothesis entailed by what we already think has
predicted nothing.

---

## By audience

The same claim provokes genuinely different questions. These are registers, not difficulty
levels, and flattening them into one voice loses the more useful half.

### No background
- What is this thing, in ordinary words?
- Why does anyone care?
- Is this a big deal or a detail?
- What is the pipeline actually trying to do?
- What would go wrong without this?

They need the *stakes* most. A layperson has no way to judge whether a fact is important, and
supplying that judgement is the substance of the answer, not a courtesy attached to it.

### Medicinal chemist
- Which functional groups are doing the work?
- Will SAR transfer between these?
- Where is the selectivity risk?
- What does this say about what to make next?
- Is the assay measuring what it claims?

### Structural biologist
- Which residues, which conformation, which state?
- Apo or holo, and does it matter?
- What is the resolution and the occupancy?
- Is the alignment real or estimated?
- What is the evidence for plasticity?

The alignment question is load-bearing here: our `compare_structures` numbers are
sequence-guided estimates, not structural alignments, and a `how_measured` branch must say so.
A structural biologist who assumes TM-align produced the number will draw conclusions the number
cannot support.

### ML practitioner
- What does this change about the training set?
- How should the split be constructed?
- Is this a feature, a constraint, or a filter?
- What is the leakage risk?
- How would we know the prior helped?

### Clinician
- What would this mean in a patient?
- Which interactions or liabilities does it imply?
- What is the exposure question?

---

## Questions that need a branch whenever they apply

Independent of kind and audience. If any is true of a finding, the branch is not optional:

- **"Is this number real or illustrative?"** If the value is a placeholder, say so at the top
  level, not one click down. A reader who builds on a placeholder has been misled by omission.
- **"Is this measured or estimated?"** Especially superposition, pocket comparison, and anything
  derived from a single structure.
- **"Does this come from one source or several?"** A `supported` finding and an `established` one
  differ, and readers do not know our confidence vocabulary.
- **"Was this searched or assumed?"** If an axis is thin, say whether it is a boundary or an
  unexplored region.
- **"Which of this is the model's own reasoning?"** A design choice with no citation is the
  agent's judgement, and that is legitimate and needs saying.

---

## Anti-patterns in question writing

- **Questions the author wants to answer.** "Why is this approach elegant?" Nobody asked.
- **Questions with the answer inside them.** "Why does promiscuity require an ensemble?" presumes
  it. Ask "Does promiscuity mean one structure is not enough?"
- **Compound questions.** Two questions in one gets half an answer. Split them; that is what
  children are for.
- **The `what_is` that never arrives.** A tree with `why` and `so_what` branches but no
  definitions serves only readers who did not need it.
- **Twelve top-level questions.** The reader scans a menu instead of recognising their question.
  Past about seven, group under fewer parents.
