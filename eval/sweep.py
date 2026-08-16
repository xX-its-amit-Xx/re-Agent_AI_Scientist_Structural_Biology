#!/usr/bin/env python
"""Evaluate selection choices on dev: which signal, and how big a rescue.

Answers the two questions `signal-scoping` and `tail-rescue` pose, using the
per-candidate true scores `eval/score_pool.py` already computed -- so a sweep is
table lookups rather than re-scoring, and trying twenty configurations costs
nothing.

What it reports:

  discrimination   ROC AUC of every native signal against pose success, with the
                   negative control checked FIRST. A control far from 0.5 means
                   the harness is wrong and no other row can be believed.
  selection        realised score per signal, so the AUC ranking can be checked
                   against what it actually buys.
  rescue sweep     score against N for each candidate rescue model, whole curve.
  significance     paired bootstrap of every candidate against the baseline.

**Dev only.** Everything here reads ground truth, so its outputs are configuration
choices -- a signal name and an integer N -- which then get frozen and applied
blind. Running this on holdout is how a holdout stops being one.

    .venv/bin/python eval/sweep.py --run-id pilot
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "eval" / "results"
sys.path.insert(0, str(ROOT / "stages"))

from candidates import (  # noqa: E402
    LOWER_IS_BETTER, NEGATIVE_CONTROL, PARTIAL_CONTROL, SIGNAL_FIELDS, load_candidates, orient,
)
from descriptors import DESCRIPTORS  # noqa: E402
from selection import within_model_best, zscore_across_models  # noqa: E402

# Native signals, the derived interface signal, the control, and the physics
# challengers -- all ranked in one table against one label. A challenger judged on
# its own terms has not been tested; that is the whole point of the comparison.
CANDIDATE_SIGNALS = SIGNAL_FIELDS + ["min_interface_pae", "random_control"] + DESCRIPTORS
SUCCESS_RMSD = 2.0
PRIMARY = "LDDT-PLI"


def auc(signal: np.ndarray, is_good: np.ndarray) -> float:
    """Rank-based ROC AUC, tie-corrected. No sklearn dependency."""
    signal, is_good = np.asarray(signal, float), np.asarray(is_good, bool)
    keep = ~np.isnan(signal)
    signal, is_good = signal[keep], is_good[keep]
    n_pos, n_neg = int(is_good.sum()), int((~is_good).sum())
    if n_pos == 0 or n_neg == 0 or signal.size == 0:
        return float("nan")
    order = signal.argsort()
    ranks = np.empty(signal.size, float)
    ranks[order] = np.arange(1, signal.size + 1)
    for v in np.unique(signal):
        m = signal == v
        ranks[m] = ranks[m].mean()
    return float((ranks[is_good].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


def bootstrap_delta(a: np.ndarray, b: np.ndarray, n: int = 1000, seed: int = 0) -> dict:
    """Paired difference b - a, resampled by item. Paired removes item difficulty."""
    rng = np.random.default_rng(seed)
    d = np.asarray(b, float) - np.asarray(a, float)
    d = d[~np.isnan(d)]
    if d.size == 0:
        return {"delta": float("nan"), "ci_lo": float("nan"), "ci_hi": float("nan"),
                "wins": 0, "losses": 0}
    means = np.array([d[rng.integers(0, d.size, d.size)].mean() for _ in range(n)])
    return {
        "delta": float(means.mean()),
        "ci_lo": float(np.percentile(means, 2.5)),
        "ci_hi": float(np.percentile(means, 97.5)),
        "wins": int((d > 0).sum()),
        "losses": int((d < 0).sum()),
    }


def selection_score(cands: pd.DataFrame, truth: pd.DataFrame, signal: str) -> pd.Series | None:
    """True primary score per item, for the selection this signal produces."""
    try:
        best = within_model_best(cands, signal)
        chosen = zscore_across_models(best, signal)
    except (SystemExit, KeyError, ValueError):
        return None
    key = ["structure_id", "model", "seed", "sample"]
    merged = chosen[key].merge(truth, on=key, how="left")
    return merged.set_index("structure_id")[PRIMARY]


def rescue_sweep(cands: pd.DataFrame, truth: pd.DataFrame, signal: str,
                 rescue_model: str, ns: list[int]) -> pd.DataFrame:
    """Score against N, overwriting the N lowest-confidence items."""
    best = within_model_best(cands, signal)
    chosen = zscore_across_models(best, signal)
    key = ["structure_id", "model", "seed", "sample"]
    tvals = truth.set_index(key)[PRIMARY]
    pool = best[best.model == rescue_model].set_index("structure_id")

    order = chosen.sort_values("z").structure_id.tolist()
    rows = []
    for n in ns:
        swapped = set(order[:n])
        vals = []
        for r in chosen.itertuples(index=False):
            src = pool.loc[r.structure_id] if (r.structure_id in swapped and r.structure_id in pool.index) else r
            k = (r.structure_id, src.model, src.seed, src.sample)
            vals.append(tvals.get(k, np.nan))
        rows.append({"n": n, "score": float(np.nanmean(vals)), "n_items": int(np.sum(~np.isnan(vals)))})
    return pd.DataFrame(rows)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--baseline-signal", default="confidence_score")
    args = ap.parse_args()

    run_dir = ROOT / "runs" / args.run_id
    truth_path = RESULTS / f"{args.run_id}_truth.csv"
    if not truth_path.exists():
        print(f"missing {truth_path.relative_to(ROOT)} -- run eval/score_pool.py first")
        return 1

    cands = load_candidates(run_dir)
    truth = pd.read_csv(truth_path)
    key = ["structure_id", "model", "seed", "sample"]
    joined = cands[cands.status == "done"].merge(truth, on=key, how="left")

    # Physics challengers, if descriptors were computed. Absent is fine and is
    # reported as absent -- a missing challenger must not look like a failed one.
    desc_path = run_dir / "descriptors.csv"
    if desc_path.exists():
        desc = pd.read_csv(desc_path)
        joined = joined.merge(desc[[c for c in desc.columns if c in key + DESCRIPTORS]],
                              on=key, how="left")
        print(f"physics challengers merged: {[d for d in DESCRIPTORS if d in joined]}\n")
    else:
        print(f"no {desc_path.relative_to(ROOT)} -- physics challengers untested. "
              f"Run: .venv/bin/python stages/descriptors.py --run-id {args.run_id}\n")

    joined["is_good"] = joined["BiSyRMSD"] <= SUCCESS_RMSD

    # --- discrimination, control first -------------------------------------
    #
    # Coverage is reported per signal and per model, because signals are NOT
    # emitted by every generator. Ranking a signal present on one model's 9
    # candidates against one present on all 29 compares different populations,
    # and the resulting order is decided by which model happened to be easy --
    # not by which signal discriminates. `full_pool` marks the comparable rows.
    n_models = int(joined.model.nunique())
    rows = []
    for s in CANDIDATE_SIGNALS:
        if s not in joined or joined[s].notna().sum() == 0:
            continue
        sub = joined[joined[s].notna()]
        rows.append({
            "signal": s,
            "auc": auc(orient(sub[s], s).to_numpy(), sub.is_good.to_numpy()),
            "n": int(len(sub)),
            "models": int(sub.model.nunique()),
            "full_pool": int(sub.model.nunique()) == n_models,
            "control": s == NEGATIVE_CONTROL,
        })
    disc = pd.DataFrame(rows).sort_values(["full_pool", "auc"], ascending=[False, False])

    partial = disc[~disc.full_pool]
    if not partial.empty:
        print("=== partial-coverage signals (NOT comparable to the rest) ===")
        print(partial[["signal", "auc", "n", "models"]].round(3).to_string(index=False))
        print("  emitted by only some generators; their AUCs describe a different "
              "population and must not be ranked against full-pool signals.\n")

    ctrl = disc[disc.control]
    print("=== negative control ===")
    if ctrl.empty:
        print(f"  {NEGATIVE_CONTROL} absent -- cannot validate the harness")
    elif not bool(ctrl.full_pool.iloc[0]):
        # A control emitted by one generator validates that generator's slice, not
        # the pool. Saying so is the point: an invalid control must not be read as
        # a passing one.
        print(f"  {NEGATIVE_CONTROL} is emitted by only {int(ctrl.models.iloc[0])} of {n_models} "
              f"generators (n={int(ctrl.n.iloc[0])}), so it does NOT validate the pool. "
              "Its AUC describes one generator's candidates.")
        print("  NO VALID POOL-WIDE CONTROL -- treat every AUC below as unvalidated.")
    else:
        c = float(ctrl.auc.iloc[0])
        verdict = "OK (near chance)" if 0.35 <= c <= 0.65 else "SUSPECT -- investigate before trusting anything below"
        print(f"  {NEGATIVE_CONTROL} AUC = {c:.3f}  {verdict}")

    print(f"\n=== discrimination, full-pool signals (success = BiSyRMSD <= {SUCCESS_RMSD} A) ===")
    print(disc[disc.full_pool].round(3).to_string(index=False))

    # --- what each signal actually buys ------------------------------------
    base = selection_score(cands, truth, args.baseline_signal)
    sel_rows = []
    for s in disc[disc.full_pool].signal:
        v = selection_score(cands, truth, s)
        if v is None:
            continue
        row = {"signal": s, f"mean_{PRIMARY}": float(v.mean()), "n_items": int(v.notna().sum())}
        if base is not None and s != args.baseline_signal:
            aligned = base.reindex(v.index)
            row.update(bootstrap_delta(aligned.to_numpy(), v.to_numpy()))
        sel_rows.append(row)
    sel = pd.DataFrame(sel_rows).sort_values(f"mean_{PRIMARY}", ascending=False)
    print(f"\n=== realised {PRIMARY} by selection signal (baseline: {args.baseline_signal}) ===")
    print(sel.round(4).to_string(index=False))

    # --- rescue sweep -------------------------------------------------------
    top = sel.signal.iloc[0]
    n_items = int(joined.structure_id.nunique())
    ns = sorted({0, 1, 2, 3, max(1, n_items // 10), max(1, n_items // 5), max(1, n_items // 3)})
    sweeps = {}
    print(f"\n=== rescue sweep on {top!r} ===")
    for m in sorted(joined.model.unique()):
        curve = rescue_sweep(cands, truth, top, m, ns)
        sweeps[m] = curve.to_dict("records")
        peak = curve.loc[curve.score.idxmax()]
        print(f"  rescue with {m}: " + "  ".join(f"N={int(r.n)}:{r.score:.4f}" for r in curve.itertuples())
              + f"   peak N={int(peak.n)}")

    out = {
        "run_id": args.run_id,
        "negative_control": {"signal": NEGATIVE_CONTROL,
                             "auc": None if ctrl.empty else float(ctrl.auc.iloc[0])},
        "discrimination": disc.to_dict("records"),
        "selection": sel.to_dict("records"),
        "rescue_sweeps": sweeps,
        "recommended": {"signal": top, "baseline": args.baseline_signal},
    }
    dest = RESULTS / f"{args.run_id}_sweep.json"
    dest.write_text(json.dumps(out, indent=2, default=str))
    print(f"\nwrote {dest.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
