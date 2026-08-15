"""Minimal PDB/mmCIF parsing and structure fetching.

A focused parser rather than Biopython, because the MCP needs to work in a plain
`pip install -e .` environment and the subset we need — backbone atoms, residue
identity, HETATM ligands — is small and stable. Anything beyond that (altlocs,
symmetry, anisotropic B-factors) is out of scope; if a stage needs it, use
Biopython from the ``struct`` extra.

Structures are fetched into ``data/cache/structures/`` and reused. That cache is
gitignored and disposable, and every fetch records where it came from, matching the
lazy-materialisation contract in ``reagent.contracts.data``.
"""

from __future__ import annotations

import contextlib
import gzip
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

RCSB_PDB = "https://files.rcsb.org/download/{pdb_id}.pdb"
RCSB_CIF = "https://files.rcsb.org/download/{pdb_id}.cif"
AF_DB = "https://alphafold.ebi.ac.uk/files/AF-{acc}-F1-model_v4.pdb"

CACHE = Path("data/cache/structures")

#: Three-letter to one-letter. Non-standard residues fall through to 'X' rather
#: than being dropped, so residue numbering stays aligned with the file.
AA3TO1 = {
    "ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C", "GLN": "Q",
    "GLU": "E", "GLY": "G", "HIS": "H", "ILE": "I", "LEU": "L", "LYS": "K",
    "MET": "M", "PHE": "F", "PRO": "P", "SER": "S", "THR": "T", "TRP": "W",
    "TYR": "Y", "VAL": "V",
    # Common modified residues, mapped to their parent so alignment still works.
    "MSE": "M", "SEC": "U", "PYL": "O", "HYP": "P", "PCA": "E", "CSO": "C",
    "SEP": "S", "TPO": "T", "PTR": "Y", "MLY": "K", "KCX": "K", "CME": "C",
}

#: Solvent, ions, buffers, and cryoprotectants that are not real ligands. Same
#: problem the structured-corpus harvest solves; kept short here because we only
#: need it to pick a *representative* ligand for display.
NOT_A_LIGAND = {
    "HOH", "DOD", "WAT", "NA", "CL", "K", "MG", "CA", "ZN", "MN", "FE", "FE2",
    "CU", "NI", "CO", "CD", "HG", "SO4", "PO4", "NO3", "ACT", "GOL", "EDO",
    "PEG", "PGE", "PG4", "1PE", "2PE", "P6G", "TRS", "MES", "EPE", "MPD",
    "DMS", "DTT", "BME", "IMD", "FMT", "ACY", "IPA", "MOH", "ETX", "BU3",
    "TLA", "CIT", "MLI", "OXL", "AZI", "BR", "IOD", "F", "UNX", "UNL",
}


@dataclass
class Residue:
    chain: str
    seq_num: int
    insertion: str
    name3: str
    ca: np.ndarray | None = None          # C-alpha coordinate
    atoms: dict[str, np.ndarray] = field(default_factory=dict)
    bfactor: float = 0.0

    @property
    def one(self) -> str:
        return AA3TO1.get(self.name3, "X")

    @property
    def label(self) -> str:
        """e.g. 'Ser247' — matches how residues are named in the graph."""
        return f"{self.name3.capitalize()}{self.seq_num}{self.insertion.strip()}"

    @property
    def key(self) -> str:
        return f"{self.chain}:{self.seq_num}{self.insertion.strip()}"


@dataclass
class Ligand:
    name3: str
    chain: str
    seq_num: int
    coords: np.ndarray            # (n_atoms, 3)
    element: list[str] = field(default_factory=list)

    @property
    def n_atoms(self) -> int:
        return len(self.coords)

    @property
    def centroid(self) -> np.ndarray:
        return self.coords.mean(axis=0)


@dataclass
class Structure:
    """Parsed coordinates plus enough provenance to cite the thing."""

    id: str
    source: str                                  # where it came from
    chains: dict[str, list[Residue]] = field(default_factory=dict)
    ligands: list[Ligand] = field(default_factory=list)
    title: str = ""
    local_path: str | None = None
    raw_text: str = ""                           # kept for the 3D viewer

    def sequence(self, chain: str) -> str:
        return "".join(r.one for r in self.chains.get(chain, []))

    def longest_chain(self) -> str:
        if not self.chains:
            raise ValueError(f"{self.id} has no protein chains")
        return max(self.chains, key=lambda c: len(self.chains[c]))

    def best_chain(self, *, contact_radius: float = 5.0) -> str:
        """The chain most worth comparing: the longest one that actually holds a ligand.

        Crystals routinely contain several copies of the same protein, and the ligand
        may be modelled in only one of them. Picking purely by length then selects an
        apo copy and every pocket comparison silently returns nothing — which reads as
        "these pockets share no residues" rather than "you looked at the wrong chain".
        Falls back to the longest chain when no chain contacts a ligand.
        """
        if not self.chains:
            raise ValueError(f"{self.id} has no protein chains")
        candidates = [
            lg for lg in self.ligands
            if lg.name3 not in NOT_A_LIGAND and lg.n_atoms >= 6
        ]
        if not candidates:
            return self.longest_chain()

        best: tuple[int, str] | None = None
        for chain in self.chains:
            n_contact = max(
                (len(self.residues_near(lg.coords, contact_radius, chain))
                 for lg in candidates),
                default=0,
            )
            if n_contact and (best is None or n_contact > best[0]
                              or (n_contact == best[0]
                                  and len(self.chains[chain]) > len(self.chains[best[1]]))):
                best = (n_contact, chain)
        return best[1] if best else self.longest_chain()

    def ca_coords(self, chain: str) -> tuple[np.ndarray, list[Residue]]:
        """C-alpha coordinates and the residues that have one."""
        res = [r for r in self.chains.get(chain, []) if r.ca is not None]
        if not res:
            return np.zeros((0, 3)), []
        return np.vstack([r.ca for r in res]), res

    def primary_ligand(
        self, chain: str | None = None, *, contact_radius: float = 5.0
    ) -> Ligand | None:
        """The largest non-solvent heteroatom group, optionally restricted to a chain.

        Passing ``chain`` is almost always what you want when a pocket is involved:
        the largest ligand in the file may sit in a different protein copy, and
        comparing chain B's residues against chain A's ligand yields an empty pocket.
        Falls back to the whole structure only when no ligand contacts that chain.
        """
        real = [lg for lg in self.ligands if lg.name3 not in NOT_A_LIGAND and lg.n_atoms >= 6]
        if not real:
            return None
        if chain is not None:
            # Strictly this chain's ligand. Falling back to the largest ligand
            # anywhere would attribute a *different* chain's ligand to this one —
            # in a heterodimer that is the partner protein's ligand, and reporting
            # it as this chain's is simply false.
            in_chain = [
                lg for lg in real
                if self.residues_near(lg.coords, contact_radius, chain)
            ]
            return max(in_chain, key=lambda lg: lg.n_atoms) if in_chain else None
        return max(real, key=lambda lg: lg.n_atoms)

    def chains_with_ligands(self, *, contact_radius: float = 5.0) -> dict[str, list[str]]:
        """Which chains hold which ligands. Used to explain an empty pocket result."""
        out: dict[str, list[str]] = {}
        real = [lg for lg in self.ligands if lg.name3 not in NOT_A_LIGAND and lg.n_atoms >= 6]
        for chain in self.chains:
            names = [
                lg.name3 for lg in real
                if self.residues_near(lg.coords, contact_radius, chain)
            ]
            if names:
                out[chain] = sorted(set(names))
        return out

    def residues_near(
        self, points: np.ndarray, radius: float, chain: str | None = None
    ) -> list[Residue]:
        """Residues with any atom within ``radius`` of any of ``points``.

        Takes a point *set* rather than a single point on purpose. Measuring from a
        ligand's centroid badly under-counts the pocket for anything larger than a
        fragment — a long or bent ligand puts most of its contacting residues far
        from its own centre of mass. Pass every ligand atom instead.
        """
        pts = np.atleast_2d(points)
        out = []
        chains = [chain] if chain else list(self.chains)
        for c in chains:
            for r in self.chains.get(c, []):
                if not r.atoms:
                    continue
                atom_xyz = np.vstack(list(r.atoms.values()))
                # Pairwise distances between this residue's atoms and every point.
                d = np.linalg.norm(atom_xyz[:, None, :] - pts[None, :, :], axis=2)
                if float(d.min()) <= radius:
                    out.append(r)
        return out


def parse_pdb(text: str, struct_id: str, source: str) -> Structure:
    """Parse ATOM/HETATM records. Takes the first model only.

    Deliberately tolerant: a malformed line is skipped rather than raising, because
    predicted-structure files from various tools have assorted quirks and aborting
    on one bad line would make the tool useless. Counts of skipped lines are not
    tracked — if a structure looks wrong, inspect the file.
    """
    st = Structure(id=struct_id, source=source, raw_text=text)
    seen: dict[tuple[str, int, str], Residue] = {}
    lig_acc: dict[tuple[str, str, int], list] = {}

    for line in text.splitlines():
        rec = line[:6]
        if rec == "ENDMDL":
            break
        if rec == "TITLE " and not st.title:
            st.title = line[10:].strip()
            continue
        if rec not in ("ATOM  ", "HETATM"):
            continue
        try:
            # Skip alternate locations other than the first.
            altloc = line[16]
            if altloc not in (" ", "A"):
                continue
            name = line[12:16].strip()
            res3 = line[17:20].strip()
            chain = line[21].strip() or "A"
            seq_num = int(line[22:26])
            insertion = line[26]
            xyz = np.array([float(line[30:38]), float(line[38:46]), float(line[46:54])])
        except (ValueError, IndexError):
            continue

        if rec == "HETATM" and res3 not in AA3TO1:
            elem = line[76:78].strip() or name[:1]
            lig_acc.setdefault((res3, chain, seq_num), []).append((xyz, elem))
            continue

        key = (chain, seq_num, insertion)
        r = seen.get(key)
        if r is None:
            r = Residue(chain=chain, seq_num=seq_num, insertion=insertion, name3=res3)
            seen[key] = r
            st.chains.setdefault(chain, []).append(r)
        r.atoms[name] = xyz
        if name == "CA":
            r.ca = xyz
            # A missing or malformed B-factor column is common in predicted models
            # and never worth failing a parse over.
            with contextlib.suppress(ValueError, IndexError):
                r.bfactor = float(line[60:66])

    for (res3, chain, seq_num), atoms in lig_acc.items():
        st.ligands.append(Ligand(
            name3=res3, chain=chain, seq_num=seq_num,
            coords=np.vstack([a[0] for a in atoms]),
            element=[a[1] for a in atoms],
        ))
    for c in st.chains:
        st.chains[c].sort(key=lambda r: (r.seq_num, r.insertion))
    return st


def _download(url: str, timeout: int = 60) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "reagent/0.1 (+structure-compare)"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return raw.decode("utf-8", errors="replace")


def fetch(node_id: str, *, cache_dir: Path | None = None, timeout: int = 60) -> Structure:
    """Fetch a structure by graph node id.

    Accepts the namespaced ids the graph uses:

        ``pdb:1M13``          -> RCSB
        ``uniprot:O75469``    -> AlphaFold DB predicted model
        ``file:path/to.pdb``  -> a local file

    Cached under ``data/cache/structures/``. A cache hit skips the network entirely,
    which matters because the comparison tool is called repeatedly and RCSB should
    not be hit once per question.
    """
    cache = Path(cache_dir or CACHE)
    cache.mkdir(parents=True, exist_ok=True)

    if node_id.startswith("file:"):
        p = Path(node_id[5:])
        if not p.is_file():
            raise FileNotFoundError(f"no such structure file: {p}")
        st = parse_pdb(p.read_text(encoding="utf-8", errors="replace"), node_id, f"file:{p}")
        st.local_path = str(p)
        return st

    safe = node_id.replace(":", "_").replace("/", "_")
    cached = cache / f"{safe}.pdb"
    if cached.is_file() and cached.stat().st_size > 0:
        st = parse_pdb(cached.read_text(encoding="utf-8", errors="replace"), node_id, "cache")
        st.local_path = str(cached)
        return st

    if node_id.startswith("pdb:"):
        acc = node_id[4:].strip().upper()
        urls = [RCSB_PDB.format(pdb_id=acc)]
        source = f"RCSB {acc}"
    elif node_id.startswith("uniprot:"):
        acc = node_id[8:].strip().upper()
        urls = [AF_DB.format(acc=acc)]
        source = f"AlphaFold DB {acc} (predicted)"
    else:
        raise ValueError(
            f"cannot fetch {node_id!r}: expected 'pdb:<id>', 'uniprot:<acc>', or "
            "'file:<path>'"
        )

    last: Exception | None = None
    for url in urls:
        try:
            text = _download(url, timeout=timeout)
            cached.write_text(text, encoding="utf-8")
            st = parse_pdb(text, node_id, source)
            st.local_path = str(cached)
            return st
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
            last = exc
    raise RuntimeError(
        f"could not fetch {node_id} from {urls}: {last}. "
        "For a UniProt accession this may mean AlphaFold DB has no model for it; "
        "try an experimental structure via 'pdb:<id>' instead."
    )
