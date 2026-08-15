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
) -> dict[str, Any]:
    from proto_tools import ToolRegistry

    spec = ToolRegistry.get(tool_key)
    return spec.run(input_dict, config_dict)


def build_input(model: str, sequence: str, smiles: str, seed: int) -> tuple[dict, dict]:
    """Shape one target for a given model.

    The cofold tools do not share an input schema. AlphaFold3 takes `complexes`;
    the Boltz-lineage tools take a Boltz-style YAML/spec. Normalising here keeps
    the branch out of stage 02.
    """
    if model == AF3_MODEL:
        # AlphaFold3Input -> complexes[].chains[], where a ligand chain carries
        # its SMILES in `sequence` and is disambiguated by entity_type.
        # Chain ids stay A/B to match the Boltz-side convention, so stage 04
        # can rename chain B's residue to LIG the same way for every model.
        return (
            {
                "complexes": [
                    {
                        "chains": [
                            {"id": "A", "sequence": sequence, "entity_type": "protein"},
                            {"id": "B", "sequence": smiles, "entity_type": "ligand"},
                        ]
                    }
                ]
            },
            {"seeds": [seed], "use_msa": True},
        )
    return (
        {
            "sequences": [
                {"protein": {"id": "A", "sequence": sequence}},
                {"ligand": {"id": "B", "smiles": smiles}},
            ]
        },
        {"seed": seed},
    )


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
        return _proto_predict(model, input_dict, config_dict)
    raise ValueError(f"unknown cofold model {model!r}; expected one of {sorted(PROTO_MODELS | {AF3_MODEL})}")
