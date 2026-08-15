#!/usr/bin/env python
"""Stage 02 — cofold each target into a protein-ligand complex.

Reads manifest/ligands.csv, emits one job per (target x model x seed) and
dispatches it through proto-tools. Nothing here selects a pose; that is stage 03.

Ensemble sizing is a Phase 2 decision and deliberately not hardcoded -- pass
--models/--seeds once timing calibration says what fits the GPU budget.

Five cofold models, deployed two different ways — `modal/client.py:cofold()`
hides the difference, so always dispatch through it rather than calling a
backend directly:

    boltz2-prediction  chai1-prediction  protenix-prediction  rf3-prediction
        proto-tools apps, `open` weights, deployed with `proto-tools deploy`
    alphafold3-prediction
        our own Modal app (modal/alphafold3_service.py) -- proto-tools ships no
        AF3 deployment. Weights are DeepMind-licensed, non-commercial research
        only, and live on the proto-cache volume.

Input format is Boltz YAML, per the organizers' tutorial
(inputs/pxr_x01378-1.yaml in OpenADMET/PXR-Challenge-Tutorial):

    version: 1
    sequences:
      - protein: {id: A, sequence: <PXR LBD>}
      - ligand:  {id: B, smiles: <target SMILES>}

Chain A must be the protein and chain B the ligand, because stage 04 expects
that assignment when it renames the ligand residue to LIG.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "manifest"
RUNS = ROOT / "runs"

# PXR ligand-binding domain, chain A -- from the organizers' tutorial
# (inputs/PXR_protein_sequence.fasta). 291 residues.
PXR_LBD = (
    "GLTEEQRMMIRELMDAQMKTFDTTFSHFKNFRLPGVLSSGCELPESLQAPSREEAAKWSQVRKDLCSLKVSLQLRGEDGS"
    "VWNYKPPADSGGKEIFSLLPHMADMSTYMFKGIISFAKVISYFRDLPIEDQISLLKGAAFELCQLRFNTVFNAETGTWEC"
    "GRLSYCLEDTAGGFQQLLLEPMLKFHYMLKKLQLHEEEYVLMQAISLFSPDRPGVLQHRVVDQLQEQFAITLKSYIECNR"
    "PQPAHRFLFLKIMAMLTELRSINAQHTQRLLRIQDIHPFATPLMQELFGITGS"
)

DEFAULT_MODELS = ["boltz2-prediction"]
DEFAULT_SEEDS = [1]


def write_boltz_yaml(structure_id: str, smiles: str, dest: Path) -> Path:
    """Write one Boltz-format cofold input. Chain A protein, chain B ligand."""
    spec = {
        "version": 1,
        "sequences": [
            {"protein": {"id": "A", "sequence": PXR_LBD}},
            {"ligand": {"id": "B", "smiles": smiles}},
        ],
    }
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(yaml.safe_dump(spec, sort_keys=False, default_flow_style=False))
    return dest


def build_jobs(ligands: pd.DataFrame, models: list[str], seeds: list[int], run_dir: Path) -> list[dict]:
    jobs = []
    for rec in ligands.itertuples(index=False):
        yaml_path = write_boltz_yaml(
            rec.structure_id, rec.smiles, run_dir / "inputs" / f"{rec.structure_id}.yaml"
        )
        for model in models:
            for seed in seeds:
                jobs.append(
                    {
                        "structure_id": rec.structure_id,
                        "smiles": rec.smiles,
                        "model": model,
                        "seed": seed,
                        "input_yaml": str(yaml_path.relative_to(ROOT)),
                        "output_dir": str(
                            (run_dir / "cofold" / model / f"seed{seed}" / rec.structure_id).relative_to(ROOT)
                        ),
                        "status": "pending",
                    }
                )
    return jobs


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-id", required=True, help="names the directory under runs/")
    ap.add_argument("--models", nargs="+", default=DEFAULT_MODELS)
    ap.add_argument("--seeds", nargs="+", type=int, default=DEFAULT_SEEDS)
    ap.add_argument("--split", choices=["dev", "holdout", "all"], default="dev",
                    help="dev = phase 1 (92). Do not touch holdout until configs are frozen.")
    ap.add_argument("--limit", type=int, help="first N targets only -- for the Phase 1 vertical slice")
    ap.add_argument("--plan-only", action="store_true", help="write the job plan without dispatching")
    args = ap.parse_args()

    ligands = pd.read_csv(MANIFEST / "ligands.csv")
    if args.split != "all":
        ligands = ligands[ligands.split == args.split]
    if args.limit:
        ligands = ligands.head(args.limit)

    run_dir = RUNS / args.run_id
    jobs = build_jobs(ligands, args.models, args.seeds, run_dir)

    plan_path = run_dir / "jobs.json"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(json.dumps(jobs, indent=2))

    print(f"{len(ligands)} targets x {len(args.models)} models x {len(args.seeds)} seeds = {len(jobs)} jobs")
    print(f"plan: {plan_path.relative_to(ROOT)}")

    if args.plan_only:
        return 0

    # Dispatch is wired in Phase 1 against the proto-tools MCP `run_tool`, one
    # job at a time for the vertical slice, then fanned out in Phase 4.
    print("dispatch not yet wired -- rerun with --plan-only, or implement in Phase 1")
    return 1


if __name__ == "__main__":
    sys.exit(main())
