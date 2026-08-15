# Downstream implications: which findings bear on which decisions

An `Implication` is the field that turns a finding into something a colleague can act on
or refuse. It has four parts and each one fails in a characteristic way: `for_stage` gets
a stage nobody reads, `decision` gets a topic instead of a decision, `direction` gets a
sentence that points nowhere, and `if_wrong` gets skipped or gets a restatement of the
finding.

This file is the mapping. The decisions named below are decisions the Stage 2, 3 and 4
skills actually make, read off their guard rails and their `meta.json` handoff keys, so
an implication written against this table lands on a consumer that exists.

## Addressing an implication correctly

`for_stage` takes a stage value — `stage0_scouting`, `stage1_literature`,
`stage2_biochem`, `stage3_prior`, `stage4_optimization` — or `"all"` when the implication
is genuinely general. It is a free string, not validated against the `Stage` enum, so a
typo produces an implication addressed to nobody and nothing will tell you. Name the skill
and, where you can, the handoff key inside `decision` instead of relying on `for_stage` to
carry the routing: `"which structures enter stage3.template_set"` is findable by the person
who has to fill that key in, and `"templating"` is not.

Both Stage 2 skills and all three Stage 3 skills share a stage value, so `for_stage` alone
cannot distinguish "this is for `pocket-anatomy`" from "this is for `pocket-dynamics`". The
`decision` field is where that distinction lives.

One honest note about `direction`. The validator checks for a side-taking keyword by
substring, so a sentence containing the word "for" passes whether or not it argues for
anything. Writing "Relevant for template selection" satisfies the code and changes no
decision. The check catches the laziest failure and nothing more; the rest is on the
author.

---

## The mapping

| Finding type | Stage | The decision it bears on | Typical direction |
|---|---|---|---|
| Nearest neighbour by pocket similarity lies outside the target's family | `stage3_prior` (`template-and-finetune`) | Which structures enter `stage3.template_set` and the fine-tuning corpus | FOR ranking candidates on pocket descriptors and admitting non-family structures weighted by measured breadth; AGAINST ranking on sequence identity alone |
| The items to predict for split into two chemically disjoint subpopulations | `stage3_prior` (`confidence-selection`) | Whether one selector serves the whole set, and whether scores are reported per subpopulation | FOR selecting and reporting per subpopulation; AGAINST a single global confidence threshold |
| A prior was derived only from drug-like compounds | `stage2_biochem` (`pocket-anatomy`) and `stage3_prior` | Whether the anchor prior is applied uniformly across items | FOR applying it as an additive bonus only, and AGAINST applying it at all to the subpopulation outside its domain of validity |
| The pocket occupies several distinct states across known structures | `stage2_biochem` (`pocket-dynamics`) | Which states go into `stage2.conformer_ensemble`, and which ligand classes each suits | FOR handing forward more than one state with its suitability labelled; AGAINST collapsing to a single representative |
| Per-residue displacement exceeds the scoring metric's tolerance | `stage3_prior` (`structure-ensemble`) | Whether a single predicted conformer can win at all, and therefore what Stage 3 optimises | FOR widening the pool across receptor states; AGAINST spending the budget refining one state |
| Only one complex exists for the target | `stage2_biochem` (`pocket-anatomy`) | Whether the interaction map is derived from the target alone or from the Stage 1 family corpus | FOR deriving it from the corpus and labelling single-complex contacts as idiosyncratic |
| The two interaction profilers disagree on a residue | `stage2_biochem` (`pocket-anatomy`) | Whether that residue is called load-bearing, and whether the disagreement is kept as a signal | AGAINST promoting a single-profiler contact to required; FOR storing both edges tagged by source and reusing the disagreement as a confidence signal |
| Mutational or conservation evidence supports a residue that is not the closest contact | `stage2_biochem` (`pocket-anatomy`) | Which residues enter `stage2.critical_residues` as required rather than optional | FOR ranking by independent evidence; AGAINST ranking by proximity |
| The obvious template structures are withheld by the challenge | `stage3_prior` (`template-and-finetune`) | Which structures may legally be used as templates | AGAINST using anything named in `ProblemSpec.withheld`; FOR building the template set from homologs and stating the substitution |
| Candidate generators are strongly correlated with one another | `stage3_prior` (`structure-ensemble`) | Which generators to fund with the remaining credits | AGAINST adding another correlated model; FOR buying a decorrelated one or spending on selection instead |
| Pool oracle sits far above realised score | `stage3_prior` (`confidence-selection`) | Where the remaining effort goes | FOR working on selection; AGAINST adding generators |
| Pool oracle sits close to realised score | `stage3_prior` (`structure-ensemble`) | The same decision, the other way | FOR widening the pool; AGAINST further work on the selector |
| Two models report confidence on different numeric scales | `stage3_prior` (`confidence-selection`) | Whether to normalise within model before comparing across models | FOR z-scoring within each model first; AGAINST any direct cross-model comparison of raw scores |
| Ligand-restricted confidence discriminates accuracy while global protein confidence does not | `stage3_prior` (`confidence-selection`) | Which signal `stage3.selection` ranks on | FOR ligand- and interface-restricted signals; AGAINST a global score or a model's default ranking field |
| A secondary metric is statistically decoupled from the graded metric | `all` | Which number any adoption decision is validated against | AGAINST using the decoupled metric for model selection or early stopping; FOR retaining it as a deliberate negative control |
| The validation set is small relative to the spread of results being compared | `all` | Whether an observed improvement is adopted | AGAINST adopting a small win; FOR expanding the validation set first and using expansion as an overfit detector |
| The compound set has one dominant scaffold | `stage3_prior` (`template-and-finetune`) | How the held-out gate is split | FOR a scaffold split; AGAINST a random split, which would report memorisation as generalisation |
| Generation models do not sample the pocket's alternative state | `stage4_optimization` (`dock-and-minimize`) | Whether refinement is expected to correct a state or placement error | AGAINST expecting local refinement to relocate a pose; FOR restricting it to nearly-correct geometry in the failure tail |
| Selected poses in the failure tail clash with a load-bearing residue | `stage4_optimization` (`medchem-pass`) | Whether a coordinate-only edit is applied, and at which tier | FOR a light-tier rigid-body or torsion edit with the whole pass gated on ground truth; AGAINST any free redraw of the ligand |
| Ligand-only force-field relaxation degrades even known-correct geometry | `stage4_optimization` (`dock-and-minimize`) | Whether ligands are minimised in isolation | AGAINST minimising a ligand outside its site under any circumstances |
| The dataset the fine-tuning corpus depends on is behind a registration wall | `stage3_prior` (`template-and-finetune`), plus `data-materialize` | Whether the curriculum can be built as designed | AGAINST planning the corpus around it; FOR recording a `DataRef` with a `fetch_hint` and designing a fallback now |
| Most test compounds carry a group that coordinates heme iron | `stage2_biochem` (`pocket-anatomy`) | Which comparison pockets to profile interactions against | FOR profiling at least one non-family promiscuous pocket, to separate features general to adaptable pockets from features specific to this target |
| Most declared similarity axes were never run | `all` | Whether this stage's neighbour ranking may be relied on downstream | AGAINST relying on it; FOR running the missing axes before any template ranking is trusted |
| External compute for the planned fine-tune has a long activation lag against the deadline | `stage3_prior` (`template-and-finetune`) | Whether the fine-tune path is on the critical path or a stretch goal | AGAINST making it the primary plan; FOR keeping a local fallback and budgeting the lag explicitly |

---

## Worked implications

These are written to the contract exactly, and each one carries an `if_wrong` that names
a downstream failure rather than restating the finding.

### The non-family template

```python
Implication(
    for_stage="stage3_prior",
    decision="which structures enter stage3.template_set and the fine-tuning corpus",
    direction=(
        "Argues FOR admitting promiscuous non-family proteins as comparison and "
        "template structures, weighted by measured breadth of binding rather than by "
        "family membership, because they share the adaptable-pocket problem even though "
        "they do not share the fold."
    ),
    strength=ImplicationStrength.STRONG,
    if_wrong=(
        "The corpus is diluted with folds that share nothing useful, the fine-tune "
        "spends capacity on irrelevant structure, and the template ranking moves away "
        "from the genuinely closest pockets rather than toward them."
    ),
)
```

### The anchor prior and its domain of validity

```python
Implication(
    for_stage="stage2_biochem",
    decision="whether the recurring anchor set is applied as a restraint to every item",
    direction=(
        "Argues FOR publishing the anchor set as an additive bonus scoped to the "
        "drug-like subpopulation, and AGAINST applying it to the fragment "
        "subpopulation at all, because those items engage zero canonical anchors and a "
        "drug-like-trained signal inverts sign on them."
    ),
    strength=ImplicationStrength.DECISIVE,
    if_wrong=(
        "If the anchors do in fact hold for fragments, we lose a real prior on roughly "
        "half the items and give up whatever it was worth. If they do not and we apply "
        "them anyway, every fragment pose is penalised for the absence of a contact it "
        "was never going to make, and the loss is larger than the gain because that "
        "half is scored on the same footing."
    ),
)
```

### Where the remaining Stage 3 effort goes

```python
Implication(
    for_stage="stage3_prior",
    decision="whether the next unit of effort goes to generation or to selection",
    direction=(
        "Argues FOR treating selection as the bottleneck and AGAINST funding additional "
        "generators, because the pool already contains a candidate far better than the "
        "one currently chosen for most items."
    ),
    strength=ImplicationStrength.STRONG,
    if_wrong=(
        "Effort goes into a selector on a pool whose ceiling is already the limit, the "
        "selector cannot improve past that ceiling however good it gets, and the weeks "
        "spent are unrecoverable because the generation budget was released."
    ),
)
```

### Normalising non-commensurable confidence signals

```python
Implication(
    for_stage="stage3_prior",
    decision="how per-model confidence signals are combined into stage3.selection",
    direction=(
        "Argues FOR z-scoring each model's scores across all items before comparing "
        "across models, and AGAINST comparing raw confidence values, because the models "
        "report on different scales and one inflated scale otherwise wins every item."
    ),
    strength=ImplicationStrength.DECISIVE,
    if_wrong=(
        "The selector degenerates into always picking one model, the pool's diversity "
        "contributes nothing, and the failure diagnosis points at the wrong model "
        "because its scores look uniformly confident rather than uniformly rescaled."
    ),
)
```

### A pocket that moves more than the metric tolerates

```python
Implication(
    for_stage="stage3_prior",
    decision="what Stage 3 optimises when the receptor has more than one relevant state",
    direction=(
        "Argues FOR generating against several receptor states and reporting per-state "
        "coverage, and AGAINST optimising a single predicted conformer, because the site "
        "moves further than the scoring tolerance so no one conformer can be correct for "
        "all items."
    ),
    strength=ImplicationStrength.STRONG,
    if_wrong=(
        "The pool is spread thin across states that do not matter, per-item depth falls, "
        "and a set of items that a single well-chosen state would have covered is now "
        "covered worse by every state."
    ),
)
```

### Refinement scope in Stage 4

```python
Implication(
    for_stage="stage4_optimization",
    decision="which items the docking and minimization pass is applied to",
    direction=(
        "Argues FOR restricting refinement to stage3.failure_tail items whose geometry "
        "is already nearly correct, and AGAINST blanket application, because local "
        "refinement polishes a near-correct pose but cannot relocate a misplaced one."
    ),
    strength=ImplicationStrength.SUGGESTIVE,
    if_wrong=(
        "Either the tail is left unrefined when refinement would have rescued it, or "
        "blanket application regresses poses that were already good and the mean hides "
        "both effects."
    ),
)
```

### An illustrative number

```python
Implication(
    for_stage="all",
    decision="whether any similarity score from this run may be used as an input",
    direction=(
        "Argues AGAINST using any score from this graph until the corresponding tool has "
        "actually been run, because every edge weight here was written down as a "
        "placeholder rather than measured."
    ),
    strength=ImplicationStrength.DECISIVE,
    if_wrong=(
        "A placeholder is treated as a measurement, and every downstream ranking "
        "inherits a fabricated ordering while looking fully cited."
    ),
)
```

---

## Implication strength

The four levels are a claim about how much a *reasonable colleague who accepts the
finding* still has left to decide. That is the test, and it is not the same as how
confident you are in the finding itself — a well-established fact can carry a weak
implication, and a tentative one can carry a decisive implication if it would settle the
matter were it true.

**`DECISIVE` — on its own this settles the decision.** Nobody who accepted the finding
could reasonably decide the other way. The withheld-structures case qualifies: if the
challenge rules forbid a structure as a template, there is no remaining judgement to
exercise. So does the placeholder case above, and so does z-scoring before cross-model
comparison, because the alternative is not a different trade-off but an arithmetic error.

**`STRONG` — you would need a good reason to go against it.** The non-family template
implication is here rather than at `DECISIVE`: a stage with a hard credit ceiling could
legitimately decline the extra corpus breadth, but it would have to say why. The test is
whether going against it requires an argument. If it does, it is strong; if it requires
only a preference, it is suggestive.

**`SUGGESTIVE` — it tips the balance.** Profiling one non-family comparison pocket, or
restricting refinement to the tail, belong here. They are worth doing and a stage that
skipped them for lack of time would not be wrong, merely less informed. This is the
contract's default value, and the default is usually right.

**`WEAK` — worth knowing, does not move the decision.** Two compounds sharing a piperazine
is a genuine observation that changes nothing downstream, because the group is almost
certainly a solubility fix rather than a binding element. Recording it as `WEAK` is more
useful than omitting it, because it tells the next reader the question was asked and
answered.

**Most findings are suggestive, and inflating them destroys the set.** A list of
implications in which everything is strong or decisive carries no ordering information at
all, so a reader cannot triage it and will read none of them carefully. Worse, the first
time a `DECISIVE` implication turns out to have been wrong, every other one loses
credibility at once, including the ones that deserved the label. A practical discipline: if
more than roughly one in five of a stage's implications sits above `SUGGESTIVE`, go back
through them and ask of each, out loud, "could a colleague who believed this finding still
reasonably decide otherwise?" Most of the time the answer is yes.

---

## The domain-of-validity problem

A prior is a claim about a population, and the population is part of the claim. An
implication that names the prior without naming its population is not merely incomplete —
it is likely to be applied where it inverts.

The reference case is documented in
`.claude/skills/ai-scientist/reference/pxr-case-study.md`. The test set held two
populations: crystallographic fragments from apo soaks, and larger drug-like analogs. The
fragments were chemically remote from every known holo ligand of the target and often
engaged **zero** canonical pocket anchors. Any signal trained on drug-like compounds
*inverted sign* on them — confirmed four times independently, with a per-family neural
network, a convolutional scoring model, a gradient-boosted model on a structural affinity
set, and a molecular-representation model on a bioactivity database. Four different model
families, one conclusion: the prior did not weaken on the fragment half, it pointed the
wrong way.

Two things follow for how implications are written.

**The population goes in `direction`, not in a footnote.** Compare:

```python
# Wrong. True on average, actively harmful where it is not.
direction="Argues FOR applying the anchor prior when scoring poses."

# Right. The scope is part of the claim.
direction=(
    "Argues FOR applying the anchor prior as an additive bonus to the drug-like "
    "subpopulation only, and AGAINST applying it to the fragment subpopulation, whose "
    "members engage none of these anchors."
)
```

The first version passes every mechanical check in the contract. It is the more confident
sentence and it is the one that costs points.

**The failure mode goes in `if_wrong`, and it is not the same field as `revisit_if`.** This
distinction gets conflated constantly. `if_wrong` lives on the `Implication` and answers
"what breaks downstream if this interpretation is mistaken" — it makes the implication
reviewable. `revisit_if` lives on the `ReasoningStep` and answers "what observation should
reopen this decision" — it stops a choice outliving its reason. For a domain-scoped prior
you generally want both: `if_wrong` naming the inversion on the out-of-scope population,
and `revisit_if` naming the measurement that would tell you the scope was drawn in the
wrong place.

Three structural consequences of this problem are already built into the pipeline, and an
implication that ignores them is arguing against the design rather than within it.
`stage1.subpopulations` exists as a handoff key so that scope has somewhere to be recorded
and something for downstream stages to group by. `pocket-anatomy` is required to state
whether each anchor is *required or optional* and which subpopulations its interaction map
is valid for, with anchors treated as additive bonuses and never as penalties for absence
unless there is evidence otherwise. And both `template-and-finetune` and
`confidence-selection` require a per-subpopulation figure, because the failure this whole
section describes is invisible in an average: a fine-tune or a selector can improve the
overall number while regressing the half that carries the points, and it will look like
progress in every summary statistic anyone is likely to read.

A last note on honesty. When a prior's domain of validity is unknown rather than known to
be narrow, say that instead of guessing the scope. "Argues FOR applying this prior to the
drug-like items, and AGAINST extending it to the fragment items until it has been tested
there, because the two populations share almost no chemistry" is a defensible implication.
Silently applying it everywhere and describing the result as a prior is not, and it is
the specific mistake this project's Stage 1 exists to prevent.
