# PXR Track 2 — Structure Prediction

## What is a skill here, and what is a script

This repo's intelligence lives in `.claude/skills/` as Markdown an agent reads.
Code exists only to supply **what an agent must not improvise** — deployment,
deterministic format hygiene, and measured facts. Anything that encodes
*scientific judgement* — which models to run, how many seeds, how to pick a
pose — belongs in a skill, because a script that decides those things hides the
decision that is the whole point.

| Kind | Where | Why |
|---|---|---|
| Judgement | `.claude/skills/*/SKILL.md` | An agent must be able to reason about it, and change its mind |
| Measured fact | `.claude/skills/*/reference/*.md` | Costly to rediscover, and contradicts a plausible assumption |
| Infrastructure | `modal/` | Deploying AF3 correctly is not a judgement call |
| Mechanical helper | `stages/`, `eval/` | Manifest building, OST scoring, submission validation |

`stages/03_rescore.py` was deleted rather than fixed: it encoded a selection
strategy, and both the strategy and the decision to script it were wrong. Its
replacement is `confidence-selection/SKILL.md`.

Stage 3 skills owned here: `structure-ensemble`, `confidence-selection`,
`template-and-finetune`. Their `meta.json` `consumes`/`produces` keys are other
people's contracts — changing one changes someone else's stage, so say so first.


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
.claude/skills/  structure-ensemble · confidence-selection · template-and-finetune
manifest/     ligands.csv (184) · receptors.csv (64) · holdout.csv (92)
stages/       01_retrieve · 02_cofold · 04_submit   (mechanical helpers only)
eval/         score.py (OST metrics) · skill_lint.py · benchflow.yaml · structure_validation.py
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
ensemble.

That argument justifies a **wide pool**, and stops there. It does *not* justify
consensus selection, which is the intuitive next step and is refuted: agreeing
models share correlated errors, so voting amplifies them. Widen with diversity;
select with z-scored native confidence. See `confidence-selection/SKILL.md`.

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
- **GPUs: 80 GB tiers**, `["H100:1", "H200:1", "A100-80GB:1"]`. Measured H100
  81,559 MiB / A100-80GB 81,920 MiB. OOM is not a live constraint at this
  target's ~320 tokens.
- If a GPU deploy ever fails with *"Please add a payment method to use \<TIER\>
  GPU functions"*, that is **billing, not quota**, and it is tier-specific — the
  lower tiers keep working, which makes it look like something else. Probe one
  trivial function per tier to find the boundary, and use
  `modal/patch_gpu_profile.py` to fall back to A10/L4 rather than losing the
  pipeline. It is currently reverted. Note `proto-tools deploy` **exits 0 while
  printing `❌`**, so never trust its exit status.
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

## Layer-1 skill evaluation

`eval/skill_lint.py` checks that a skill is structurally sound before anyone
spends GPU finding out otherwise. Run it against the full tree, since Stage 3
consumes Stage 1/2 keys and a subset alone looks like a broken graph:

```bash
.venv/bin/python eval/skill_lint.py .claude/skills --graph-from <other-tree>/.claude/skills --strict
```

ERROR means the contract or structure is broken. WARN is drift. It is calibrated
to report **zero errors on a healthy tree** — a linter that fires on working code
gets muted, and then it catches nothing.

This is Layer 1 only: it proves the skills fit together, not that following them
produces good science. Layers 2-4 (does it trigger, does an agent produce the
declared artifact, does the artifact score better) still need a real run.
