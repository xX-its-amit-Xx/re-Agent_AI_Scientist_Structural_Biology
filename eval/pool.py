#!/usr/bin/env python
"""Assemble a cofold run into a candidate table, and measure the pool.

Produces the three numbers Stage 3 turns on, and nothing else:

  oracle gap      how good the pool's best candidate is, versus what a selector
                  picks. Decides whether the bottleneck is generation or selection.
  correlation     pairwise per-item accuracy correlation between models. What a
                  pool is actually buying; also picks the rescue model.
  unique wins     items where one model is the only one that succeeds. A model
                  with none of these is paying rent without contributing coverage.

This file measures; it does not choose. Which signal to select on, and whether to
widen or improve the selector, are judgement -- see the `bottleneck-triage`,
`generator-diversity` and `signal-scoping` skills.

Ground truth is read here, and only here, because scoring the pool requires it.
Nothing downstream of `stage3.pose_pool` may read the columns this writes under
`true_*`; see the `leak-containment` skill.

    .venv/bin/python eval/pool.py --run-id pilot
"""

from __future__ import annotations

import argparse
import json
import sys
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "eval" / "results"
sys.path.insert(0, str(ROOT / "stages"))

from candidates import NEGATIVE_CONTROL, load_candidates  # noqa: E402

SUCCESS_RMSD = 2.0  # the conventional pose-accuracy threshold


def oracle_gap(scored: pd.DataFrame, metric: str, higher_better: bool) -> dict:
    """Realised (best native confidence) versus oracle (best true score)."""
    pick = "max" if higher_better else "min"
    per_item = []
    for sid, g in scored.groupby("structure_id"):
        g = g.dropna(subset=[metric])
        if g.empty:
            continue
        oracle = getattr(g[metric], pick)()
        # Baseline selector: highest native confidence, ignorant of truth.
        realised = g.loc[g.confidence_score.idxmax(), metric] if g.confidence_score.notna().any() else np.nan
        per_item.append({"structure_id": sid, "oracle": oracle, "realised": realised})
    df = pd.DataFrame(per_item)
    return {
        "n_items": len(df),
        "oracle_mean": float(df.oracle.mean()),
        "realised_mean": float(df.realised.mean()),
        "gap": float(df.oracle.mean() - df.realised.mean()),
        "per_item": df,
    }


def best_at_k(scored: pd.DataFrame, metric: str, higher_better: bool,
              ks: list[int], trials: int = 300, seed: int = 0) -> pd.DataFrame:
    """Expected best-of-k when sampling k candidates per item at random."""
    rng = np.random.default_rng(seed)
    pick = np.max if higher_better else np.min
    by_item = [g[metric].dropna().to_numpy() for _, g in scored.groupby("structure_id")]
    by_item = [a for a in by_item if a.size]
    out = []
    for k in ks:
        means = [
            np.mean([pick(rng.choice(a, size=min(k, a.size), replace=False)) for a in by_item])
            for _ in range(trials)
        ]
        out.append({"k": k, "mean": float(np.mean(means)), "std": float(np.std(means))})
    return pd.DataFrame(out)


def correlation_and_wins(scored: pd.DataFrame, metric: str, higher_better: bool) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Pairwise per-item accuracy correlation, and per-model unique-win counts."""
    pick = "max" if higher_better else "min"
    wide = scored.pivot_table(index="structure_id", columns="model", values=metric, aggfunc=pick)

    models = list(wide.columns)
    corr = pd.DataFrame(index=models, columns=models, dtype=float)
    for a, b in combinations(models, 2):
        both = wide[[a, b]].dropna()
        c = both[a].corr(both[b]) if len(both) > 1 else np.nan
        corr.loc[a, b] = corr.loc[b, a] = c
    for m in models:
        corr.loc[m, m] = 1.0

    # Success is always an RMSD question, whatever metric the pool is ranked on.
    # Applying the 2 A threshold to LDDT-PLI silently yields zero successes for
    # everything, because LDDT-PLI never exceeds 1 -- which reads as "no model
    # solved anything" rather than as a unit error.
    rmsd = scored.pivot_table(index="structure_id", columns="model", values="BiSyRMSD", aggfunc="min")
    ok = rmsd <= SUCCESS_RMSD
    wins = pd.DataFrame({
        "model": models,
        "n_items": [int(wide[m].notna().sum()) for m in models],
        "solved": [int(ok[m].sum()) for m in models if m in ok],
        "unique_wins": [
            int(((ok[m]) & (ok.drop(columns=[m]).sum(axis=1) == 0)).sum()) for m in models if m in ok
        ],
        "best_on": [int((wide[m] == getattr(wide, pick)(axis=1)).sum()) for m in models],
    })
    return corr, wins


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--metric", default="BiSyRMSD", help="true-score column to measure the pool on")
    ap.add_argument("--higher-better", action="store_true", help="set for LDDT-PLI, omit for BiSyRMSD")
    args = ap.parse_args()

    run_dir = ROOT / "runs" / args.run_id
    cands = load_candidates(run_dir)
    done = cands[cands.status == "done"]
    print(f"{len(done)}/{len(cands)} candidates, {done.structure_id.nunique()} items, "
          f"{done.model.nunique()} models")

    scored_path = RESULTS / f"{args.run_id}_candidates.csv"
    truth_path = RESULTS / f"{args.run_id}_truth.csv"
    if not truth_path.exists():
        cands.to_csv(scored_path, index=False)
        print(f"wrote {scored_path.relative_to(ROOT)}")
        print(f"no true scores yet -- run eval/score_pool.py --run-id {args.run_id} first")
        return 1

    truth = pd.read_csv(truth_path)
    scored = done.merge(truth, on=["structure_id", "model", "seed", "sample"], how="left")
    scored.to_csv(scored_path, index=False)

    gap = oracle_gap(scored, args.metric, args.higher_better)
    curve = best_at_k(scored, args.metric, args.higher_better, ks=[1, 2, 3, 5, 10])
    corr, wins = correlation_and_wins(scored, args.metric, args.higher_better)

    print(f"\n=== oracle gap ({args.metric}, {'higher' if args.higher_better else 'lower'} better) ===")
    print(f"  oracle   {gap['oracle_mean']:.4f}")
    print(f"  realised {gap['realised_mean']:.4f}")
    print(f"  gap      {gap['gap']:+.4f}  over {gap['n_items']} items")
    print(f"\n=== best@k ===\n{curve.to_string(index=False)}")
    print(f"\n=== pairwise accuracy correlation ===\n{corr.round(3).to_string()}")
    print(f"\n=== per-model coverage ===\n{wins.to_string(index=False)}")

    summary = {
        "run_id": args.run_id, "metric": args.metric, "higher_better": args.higher_better,
        "oracle": gap["oracle_mean"], "realised": gap["realised_mean"], "gap": gap["gap"],
        "n_items": gap["n_items"],
        "best_at_k": curve.to_dict("records"),
        "correlation": corr.round(4).to_dict(),
        "coverage": wins.to_dict("records"),
        "negative_control": NEGATIVE_CONTROL,
    }
    (RESULTS / f"{args.run_id}_pool.json").write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nwrote {(RESULTS / f'{args.run_id}_pool.json').relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
