#!/usr/bin/env python
"""Physics and geometry descriptors per candidate — the Scoring half's challengers.

Adds signals a cofolder does not emit, so `eval/sweep.py` can test them against
the z-scored-confidence baseline. Every one is computed from the candidate's own
coordinates and **no ground truth**, which is why this lives in `stages/`.

Read this before adding one: the prior on these winning is low. Strain gating,
plausibility filters and physics rescoring have all been tried on co-folding pose
pools and lost to plain z-scored native confidence. That is a reason to build them
as *challengers* with a fair test, not a reason to skip them -- a documented
negative result is a real output, and the alternative is re-litigating the same
idea every few weeks. What is refuted is adopting them by default.

Descriptors, and what each is actually measuring:

  mmff_strain        ligand internal energy at the pose geometry minus its relaxed
                     energy. A pose the model bent into an implausible conformer
                     scores high. Sensitive to protonation and to the template
                     match, so a large value can mean a bad pose or a bad parse.
  contacts_4a        heavy-atom protein-ligand pairs within 4 A. Crude buriedness;
                     a ligand dangling in solvent scores low.
  min_contact_dist   closest protein-ligand heavy-atom approach.
  clashes            pairs closer than 0.75x the sum of covalent radii. A pose the
                     model pushed into the protein.
  radius_of_gyration ligand compactness, as a shape control.

    .venv/bin/python stages/descriptors.py --run-id pilot
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from rdkit import Chem, RDLogger
from rdkit.Chem import AllChem

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "stages"))

from candidates import load_candidates  # noqa: E402
from pose_to_pdb import LIG_RESNAME, convert  # noqa: E402

DESCRIPTORS = ["mmff_strain", "contacts_4a", "min_contact_dist", "clashes", "radius_of_gyration"]

# Lower is better for all but contacts and gyration, which have no monotone
# direction on their own; sweep.py treats direction per signal.
LOWER_IS_BETTER = {"mmff_strain", "clashes"}

_COVALENT = {"C": 0.76, "N": 0.71, "O": 0.66, "S": 1.05, "F": 0.57, "CL": 1.02,
             "BR": 1.20, "I": 1.39, "P": 1.07, "H": 0.31}


def mmff_strain(mol: Chem.Mol) -> float | None:
    """Pose energy minus relaxed energy, kcal/mol, using MMFF94.

    Returns None rather than 0.0 when MMFF has no parameters for the molecule --
    a missing descriptor and a zero-strain pose are different facts, and merging
    them silently credits unparameterised ligands with perfect scores.
    """
    RDLogger.DisableLog("rdApp.*")
    try:
        m = Chem.AddHs(mol, addCoords=True)
        props = AllChem.MMFFGetMoleculeProperties(m)
        if props is None:
            return None
        ff = AllChem.MMFFGetMoleculeForceField(m, props)
        if ff is None:
            return None
        e_pose = ff.CalcEnergy()

        relaxed = Chem.Mol(m)
        ff_r = AllChem.MMFFGetMoleculeForceField(relaxed, AllChem.MMFFGetMoleculeProperties(relaxed))
        ff_r.Minimize(maxIts=2000)
        return float(e_pose - ff_r.CalcEnergy())
    except Exception:
        return None
    finally:
        RDLogger.EnableLog("rdApp.*")


def geometry(pdb: Path) -> dict:
    """Protein-ligand contact geometry, straight off the written PDB."""
    import gemmi

    st = gemmi.read_structure(str(pdb))
    st.remove_hydrogens()
    lig, prot = [], []
    for ch in st[0]:
        for res in ch:
            target = lig if res.name == LIG_RESNAME else prot
            for a in res:
                target.append((a.element.name.upper(), a.pos.x, a.pos.y, a.pos.z))
    if not lig or not prot:
        return {k: None for k in DESCRIPTORS if k != "mmff_strain"}

    L = np.array([[x, y, z] for _, x, y, z in lig])
    P = np.array([[x, y, z] for _, x, y, z in prot])
    d = np.linalg.norm(L[:, None, :] - P[None, :, :], axis=-1)

    lr = np.array([_COVALENT.get(e, 0.77) for e, *_ in lig])
    pr = np.array([_COVALENT.get(e, 0.77) for e, *_ in prot])
    clash_cut = 0.75 * (lr[:, None] + pr[None, :])

    return {
        "contacts_4a": int((d < 4.0).sum()),
        "min_contact_dist": float(d.min()),
        "clashes": int((d < clash_cut).sum()),
        "radius_of_gyration": float(np.sqrt(((L - L.mean(0)) ** 2).sum(1).mean())),
    }


def describe_one(cif: Path, smiles: str, workdir: Path, key: str) -> dict:
    """Convert to submission format once, then read every descriptor off it.

    Using the converted PDB rather than the raw CIF is deliberate: these
    descriptors must describe the pose that would actually be submitted, including
    anything the conversion changed.
    """
    pdb = workdir / f"{key}.pdb"
    if not pdb.exists():
        convert(cif, smiles, pdb)

    out = geometry(pdb)
    lig_mol = Chem.MolFromPDBFile(str(pdb), removeHs=True, sanitize=False)
    strain = None
    if lig_mol is not None:
        frag = Chem.RWMol(lig_mol)
        keep = [a.GetIdx() for a in frag.GetAtoms()
                if a.GetPDBResidueInfo() and a.GetPDBResidueInfo().GetResidueName().strip() == LIG_RESNAME]
        if keep:
            sub = Chem.RWMol(lig_mol)
            for idx in sorted(set(range(lig_mol.GetNumAtoms())) - set(keep), reverse=True):
                sub.RemoveAtom(idx)
            ref = Chem.MolFromSmiles(smiles)
            RDLogger.DisableLog("rdApp.*")
            try:
                strain = mmff_strain(AllChem.AssignBondOrdersFromTemplate(ref, sub.GetMol()))
            except Exception:
                strain = None
            finally:
                RDLogger.EnableLog("rdApp.*")
    out["mmff_strain"] = strain
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-id", required=True)
    args = ap.parse_args()

    run_dir = ROOT / "runs" / args.run_id
    cands = load_candidates(run_dir)
    done = cands[cands.status == "done"]
    workdir = run_dir / "candidates"
    workdir.mkdir(parents=True, exist_ok=True)

    rows, failed = [], 0
    for r in done.itertuples(index=False):
        key = f"{r.structure_id}__{r.model}__s{r.seed}__{r.sample}"
        rec = {"structure_id": r.structure_id, "model": r.model, "seed": r.seed, "sample": r.sample}
        try:
            rec.update(describe_one(ROOT / r.cif, r.smiles, workdir, key))
        except Exception as e:
            rec.update({k: None for k in DESCRIPTORS})
            rec["descriptor_error"] = f"{type(e).__name__}: {e}"
            failed += 1
        rows.append(rec)

    df = pd.DataFrame(rows)
    dest = run_dir / "descriptors.csv"
    df.to_csv(dest, index=False)

    print(f"{len(df)} candidates described, {failed} failed")
    present = [d for d in DESCRIPTORS if d in df and df[d].notna().any()]
    if present:
        print(df[present].describe().round(3).to_string())
    print(f"wrote {dest.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
