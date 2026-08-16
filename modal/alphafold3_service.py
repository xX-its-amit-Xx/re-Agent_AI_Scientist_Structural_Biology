"""AlphaFold3 Modal service — the deployment proto-tools does not ship.

proto-tools wraps AlphaFold3 as a tool (schemas, standalone env recipe, license)
but carries no Modal app for it: `proto_tools/modal/structure_prediction/` has
deployments for alphafold2, boltz2, chai1, esmfold, esmfold2, opendde, protenix,
rf3 and viennarna, and no `alphafold3_deployment`. So `proto-tools deploy` has
nothing to push and AF3 never appears in `deploy --list`. This file is that
missing piece.

It deliberately lives in *this* repo rather than patching the installed
proto-tools tree, for two reasons: an in-place edit under
`~/.local/share/uv/tools/` is silently clobbered on the next upgrade, and
registering a service through proto-tools' manifest means editing four separate
tables (APP_BUCKETS, SERVICE_TIERS, SERVICE_TO_MODULE, GPU_SERVICES) whose
completeness check fails the import if any is missed. Owning the app outright is
smaller and survives upgrades.

The tradeoff: this service is invisible to `proto-tools deploy --list` and to the
proto-tools MCP `run_tool`. Call it through `client.py` instead, which is what
`stages/02_cofold.py` does.

Deploy (weights MUST be staged first — setup.sh fails fast without them):

    .venv/bin/modal volume create proto-cache
    .venv/bin/modal volume put proto-cache af3.bin.zst alphafold3/af3.bin.zst
    .venv/bin/modal deploy -e proto-env modal/alphafold3_service.py

Weights are DeepMind-licensed, non-commercial research only, and must not be
redistributed — hence the volume, and hence af3.bin.zst in .gitignore.
"""

from pathlib import Path
from typing import Any

import modal

from proto_tools.modal.app import (
    HF_TOKEN_SECRET,
    MODEL_CACHE,
    SCALEDOWN_WINDOW,
    SERVICE_RETRIES,
)
from proto_tools.modal.base_images import GPU_BASE, with_proto_tools
from proto_tools.modal.utils import RUNTIME_ENV, ensure_gpu_ready, env_for, run_tool_call

APP_NAME = "pxr-af3"

# Stated explicitly rather than imported from proto_tools.modal.gpu_profiles, so
# this file does not silently depend on the state of an installed package that
# any upgrade can change. It happens to match GPU_DEFAULT today.
#
# 80 GB tiers. An earlier revision ran on A10/L4 (23 GB) because this workspace
# had no payment method and Modal gates GPUs by tier -- see
# structure-ensemble/reference/backends.md for that episode. Billing is now
# active and H100/A100-80GB schedule normally.
#
# AF3 is the most memory-hungry of the five: 5 diffusion samples per seed, and
# memory scales with token count. 23 GB was workable for a PXR LBD plus a small
# fragment (~320 tokens) but had no headroom; 80 GB removes OOM as a live
# constraint on sample count and admits much larger complexes.
GPU_TIERS = ["H100:1", "H200:1", "A100-80GB:1"]

# Where the weights live on the shared proto-cache volume. The tool resolves
# PROTO_ALPHAFOLD3_WEIGHTS_DIR first, ahead of PROTO_MODEL_CACHE and PROTO_HOME.
WEIGHTS_DIR = "/weights/alphafold3"

# AF3 does num_diffusion_samples (default 5) per seed and may generate MSAs via
# MMseqs2, so it sits on the same one-hour tier as the other cofold services
# (SERVICE_MODAL_TIMEOUTS gives Boltz2/Chai1/Protenix/RF3 3600s).
TIMEOUT_S = 3600


def _warmup() -> None:
    """Build the AlphaFold3 standalone env at image-build time.

    `ensure_ready()` runs the toolkit's setup.sh — CUDA toolkit, JAX, HMMER,
    an AF3 source clone, and build_data — without running inference. Boltz2's
    service warms up by folding its example input, but AF3 inference would also
    pay MSA generation here for no extra signal: the thing worth baking into the
    image layer is the environment, and a failure to build it should fail the
    deploy rather than the first prediction.

    setup.sh prechecks the weights before any heavy work, so a missing
    af3.bin.zst fails this in seconds rather than after a ~30 minute build.
    """
    from proto_tools.utils.tool_instance import ToolInstance

    ToolInstance("alphafold3").ensure_ready()


image = with_proto_tools(GPU_BASE, overrides="alphafold3", overrides_dir=Path(__file__).parent)
image = (
    image.env(
        {
            **env_for(),
            "PROTO_ALPHAFOLD3_WEIGHTS_DIR": WEIGHTS_DIR,
            # MSA generation and any HF-backed assets land on the volume, not
            # the container's ephemeral disk.
            "HF_HOME": "/weights",
        }
    )
    # NOTE: no include_source=False here, unlike proto-tools' own service files.
    # Theirs can omit the source because their _warmup lives inside the
    # proto-tools package already mounted at /pkg/proto-tools. This module sits
    # outside that tree, so suppressing the source upload makes the build
    # container fail with `ModuleNotFoundError: No module named
    # 'alphafold3_service'` when it tries to import _warmup.
    .run_function(
        _warmup,
        gpu=GPU_TIERS,
        volumes={"/weights": MODEL_CACHE},
        secrets=[HF_TOKEN_SECRET],
    )
    .env(RUNTIME_ENV)
)


app = modal.App(APP_NAME, secrets=[HF_TOKEN_SECRET])


@app.cls(
    # Same reason as the warmup above: AlphaFold3Service is defined in this
    # module, which is not part of the mounted proto-tools tree, so the runtime
    # container needs the source uploaded to resolve the class.
    image=image,
    gpu=GPU_TIERS,
    scaledown_window=SCALEDOWN_WINDOW,
    volumes={"/weights": MODEL_CACHE},
    timeout=TIMEOUT_S,
    retries=SERVICE_RETRIES,
    secrets=[HF_TOKEN_SECRET],
)
class AlphaFold3Service:
    """Modal service for AlphaFold3 structure prediction."""

    @modal.enter()
    def setup(self) -> None:
        """Start a persistent worker so weights stay resident across requests."""
        ensure_gpu_ready("alphafold3")
        from proto_tools.utils.tool_instance import ToolInstance

        self._persist_ctx = ToolInstance.persist_tool("alphafold3")
        self.instance = self._persist_ctx.__enter__()

    @modal.exit()
    def teardown(self) -> None:
        self._persist_ctx.__exit__(None, None, None)

    @modal.method()
    def predict(self, input_dict: dict[str, Any], config_dict: dict[str, Any]) -> dict[str, Any]:
        """Run AlphaFold3 structure prediction.

        Args:
            input_dict (dict[str, Any]): Serialized ``AlphaFold3Input`` — notably
                ``complexes``, each carrying protein sequences and ligand SMILES.
            config_dict (dict[str, Any]): Serialized ``AlphaFold3Config``.

        Returns:
            dict[str, Any]: Structure prediction results with confidence metrics.
        """
        from proto_tools.tools.structure_prediction.alphafold3.alphafold3 import (
            AlphaFold3Config,
            AlphaFold3Input,
            run_alphafold3,
        )

        # model_dir is left to env resolution (PROTO_ALPHAFOLD3_WEIGHTS_DIR)
        # unless the caller overrides it -- config wins over env in the tool.
        return run_tool_call(
            run_alphafold3,
            AlphaFold3Input,
            AlphaFold3Config,
            input_dict,
            config_dict,
            instance=self.instance,
        )
