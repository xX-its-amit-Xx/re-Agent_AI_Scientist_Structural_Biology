# Analogous cascade roles

The axis nothing else can reach.

Every other axis relates two proteins by something they *share*: sequence, fold, motif, pocket,
partner, pathway, tissue. This one relates them by **the shape of the slot they occupy in
otherwise unrelated networks**. Two proteins can each be the xenobiotic sensor of their own
cascade — same trigger class upstream, same effector class downstream, same feedback structure —
and share no homology, no pathway, no partner, and no tissue.

No similarity search returns that, because there is no similarity to measure. It has to be
reasoned about, which is exactly why an agent optimising for apparent progress skips it.

## Why bother

Three payoffs, in increasing order of value.

**Template donors from outside the family.** If the pocket problem is set by the *role* — an
adaptable pocket because the job is to detect arbitrary foreign molecules — then a
role-analogue's structures are informative about the conformational range even at 15% identity.
A rigid family member is less useful.

**Transferable modelling decisions.** Whoever solved the analogue's cascade faced the same
structural problem and published what worked. That is a method transfer with a stated
precondition, which is the strongest kind available.

**Negative results with a reason.** If the analogue's cascade is known to defeat single-conformer
docking, that is a specific, mechanistic prediction about our target, not a vague caution.

## Finding them

### 1. Abstract the role

Write the target's position as a *role signature*, deliberately stripped of identity:

```
trigger:    small hydrophobic molecule, structurally unconstrained, exogenous
sensor:     ligand-binding domain, adaptable, low specificity by design
transducer: conformational change -> partner recruitment
effector:   transcription of a set of metabolising enzymes
feedback:   effectors clear the trigger, closing the loop
```

The stripping is the technique. "PXR" and "nuclear receptor" both smuggle identity back in and
route you to family members — which you already have from another axis.

### 2. Ask what else has that signature

Now search on the signature, not the target. For the one above:

- **Bacterial multidrug-resistance regulators** (TetR/MarR family; BmrR, QacR, MexR). Sense
  arbitrary hydrophobic xenobiotics, adaptable pocket, drive efflux-pump transcription. Same
  five-line signature, zero homology to a nuclear receptor. And they are *structurally
  well-characterised with many ligands*, because they are small and crystallise well — so the
  conformational-range data we lack for the target exists for them.
- **Bacterial quorum-sensing receptors** (LuxR-type). Ligand-gated transcription with an
  adaptable pocket; the trigger is endogenous, so the signature matches on four lines of five.
- **Insect nuclear receptors and hormone sensors.** Same mechanism class, different chemistry.
- **Olfactory receptors.** Extreme case of designed low specificity. Different mechanism
  (GPCR, not TF) so the transducer line fails, but the *pocket-adaptability* line matches
  strongly and their literature on promiscuous recognition is deep.

None of these appears in a fold search, a pathway search, or a family search.

### 3. Score the match line by line

Record which lines of the signature match and which do not. A four-of-five match with a stated
mismatch is usable; an unscored "these are analogous" is not.

```python
attrs = {
    "own_pathway": "reactome:R-HSA-211859",       # xenobiotic nuclear receptors
    "other_pathway": "kegg:ko02020",              # bacterial two-component / MDR regulation
    "role": "xenobiotic sensor -> efflux/metabolism transcription",
    "shared_elements": ["arbitrary-hydrophobic trigger",
                        "adaptable low-specificity pocket",
                        "conformational transduction",
                        "transcriptional effector"],
    "mismatched_elements": ["no coactivator recruitment step",
                            "prokaryotic, no chromatin context"],
    "match_fraction": 0.8,
}
```

`mismatched_elements` is the field that makes the edge safe. It is the domain of validity: it
says exactly which inferences do *not* carry, and without it a role analogy will be applied to
whatever the reader hoped it covered.

### 4. Verify against literature

Somebody has usually noticed. Search for the pair explicitly, in both fields' vocabularies. Two
outcomes, both useful:

- **Someone stated it.** Cite them; confidence can rise above `tentative`.
- **Nobody stated it.** `NeglectReason.NEVER_STATED`, channel `graph_gap`, confidence
  `tentative` at most, and the role signature as the justification. This is a Swanson
  connection arrived at by reasoning rather than by graph traversal, and it is the more
  reliable route because the mechanism is stated up front.

## Ranking

Prefer analogues that are:

- **Better characterised than the target.** The point is to borrow data. An analogue with less
  structural coverage than the target is an interesting observation and not a resource.
- **Further away in every other axis.** A role analogue that is *also* a family member tells
  you nothing new; the axis has collapsed into another one. Maximum value at maximum distance
  elsewhere.
- **Mechanistically explicit.** If you cannot write the five-line signature for the analogue,
  you do not have a role match, you have a feeling.

## Failure modes

**Metaphor mistaken for mechanism.** "Both are gatekeepers" is not a role signature. The test
is whether the analogy makes a *checkable structural prediction*. If it does not, it is a
description of how you feel about both proteins.

**Analogy to something with no data.** Common and useless. Check coverage before investing.

**Letting it swallow the pathway axis.** These are different questions —
`SHARES_PATHWAY_WITH` says "same cascade", `ANALOGOUS_ROLE_TO` says "different cascade, same
slot". Merging them is exactly the loss the separate checklist item exists to prevent.

**Stopping at one.** The axis has a discovery curve like any other. One analogue is a lead;
`axis-sweep`'s stopping rule applies here too, and this axis will usually finish
`truncated` rather than `saturated` because it is reasoning-bound rather than query-bound.
Record that honestly — it is an open lead, and saying so is what lets a second pass resume it.

**Reasoning it out without recording the signature.** Then nobody can check the analogy or
reuse the method, and the edge becomes an assertion. The signature *is* the evidence.
