"""Read a cofold run into a candidate table. No ground truth, ever.

This lives in `stages/` rather than `eval/` on purpose. `eval/` is the only place
allowed to open ground truth, and selection runs in `stages/` -- so the shared
loader belongs on the side of the boundary that has no such access. If this file
ever imports from `eval/`, the boundary has been inverted; see the
`leak-containment` skill for why that failure is invisible in the final score.

Every native signal is carried through **unnormalised**. Cross-model comparison
needs the raw per-model scale, and normalising here would destroy it.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

# Signals a cofolder emits that are worth ranking on, or worth carrying as a
# control. Not every model emits every field; missing ones stay NaN rather than
# being filled, so a model is never credited with a signal it did not produce.
SIGNAL_FIELDS = [
    "confidence_score", "ptm", "iptm", "ligand_iptm", "protein_iptm",
    "complex_plddt", "complex_iplddt", "complex_pde", "complex_ipde", "avg_pae",
]

# The negative control must be emitted for EVERY candidate, or it validates one
# generator's slice rather than the pool. `complex_plddt` is boltz2-only here, so
# a seeded random value is used instead: it is guaranteed to carry no information,
# it exists for every row, and it must land near 0.5 AUC. If it does not, the
# harness is leaking and nothing downstream can be believed.
NEGATIVE_CONTROL = "random_control"

# A global score, kept as a *secondary* control where the model emits it. Not the
# primary one, precisely because its coverage is uneven.
PARTIAL_CONTROL = "complex_plddt"

# Signals where a *lower* value is better, so ranking flips.
LOWER_IS_BETTER = {
    "avg_pae", "min_interface_pae", "complex_pde", "complex_ipde",
    "mmff_strain", "clashes",
}


def random_control(structure_id: str, model: str, seed: int, sample: int) -> float:
    """A signal that cannot possibly predict anything, derived deterministically.

    Seeded on the candidate's identity so it is stable across reruns -- a control
    that changes between runs cannot distinguish "the harness is fine" from "the
    control moved".
    """
    key = f"{structure_id}|{model}|{seed}|{sample}"
    return float(np.random.default_rng(abs(hash(key)) % (2**32)).random())


def min_interface_pae(metrics: dict, n_ligand_tokens: int | None = None) -> float | None:
    """Minimum PAE over protein-ligand token pairs.

    These models tokenise a ligand **per heavy atom**, so a 293-residue receptor
    with a 9-atom ligand yields a 302x302 matrix. The interface is the whole
    off-diagonal block `pae[:n_prot, n_prot:]`, not the last row and column --
    taking only the last index scores one ligand atom against the protein and
    discards the rest, which reads as noise rather than as a bug.

    `n_ligand_tokens` comes from the ligand's heavy-atom count. Without it the
    block boundary is unknown and the honest answer is None, not a guess.
    """
    pae = metrics.get("pae")
    if not pae or not n_ligand_tokens:
        return None
    a = np.asarray(pae, dtype=float)
    if a.ndim != 2 or a.shape[0] != a.shape[1]:
        return None
    n_prot = a.shape[0] - n_ligand_tokens
    if n_prot < 1 or n_ligand_tokens < 1:
        return None
    return float(min(a[:n_prot, n_prot:].min(), a[n_prot:, :n_prot].min()))


def load_candidates(run_dir: Path) -> pd.DataFrame:
    """One row per candidate produced by a run, including the ones that failed."""
    jobs = json.loads((run_dir / "jobs.json").read_text())
    rows = []
    for job in jobs:
        base = {
            "structure_id": job["structure_id"],
            "model": job["model"],
            "seed": job["seed"],
            "smiles": job["smiles"],
        }
        if job.get("status") != "done":
            rows.append({**base, "sample": 0, "status": job.get("status", "pending"),
                         "error": job.get("error")})
            continue
        # Ligand token count == heavy atoms, which locates the interface block in
        # the PAE matrix. Derived from the SMILES rather than assumed.
        n_lig = _heavy_atoms(job["smiles"])
        metrics = json.loads((ROOT / job["metrics_json"]).read_text())
        for i, (path, m) in enumerate(zip(job["structures"], metrics)):
            row = {**base, "sample": i, "status": "done", "cif": path}
            for f in SIGNAL_FIELDS:
                row[f] = m.get(f)
            row["min_interface_pae"] = min_interface_pae(m, n_lig)
            row["random_control"] = random_control(
                job["structure_id"], job["model"], job["seed"], i
            )
            rows.append(row)
    return pd.DataFrame(rows)


def _heavy_atoms(smiles: str) -> int | None:
    from rdkit import Chem, RDLogger

    RDLogger.DisableLog("rdApp.*")
    try:
        mol = Chem.MolFromSmiles(smiles)
        return mol.GetNumHeavyAtoms() if mol else None
    finally:
        RDLogger.EnableLog("rdApp.*")


def orient(series: pd.Series, signal: str) -> pd.Series:
    """Flip a lower-is-better signal so argmax is always the right operation."""
    return -series if signal in LOWER_IS_BETTER else series
