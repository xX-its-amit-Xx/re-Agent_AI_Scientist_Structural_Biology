---
name: compound-neighborhood
description: >-
  Stage 1. Map the chemical space around the items a pipeline must predict
  for, and quantify how far they sit from the compounds anything was trained
  or measured on. Produces chemotype clusters, a scaffold census, and the
  train/test similarity distribution that decides whether one model can serve
  the whole test set. Use when characterising test compounds, choosing a
  chemical split, or checking whether a chemical prior will transfer. Trigger
  on: "what compounds are similar", "chemical space", "scaffold split",
  "chemotype", "will this prior transfer", or /compound-neighborhood.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, Agent
---

# Compound neighbourhood

Characterise the chemistry we must predict for, and measure its distance from the
chemistry anything was trained on. The second half is the point.

## Guard rails

- **Report distributions, never means.** A mean similarity of 0.45 is compatible
  with a unimodal set and with two disjoint clusters at 0.2 and 0.7, and those
  demand different pipelines. Bimodality is the finding.
- **Run this on the TEST items, not on the target's known ligands.** The gap
  between them *is* the domain shift, and it is the single most decision-relevant
  number Stage 1 produces.
- **A similarity threshold is a modelling choice, not a fact.** State the
  fingerprint, radius, and metric with every number. Morgan-r2 Tanimoto 0.3 is
  not comparable to MCES 0.3.
- **NEVER assume a chemical prior transfers across a chemotype gap.** In the
  reference case, signals trained on drug-like ligands *inverted sign* on the
  fragment half of the test set — confirmed four independent ways. Report the
  domain of validity, not just the prior.

## Workflow

1. **Load the test manifest** from `ProblemSpec.test_items`. Standardise every
   structure (neutralise, strip salts, canonical tautomer) before any comparison;
   unstandardised SMILES silently inflate dissimilarity.
2. **Census the scaffolds** — Murcko and generic-Murcko frameworks, with counts.
   A scaffold appearing once is a different prediction problem from one appearing
   forty times.
3. **Build the reference set**: known binders of the target and its Stage 1
   neighbours, from ChEMBL/BindingDB plus co-crystallised ligands in the graph.
4. **Compute nearest-neighbour similarity** from each test item to the reference
   set. Report the full distribution plus the fraction below 0.3, which is the
   conventional "no useful analogue" line.
5. **Cluster into chemotypes** and check whether the clusters align with any
   physicochemical property split (heavy atoms, rotatable bonds, logP). If they
   do, that property is your subpopulation label and Stage 3 should route on it.
6. **Emit** `SIMILAR_COMPOUND_TO` and `SHARES_SCAFFOLD` edges with the
   fingerprint recorded in `attrs`, plus `Compound` and `Fragment` nodes.

## Required visuals

- Nearest-neighbour similarity **histogram**, with the subpopulation split marked.
- Chemotype cluster map (UMAP or MDS over fingerprints), coloured by
  subpopulation — the figure that shows whether the test set is one problem or two.
- Scaffold census as a ranked bar chart.

## Handoff

`stage1.compound_neighbourhood` and `stage1.chemotype_split`, the latter being the
labels Stage 3 routes on. Include, for each subpopulation: n, median
nearest-neighbour similarity, and which priors are valid for it.
