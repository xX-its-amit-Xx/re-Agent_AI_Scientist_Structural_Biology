# Case study: the rank-2 OpenADMET PXR entry, reverse-engineered

Source repo: `O:/OpenADMET-pxr-structure`. This is the pipeline our meta-pipeline
must be able to *design*, so read it as a specification of the target, not as
trivia. Every number here is from that repo's own records.

## The challenge

Predict a 3D protein-ligand complex for each of **184 PXR-LBD + small-molecule
pairs**, blind. Scored by **LDDT-PLI** (OpenStructure `ligand_scoring`,
bootstrap-averaged over 1000 resamples; half live, half held out). Submit a zip
of 184 PDBs; ligand resname must be exactly `LIG`; the RDKit-parsed ligand graph
must match the expected SMILES. Connectivity failure scores that compound **0**
and adds a 20 Å RMSD penalty.

Test set composition matters enormously and drove every real decision:

- **76 PanDDA fragments** — apo P2₁2₁2₁ crystal soaks at 10 mM.
- **108 drug-like analogs** — mostly *weak* binders (all measured pEC50 ≤ 4.4).

Drug-like was defined as MW ≥ 330 or rotatable bonds ≥ 5 or heavy atoms ≥ 24
(~87/184). Per-model scores were ~0.46 on drug-like vs ~0.55-0.57 on fragments,
so **the drug-like half is where the points were**.

## Final standing

| | |
|---|---|
| Best score | **0.5640 LDDT-PLI** |
| Best rank | **2 / ~50** |
| Winner | 0.5725 — federated OpenFold3 fine-tune on four pharma companies' proprietary crystals |
| Gap | 0.0085 |

Note what beat them: not a cleverer algorithm, but **proprietary training data**.
That is a structural advantage, and recognising which gaps are closeable by
method versus only by data is itself a Stage 0 skill.

## The winning method

`prot_rescue8` — a 4-model z-hybrid confidence selector grafted with Protenix-v2
poses on the 8 lowest-confidence ligands.

**1. Widen the pool.** Six co-folders: AlphaFold3 (Modal A100 + AF Server, 4-10
seeds), Boltz-2.1 (hosted API, 5-10), OpenFold3 (20), Chai-1 (5), Protenix-v2
(25), ESMFold2 (25 × 4 MSA modes). Pool oracle — best achievable — was **~1.08 Å
median RMSD**, far better than any single model realised.

**2. Select within each model** using that model's *native* confidence, not a
universal score: AF3 `iptm`; Boltz-2 `-complex_ipde`; OF3 `-mean(PAE[pocket,
ligand])`; Chai `iptm`.

**3. Select across models by z-score.** Raw confidences from different models are
not commensurable, so z-score each model's best-sample scores across all 184
ligands, then take `argmax_m z[m,i]` per ligand. This is the core trick and it
took **0.4996 → 0.5472**.

**4. Rescue the failure tail with a different model.** Overwrite only the N
lowest-confidence ligands with Protenix-v2's best pose. The sweep is instructive:

| N swapped | 4 | **8** | 12 | 20 |
|---|---|---|---|---|
| Score | 0.5578 | **0.5640** | 0.5629 | 0.5587 |

One rescue went 0.123 → 0.919. Over-swapping hurts — the tail is real but small.

**5. Submission hygiene, every time.** Format/SMILES-graph validation (zero
errors required) → swap 3 server-confirmed scoring-fail ligands → inject CONECT
records into all 184 PDBs so the server infers bonds from topology rather than
3D geometry.

## The single most important finding: the selection wall

With a fixed pool and no ground truth to train on, **every** learned, agentic, or
consensus selector regressed against the plain z-scored native-confidence argmax.
"Chemically plausible ≠ native."

An independent literature review in that repo reached the same conclusion before
the experiments confirmed it: on co-folding pose pools, native-confidence
ranking and cross-model consensus largely **do not beat random**, and consensus
can be *actively harmful* because agreeing models share correlated errors.

The two levers that did work: **widen the pool**, and **rescue the failure tail**.
Use cross-model diversity to widen, never to vote.

## What was refuted, and how

This list is more valuable than the winning method, because the literature does
not publish it:

- **OpenMM local MD refinement** — could not recover a 2 Å translation.
- **Agentic ligand re-drawing** — 4NY9 went 3.88 → 24.63 Å. Agents hallucinate
  unphysical poses. A hard lesson for anyone building an AI scientist.
- **Crystal anchor priors** — fine on drug-like, fail on PanDDA fragments.
- **MMFF strain gating** — `blend_top3` 2.251 Å vs IPDE 2.230 Å, i.e. 0.020
  *worse*. High-variance: big wins on 4 holos, catastrophic losses on 3.
- **Ligand-only MMFF relaxation of ground truth** — monotonically hurts. The
  bound conformer is legitimately strained.
- **Genetic anchor+tail crossover** — oracle improved, but no selector could find
  the hybrid. A pure selection-wall casualty.
- **Learned pose scorer (XGBoost LambdaMART, 37 features)** — scored 0.4762 /
  rank 32, the project's worst submission. Trained on 35-53 holos: far too few.
- **Consensus / medoid / Borda / RRF** — the correlated-error trap.

## Four pieces of transferable machinery

These generalise past PXR and should be built into any pipeline we design.

### 1. A pre-registered three-gate admission test

Submissions were scarce (~1 per 4 h). Nothing reached the server without passing:

1. **Connectivity/format** — zero validator errors.
2. **Divergence band vs the incumbent: 5-30 %.** Below 5 % is sub-noise and
   wastes a slot; above 30 % is the empirically-identified "anchor-disaster
   band" — every candidate above it (94.6 %, 99.5 %, 95.7 %, 88.6 %, 86.4 %)
   scored below 0.47. This gate alone rejected 13 candidates and is the novel,
   highest-yield one.
3. **Local ground-truth RMSD ≤ 2.15 Å** on the 53-holo validation set, with ≥3
   of 4 confidence signals supporting.

Result: 0 of 12 candidates passed all three gates in iterations 3-6 — which is
the gate working, not the gate failing.

### 2. A falsification harness with pre-committed transitive rejection

A local ground-truth gate (`pose_lib.py`, `*_gtgate.py`) killed 8 approaches
before any consumed a submission slot. Better still, rejection rules were
committed *in advance*: "if MMFF strain fails validation, the DFT-torsion-prior
project is cancelled unbuilt." It failed; 14 dev-hours were saved without a new
argument. **Pre-register the kill criterion and its consequences** — this is why
`Proposal.kill_criterion` is a required field in our contract.

### 3. Validation-set expansion as an overfit detector

Expanding the validation set from 35 to 53 holo structures produced a clean
diagnostic. Every method gained ~+0.020 lddt-proxy on the easier set — *except*
pLDDT-based selection, which gained +0.0015 and fell from 1st to last. The
signature of an overfit is **failing to improve when the task gets easier.**

Also recorded, and vital: local validation was **not monotonic** with the
leaderboard. All methods clustered within 0.05 Å on 35 holos (the noise floor)
while the leaderboard spanned a 5× wider range. Trust the real metric over a
tiny local ground truth.

### 4. A structured-corpus literature phase (the direct ancestor of our Stage 1)

The repo's knowledge-acquisition phase produced **data, not prose** — and this is
the pattern our Stage 1 must beat:

`nr_lbd_query.py` posts to the RCSB Search API v2 for Pfam **PF00104** (nuclear
receptor LBD) AND `nonpolymer_entity_count > 0` → 1,291 hits. `nr_lbd_ligfilter.py`
queries the RCSB GraphQL endpoint for each entry's chemical components and
buckets them using a hand-curated ~230-entry exclude set (waters, ions, buffers,
cryoprotectants, PEGs, detergents) into ligand-bound / additive-only / truly-apo.
`nr_lbd_segment.py` maps 31 human NR UniProt accessions. `nr_lbd_assemble.py`
intersects and emits **1,264 labeled PDB IDs**.

The resulting distribution across 30 receptors is our Stage 1 baseline to
reproduce and exceed:

| Receptor | n | Receptor | n | Receptor | n |
|---|---|---|---|---|---|
| ESR1 | 312 | ESR2 | 38 | RARG | 11 |
| RORC | 158 | GR_NR3C1 | 34 | TRA_THRA | 8 |
| AR_NR3C4 | 92 | ERRG_ESRRG | 26 | RARB | 7 |
| PPARG | 88 | MR_NR3C2 | 23 | SF1_NR5A1 | 5 |
| FXR_NR1H4 | 79 | LRH1_NR5A2 | 23 | RXRB | 5 |
| **PXR_NR1I2** | **70** | PR_NR3C3 | 18 | NR4A_NURR1 | 4 |
| OTHER_NR | 58 | TRB_THRB | 18 | RORA | 3 |
| PPARD | 50 | RXRA | 12 | ERRA_ESRRA | 3 |
| VDR_NR1I1 | 48 | LXRB_NR1H2 | 12 | CAR_NR1I3 | 2 |
| PPARA | 44 | RARA | 12 | HNF4A | 1 |

A "close homolog" corpus of PXR + VDR + CAR + PPARα/γ/δ gives **302** entries.

For the **promiscuity axis** it separately harvested six promiscuous, xenobiotic-
handling target classes — explicitly because PXR's pocket is >1600 Å³ and
promiscuous:

| Class | RCSB total |
|---|---|
| cytochrome P450 | 419 |
| kinase | 5,784 |
| GPCR | 25 |
| transporter | 755 |
| protease | 4,433 |
| phosphodiesterase | 517 |

That corpus fed a **4-stage curriculum fine-tune** of OpenFold3 with escalating
specificity and decreasing learning rate — drug-like (2000 steps, 3e-4) →
promiscuous classes (1500, 1e-4) → all 1,264 NR LBDs with PXR up-weighted 3× and
FXR/CAR 2× (800, 5e-5) → 70 PXR holos (350, 2e-5), interface weight rising
1.0 → 3.0. **This is the handoff our Stage 1 owes Stage 3**: not a reading list,
but a weighted, deduplicated, ligand-filtered corpus with per-entry sample
weights.

## PXR structural knowledge worth carrying forward

Pocket anchors (UniProt O75469 numbering): **Ser247** (polar, agonist-defining),
**Gln285**, **His407** (protonatable, flexible α10), **Arg410** (salt bridge).
Hydrophobic/aromatic subpocket: **Phe288, Trp299, Tyr306**.

A 28-residue pocket map (0-indexed into the 293-aa LBD, UniProt 142-434):

```
Helices α1/α3:   64, 65, 67, 68, 70, 99, 102, 103, 105, 106, 110
β-sheet / loop:  140, 143, 144, 147, 158, 165, 167
Pocket floor:    182, 183, 186
Helix αAF / lid: 262, 266, 269, 270, 273, 279, 284
```

**Critical caveat, and a warning about priors generally:** PanDDA fragments have
Morgan-r2 Tanimoto < 0.3 to *every* known PXR holo ligand, and often engage
**zero** canonical anchors. Any drug-like-trained signal **inverts sign** on
them — confirmed four times independently (per-family MLP, gnina CNN, PDBbind
XGB, ChEMBL Uni-Mol). A prior that helps on one half of a test set can hurt on
the other, so Stage 1 must report the *domain of validity* of every prior it
hands downstream, not just the prior.

## Metric caveats that decided real submissions

- **LDDT-LP is decoupled from LDDT-PLI** (Spearman ≈ +0.01 across 18
  submissions). Never rank by it.
- **BiSyRMSD tracks LDDT-PLI** (ρ ≈ +0.94) and is a safe corroborating column.
- **The leaderboard displays your most recent submission, not your best.** Three
  competitor teams destroyed their own standings this way (0.5521 → 0.4727, rank
  2 → 18 being the worst). This repo built a submission ladder with a deadline
  guard and two redundant OS-level restore tasks specifically against it.

## What the authors said they would do differently

1. Codify the pre-flight gate by iteration 2, not 3 — 11 wasted submission slots,
   8 of which the divergence gate would have caught.
2. Build the expanded validation set earlier.
3. Stop sinking 80 hours into external notebook attempts: **0 of 8** reached a
   submittable output. External resources had a ~12-week activation lag against a
   30-day window.
4. Spend 70 % of ideation on the *test-set distribution* rather than on methods.

Item 4 is the strongest argument for our Stage 1 existing at all.
