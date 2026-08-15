"""Knowledge-graph contract.

Stage 1 writes the graph; Stages 2-4 read it. The source of truth is two
append-only JSONL files (``nodes.jsonl``, ``edges.jsonl``) because that is
git-diffable and keeps provenance attached to every assertion. A SQLite view is
built on demand for querying — see ``reagent.kg.store``.

Design note: one predicate per similarity axis
----------------------------------------------
Stage 1's brief is "what is similar to the target?" — but *similar* is
domain-specific, so the axes are supplied by a ``ProblemSpec`` (see
``reagent.contracts.problem``) and each axis gets its **own** predicate rather
than a generic ``SIMILAR_TO``. That is what lets a downstream agent ask a precise
question instead of a vague one.

For a protein-structure problem the axes typically bind to:

  * sequence / fold similarity -> SIMILAR_SEQUENCE_TO, SIMILAR_FOLD_TO
  * structural motif sharing   -> SHARES_MOTIF (3D motifs, or SAE features)
  * promiscuity                -> PROMISCUOUS_WITH, and breadth of BINDS
  * receptor / protein family  -> MEMBER_OF_FAMILY

For a DNA-encoded-library problem the same machinery binds to SHARES_SCAFFOLD,
HAS_FRAGMENT (building blocks), SIMILAR_ASSAY_TO, and MEMBER_OF_FAMILY over
target classes. **Nothing in this module is specific to any target or domain.**

The payoff: "give me templates that share the target's hydrophobic pocket but are
NOT in its receptor family" is one SQL join away, which is the whole reason to
build a graph rather than write prose.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator

from .report import Confidence, Evidence

KG_SCHEMA_VERSION = "1.0.0"


class NodeType(str, Enum):
    PROTEIN = "Protein"            # a gene product / UniProt entry
    STRUCTURE = "Structure"        # a PDB/CIF/predicted coordinate set
    POCKET = "Pocket"              # a binding site on a Structure
    RESIDUE = "Residue"            # a specific position, pocket-lining etc.
    MOTIF = "Motif"                # sequence or 3D motif, incl. SAE features
    COMPOUND = "Compound"          # small molecule
    FRAGMENT = "Fragment"          # substructure / functional group
    ASSAY = "Assay"                # a measurement context
    DATASET = "Dataset"            # a data deposit, referenced not downloaded (see contracts.data)
    PAPER = "Paper"                # literature/patent/trial/regulatory/grey source
    METHOD = "Method"              # a computational method or model
    PIPELINE_STEP = "PipelineStep"  # a stage/technique in someone's pipeline
    ANALOGY = "Analogy"            # a cross-domain mechanism card
    DOMAIN = "Domain"              # a field of study (for analogy provenance)
    FAMILY = "Family"              # protein family / receptor subfamily


class Predicate(str, Enum):
    """Controlled vocabulary. Adding one? Add it here and to PREDICATE_DOMAINS."""

    # --- similarity axes -------------------------------------------------
    SIMILAR_SEQUENCE_TO = "SIMILAR_SEQUENCE_TO"    # attrs: identity, coverage, evalue
    SIMILAR_FOLD_TO = "SIMILAR_FOLD_TO"            # attrs: tm_score, rmsd, aligned_len
    SHARES_MOTIF = "SHARES_MOTIF"                  # attrs: motif_id, sae_feature, score
    SIMILAR_POCKET_TO = "SIMILAR_POCKET_TO"        # attrs: method, score
    SIMILAR_COMPOUND_TO = "SIMILAR_COMPOUND_TO"    # attrs: tanimoto, fp_type, scaffold_match
    SHARES_SCAFFOLD = "SHARES_SCAFFOLD"            # attrs: scaffold_smiles, generic
    SIMILAR_ASSAY_TO = "SIMILAR_ASSAY_TO"          # attrs: readout, condition_overlap

    # --- composition -----------------------------------------------------
    HAS_STRUCTURE = "HAS_STRUCTURE"
    HAS_POCKET = "HAS_POCKET"
    POCKET_LINED_BY = "POCKET_LINED_BY"
    HAS_MOTIF = "HAS_MOTIF"
    HAS_FRAGMENT = "HAS_FRAGMENT"
    MEMBER_OF_FAMILY = "MEMBER_OF_FAMILY"

    # --- interaction / pharmacology --------------------------------------
    BINDS = "BINDS"                        # attrs: affinity_nm, affinity_type, assay
    CO_CRYSTALLIZED_WITH = "CO_CRYSTALLIZED_WITH"
    PROMISCUOUS_WITH = "PROMISCUOUS_WITH"  # attrs: n_distinct_ligands, breadth_score
    MODULATES = "MODULATES"                # e.g. PXR -MODULATES-> CYP3A4
    COMPETES_WITH = "COMPETES_WITH"

    # --- epistemics ------------------------------------------------------
    SUPPORTED_BY = "SUPPORTED_BY"          # any node -> Paper
    CONTRADICTED_BY = "CONTRADICTED_BY"
    MEASURED_IN = "MEASURED_IN"            # edge fact -> Assay

    # --- data availability (lazy: metadata now, bytes later) -------------
    # Stage 1 writes these so a downstream agent can ask "what data exists for
    # this compound/target pair?" and only then resolve the URL and download.
    HAS_DATA = "HAS_DATA"                  # Protein/Compound/Assay -> Dataset
    DATASET_COVERS = "DATASET_COVERS"      # Dataset -> any entity it contains
    MEASURED_BETWEEN = "MEASURED_BETWEEN"  # Assay -> the pair it measures
    DERIVED_FROM = "DERIVED_FROM"          # Dataset -> Dataset / Paper it came from

    # --- method / pipeline space (Stage 0) -------------------------------
    USED_IN = "USED_IN"                    # Method -> PipelineStep
    EVALUATED_ON = "EVALUATED_ON"          # Method -> Assay/benchmark
    OUTPERFORMS = "OUTPERFORMS"            # attrs: metric, delta
    FAILS_ON = "FAILS_ON"                  # Method -> failure mode; the honest edge
    ALTERNATIVE_TO = "ALTERNATIVE_TO"

    # --- cross-domain innovation -----------------------------------------
    ANALOGOUS_TO = "ANALOGOUS_TO"          # Analogy <-> Method/PipelineStep
    ORIGINATES_IN = "ORIGINATES_IN"        # Analogy -> Domain
    INSPIRES = "INSPIRES"                  # Analogy -> a proposed PipelineStep


#: Which node types each predicate legally connects. ``None`` means unrestricted.
PREDICATE_DOMAINS: dict[Predicate, tuple[set[NodeType] | None, set[NodeType] | None]] = {
    Predicate.SIMILAR_SEQUENCE_TO: ({NodeType.PROTEIN}, {NodeType.PROTEIN}),
    Predicate.SIMILAR_FOLD_TO: (
        {NodeType.PROTEIN, NodeType.STRUCTURE},
        {NodeType.PROTEIN, NodeType.STRUCTURE},
    ),
    Predicate.SIMILAR_POCKET_TO: ({NodeType.POCKET}, {NodeType.POCKET}),
    Predicate.SIMILAR_COMPOUND_TO: ({NodeType.COMPOUND}, {NodeType.COMPOUND}),
    Predicate.HAS_STRUCTURE: ({NodeType.PROTEIN}, {NodeType.STRUCTURE}),
    Predicate.HAS_POCKET: ({NodeType.STRUCTURE, NodeType.PROTEIN}, {NodeType.POCKET}),
    Predicate.POCKET_LINED_BY: ({NodeType.POCKET}, {NodeType.RESIDUE}),
    Predicate.MEMBER_OF_FAMILY: ({NodeType.PROTEIN}, {NodeType.FAMILY}),
    Predicate.BINDS: (
        {NodeType.PROTEIN, NodeType.POCKET},
        {NodeType.COMPOUND, NodeType.FRAGMENT},
    ),
    Predicate.PROMISCUOUS_WITH: ({NodeType.PROTEIN}, {NodeType.PROTEIN}),
    Predicate.SUPPORTED_BY: (None, {NodeType.PAPER}),
    Predicate.CONTRADICTED_BY: (None, {NodeType.PAPER}),
    Predicate.ORIGINATES_IN: ({NodeType.ANALOGY}, {NodeType.DOMAIN}),
    Predicate.ANALOGOUS_TO: (
        {NodeType.ANALOGY},
        {NodeType.METHOD, NodeType.PIPELINE_STEP},
    ),
}


PREDICATE_DOMAINS.update({
    Predicate.HAS_DATA: (None, {NodeType.DATASET}),
    Predicate.DATASET_COVERS: ({NodeType.DATASET}, None),
    Predicate.DERIVED_FROM: ({NodeType.DATASET}, {NodeType.DATASET, NodeType.PAPER}),
    Predicate.SHARES_SCAFFOLD: (
        {NodeType.COMPOUND, NodeType.FRAGMENT},
        {NodeType.COMPOUND, NodeType.FRAGMENT},
    ),
    Predicate.HAS_FRAGMENT: (
        {NodeType.COMPOUND},
        {NodeType.FRAGMENT, NodeType.MOTIF},
    ),
})


class PredicateFamily(str, Enum):
    """Semantic grouping of predicates, used purely for visual encoding.

    Why this exists: the vocabulary has ~27 predicates, and no human can
    distinguish 27 categorical colours — the practical ceiling for a
    colour-blind-safe categorical palette is about 8. So **colour encodes the
    family** and a **dash pattern distinguishes predicates within a family**,
    with the exact predicate available on hover. Eight families, eight colours.
    """

    STRUCTURAL = "structural"      # 3D similarity
    SEQUENCE = "sequence"          # primary-sequence relatedness
    CHEMICAL = "chemical"          # small-molecule similarity
    COMPOSITION = "composition"    # part-of / member-of scaffolding
    INTERACTION = "interaction"    # binding and pharmacology
    DATA = "data"                  # where measurements live (lazy dataset pointers)
    EVIDENCE = "evidence"          # epistemic links to sources
    METHOD = "method"              # pipeline-space relations
    ANALOGY = "analogy"            # cross-domain transfer


PREDICATE_FAMILY: dict[Predicate, PredicateFamily] = {
    Predicate.SIMILAR_FOLD_TO: PredicateFamily.STRUCTURAL,
    Predicate.SIMILAR_POCKET_TO: PredicateFamily.STRUCTURAL,
    Predicate.SHARES_MOTIF: PredicateFamily.STRUCTURAL,
    Predicate.SIMILAR_SEQUENCE_TO: PredicateFamily.SEQUENCE,
    Predicate.SIMILAR_COMPOUND_TO: PredicateFamily.CHEMICAL,
    Predicate.SHARES_SCAFFOLD: PredicateFamily.CHEMICAL,
    Predicate.HAS_STRUCTURE: PredicateFamily.COMPOSITION,
    Predicate.HAS_POCKET: PredicateFamily.COMPOSITION,
    Predicate.POCKET_LINED_BY: PredicateFamily.COMPOSITION,
    Predicate.HAS_MOTIF: PredicateFamily.COMPOSITION,
    Predicate.HAS_FRAGMENT: PredicateFamily.COMPOSITION,
    Predicate.MEMBER_OF_FAMILY: PredicateFamily.COMPOSITION,
    Predicate.BINDS: PredicateFamily.INTERACTION,
    Predicate.CO_CRYSTALLIZED_WITH: PredicateFamily.INTERACTION,
    Predicate.PROMISCUOUS_WITH: PredicateFamily.INTERACTION,
    Predicate.MODULATES: PredicateFamily.INTERACTION,
    Predicate.COMPETES_WITH: PredicateFamily.INTERACTION,
    Predicate.SUPPORTED_BY: PredicateFamily.EVIDENCE,
    Predicate.CONTRADICTED_BY: PredicateFamily.EVIDENCE,
    Predicate.MEASURED_IN: PredicateFamily.EVIDENCE,
    Predicate.SIMILAR_ASSAY_TO: PredicateFamily.EVIDENCE,
    Predicate.DERIVED_FROM: PredicateFamily.EVIDENCE,
    Predicate.DATASET_COVERS: PredicateFamily.EVIDENCE,
    # HAS_DATA and MEASURED_BETWEEN get their own family because "where can I get
    # the numbers for this pair?" is a different question from "who says so", and
    # the reader wants to see it as a distinct layer.
    Predicate.HAS_DATA: PredicateFamily.DATA,
    Predicate.MEASURED_BETWEEN: PredicateFamily.DATA,
    Predicate.USED_IN: PredicateFamily.METHOD,
    Predicate.EVALUATED_ON: PredicateFamily.METHOD,
    Predicate.OUTPERFORMS: PredicateFamily.METHOD,
    Predicate.FAILS_ON: PredicateFamily.METHOD,
    Predicate.ALTERNATIVE_TO: PredicateFamily.METHOD,
    Predicate.ANALOGOUS_TO: PredicateFamily.ANALOGY,
    Predicate.ORIGINATES_IN: PredicateFamily.ANALOGY,
    Predicate.INSPIRES: PredicateFamily.ANALOGY,
}

#: Okabe-Ito, the standard colour-blind-safe categorical palette, extended with a
#: deep purple and two greys.
#:
#: There are nine families against a stated ceiling of ~8 discriminable colours,
#: which is deliberate and safe for one reason: **at most seven are ever visible at
#: once.** Both grey families are hidden by default, and colour is always paired
#: with dash pattern as a redundant channel (see ``visual_encoding_summary``). The
#: two greys are dark and light respectively and never compete, because they are
#: never both shown.
FAMILY_COLOR: dict[PredicateFamily, str] = {
    PredicateFamily.STRUCTURAL: "#0072B2",   # blue
    PredicateFamily.SEQUENCE: "#56B4E9",     # sky blue
    PredicateFamily.CHEMICAL: "#009E73",     # bluish green
    PredicateFamily.INTERACTION: "#CC79A7",  # light reddish purple
    PredicateFamily.METHOD: "#D55E00",       # vermillion
    PredicateFamily.ANALOGY: "#E69F00",      # orange
    PredicateFamily.DATA: "#6A3D9A",         # deep purple (dark, vs INTERACTION's light pink)
    PredicateFamily.COMPOSITION: "#454545",  # dark grey
    PredicateFamily.EVIDENCE: "#A6A6A6",     # light grey
}

#: Dash patterns cycled within a family, so two structural predicates are
#: distinguishable at the same colour. Solid is reserved for the first/primary
#: predicate in each family. Six patterns covers the largest family (evidence, 6).
DASH_CYCLE: list[list[int] | None] = [
    None, [6, 3], [2, 3], [10, 3, 2, 3], [1, 3], [8, 2, 2, 2],
]

#: Families whose edges are hidden until the reader asks for them.
#:
#: Evidence edges are the classic graph-ruining category: correct, essential, and
#: so numerous they bury the signal — every claim links to at least one source.
#: Data edges are hidden for the same reason and because they answer a question
#: the reader asks deliberately ("where do I get the numbers?") rather than
#: incidentally.
HIDDEN_BY_DEFAULT: set[PredicateFamily] = {
    PredicateFamily.EVIDENCE,
    PredicateFamily.DATA,
}


def family_of(predicate: Predicate) -> PredicateFamily:
    return PREDICATE_FAMILY.get(predicate, PredicateFamily.COMPOSITION)


def dash_for(predicate: Predicate) -> list[int] | None:
    """Stable dash pattern for a predicate within its family."""
    fam = family_of(predicate)
    siblings = sorted(p.value for p, f in PREDICATE_FAMILY.items() if f is fam)
    try:
        idx = siblings.index(predicate.value)
    except ValueError:
        idx = 0
    return DASH_CYCLE[idx % len(DASH_CYCLE)]


def visual_encoding_summary() -> dict[str, str]:
    """The declared grammar, for a Visualization's ``encoding`` field and the legend."""
    return {
        "node_fill": "node.type",
        "node_size": "degree (capped)",
        "edge_stroke": "predicate family (9 defined, at most 7 visible at once)",
        "edge_dash": "predicate within family",
        "edge_width": "axis score, normalised per axis to its declared score_range",
        "edge_opacity": "confidence (4 levels)",
        "ring_radius": "graph distance from the focal node",
    }


class Node(BaseModel):
    """A graph entity.

    ``id`` must be a namespaced, resolvable key so two agents that discover the
    same protein independently produce the same node. Use the canonical
    external accession wherever one exists.

    Conventions (enforced loosely, documented strictly):
        Protein   -> ``uniprot:O75469``      (PXR / NR1I2)
        Structure -> ``pdb:1M13`` or ``pred:boltz2/PXR-x00035-seed3``
        Pocket    -> ``pocket:pdb:1M13/LBD``
        Compound  -> ``chembl:CHEMBL1200973`` or ``inchikey:...``
        Motif     -> ``motif:sae/esmc-6b/L24-F3097`` or ``motif:prosite/PS51843``
        Paper     -> ``doi:10.1016/j.cell.2004.01.008`` / ``pmid:...`` / ``patent:US...``
        Family    -> ``family:NR1I`` , ``family:nuclear-receptor``
        Method    -> ``method:boltz-2.1``
        Analogy   -> ``analogy:finance/regime-switching-ensemble``
        Domain    -> ``domain:quantitative-finance``
    """

    id: str
    type: NodeType
    label: str = Field(..., description="Human-readable name.")
    aliases: list[str] = Field(default_factory=list)
    attrs: dict[str, Any] = Field(default_factory=dict)
    # Provenance: which stage/skill asserted this node exists.
    asserted_by: str = Field(..., description="Skill or stage name.")
    run_id: str | None = None
    created_utc: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("id")
    @classmethod
    def _namespaced(cls, v: str) -> str:
        if ":" not in v:
            raise ValueError(
                f"node id {v!r} must be namespaced as '<namespace>:<accession>' "
                "so independently-discovered duplicates collapse"
            )
        return v.strip()


class Edge(BaseModel):
    """A provenanced assertion between two nodes."""

    src: str
    predicate: Predicate
    dst: str
    attrs: dict[str, Any] = Field(
        default_factory=dict,
        description="Quantitative payload, e.g. {'tm_score': 0.82, 'aligned_len': 241}.",
    )
    confidence: Confidence = Confidence.TENTATIVE
    evidence: list[Evidence] = Field(default_factory=list)
    asserted_by: str
    run_id: str | None = None
    created_utc: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def key(self) -> tuple[str, str, str]:
        """Dedup key. Two agents asserting the same triple should merge, not duplicate."""
        return (self.src, self.predicate.value, self.dst)


class GraphDelta(BaseModel):
    """What one skill contributed. Skills emit deltas; the store merges them."""

    run_id: str
    asserted_by: str
    nodes: list[Node] = Field(default_factory=list)
    edges: list[Edge] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    def validate_referential_integrity(self, known_ids: Iterable[str] = ()) -> list[str]:
        """Return a list of problems. Empty list means the delta is safe to merge.

        Checked here rather than at write time so a skill can fix its own delta
        before polluting the graph.
        """
        problems: list[str] = []
        ids = {n.id for n in self.nodes} | set(known_ids)

        for n in self.nodes:
            if n.type is NodeType.ANALOGY and not any(
                e.src == n.id and e.predicate is Predicate.ORIGINATES_IN for e in self.edges
            ):
                problems.append(
                    f"analogy node {n.id} has no ORIGINATES_IN edge — every analogy must "
                    "name the domain it came from"
                )

        for e in self.edges:
            for endpoint, side in ((e.src, "src"), (e.dst, "dst")):
                if endpoint not in ids:
                    problems.append(
                        f"edge {e.key} references unknown {side} node {endpoint!r}"
                    )
            allowed = PREDICATE_DOMAINS.get(e.predicate)
            if allowed:
                src_ok, dst_ok = allowed
                by_id = {n.id: n for n in self.nodes}
                s, d = by_id.get(e.src), by_id.get(e.dst)
                if src_ok and s and s.type not in src_ok:
                    problems.append(
                        f"edge {e.key}: {e.predicate.value} cannot start at a {s.type.value}"
                    )
                if dst_ok and d and d.type not in dst_ok:
                    problems.append(
                        f"edge {e.key}: {e.predicate.value} cannot end at a {d.type.value}"
                    )
        return problems

    def write_jsonl(self, out_dir: Path) -> tuple[Path, Path]:
        """Append this delta to the graph files."""
        out_dir.mkdir(parents=True, exist_ok=True)
        npath, epath = out_dir / "nodes.jsonl", out_dir / "edges.jsonl"
        with npath.open("a", encoding="utf-8") as fh:
            for n in self.nodes:
                fh.write(n.model_dump_json(exclude_none=True) + "\n")
        with epath.open("a", encoding="utf-8") as fh:
            for e in self.edges:
                fh.write(e.model_dump_json(exclude_none=True) + "\n")
        return npath, epath


def read_jsonl(path: Path, model: type[BaseModel]) -> Iterator[Any]:
    """Stream a graph file. Tolerates blank lines; raises on malformed records."""
    if not Path(path).exists():
        return
    with Path(path).open("r", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                yield model.model_validate(json.loads(line))
            except Exception as exc:
                raise ValueError(f"{path}:{lineno} is not a valid {model.__name__}: {exc}") from exc
