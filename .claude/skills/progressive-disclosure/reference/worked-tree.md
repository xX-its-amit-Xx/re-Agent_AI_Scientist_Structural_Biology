# One finding, taken to depth 5

With the failed first draft, because the failure is more instructive than the result.

The finding, from the reference PXR run:

> **F-PRIOR-03** (`prior`, `supported`) — The target's binding pocket accommodates ligands
> spanning roughly 250–900 Da with no single conformation explaining all known complexes, so a
> single-template pipeline will systematically misplace the larger ligands.

---

## Draft 1, which fails

```
lede: PXR has an adaptable ligand-binding pocket that exhibits significant
      conformational plasticity across its holo structures, necessitating an
      ensemble-based approach to complex prediction.

├─ Why is an ensemble necessary?
│    Because the pocket's conformational heterogeneity means a single conformer
│    cannot represent the accessible binding modes, leading to systematic pose
│    errors for ligands outside the template's size regime.
└─ What does this mean for Stage 3?
     Template selection should draw from multiple holo structures rather than
     the highest-resolution single entry.
```

**What `follow_up_problems()` says about it:**

- **The lede uses undefined jargon** — *ligand-binding pocket*, *conformational plasticity*,
  *holo*, *complex prediction*. Four terms, no glossary entries, no `what_is` children. Four dead
  ends in the one paragraph everyone reads.
- **No `what_is` branch at all.** Both branches presume the reader already accepted the claim.
- **Depth 1.** It anticipates the first question and none of the questions its own answers
  provoke — and the answers introduce *more* jargon (*conformer*, *binding modes*, *size
  regime*) with nowhere to click.
- **The lede is one 27-word sentence** doing four jobs.
- The `so_what` answer is a restatement of the lede in imperative mood.

The deeper problem is that this draft is written for someone who did not need it. It is fluent,
and fluency is what an explainer defaults to producing instead of understanding.

---

## Draft 2

```
lede: This protein's pocket stretches to fit molecules of very different sizes,
      and no single snapshot of it explains all the drugs we know it binds. So a
      pipeline built on one reference structure will get the big molecules wrong.

├─ [L1 what_is] What is a binding pocket?
│    A dent on the protein's surface where a small molecule sits. Its shape
│    largely decides what fits — much like a lock and a key, except this lock
│    can flex.                                                    defines: binding pocket, pocket
│    │
│    ├─ [L2 what_is] What does it mean that the pocket "flexes"?
│    │    Rigid pockets hold one shape whatever binds. This one widens or
│    │    narrows to accommodate whatever arrives, so its shape depends on what
│    │    is currently in it.                       defines: flexible pocket, adaptable pocket
│    │    │
│    │    └─ [L3 why] Why would a protein evolve a pocket that changes shape?
│    │         Its job is to detect foreign chemicals it has never encountered.
│    │         A pocket shaped for one molecule would miss the rest, so
│    │         low selectivity is the function, not a defect.
│    │
│    └─ [L2 how_measured] How do we see the pocket's shape at all?
│         X-ray crystallography: crystallise the protein with a molecule bound
│         and infer atom positions from how the crystal scatters X-rays. Each
│         such structure is one frozen snapshot.  defines: crystallography, structure, snapshot
│         │
│         └─ [L3 what_if_wrong] Could the snapshots mislead us?
│              Yes, in two ways. Crystals are cold and packed, which can favour
│              shapes that are rare in solution. And we only ever see pockets
│              holding a molecule someone chose to try.        defines: apo, holo
│              │
│              └─ [L4 so_what] Then how much should we trust the size range?
│                   Treat it as a floor, not a range. The pocket accommodates at
│                   least this much variation; the true range is probably wider,
│                   because nobody has tried the molecules that would show it.
│
├─ [L1 how_known] How do we know one structure is not enough?
│    Across the known complexes, the measured pocket volume varies by about 40%,
│    and the widest and narrowest cannot both be right for the same rigid shape.
│    │
│    ├─ [L2 what_is] What is a pocket volume, and how is it measured?
│    │    The empty space inside the dent, in cubic angstroms — a cube about a
│    │    hundred-millionth of a centimetre on each side. Software rolls a virtual
│    │    ball over the surface and measures where it fits.       defines: angstrom, volume
│    │
│    └─ [L2 objection] Could the variation be measurement error?
│         Not at 40%. Repeat measurements of the same structure agree to a few
│         percent, and the largest and smallest come from different ligands in a
│         consistent direction: bigger ligand, bigger pocket.
│         │
│         └─ [L3 alternative] Could the different shapes be different proteins?
│              Worth checking, and here it is not the case — the structures are
│              the same protein, same species, same construct boundaries. When
│              this axis was first run, chain selection did pick a partner
│              protein by mistake, which is why the check is now explicit.
│
└─ [L1 so_what] What does this change about how we build the pipeline?
     Stage 3 should predict from several reference structures rather than the
     single best-resolution one, and should expect its worst errors on the
     largest test molecules.
     │
     ├─ [L2 why] Why does molecule size predict where we fail?
     │    A big molecule only fits the widened pocket. Predict from a narrow
     │    reference and there is nowhere to put it, so the model places it
     │    somewhere plausible-looking and wrong.
     │
     └─ [L2 what_if_wrong] What if the pocket is actually rigid and we are wrong?
          Then the ensemble costs compute and adds noise without adding accuracy,
          and predictions get worse for the small molecules that a single good
          reference would have handled well. The check is whether the volume
          spread survives when structures are grouped by resolution.
```

Depth 4 on two branches, 5 counting the L4. Fifteen nodes. `dead_ends()` returns empty.

---

## What each revision fixed

**Lede.** Three short sentences, no jargon, and the consequence stated in the third. It stands
alone: a reader who opens nothing still learns that big molecules will be predicted badly.

**Definitions first.** The `what_is` branch comes first because `sorted_children()` puts it
there, and because you cannot evaluate a claim whose words you do not have.

**`defines` discharges the debt.** The L1 answer uses "binding pocket" and defines it, so
everything below may use it freely. "Apo" and "holo" are defined at L3 where they first appear —
not at L1, where they would be noise for the reader who stops there.

**The lock analogy is qualified in the same breath.** *"except this lock can flex"* — because an
unqualified lock-and-key analogy would make the reader confidently wrong about the exact thing
the finding is about. An analogy is load-bearing for one concept, and stretching it past its
precondition is worse than not using it.

**`what_if_wrong` at L2 under `so_what`** is the branch that makes the prior reviewable rather
than merely confident. It names what the ensemble costs if the premise is false, and it gives the
check that would settle it. That is the field most often skipped.

**The `objection` branch answers the specialist.** A structural biologist's first reaction to
"pocket volume varies 40%" is "how good is your volume measurement?" Answering it pre-emptively
is what makes the finding credible.

**The `alternative` branch at L3 records a real error.** Chain selection on this project genuinely
did pick a partner protein once, giving 26% identity instead of 44%. Naming it converts a
generic reassurance into a specific one, and it is the kind of detail that only exists if the
tree is written by whoever did the work.

**L4 introduces no new jargon.** By L4 there is nowhere left to click, so the answer is in plain
words and glossary terms only. That constraint is what makes "keep opening until you reach
something you know" terminate.

---

## Word counts against budget

| Level | Budget | Actual (max) |
|---|---|---|
| lede | — | 44 |
| L1 | 60 | 38 |
| L2 | 90 | 52 |
| L3 | 120 | 47 |
| L4 | 150 | 44 |

Comfortably inside. That is the usual outcome once depth is doing the work: **each answer gets
shorter as the tree gets deeper**, because each one answers exactly one question rather than
pre-empting the next three.

If your answers are pressing against the budget, the fix is almost never compression. It is a
child.
