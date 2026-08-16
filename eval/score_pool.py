#!/usr/bin/env python
"""Score every candidate in a pool against ground truth, for the oracle gap.

`eval/score.py` scores one chosen pose per item -- what a submission looks like.
This scores the *whole pool*, which is what measuring a ceiling requires and what
no submission ever contains.

Two things this must get right, both of which are easy to get silently wrong:

  * Every candidate is converted through the same submission-format path a real
    pose takes, so a pool score reflects poses that could actually be submitted.
    A candidate that fails conversion is recorded as a failure, not dropped --
    dropping it flatters the model that produced it.
  * The output of this file is ground truth. It feeds `eval/pool.py` for
    diagnosis and it must never reach a selector; see `leak-containment`.

    .venv/bin/python eval/score_pool.py --run-id pilot
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "eval" / "results"
sys.path.insert(0, str(ROOT / "eval"))
sys.path.insert(0, str(ROOT / "stages"))

from score import BISYRMSD_NAN_PENALTY, STRUCTURE_METRICS, score_with_ost  # noqa: E402
from pose_to_pdb import convert  # noqa: E402


def prepare(run_dir: Path, ligands: pd.DataFrame) -> tuple[list[tuple[Path, Path, str]], list[dict]]:
    """Convert every finished candidate to submission-format PDB.

    The OST driver keys results by a single id, so each candidate gets a
    synthetic one (`<sid>__<model>__s<seed>__<sample>`) that is split back apart
    after scoring.
    """
    jobs = json.loads((run_dir / "jobs.json").read_text())
    smiles = dict(zip(ligands.structure_id, ligands.smiles))
    gt = dict(zip(ligands.structure_id, ligands.ground_truth_pdb))

    pairs, failures = [], []
    pose_dir = run_dir / "candidates"
    for job in jobs:
        if job.get("status") != "done":
            continue
        sid = job["structure_id"]
        for i, cif in enumerate(job["structures"]):
            key = f"{sid}__{job['model']}__s{job['seed']}__{i}"
            dest = pose_dir / f"{key}.pdb"
            try:
                if not dest.exists():
                    convert(ROOT / cif, smiles[sid], dest)
            except Exception as e:
                failures.append({
                    "structure_id": sid, "model": job["model"], "seed": job["seed"],
                    "sample": i, "convert_error": f"{type(e).__name__}: {e}",
                })
                continue
            ref = ROOT / gt[sid]
            if ref.exists():
                pairs.append((dest, ref, key))
    return pairs, failures


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-id", required=True)
    args = ap.parse_args()

    run_dir = ROOT / "runs" / args.run_id
    ligands = pd.read_csv(ROOT / "manifest" / "ligands.csv")

    pairs, failures = prepare(run_dir, ligands)
    print(f"{len(pairs)} candidates converted, {len(failures)} failed conversion")
    if failures:
        for f in failures[:10]:
            print(f"  {f['structure_id']} {f['model']}: {f['convert_error'][:110]}")
    if not pairs:
        print("nothing to score")
        return 1

    df = score_with_ost(pairs, RESULTS / f"{args.run_id}_pool_ost")

    # Split the synthetic key back into the columns eval/pool.py joins on.
    parts = df["Molecule Name"].str.split("__", expand=True)
    df["structure_id"], df["model"] = parts[0], parts[1]
    df["seed"] = parts[2].str.lstrip("s").astype(int)
    df["sample"] = parts[3].astype(int)

    for m in STRUCTURE_METRICS:
        if m not in df:
            df[m] = pd.NA
    df["scored"] = df["LDDT-PLI"].notna()
    df["LDDT-PLI"] = df["LDDT-PLI"].fillna(0.0)
    df["LDDT-LP"] = df["LDDT-LP"].fillna(0.0)
    df["BiSyRMSD"] = df["BiSyRMSD"].fillna(BISYRMSD_NAN_PENALTY)

    # Conversion failures are candidates too, and they are worst-case ones.
    if failures:
        fdf = pd.DataFrame(failures)
        for m, v in [("LDDT-PLI", 0.0), ("LDDT-LP", 0.0), ("BiSyRMSD", BISYRMSD_NAN_PENALTY)]:
            fdf[m] = v
        fdf["scored"] = False
        df = pd.concat([df, fdf], ignore_index=True)

    cols = ["structure_id", "model", "seed", "sample", *STRUCTURE_METRICS, "scored"]
    out = RESULTS / f"{args.run_id}_truth.csv"
    df[cols + [c for c in ("convert_error",) if c in df]].to_csv(out, index=False)

    print(f"\nscored {int(df.scored.sum())}/{len(df)} candidates")
    print(df.groupby("model")[STRUCTURE_METRICS].mean().round(4).to_string())
    print(f"\nwrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
