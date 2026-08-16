# Co-folding backends: what is deployed, and what it costs

Everything here was measured on this account, not read off a spec sheet. If a
number looks wrong, re-measure it rather than reasoning from the vendor's docs.

## What is deployed

Five co-folders are live in the Modal environment `proto-env`
(workspace `sumershinde22`):

| Model | App | Deployed by |
|---|---|---|
| Boltz-2 | `proto-tools-boltz2` | `proto-tools deploy` |
| Chai-1 | `proto-tools-chai1` | `proto-tools deploy` |
| Protenix | `proto-tools-protenix` | `proto-tools deploy` |
| RF3 | `proto-tools-rf3` | `proto-tools deploy` |
| AlphaFold3 | `pxr-af3` | **ours** — `modal/alphafold3_service.py` |

Verified end to end: `boltz2-prediction` returned a real structure on Modal
hardware (`ran_on: modal`, confidence 0.809, complex-pLDDT 0.942).

## Dispatch through `modal/client.py`, never directly

The five are not reachable the same way, which is the whole reason the client
exists:

- The four proto-tools apps dispatch through proto-tools' own runner and are
  visible to `proto-tools deploy --list` and the proto-tools MCP.
- **AlphaFold3 is not.** proto-tools ships an AF3 *tool wrapper* (schemas, docs,
  licence, a standalone env recipe) but no Modal *app* — there is no
  `alphafold3_deployment` in `proto_tools/modal/structure_prediction/`, so
  `proto-tools deploy` has nothing to push and AF3 never appears in its list.
  `modal/alphafold3_service.py` supplies the missing app and is reached with
  `modal.Cls.from_name("pxr-af3", "AlphaFold3Service", environment_name="proto-env")`.

`cofold()` hides the split. Calling a backend directly works until it silently
does not, and the failure looks like a missing model rather than a routing bug.

AF3 weights are DeepMind-licensed, **non-commercial research only**, and must not
be redistributed. They live on the `proto-cache` volume at
`alphafold3/af3.bin.zst`, never in git.

## The capacity ceiling: 23 GB

This account has no payment method, and Modal gates GPUs **by tier**, not
wholesale. Measured directly, one trivial function per tier:

| Tier | Result |
|---|---|
| T4 | allowed — Tesla T4, 15,360 MiB |
| L4 | allowed — NVIDIA L4, 23,034 MiB |
| A10 | allowed — NVIDIA A10, 23,028 MiB |
| L40S | refused — payment method required |
| A100-40GB | refused |
| A100-80GB | refused |
| H100 | refused |

So the ceiling is **23 GB, one GPU per job**. Everything runs on
`["A10:1", "L4:1"]`. T4 is excluded deliberately: at 15 GB it is the tier most
likely to OOM partway through a co-fold, and a job that dies at minute 20 costs
more than one that waited for a bigger card.

**This ceiling is a property of the current target, not a general result.** A
291-residue receptor plus a ≤32-heavy-atom ligand is roughly 320 tokens, which is
comfortable at 23 GB. A large complex would not be. When sizing diffusion samples
or batch size, treat OOM as a live constraint rather than assuming headroom.

proto-tools hardcodes `GPU_DEFAULT = ["H100:1", "H200:1", "A100-80GB:1"]` — every
one of them refused — and offers no environment-variable override.
`modal/patch_gpu_profile.py` repoints that constant, idempotently and reversibly.
**Re-run it after any `proto-tools` upgrade**; it edits an installed package and
will not survive one. `modal/alphafold3_service.py` names its tiers explicitly
rather than importing the patched constant, since it is ours and should not
depend on a patch to someone else's package.

## Traps that cost real time here

- **`proto-tools deploy` exits 0 while printing `❌` for every app.** The shell
  exit code is not a success signal. Parse the result lines.
- **Deploy serially.** Five concurrent app creates tripped `App create rate limit
  exceeded`, an error that looks nothing like the real problem.
- **`include_source=False` is not copyable between service files.** proto-tools'
  own services can omit the source because their module already lives inside the
  package tree mounted at `/pkg/proto-tools`. A service defined outside that tree
  fails at build with `ModuleNotFoundError: No module named '<service>'`.
- **Failures stack, and the first one masks the rest.** The payment gate hid the
  `include_source` bug entirely; clearing it is what exposed the second. Distrust
  "it failed for the reason I already know about".

## Native confidence fields

Record these unaltered — `confidence-selection` needs native units. From the
reference case:

| Model | Native signal |
|---|---|
| AlphaFold3 | `iptm` |
| Boltz-2 | `-complex_ipde` |
| OpenFold3 | `-mean(PAE[pocket, ligand])` |
| Chai-1 | `iptm` |

Two schema traps that silently corrupt cross-model comparison: one major model
reports complex pLDDT on **0–100** while another uses **0–1**, and PAE matrices
are **token-indexed** while per-atom pLDDT is **atom-indexed**, so they have
different lengths. Derive chain boundaries from token identifiers, never residue
counts — a ligand is many tokens, not one.
