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

## Capacity: 80 GB, one GPU per job

Everything runs on `["H100:1", "H200:1", "A100-80GB:1"]` — proto-tools'
`GPU_DEFAULT`, which `modal/alphafold3_service.py` also names explicitly rather
than importing, so our app does not depend on the state of an installed package.

Measured on this account, one trivial function per tier:

| Tier | Memory |
|---|---|
| H100 | 81,559 MiB |
| A100-80GB | 81,920 MiB |
| L40S | 46,068 MiB |
| A10 / L4 | 23,034 MiB |
| T4 | 15,360 MiB |

At 80 GB, OOM is not a live constraint for this target — a 291-residue receptor
plus a ≤32-heavy-atom fragment is roughly 320 tokens. It can become one for much
larger complexes or aggressive sample counts, so measure rather than assume when
either changes.

### If GPU deploys suddenly fail, read this before debugging anything else

Modal gates GPUs **by tier**, not wholesale, and the error names the tier:

```
Please add a payment method to use H100 GPU functions.
```

That is a **billing** message, not a capacity or quota one, and it blocked every
co-folder here until the account's payment method was sorted. Two things made it
expensive to diagnose:

- The lower tiers kept working, so "GPUs are broken" was false — T4/L4/A10
  scheduled fine throughout. Probing one trivial function per tier is what
  located the boundary, and is the fastest way to re-locate it if this recurs.
- `proto-tools deploy` **exits 0 while printing `❌`** for every app, so nothing
  in the shell's exit status said anything was wrong.

`modal/patch_gpu_profile.py` exists for this case: proto-tools hardcodes
`GPU_DEFAULT` with no environment-variable override, so the script repoints it
idempotently and reversibly (`--check`, `--revert`). It is currently **reverted**,
because the default tiers work again. If billing lapses, re-apply it to fall back
to A10/L4 rather than losing the pipeline entirely — and re-run it after any
`proto-tools` upgrade, since it edits an installed package.

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
