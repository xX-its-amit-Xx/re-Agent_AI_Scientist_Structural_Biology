#!/usr/bin/env python
"""Stage 02 — cofold each target into a protein-ligand complex.

Reads manifest/ligands.csv, emits one job per (target x model x seed) and
dispatches it through proto-tools. Nothing here selects a pose; that is stage 03.

Ensemble sizing is a Phase 2 decision and deliberately not hardcoded -- pass
--models/--seeds once timing calibration says what fits the GPU budget.

Five cofold models, deployed two different ways — `modal/client.py:cofold()`
hides the difference, so always dispatch through it rather than calling a
backend directly:

    boltz2-prediction  chai1-prediction  protenix-prediction  rf3-prediction
        proto-tools apps, `open` weights, deployed with `proto-tools deploy`
    alphafold3-prediction
        our own Modal app (modal/alphafold3_service.py) -- proto-tools ships no
        AF3 deployment. Weights are DeepMind-licensed, non-commercial research
        only, and live on the proto-cache volume.

Input format is Boltz YAML, per the organizers' tutorial
(inputs/pxr_x01378-1.yaml in OpenADMET/PXR-Challenge-Tutorial):

    version: 1
    sequences:
      - protein: {id: A, sequence: <PXR LBD>}
      - ligand:  {id: B, smiles: <target SMILES>}

Chain A must be the protein and chain B the ligand, because stage 04 expects
that assignment when it renames the ligand residue to LIG.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "manifest"
RUNS = ROOT / "runs"

# PXR ligand-binding domain, chain A -- from the organizers' tutorial
# (inputs/PXR_protein_sequence.fasta). 291 residues.
PXR_LBD = (
    "GLTEEQRMMIRELMDAQMKTFDTTFSHFKNFRLPGVLSSGCELPESLQAPSREEAAKWSQVRKDLCSLKVSLQLRGEDGS"
    "VWNYKPPADSGGKEIFSLLPHMADMSTYMFKGIISFAKVISYFRDLPIEDQISLLKGAAFELCQLRFNTVFNAETGTWEC"
    "GRLSYCLEDTAGGFQQLLLEPMLKFHYMLKKLQLHEEEYVLMQAISLFSPDRPGVLQHRVVDQLQEQFAITLKSYIECNR"
    "PQPAHRFLFLKIMAMLTELRSINAQHTQRLLRIQDIHPFATPLMQELFGITGS"
)

DEFAULT_MODELS = ["boltz2-prediction"]
DEFAULT_SEEDS = [1]


def write_boltz_yaml(structure_id: str, smiles: str, dest: Path) -> Path:
    """Write one Boltz-format cofold input. Chain A protein, chain B ligand."""
    spec = {
        "version": 1,
        "sequences": [
            {"protein": {"id": "A", "sequence": PXR_LBD}},
            {"ligand": {"id": "B", "smiles": smiles}},
        ],
    }
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(yaml.safe_dump(spec, sort_keys=False, default_flow_style=False))
    return dest


def build_jobs(ligands: pd.DataFrame, models: list[str], seeds: list[int], run_dir: Path) -> list[dict]:
    jobs = []
    for rec in ligands.itertuples(index=False):
        yaml_path = write_boltz_yaml(
            rec.structure_id, rec.smiles, run_dir / "inputs" / f"{rec.structure_id}.yaml"
        )
        for model in models:
            for seed in seeds:
                jobs.append(
                    {
                        "structure_id": rec.structure_id,
                        "smiles": rec.smiles,
                        "model": model,
                        "seed": seed,
                        "input_yaml": str(yaml_path.relative_to(ROOT)),
                        "output_dir": str(
                            (run_dir / "cofold" / model / f"seed{seed}" / rec.structure_id).relative_to(ROOT)
                        ),
                        "status": "pending",
                    }
                )
    return jobs


def write_result(job: dict, out: dict) -> dict:
    """Persist one cofold result and return what the job record should remember.

    Writes the structure and the model's metrics **verbatim and unnormalised** --
    stage 03 needs each model's native confidence in its own units, and
    normalising here would destroy exactly the signal it selects on.
    """
    out_dir = ROOT / job["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)

    structures = out.get("structures") or []
    if not structures:
        raise RuntimeError("tool returned no structures")

    written = []
    for i, s in enumerate(structures):
        fmt = s.get("structure_format") or "cif"
        path = out_dir / f"sample{i}.{fmt}"
        path.write_text(s["structure"])
        written.append(str(path.relative_to(ROOT)))

    metrics = [s.get("metrics") or {} for s in structures]
    (out_dir / "metrics.json").write_text(json.dumps(metrics, indent=2, default=str))

    primary = metrics[0] if metrics else {}
    return {
        "structures": written,
        "metrics_json": str((out_dir / "metrics.json").relative_to(ROOT)),
        "execution_time_s": out.get("execution_time"),
        "primary_metric": primary.get("primary_metric"),
    }


MSA_CACHE = ROOT / "runs" / "_msa" / "pxr_lbd.json"


def _client():
    """Load modal/client.py by path.

    Not `from modal.client import ...`: our directory is named `modal/`, and the
    Modal SDK is a regular package that wins that name on sys.path, so the import
    silently resolves to the SDK's own client.py.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location("pxr_cofold_client", ROOT / "modal" / "client.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_msa() -> dict | None:
    """The receptor MSA, computed once and reused by every job.

    Every target folds the *same* 293-residue receptor against a different ligand,
    so per-job MSA generation re-derives one identical alignment hundreds of times.
    Building it once takes seconds; leaving it in the loop is the largest
    avoidable cost in this stage.

    A missing cache falls back to per-job generation -- correct but slow, so it
    says so rather than quietly costing hours.
    """
    if not MSA_CACHE.exists():
        print(f"no MSA cache at {MSA_CACHE.relative_to(ROOT)} -- every job will generate its "
              "own (slow). Build it: .venv/bin/python stages/build_msa.py")
        return None
    m = json.loads(MSA_CACHE.read_text())
    if m.get("sequence") != PXR_LBD:
        raise SystemExit(
            f"{MSA_CACHE.relative_to(ROOT)} was built for a different sequence "
            f"({len(m.get('sequence', ''))} residues vs {len(PXR_LBD)}). Rebuild it -- a "
            "mismatched alignment is worse than none, because it silently misinforms "
            "every prediction instead of failing."
        )
    print(f"MSA cache: {len(m['aligned_sequences'])} rows, reused by every job")
    return {"aligned_sequences": m["aligned_sequences"], "sequence_ids": m["sequence_ids"]}


def dispatch(jobs: list[dict], plan_path: Path, *, batch: bool = True,
             scaledown: int | None = 600) -> tuple[int, int]:
    """Run every pending job: grouped by model, groups run concurrently.

    Two independent things, and both matter:

    **Grouping** keeps one model's container warm for its whole run. Alternating
    models round-robin lets each scale down between turns, so nearly every job
    pays a cold start.

    **Overlapping the groups** is the other 4x. Each model is a *separate Modal
    app* with its own container pool, so running the groups concurrently costs
    nothing in cold starts -- they do not compete for the same containers. Run
    them one after another and the wall time is the sum of the groups rather than
    the longest one, which is how a 12 s/job run still takes over an hour.
    """
    from concurrent.futures import ThreadPoolExecutor

    mod = _client()
    msa = load_msa()
    pending = [j for j in jobs if j.get("status") != "done"]
    if not pending:
        return 0, 0

    by_model: dict[str, list[dict]] = {}
    for j in pending:
        by_model.setdefault(j["model"], []).append(j)

    # One checkpoint writer, because several groups finish into the same plan.
    lock = threading.Lock()

    def checkpoint() -> None:
        with lock:
            plan_path.write_text(json.dumps(jobs, indent=2))

    def run_group(item: tuple[str, list[dict]]) -> tuple[int, int]:
        model, group = item
        return _run_model_group(mod, model, group, msa, checkpoint,
                                batch=batch, scaledown=scaledown)

    with ThreadPoolExecutor(max_workers=len(by_model)) as pool:
        results = list(pool.map(run_group, by_model.items()))
    return sum(d for d, _ in results), sum(f for _, f in results)


def _run_model_group(mod, model: str, group: list[dict], msa: dict | None,
                     checkpoint, *, batch: bool, scaledown: int | None) -> tuple[int, int]:
    """Run one model's jobs. Called concurrently, once per model."""
    n_done = n_failed = 0
    payloads = [mod.build_input(model, PXR_LBD, j["smiles"], j["seed"], msa) for j in group]
    inputs, configs = [p[0] for p in payloads], [p[1] for p in payloads]
    use_batch = batch and model != mod.AF3_MODEL
    print(f"{model}: {len(group)} jobs ({'batch fan-out' if use_batch else 'serial'})", flush=True)

    results = None
    if use_batch:
        try:
            results = mod.cofold_batch(model, inputs, configs, scaledown_window=scaledown)
        except Exception as e:
            # A whole-batch fault must not be recorded as N target failures --
            # that blames the targets for an infrastructure problem.
            print(f"  {model}: batch dispatch failed ({type(e).__name__}: {e}); serial fallback")

    if results is not None:
        for job, out in zip(group, results):
            try:
                if isinstance(out, Exception):
                    raise out
                job.update(status="done", **write_result(job, out))
                n_done += 1
            except Exception as e:
                job.update(status="failed", error=f"{type(e).__name__}: {e}")
                n_failed += 1
        checkpoint()
        print(f"  {model}: {n_done}/{len(group)} succeeded", flush=True)
        return n_done, n_failed

    for job, input_dict, config_dict in zip(group, inputs, configs):
        tag = f"  {model} {job['structure_id']} seed{job['seed']}"
        try:
            out = mod.cofold(model, input_dict, config_dict)
            job.update(status="done", **write_result(job, out))
            n_done += 1
            print(f"{tag} done", flush=True)
        except Exception as e:  # one bad target must not lose the rest of the run
            job.update(status="failed", error=f"{type(e).__name__}: {e}")
            n_failed += 1
            print(f"{tag} FAILED {type(e).__name__}: {e}", flush=True)
        checkpoint()
    return n_done, n_failed


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-id", required=True, help="names the directory under runs/")
    ap.add_argument("--models", nargs="+", default=DEFAULT_MODELS)
    ap.add_argument("--seeds", nargs="+", type=int, default=DEFAULT_SEEDS)
    ap.add_argument("--split", choices=["dev", "holdout", "all"], default="dev",
                    help="dev = phase 1 (92). Do not touch holdout until configs are frozen.")
    ap.add_argument("--limit", type=int, help="first N targets only -- for the Phase 1 vertical slice")
    ap.add_argument("--ids", nargs="+", help="explicit structure_ids -- a stratified pilot subset is "
                                             "not the head of the split, and head() would sample the "
                                             "easy end of the difficulty range")
    ap.add_argument("--plan-only", action="store_true", help="write the job plan without dispatching")
    ap.add_argument("--serial", action="store_true",
                    help="one job at a time instead of a per-model batch fan-out; much slower, "
                         "but the log names the job that failed")
    ap.add_argument("--scaledown", type=int, default=600,
                    help="seconds an idle container stays alive. Raising it trades a little "
                         "idle cost for not paying a cold start between groups")
    args = ap.parse_args()

    ligands = pd.read_csv(MANIFEST / "ligands.csv")
    if args.split != "all":
        ligands = ligands[ligands.split == args.split]
    if args.ids:
        want = set(args.ids)
        ligands = ligands[ligands.structure_id.isin(want)]
        if missing := want - set(ligands.structure_id):
            print(f"unknown structure_ids for split {args.split!r}: {sorted(missing)}")
            return 1
    if args.limit:
        ligands = ligands.head(args.limit)

    run_dir = RUNS / args.run_id
    jobs = build_jobs(ligands, args.models, args.seeds, run_dir)

    plan_path = run_dir / "jobs.json"
    plan_path.parent.mkdir(parents=True, exist_ok=True)

    # Merge onto any existing plan instead of overwriting it. Rebuilding from
    # scratch marks every job pending again, so the resume check in dispatch()
    # never fires and a re-run silently repeats work already paid for -- which is
    # exactly what you do after an interrupted run.
    if plan_path.exists():
        prior = {
            (j["structure_id"], j["model"], j["seed"]): j
            for j in json.loads(plan_path.read_text())
        }
        resumed = 0
        for i, job in enumerate(jobs):
            old = prior.get((job["structure_id"], job["model"], job["seed"]))
            if old and old.get("status") == "done":
                jobs[i] = old
                resumed += 1
        if resumed:
            print(f"resuming: {resumed} of {len(jobs)} already done, will not be re-run")

    plan_path.write_text(json.dumps(jobs, indent=2))

    print(f"{len(ligands)} targets x {len(args.models)} models x {len(args.seeds)} seeds = {len(jobs)} jobs")
    print(f"plan: {plan_path.relative_to(ROOT)}")

    if args.plan_only:
        return 0

    n_done, n_failed = dispatch(jobs, plan_path, batch=not args.serial, scaledown=args.scaledown)
    print(f"\n{n_done} succeeded, {n_failed} failed of {len(jobs)}")
    return 1 if n_failed else 0


if __name__ == "__main__":
    sys.exit(main())
