# Scoring and submission: the parts that silently score zero

Measured against the OpenADMET PXR structure track. The specifics are that
challenge's, but every trap below is the general kind — a metric that measures
something adjacent to what you care about, and a format rule that fails quietly.

## Score with the organizers' metric, not a convenient one

Submissions are scored by **OpenStructure** `ost.mol.alg.ligand_scoring`:

| Metric | Direction |
|---|---|
| `LDDT-PLI` | higher better — the headline |
| `BiSyRMSD` | lower better |
| `LDDT-LP` | higher better |

**proto-tools does not wrap OpenStructure.** It ships TM-align, US-align, PyMOL
RMSD and FoldMason LDDT — all *protein-fold* metrics. A pose with the ligand in
the wrong subpocket scores excellently on TM-score and badly on LDDT-PLI, so
substituting one optimises the wrong objective and the error is invisible: the
numbers go up.

OST is not pip-installable. Run the official container:

```
registry.scicore.unibas.ch/schwede/openstructure:latest
```

Invoke it as `ost <script.py> <args>`; there is no `-c` flag. On Apple silicon the
image is amd64 and runs emulated — correct, but slow enough to matter when
scoring 184 items.

**A NaN is not a skip.** A pose OST cannot match scores `BiSyRMSD = 20.0` and
`LDDT-PLI = 0.0`. A harness that drops unmatched items reports a better number
than the leaderboard will. Track a `coverage` column alongside the means.

## Reference structures may hold several ligand copies

Of the 184 ground-truth structures, only **50 contain a single `LIG` residue**;
124 hold two, and some up to five, spread across both protein chains. The
receptor's pocket is large enough to bind more than one fragment at once.

Submissions must contain **exactly one** ligand. OST performs an assignment and
scores against the best-matching copy, so this asymmetry is expected — but it
means a per-item score is "best over reference copies", not "against the one true
pose". Do not add your own copy-matching logic on top; mirror the organizers'
implementation so the numbers stay comparable.

## Submission format — enforced, and quiet when violated

From the organizers' own `structure_validation.py`:

- a single **`.zip`**
- one **`.pdb`** per item, named `<item_id>.pdb`, **184** of them
- exactly **one residue named `LIG`**
- at most **2 chains**
- the `LIG` bond graph must match the expected SMILES under RDKit
  `AssignBondOrdersFromTemplate`

**Connectivity failure scores that compound 0 and adds a 20 Å RMSD penalty.**

Two things that catch people:

- **Renaming the ligand residue to `LIG` is not enough.** Co-folding models emit
  ligands with their own residue names and bond-order guesses, and the
  connectivity has to survive the PDB round-trip. Validate the zip, do not
  inspect one file and assume.
- **Inject `CONECT` records into every PDB** so the scorer infers bonds from
  topology rather than 3D geometry. The reference entry did this for all 184 as
  standard submission hygiene, alongside a format/SMILES validation pass that had
  to come back with zero errors.

Ligand SMILES will be canonicalised on the way through a model (Kekulé to
aromatic, say). That is not corruption — compare RDKit canonical forms rather
than strings before believing a mismatch.

## Subpopulations are where the points are

The 184 items are not homogeneous:

- **76 PanDDA fragments** — apo crystal soaks at 10 mM
- **108 drug-like analogs** — mostly weak binders (all measured pEC50 ≤ 4.4)

Drug-like was defined as **MW ≥ 330 or rotatable bonds ≥ 5 or heavy atoms ≥ 24**
(~87/184). Per-model scores ran **~0.46 on drug-like vs ~0.55–0.57 on fragments**,
so the drug-like half carries the difficulty and most of the headroom.
`manifest/ligands.csv` already carries `mw`, `heavy_atoms` and `rot_bonds`, so the
split is derivable — compute it and report both halves separately. A selector can
win overall while losing the half that decides the ranking.

## Hold the holdout out

Ground truth exists locally for all 184, so the dev/holdout separation is
self-imposed and nothing enforces it. Use the organizers' own `phase` column —
92 items were the live-leaderboard half, 92 stayed blinded — so internal numbers
stay comparable to the published leaderboard. Sweep configurations on dev; score
holdout once, at the end.

A validation set of ~35–50 items sits inside the noise floor. Bootstrap
(1000 resamples) and state the interval; a config that gains 0.01 with a
bootstrap std of 0.03 has gained nothing.
