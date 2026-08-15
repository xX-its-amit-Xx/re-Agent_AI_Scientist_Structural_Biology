# The visual grammar

Every channel, what it encodes, and why. Written down because a figure whose
encoding is undeclared cannot be checked against its data, and an unchecked figure
is an assertion with a picture attached.

The authoritative values live in `reagent/contracts/kg.py`
(`FAMILY_COLOR`, `PREDICATE_FAMILY`, `DASH_CYCLE`, `HIDDEN_BY_DEFAULT`) and
`reagent/viz/graph_html.py` (`NODE_COLOR`, `NODE_SHAPE`). This document explains
the reasoning; the code is the source of truth.

## The channel assignment

| Channel | Encodes | Range |
|---|---|---|
| ring radius | graph distance from the focal node | 0 = focus, then outward |
| node fill | entity type | 15 types |
| node shape | entity type (redundant with fill) | 15 silhouettes |
| node size | degree, capped | 14-54 px |
| edge stroke colour | predicate **family** | 9 families, ≤7 visible at once |
| edge dash pattern | predicate within its family | 6 patterns |
| edge width | similarity score, normalised within its axis | 1.2-8.0 px |
| edge opacity | confidence | 0.32 / 0.55 / 0.80 / 1.00 |
| edge arrowhead | direction | always shown |

Two channels are deliberately redundant. **Node shape duplicates node fill** so
the figure survives greyscale printing and colour-vision deficiency. **Dash
duplicates nothing but subdivides colour**, which is what makes nine families
tractable.

## Why colour encodes a family, not a predicate

There are about thirty predicates in the controlled vocabulary. The ceiling for a
categorical palette that a colour-blind reader can reliably distinguish is roughly
eight — ColorBrewer's qualitative sets top out around twelve with only small
colour-blind-safe subsets, and Okabe-Ito, the standard safe palette, has eight.
Assigning thirty hues would produce a figure that no one, colour-blind or not,
could read by legend lookup.

So predicates collapse into nine semantic families, colour encodes the family, and
the exact predicate is recoverable two ways: the dash pattern within the family,
and the hover tooltip. Interaction replaces discrimination — colour only has to
narrow the field, not identify.

The families:

| Family | Colour | Predicates |
|---|---|---|
| structural | `#0072B2` blue | `SIMILAR_FOLD_TO`, `SIMILAR_POCKET_TO`, `SHARES_MOTIF` |
| sequence | `#56B4E9` sky blue | `SIMILAR_SEQUENCE_TO` |
| chemical | `#009E73` bluish green | `SIMILAR_COMPOUND_TO`, `SHARES_SCAFFOLD` |
| interaction | `#CC79A7` light reddish purple | `BINDS`, `CO_CRYSTALLIZED_WITH`, `PROMISCUOUS_WITH`, `MODULATES`, `COMPETES_WITH` |
| method | `#D55E00` vermillion | `USED_IN`, `EVALUATED_ON`, `OUTPERFORMS`, `FAILS_ON`, `ALTERNATIVE_TO` |
| analogy | `#E69F00` orange | `ANALOGOUS_TO`, `ORIGINATES_IN`, `INSPIRES` |
| data | `#6A3D9A` deep purple | `HAS_DATA`, `MEASURED_BETWEEN` |
| composition | `#454545` dark grey | `HAS_STRUCTURE`, `HAS_POCKET`, `POCKET_LINED_BY`, `HAS_MOTIF`, `HAS_FRAGMENT`, `MEMBER_OF_FAMILY` |
| evidence | `#A6A6A6` light grey | `SUPPORTED_BY`, `CONTRADICTED_BY`, `MEASURED_IN`, `SIMILAR_ASSAY_TO`, `DERIVED_FROM`, `DATASET_COVERS` |

Structural and sequence are adjacent blues on purpose: they answer nearby
questions, and a reader who confuses them has made a small error rather than a
category error. Interaction (light pink) and data (deep purple) are separated by
lightness as well as hue, since they are the pair most likely to co-occur.

Nine families against a stated ceiling of eight is safe for one reason: **at most
seven are ever visible simultaneously**, because both grey families are hidden by
default. The two greys are dark and light respectively and never compete, because
they are never both shown.

## Why two families are hidden by default

`evidence` and `data` are correct, essential, and ruinous to display.

Every claim links to at least one source, so `SUPPORTED_BY` edges typically
outnumber every substantive edge combined. Every entity worth studying has data
pointers. Drawn by default, they form a dense grey mat under the actual science.

They are one checkbox away, never gone. And they answer questions a reader asks
*deliberately* — "who says so?", "where do I get the numbers?" — rather than
questions asked incidentally while scanning the structure of the graph.

## Why width is normalised within its axis

This is the encoding rule that matters most, because breaking it misinforms rather
than merely confusing.

A TM-score of 0.8 means "these folds are essentially the same". A Morgan-r2
Tanimoto of 0.8 means "these molecules share most of their substructure". A
sequence identity of 0.8 means something else again. They are not the same claim,
and they do not live on the same scale — a Tanimoto of 0.3 is a meaningful signal
in chemical space, while a TM-score of 0.3 is noise.

So `AxisSpec.score_range` declares each axis's honest range, and width maps the
score into 1.2-8.0 px *within that range*. An edge whose predicate has no declared
axis draws at minimum width, so an unscored edge never looks stronger than a
measured one.

## Multiple metrics on one edge

The store merges `attrs` when the same triple is asserted twice, so an edge
accumulates every metric anyone measured for that relationship:

```
uniprot:O75469 --SIMILAR_FOLD_TO--> uniprot:Q14994
  attrs: {tm_score: 0.87, rmsd: 1.9, aligned_len: 241,
          sae_feature_overlap: 0.81, shared_pocket_residues: 19}
```

Width comes from the axis's declared `score_key`; everything else appears on hover
and is queryable in SQL. Adding metrics therefore costs nothing visually, and
**disagreement between metrics on one edge is a finding** worth annotating.

## Truncation must be visible

The renderer extracts a k-hop neighbourhood with a per-node fan-out cap, keeping
the strongest edges first. It records which nodes were capped and how many edges
fell outside the depth horizon, and prints that in the page subtitle.

This is not politeness. A figure that hides its own truncation reads as "this is
everything", and a reader who believes that will draw a wrong conclusion about
sparsity. `EgoSubgraph.truncation_note()` produces the sentence; do not suppress it.

## Ring spacing

Concentric layout with `minNodeSpacing` scaled to the busiest ring's population. A
focal node in a dense graph puts most of its neighbours on ring 1, and a fixed
spacing then packs them shoulder to shoulder — legible in a small demo, a solid
band in a real graph. Scaling the spacing keeps the ring readable at the cost of a
larger canvas, which is the right trade because the canvas pans.

## Interaction, and why it is part of the encoding

Static encoding does the coarse work; interaction does the precise work.

- **Hover an edge** for the exact predicate, every attribute, the confidence, and
  the citations. This is where the graph stops being a picture and becomes evidence.
- **Click an edge** to isolate that predicate across the whole graph — the fastest
  way to see one axis alone.
- **Click a node** to isolate its neighbourhood.
- **Family checkboxes** to add or remove whole layers.
- **Search** to locate and centre an entity by label or id.
- **Layout toggle** between concentric rings (structure by distance) and force
  (structure by clustering). They answer different questions and neither dominates.

## Accessibility

Okabe-Ito throughout, with shape redundant to node colour and dash redundant to
edge family. Opacity carries confidence rather than a separate hue, which keeps
the categorical channel uncluttered. The page is theme-aware: a full light palette
on bare `:root`, redefined under `prefers-color-scheme: dark` guarded against an
explicit light choice, and again under `[data-theme="dark"]`, so it renders
correctly whether the viewer has chosen a theme or left it on system default.

Alt text on every `Visualization` describes the encoding rather than repeating the
title, because a reader who cannot see the figure needs to know what the channels
mean before the takeaway means anything.
