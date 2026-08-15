# Phase 0 report — 2026-08-15

Status against the exit gate, then the four findings that change the plan.

## The payment gate is tier-specific — routed around, not waiting on billing

Every GPU deploy first failed with `Please add a payment method to use H100 GPU
functions`, and adding one was impossible (Stripe declined every method). That
looked terminal. It was not: the message names a *tier*, so probing one trivial
function per tier found a clean boundary.

| Tier | Result |
|---|---|
| T4 | **allowed** — Tesla T4, 15,360 MiB |
| L4 | **allowed** — NVIDIA L4, 23,034 MiB |
| A10 | **allowed** — NVIDIA A10, 23,028 MiB |
| L40S · A100-40GB · A100-80GB · H100 | refused — payment method required |

The free tier reaches 23 GB, which is ample here: a PXR LBD (291 residues) plus a
≤32-heavy-atom fragment is roughly 320 tokens. It would not be ample for a large
complex, so this ceiling is a property of *this* target, not a general result.

proto-tools hardcodes `GPU_DEFAULT = ["H100:1", "H200:1", "A100-80GB:1"]` and
offers no env-var override, so all four cofold services inherited the refused
tier. `modal/patch_gpu_profile.py` repoints that constant to `["A10:1", "L4:1"]`
— idempotent, reversible, and versioned here rather than hand-edited, because it
modifies an installed package and **will not survive a `proto-tools` upgrade**.
T4 is excluded on purpose: 15 GB is the tier most likely to OOM partway through a
cofold, and a job that dies at minute 20 costs more than one that waits.

`modal/alphafold3_service.py` states its own tiers instead of importing the
patched constant — it is our file and should not depend on a patch to someone
else's package.

Two things that made this harder to diagnose than it should have been:

- **`proto-tools deploy` exits 0 while printing `❌` for every app.** The shell
  exit code is not a success signal. Worth remembering in Phase 5, when an
  orchestrator starts checking return codes.
- **Deploy serially.** Five concurrent app creates tripped `App create rate limit
  exceeded` on rf3, which looks nothing like the real problem.

## Exit gate

| Item | Status |
|---|---|
| One Proto tool call executed successfully | **Done** — `boltz2-prediction` ran on Modal (`ran_on: modal`), returning a CIF with confidence 0.809 / complex-pLDDT 0.942. All five cofolders are deployed to `proto-env`: `proto-tools-{boltz2,chai1,protenix,rf3}` and `pxr-af3`. |
| GPU count/memory known and recorded | **Done** — see below. Serverless, not a fixed allocation. |
| Ligands, receptors, holdout on disk | **Done** — 184 targets, 64 receptors, 184/184 ground truth. |
| Repo skeleton exists | **Done** — plus manifests built and self-checking. |
| Gated access request submitted | **Moot / superseded** — no request queue exists. Weights are staged and `modal/alphafold3_service.py` is written and builds; see finding 4. |

## GPU allocation

Modal is serverless, so "how many GPUs" is the wrong shape of question. What's fixed:

- **Per job:** 1 GPU, `["A10:1", "L4:1"]` — both 23 GB. Not proto-tools' default
  (H100/H200/A100-80GB); see the tier section above for why, and
  `modal/patch_gpu_profile.py` for how. 23 GB is comfortable for ~320 tokens but
  leaves no headroom, so treat OOM as a live risk when Phase 2 tunes batch/sample
  counts rather than assuming it away.
- **Dedicated**, not shared: each container holds its GPU for the call.
- **Concurrency** is bounded by the Modal account's limit and by spend, not by a
  node count. Effective ceiling for the hackathon is the **$100 partner credit**.
- Workspace `sumershinde22`, environment `proto-env` (created this phase, no apps
  deployed yet).

Consequence for Phase 2: calibrate on **cost per cofold**, not on GPUs-in-hand.
The budget question is "how many of the 184 × models × seeds fit in $100", and
the 184 (not 110) makes that 67% tighter than the plan assumed.

## Findings that change the plan

### 1. 184 targets, not 110

The 110 figure is from the April announcement. Every authoritative source says 184:

- `STRUCTURE_DATASET_SIZE = 184` — organizers' `validation/structure_validation.py`
- 184 rows in `pxr-challenge_structure_TEST_BLINDED.csv`
- 184 PDBs in `structure_ground_truth/`
- 184 files in their own example submission

The set grew as late-breaking structures landed. **67% more compute than planned.**

### 2. Scoring is OpenStructure, and proto-tools does not wrap it

Official metrics: `LDDT-PLI` (↑), `BiSyRMSD` (↓, NaN→20 Å penalty), `LDDT-LP` (↑),
from `ost.mol.alg.ligand_scoring`.

The project stack listed US-align / TM-align / PyMOL RMSD for pose comparison.
Those are in proto-tools, but they measure **protein fold agreement** — a pose with
the ligand in the wrong subpocket scores well on TM-score and badly on LDDT-PLI.
Optimising them would optimise the wrong thing.

OST is not pip-installable. `eval/score.py` shells to the official container
(`registry.scicore.unibas.ch/schwede/openstructure:latest`); Docker is present on
this machine. **Verifying that container runs is the first Phase 3 task.**

### 3. We hold ground truth for all 184 — so the discipline is self-imposed

The plan assumed Analog Set 1 would be the holdout and the rest blind. In fact
`structure_ground_truth/` has every answer, and `identifiers.parquet` carries the
organizers' own `phase` column: **92 phase-1** (live leaderboard half) and
**92 phase-2** (blinded until July 1).

Adopted as the dev/holdout split — it beats an arbitrary split because dev numbers
stay comparable to the published leaderboard. Nothing enforces the separation but
us, so `paperclip/permissions.yaml` grants `read_ground_truth` to the `eval` agent
alone, and `data/challenge/structure_ground_truth/**` is explicitly denied to
retrieval, cofold and rescore.

### 4. AlphaFold3 is not queue-gated — but it is not deployable out of the box

Two separate results.

**No approval queue.** The weights are a direct download:
`https://storage.googleapis.com/alphafold3/af3.bin.zst` → HTTP 200, 1,020,545,840 B
(~973 MB), publicly readable. The gate is accepting DeepMind's Model Parameters
Terms of Use (non-commercial research only), not waiting on anyone. Phase 0 put
this first on the critical path; there is no critical path here.

**proto-tools ships no Modal app for it.** This is not about the Modal account —
that is authenticated and working (`sumershinde22` / `proto-env`). It is that
proto-tools carries one Modal *service definition* per deployable tool under
`proto_tools/modal/structure_prediction/`, and that directory holds alphafold2,
boltz2, chai1, esmfold, esmfold2, opendde, protenix, rf3, viennarna — **no
`alphafold3_deployment`**. So `proto-tools deploy` has nothing to push, and AF3 is
absent from `deploy --list`. It runs only via `run_on="local"`, which needs an
NVIDIA GPU this Mac does not have.

**Gap closed — we wrote the deployment.** AF3 ships
`tools/structure_prediction/alphafold3/standalone/` (`setup.sh`,
`requirements.txt`, `python_version.txt`, `env_vars.txt`, `inference.py`,
`Singularity.def`) — a complete environment recipe — and a deployable tool's Modal
side is small: `boltz2_deployment/` is a single 150-line `boltz2_service.py`.

`modal/alphafold3_service.py` is that missing app:

- **Own `modal.App("pxr-af3")`**, kept in this repo rather than added to the
  installed proto-tools tree. Registering through proto-tools' manifest means
  editing four tables (`APP_BUCKETS`, `SERVICE_TIERS`, `SERVICE_TO_MODULE`,
  `GPU_SERVICES`) whose completeness check fails the import if any is missed —
  and any such edit under `~/.local/share/uv/tools/` is clobbered on upgrade.
- **Warmup builds the env, not a prediction.** `ToolInstance("alphafold3")
  .ensure_ready()` runs setup.sh at image-build time so the environment is baked
  into the layer; Boltz2's service folds its example input instead, but for AF3
  that would also pay MSA generation for no extra signal.
- **Weights on the `proto-cache` volume** at `alphafold3/af3.bin.zst`, resolved
  via `PROTO_ALPHAFOLD3_WEIGHTS_DIR=/weights/alphafold3`. Verified byte-exact
  against Google's bucket (1,020,545,840 B) and valid zstd. `setup.sh` prechecks
  them in seconds, so a staging mistake fails fast rather than after a ~30 min build.
- **`modal/standalone_overrides/alphafold3/`** is the hook for patching AF3's
  build (JAX pin, sif path) without touching proto-tools.

Cost of the choice: AF3 is invisible to `proto-tools deploy --list` and the
proto-tools MCP `run_tool`. `modal/client.py:cofold()` hides that — AF3 routes
through `modal.Cls`, the other four through proto-tools' runner.

## Also worth knowing

- **Submission format** (enforced by the organizers' validator): one `.zip` of
  `<structure_id>.pdb`; chain A protein, chain B ligand; exactly one residue named
  `LIG`; ≤2 chains; and the `LIG` bond graph must match the target SMILES under
  RDKit `AssignBondOrdersFromTemplate`. That last check is the silent failure —
  renaming a cofold model's ligand residue to `LIG` is not sufficient, the
  connectivity has to survive the PDB round-trip.
- **The validation script exists** — vendored to `eval/structure_validation.py`.
  The plan flagged its absence as a Phase 1 risk; that risk is closed.
- **Receptors: 64, not 68.** The announcement said 68; the final re-refined dataset
  is 64 entries (44 re-refined + 20 original depositions judged better as-is).
  62 ship `.pdb`; `9fzg` and `9fzh` are mmCIF-only and need conversion before any
  PDB-only tool sees them.
- **6 of the 64 receptors have two ligands bound simultaneously** — consistent with
  PXR's large promiscuous pocket, and a reason to expect multi-modal pose
  distributions.
- **Targets are fragment-sized:** MW 127–474 (median 309), 9–32 heavy atoms
  (median 21). Small ligands in a large pocket is exactly where placement is
  hardest and model confidence is least informative — which is the argument for
  consensus selection over confidence ranking in stage 03.

## One more trap, found only after the payment gate cleared

The AF3 deploy then failed with `ModuleNotFoundError: No module named
'alphafold3_service'`. Cause: `include_source=False`, copied from
`boltz2_service.py`. That flag is safe *there* because proto-tools' own service
modules already live inside the package tree mounted at `/pkg/proto-tools`; this
module sits outside it, so suppressing the source upload left the build container
unable to import `_warmup`. Dropping the flag in both the `run_function` and the
`@app.cls` fixed it, and the env then built in 321 s.

Worth noting the sequencing: the payment gate *masked* this bug. Two independent
failures stacked on the same command, and clearing the first is what exposed the
second — a reason to distrust "it failed for the reason I already know about".

## Immediate next steps

1. Deploy one cofold app (`boltz2`) to `proto-env` and run a single prediction —
   closes the exit gate and doubles as the Phase 1 vertical slice. Needs spend approval.
2. Verify the OST container scores a known-good pair (predict `x01378-1`, score
   against its ground truth) before building anything on top of `eval/score.py`.
3. Recalibrate Phase 2 for 184 targets and a $100 ceiling.
