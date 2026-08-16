#!/usr/bin/env python
"""Score predicted complexes against ground truth using the official metrics.

The metrics that count are the ones the organizers compute, not the ones that
are convenient to compute:

    LDDT-PLI   local distance difference test over protein-ligand contacts (higher better)
    BiSyRMSD   binding-site-superposed symmetry-corrected ligand RMSD (lower better)
    LDDT-LP    LDDT of the binding pocket itself (higher better)

All three come from OpenStructure's ost.mol.alg.ligand_scoring
(SCRMSDScorer, LDDTPLIScorer). Failures are penalised rather than dropped:
LDDT-PLI/LDDT-LP -> 0.0, BiSyRMSD -> 20.0 A. Two details worth keeping:

  * A NaN is not a skip. A pose OST cannot match scores 20 A, so a pipeline
    that silently drops hard targets looks better than it is. `coverage`
    reports the true match rate alongside the means.
  * proto-tools does NOT wrap OST. TM-align/US-align/PyMOL RMSD measure
    protein fold agreement and will happily report a great score for a pose
    with the ligand in the wrong subpocket. Do not substitute them here.

OST is not pip-installable; this runs the official container:
    registry.scicore.unibas.ch/schwede/openstructure:latest
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "manifest"
RESULTS = ROOT / "eval" / "results"

OST_IMAGE = "registry.scicore.unibas.ch/schwede/openstructure:latest"
STRUCTURE_METRICS = ["LDDT-PLI", "BiSyRMSD", "LDDT-LP"]
BISYRMSD_NAN_PENALTY = 20.0
BOOTSTRAP_SAMPLES = 1000

# Runs inside the OST container: scores one model/reference pair and prints JSON.
_OST_DRIVER = r'''
import json, sys
from ost.mol.alg.ligand_scoring import LDDTPLIScorer, SCRMSDScorer
from ost.mol.alg.scoring_base import PDBPrep

out = []
for model_path, ref_path, sid in json.load(open(sys.argv[1])):
    try:
        model = PDBPrep(model_path, fault_tolerant=True)
        ref = PDBPrep(ref_path, fault_tolerant=True)
        ml, rl = model.Select("rname=LIG"), ref.Select("rname=LIG")
        scr = SCRMSDScorer(model=model, target=ref, model_ligands=[ml], target_ligands=[rl])
        pli = LDDTPLIScorer(model=model, target=ref, model_ligands=[ml], target_ligands=[rl])
        rows = []
        for i, j in scr.assignment:
            rows.append({
                "LDDT-PLI": float(pli.score_matrix[i, j]),
                "BiSyRMSD": float(scr.score_matrix[i, j]),
                "LDDT-LP": float(scr.aux_matrix[i, j]["lddt_lp"]),
            })
        # rank as the organizers do: best LDDT-PLI, then lowest BiSyRMSD
        rows.sort(key=lambda r: (-r["LDDT-PLI"], r["BiSyRMSD"]))
        out.append({"Molecule Name": sid, **(rows[0] if rows else {})})
    except Exception as e:
        out.append({"Molecule Name": sid, "error": str(e)})
print("@@JSON@@" + json.dumps(out))
'''


def score_with_ost(pairs: list[tuple[Path, Path, str]], workdir: Path) -> pd.DataFrame:
    """Score (model, reference, id) triples inside the OST container."""
    workdir.mkdir(parents=True, exist_ok=True)
    driver = workdir / "_ost_driver.py"
    driver.write_text(_OST_DRIVER)

    # Container sees the repo at /work, so every path must be repo-relative.
    spec = [[f"/work/{m.relative_to(ROOT)}", f"/work/{r.relative_to(ROOT)}", sid] for m, r, sid in pairs]
    spec_path = workdir / "_ost_pairs.json"
    spec_path.write_text(json.dumps(spec))

    # The image's ENTRYPOINT is already ["ost"], so the script path goes straight
    # in as the first argument. Passing "ost" again makes the interpreter try to
    # open a file literally named 'ost' and fail with a bare FileNotFoundError.
    cmd = [
        "docker", "run", "--rm",
        "--platform", "linux/amd64",  # image is amd64-only; emulated on Apple silicon
        "-v", f"{ROOT}:/work",
        OST_IMAGE, f"/work/{driver.relative_to(ROOT)}", f"/work/{spec_path.relative_to(ROOT)}",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"OST container failed:\n{proc.stderr[-2000:]}")

    marker = [ln for ln in proc.stdout.splitlines() if ln.startswith("@@JSON@@")]
    if not marker:
        raise RuntimeError(f"no result from OST driver:\n{proc.stdout[-2000:]}")
    return pd.DataFrame(json.loads(marker[-1][len("@@JSON@@"):]))


def apply_penalties(df: pd.DataFrame) -> pd.DataFrame:
    """Record coverage, then fill failures with worst-case values."""
    for m in STRUCTURE_METRICS:
        if m not in df:
            df[m] = np.nan
    df["coverage"] = df["LDDT-PLI"].notna().astype(float)
    df["LDDT-PLI"] = df["LDDT-PLI"].fillna(0.0)
    df["LDDT-LP"] = df["LDDT-LP"].fillna(0.0)
    df["BiSyRMSD"] = df["BiSyRMSD"].fillna(BISYRMSD_NAN_PENALTY)
    return df


def bootstrap(df: pd.DataFrame, n: int = BOOTSTRAP_SAMPLES, seed: int = 0) -> pd.DataFrame:
    """Resample compounds with replacement so config deltas come with error bars.

    This is what separates a real improvement from noise: a config that gains
    0.01 LDDT-PLI with a bootstrap std of 0.03 has gained nothing.
    """
    rng = np.random.default_rng(seed)
    scores = df[STRUCTURE_METRICS].to_numpy()
    n_c = scores.shape[0]
    means = np.array([scores[rng.integers(0, n_c, n_c)].mean(axis=0) for _ in range(n)])
    return pd.DataFrame(
        {
            "metric": STRUCTURE_METRICS,
            "mean": means.mean(axis=0),
            "std": means.std(axis=0),
            "ci_lo": np.percentile(means, 2.5, axis=0),
            "ci_hi": np.percentile(means, 97.5, axis=0),
        }
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pose-dir", required=True, type=Path, help="directory of <structure_id>.pdb")
    ap.add_argument("--split", choices=["dev", "holdout", "all"], default="dev")
    ap.add_argument("--tag", default="run", help="names the output under eval/results/")
    ap.add_argument("--limit", type=int)
    args = ap.parse_args()

    ligands = pd.read_csv(MANIFEST / "ligands.csv")
    if args.split != "all":
        ligands = ligands[ligands.split == args.split]
    if args.limit:
        ligands = ligands.head(args.limit)

    # Resolve to absolute: paths are later rebased onto the container's /work
    # mount via relative_to(ROOT), which raises on a relative input.
    pose_dir = args.pose_dir if args.pose_dir.is_absolute() else (Path.cwd() / args.pose_dir).resolve()

    pairs = []
    for rec in ligands.itertuples(index=False):
        model = pose_dir / f"{rec.structure_id}.pdb"
        ref = ROOT / rec.ground_truth_pdb
        if model.exists() and ref.exists():
            pairs.append((model, ref, rec.structure_id))

    print(f"scoring {len(pairs)}/{len(ligands)} targets ({args.split}) with OST")
    if not pairs:
        print("nothing to score -- no poses found in --pose-dir")
        return 1

    per_compound = apply_penalties(score_with_ost(pairs, RESULTS / args.tag))
    agg = bootstrap(per_compound)

    RESULTS.mkdir(parents=True, exist_ok=True)
    per_compound.to_csv(RESULTS / f"{args.tag}_per_compound.csv", index=False)
    agg.to_csv(RESULTS / f"{args.tag}_summary.csv", index=False)

    print(f"\ncoverage: {per_compound.coverage.mean():.1%} "
          f"({int(per_compound.coverage.sum())}/{len(per_compound)} matched by OST)")
    print(agg.to_string(index=False))
    print(f"\nwrote eval/results/{args.tag}_{{per_compound,summary}}.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
