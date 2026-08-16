#!/usr/bin/env python
"""Collapse a candidate pool to one pose per item. Mechanical only.

This executes a selection rule; it does not choose one. Which signal to rank on,
whether to rescue a tail and with which model, and how many to rescue are
**judgement**, and they live in the `signal-scoping`, `score-normalization` and
`tail-rescue` skills. They arrive here as arguments.

That split is deliberate and was learned the expensive way: an earlier version of
this stage hardcoded pose-agreement (medoid) selection, which is refuted, and the
hardcoding is what made the refutation cost a rewrite instead of a flag.

The rule implemented, in order:

  1. per model, per item -- keep that model's best sample by its own native signal
  2. z-score each model's best-sample scores across all items, then argmax per item
  3. optionally overwrite the N lowest-confidence items with a rescue model's pose

Step 2 is the load-bearing one. Raw confidences from different models are not
commensurable, and comparing them directly selects the model with the widest
scale rather than the better pose.

**This file never reads ground truth.** Choosing N by looking at true scores is a
leak; sweep it on dev with eval/sweep.py, freeze N, then apply it here.

Named `selection.py`, not `select.py`: `select` is a stdlib module that `selectors`
imports, so a file by that name on sys.path breaks pandas, sockets and anything
else that reaches asyncio. The same collision class as naming a directory `modal/`.

    .venv/bin/python stages/selection.py --run-id pilot --signal confidence_score
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "stages"))

from candidates import LOWER_IS_BETTER, load_candidates, orient  # noqa: E402
from pose_to_pdb import convert  # noqa: E402


def within_model_best(cands: pd.DataFrame, signal: str) -> pd.DataFrame:
    """Step 1 — each model's own best sample per item, by its own native signal."""
    done = cands[(cands.status == "done") & cands[signal].notna()].copy()
    if done.empty:
        raise SystemExit(f"no candidates carry signal {signal!r}")
    done["_rank"] = orient(done[signal], signal)
    idx = done.groupby(["structure_id", "model"])["_rank"].idxmax()
    return done.loc[idx].drop(columns="_rank").reset_index(drop=True)


def zscore_across_models(best: pd.DataFrame, signal: str) -> pd.DataFrame:
    """Step 2 — z-score within each model across items, then argmax per item."""
    best = best.copy()
    best["_oriented"] = orient(best[signal], signal)

    def _z(g: pd.Series) -> pd.Series:
        sd = g.std()
        # A model with no spread carries no ranking information. Zeroing abstains
        # rather than dividing by ~0 and producing garbage extremes.
        return pd.Series(np.zeros(len(g)), index=g.index) if not sd or sd < 1e-12 else (g - g.mean()) / sd

    best["z"] = best.groupby("model")["_oriented"].transform(_z)
    idx = best.groupby("structure_id")["z"].idxmax()
    chosen = best.loc[idx].drop(columns="_oriented").reset_index(drop=True)
    chosen["reason"] = f"argmax z({signal}) across models"
    return chosen.sort_values("z").reset_index(drop=True)


def rescue_tail(chosen: pd.DataFrame, best: pd.DataFrame, rescue_model: str, n: int,
                signal: str) -> pd.DataFrame:
    """Step 3 — overwrite the N lowest-confidence items with a rescue model's pose.

    Chosen by *confidence rank*, never by true score. Ranking the tail by truth is
    the leak that makes this step look far better than it is.
    """
    if n <= 0:
        return chosen
    pool = best[best.model == rescue_model].set_index("structure_id")
    if pool.empty:
        raise SystemExit(f"rescue model {rescue_model!r} produced no candidates")

    out = chosen.copy()
    out["rescued"] = False
    tail = out.nsmallest(n, "z").structure_id
    for sid in tail:
        if sid not in pool.index:
            continue
        row = pool.loc[sid]
        mask = out.structure_id == sid
        for col in ("model", "seed", "sample", "cif", signal):
            if col in row:
                out.loc[mask, col] = row[col]
        out.loc[mask, "rescued"] = True
        out.loc[mask, "reason"] = f"tail rescue from {rescue_model} (N={n})"
    return out


def write_poses(chosen: pd.DataFrame, dest: Path) -> tuple[int, list[str]]:
    """Convert each chosen candidate into submission-format PDB."""
    dest.mkdir(parents=True, exist_ok=True)
    ok, failed = 0, []
    for row in chosen.itertuples(index=False):
        try:
            convert(ROOT / row.cif, row.smiles, dest / f"{row.structure_id}.pdb")
            ok += 1
        except Exception as e:
            failed.append(f"{row.structure_id}: {type(e).__name__}: {e}")
    return ok, failed


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--signal", default="confidence_score",
                    help="native confidence field to rank on; chosen by signal-scoping, not here")
    ap.add_argument("--rescue-model", help="decorrelated model to overwrite the tail with")
    ap.add_argument("--rescue-n", type=int, default=0, help="how many tail items to overwrite; sweep it on dev")
    ap.add_argument("--out", type=Path, help="pose directory (default runs/<run-id>/selected)")
    ap.add_argument("--no-poses", action="store_true", help="write the table only, skip PDB conversion")
    args = ap.parse_args()

    run_dir = ROOT / "runs" / args.run_id
    cands = load_candidates(run_dir)
    best = within_model_best(cands, args.signal)
    chosen = zscore_across_models(best, args.signal)
    if args.rescue_model:
        chosen = rescue_tail(chosen, best, args.rescue_model, args.rescue_n, args.signal)

    sel_path = run_dir / "selection.csv"
    cols = [c for c in ("structure_id", "model", "seed", "sample", args.signal, "z",
                        "rescued", "reason", "cif") if c in chosen]
    chosen[cols].to_csv(sel_path, index=False)

    direction = "lower" if args.signal in LOWER_IS_BETTER else "higher"
    print(f"{len(chosen)} items selected on {args.signal!r} ({direction} is better)")
    print(chosen.model.value_counts().to_string())
    if args.rescue_model:
        print(f"rescued {int(chosen.rescued.sum())} from {args.rescue_model}")
    print(f"wrote {sel_path.relative_to(ROOT)}")

    if not args.no_poses:
        dest = args.out or (run_dir / "selected")
        ok, failed = write_poses(chosen, dest)
        print(f"wrote {ok}/{len(chosen)} poses to {dest.relative_to(ROOT)}")
        for f in failed:
            print(f"  FAILED {f}")
        if failed:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
