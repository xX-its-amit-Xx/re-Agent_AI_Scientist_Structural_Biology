"""Scaffold a Model Report skeleton for a stage to fill in.

The skeleton is deliberately *invalid until edited*: placeholder text sits in the
required fields and the limitations list carries a single entry saying the report is
unfinished. A scaffold that validated straight out of the box would let a stage ship
an empty report by accident, which is the failure this whole contract exists to
prevent.
"""

from __future__ import annotations

from pathlib import Path

from reagent.contracts import (
    AgentIdentity,
    Handoff,
    ModelReport,
    ProblemSpec,
    Stage,
)
from reagent.contracts.viz import EXPECTED_VIZ

#: The stage each stage hands off to by default.
NEXT_STAGE = {
    Stage.SCOUTING: Stage.LITERATURE,
    Stage.LITERATURE: Stage.BIOCHEM,
    Stage.BIOCHEM: Stage.PRIOR,
    Stage.PRIOR: Stage.OPTIMIZATION,
    Stage.OPTIMIZATION: Stage.SYNTHESIS,
    Stage.SYNTHESIS: Stage.SYNTHESIS,
}


def new_report(
    stage: Stage,
    run_id: str,
    *,
    title: str | None = None,
    owner: str | None = None,
    model: str = "claude-fable-5",
    spec: ProblemSpec | None = None,
) -> ModelReport:
    """Build an unfinished report skeleton with the stage's obligations spelled out."""
    expected = [k.value for k in EXPECTED_VIZ.get(stage.value, [])]
    target = spec.primary_target.label if spec else "the target"

    return ModelReport(
        report_id=f"{stage.value}-{run_id}",
        run_id=run_id,
        stage=stage,
        title=title or f"{stage.value} for {target}",
        produced_by=AgentIdentity(model=model, human_owner=owner),
        objective="TODO: what was this stage asked to do? One or two sentences.",
        executive_summary=(
            "TODO: what a reader needs if they read nothing else. Lead with the "
            "outcome, not the method. This report is a scaffold and is not yet valid."
        ),
        handoff=Handoff(
            to_stage=NEXT_STAGE[stage],
            ready=False,
            payload={},
            recommended_actions=[],
            blocking_unknowns=["TODO: this report is a scaffold; nothing here is real yet."],
        ),
        limitations=[
            "TODO: this is an unedited scaffold. Replace every TODO before handing off.",
            f"TODO: this stage is expected to produce these figures: {expected or 'none declared'}.",
        ],
        open_questions=[
            "TODO: what does the evidence not settle? These feed the next scouting pass."
        ],
    )


def write_scaffold(
    stage: Stage,
    run_id: str,
    out_dir: Path | None = None,
    **kwargs,
) -> Path:
    """Write the skeleton to the conventional path and return it."""
    report = new_report(stage, run_id, **kwargs)
    out = Path(out_dir or Path("reports") / run_id / stage.value) / "report.json"
    return report.write(out)
