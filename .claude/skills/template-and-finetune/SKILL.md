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

# Template and fine-tune

**Owner: Sumer.** Contract-complete stub — replace the body, keep the interface.

## Guard rails

- **Gate every checkpoint against held-out complexes.** A fine-tune that does not
  beat the public model on held-out ground truth is a regression with extra steps.
  Make this gate the first thing you build, not the last.
- **Escalate specificity, decay the learning rate.** Broad and general first,
  narrow and specific last, with the interface weight rising as the corpus
  narrows. A single-stage fine-tune on the narrow corpus overfits.
- **Use the sample weights Stage 1 supplied.** They encode which corpus members
  resemble the target and are the difference between a curriculum and a shuffle.
- **Beware activation lag on external platforms.** In the reference case, external
  compute had a ~12-week practical activation lag against a 30-day window, and
  **0 of 8** attempts produced a submittable output. Budget accordingly, and keep
  a local fallback.
- **Templating is often illegal.** Check `ProblemSpec.withheld` before using any
  structure as a template; a blind challenge usually forbids the obvious ones.

## The reference curriculum, as a starting point

Four stages of escalating specificity over a corpus assembled by Stage 1:

| Stage | Corpus | Steps | LR | Interface weight |
|---|---|---|---|---|
| 1 | broad drug-like complexes | 2000 | 3e-4 | 1.0 |
| 2 | promiscuous target classes | 1500 | 1e-4 | 1.5 |
| 3 | the target's full family, weighted (target 3x, close homologs 2x, rest 1x) | 800 | 5e-5 | 2.0 |
| 4 | the target's own complexes | 350 | 2e-5 | 3.0 |

Other settings that mattered: ligand-pocket cropping on, 3 recycles, bf16, EMA
0.999, gradient clipping 1.0, checkpoint and evaluate every 100 steps.

Note this path was packaged but **never produced a scored result** in the reference
work, so the table is a credible starting configuration, not a validated recipe.
Treat it as a hypothesis and gate it like one.

## Required visuals

- **Training curves per curriculum stage**, with the held-out gate line drawn on.
- **Before/after per-subpopulation comparison** — a fine-tune that helps the
  family average while hurting the hard subpopulation is a net loss.
- **Corpus composition chart** showing what the model actually saw at each stage.

## Handoff

`stage3.finetuned_model` (checkpoint plus its gate result, or an explicit
statement that it failed the gate) and `stage3.template_set`.
