#!/usr/bin/env python
"""Repoint proto-tools' default GPU profile at the tiers this account can schedule.

Why this exists: Modal gates its premium GPU tiers behind a payment method, and
this workspace has none. Probing every tier gave a clean boundary --

    allowed   T4 (15 GB)   L4 (23 GB)   A10 (23 GB)
    refused   L40S   A100-40GB   A100-80GB   H100   ("Please add a payment
              method to use <TIER> GPU functions.")

proto-tools hardcodes ``GPU_DEFAULT = ["H100:1", "H200:1", "A100-80GB:1"]`` in
``proto_tools/modal/gpu_profiles.py`` and every cofold service imports that
constant, so all four (boltz2, chai1, protenix, rf3) fail to deploy. There is no
env-var override, and rewriting four service files into this repo to change one
list would be worse than changing the list.

So this patches the constant in place -- but as versioned, idempotent, reversible
code rather than an invisible hand-edit, because the change lives in an installed
package and **will be lost on the next `proto-tools` upgrade**. Re-run it after
any upgrade.

    .venv/bin/python modal/patch_gpu_profile.py          # apply
    .venv/bin/python modal/patch_gpu_profile.py --revert # restore
    .venv/bin/python modal/patch_gpu_profile.py --check  # report only

A10 and L4 are both 23 GB. T4 is deliberately excluded: at 15 GB it is the tier
most likely to OOM partway through a cofold, and a job that dies at minute 20
costs more than one that waits for a bigger card.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ORIGINAL = '["H100:1", "H200:1", "A100-80GB:1"]'
PATCHED = '["A10:1", "L4:1"]'
MARKER = "# patched by modal/patch_gpu_profile.py"


def find_targets() -> list[Path]:
    """Every installed proto_tools whose gpu_profiles.py we might need to patch.

    There are normally two: the `uv tool` install behind the `proto-tools` CLI
    (used by `proto-tools deploy`) and the copy in this repo's .venv (used by
    `modal deploy`). Both must agree or the two deploy paths disagree on GPU.
    """
    roots = [
        Path.home() / ".local/share/uv/tools/proto-tools/lib",
        Path(__file__).resolve().parents[1] / ".venv/lib",
    ]
    found = []
    for root in roots:
        found.extend(root.glob("python3.*/site-packages/proto_tools/modal/gpu_profiles.py"))
    return found


def apply(path: Path, revert: bool = False) -> str:
    text = path.read_text()
    backup = path.with_suffix(".py.orig")

    if revert:
        if backup.exists():
            shutil.copy2(backup, path)
            backup.unlink()
            return "reverted"
        return "no backup — nothing to revert"

    if MARKER in text:
        return "already patched"
    if ORIGINAL not in text:
        return f"SKIP — expected default not found (upstream changed?): {ORIGINAL}"

    if not backup.exists():
        shutil.copy2(path, backup)
    path.write_text(
        text.replace(
            f"GPU_DEFAULT: Final[list[str]] = {ORIGINAL}",
            f"GPU_DEFAULT: Final[list[str]] = {PATCHED}  {MARKER}",
        )
    )
    return "patched"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--revert", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    targets = find_targets()
    if not targets:
        print("no installed proto_tools/modal/gpu_profiles.py found")
        return 1

    for path in targets:
        if args.check:
            state = "patched" if MARKER in path.read_text() else "original"
            print(f"  [{state}] {path}")
            continue
        print(f"  [{apply(path, revert=args.revert)}] {path}")

    if not args.check:
        print(f"\nGPU_DEFAULT -> {PATCHED if not args.revert else ORIGINAL}")
        print("Re-run after any `proto-tools` upgrade; installed-package edits do not survive one.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
