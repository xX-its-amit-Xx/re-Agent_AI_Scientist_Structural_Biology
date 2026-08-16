# The 17 failure signals

For each: how it is diagnosed, what it usually means, and — the column worth reading — **what
it gets confused with.** Most wasted effort here comes from applying the right remedy to the
wrong signal, and the pairs below are the ones that look alike.

---

## The model is unsure

### `low_global_confidence`
**Diagnosed by** mean pLDDT or pTM below the target's usual range.
**Usually means** a shallow MSA, or a genuinely novel fold.
**Confused with** `high_domain_pae` — a hinged multi-domain protein can have excellent local
pLDDT and a poor global pTM, and deepening the MSA will not help. Check whether the low
confidence is uniform or localised before treating it as global.

### `low_pocket_confidence`
**Diagnosed by** pLDDT restricted to the pocket-lining residues being materially below the
protein's mean.
**Usually means** the site is flexible, or the alignment is thin exactly there.
**Confused with** the model being *right*. A mobile loop with low pLDDT is correct uncertainty.
The free rung exists to check this against the holo structures in the graph, because imposing a
restraint on a genuinely flexible region fights the biology and looks like an improvement in
pLDDT while making the pose worse.

### `low_interface_confidence`
**Diagnosed by** ipTM or interface PAE poor while intra-chain confidence is fine.
**Usually means** the relative orientation of two chains is unconstrained.
**Confused with** having the *wrong partner chain*. This project has already selected an RXR
partner in place of the intended chain, which produced a meaningless interface score. Confirm
the biological assembly first.

### `high_domain_pae`
**Diagnosed by** high PAE between residue pairs in different domains, low within each.
**Usually means** flexible linkage — often the correct answer.
**Confused with** `low_global_confidence`. The remedy differs completely: predict domains
separately and assess the site in its own domain, rather than deepening an MSA that was fine.

---

## The ligand is wrong

### `low_ligand_accuracy`
**Diagnosed by** LDDT-PLI or pose RMSD against a reference.
**Usually means** almost anything, which is why the free rungs matter here more than anywhere.
**Confused with** `metric_artefact`. A symmetric ligand scored without symmetry correction
reports a large error for a correct pose — **the single most common false failure in pose
evaluation.** Check symmetry before concluding anything.

### `ligand_outside_pocket`
**Diagnosed by** the ligand centroid outside the pocket envelope, or zero contacts with lining
residues.
**Usually means** the predicted protein is apo-like and there is nowhere to put the ligand.
**Confused with** `low_ligand_accuracy`. The ligand is not misplaced — the pocket is missing.
Fixing the pose without fixing the pocket treats the symptom, and the two have different
remedies (holo seeding versus rescoring).

### `ligand_clashes`
**Diagnosed by** heavy-atom overlaps below a van der Waals cutoff.
**Usually means** a protonation mismatch between the prediction and the clash checker.
**Confused with** `implausible_internal_geometry`. A clash is with the *protein*; strain is
*within* the ligand. Minimisation resolves small strain and will not resolve a real placement
error, which is a useful discriminator: if the clash survives minimisation it is placement.

### `wrong_stereochemistry`
**Diagnosed by** comparing stereo descriptors of the input against what reached the model.
**Usually means** a format conversion lost it — silently, which is the problem.
**Confused with** a model failure, completely. It produces a confidently wrong pose with good
confidence scores. Free to check and worth checking always, because nothing downstream reveals
it.

### `implausible_internal_geometry`
**Diagnosed by** torsional strain, bond lengths, planarity of aromatic systems.
**Usually means** a poor input conformer, or a force-field parameterisation mismatch.
**Confused with** a real failure. Strain terms are sensitive to parameterisation and to assumed
protonation; a mismatched force field reports strain for a reasonable geometry.

---

## The protein is wrong

### `pocket_collapsed`
**Diagnosed by** predicted pocket volume at or below the low end of the observed holo range.
**Usually means** the model defaulted to apo, because most training structures are apo.
**Confused with** a malfunction. For an adaptable pocket this is the *expected* default, not an
error — which is why the free rung checks `binder-census` for whether the target is known to be
induced-fit. The remedy is conditioning, not resampling: more seeds of an apo-biased model give
more apo predictions.

### `missing_region`
**Diagnosed by** residues absent or at very low confidence.
**Usually means** disorder, and absence from the PDB is *evidence of* disorder rather than of a
modelling failure.
**Confused with** something to fix. Forcing a conformation onto a disordered tail invents
structure and then scores it. The one thing that matters is whether the region lines the pocket
— if it does, the pocket definition and every contact measured in it change.

---

## The sampling is wrong

### `high_seed_variance`
**Diagnosed by** pose RMSD spread across seeds.
**Usually means** under-convergence, or a genuinely underdetermined site.
**Confused with** a failure at all. Variance is only a failure if the *selector* cannot find the
good candidate — so the check that decides everything is the oracle gap, and it may redirect the
whole effort to selection.

### `consistent_but_wrong`
**Diagnosed by** low variance across seeds and a bad score.
**Usually means** systematic bias, or a wrong reference.
**Confused with** `high_seed_variance`, and the remedies are opposites. More seeds of a biased
model reproduce the bias exactly; only a **decorrelated** generator — a different model family,
not more sampling — can put a right answer in the pool. This is the signal where
`generator-diversity` earns its cost, and where a cross-domain analogy is most likely to help,
because every in-field method trained on the same structures may share the blind spot.

---

## The selection is wrong, not the pool

### `good_pool_bad_pick`
**Diagnosed by** a large oracle gap: the best candidate in the pool scores well, the selected one
does not.
**Usually means** confidence is being compared across generators without normalisation.
**Confused with** a generation problem, which is the expensive mistake. `bottleneck-triage`
exists to settle this before anything is spent, and the first remedy — normalise within each
generator, then per-item argmax — costs nothing and usually closes most of the gap.

### `confidence_uncorrelated`
**Diagnosed by** discrimination AUC of the ranking signal near 0.5.
**Usually means** the signal is scoped to the wrong object — a whole-model confidence cannot
rank poses that share the model, because it does not vary with what is being chosen.
**Confused with** the signal being bad. It may be a fine signal measured on the wrong thing, and
the negative control in `signal-scoping` is what tells the two apart.

---

## The measurement is wrong

### `metric_artefact`
**Diagnosed by** the identity and perturbation tests, and by re-reading the official metric.
**Usually means** symmetry handling, a wrong reference, or units.
**Confused with** every other signal on this page. This is why `harness-verification` is a free
rung on all of them: a scorer that does not return a perfect score for a structure against
itself is broken, and that is one call to find out.

### `harness_unverified`
**Diagnosed by** nobody having run the checks.
**Usually means** exactly that, and every downstream conclusion inherits it.
**Confused with** nothing — it is a process state rather than an observation, and it gates
everything else. If this signal is raised, stop and verify before making any decision from a
number the harness produced.

---

## The pairs to hold in mind

Five confusions cause most of the wasted effort. Each has a free check that separates them:

| Looks the same | Actually | Free check |
|---|---|---|
| low ligand accuracy / metric artefact | a correct pose scored wrongly | identity test, symmetry handling |
| ligand outside pocket / low ligand accuracy | no pocket to place it in | predicted pocket volume vs holo range |
| high seed variance / consistent-but-wrong | opposite remedies | variance across seeds |
| good pool bad pick / weak generation | selection, not generation | oracle gap |
| low pocket confidence / correct uncertainty | the model is right | compare against holo structures |

## When the signal is not on this list

`Experiment.unanticipated_signals()` names it. That is not a failure of the run — it is the list
of branches to add before the next one, and the registry is explicitly a floor rather than a
ceiling. Escalate to `RemedyTier.NOVEL`, and when the new signal turns out to recur, add it here
with its diagnosis and the confusion it belongs to.
