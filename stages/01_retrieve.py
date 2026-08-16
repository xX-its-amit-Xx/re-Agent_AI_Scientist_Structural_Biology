#!/usr/bin/env python
"""Stage 01 — build the manifests every downstream stage reads from.

Sources (all already on disk under data/, pulled in Phase 0):
  data/challenge/    HuggingFace openadmet/pxr-challenge-train-test
  data/rerefined/    github.com/OpenADMET/pxr_xtal_re-refinement

Writes:
  manifest/ligands.csv    184 structure-track targets (id, smiles, phase, descriptors)
  manifest/receptors.csv  64 re-refined PXR receptor structures
  manifest/holdout.csv    the 92 phase-2 targets held out from all config selection

The dev/holdout split is the organizers' own `phase` column, not an arbitrary
one: phase 1 (92) was the live-leaderboard half during the challenge, phase 2
(92) stayed blinded until July 1. Reusing it keeps our internal numbers
comparable to the published leaderboard.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
from rdkit import Chem, RDLogger
from rdkit.Chem import Descriptors

RDLogger.DisableLog("rdApp.*")

ROOT = Path(__file__).resolve().parents[1]
CHALLENGE = ROOT / "data" / "challenge"
REREFINED = ROOT / "data" / "rerefined"
MANIFEST = ROOT / "manifest"

# Authoritative: validation/structure_validation.py in OpenADMET/PXR-Challenge-Tutorial
STRUCTURE_DATASET_SIZE = 184


def build_ligands() -> pd.DataFrame:
    blinded = pd.read_csv(CHALLENGE / "pxr-challenge_structure_TEST_BLINDED.csv")
    phases = pd.read_parquet(CHALLENGE / "pxr-challenge_structure_TEST_identifiers.parquet")

    # identifiers.parquet keys on "Molecule Name", which holds the structure id
    # (x#####-1) -- not the sparsely-populated "Molecule Name" of the blinded csv.
    phases = phases.rename(columns={"Molecule Name": "structure"})
    df = blinded.merge(phases, on="structure", how="left", validate="one_to_one")

    gt_dir = CHALLENGE / "structure_ground_truth"
    rows = []
    for rec in df.itertuples(index=False):
        mol = Chem.MolFromSmiles(rec.smiles)
        if mol is None:
            raise ValueError(f"unparseable SMILES for {rec.structure}: {rec.smiles}")
        gt = gt_dir / f"{rec.structure}.pdb"
        rows.append(
            {
                "structure_id": rec.structure,
                "smiles": rec.smiles,
                "canonical_smiles": Chem.MolToSmiles(mol),
                "phase": int(rec.phase),
                "split": "dev" if int(rec.phase) == 1 else "holdout",
                "mw": round(Descriptors.MolWt(mol), 2),
                "heavy_atoms": mol.GetNumHeavyAtoms(),
                "rot_bonds": Descriptors.NumRotatableBonds(mol),
                "ground_truth_pdb": str(gt.relative_to(ROOT)) if gt.exists() else "",
            }
        )
    return pd.DataFrame(rows).sort_values("structure_id").reset_index(drop=True)


def _parse_pdb_ids(path: Path) -> pd.DataFrame:
    """Parse pxr_pdb_ids.txt, which is headerless and variable-width.

    Layout is `pdb_id` followed by one 4-field group per bound ligand:
    (ligand_code, chains, resnums, smiles). Six of the 66 entries carry two
    ligands -- PXR's pocket is large enough to bind more than one at a time --
    so a fixed-width read_csv trips over the extra commas.
    """
    rows = []
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line:
            continue
        parts = line.split(",")
        pdb_id, rest = parts[0], parts[1:]
        if len(rest) % 4 != 0:
            raise ValueError(f"{path.name}: {pdb_id} has {len(rest)} ligand fields, expected a multiple of 4")
        groups = [rest[i : i + 4] for i in range(0, len(rest), 4)]
        rows.append(
            {
                "pdb_id": pdb_id,
                "n_ligands": len(groups),
                "ligand_code": ";".join(g[0] for g in groups),
                "chains": ";".join(g[1] for g in groups),
                "ligand_resnums": ";".join(g[2] for g in groups),
                "ligand_smiles": ";".join(g[3] for g in groups),
            }
        )
    return pd.DataFrame(rows)


def build_receptors() -> pd.DataFrame:
    meta = _parse_pdb_ids(REREFINED / "pxr_pdb_ids.txt")
    best = pd.read_csv(REREFINED / "pxr_structures.csv").rename(
        columns={"Structure": "pdb_id", "Best_structure": "best_refinement"}
    )
    df = meta.merge(best, on="pdb_id", how="outer")

    struct_dir = REREFINED / "pxr_rerefined_structures"
    rows = []
    for rec in df.itertuples(index=False):
        entry = struct_dir / str(rec.pdb_id)
        if not entry.is_dir():
            # 1ilh and 4j5x were dropped from the final re-refined dataset
            continue
        pdb = entry / f"{rec.pdb_id}.pdb"
        cif = entry / f"{rec.pdb_id}.cif"
        rows.append(
            {
                "pdb_id": rec.pdb_id,
                "n_ligands": rec.n_ligands,
                "ligand_code": rec.ligand_code,
                "chains": rec.chains,
                "ligand_smiles": rec.ligand_smiles,
                # NaN in pxr_structures.csv means the original deposition beat both
                # re-refinement protocols and was kept as-is.
                "best_refinement": rec.best_refinement
                if isinstance(rec.best_refinement, str)
                else "original_deposition",
                "pdb_path": str(pdb.relative_to(ROOT)) if pdb.exists() else "",
                "cif_path": str(cif.relative_to(ROOT)) if cif.exists() else "",
                # 9fzg/9fzh ship mmCIF only -- convert before any PDB-only tool sees them
                "has_pdb": pdb.exists(),
            }
        )
    return pd.DataFrame(rows).sort_values("pdb_id").reset_index(drop=True)


def main() -> int:
    MANIFEST.mkdir(exist_ok=True)

    ligands = build_ligands()
    receptors = build_receptors()
    holdout = ligands[ligands.split == "holdout"].copy()

    ligands.to_csv(MANIFEST / "ligands.csv", index=False)
    receptors.to_csv(MANIFEST / "receptors.csv", index=False)
    holdout.to_csv(MANIFEST / "holdout.csv", index=False)

    print(f"ligands.csv    {len(ligands):>4} targets  "
          f"(dev {(ligands.split == 'dev').sum()}, holdout {(ligands.split == 'holdout').sum()})")
    print(f"receptors.csv  {len(receptors):>4} structures  "
          f"({receptors.has_pdb.sum()} with .pdb, {(~receptors.has_pdb).sum()} cif-only)")
    print(f"holdout.csv    {len(holdout):>4} targets")

    missing_gt = (ligands.ground_truth_pdb == "").sum()
    print(f"ground-truth coverage: {len(ligands) - missing_gt}/{len(ligands)}")

    ok = True
    if len(ligands) != STRUCTURE_DATASET_SIZE:
        print(f"FAIL: expected {STRUCTURE_DATASET_SIZE} targets, got {len(ligands)}")
        ok = False
    if missing_gt:
        print(f"FAIL: {missing_gt} targets have no ground-truth PDB")
        ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
