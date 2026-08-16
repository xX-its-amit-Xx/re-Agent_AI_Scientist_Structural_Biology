#!/usr/bin/env python
"""Build the receptor MSA once, so no cofold job ever generates it again.

Every target in this challenge folds the **same** receptor against a different
ligand. The protein sequence is a constant. So per-job MSA generation computes an
identical alignment once per job -- hundreds of times for one answer, and it is
the dominant term in a large run's wall clock.

This searches once and caches the result. Cofold then supplies it on every call,
which also makes runs reproducible: a remote alignment service can return
different depth on different days, and a cached MSA removes that variance from
comparisons between runs.

Runs locally against the ColabFold API -- no deployment needed, seconds to
complete.

    .venv/bin/python stages/build_msa.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "runs" / "_msa" / "pxr_lbd.json"


def sequence_from_stage02() -> str:
    """Read PXR_LBD out of stage 02 rather than duplicating it.

    Two copies of a sequence is one copy too many: the cache validates itself
    against stage 02's constant, so a divergence here would produce an alignment
    that silently describes a different protein.
    """
    text = (ROOT / "stages" / "02_cofold.py").read_text()
    body = text.split("PXR_LBD = (", 1)[1].split(")", 1)[0]
    return "".join(part.strip().strip('"') for part in body.splitlines() if part.strip())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=CACHE)
    ap.add_argument("--metagenomic", action="store_true",
                    help="also search the environmental DB for a deeper alignment")
    ap.add_argument("--force", action="store_true", help="rebuild even if the cache is current")
    args = ap.parse_args()

    from proto_tools import (
        Mmseqs2HomologySearchConfig,
        Mmseqs2HomologySearchInput,
        run_mmseqs2_homology_search,
    )

    seq = sequence_from_stage02()
    print(f"receptor: {len(seq)} residues")

    if args.out.exists() and not args.force:
        cached = json.loads(args.out.read_text())
        if cached.get("sequence") == seq:
            print(f"cache is current ({len(cached['aligned_sequences'])} rows); --force to rebuild")
            return 0
        print("cache is for a different sequence; rebuilding")

    out = run_mmseqs2_homology_search(
        Mmseqs2HomologySearchInput(
            queries=[{"sequence": seq, "sequence_id": "PXR_LBD", "molecule_type": "protein"}]
        ),
        Mmseqs2HomologySearchConfig(search_mode="remote", use_metagenomic_db=args.metagenomic),
    )
    res = out.results[0]
    if not res.msas:
        print("search returned no alignment")
        return 1
    msa = res.msas[0]

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({
        "sequence": seq,
        "aligned_sequences": msa.aligned_sequences,
        "sequence_ids": msa.sequence_ids,
        "datasets_searched": res.datasets_searched,
        "num_homologs_found": res.num_homologs_found,
    }))
    print(f"{len(msa.aligned_sequences)} rows from {res.datasets_searched}")
    print(f"wrote {args.out.relative_to(ROOT)} ({args.out.stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
