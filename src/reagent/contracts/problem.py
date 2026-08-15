"""ProblemSpec — the one object that makes the whole pipeline target-agnostic.

Nothing downstream may hardcode a target, an organism, a domain, or a notion of
similarity. All of it arrives here and is threaded through. PXR is *an instance*
of a ProblemSpec, not a special case in the code; so is a DEL-ML hit-finding
challenge, an ADMET regression, or a binder-design task.

The design pressure this resolves
---------------------------------
Stage 1's brief is "find things similar to the target". But *similar* means
completely different things per domain:

    protein structure target -> fold, motif, pocket, promiscuity, family
    DNA-encoded library task -> scaffold, library topology, target class, assay
    ADMET regression         -> chemical series, physicochemical space, endpoint
    binder design            -> epitope, framework, developability

So similarity is not hardcoded either. It is a list of ``AxisSpec`` — declarative
descriptions of the neighbourhoods to build — supplied by a domain profile in
``reagent.domains``. Adding a new problem domain means registering a profile, not
editing Stage 1.

Read ``AXIS_REGISTRY_NOTE`` at the bottom before adding an axis.
"""

from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class Domain(str, Enum):
    """The problem domain. Extend freely — this is not a closed world."""

    STRUCTURAL_BIOLOGY = "structural_biology"   # co-folding, docking, pose prediction
    DEL_ML = "del_ml"                           # DNA-encoded library machine learning
    ADMET = "admet"                             # property / liability prediction
    PROTEIN_DESIGN = "protein_design"           # binders, enzymes, scaffolds
    CHEMINFORMATICS = "cheminformatics"         # QSAR, virtual screening
    GENOMICS = "genomics"
    OTHER = "other"


class TaskType(str, Enum):
    """What is actually being predicted. Drives metric choice and pipeline shape."""

    COMPLEX_PREDICTION = "complex_prediction"       # 3D protein-ligand complex
    STRUCTURE_PREDICTION = "structure_prediction"   # apo/holo fold
    POSE_SELECTION = "pose_selection"               # rank an existing pool
    AFFINITY_RANKING = "affinity_ranking"
    PROPERTY_REGRESSION = "property_regression"
    CLASSIFICATION = "classification"
    HIT_IDENTIFICATION = "hit_identification"       # find actives in a large library
    GENERATIVE_DESIGN = "generative_design"
    OTHER = "other"


class MetricDirection(str, Enum):
    MAXIMIZE = "maximize"
    MINIMIZE = "minimize"


class TargetEntity(BaseModel):
    """Whatever the pipeline is *about*. Deliberately loose.

    A protein target, a target class, a library, an endpoint, a cell line. The
    only hard requirement is a namespaced ``id`` so the knowledge graph can key
    on it, matching ``reagent.contracts.kg.Node`` conventions.
    """

    id: str = Field(
        ...,
        description=(
            "Namespaced id, e.g. 'uniprot:O75469' (PXR), 'uniprot:Q9Y5Y4' , "
            "'family:NR1I', 'chembl:CHEMBL240', 'endpoint:hERG-IC50', "
            "'library:DEL-triazine-3cycle'."
        ),
    )
    kind: Literal[
        "protein", "protein_family", "complex", "compound", "compound_library",
        "endpoint", "cell_line", "organism", "other",
    ]
    label: str
    # Optional and only meaningful for some kinds. Never assume these exist.
    sequence: str | None = None
    organism: str | None = None
    aliases: list[str] = Field(default_factory=list)
    known_structures: list[str] = Field(
        default_factory=list, description="e.g. ['pdb:1M13'] — may be empty."
    )
    attrs: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _namespaced(self) -> TargetEntity:
        if ":" not in self.id:
            raise ValueError(
                f"target id {self.id!r} must be namespaced '<ns>:<accession>' to key the graph"
            )
        return self


class AxisSpec(BaseModel):
    """One declarative "what counts as similar" axis for Stage 1 to populate.

    An axis is a *question plus the machinery to answer it*, not a hardcoded
    method. Stage 1 reads these and dispatches; a domain profile supplies them.
    """

    name: str = Field(..., description="Short slug, e.g. 'fold', 'motif', 'promiscuity'.")
    question: str = Field(
        ..., min_length=15, description="The neighbourhood question, in plain language."
    )
    predicate: str = Field(
        ...,
        description=(
            "The kg Predicate this axis writes, e.g. 'SIMILAR_FOLD_TO'. Must exist in "
            "reagent.contracts.kg.Predicate."
        ),
    )
    score_key: str = Field(
        ...,
        description="Edge attr holding this axis's similarity score, e.g. 'tm_score'.",
    )
    score_range: tuple[float, float] = Field(
        default=(0.0, 1.0),
        description="So the renderer can normalise edge weights across axes honestly.",
    )
    methods: list[str] = Field(
        default_factory=list,
        description="Candidate tools, in preference order, e.g. ['foldseek', 'tmalign'].",
    )
    required: bool = Field(
        default=True, description="False for axes that are nice-to-have for this problem."
    )
    notes: str | None = None


class Metric(BaseModel):
    """The scoring function. Get this wrong and every stage optimises the wrong thing."""

    name: str = Field(..., description="e.g. 'LDDT-PLI', 'Spearman rho', 'PR-AUC'.")
    direction: MetricDirection = MetricDirection.MAXIMIZE
    definition: str = Field(
        ..., min_length=20, description="How it is computed, precisely enough to reimplement."
    )
    eval_set: str | None = Field(
        default=None, description="What it is computed over. A metric without this is uncomparable."
    )
    known_caveats: list[str] = Field(
        default_factory=list,
        description=(
            "Ways this metric misleads. Populate from Stage 0 scouting — e.g. a "
            "secondary metric that is statistically decoupled from the primary one."
        ),
    )
    proxy_metrics: list[str] = Field(
        default_factory=list, description="Local stand-ins usable before the real score arrives."
    )


class Budget(BaseModel):
    """Hard limits. The orchestrator refuses to exceed these."""

    deadline_utc: str | None = None
    max_submissions: int | None = None
    submission_cooldown_hours: float | None = None
    max_cost_usd: float | None = None
    credit_pools: list[str] = Field(
        default_factory=list, description="e.g. ['boltz', 'modal', 'tamarind', 'anthropic']."
    )
    compute: list[str] = Field(
        default_factory=list, description="e.g. ['slurm:explorer', 'modal', 'colab']."
    )


class ProblemSpec(BaseModel):
    """The complete parameterisation of one pipeline-design run.

    Written once at the start (by hand or by the `ai-scientist` skill reading a
    brief) and then read by every stage. If a stage needs to know something about
    the problem, it belongs here — not in that stage's code.
    """

    spec_version: str = "1.0.0"
    run_id: str
    name: str = Field(..., description="Human name for this challenge/problem.")
    domain: Domain
    task_type: TaskType

    targets: list[TargetEntity] = Field(
        ..., min_length=1, description="Usually one, but co-targets and panels are allowed."
    )
    test_items: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "What we must produce predictions for: {'n': 184, 'kind': 'compound', "
            "'manifest': 'data/test.csv', 'subpopulations': {...}}. Stage 0 should "
            "characterise subpopulations — a prior that helps one can hurt another."
        ),
    )
    metric: Metric
    axes: list[AxisSpec] = Field(
        default_factory=list,
        description="Similarity axes for Stage 1. Populate from a domain profile.",
    )
    budget: Budget = Field(default_factory=Budget)

    output_contract: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Mechanical submission requirements — file format, naming, validators. "
            "These have decided real leaderboards; treat as FindingKind.CONSTRAINT."
        ),
    )
    withheld: list[str] = Field(
        default_factory=list,
        description="What we do NOT get. Determines whether templating/training is legal.",
    )
    notes: str | None = None

    @model_validator(mode="after")
    def _axes_are_known_predicates(self) -> ProblemSpec:
        # Imported lazily to keep this module free of graph dependencies at import time.
        from .kg import Predicate

        valid = {p.value for p in Predicate}
        bad = [a.predicate for a in self.axes if a.predicate not in valid]
        if bad:
            raise ValueError(
                f"axes reference predicates absent from kg.Predicate: {bad}. "
                "Add them to the controlled vocabulary first — an unregistered predicate "
                "cannot be queried by a downstream stage."
            )
        dupes = {a.name for a in self.axes if [x.name for x in self.axes].count(a.name) > 1}
        if dupes:
            raise ValueError(f"duplicate axis names: {sorted(dupes)}")
        return self

    @property
    def primary_target(self) -> TargetEntity:
        return self.targets[0]

    def required_axes(self) -> list[AxisSpec]:
        return [a for a in self.axes if a.required]

    def axis(self, name: str) -> AxisSpec:
        for a in self.axes:
            if a.name == name:
                return a
        raise KeyError(f"no axis named {name!r}; have {[a.name for a in self.axes]}")

    def write(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2, exclude_none=True) + "\n", encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: Path) -> ProblemSpec:
        return cls.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))


AXIS_REGISTRY_NOTE = """
Adding a similarity axis
------------------------
1. Make sure the predicate exists in `reagent.contracts.kg.Predicate`. If it does
   not, add it there *and* to `PREDICATE_DOMAINS`, because an unregistered
   predicate is invisible to the query layer and to the graph renderer.
2. Add the AxisSpec to the relevant profile in `reagent.domains`, not to Stage 1.
3. Give it an honest `score_range`. The graph renderer normalises edge width
   across axes, so a score on a different scale will silently misrepresent
   strength relative to the other axes — the most likely way this system lies to
   a reader.
4. If the axis has a limited domain of validity (e.g. a similarity measure that
   inverts sign on a subpopulation of the test set), say so in `notes`. Stage 1
   is required to propagate that into the prior it hands Stage 3.
"""
