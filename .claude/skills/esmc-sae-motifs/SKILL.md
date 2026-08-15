---
name: esmc-sae-motifs
description: >-
  Stage 1. Use sparse-autoencoder features over a protein language model
  (ESM-C) to find structural or functional motifs the target shares with other
  proteins, including motifs that sequence and fold search miss. Emits Motif
  nodes and SHARES_MOTIF edges, but only for features that survive a
  structural interpretation check. Use for the motif similarity axis, or when
  conventional homology search returns nothing useful. Trigger on: "structural
  motif", "SAE features", "ESM-C", "latent features", "what motifs does it
  share", or /esmc-sae-motifs.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
---

# ESM-C sparse-autoencoder motifs

Protein language models encode structure and function in superposed features; a
sparse autoencoder over the residue embeddings can pull individual features apart.
Some correspond to recognisable motifs — a catalytic triad, a hydrophobic pocket
lining, a dimerisation surface. This axis finds neighbours that share those
features, which is exactly the set that sequence identity and fold similarity can
both miss.

It is also the axis most likely to produce confident nonsense, so the bar is high.

## Guard rails

- **A feature is not a motif until it has a structural interpretation.** An SAE
  feature index is a number. Before emitting a `SHARES_MOTIF` edge you must be
  able to say *what* the feature fires on, verified against structure or
  annotation. Unverified features go in the report as `open_questions`, not in the
  graph.
- **Verify with a negative control.** Check the feature does *not* fire on a
  matched set of unrelated proteins. Without that, high activation is
  uninformative — many features fire on everything.
- **Report activation, position, and context.** A feature firing on 3 contiguous
  residues in a helix is a different claim from the same feature firing scattered
  across a domain.
- **Confidence caps at `tentative`** for a motif supported only by feature
  similarity. Promote to `supported` only when structure or literature
  independently backs it.
- **Record the model and SAE checkpoint** in every edge's `attrs`. Features are
  not portable across checkpoints, and an unlabelled feature index is unusable
  six weeks later.

## Workflow

1. **Embed** the target and the candidate set (Stage 1's family and promiscuity
   neighbours are the natural pool) with ESM-C. Record model id and layer.
2. **Encode with the SAE** to per-residue sparse feature activations.
3. **Select the target's characteristic features**: high activation on the region
   of interest (e.g. the pocket-lining residues Stage 2 cares about), low
   elsewhere. Specificity matters more than magnitude.
4. **Interpret each candidate feature.** Which residues does it fire on across
   many proteins? Do those positions share a known annotation (InterPro, PROSITE)
   or a 3D arrangement? Name it, or discard it.
5. **Negative control.** Confirm it does not fire on a matched unrelated set.
6. **Score sharing** between the target and each candidate on the surviving
   features, and emit `Motif` nodes plus `HAS_MOTIF` / `SHARES_MOTIF` edges.

## Required visuals

- **Feature activation heatmap**: residue position x feature, for the target, with
  the region of interest marked.
- **Motif-sharing matrix**: candidate proteins x interpreted motifs.
- For the top motifs, a **structure render** with the firing residues highlighted
  — the figure that turns a feature index into a claim a biochemist can judge.

## Handoff

`motif.features` and `kg.motif_nodes`. For each motif: an interpretation, the
residues involved, the negative-control result, and the checkpoint it came from.
Motifs that failed interpretation belong in `limitations` — that is a real result
about the method, and hiding it invites someone to repeat the work.
