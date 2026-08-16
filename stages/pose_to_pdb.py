#!/usr/bin/env python
"""Convert one cofold output into the submission's PDB format, and prove it survived.

Mechanical format hygiene only -- there is **no selection judgement here**. Which
candidate to convert is decided by the `confidence-selection` skill; this file
just writes the one it was handed into the shape the grader accepts.

The conversion itself is three renames and a chain assignment. The reason this
file exists is the fourth step, which is the one that silently fails:

    the LIG residue's bond graph must match the target SMILES under RDKit
    AssignBondOrdersFromTemplate, *after* a PDB round trip

A PDB has no bond column. The grader extracts the LIG residue with MDAnalysis,
writes it to its own file, and reparses it with RDKit -- so connectivity survives
only through CONECT records. Without them RDKit re-perceives bonds by distance,
which is a coin toss on fused rings and on anything with an unusual geometry.
So we emit CONECT, and then re-read the file exactly the way the grader does and
check the template match before declaring success.

    .venv/bin/python stages/pose_to_pdb.py \\
        --cif runs/<run>/cofold/<model>/seed1/<id>/sample0.cif \\
        --smiles "<SMILES>" --out runs/<run>/selected/<id>.pdb
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

import gemmi
from rdkit import Chem, RDLogger
from rdkit.Chem import AllChem

ROOT = Path(__file__).resolve().parents[1]
LIG_RESNAME = "LIG"


def split_chains(st: gemmi.Structure) -> tuple[gemmi.Chain, gemmi.Chain]:
    """Return (protein chain, ligand chain) from a two-chain cofold model.

    Cofold models emit the ligand under their own residue name -- Boltz-2 resolves
    a CCD code, so chain B arrives as e.g. `MAJ`, not `LIG`. Identify by shape
    (the single-residue chain) rather than by name, which differs per model.
    """
    chains = list(st[0])
    if len(chains) != 2:
        raise ValueError(f"expected 2 chains, found {len(chains)}: {[c.name for c in chains]}")
    by_len = sorted(chains, key=lambda c: len(list(c)))
    ligand, protein = by_len[0], by_len[-1]
    if len(list(ligand)) != 1:
        raise ValueError(f"ligand chain {ligand.name!r} has {len(list(ligand))} residues, expected 1")
    return protein, ligand


def ligand_mol(st: gemmi.Structure, ligand: gemmi.Chain, smiles: str) -> Chem.Mol:
    """Build the ligand as an RDKit mol with correct bond orders.

    Bonds come from proximity perception on the raw coordinates, then are corrected
    against the target SMILES. If that template match fails here it will also fail
    in the grader, so failing now -- with the pose still on disk -- is the point.
    """
    sub = gemmi.Structure()
    sub.add_model(gemmi.Model("1"))
    ch = gemmi.Chain("B")
    ch.add_residue(ligand[0])
    sub[0].add_chain(ch)
    sub.setup_entities()

    raw = Chem.MolFromPDBBlock(sub.make_pdb_string(), removeHs=True, sanitize=False)
    if raw is None:
        raise ValueError("RDKit could not parse the ligand residue out of the model")

    ref = Chem.MolFromSmiles(smiles)
    if ref is None:
        raise ValueError(f"unparseable target SMILES: {smiles}")

    RDLogger.DisableLog("rdApp.*")
    try:
        return AllChem.AssignBondOrdersFromTemplate(ref, raw)
    except ValueError as e:
        raise ValueError(
            f"ligand connectivity does not match {smiles!r} ({e}). The model placed atoms "
            "the template cannot explain -- this pose cannot be submitted as-is."
        ) from e
    finally:
        RDLogger.EnableLog("rdApp.*")


def write_pdb(protein: gemmi.Chain, ligand: gemmi.Chain, mol: Chem.Mol, dest: Path) -> Path:
    """Write chain A protein + chain B LIG, with CONECT records for the ligand."""
    out = gemmi.Structure()
    out.add_model(gemmi.Model("1"))

    prot = gemmi.Chain("A")
    for res in protein:
        prot.add_residue(res)
    out[0].add_chain(prot)

    lig_res = gemmi.Residue()
    lig_res.name = LIG_RESNAME
    lig_res.seqid = gemmi.SeqId(1, " ")
    lig_res.het_flag = "H"
    for atom in ligand[0]:
        lig_res.add_atom(atom)
    lig_chain = gemmi.Chain("B")
    lig_chain.add_residue(lig_res)
    out[0].add_chain(lig_chain)

    out.setup_entities()
    lines = [ln for ln in out.make_pdb_string().splitlines() if not ln.startswith("END")]

    # CONECT is how connectivity survives the grader's extract-and-reparse. Serial
    # numbers are taken from the written file rather than assumed, because gemmi
    # renumbers on output.
    serials = [
        int(ln[6:11]) for ln in lines
        if ln.startswith("HETATM") and ln[17:20].strip() == LIG_RESNAME
    ]
    if len(serials) != mol.GetNumAtoms():
        raise ValueError(
            f"wrote {len(serials)} LIG atoms but the template mol has {mol.GetNumAtoms()}"
        )
    for bond in mol.GetBonds():
        a, b = serials[bond.GetBeginAtomIdx()], serials[bond.GetEndAtomIdx()]
        lines.append(f"CONECT{a:>5}{b:>5}")
    lines.append("END")

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("\n".join(lines) + "\n")
    return dest


def verify(pdb: Path, smiles: str) -> None:
    """Re-read the written file the way the grader does, and check the same things.

    Deliberately duplicates the grader's steps rather than trusting the objects we
    just held in memory: the whole failure mode is that the in-memory molecule is
    right and the file is not.
    """
    import MDAnalysis as mda

    u = mda.Universe(str(pdb))
    lig = u.select_atoms(f"resname {LIG_RESNAME}")
    if len(lig) == 0:
        raise ValueError("round trip lost the LIG residue")
    if len(lig.residues) != 1:
        raise ValueError(f"round trip produced {len(lig.residues)} LIG residues, expected 1")
    if len(u.segments) > 2:
        raise ValueError(f"round trip produced {len(u.segments)} chains, expected <= 2")

    with tempfile.TemporaryDirectory() as td:
        lig_path = Path(td) / "lig.pdb"
        lig.write(str(lig_path))
        reparsed = Chem.MolFromPDBFile(str(lig_path), removeHs=True, sanitize=False)
        if reparsed is None:
            raise ValueError("round trip produced a LIG residue RDKit cannot parse")
        ref = Chem.MolFromSmiles(smiles)
        RDLogger.DisableLog("rdApp.*")
        try:
            AllChem.AssignBondOrdersFromTemplate(ref, reparsed)
        except ValueError as e:
            raise ValueError(f"round trip broke ligand connectivity vs {smiles!r}: {e}") from e
        finally:
            RDLogger.EnableLog("rdApp.*")


def convert(cif: Path, smiles: str, dest: Path) -> Path:
    st = gemmi.read_structure(str(cif))
    st.setup_entities()
    protein, ligand = split_chains(st)
    mol = ligand_mol(st, ligand, smiles)
    out = write_pdb(protein, ligand, mol, dest)
    verify(out, smiles)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cif", required=True, type=Path)
    ap.add_argument("--smiles", required=True)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()

    try:
        out = convert(args.cif, args.smiles, args.out)
    except ValueError as e:
        print(f"FAILED: {e}")
        return 1
    print(f"wrote {out} — LIG intact, connectivity matches SMILES after round trip")
    return 0


if __name__ == "__main__":
    sys.exit(main())
