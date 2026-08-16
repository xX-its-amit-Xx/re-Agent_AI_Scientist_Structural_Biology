---
name: template-and-finetune
description: >-
  Stage 3. Inject the biological prior into the model itself, via structural
  templating and curriculum fine-tuning on the corpus Stage 1 assembled.
  Escalates specificity in stages with decreasing learning rate, and gates
  every checkpoint against held-out complexes before it is allowed near a
  prediction. Use when a general model underperforms on a specific target
  family, or when a curated corpus with sample weights is available. Trigger
  on: "fine-tune", "curriculum", "structural template", "LoRA", "transfer
  learning", "train on the family", or /template-and-finetune.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
---

# Template and finetune

**Owner: Sumer.** The two ways to inject what is already known about a target
into generation: hand the model a measured structure to start from, or adapt the
model's weights to the family.

Judge both by the same test — does the pool's oracle improve? A template set that
does not widen the pool has bought nothing, however respectable its provenance.

## The honest prior on fine-tuning

In the reference case the entry that *won* did so with a federated fine-tune on
four pharma companies' proprietary crystal structures, beating a strong
z-hybrid selector by 0.0085. The lesson is uncomfortable and worth stating
plainly: **that gap was closed by data, not by method.**

Recognising which gaps are closeable by cleverness and which only by data is
itself the judgement this skill exists to exercise. Before proposing a fine-tune,
say what corpus makes it plausible, and if the honest answer is "we do not have
one comparable to theirs", say that instead of spending the compute.

## Guard rails

- **Never template from the answer.** If ground truth exists locally for
  evaluation, it is not a template source. The leak is invisible in the final
  score because the score is computed from the same files. Template only from
  independently published structures.
- **Check the holdout for template leakage too.** A published structure that *is*
  one of your evaluation targets is the same leak wearing a citation.
- **Prefer measured coordinates to predicted ones.** A re-refined crystal
  structure is evidence; a predicted receptor is a hypothesis, and templating from
  one launders a guess into an input.
- **Templates narrow as well as widen.** A single template pulls every sample
  toward one conformation, which is the opposite of what `structure-ensemble`
  wants. Template from *several* structures spanning the conformational range, or
  measure the diversity you lost.
- **Fine-tuning is a `Proposal`, not a default.** It is the most expensive thing
  in Stage 3. State the corpus, the falsifiable prediction, the kill criterion,
  and the cost; get an accepted decision before spending.
- **Respect each template's domain of validity.** A structure solved with a very
  different ligand class may not describe the pocket your ligands see.

## Choosing a template set

1. **Inventory what is actually measured.** For this target,
   `manifest/receptors.csv` holds 64 re-refined receptor structures — 44
   re-refined plus 20 original depositions kept because re-refinement did not
   improve them. Which coordinate set won is recorded per entry; prefer the
   selected one.
2. **Cluster by pocket conformation, not sequence.** The receptors are near-identical
   in sequence and differ in the thing that matters — pocket shape. Cluster on
   pocket geometry and pick representatives across clusters.
3. **Carry the awkward cases deliberately.** Six of the 64 structures have **two
   ligands bound at once**, which is real information about a promiscuous pocket
   rather than a parsing error. Decide explicitly whether to include them.
4. **Watch the format.** Two of the 64 ship mmCIF only and need conversion before
   any PDB-only tool sees them. A silently skipped template is a quietly narrower
   template set.

## If a fine-tune is accepted: the curriculum

Escalate specificity in stages, dropping the learning rate at each step, so the
model is nudged toward the family rather than yanked into it:

1. **Broad** — all protein-ligand complexes in the Stage 1 corpus, highest LR.
2. **Family** — the receptor's family (here, nuclear receptors), LR reduced.
3. **Target** — the target's own measured complexes, lowest LR, fewest epochs.

Two rules make this safe rather than merely elaborate:

- **Gate every checkpoint against held-out complexes before it is allowed near a
  prediction.** A checkpoint that improves training loss and not held-out score is
  memorising the corpus, and the later, most-specific stages are exactly where
  that happens. Keep the last checkpoint that passed, not the last one produced.
- **Split the holdout by family, not at random.** A random split leaves near-duplicate
  complexes on both sides and reports a score that will not survive contact with a
  new target.

Prefer a low-rank adapter over full fine-tuning unless the corpus is genuinely
large: it is cheaper, it is reversible, and when it fails it fails visibly rather
than by quietly degrading the base model's generality.

## What Stage 2 tells you, and what it forbids

If Stage 2 reports a flexible pocket, templating becomes more attractive and
fine-tuning less so — co-folding models sample receptor plasticity poorly (zero
alternative conformations in twenty attempts, in the closest published study), so
supplying the alternative conformation directly is one of the few ways to get it
into the pool at all.

That same finding means: do not claim a fine-tune will teach the model to explore
plasticity. It will not.

## Required visuals

- **Template coverage map**: pocket-conformation clusters against which templates
  were selected, showing what the set spans and what it misses.
- **Oracle-with-vs-without-templates**, since that is the only test that matters.
- **Fine-tune learning curve** against a held-out family split, if a fine-tune is
  ever accepted.

## Anti-patterns

- **Templating from the single highest-resolution structure.** Resolution is not
  representativeness, and it collapses pool diversity.
- **Fine-tuning because compute is available.** The reference case says the
  winning margin came from proprietary data; without a comparable corpus you are
  buying a much smaller effect at a much larger cost.
- **Reporting fine-tune improvement on the training family.** Split by family and
  report held-out, or the number means nothing.
- **Silently dropping templates that fail to parse.** Record the failure; a
  narrower set reached by accident is not a decision.

## Handoff

`stage3.finetuned_model` (weights plus the corpus and split that produced them)
and `stage3.template_set` (the selected structures, with why each was chosen and
what conformational range the set spans).
