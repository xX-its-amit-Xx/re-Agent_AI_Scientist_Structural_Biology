#!/usr/bin/env python
"""Stage 04 — assemble and validate the submission zip.

The format is not negotiable and is enforced by the organizers' own
validation/structure_validation.py. Every rule below comes from that file:

  * a single .zip
  * one .pdb per target, named <structure_id>.pdb
  * 184 of them (STRUCTURE_DATASET_SIZE), unless expected_ids is passed
  * each PDB has exactly one residue named LIG
  * each PDB has at most 2 chains
  * the LIG residue's bond graph must match the target SMILES, checked with
    RDKit AssignBondOrdersFromTemplate

The last rule is the one that silently fails: a cofold model emits the ligand
with its own residue name and element/bond guesses, so renaming to LIG is not
enough -- the connectivity has to survive a PDB round-trip. Validate before
submitting, not after.
"""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "manifest"
SUBMISSION = ROOT / "submission"

STRUCTURE_DATASET_SIZE = 184


def collect(pose_dir: Path, ligands: pd.DataFrame) -> tuple[dict[str, Path], list[str]]:
    """Map structure_id -> chosen pose PDB, reporting anything absent."""
    found, missing = {}, []
    for sid in ligands.structure_id:
        pdb = pose_dir / f"{sid}.pdb"
        if pdb.exists():
            found[sid] = pdb
        else:
            missing.append(sid)
    return found, missing


def write_zip(poses: dict[str, Path], dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        for sid, pdb in sorted(poses.items()):
            zf.write(pdb, arcname=f"{sid}.pdb")
    return dest


def validate(zip_path: Path, ligands: pd.DataFrame) -> tuple[bool, list[str]]:
    """Run the organizers' validator, vendored under eval/."""
    sys.path.insert(0, str(ROOT / "eval"))
    try:
        from structure_validation import validate_structure_submission
    except ImportError:
        return False, [
            "eval/structure_validation.py not found -- copy it from "
            "github.com/OpenADMET/PXR-Challenge-Tutorial (validation/)"
        ]
    return validate_structure_submission(
        zip_path,
        expected_ids=set(ligands.structure_id),
        expected_ligand_smiles=dict(zip(ligands.structure_id, ligands.smiles)),
        require_lig_resname=True,
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pose-dir", required=True, type=Path,
                    help="directory of <structure_id>.pdb chosen by stage 03")
    ap.add_argument("--out", type=Path, default=SUBMISSION / "pxr_structures.zip")
    ap.add_argument("--split", choices=["dev", "holdout", "all"], default="all")
    ap.add_argument("--allow-partial", action="store_true",
                    help="zip what exists -- for Phase 1 slice checks, never for a real submission")
    args = ap.parse_args()

    ligands = pd.read_csv(MANIFEST / "ligands.csv")
    if args.split != "all":
        ligands = ligands[ligands.split == args.split]

    # Resolve before use: the success line reports the path via relative_to(ROOT),
    # which raises on a relative --out rather than on anything to do with the zip.
    if not args.out.is_absolute():
        args.out = (Path.cwd() / args.out).resolve()

    poses, missing = collect(args.pose_dir, ligands)
    print(f"poses found: {len(poses)}/{len(ligands)}")
    if missing:
        print(f"missing {len(missing)}: {missing[:10]}{' ...' if len(missing) > 10 else ''}")
        if not args.allow_partial:
            print("refusing to build a partial submission (pass --allow-partial to override)")
            return 1

    zip_path = write_zip(poses, args.out)
    print(f"wrote {zip_path.relative_to(ROOT)} ({zip_path.stat().st_size / 1e6:.1f} MB)")

    if args.split == "all" and len(poses) != STRUCTURE_DATASET_SIZE and not args.allow_partial:
        print(f"WARNING: {len(poses)} structures, official set is {STRUCTURE_DATASET_SIZE}")

    ok, errors = validate(zip_path, ligands)
    if ok:
        print("VALID — passes the organizers' structure validator")
        return 0
    print(f"INVALID — {len(errors)} error(s):")
    for e in errors[:25]:
        print(f"  {e}")
    if len(errors) > 25:
        print(f"  ... and {len(errors) - 25} more")
    return 1


if __name__ == "__main__":
    sys.exit(main())
