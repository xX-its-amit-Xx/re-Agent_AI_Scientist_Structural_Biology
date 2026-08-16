"""Visualization contract — every stage must *show* its result, not just assert it.

Most AI pipelines emit prose and a number. A reader then has to trust the
number, because nothing about it is inspectable. The fix is structural rather
than cosmetic: make a visualization a **required, typed, validated field of the
Model Report**, on the same footing as a Finding.

Three fields do the real work here:

``question``
    What a reader can answer by looking at this, phrased as a question. A chart
    that cannot state its question is decoration, and the validator rejects it.
    This is the single most effective guard against dashboard-filler.

``encoding``
    The visual grammar, made explicit: which data channel drives which visual
    channel (``{"node_color": "node.type", "edge_width": "attrs.tm_score"}``).
    Writing it down means a reader can verify the picture matches the data, and
    it lets us lint for the classic sins — colour carrying two meanings, weight
    encoding an unnormalised score, more categories than a palette can hold.

``reads_from``
    The exact artifacts the picture was drawn from, so any figure can be
    regenerated or challenged. A figure with no data provenance is an assertion.

Everything renders to a self-contained HTML file or a static image, because the
publish target blocks external hosts.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

#: Above this many categories, colour alone stops being discriminable and must be
#: paired with a second channel (dash pattern, marker shape) or grouped.
MAX_CATEGORICAL_COLORS = 8


class VizKind(str, Enum):
    # graph / network
    KG_SUBGRAPH = "kg_subgraph"          # ego network around a focal node
    KG_OVERVIEW = "kg_overview"          # whole-graph structure, clustered
    # molecular
    STRUCTURE_3D = "structure_3d"        # interactive 3D viewer
    STRUCTURE_RENDER = "structure_render"  # ray-traced still (ChimeraX/PyMOL)
    INTERACTION_2D = "interaction_2d"    # PLIP / LigPlot-style contact diagram
    INTERACTION_3D = "interaction_3d"    # two parts side by side, contacts by kind
    POCKET_SURFACE = "pocket_surface"    # pocket volume / lipophilicity surface
    ENSEMBLE_OVERLAY = "ensemble_overlay"  # N poses or N models superposed
    # quantitative
    HEATMAP = "heatmap"                  # e.g. residue x ligand x interaction type
    SCATTER = "scatter"                  # e.g. confidence vs accuracy
    DISTRIBUTION = "distribution"
    RANKED_BAR = "ranked_bar"
    TRAJECTORY = "trajectory"            # a quantity over time / over MD frames
    PARALLEL_COORDS = "parallel_coords"  # multi-metric model comparison
    # reasoning
    DECISION_TREE = "decision_tree"      # the pipeline-space branch we are on
    PROVENANCE_CHAIN = "provenance_chain"  # claim -> evidence -> source
    TABLE = "table"


class VizMedium(str, Enum):
    HTML_SELF_CONTAINED = "html_self_contained"  # inlined JS+data, no network
    SVG = "svg"
    PNG = "png"
    MERMAID = "mermaid"                          # fenced block, renders natively
    MARKDOWN_TABLE = "markdown_table"


class ColorMap(BaseModel):
    """An explicit, reviewable legend. Never let a renderer pick colours silently."""

    channel: str = Field(..., description="Visual channel, e.g. 'node_fill', 'edge_stroke'.")
    data_field: str = Field(..., description="Data field driving it, e.g. 'node.type'.")
    scale_type: Literal["categorical", "sequential", "diverging", "binary"]
    mapping: dict[str, str] = Field(
        default_factory=dict, description="category -> colour, for categorical scales."
    )
    domain: tuple[float, float] | None = Field(
        default=None, description="For continuous scales — state it so the scale is auditable."
    )
    secondary_channel: str | None = Field(
        default=None,
        description=(
            "A redundant encoding paired with colour (dash pattern, shape). Required "
            "when a categorical scale exceeds MAX_CATEGORICAL_COLORS or the figure "
            "must survive colour-blind readers."
        ),
    )

    @model_validator(mode="after")
    def _too_many_colors(self) -> ColorMap:
        if (
            self.scale_type == "categorical"
            and len(self.mapping) > MAX_CATEGORICAL_COLORS
            and not self.secondary_channel
        ):
            raise ValueError(
                f"{self.channel} maps {len(self.mapping)} categories to colour alone; "
                f"beyond ~{MAX_CATEGORICAL_COLORS} categories colour is not discriminable. "
                "Either group the categories into families or add a secondary_channel "
                "(dash pattern / shape) so the encoding is redundant."
            )
        return self


class Visualization(BaseModel):
    """One figure, with its question, its grammar, and its provenance."""

    id: str = Field(..., description="Stable within a report, e.g. 'V-KG-01'.")
    kind: VizKind
    medium: VizMedium
    title: str
    question: str = Field(
        ...,
        min_length=15,
        description=(
            "The question a reader answers by looking at this, ending in '?'. If you "
            "cannot write one, delete the figure."
        ),
    )
    takeaway: str = Field(
        ...,
        min_length=15,
        description="What the figure actually shows — the answer, stated plainly.",
    )
    path: str = Field(..., description="Repo-relative output path.")
    reads_from: list[str] = Field(
        ...,
        min_length=1,
        description="Repo-relative data artifacts this was drawn from.",
    )
    encoding: dict[str, str] = Field(
        default_factory=dict,
        description="visual channel -> data field, e.g. {'edge_width': 'attrs.tm_score'}.",
    )
    color_maps: list[ColorMap] = Field(default_factory=list)
    interactive: bool = False
    alt_text: str = Field(
        ...,
        min_length=20,
        description="Describes the content for a reader who cannot see it. Not the title again.",
    )
    covers_metrics: list[str] = Field(
        default_factory=list,
        description=(
            "Keys from the report's `metrics` that a reader can read off this figure. "
            "Declared rather than inferred: guessing from the caption text produces "
            "both false positives and false negatives, and this is the field that "
            "decides whether `--strict` considers a headline number visible."
        ),
    )
    focal_node: str | None = Field(
        default=None, description="For ego-network views: the centre, e.g. 'uniprot:O75469'."
    )
    n_elements: int | None = Field(
        default=None, description="Nodes+edges, or points. Used to lint for overplotting."
    )
    params: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _sanity(self) -> Visualization:
        if not self.question.rstrip().endswith("?"):
            raise ValueError(
                f"visualization {self.id}: `question` must be phrased as a question — "
                "it is the test of whether the figure earns its place"
            )
        if self.question.strip().lower() == self.takeaway.strip().lower():
            raise ValueError(
                f"visualization {self.id}: `takeaway` restates `question`; say what the "
                "figure shows, not what it asks"
            )
        # An ego view without a centre is just a network dump.
        if self.kind is VizKind.KG_SUBGRAPH and not self.focal_node:
            raise ValueError(
                f"visualization {self.id}: a kg_subgraph must name its focal_node"
            )
        # Overplotting guard: past a few thousand marks, a scatter/network needs
        # aggregation, not more ink.
        if self.n_elements and self.n_elements > 5000 and not (
            self.params.get("clustered")
            or self.params.get("aggregated")
            or self.params.get("filtered")
        ):
            raise ValueError(
                f"visualization {self.id} draws {self.n_elements} elements with no "
                "clustering/aggregation/filtering declared in params — it will read as a "
                "hairball. Collapse communities or filter by weight first."
            )
        return self


class VizBundle(BaseModel):
    """The figures for one stage, plus the narrative order to read them in."""

    stage: str
    visualizations: list[Visualization] = Field(default_factory=list)
    reading_order: list[str] = Field(
        default_factory=list,
        description="Viz ids in the order that tells the story. Empty means declaration order.",
    )

    @model_validator(mode="after")
    def _order_resolves(self) -> VizBundle:
        known = {v.id for v in self.visualizations}
        unknown = [i for i in self.reading_order if i not in known]
        if unknown:
            raise ValueError(f"reading_order references unknown visualization ids: {unknown}")
        return self

    def ordered(self) -> list[Visualization]:
        if not self.reading_order:
            return self.visualizations
        by_id = {v.id: v for v in self.visualizations}
        rest = [v for v in self.visualizations if v.id not in set(self.reading_order)]
        return [by_id[i] for i in self.reading_order] + rest


#: What each stage is expected to show. The orchestrator warns when a stage's
#: report is missing its characteristic figures — this is the "every step gives
#: the user insight into what is happening under the hood" requirement, encoded.
EXPECTED_VIZ: dict[str, list[VizKind]] = {
    "stage0_scouting": [VizKind.DECISION_TREE, VizKind.RANKED_BAR],
    "stage1_literature": [VizKind.KG_SUBGRAPH, VizKind.HEATMAP, VizKind.PROVENANCE_CHAIN],
    # INTERACTION_3D is required rather than optional: Stage 2 exists to show which piece
    # touches which, and a heatmap of contacts is a summary of a thing the reader has
    # never seen. The side-by-side part view is the thing itself.
    "stage2_biochem": [VizKind.INTERACTION_2D, VizKind.INTERACTION_3D,
                      VizKind.STRUCTURE_RENDER, VizKind.HEATMAP],
    "stage3_prior": [VizKind.ENSEMBLE_OVERLAY, VizKind.SCATTER, VizKind.PARALLEL_COORDS],
    "stage4_optimization": [VizKind.STRUCTURE_3D, VizKind.SCATTER, VizKind.RANKED_BAR],
    "synthesis": [VizKind.DECISION_TREE, VizKind.PROVENANCE_CHAIN],
}


def missing_expected(stage: str, bundle: VizBundle) -> list[VizKind]:
    """Which characteristic figures a stage did not produce. Advisory, not fatal."""
    present = {v.kind for v in bundle.visualizations}
    return [k for k in EXPECTED_VIZ.get(stage, []) if k not in present]
