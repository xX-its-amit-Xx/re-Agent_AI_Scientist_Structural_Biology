# The binder classes

For each: how to recognise it, **what its pose is evidence of**, and what goes wrong if you
misclassify it. The middle column is the reason the taxonomy exists — pooling classes and calling
the result "the binding mode" is the error everything here guards against.

`informs_intended_mode` and `informs_druggability` partition the usable classes; artefacts and
unknowns are excluded from both by `is_usable_evidence`.

---

## Tells you what the protein is *for*

### `endogenous`
**Recognise:** a physiological ligand, argued in the literature rather than found in a database.
Usually contested for anything other than a classical receptor.
**Its pose is evidence of:** the mode the protein was selected for. The strongest available
evidence, and for a xenobiotic sensor there may be none.
**Misclassify it as a drug and:** you lose the only reference you had. Misclassify a *drug* as
endogenous and you build a canonical mode on what medicinal chemistry achieved.

### `substrate` / `product`
**Recognise:** for an enzyme, the thing transformed and the thing produced. Product complexes are
often the ones that crystallise.
**Evidence of:** the catalytically competent geometry, which is not the same as the highest-affinity
geometry.
**Watch:** a product complex shows the *post*-reaction pose. Using it as a docking reference biases
toward the wrong end of the reaction coordinate.

### `cofactor`
**Recognise:** required for activity; usually in `CONTEXT_DEPENDENT` codes.
**Evidence of:** an obligate structural feature of the site. A pocket modelled without its cofactor
is a pocket that never exists.
**Misclassify it as an artefact and:** you predict into a site whose real shape includes something
you deleted.

### `metabolite`
**Recognise:** a downstream product of something else, often endogenous.
**Evidence of:** plausible physiological occupancy, weaker than a true endogenous ligand.

---

## Tells you what chemistry can *do*

### `orthosteric_drug`
**Recognise:** designed against this target, binds the main site, part of a series.
**Evidence of:** what medicinal chemistry achieved here — an upper bound on affinity and a map of
which sub-pockets are exploitable. **Not** what the protein is for.
**Most useful for:** the druggability question and the SAR. Least useful for the canonical mode.

### `off_target_drug`
**Recognise:** designed for a different target, hits this one too. The interesting half of a
promiscuity census.
**Evidence of:** which chemotypes engage this site *incidentally*, which is the selectivity
problem stated from the other end. For a xenobiotic sensor these dominate the census, and that
dominance is itself the finding.
**Misclassify as orthosteric and:** you conclude a chemotype was optimised for this target when it
was optimised elsewhere and tolerated here.

### `allosteric_modulator`
**Recognise:** binds away from the orthosteric site; affects activity without competing.
**Evidence of:** a second site, which is a different pocket and should be a different `Pocket`
node.
**Misclassify as orthosteric and:** its contacts pollute the orthosteric interaction matrix with
residues from a different part of the protein. This is a common and quiet failure.

### `tool_compound`
**Recognise:** a chemical probe. Never intended as a medicine; often very potent and very
insoluble.
**Evidence of:** what is achievable when developability is ignored. Useful for the pocket, actively
misleading for a property model — a tool compound's physicochemistry is not a target to aim at.

### `natural_product`
**Recognise:** plant or microbial origin, often large and stereochemically dense.
**Evidence of:** genuine binding, and a chemotype outside typical synthetic space. Frequently
over-represented among promiscuous binders because they are assayed broadly.

### `fragment`
**Recognise:** small, weak, from a fragment screen. Often sub-millimolar and sub-threshold for
"active".
**Evidence of:** which sub-pockets can be engaged in isolation — a hot-spot map. **And the class
most likely to break an anchor assumption:** in this project's reference case fragments engaged
*zero* canonical anchors, which inverted an anchor-based prior on the fragment half of the test
set.
**Never pool with drug-like ligands** when computing recurrence or building a pharmacophore.
Report per subpopulation.

### `covalent`
**Recognise:** a warhead, a modified residue, continuous density into the protein.
**Evidence of:** reactivity plus proximity, not affinity. Its pose is constrained by the bond, so
it says less about non-covalent complementarity than its buriedness suggests.
**Misclassify as non-covalent and:** you fit a scoring function to a geometry that a bond, not
recognition, determined.

---

## Tells you about the experiment

### `crystallization_artefact`
**Recognise:** the code lists in [artefact-codes.md](artefact-codes.md).
**Evidence of:** the crystallisation and freezing protocol.
**Consequence of missing one:** it pollutes every statement about the pocket — pharmacophore
models, promiscuity counts, sub-pocket occupancy, the interaction matrix. `misclassified_artefacts()`
catches these arithmetically because catching them by eye does not work.

### `unknown`
**Recognise:** you have not decided.
**Legitimate as a temporary state and not as a result.** `BinderCensus.unclassified` is a list of
holes: each entry is neither counted as a binder nor recorded as an artefact, so the census total
means nothing while any remain.

---

## Class composition as a diagnostic

The mix is informative before any individual entry is:

| Pattern | Reading |
|---|---|
| mostly `off_target_drug`, no `endogenous` | a promiscuous xenobiotic handler — expect no canonical mode |
| one `endogenous` plus a series of `orthosteric_drug` | a classical receptor with a real reference mode |
| mostly `fragment` | early-stage target; hot-spot data but little on drug-like binding |
| `cofactor` plus `substrate` plus `product` | an enzyme; the reference is a reaction coordinate, not a pose |
| high `crystallization_artefact` fraction | either a hard-to-crystallise target or a census that was not filtered |

`chemotype_spread()` counts distinct usable classes as a crude diversity proxy. A census of thirty
binders all in one class is a narrower result than the count suggests.

## Recording the class

`Binder.classified_because` is required and is where the reasoning goes. For a
`CONTEXT_DEPENDENT` het code the contract enforces more than one clause, and the reasoning that
actually decides these cases is in [artefact-codes.md](artefact-codes.md).

For everything else the useful content is *how you know* — an assay type, a paper, a patent
series, the fact that the compound's primary target is something else. **"It is a drug" is not a
classification**; "it is an approved antibiotic whose primary target is bacterial RNA polymerase
and which activates this receptor as a side effect, which is why it is the textbook inducer" is.
