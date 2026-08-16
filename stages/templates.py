#!/usr/bin/env python
"""Select a template set spanning the receptor's conformational range.

### The injection path is blocked, and that is the headline

All five deployed cofolders take exactly two inputs -- `complexes` and `msas`.
None exposes a `templates` field, and their schemas are `additionalProperties:
false`, so an extra key is rejected rather than ignored. **Structural templating
cannot currently be applied through the proto-tools path.** Adding it means
either patching installed input models (clobbered on upgrade, and still rejected
by the schema) or extending `modal/alphafold3_service.py`, which is our file and
where AF3's native template support would be reachable.

So this file does the half that is reachable and useful regardless: choosing
*which* structures a template set should contain. That is a real declared output
(`stage3.template_set`), it is what a fine-tune corpus is built from, and it is
the input to the injection work whenever the path opens.

### Why cluster on pocket geometry rather than sequence

The receptors are near-identical in sequence and differ in the thing that
matters: pocket shape. Clustering on sequence returns one cluster and tells you
nothing. Clustering on pocket-lining atom positions separates the conformations a
template set exists to span.

A single template pulls every sample toward one conformation, which is the
opposite of what a pool needs -- so the objective here is *coverage of the range*,
not proximity to any one structure.

    .venv/bin/python stages/templates.py --k 6
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "manifest"

POCKET_RADIUS = 8.0   # A around the bound ligand that counts as pocket lining
MIN_POCKET_ATOMS = 20


def pocket_fingerprint(pdb: Path, radius: float = POCKET_RADIUS) -> np.ndarray | None:
    """Describe a receptor's pocket by the shape of its lining, not its sequence.

    Uses the bound ligand to locate the pocket, then summarises the lining atoms
    with rotation-invariant descriptors -- pairwise-distance quantiles and
    inertia-tensor eigenvalues -- so two structures can be compared without
    superposing them, which would otherwise require a reference frame that does
    not exist across different depositions.
    """
    import gemmi

    st = gemmi.read_structure(str(pdb))
    st.remove_hydrogens()
    st.remove_waters()

    lig, prot = [], []
    for ch in st[0]:
        for res in ch:
            if res.het_flag == "H" and res.name not in ("HOH", "SO4", "GOL", "EDO", "PO4", "CL", "NA"):
                lig += [(a.pos.x, a.pos.y, a.pos.z) for a in res]
            elif res.het_flag != "H":
                prot += [(a.pos.x, a.pos.y, a.pos.z) for a in res if a.name in ("CA", "CB")]
    if not lig or not prot:
        return None

    L, P = np.array(lig), np.array(prot)
    d = np.linalg.norm(P[:, None, :] - L[None, :, :], axis=-1).min(axis=1)
    lining = P[d < radius]
    if len(lining) < MIN_POCKET_ATOMS:
        return None

    c = lining - lining.mean(0)
    pair = np.linalg.norm(c[:, None, :] - c[None, :, :], axis=-1)
    iu = np.triu_indices(len(c), k=1)
    eig = np.linalg.eigvalsh(np.cov(c.T))
    return np.concatenate([
        np.percentile(pair[iu], [10, 25, 50, 75, 90]),
        np.sort(eig)[::-1],
        [len(lining), float(np.linalg.norm(c, axis=1).mean())],
    ])


def kmeans(X: np.ndarray, k: int, seed: int = 0, iters: int = 100) -> np.ndarray:
    """Lloyd's algorithm with k-means++ seeding. Stdlib-adjacent; no sklearn."""
    rng = np.random.default_rng(seed)
    centres = [X[rng.integers(len(X))]]
    for _ in range(k - 1):
        d2 = np.min(((X[:, None, :] - np.array(centres)[None, :, :]) ** 2).sum(-1), axis=1)
        centres.append(X[rng.choice(len(X), p=d2 / d2.sum())] if d2.sum() > 0 else X[rng.integers(len(X))])
    C = np.array(centres)
    labels = np.zeros(len(X), int)
    for _ in range(iters):
        new = np.argmin(((X[:, None, :] - C[None, :, :]) ** 2).sum(-1), axis=1)
        if (new == labels).all():
            break
        labels = new
        for j in range(k):
            if (labels == j).any():
                C[j] = X[labels == j].mean(0)
    return labels


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--k", type=int, default=6, help="conformational clusters to span")
    ap.add_argument("--out", type=Path, default=MANIFEST / "template_set.csv")
    args = ap.parse_args()

    rec = pd.read_csv(MANIFEST / "receptors.csv")
    print(f"{len(rec)} receptors; {int((~rec.has_pdb).sum())} are mmCIF-only")

    def _path(*candidates: object) -> str | None:
        # An absent path arrives from pandas as NaN, which is a float and is
        # *truthy* -- so `a or b` silently selects the missing one. The two
        # mmCIF-only receptors are exactly the rows this hits, and gemmi reads
        # CIF perfectly well, so getting this wrong narrows the template set for
        # no reason at all.
        for c in candidates:
            if isinstance(c, str) and c.strip():
                return c
        return None

    fps, kept, skipped = [], [], []
    for r in rec.itertuples(index=False):
        path = _path(r.pdb_path, r.cif_path)
        if not path:
            skipped.append((r.pdb_id, "no coordinate file"))
            continue
        try:
            fp = pocket_fingerprint(ROOT / path)
        except Exception as e:
            skipped.append((r.pdb_id, f"{type(e).__name__}: {e}"))
            continue
        if fp is None:
            skipped.append((r.pdb_id, "no ligand-defined pocket"))
            continue
        fps.append(fp)
        kept.append(r)

    if not fps:
        print("no receptor yielded a pocket fingerprint")
        return 1

    X = np.array(fps)
    X = (X - X.mean(0)) / np.where(X.std(0) < 1e-12, 1.0, X.std(0))
    k = min(args.k, len(X))
    labels = kmeans(X, k)

    # One representative per cluster: the member closest to its centroid, which is
    # the most typical conformation of that cluster rather than the most extreme.
    df = pd.DataFrame({
        "pdb_id": [r.pdb_id for r in kept],
        "cluster": labels,
        "n_ligands": [r.n_ligands for r in kept],
        "best_refinement": [r.best_refinement for r in kept],
        "path": [_path(r.pdb_path, r.cif_path) for r in kept],
    })
    chosen = []
    for j in range(k):
        m = labels == j
        if not m.any():
            continue
        sub = X[m]
        idx = np.argmin(((sub - sub.mean(0)) ** 2).sum(1))
        chosen.append(df[m].iloc[idx].pdb_id)
    df["representative"] = df.pdb_id.isin(chosen)

    df.to_csv(args.out, index=False)
    print(f"\nfingerprinted {len(df)}, skipped {len(skipped)}")
    for pid, why in skipped[:8]:
        print(f"  skipped {pid}: {why}")
    print(f"\ncluster sizes: {df.cluster.value_counts().sort_index().to_dict()}")
    print(f"representatives ({len(chosen)}): {sorted(chosen)}")
    print(f"multi-ligand structures carried: {int((df.n_ligands > 1).sum())}")
    print(f"\nwrote {args.out.relative_to(ROOT)}")

    (MANIFEST / "template_set.json").write_text(json.dumps({
        "k": k, "representatives": sorted(chosen),
        "n_fingerprinted": len(df), "n_skipped": len(skipped),
        "skipped": [{"pdb_id": p, "reason": w} for p, w in skipped],
        "injection_blocked": (
            "No deployed cofolder exposes a `templates` input; all five accept only "
            "`complexes` and `msas` under additionalProperties:false. This set is "
            "selected but cannot currently be injected via proto-tools."
        ),
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
