#!/usr/bin/env python
"""Stage 03 — pick one pose per target from the ensemble.

PXR is the reason this stage exists. The pocket is large, hydrophobic and
promiscuous, the adjacent loops are disordered, and the receptor is documented
in multiple distinct conformations -- so any single cofold run is a sample from
a wide distribution, not an answer. The ensemble hedges; this stage collapses it.

Selection strategies (choose per-config in Phase 6, measure on dev in Phase 3):

  confidence   highest model-reported confidence (ipTM / plDDT / affinity head).
               Cheap, and a reasonable baseline -- but each model's confidence
               is calibrated on its own training distribution, so scores are
               not comparable across models without normalisation.

  medoid       the pose with lowest mean symmetry-corrected ligand RMSD to all
               other poses in the ensemble, after superposing on the binding
               site. Consensus rather than self-report: it asks which pose the
               ensemble agrees on. Robust when models disagree about which
               subpocket the ligand sits in, which for PXR is the usual failure.

  hybrid       medoid within the top-k by confidence -- discards low-confidence
               outliers before asking for agreement.

Ligand RMSD here must be symmetry-corrected (RDKit GetBestRMS over automorphisms),
otherwise a ring flip in a symmetric fragment reads as a large disagreement.
Note this is our internal pose-agreement metric, not the scoring metric --
eval/score.py owns the official LDDT-PLI / BiSyRMSD numbers.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "manifest"
RUNS = ROOT / "runs"

STRATEGIES = ["confidence", "medoid", "hybrid"]


def load_ensemble(run_dir: Path, structure_id: str) -> list[Path]:
    """Every predicted pose for one target, across models and seeds."""
    return sorted(run_dir.glob(f"cofold/*/seed*/{structure_id}/*.pdb"))


def select_confidence(poses: list[Path], conf: dict[Path, float]) -> Path:
    return max(poses, key=lambda p: conf.get(p, float("-inf")))


def select_medoid(poses: list[Path]) -> Path:
    """Lowest mean symmetry-corrected ligand RMSD to the rest of the ensemble."""
    raise NotImplementedError("Phase 4: pairwise GetBestRMS over binding-site-superposed ligands")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--strategy", choices=STRATEGIES, default="medoid")
    ap.add_argument("--top-k", type=int, default=5, help="for --strategy hybrid")
    ap.add_argument("--split", choices=["dev", "holdout", "all"], default="dev")
    ap.add_argument("--out", type=Path, help="default runs/<run-id>/selected/")
    args = ap.parse_args()

    run_dir = RUNS / args.run_id
    out_dir = args.out or run_dir / "selected"
    out_dir.mkdir(parents=True, exist_ok=True)

    ligands = pd.read_csv(MANIFEST / "ligands.csv")
    if args.split != "all":
        ligands = ligands[ligands.split == args.split]

    counts = {sid: len(load_ensemble(run_dir, sid)) for sid in ligands.structure_id}
    have = {k: v for k, v in counts.items() if v}
    print(f"targets with poses: {len(have)}/{len(ligands)}")
    if have:
        sizes = sorted(have.values())
        print(f"ensemble size min/median/max: {sizes[0]}/{sizes[len(sizes) // 2]}/{sizes[-1]}")
    print(f"strategy: {args.strategy} -> {out_dir.relative_to(ROOT)}")

    print("selection not yet wired -- implement alongside the Phase 4 ensemble")
    return 1


if __name__ == "__main__":
    sys.exit(main())
