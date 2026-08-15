# PXR Track 2 — Structure Prediction

Agentic pipeline predicting bound protein-ligand complexes for the OpenADMET PXR
Blind Challenge structure track. The original July 1 2026 deadline has passed;
this is a hackathon rebuild scored against the now-unblinded ground truth.

## Read this before changing anything

Four facts were established in Phase 0 by reading the organizers' own code and
data. Each contradicts a reasonable assumption, and each is expensive to
rediscover.

**1. There are 184 targets, not 110.** The 110 figure is from the April
announcement. The final structure set is 184: `STRUCTURE_DATASET_SIZE = 184` in
the organizers' validator, 184 rows in the blinded test CSV, 184 ground-truth
PDBs, 184 files in their example submission. Budget compute for 184.

**2. The scoring metrics are OpenStructure's, and proto-tools does not wrap
them.** Submissions are scored on `LDDT-PLI` (↑), `BiSyRMSD` (↓), `LDDT-LP` (↑)
via `ost.mol.alg.ligand_scoring`. proto-tools ships TM-align, US-align, PyMOL
RMSD and FoldMason LDDT — all protein-fold metrics. A pose with the ligand in
the wrong subpocket scores well on TM-score and badly on LDDT-PLI. Score with
`eval/score.py`, which runs the official OST container. Do not substitute a
protein-level aligner because it is easier to install.

**3. We hold ground truth for all 184 targets, so the dev/holdout discipline is
self-imposed.** `data/challenge/structure_ground_truth/` has every answer. The
split in `manifest/ligands.csv` is the organizers' own `phase` column — phase 1
(92) was the live-leaderboard half, phase 2 (92) stayed blinded. Sweep configs on
`dev`; score `holdout` once, in Phase 7. Nothing enforces this but us, which is
exactly why `paperclip/permissions.yaml` grants `read_ground_truth` to the `eval`
agent alone.

**4. AlphaFold3 needed a Modal deployment written by hand — it now exists.**
Weights are a direct download (~973 MB, HTTP 200, no approval queue); the only
gate is DeepMind's Model Parameters Terms of Use, non-commercial research only.
The real obstacle was that proto-tools ships an AF3 *tool wrapper* but no Modal
*app*, so `proto-tools deploy` had nothing to push. `modal/alphafold3_service.py`
is that missing app, kept in this repo rather than patched into the installed
proto-tools tree (an in-place edit is clobbered on upgrade). Weights live on the
`proto-cache` Modal volume at `alphafold3/af3.bin.zst`; never commit them.

Because AF3 is deployed as our own app, it is invisible to `proto-tools deploy
--list` and the proto-tools MCP. Dispatch every cofold through
`modal/client.py:cofold()`, which routes AF3 to `modal.Cls` and the other four
through proto-tools.

## Layout

```
manifest/     ligands.csv (184) · receptors.csv (64) · holdout.csv (92)
stages/       01_retrieve → 02_cofold → 03_rescore → 04_submit
eval/         score.py (OST metrics) · benchflow.yaml · structure_validation.py (vendored)
modal/        alphafold3_service.py (our AF3 app) · client.py (unified cofold dispatch)
paperclip/    org.yaml · permissions.yaml       — Phase 5, do not wire early
benchling/    schema.json                        — run provenance
data/         challenge/ (HuggingFace) · rerefined/ (64 PXR structures)   [gitignored]
runs/         per-run outputs                                            [gitignored]
```

To patch AF3's build without touching proto-tools, drop files in
`modal/standalone_overrides/alphafold3/` — the image builder overlays them onto
the upstream standalone dir and the changed hash forces a clean env rebuild.

Regenerate manifests any time: `.venv/bin/python stages/01_retrieve.py`
(self-checks 184 targets, 92/92 split, 184/184 ground-truth coverage).

## Submission format

A single `.zip` of `<structure_id>.pdb`, 184 of them. Each PDB: chain A protein,
chain B ligand, **exactly one residue named `LIG`**, at most 2 chains, and the
`LIG` bond graph must match the target SMILES under RDKit
`AssignBondOrdersFromTemplate`.

That last rule is the silent failure. Cofold models emit the ligand under their
own residue name with their own bond-order guesses; renaming to `LIG` is not
sufficient, the connectivity has to survive the PDB round-trip. `stages/04_submit.py`
runs the organizers' validator — always build the zip through it.

## The target

PXR's binding pocket is large, hydrophobic and promiscuous, the adjacent loops
are disordered, and the receptor adopts multiple documented conformations. Six of
the 64 re-refined structures have **two** ligands bound simultaneously. Any single
cofold run is a sample from a wide distribution, not an answer — hence the
ensemble in Phase 4 and consensus selection in `stages/03_rescore.py`, rather
than trusting one model's confidence head.

Targets are fragment-sized: MW 127–474 (median 309), 9–32 heavy atoms
(median 21). Small ligands in a large pocket is the regime where pose placement
is hardest and where model confidence is least informative.

## Working rules

- **Score before you scale.** `eval/score.py` and the dev split exist before the
  ensemble does. A config that gains 0.01 LDDT-PLI with a bootstrap std of 0.03
  has gained nothing; `eval/benchflow.yaml` requires non-overlapping CIs.
- **Get the pipeline working before agentifying it.** Stages 01–04 run by hand
  first. `paperclip/` is Phase 5.
- **Never read `structure_ground_truth/` from a cofold or rescore path.** The
  leak is invisible in the final score, because the score comes from the same
  files.
- **Record provenance per run** against `benchling/schema.json`: model, version,
  seed, receptor, proto-tools commit.

## Environment

- `.venv/` — pandas, pyarrow, rdkit, MDAnalysis, biopython, pyyaml, modal,
  proto-tools (`uv`-managed). proto-tools must be in the venv, not just the
  `uv tool` install, or `modal deploy` cannot import it.
- Modal — workspace `sumershinde22`, environment `proto-env`, volume
  `proto-cache` (holds `alphafold3/af3.bin.zst`, mounted at `/weights`).
- **GPU tier is capped at 23 GB.** This workspace has no payment method, and
  Modal gates GPUs *by tier*: T4/L4/A10 schedule fine; L40S, A100-40GB,
  A100-80GB and H100 are all refused. Everything runs on `["A10:1", "L4:1"]`.
  proto-tools' hardcoded `GPU_DEFAULT` is the refused tier, so after any
  `proto-tools` upgrade re-run `.venv/bin/python modal/patch_gpu_profile.py` or
  every cofold deploy breaks again.
- OpenStructure — not pip-installable; `eval/score.py` shells to the official
  container `registry.scicore.unibas.ch/schwede/openstructure:latest`

Deploy the cofold backends:

```bash
proto-tools deploy --apps boltz2,chai1,protenix,rf3 --env proto-env
.venv/bin/modal deploy -e proto-env modal/alphafold3_service.py
```

AF3 weights must already be on the volume — `setup.sh` prechecks them and fails
in seconds rather than after the ~30 minute env build:

```bash
.venv/bin/modal volume put proto-cache af3.bin.zst alphafold3/af3.bin.zst -e proto-env
```

## Sources

- Challenge data — [openadmet/pxr-challenge-train-test](https://huggingface.co/datasets/openadmet/pxr-challenge-train-test)
- Validator + tutorial — [OpenADMET/PXR-Challenge-Tutorial](https://github.com/OpenADMET/PXR-Challenge-Tutorial)
- Re-refined receptors — [OpenADMET/pxr_xtal_re-refinement](https://github.com/OpenADMET/pxr_xtal_re-refinement) ([10.5281/zenodo.21504333](https://doi.org/10.5281/zenodo.21504333))
- Challenge announcement — [openadmet.ghost.io](https://openadmet.ghost.io/announcing-the-next-openadmet-blind-challenge-predicting-pxr-induction/)
