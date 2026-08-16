# The side-by-side part view: what each channel means

The interaction: **click a node, shift-click a second, see the two parts and their contacts
next to each other, with the graph's own explanation of why they belong together.**

Three surfaces, in the order a reader meets them.

---

## 1. The ego view's pair panel

Click a node — it isolates its neighbourhood, as before. **Shift-click** a second and the
sidebar panel appears with:

- both labels,
- every direct edge between them: predicate, confidence, the first numeric attribute, citation
  count, and a `placeholder` chip when `illustrative` is set,
- **the edge's `commentary`**, or a stated absence,
- the `compare_parts` command, with a copy button.

When there is no direct edge it lists shared neighbours instead, because *"no direct edge"* and
*"unrelated"* are different claims and the intermediate is usually the interesting part. Two
fragments of the same compound come back as `HAS_FRAGMENT · SR12813 · HAS_FRAGMENT`, which is
the correct and useful answer.

Selection is marked on the nodes themselves: pick A gets a solid blue border, pick B a double
vermillion one. **Two channels, border colour and border style**, so the pair is legible
without relying on hue.

A static page cannot render 3D on demand — it has no Python. So it does the half it can do
honestly and immediately, and hands over the command for the half it cannot.

## 2. `compare_parts`, the 3D page

### Why it leads with the connection

The block above the panels is not decoration. A reader shown two things side by side asks *why
are these together?* before anything else, and the answer is already in the graph. Rendering it
from `KGStore.between()` rather than asking the caller to retype it means the sentence a med
chemist reads here is the same sentence Stage 3 will be handed.

Three states, all explicit:

| State | What the page says |
|---|---|
| direct edge | predicate, confidence, score, citations, and the commentary |
| no direct edge | *"connected through N shared neighbours"* and lists them, framed as the weaker claim it is |
| nothing passed | *"why these two are side by side is not recorded"* — the judgement was made outside the graph and is not auditable from this page |

That third row matters. A comparison view that silently renders any two things invites the
reader to assume a relationship exists.

### Encoding

| Channel | Encodes | Why not the obvious alternative |
|---|---|---|
| stick colour on the ligand | **interaction kind** | CPK colouring answers "which atom is nitrogen", which the reader already knows. What they cannot see is which contacts constrain the pose. |
| dashed connector | **directional contact** | The redundant channel required once the palette exceeds ~8 categories — and it carries the more decision-relevant half: a directional contact is a constraint a wrong pose violates, a hydrophobic one is satisfied by any nearby apolar atom. |
| stick residues | residues in contact with **this part** | Not the whole pocket. Showing all lining residues buries the three that matter. |
| thin lines on the rest of the ligand | the part in its whole | So a fragment reads as *part of* a molecule rather than a molecule. |
| cartoon at 0.22 thickness, 55% opacity | the protein, as context | The backbone is the setting, not the subject. Full-opacity cartoon makes the pocket the smallest thing on screen. |
| zoom | **the part**, at 1.5× | The single biggest legibility win over `compare_structures`, where both ligands are two pixels of hetero-atom. |
| left/right position | which of the two selected nodes | Cameras stay linked, because comparing two poses by eye needs them held in the same orientation. |
| table row with a coloured left edge | interaction occurs on **both** sides | Shared rows sort first: that is the transferable part. |

`ColorMap` declares all of this, and its validator is what forced the redundant channel — ten
interaction kinds exceed the categorical-colour ceiling, and the honest fix was to pair colour
with dashing rather than to pretend ten hues are discriminable.

### What the page refuses to claim

Printed in the page, not just in the docstring:

> **This view does not claim the two sides are positionally equivalent.**

Two proteins number their residues differently. Deciding that Ser247 in one *is* Ser208 in the
other requires a sequence-guided superposition — which `compare_structures` computes and
labels an estimate. So the shared-interaction table compares **interaction kinds and residue
identities**, which the coordinates support directly, and says so.

This is the same discipline as the `illustrative` flag: state the limit where the reader meets
it, not in a methods section they will not reach.

### The geometry fallback, and why it shouts

With no `CONTACTS` edges in the graph, `compare_parts` derives contacts from distance and
returns:

> no CONTACTS edges in the graph, so contacts were derived from geometry (4.5 Å from the
> ligand) and every one is typed 'hydrophobic' by default. Interaction kinds require a
> profiler — run pocket-anatomy.

Loud on purpose. A page full of "hydrophobic" contacts looks like a result and is a list of
neighbours. The alternative — silently typing everything hydrophobic — would produce a
confident-looking figure asserting something nobody measured.

## 3. `explain_pair`, the cheap one

Ask this first. It is one query, no coordinates, and most of the time it is the whole answer:
the predicate, the score, whether it is a placeholder, the citation count, and the commentary.
Rendering 1 MB of 3D to read a sentence that was already in the graph is the wrong order.

## Controls

| Control | Default | What it is for |
|---|---|---|
| Part only / Part plus pocket | part only | Whether non-contacting lining residues are drawn. Off by default so the contacts read. |
| Pocket surface | off | Shape of the sub-region. Useful for "does this fragment fill the lobe?", noise otherwise. |
| Residue labels | on | Off for a figure going into a slide with its own annotation. |
| Directional only | off | **Hides hydrophobic contacts.** The fastest way to see what actually constrains a pose. |
| Re-centre | — | After manual rotation. |

## Implementation notes worth not relearning

- **`createViewerGrid` is called exactly once.** It appends one shared canvas and splits it into
  cells; calling it per side appends a second canvas and the panes desync. The captions live
  outside the grid container for the same reason.
- **Write with `newline=""`.** A CRLF inside the inlined JS breaks a regex literal. This has
  cost an afternoon once already.
- **`PartView` accepts a `Ligand` where a residue name is expected.** `primary_ligand()`
  returns a `Ligand`, which is what a caller has in hand, and passing it through failed much
  later with a JSON encoding error that said nothing about the cause.
- **Slugs are sanitised.** A SMARTS pattern is a legal node id and a hostile filename;
  brackets and equals signs survive on disk and then need escaping in every URL. The real ids
  stay inside the page.
- **Pages are ~1 MB** — 3Dmol at 538 KB plus two copies of the coordinates. Under the 16 MB
  publish ceiling with room to spare, but do not batch-render hundreds.
