"""Call the cofold models from the pipeline, whichever way they are deployed.

Two dispatch paths, because AlphaFold3 is deployed differently from the rest:

  boltz2 / chai1 / protenix / rf3   proto-tools apps -> proto-tools' own runner
  alphafold3                        our app (modal/alphafold3_service.py) -> modal.Cls

`cofold()` hides the difference so `stages/02_cofold.py` can treat all five
models uniformly. Everything returns the tool's serialized Output dict.
"""

from __future__ import annotations

from typing import Any

AF3_APP = "pxr-af3"
AF3_CLASS = "AlphaFold3Service"

# Models proto-tools deploys and dispatches itself.
PROTO_MODELS = {
    "boltz2-prediction",
    "chai1-prediction",
    "protenix-prediction",
    "rf3-prediction",
}
AF3_MODEL = "alphafold3-prediction"

# Models whose config rejects `include_pae_matrix` outright. RF3 has no per-token
# PAE to return, so requesting it is a validation error rather than a no-op --
# and a per-token signal simply is not available from it.
NO_PAE_MATRIX = {"rf3-prediction"}


def _af3_predict(
    input_dict: dict[str, Any],
    config_dict: dict[str, Any],
    *,
    environment: str = "proto-env",
) -> dict[str, Any]:
    import modal

    svc = modal.Cls.from_name(AF3_APP, AF3_CLASS, environment_name=environment)
    return svc().predict.remote(input_dict, config_dict)


def _proto_predict(
    tool_key: str,
    input_dict: dict[str, Any],
    config_dict: dict[str, Any],
    *,
    environment: str = "proto-env",
) -> dict[str, Any]:
    """Run a proto-tools model on its deployed Modal app.

    `ToolSpec` has no `.run()`; calling the bare `run_boltz2`-style function would
    execute locally, which needs a GPU this machine does not have. The deployed
    path is `dispatch_to_modal`, and it takes validated pydantic models rather
    than dicts — so coerce through the spec's own input/config models, which also
    surfaces a schema mistake here instead of inside a container.
    """
    from proto_tools import ToolRegistry
    from proto_tools.modal import dispatch_to_modal

    spec = ToolRegistry.get(tool_key)
    inputs = spec.input_model.model_validate(input_dict)
    config = spec.config_model.model_validate(config_dict)
    out = dispatch_to_modal(tool_key, inputs, config, environment=environment)
    return out.model_dump()


def build_input(model: str, sequence: str, smiles: str, seed: int,
                msa: dict[str, Any] | None = None) -> tuple[dict, dict]:
    """Shape one target for a given model.

    All five cofolders inherit `StructurePredictionInput`, so they share one input
    shape: `complexes[].chains[]`. A chain dict carrying `sequence` validates as a
    protein `Chain`; one carrying `smiles` validates as a ligand `Fragment`. Chain
    ids stay A/B for every model, so stage 04 renames chain B's residue to LIG the
    same way regardless of which model produced the pose.

    `msa` is the single biggest lever on wall time for this target. Every job here
    folds the *same* receptor against a different ligand, so regenerating the
    protein MSA per job re-derives an identical answer hundreds of times. Supplying
    it once removes that work from every call; a supplied MSA overrides
    `use_msa=False`, so the flag is set to stop generation rather than to disable
    the alignment.

    Only the config differs otherwise: AlphaFold3 takes a `seeds` list, the rest
    take a scalar `seed`.
    """
    input_dict: dict[str, Any] = {
        "complexes": [
            {
                "chains": [
                    {"id": "A", "sequence": sequence, "entity_type": "protein"},
                    {"id": "B", "smiles": smiles},
                ]
            }
        ]
    }
    # include_pae_matrix is not cosmetic: min interface PAE is among the strongest
    # ranking signals available and cannot be recovered after the fact. But RF3
    # *rejects* the flag rather than ignoring it -- it emits chain-pair aggregates
    # and an avg_pae scalar, never a per-token LxL matrix -- so asking for it there
    # fails the whole job at config validation.
    config: dict[str, Any] = {}
    if model not in NO_PAE_MATRIX:
        config["include_pae_matrix"] = True
    if msa:
        # chain index 0 is the protein; the ligand carries no alignment
        input_dict["msas"] = [{"per_chain": {0: msa}, "paired": False}]
        config["use_msa"] = False
    else:
        config["use_msa"] = True
    config["seeds" if model == AF3_MODEL else "seed"] = [seed] if model == AF3_MODEL else seed
    return input_dict, config


def cofold_batch(
    model: str,
    input_dicts: list[dict[str, Any]],
    config_dicts: list[dict[str, Any]],
    *,
    environment: str = "proto-env",
    scaledown_window: int | None = None,
) -> list[dict[str, Any] | Exception]:
    """Run many jobs of one model as a single fan-out.

    Modal's starmap spreads the batch across containers, so throughput stops being
    one-job-at-a-time and the per-call container reconnect is paid once for the
    batch rather than once per job. Results come back positionally, and a failed
    element arrives as an Exception rather than aborting its siblings — so one bad
    target costs one row.

    Batch only covers the proto-tools models. AF3 is our own `modal.Cls` app and
    has no starmap equivalent, so it stays serial; `cofold()` still handles it.
    """
    if model == AF3_MODEL:
        raise ValueError("alphafold3 has no batch path; dispatch it through cofold() serially")
    if model not in PROTO_MODELS:
        raise ValueError(f"unknown cofold model {model!r}")

    from proto_tools import ToolRegistry
    from proto_tools.modal import dispatch_batch_to_modal

    spec = ToolRegistry.get(model)
    inputs = [spec.input_model.model_validate(d) for d in input_dicts]
    configs = [spec.config_model.model_validate(d) for d in config_dicts]
    results = dispatch_batch_to_modal(
        model, inputs, configs, environment=environment, scaledown_window=scaledown_window
    )
    return [r if isinstance(r, Exception) else r.model_dump() for r in results]


def cofold(
    model: str,
    input_dict: dict[str, Any],
    config_dict: dict[str, Any],
    *,
    environment: str = "proto-env",
) -> dict[str, Any]:
    """Run one cofold job, routing to whichever backend owns the model."""
    if model == AF3_MODEL:
        return _af3_predict(input_dict, config_dict, environment=environment)
    if model in PROTO_MODELS:
        return _proto_predict(model, input_dict, config_dict, environment=environment)
    raise ValueError(f"unknown cofold model {model!r}; expected one of {sorted(PROTO_MODELS | {AF3_MODEL})}")
