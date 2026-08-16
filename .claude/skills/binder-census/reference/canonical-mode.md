# Does a reference binding mode exist?

The question behind *"the binding mode intended for this target."* It has three possible answers
and the middle one is the one most often needed.

| Answer | What it means | `is_defined` |
|---|---|---|
| **Yes** | An endogenous ligand, substrate or cofactor whose pose is the reference | `True` |
| **No, and that is the function** | Breadth is what the protein was selected for | `False` |
| **Unknown** | Not yet established either way | `False`, with `why` saying so |

The second and third are different and must not be collapsed. "Breadth is the function" is a
positive claim with consequences; "we have not found out" is a gap.

## The PXR case, worked

PXR is a xenobiotic sensor. Its job is to notice chemicals the organism has never encountered,
which means **a pocket shaped for one molecule would fail at the job**. Low selectivity is the
adaptation, not a defect of the assay.

Candidate endogenous ligands have been proposed — bile acids such as lithocholic acid, and some
pregnane steroids — but none is uncontested, and none accounts for more than a fraction of the
observed ligand set. The pocket volume varies substantially across holo structures with different
ligands, and the ligands themselves span roughly an order of magnitude in molecular weight.

So the honest record is:

```python
BindingModeReference(
    target_id="uniprot:O75469",
    is_defined=False,
    why=(
        "A xenobiotic sensor selected for breadth: recognising chemicals the organism has not "
        "encountered is the function, so no single endogenous pose can be a reference. Bile "
        "acid and pregnane candidates are proposed and contested, and none accounts for more "
        "than a fraction of the observed ligand set."
    ),
    anchor_policy="additive",
    conformational_range=(
        "pocket volume spans roughly 1150-1650 A^3 across five holo structures; an ensemble "
        "must cover that range rather than the best-resolution single conformer"
    ),
    anchor_residues=["Ser247", "Gln285", "His407", "Arg410"],
)
```

Note that `anchor_residues` is still populated. Anchors exist and recur; what the undefined mode
forbids is *requiring* them.

## Why the policy field is a validation error and not advice

`anchor_policy="required"` with `is_defined=False` raises. That guard exists because of a specific
measured failure in this project's reference case:

> Fragment ligands engaged **zero** canonical anchors. An anchor-based prior applied uniformly
> **inverted** on the fragment half of the test set — predictions got worse, and the prior looked
> better-informed than having none.

That is the shape of the error worth remembering: not a missed opportunity but an active
regression, produced by a reasonable-sounding assumption, in the subpopulation nobody checked.
A uniform prior over a heterogeneous test set is a bet that the set is homogeneous.

So:

- **`additive`** (default) — engaging an anchor is a bonus; not engaging one is never a penalty.
- **`required`** — needs an argument that *every subpopulation* engages them, and the contract
  demands that argument be more than a sentence. Fragments, covalent binders and allosteric
  ligands routinely do not.

## When a mode *is* defined

An enzyme with a known substrate, a receptor with a characterised hormone, a protein with an
obligate cofactor. Then:

- `reference_binders` names the binders and `reference_structures` the complexes. A mode with no
  pose is an assumption, and the validator rejects it.
- `anchor_residues` are the residues the reference pose engages.
- **The reference is still not a requirement for other ligands** unless argued. A designed
  inhibitor that beats the natural substrate on affinity may well engage a different subset.

And a check that catches a subtle failure: if a mode is claimed as defined but the census contains
no endogenous, substrate, product or cofactor binder, `problems()` flags it. The reference is then
resting on drugs and tool compounds — which describe what medicinal chemistry achieved, not what
the protein is for. That is a legitimate thing to have and an illegitimate thing to call the
intended mode.

## What an undefined mode changes downstream

Concrete, and it belongs in the report's `implications` rather than being left for Stage 3 to
infer:

**Stage 2** — do not build a pharmacophore from the union of all ligands. Ligands binding in
different modes give a consensus pharmacophore satisfied by nothing.

**Stage 3** — size the ensemble to `conformational_range`, not to resolution. And do not select a
single template by best resolution: the clearest structure is the one that crystallised best,
which is not the one that represents the range.

**Stage 4** — no uniform anchor bonus in scoring. If anchors are used, they are additive and
per-subpopulation.

**Reporting** — say it plainly in the plain-language summary. *"This protein has no single
intended shape for the molecules it binds; that is what it is for, and it is why one reference
structure is not enough."* That sentence is more useful to a non-specialist than any pocket
statistic.

## Establishing it

Mostly a literature question, not a database one. Databases record what was crystallised; *"this
is the physiological ligand"* is a claim someone argued in prose.

1. **Search for the endogenous-ligand claim directly**, and for its rebuttals. A contested
   endogenous ligand is where `neglected-literature` earns its place — the dissenting
   low-citation paper is exactly the thing a citation-ranked search buries.
2. **Check the mechanism class.** Sensors, xenobiotic handlers and promiscuous transporters are
   *selected* for breadth. Enzymes, hormone receptors and structural proteins usually are not.
   This is a strong prior and should be stated as one.
3. **Measure the conformational spread** across holo structures. A pocket whose volume varies by
   40% across ligands does not have one shape to be a reference.
4. **Check whether ligand classes cluster by pose.** If drugs bind one way and fragments another,
   there is no single mode regardless of what the endogenous story says — and that split is the
   subpopulation the uniform prior will fail on.

Record the answer either way. **"We looked and there is no canonical mode" is a finding**; the
absence of the field is not, and the next run will assume one exists.
