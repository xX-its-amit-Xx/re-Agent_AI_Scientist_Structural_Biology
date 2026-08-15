"""Domain profiles — pluggable definitions of "what counts as similar".

This module is the extension point that keeps the meta-pipeline target- and
domain-agnostic. A profile supplies the ``AxisSpec`` list for a ``ProblemSpec``,
so Stage 1 dispatches over declared axes instead of containing per-domain
branches. Adding a new problem type is a matter of registering a profile here;
no stage code changes.

    from reagent.domains import profile_for
    spec.axes = profile_for(Domain.DEL_ML, TaskType.HIT_IDENTIFICATION)

Profiles are **defaults, not law.** The `ai-scientist` skill is expected to prune
or extend the axis list for a specific problem — e.g. dropping the fold axis when
no experimental structure of the target exists, or adding an axis that Stage 0
scouting discovered mattered for this challenge.
"""

from __future__ import annotations

from reagent.contracts import AxisSpec, Domain, TaskType

# --------------------------------------------------------------------------
# Structural biology — protein/complex targets
# --------------------------------------------------------------------------

STRUCTURAL_BIOLOGY_AXES: list[AxisSpec] = [
    AxisSpec(
        name="sequence",
        question="Which proteins are related to the target by primary sequence?",
        predicate="SIMILAR_SEQUENCE_TO",
        score_key="identity",
        score_range=(0.0, 1.0),
        methods=["blast", "mmseqs2", "jackhmmer"],
        notes=(
            "Cheap and reliable, but sequence identity is a weak predictor of pocket "
            "similarity for promiscuous targets. Do not let it dominate the ranking."
        ),
    ),
    AxisSpec(
        name="fold",
        question="Which proteins share the target's three-dimensional fold?",
        predicate="SIMILAR_FOLD_TO",
        score_key="tm_score",
        score_range=(0.0, 1.0),
        methods=["foldseek", "tmalign", "dali", "us-align"],
        notes=(
            "Requires a structure for the target — experimental or predicted. If only a "
            "prediction is available, record its confidence, because fold-similarity "
            "scores inherit the model's error."
        ),
    ),
    AxisSpec(
        name="pocket",
        question="Which proteins have a binding pocket geometrically like the target's?",
        predicate="SIMILAR_POCKET_TO",
        score_key="score",
        score_range=(0.0, 1.0),
        methods=["fpocket+comparison", "prank", "sitehound", "probis", "apoc"],
        notes=(
            "Often more predictive than fold for ligand-transfer questions, and more "
            "fragile. Pocket definition is a free parameter — record it."
        ),
    ),
    AxisSpec(
        name="motif",
        question="Which proteins share a local structural or learned-feature motif with the target?",
        predicate="SHARES_MOTIF",
        score_key="score",
        score_range=(0.0, 1.0),
        methods=["esmc-sae", "prosite", "interpro", "3d-motif-search", "pyscomotif"],
        notes=(
            "The axis with the most upside and the least established practice. Sparse "
            "autoencoder features over a protein language model can surface motifs no "
            "sequence or fold method finds, but a feature is only evidence once it has "
            "been given a structural interpretation — see the esmc-sae-motifs skill."
        ),
    ),
    AxisSpec(
        name="promiscuity",
        question="Which proteins bind a comparably broad and chemically diverse ligand set?",
        predicate="PROMISCUOUS_WITH",
        score_key="breadth_score",
        score_range=(0.0, 1.0),
        methods=["pdb-ligand-census", "chembl-breadth", "bindingdb"],
        notes=(
            "Operationalise as measured breadth of BINDS — distinct chemotypes, not a "
            "literature adjective. Promiscuous proteins outside the target's family are "
            "often the most useful transfer sources, because they share the *problem* "
            "(a large adaptable pocket) without sharing the fold. "
            "IMPORTANT: every listed method yields an UNBOUNDED count, but this axis "
            "declares a 0-1 range, so you must apply and record a normalisation. Use "
            "either rank-percentile within the candidate set, or "
            "log1p(n_chemotypes)/log1p(max_in_set); put which one in the edge attrs as "
            "`breadth_transform`. Two runs using different transforms produce "
            "incomparable graphs."
        ),
    ),
    AxisSpec(
        name="family",
        question="Which proteins are in the target's family or superfamily?",
        predicate="MEMBER_OF_FAMILY",
        # Family membership is categorical, not graded. There is no honest similarity
        # score here, so the axis declares `membership` (1.0 = asserted member) and the
        # renderer draws every family edge at the same width — which is correct, since
        # varying the width would imply a gradation that does not exist.
        score_key="membership",
        score_range=(0.0, 1.0),
        methods=["pfam", "interpro", "uniprot-family", "rcsb-search"],
        notes=(
            "The most reliable axis and the least surprising. Its value is coverage: it "
            "defines the corpus a downstream fine-tune is weighted over. "
            "Membership is categorical — set `membership: 1.0` and put the real "
            "confidence in the edge's `confidence` field, not in the score. "
            "NOTE ON THE CORPUS: MEMBER_OF_FAMILY connects Protein to Family, so it "
            "cannot itself carry a corpus of *structure* entries. The structure corpus "
            "rides on HAS_STRUCTURE and CO_CRYSTALLIZED_WITH edges from the family's "
            "member proteins; this axis identifies the members."
        ),
    ),
    AxisSpec(
        name="compound",
        question="Which known compounds resemble the test compounds we must predict for?",
        predicate="SIMILAR_COMPOUND_TO",
        score_key="tanimoto",
        score_range=(0.0, 1.0),
        methods=["rdkit-morgan", "rdkit-scaffold", "mces", "shape-tanimoto"],
        notes=(
            "Run this on the *test* compounds, not only the target's known ligands. The "
            "gap between them is the domain shift the whole pipeline must survive, and "
            "measuring it early is the highest-value thing Stage 1 does."
        ),
    ),
]

# --------------------------------------------------------------------------
# DNA-encoded library machine learning
# --------------------------------------------------------------------------

DEL_ML_AXES: list[AxisSpec] = [
    AxisSpec(
        name="scaffold",
        question="Which library members share the core scaffold of the hits?",
        predicate="SHARES_SCAFFOLD",
        score_key="scaffold_tanimoto",
        score_range=(0.0, 1.0),
        methods=["rdkit-murcko", "generic-scaffold", "rdkit-morgan"],
    ),
    AxisSpec(
        name="building_block",
        question="Which library members share building blocks at each synthetic cycle?",
        predicate="HAS_FRAGMENT",
        score_key="cycle_overlap",
        score_range=(0.0, 1.0),
        methods=["cycle-decomposition", "bb-enumeration"],
        notes=(
            "DEL-specific and load-bearing: enrichment is frequently a building-block "
            "effect rather than a whole-molecule effect, and a model that ignores cycle "
            "structure will learn synthesis artefacts instead of binding."
        ),
    ),
    AxisSpec(
        name="target_class",
        question="Which other targets are in the same class as this selection's target?",
        predicate="MEMBER_OF_FAMILY",
        score_key="membership",
        score_range=(0.0, 1.0),
        methods=["chembl-target-class", "pfam", "uniprot-family"],
    ),
    AxisSpec(
        name="selection_condition",
        question="Which published selections used a comparable assay and condition set?",
        predicate="SIMILAR_ASSAY_TO",
        score_key="condition_overlap",
        score_range=(0.0, 1.0),
        methods=["literature-harvest", "chembl-assay"],
        notes=(
            "Matrix/no-target control design, wash stringency, and sequencing depth "
            "dominate DEL signal quality. Two selections on the same target with "
            "different conditions are not comparable data."
        ),
    ),
    AxisSpec(
        name="compound",
        question="Which known actives outside the library resemble the enriched members?",
        predicate="SIMILAR_COMPOUND_TO",
        score_key="tanimoto",
        score_range=(0.0, 1.0),
        methods=["rdkit-morgan", "chembl-similarity"],
        required=False,
    ),
]

# --------------------------------------------------------------------------
# ADMET / property prediction
# --------------------------------------------------------------------------

ADMET_AXES: list[AxisSpec] = [
    AxisSpec(
        name="chemical_series",
        question="Which compounds are in the same chemical series as our query set?",
        predicate="SIMILAR_COMPOUND_TO",
        score_key="tanimoto",
        score_range=(0.0, 1.0),
        methods=["rdkit-morgan", "mces", "matched-molecular-pairs"],
    ),
    AxisSpec(
        name="scaffold",
        question="Which scaffolds does the training data cover, and does our query set fall inside?",
        predicate="SHARES_SCAFFOLD",
        score_key="scaffold_tanimoto",
        score_range=(0.0, 1.0),
        methods=["rdkit-murcko"],
        notes="Scaffold split is the honest evaluation; random split flatters every model.",
    ),
    AxisSpec(
        name="mechanism",
        question="Which proteins mediate this endpoint, and what is known about their ligands?",
        predicate="MODULATES",
        score_key="confidence_numeric",
        score_range=(0.0, 1.0),
        methods=["literature-harvest", "open-targets", "chembl"],
        notes=(
            "The axis that turns a black-box regression into a mechanistic one — e.g. an "
            "induction endpoint mediated by a xenobiotic receptor lets you borrow that "
            "receptor's structural biology as a feature source."
        ),
    ),
    AxisSpec(
        name="assay",
        question="Which assays produced the training labels, and are they commensurable?",
        predicate="SIMILAR_ASSAY_TO",
        score_key="condition_overlap",
        score_range=(0.0, 1.0),
        methods=["chembl-assay", "literature-harvest"],
    ),
]

# --------------------------------------------------------------------------
# Protein design
# --------------------------------------------------------------------------

PROTEIN_DESIGN_AXES: list[AxisSpec] = [
    AxisSpec(
        name="epitope",
        question="Which known binders engage the same surface patch on the target?",
        predicate="SIMILAR_POCKET_TO",
        score_key="score",
        score_range=(0.0, 1.0),
        methods=["interface-comparison", "sabdab-epitope", "pdbe-kb"],
    ),
    AxisSpec(
        name="fold",
        question="Which scaffolds or frameworks have succeeded against similar targets?",
        predicate="SIMILAR_FOLD_TO",
        score_key="tm_score",
        score_range=(0.0, 1.0),
        methods=["foldseek", "tmalign"],
    ),
    AxisSpec(
        name="motif",
        question="Which binding motifs recur across successful binders for this target class?",
        predicate="SHARES_MOTIF",
        score_key="score",
        score_range=(0.0, 1.0),
        methods=["esmc-sae", "3d-motif-search", "interface-motif-mining"],
    ),
    AxisSpec(
        name="family",
        question="What is the target's family, and which members already have binders?",
        predicate="MEMBER_OF_FAMILY",
        score_key="membership",
        score_range=(0.0, 1.0),
        methods=["pfam", "interpro"],
    ),
]


PROFILES: dict[Domain, list[AxisSpec]] = {
    Domain.STRUCTURAL_BIOLOGY: STRUCTURAL_BIOLOGY_AXES,
    Domain.DEL_ML: DEL_ML_AXES,
    Domain.ADMET: ADMET_AXES,
    Domain.PROTEIN_DESIGN: PROTEIN_DESIGN_AXES,
    Domain.CHEMINFORMATICS: ADMET_AXES,  # same neighbourhood logic, different endpoint
}


def profile_for(domain: Domain, task_type: TaskType | None = None) -> list[AxisSpec]:
    """Default axes for a domain, deep-copied so callers can prune without side effects.

    ``task_type`` narrows the defaults where it clearly should: a pose-selection
    task already has structures and a candidate pool, so the compound-similarity
    axis stops being required.
    """
    axes = [a.model_copy(deep=True) for a in PROFILES.get(domain, [])]

    if task_type is TaskType.POSE_SELECTION:
        for a in axes:
            if a.name in {"compound", "family"}:
                a.required = False
    elif task_type is TaskType.PROPERTY_REGRESSION:
        for a in axes:
            if a.name in {"fold", "pocket"}:
                a.required = False

    if not axes:
        raise KeyError(
            f"no axis profile registered for domain {domain.value!r}. Add one to "
            "reagent.domains.PROFILES — Stage 1 dispatches over declared axes and "
            "cannot guess what similarity means in a new domain."
        )
    return axes


def registered_domains() -> list[str]:
    return sorted(d.value for d in PROFILES)
