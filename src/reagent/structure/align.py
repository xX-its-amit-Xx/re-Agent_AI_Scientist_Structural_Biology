"""Sequence alignment, superposition, and a structural-similarity estimate.

What this is, stated plainly, because the numbers it returns look like TM-align's
and are not: a **sequence-guided superposition**. It aligns the two sequences with
Needleman-Wunsch, superposes the matched C-alpha pairs with Kabsch, iteratively
discards the worst-fitting pairs, and reports RMSD plus a TM-score computed over the
surviving correspondence.

That is a good estimate for proteins related by homology — the case a receptor-family
comparison is almost always in — and a **poor** one for structurally similar proteins
with unrelated sequences, because a sequence alignment cannot find that
correspondence at all. Real structural aligners (TM-align, Foldseek, US-align)
search over correspondences rather than inheriting one from the sequence.

So every result carries ``method`` and ``is_estimate``, and the MCP surfaces both.
When Foldseek or TM-align is available, prefer it and record which ran; the point of
this module is that a comparison is always *possible*, not that it is authoritative.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .model import Residue, Structure

# BLOSUM62-ish: a flat substitution scheme is enough for closely related sequences
# and avoids shipping a matrix. Identity dominates the alignment either way.
MATCH, MISMATCH, GAP_OPEN, GAP_EXTEND = 2.0, -1.0, -10.0, -0.5

#: The conventional "structurally equivalent" cutoff for a superposed C-alpha pair.
CLOSE_ANGSTROM = 5.0

#: How close in TM-score two chain pairs must be before other considerations (namely,
#: whether both chains actually hold a ligand) are allowed to decide between them.
#: Identical copies in one crystal typically differ by well under this.
TM_TIE_MARGIN = 0.05


@dataclass
class ResiduePair:
    a: Residue
    b: Residue
    distance: float

    @property
    def is_close(self) -> bool:
        return self.distance <= CLOSE_ANGSTROM

    @property
    def identical(self) -> bool:
        return self.a.one == self.b.one and self.a.one != "X"


@dataclass
class Alignment:
    """The result of comparing two structures."""

    id_a: str
    id_b: str
    chain_a: str
    chain_b: str
    method: str
    is_estimate: bool

    n_aligned: int
    n_close: int
    rmsd: float
    tm_score: float
    seq_identity: float
    len_a: int
    len_b: int
    rotation: np.ndarray = field(default_factory=lambda: np.eye(3))
    translation: np.ndarray = field(default_factory=lambda: np.zeros(3))
    pairs: list[ResiduePair] = field(default_factory=list)
    caveats: list[str] = field(default_factory=list)

    @property
    def coverage(self) -> float:
        """Fraction of the shorter chain that ended up structurally equivalent."""
        return self.n_close / max(1, min(self.len_a, self.len_b))

    def conserved_pairs(self) -> list[ResiduePair]:
        """Close in space *and* the same amino acid — the strongest correspondence."""
        return [p for p in self.pairs if p.is_close and p.identical]

    def divergent_pairs(self, threshold: float = 4.0) -> list[ResiduePair]:
        """Aligned in sequence but far apart after superposition: where the folds differ."""
        return sorted(
            (p for p in self.pairs if p.distance > threshold),
            key=lambda p: -p.distance,
        )

    def apply_to(self, coords: np.ndarray) -> np.ndarray:
        """Move coordinates of B into A's frame."""
        return coords @ self.rotation.T + self.translation

    def summary(self) -> str:
        lines = [
            f"{self.id_a} chain {self.chain_a} ({self.len_a} residues) vs "
            f"{self.id_b} chain {self.chain_b} ({self.len_b} residues)",
            f"  method            {self.method}"
            + ("  [ESTIMATE — see caveats]" if self.is_estimate else ""),
            f"  aligned pairs     {self.n_aligned}",
            f"  within {CLOSE_ANGSTROM:g} A       {self.n_close} "
            f"({self.coverage:.0%} of the shorter chain)",
            f"  C-alpha RMSD      {self.rmsd:.2f} A (over the {self.n_close} close pairs)",
            f"  TM-score          {self.tm_score:.3f}",
            f"  sequence identity {self.seq_identity:.1%}",
        ]
        if self.caveats:
            lines.append("  caveats:")
            lines += [f"    - {c}" for c in self.caveats]
        return "\n".join(lines)


def needleman_wunsch(a: str, b: str) -> list[tuple[int | None, int | None]]:
    """Global alignment with affine gaps. Returns index pairs; None marks a gap.

    Written out rather than pulled from a library because it is thirty lines and the
    alternative is a Biopython dependency on the MCP's hot path.
    """
    n, m = len(a), len(b)
    if n == 0 or m == 0:
        return []

    neg = -1e18
    # M: match state, X: gap in b, Y: gap in a.
    M = np.full((n + 1, m + 1), neg)
    X = np.full((n + 1, m + 1), neg)
    Y = np.full((n + 1, m + 1), neg)
    ptr_M = np.zeros((n + 1, m + 1), dtype=np.int8)
    ptr_X = np.zeros((n + 1, m + 1), dtype=np.int8)
    ptr_Y = np.zeros((n + 1, m + 1), dtype=np.int8)

    M[0, 0] = 0.0
    for i in range(1, n + 1):
        X[i, 0] = GAP_OPEN + GAP_EXTEND * (i - 1)
        ptr_X[i, 0] = 1
    for j in range(1, m + 1):
        Y[0, j] = GAP_OPEN + GAP_EXTEND * (j - 1)
        ptr_Y[0, j] = 2

    for i in range(1, n + 1):
        ai = a[i - 1]
        for j in range(1, m + 1):
            s = MATCH if ai == b[j - 1] and ai != "X" else MISMATCH
            best = max(M[i - 1, j - 1], X[i - 1, j - 1], Y[i - 1, j - 1])
            M[i, j] = best + s
            ptr_M[i, j] = int(np.argmax([M[i - 1, j - 1], X[i - 1, j - 1], Y[i - 1, j - 1]]))

            open_x, ext_x = M[i - 1, j] + GAP_OPEN, X[i - 1, j] + GAP_EXTEND
            X[i, j] = max(open_x, ext_x)
            ptr_X[i, j] = 0 if open_x >= ext_x else 1

            open_y, ext_y = M[i, j - 1] + GAP_OPEN, Y[i, j - 1] + GAP_EXTEND
            Y[i, j] = max(open_y, ext_y)
            ptr_Y[i, j] = 0 if open_y >= ext_y else 2

    i, j = n, m
    state = int(np.argmax([M[n, m], X[n, m], Y[n, m]]))
    out: list[tuple[int | None, int | None]] = []
    while i > 0 or j > 0:
        if state == 0 and i > 0 and j > 0:
            out.append((i - 1, j - 1))
            state = int(ptr_M[i, j])
            i, j = i - 1, j - 1
        elif state == 1 and i > 0:
            out.append((i - 1, None))
            state = int(ptr_X[i, j])
            i -= 1
        elif state == 2 and j > 0:
            out.append((None, j - 1))
            state = int(ptr_Y[i, j])
            j -= 1
        elif i > 0:
            out.append((i - 1, None))
            i -= 1
        else:
            out.append((None, j - 1))
            j -= 1
    out.reverse()
    return out


def kabsch(P: np.ndarray, Q: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
    """Optimal rigid transform mapping Q onto P. Returns (rotation, translation, rmsd)."""
    if len(P) < 3:
        return np.eye(3), np.zeros(3), float("nan")
    Pc, Qc = P.mean(axis=0), Q.mean(axis=0)
    H = (Q - Qc).T @ (P - Pc)
    U, _, Vt = np.linalg.svd(H)
    d = np.sign(np.linalg.det(Vt.T @ U.T))
    R = Vt.T @ np.diag([1.0, 1.0, d]) @ U.T
    t = Pc - Qc @ R.T
    diff = P - (Q @ R.T + t)
    rmsd = float(np.sqrt((diff ** 2).sum() / len(P)))
    return R, t, rmsd


def tm_score(distances: np.ndarray, length_norm: int) -> float:
    """TM-score over an existing correspondence.

    Note this does *not* optimise the superposition to maximise TM-score the way
    TM-align does, so it is a lower bound on what a real structural aligner would
    report. ``length_norm`` should be the reference chain's length.
    """
    if length_norm <= 15:
        return 0.0
    d0 = 1.24 * (length_norm - 15) ** (1.0 / 3.0) - 1.8
    d0 = max(d0, 0.5)
    return float((1.0 / (1.0 + (distances / d0) ** 2)).sum() / length_norm)


def _candidate_chains(st: Structure, min_len: int = 30, cap: int = 6) -> list[str]:
    """Distinct chains worth trying, deduplicated by sequence.

    A crystal often holds several identical copies and aligning against each is wasted
    work, so one representative per distinct *sequence* is enough — and in a
    heterodimer the distinct sequences are different proteins, only one of which is
    the homolog you meant.

    The representative is the copy that **holds a ligand**, preferring length only as
    a tiebreak. Choosing by length alone will happily keep an apo copy and discard the
    holo one, which then makes a pocket comparison impossible for no reason.
    """
    # The length floor skips crystallographic peptides and tags that would waste an
    # alignment. But short chains are sometimes the whole point — a coactivator
    # peptide, a designed miniprotein — so if the floor would leave nothing, drop it
    # to the Kabsch minimum rather than refusing to compare anything.
    floor = min_len
    if not any(len(res) >= floor for res in st.chains.values()):
        floor = 3

    by_seq: dict[str, list[str]] = {}
    for chain in st.chains:
        if len(st.chains[chain]) < floor:
            continue
        by_seq.setdefault(st.sequence(chain), []).append(chain)

    reps: list[tuple[int, str]] = []
    for chains in by_seq.values():
        holo = [c for c in chains if st.primary_ligand(c) is not None]
        pool = holo or chains
        rep = max(pool, key=lambda c: len(st.chains[c]))
        reps.append((len(st.chains[rep]), rep))
    reps.sort(key=lambda x: -x[0])
    return [c for _n, c in reps[:cap]]


def superpose(
    a: Structure,
    b: Structure,
    *,
    chain_a: str | None = None,
    chain_b: str | None = None,
    trim_rounds: int = 5,
    trim_cutoff: float = 5.0,
) -> Alignment:
    """Sequence-guided superposition of two structures.

    When a chain is not specified, every distinct chain pair is tried and the one
    with the best TM-score wins. That matters more than it sounds: a heterodimer
    contains two *different* proteins, and choosing a chain by length or by which
    one holds the biggest ligand can select the partner rather than the homolog —
    silently turning a 44 %-identity comparison into a 26 % one.

    Iteratively refines each fit: superpose on all aligned pairs, drop pairs further
    apart than ``trim_cutoff``, superpose again. Without the trimming a single
    divergent loop drags the whole superposition and both the RMSD and the visual
    overlay mislead.
    """
    if chain_a is None or chain_b is None:
        cands_a = [chain_a] if chain_a else _candidate_chains(a)
        cands_b = [chain_b] if chain_b else _candidate_chains(b)
        if not cands_a or not cands_b:
            raise ValueError(
                f"no chain of at least 30 residues in "
                f"{a.id if not cands_a else b.id} to align"
            )
        scored: list[Alignment] = []
        for ca in cands_a:
            for cb in cands_b:
                try:
                    scored.append(_superpose_pair(a, b, ca, cb, trim_rounds, trim_cutoff))
                except ValueError:
                    continue
        if not scored:
            raise ValueError(
                f"no chain pair between {a.id} and {b.id} could be aligned — their "
                "sequences are too dissimilar for a sequence-guided superposition. "
                "Use a structural aligner (Foldseek, TM-align) instead."
            )
        scored.sort(key=lambda x: -x.tm_score)
        best = scored[0]

        # Among pairs that fit essentially as well, prefer one where BOTH chains hold
        # a ligand. In a crystal with several copies the apo and holo copies align
        # equally well, and picking the apo one produces a correct fold comparison
        # with an empty pocket — technically true, practically useless.
        holo_note = ""
        near = [x for x in scored if best.tm_score - x.tm_score <= TM_TIE_MARGIN]
        for cand in near:
            if (a.primary_ligand(cand.chain_a) is not None
                    and b.primary_ligand(cand.chain_b) is not None):
                if cand is not best:
                    holo_note = (
                        f" {cand.chain_a}/{cand.chain_b} was preferred over the "
                        f"top-scoring {best.chain_a}/{best.chain_b} (TM "
                        f"{best.tm_score:.3f}) because both of its chains hold a ligand, "
                        f"which makes a pocket comparison possible."
                    )
                best = cand
                break

        if len(scored) > 1:
            best.caveats.insert(0, (
                f"chains were chosen automatically: {len(scored)} distinct chain pairs "
                f"were tried and {best.chain_a}/{best.chain_b} was selected "
                f"(TM {best.tm_score:.3f}).{holo_note} Pass chain_a/chain_b to override."
            ))
        return best
    return _superpose_pair(a, b, chain_a, chain_b, trim_rounds, trim_cutoff)


def _superpose_pair(
    a: Structure,
    b: Structure,
    ca_chain: str,
    cb_chain: str,
    trim_rounds: int = 5,
    trim_cutoff: float = 5.0,
) -> Alignment:
    """Superpose one specific chain pair."""

    coords_a, res_a = a.ca_coords(ca_chain)
    coords_b, res_b = b.ca_coords(cb_chain)
    seq_a = "".join(r.one for r in res_a)
    seq_b = "".join(r.one for r in res_b)

    caveats: list[str] = []
    if not res_a or not res_b:
        raise ValueError(
            f"no C-alpha atoms found for {a.id} chain {ca_chain} or {b.id} chain {cb_chain}"
        )

    pairs_idx = [(i, j) for i, j in needleman_wunsch(seq_a, seq_b)
                 if i is not None and j is not None]
    if len(pairs_idx) < 3:
        raise ValueError(
            f"only {len(pairs_idx)} aligned residue pairs between {a.id} and {b.id} — "
            "these sequences are too dissimilar for a sequence-guided superposition. "
            "Use a structural aligner (Foldseek, TM-align) instead."
        )

    n_ident = sum(1 for i, j in pairs_idx if seq_a[i] == seq_b[j] and seq_a[i] != "X")
    seq_identity = n_ident / max(1, len(pairs_idx))
    if seq_identity < 0.20:
        caveats.append(
            f"sequence identity is only {seq_identity:.0%}. A sequence-guided "
            "superposition is unreliable below roughly 20-25%; the residue "
            "correspondence itself may be wrong, not merely the fit."
        )

    keep = list(range(len(pairs_idx)))
    # Seeded with identity so a graph with fewer than three pairs still returns a
    # usable transform. The reported RMSD comes from the close-pair set below, not
    # from these rounds, so the per-round value is deliberately discarded.
    R, t = np.eye(3), np.zeros(3)
    for _ in range(max(1, trim_rounds)):
        P = np.vstack([coords_a[pairs_idx[k][0]] for k in keep])
        Q = np.vstack([coords_b[pairs_idx[k][1]] for k in keep])
        R, t, _round_rmsd = kabsch(P, Q)
        moved = Q @ R.T + t
        d = np.linalg.norm(P - moved, axis=1)
        surviving = [k for k, dist in zip(keep, d, strict=True) if dist <= trim_cutoff]
        if len(surviving) < 3 or len(surviving) == len(keep):
            break
        keep = surviving

    # Final distances over the FULL aligned set, using the refined transform, so the
    # reported pairs include the divergent ones rather than only the ones that fit.
    all_P = np.vstack([coords_a[i] for i, _ in pairs_idx])
    all_Q = np.vstack([coords_b[j] for _, j in pairs_idx])
    all_moved = all_Q @ R.T + t
    all_d = np.linalg.norm(all_P - all_moved, axis=1)

    pairs = [
        ResiduePair(a=res_a[i], b=res_b[j], distance=float(dist))
        for (i, j), dist in zip(pairs_idx, all_d, strict=True)
    ]
    close = [p for p in pairs if p.is_close]
    close_d = np.array([p.distance for p in close]) if close else np.zeros(0)
    core_rmsd = float(np.sqrt((close_d ** 2).mean())) if len(close_d) else float("nan")

    if a.source.endswith("(predicted)") or b.source.endswith("(predicted)"):
        caveats.append(
            "at least one structure is a predicted model, so its coordinate error is "
            "folded into every number here — check per-residue confidence before "
            "treating a local deviation as real."
        )
    if len(close) < 0.5 * min(len(res_a), len(res_b)):
        caveats.append(
            f"only {len(close)} of {min(len(res_a), len(res_b))} residues in the shorter "
            "chain superpose within 5 A, so these folds agree over a minority of their "
            "length; treat the global RMSD as uninformative and read the per-region "
            "breakdown instead."
        )

    return Alignment(
        id_a=a.id, id_b=b.id, chain_a=ca_chain, chain_b=cb_chain,
        method="Needleman-Wunsch sequence alignment + iterative Kabsch superposition",
        is_estimate=True,
        n_aligned=len(pairs), n_close=len(close),
        rmsd=core_rmsd,
        tm_score=tm_score(all_d, min(len(res_a), len(res_b))),
        seq_identity=seq_identity,
        len_a=len(res_a), len_b=len(res_b),
        rotation=R, translation=t, pairs=pairs,
        caveats=[
            *caveats,
            "This is a sequence-guided superposition, not a structural alignment. It "
            "assumes the sequence alignment found the right correspondence, which is "
            "safe for homologs and wrong for structurally similar proteins with "
            "unrelated sequences. TM-score is a lower bound on what TM-align would give."
        ],
    )


def pocket_comparison(
    a: Structure,
    b: Structure,
    aln: Alignment,
    *,
    radius: float = 6.0,
) -> dict:
    """Compare the two structures' ligand-binding pockets, if both have a ligand.

    This is the part a biochemist actually wants from a side-by-side: not the global
    fold number, but whether the *pocket* is built from the same residues.
    """
    lig_a = a.primary_ligand(aln.chain_a)
    lig_b = b.primary_ligand(aln.chain_b)
    out: dict = {
        "ligand_a": lig_a.name3 if lig_a else None,
        "ligand_b": lig_b.name3 if lig_b else None,
    }
    if lig_a is None or lig_b is None:
        # Say *which* side is apo and where a ligand does sit, so the caller can
        # re-run against the right chain instead of concluding the pockets differ.
        parts = []
        for st, chain, lig, side in (
            (a, aln.chain_a, lig_a, a.id), (b, aln.chain_b, lig_b, b.id)
        ):
            if lig is None:
                elsewhere = st.chains_with_ligands()
                where = (
                    "; a ligand is bound in chain(s) "
                    + ", ".join(f"{c} ({'/'.join(n)})" for c, n in elsewhere.items())
                    + " — re-run with that chain to compare pockets"
                    if elsewhere else
                    "; no chain in this structure has a bound ligand"
                )
                parts.append(f"{side} chain {chain} is apo{where}")
        out["note"] = (
            "No pocket pair to compare: " + "; and ".join(parts)
            + ". The fold comparison above still stands."
        )
        return out

    # Measure from every ligand atom, not the centroid — see Structure.residues_near.
    near_a = {r.key: r for r in a.residues_near(lig_a.coords, radius, aln.chain_a)}
    near_b = {r.key: r for r in b.residues_near(lig_b.coords, radius, aln.chain_b)}

    # Map B's pocket residues into A's numbering through the alignment.
    b_to_a = {p.b.key: p for p in aln.pairs}
    shared, only_a, only_b = [], [], []
    matched_b_keys = set()
    for key_b in near_b:
        pair = b_to_a.get(key_b)
        if pair and pair.a.key in near_a:
            shared.append({
                "a": pair.a.label, "b": pair.b.label,
                "identical": pair.identical,
                "ca_distance": round(pair.distance, 2),
            })
            matched_b_keys.add(key_b)
    shared_a_keys = {b_to_a[k].a.key for k in matched_b_keys if k in b_to_a}
    only_a = [near_a[k].label for k in near_a if k not in shared_a_keys]
    only_b = [near_b[k].label for k in near_b if k not in matched_b_keys]

    n_shared = len(shared)
    n_union = n_shared + len(only_a) + len(only_b)
    out.update({
        "radius_angstrom": radius,
        "n_pocket_residues_a": len(near_a),
        "n_pocket_residues_b": len(near_b),
        "shared": sorted(shared, key=lambda d: d["ca_distance"]),
        "conserved_identity": sum(1 for s in shared if s["identical"]),
        "only_in_a": sorted(only_a),
        "only_in_b": sorted(only_b),
        "jaccard": round(n_shared / n_union, 3) if n_union else 0.0,
        "ligand_size_a": lig_a.n_atoms,
        "ligand_size_b": lig_b.n_atoms,
    })
    return out
