"""Knowledge-graph contract.

**One graph, written by every stage.** Stage 1 populates the target's neighbourhood from the
literature; Stage 2 extends the *same* store downward into anatomy — which pockets, which
sub-regions, which fragments, which contacts — rather than starting a second graph. Stages 3
and 4 read both layers. The source of truth is two append-only JSONL files
(``nodes.jsonl``, ``edges.jsonl``) because that is git-diffable and keeps provenance attached
to every assertion. A SQLite view is built on demand for querying — see ``reagent.kg.store``.

Keeping the two layers in one store is what makes the useful med-chem question a single
join. *"Which fragment in my test batch engages a sub-pocket residue that is conserved across
the promiscuous non-family proteins Stage 1 found?"* spans a literature axis, a family
corpus, a sub-pocket decomposition and an interaction profile — four hops in one graph, and
four incompatible files if Stage 2 had started fresh.

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
  * pathway membership         -> IN_PATHWAY, SHARES_PATHWAY_WITH
  * cascade position           -> UPSTREAM_OF
  * *analogous* cascade position -> ANALOGOUS_ROLE_TO
  * shared binding partners    -> INTERACTS_WITH, SHARES_PARTNER_WITH
  * localisation / expression  -> EXPRESSED_IN, CO_EXPRESSED_WITH
  * being a kind of thing      -> HAS_PROPERTY

Two of those deserve emphasis because they are the ones a similarity search
structurally cannot produce. ``ANALOGOUS_ROLE_TO`` relates proteins that occupy the
same *position* in different cascades at zero sequence identity. ``HAS_PROPERTY``
reifies a class membership as a node, so "the target is a promiscuous binder" becomes
a traversable hub rather than a sentence that an agent may forget to act on.

For a DNA-encoded-library problem the same machinery binds to SHARES_SCAFFOLD,
HAS_FRAGMENT (building blocks), SIMILAR_ASSAY_TO, and MEMBER_OF_FAMILY over
target classes. **Nothing in this module is specific to any target or domain.**

The payoff: "give me templates that share the target's hydrophobic pocket but are
NOT in its receptor family" is one SQL join away, which is the whole reason to
build a graph rather than write prose.
"""

from __future__ import annotations

import json
import re
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
    # -- systems context: the target is embedded in networks, not just folds ----
    PATHWAY = "Pathway"            # Reactome/KEGG/WikiPathways cascade
    PROCESS = "Process"            # a biological process (GO BP) or function
    TISSUE = "Tissue"              # anatomical site / cell type (UBERON, CL)
    # -- the meta-concept, made explicit ---------------------------------------
    PROPERTY = "Property"          # "promiscuous binder", "liver-enriched", "ligand-activated TF"
    # -- the regulatory layer --------------------------------------------------
    # A gene is not a protein and the distinction is load-bearing here: splice isoforms and
    # sequence variants are gene-level objects, and folding them into the protein node loses
    # the isoform relation entirely — which for a target with functionally distinct isoforms
    # means silently averaging two different proteins.
    GENE = "Gene"                  # a locus; splice isoforms and variants hang off this
    RNA = "RNA"                    # miRNA, lncRNA, siRNA — regulates without binding the protein
    VARIANT = "Variant"            # a specific allele, with its own phenotype and evidence

    # -- Stage 2 anatomy: the pieces both sides are made of --------------------
    # Deliberately few new types. POCKET, RESIDUE, MOTIF and FRAGMENT already exist and are
    # reused; SUBPOCKET is a POCKET with a PART_OF edge, and a functional group is a
    # FRAGMENT. Only the pharmacophore feature earns its own type, because a med chemist
    # treats "an acceptor 4.2 A from an aromatic centroid" as an object in its own right and
    # its semantics — a typed point with a direction — match nothing already here.
    PHARMACOPHORE = "Pharmacophore"  # a typed feature: donor, acceptor, hydrophobe, aromatic


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

    # --- systems / network position --------------------------------------
    # A target is not only a fold. It occupies a position in a cascade, has partners,
    # and is expressed somewhere — and each of those is a legitimate way for two
    # proteins to be related even at zero sequence identity.
    IN_PATHWAY = "IN_PATHWAY"                    # Protein -> Pathway; attrs: role, source_db
    SHARES_PATHWAY_WITH = "SHARES_PATHWAY_WITH"  # attrs: pathway_ids, n_shared, jaccard
    UPSTREAM_OF = "UPSTREAM_OF"                  # attrs: pathway, n_steps, direct
    ANALOGOUS_ROLE_TO = "ANALOGOUS_ROLE_TO"
    """Same *position* in a different cascade — the structural analogy of a role.

    This is the axis a fold-similarity search cannot find. Two proteins can be the
    xenobiotic sensor of their respective cascades, with the same upstream trigger
    shape and the same downstream effector class, while sharing no detectable
    homology. attrs: own_pathway, other_pathway, role, shared_elements.
    """
    INTERACTS_WITH = "INTERACTS_WITH"            # PPI; attrs: method, n_publications, score
    SHARES_PARTNER_WITH = "SHARES_PARTNER_WITH"  # attrs: partners, n_shared, jaccard, partner_role
    PARTICIPATES_IN = "PARTICIPATES_IN"          # Protein -> Process
    EXPRESSED_IN = "EXPRESSED_IN"                # Protein -> Tissue; attrs: level, specificity
    CO_EXPRESSED_WITH = "CO_EXPRESSED_WITH"      # attrs: tissue, correlation, dataset

    # --- meta-properties -------------------------------------------------
    HAS_PROPERTY = "HAS_PROPERTY"
    """The target *is a kind of thing*, and that is itself a connector.

    Reifying the property as a node is the whole point. "PXR is a promiscuous binder"
    stops being a sentence in a report that an agent may or may not think to act on,
    and becomes a node with a degree — so every other promiscuous binder is two hops
    away, and a property with degree 1 is visibly an unexplored lead rather than an
    invisible one. attrs: kind, basis, threshold.
    """

    # --- pharmacology and drug-drug -------------------------------------------
    # The clinical layer. For a xenobiotic sensor this is not peripheral: PXR matters
    # medically almost entirely because of the interactions it mediates, and a graph that
    # records what binds it but not what that binding does to a co-administered drug has
    # captured the biochemistry and missed the reason anyone asked.
    METABOLIZED_BY = "METABOLIZED_BY"        # Compound -> Protein; attrs: fraction, route
    TRANSPORTED_BY = "TRANSPORTED_BY"        # Compound -> Protein; attrs: direction, km
    INHIBITS = "INHIBITS"                    # attrs: ic50_nm, mode (competitive, TDI, ...)
    INDUCES = "INDUCES"                      # attrs: fold, ec50_nm, readout
    INTERACTS_CLINICALLY_WITH = "INTERACTS_CLINICALLY_WITH"
    """A drug-drug interaction, with the protein that mediates it.

    ``via`` is the field that matters and the one usually missing: a DDI recorded without its
    mechanism is a warning label, while one recorded as "rifampicin induces this target, which
    transcribes CYP3A4, which clears the other drug" is a causal chain the graph can check and
    a model can use. attrs: mechanism, severity, via, direction.
    """
    SHARES_TARGET_WITH = "SHARES_TARGET_WITH"  # Compound<->Compound; attrs: n_shared, jaccard

    # --- genetics: what the protein is transcribed from, and its variation ------
    ENCODED_BY = "ENCODED_BY"                # Protein -> Gene
    HAS_ISOFORM = "HAS_ISOFORM"              # Gene -> Protein; attrs: isoform_id, differs_by
    SPLICE_VARIANT_OF = "SPLICE_VARIANT_OF"
    """One isoform relative to another, with the splicing event that produced it.

    Kept distinct from HAS_ISOFORM because the *event* carries the prediction: an exon skip
    that removes part of the ligand-binding domain makes an isoform whose pocket does not
    exist, and treating its activity data as the target's is a category error.
    attrs: event_type, exons, functional_effect.
    """
    HAS_VARIANT = "HAS_VARIANT"              # Gene/Protein -> Variant; attrs: rsid, af
    VARIANT_AFFECTS = "VARIANT_AFFECTS"      # Variant -> Protein/Pocket/Residue; attrs: effect
    ORTHOLOG_OF = "ORTHOLOG_OF"              # attrs: species, identity, pocket_identity
    PARALOG_OF = "PARALOG_OF"                # attrs: identity, duplication_event

    # --- transcriptional and RNA regulation ------------------------------------
    TRANSCRIPTIONALLY_ACTIVATES = "TRANSCRIPTIONALLY_ACTIVATES"   # Protein -> Gene
    TRANSCRIPTIONALLY_REPRESSES = "TRANSCRIPTIONALLY_REPRESSES"   # Protein -> Gene
    BINDS_PROMOTER_OF = "BINDS_PROMOTER_OF"  # Protein -> Gene; attrs: response_element, site
    REGULATED_BY = "REGULATED_BY"            # Gene/Protein -> Protein/RNA; attrs: mechanism
    TARGETS_TRANSCRIPT = "TARGETS_TRANSCRIPT"  # RNA -> Gene; attrs: seed_match, validated
    SILENCED_BY = "SILENCED_BY"              # Gene/Protein -> RNA/Compound; attrs: knockdown_pct
    CO_REGULATED_WITH = "CO_REGULATED_WITH"  # Gene<->Gene; attrs: correlation, condition

    # --- anatomy: which piece is part of what, and which piece touches which ---
    # Stage 2 extends the Stage 1 graph rather than starting a new one, so a template
    # protein discovered by a literature axis and the sub-pocket a fragment occupies live in
    # the same store and are one join apart.
    PART_OF = "PART_OF"
    """Generic containment, for hierarchies the typed predicates do not cover.

    Subpocket -> Pocket, residue-group -> Subpocket, substituent -> Compound. Typed
    predicates win where one exists: HAS_POCKET, HAS_FRAGMENT, POCKET_LINED_BY, HAS_MOTIF.
    attrs: covers (atom indices or residue keys), partition (bool).
    """
    HAS_PHARMACOPHORE = "HAS_PHARMACOPHORE"  # Compound/Fragment -> Pharmacophore
    CONTACTS = "CONTACTS"
    """One piece touching another, per profiler, per complex.

    The med-chem core of Stage 2 and the edge the interaction matrix is built from. Recorded
    once per (source, structure) rather than merged, because two profilers agreed on only
    47% of contact residues on a real complex and their disagreement is a free confidence
    signal. attrs: interaction, source, structure, distance_a, angle_deg, ligand_atoms,
    residue_atoms, recurrence, n_sources.
    """
    OCCUPIES = "OCCUPIES"                    # Fragment/Compound -> Pocket; attrs: buried_frac
    COMPLEMENTARY_TO = "COMPLEMENTARY_TO"
    """Chemistry that suits a site, aggregated across the corpus.

    Distinct from CONTACTS: a contact is an observation in one structure, this is a claim
    about what *would* work there. attrs: n_supporting_complexes, interaction, subpopulation.
    """

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


#: The rest of the vocabulary. Kept as a separate update block only because it was
#: added later; semantically it is one table. **Every predicate must appear here.**
#: A predicate absent from this table gets no endpoint type-checking at all, which
#: means a delta can quietly attach a Compound to a Family and nothing complains
#: until a downstream query returns nonsense.
PREDICATE_DOMAINS.update({
    # similarity
    Predicate.SHARES_MOTIF: (
        {NodeType.PROTEIN, NodeType.STRUCTURE, NodeType.POCKET, NodeType.COMPOUND},
        {NodeType.MOTIF},
    ),
    Predicate.SHARES_SCAFFOLD: (
        {NodeType.COMPOUND, NodeType.FRAGMENT},
        {NodeType.COMPOUND, NodeType.FRAGMENT},
    ),
    Predicate.SIMILAR_ASSAY_TO: ({NodeType.ASSAY}, {NodeType.ASSAY}),
    # composition
    Predicate.HAS_MOTIF: (
        {NodeType.PROTEIN, NodeType.STRUCTURE, NodeType.POCKET, NodeType.COMPOUND},
        {NodeType.MOTIF},
    ),
    Predicate.HAS_FRAGMENT: ({NodeType.COMPOUND}, {NodeType.FRAGMENT, NodeType.MOTIF}),
    # interaction
    Predicate.CO_CRYSTALLIZED_WITH: (
        {NodeType.STRUCTURE, NodeType.PROTEIN},
        {NodeType.COMPOUND, NodeType.FRAGMENT},
    ),
    Predicate.MODULATES: ({NodeType.PROTEIN, NodeType.COMPOUND}, {NodeType.PROTEIN}),
    Predicate.COMPETES_WITH: (
        {NodeType.COMPOUND, NodeType.FRAGMENT},
        {NodeType.COMPOUND, NodeType.FRAGMENT},
    ),
    # epistemics
    Predicate.MEASURED_IN: (None, {NodeType.ASSAY}),
    # data availability
    Predicate.HAS_DATA: (
        {NodeType.PROTEIN, NodeType.COMPOUND, NodeType.ASSAY, NodeType.STRUCTURE,
         NodeType.FAMILY, NodeType.METHOD},
        {NodeType.DATASET},
    ),
    Predicate.DATASET_COVERS: ({NodeType.DATASET}, None),
    Predicate.MEASURED_BETWEEN: (
        {NodeType.ASSAY},
        {NodeType.PROTEIN, NodeType.COMPOUND, NodeType.FRAGMENT, NodeType.POCKET},
    ),
    Predicate.DERIVED_FROM: ({NodeType.DATASET}, {NodeType.DATASET, NodeType.PAPER}),
    # method / pipeline space
    Predicate.USED_IN: ({NodeType.METHOD}, {NodeType.PIPELINE_STEP}),
    Predicate.EVALUATED_ON: ({NodeType.METHOD}, {NodeType.ASSAY, NodeType.DATASET}),
    Predicate.OUTPERFORMS: (
        {NodeType.METHOD, NodeType.PIPELINE_STEP},
        {NodeType.METHOD, NodeType.PIPELINE_STEP},
    ),
    Predicate.FAILS_ON: (
        {NodeType.METHOD, NodeType.PIPELINE_STEP},
        None,  # a failure mode can be almost anything: a subpopulation, an assay, a motif
    ),
    Predicate.ALTERNATIVE_TO: (
        {NodeType.METHOD, NodeType.PIPELINE_STEP},
        {NodeType.METHOD, NodeType.PIPELINE_STEP},
    ),
    # cross-domain innovation
    Predicate.INSPIRES: ({NodeType.ANALOGY}, {NodeType.PIPELINE_STEP, NodeType.METHOD}),
    # systems / network position
    Predicate.IN_PATHWAY: ({NodeType.PROTEIN}, {NodeType.PATHWAY}),
    Predicate.SHARES_PATHWAY_WITH: ({NodeType.PROTEIN}, {NodeType.PROTEIN}),
    Predicate.UPSTREAM_OF: ({NodeType.PROTEIN}, {NodeType.PROTEIN}),
    Predicate.ANALOGOUS_ROLE_TO: ({NodeType.PROTEIN}, {NodeType.PROTEIN}),
    Predicate.INTERACTS_WITH: ({NodeType.PROTEIN}, {NodeType.PROTEIN}),
    Predicate.SHARES_PARTNER_WITH: ({NodeType.PROTEIN}, {NodeType.PROTEIN}),
    Predicate.PARTICIPATES_IN: ({NodeType.PROTEIN}, {NodeType.PROCESS}),
    Predicate.EXPRESSED_IN: ({NodeType.PROTEIN}, {NodeType.TISSUE}),
    Predicate.CO_EXPRESSED_WITH: ({NodeType.PROTEIN}, {NodeType.PROTEIN}),
    # meta-properties. Deliberately unrestricted on the source side: a compound class,
    # an assay, or a method can each be "a kind of thing" whose peers matter.
    Predicate.HAS_PROPERTY: (None, {NodeType.PROPERTY}),
    # anatomy. PART_OF is unrestricted on both sides because the hierarchy spans both
    # substrates — a substituent is part of a compound, a subpocket part of a pocket — and
    # enumerating every legal pair would be a table nobody keeps current.
    Predicate.PART_OF: (None, None),
    Predicate.HAS_PHARMACOPHORE: (
        {NodeType.COMPOUND, NodeType.FRAGMENT, NodeType.POCKET},
        {NodeType.PHARMACOPHORE},
    ),
    Predicate.CONTACTS: (
        {NodeType.COMPOUND, NodeType.FRAGMENT, NodeType.PHARMACOPHORE},
        {NodeType.RESIDUE, NodeType.POCKET, NodeType.MOTIF, NodeType.PHARMACOPHORE},
    ),
    Predicate.OCCUPIES: ({NodeType.COMPOUND, NodeType.FRAGMENT}, {NodeType.POCKET}),
    Predicate.COMPLEMENTARY_TO: (
        {NodeType.RESIDUE, NodeType.POCKET, NodeType.MOTIF},
        {NodeType.FRAGMENT, NodeType.PHARMACOPHORE, NodeType.COMPOUND},
    ),
    # pharmacology / clinical
    Predicate.METABOLIZED_BY: ({NodeType.COMPOUND}, {NodeType.PROTEIN}),
    Predicate.TRANSPORTED_BY: ({NodeType.COMPOUND}, {NodeType.PROTEIN}),
    Predicate.INHIBITS: ({NodeType.COMPOUND, NodeType.PROTEIN}, {NodeType.PROTEIN}),
    Predicate.INDUCES: ({NodeType.COMPOUND, NodeType.PROTEIN}, {NodeType.PROTEIN, NodeType.GENE}),
    Predicate.INTERACTS_CLINICALLY_WITH: ({NodeType.COMPOUND}, {NodeType.COMPOUND}),
    Predicate.SHARES_TARGET_WITH: ({NodeType.COMPOUND}, {NodeType.COMPOUND}),
    # genetics
    Predicate.ENCODED_BY: ({NodeType.PROTEIN}, {NodeType.GENE}),
    Predicate.HAS_ISOFORM: ({NodeType.GENE}, {NodeType.PROTEIN}),
    Predicate.SPLICE_VARIANT_OF: ({NodeType.PROTEIN}, {NodeType.PROTEIN}),
    Predicate.HAS_VARIANT: ({NodeType.GENE, NodeType.PROTEIN}, {NodeType.VARIANT}),
    Predicate.VARIANT_AFFECTS: (
        {NodeType.VARIANT},
        {NodeType.PROTEIN, NodeType.POCKET, NodeType.RESIDUE, NodeType.PROCESS},
    ),
    Predicate.ORTHOLOG_OF: ({NodeType.PROTEIN, NodeType.GENE}, {NodeType.PROTEIN, NodeType.GENE}),
    Predicate.PARALOG_OF: ({NodeType.PROTEIN, NodeType.GENE}, {NodeType.PROTEIN, NodeType.GENE}),
    # transcriptional / RNA regulation
    Predicate.TRANSCRIPTIONALLY_ACTIVATES: ({NodeType.PROTEIN}, {NodeType.GENE}),
    Predicate.TRANSCRIPTIONALLY_REPRESSES: ({NodeType.PROTEIN}, {NodeType.GENE}),
    Predicate.BINDS_PROMOTER_OF: ({NodeType.PROTEIN}, {NodeType.GENE}),
    Predicate.REGULATED_BY: (
        {NodeType.GENE, NodeType.PROTEIN},
        {NodeType.PROTEIN, NodeType.RNA, NodeType.COMPOUND},
    ),
    Predicate.TARGETS_TRANSCRIPT: ({NodeType.RNA}, {NodeType.GENE, NodeType.PROTEIN}),
    Predicate.SILENCED_BY: (
        {NodeType.GENE, NodeType.PROTEIN},
        {NodeType.RNA, NodeType.COMPOUND},
    ),
    Predicate.CO_REGULATED_WITH: ({NodeType.GENE}, {NodeType.GENE}),
})


def unconstrained_predicates() -> list[str]:
    """Predicates with no entry in PREDICATE_DOMAINS. Should always be empty.

    Exercised by the test suite so that adding a predicate without registering its
    endpoint types fails CI rather than silently disabling type-checking for it.
    """
    return sorted(p.value for p in Predicate if p not in PREDICATE_DOMAINS)


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
    INTERACTION = "interaction"    # binding and physical contact
    SYSTEMS = "systems"            # pathway, cascade position, protein-protein partners
    CONTEXT = "context"            # where and what: expression, tissue, meta-properties
    GENETIC = "genetic"            # gene, isoform, splice event, variant, orthology
    REGULATORY = "regulatory"      # transcriptional control and RNA-mediated silencing
    CLINICAL = "clinical"          # pharmacology, ADME, drug-drug interaction
    DATA = "data"                  # where measurements live (lazy dataset pointers)
    EVIDENCE = "evidence"          # epistemic links to sources
    METHOD = "method"              # pipeline-space relations
    ANALOGY = "analogy"            # cross-domain transfer

    @property
    def tier(self) -> FamilyTier:
        return FAMILY_TIER[self]


class FamilyTier(str, Enum):
    """The grouping that lets the vocabulary grow while perception does not.

    **The problem this solves.** Every time the graph gained a layer, a family was added and
    the colour budget was stretched a little further with a paragraph of justification. That
    does not scale: the vocabulary is now 69 predicates in 14 families, and there is no
    arrangement of 14 categorical colours that a reader can tell apart. Adding a fifteenth
    family would be worse, and refusing to add one would mean refusing to model the biology.

    **The fix is to stop asking colour to carry it.** Families group into six tiers, and the
    guarantee changes from *"colour identifies the family"* to **"colour identifies the family
    within its tier"** — so the same hue means structural-similarity in the molecular tier and
    transcriptional-activation in the regulatory tier, and that is fine, because the tier
    filter is how a reader gets to either one.

    A tier answers one kind of question, which is why it is the right unit for a filter:

    * ``MOLECULAR`` — what is this thing, and what does it look like?
    * ``PHYSICAL`` — what touches it?
    * ``SYSTEMS`` — where does it sit in the network?
    * ``REGULATORY`` — what controls it, and what does it control?
    * ``CLINICAL`` — what does it do in a patient?
    * ``PROVENANCE`` — who says so, and where is the data?
    * ``META`` — how are we modelling it?

    At most four families sit in any tier, so at most four hues are ever needed at once. The
    ego view opens on the tiers relevant to the focal node's type; the rest render desaturated
    and are one toggle away. Enabling every tier at once is explicitly hairball mode and is
    labelled as such.
    """

    MOLECULAR = "molecular"
    PHYSICAL = "physical"
    SYSTEMS = "systems"
    REGULATORY = "regulatory"
    CLINICAL = "clinical"
    PROVENANCE = "provenance"
    META = "meta"

    @property
    def question(self) -> str:
        return {
            "molecular": "What is this made of, and what does it resemble?",
            "physical": "What physically touches it, and where?",
            "systems": "Where does it sit in the network?",
            "regulatory": "What controls it, and what does it control?",
            "clinical": "What does it do in a patient?",
            "provenance": "Who says so, and where is the underlying data?",
            "meta": "How are we modelling this?",
        }[self.value]


#: Which tier each family belongs to. The only table that has to stay complete as the
#: vocabulary grows — a new family needs a tier, not a new colour.
FAMILY_TIER: dict[PredicateFamily, FamilyTier] = {
    PredicateFamily.STRUCTURAL: FamilyTier.MOLECULAR,
    PredicateFamily.SEQUENCE: FamilyTier.MOLECULAR,
    PredicateFamily.CHEMICAL: FamilyTier.MOLECULAR,
    PredicateFamily.COMPOSITION: FamilyTier.MOLECULAR,
    PredicateFamily.INTERACTION: FamilyTier.PHYSICAL,
    PredicateFamily.SYSTEMS: FamilyTier.SYSTEMS,
    PredicateFamily.CONTEXT: FamilyTier.SYSTEMS,
    PredicateFamily.GENETIC: FamilyTier.REGULATORY,
    PredicateFamily.REGULATORY: FamilyTier.REGULATORY,
    PredicateFamily.CLINICAL: FamilyTier.CLINICAL,
    PredicateFamily.DATA: FamilyTier.PROVENANCE,
    PredicateFamily.EVIDENCE: FamilyTier.PROVENANCE,
    PredicateFamily.METHOD: FamilyTier.META,
    PredicateFamily.ANALOGY: FamilyTier.META,
}

#: Tiers shown chromatically when the ego view opens, keyed by the focal node's type.
#:
#: A default, not a restriction. It exists because opening on all seven tiers is the hairball
#: this whole file is arranged to avoid, and because the right opening view genuinely differs:
#: land on a compound and the clinical tier is the interesting one, land on a pocket and it is
#: physical contact.
DEFAULT_TIERS: dict[str, tuple[FamilyTier, ...]] = {
    NodeType.PROTEIN.value: (FamilyTier.MOLECULAR, FamilyTier.SYSTEMS, FamilyTier.PHYSICAL),
    NodeType.GENE.value: (FamilyTier.REGULATORY, FamilyTier.MOLECULAR),
    NodeType.RNA.value: (FamilyTier.REGULATORY,),
    NodeType.VARIANT.value: (FamilyTier.REGULATORY, FamilyTier.CLINICAL),
    NodeType.COMPOUND.value: (FamilyTier.CLINICAL, FamilyTier.MOLECULAR, FamilyTier.PHYSICAL),
    NodeType.FRAGMENT.value: (FamilyTier.PHYSICAL, FamilyTier.MOLECULAR),
    NodeType.POCKET.value: (FamilyTier.PHYSICAL, FamilyTier.MOLECULAR),
    NodeType.RESIDUE.value: (FamilyTier.PHYSICAL, FamilyTier.MOLECULAR),
    NodeType.PATHWAY.value: (FamilyTier.SYSTEMS, FamilyTier.REGULATORY),
    NodeType.METHOD.value: (FamilyTier.META,),
    NodeType.ANALOGY.value: (FamilyTier.META,),
    NodeType.PAPER.value: (FamilyTier.PROVENANCE,),
    NodeType.DATASET.value: (FamilyTier.PROVENANCE,),
}

#: Fallback when the focal type has no entry.
FALLBACK_TIERS: tuple[FamilyTier, ...] = (
    FamilyTier.MOLECULAR, FamilyTier.PHYSICAL, FamilyTier.SYSTEMS,
)


def default_tiers_for(node_type: str) -> tuple[FamilyTier, ...]:
    return DEFAULT_TIERS.get(node_type, FALLBACK_TIERS)


def families_in(tier: FamilyTier) -> list[PredicateFamily]:
    return [f for f, t in FAMILY_TIER.items() if t is tier]


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
    # Network position gets its own colour rather than being folded into INTERACTION,
    # because "binds this molecule" and "sits at this point in this cascade" are
    # different questions and a reader filtering for one does not want the other.
    Predicate.IN_PATHWAY: PredicateFamily.SYSTEMS,
    Predicate.SHARES_PATHWAY_WITH: PredicateFamily.SYSTEMS,
    Predicate.UPSTREAM_OF: PredicateFamily.SYSTEMS,
    Predicate.ANALOGOUS_ROLE_TO: PredicateFamily.SYSTEMS,
    Predicate.INTERACTS_WITH: PredicateFamily.SYSTEMS,
    Predicate.SHARES_PARTNER_WITH: PredicateFamily.SYSTEMS,
    Predicate.PARTICIPATES_IN: PredicateFamily.SYSTEMS,
    Predicate.EXPRESSED_IN: PredicateFamily.CONTEXT,
    Predicate.CO_EXPRESSED_WITH: PredicateFamily.CONTEXT,
    Predicate.HAS_PROPERTY: PredicateFamily.CONTEXT,
    # Anatomy deliberately reuses two existing families rather than adding one, because the
    # palette is already at its discriminability ceiling. Containment is composition;
    # touching is interaction. That split also matches how the ego view gets filtered: a med
    # chemist isolates INTERACTION to see what engages what, and COMPOSITION to see what a
    # thing is made of.
    Predicate.PART_OF: PredicateFamily.COMPOSITION,
    Predicate.HAS_PHARMACOPHORE: PredicateFamily.COMPOSITION,
    Predicate.CONTACTS: PredicateFamily.INTERACTION,
    Predicate.OCCUPIES: PredicateFamily.INTERACTION,
    Predicate.COMPLEMENTARY_TO: PredicateFamily.INTERACTION,
    # clinical
    Predicate.METABOLIZED_BY: PredicateFamily.CLINICAL,
    Predicate.TRANSPORTED_BY: PredicateFamily.CLINICAL,
    Predicate.INHIBITS: PredicateFamily.CLINICAL,
    Predicate.INDUCES: PredicateFamily.CLINICAL,
    Predicate.INTERACTS_CLINICALLY_WITH: PredicateFamily.CLINICAL,
    Predicate.SHARES_TARGET_WITH: PredicateFamily.CLINICAL,
    # genetic
    Predicate.ENCODED_BY: PredicateFamily.GENETIC,
    Predicate.HAS_ISOFORM: PredicateFamily.GENETIC,
    Predicate.SPLICE_VARIANT_OF: PredicateFamily.GENETIC,
    Predicate.HAS_VARIANT: PredicateFamily.GENETIC,
    Predicate.VARIANT_AFFECTS: PredicateFamily.GENETIC,
    Predicate.ORTHOLOG_OF: PredicateFamily.GENETIC,
    Predicate.PARALOG_OF: PredicateFamily.GENETIC,
    # regulatory
    Predicate.TRANSCRIPTIONALLY_ACTIVATES: PredicateFamily.REGULATORY,
    Predicate.TRANSCRIPTIONALLY_REPRESSES: PredicateFamily.REGULATORY,
    Predicate.BINDS_PROMOTER_OF: PredicateFamily.REGULATORY,
    Predicate.REGULATED_BY: PredicateFamily.REGULATORY,
    Predicate.TARGETS_TRANSCRIPT: PredicateFamily.REGULATORY,
    Predicate.SILENCED_BY: PredicateFamily.REGULATORY,
    Predicate.CO_REGULATED_WITH: PredicateFamily.REGULATORY,
}

#: Okabe-Ito, the standard colour-blind-safe categorical palette, allocated **per tier**.
#:
#: **What changed and why.** This table used to promise that colour identified the family, and
#: that promise died quietly as the vocabulary grew — fourteen families cannot be told apart
#: by hue, and no amount of careful shade-picking fixes it. The promise is now scoped:
#:
#:   **colour identifies the family within its tier.**
#:
#: So blue means structural-similarity in the molecular tier and transcriptional-activation in
#: the regulatory tier. That is not a collision to apologise for — it is the mechanism that
#: lets the graph model splicing, drug-drug interaction and RNA silencing without the figure
#: becoming unreadable. At most four families occupy a tier, so at most four hues are needed
#: at once, comfortably inside the discriminability ceiling.
#:
#: Two channels still back it up. Dash pattern separates predicates inside a family, and
#: **inactive tiers render desaturated** rather than competing for hue. Enabling every tier is
#: hairball mode and the legend says so.
#:
#: Yellow (#F0E442) is absent throughout: it is in the Okabe-Ito set and unusable for thin
#: strokes on a light background.
FAMILY_COLOR: dict[PredicateFamily, str] = {
    # molecular — what is this, and what does it resemble
    PredicateFamily.STRUCTURAL: "#0072B2",   # blue
    PredicateFamily.SEQUENCE: "#56B4E9",     # sky blue
    PredicateFamily.CHEMICAL: "#009E73",     # bluish green
    PredicateFamily.COMPOSITION: "#454545",  # dark grey — scaffolding, deliberately achromatic
    # physical — what touches it
    PredicateFamily.INTERACTION: "#CC79A7",  # light reddish purple
    # systems — where it sits
    PredicateFamily.SYSTEMS: "#6A3D9A",      # deep purple
    PredicateFamily.CONTEXT: "#8C6D31",      # darkened olive
    # regulatory — what controls it. Hues reused from the molecular tier by design.
    PredicateFamily.GENETIC: "#0072B2",      # blue
    PredicateFamily.REGULATORY: "#009E73",   # bluish green
    # clinical — what it does in a patient
    PredicateFamily.CLINICAL: "#D55E00",     # vermillion
    # meta — how we are modelling it
    PredicateFamily.METHOD: "#D55E00",       # vermillion (never co-visible with clinical)
    PredicateFamily.ANALOGY: "#E69F00",      # orange
    # provenance — who says so
    PredicateFamily.DATA: "#767676",         # mid grey
    PredicateFamily.EVIDENCE: "#A6A6A6",     # light grey
}


def color_collisions() -> dict[str, list[str]]:
    """Families sharing a colour **within one tier**. Must always be empty.

    Reused hues across tiers are the design. Reused hues *inside* a tier are a bug, and the
    kind that survives review because the figure still renders. Exercised by the test suite.
    """
    out: dict[str, list[str]] = {}
    for tier in FamilyTier:
        seen: dict[str, list[str]] = {}
        for fam in families_in(tier):
            seen.setdefault(FAMILY_COLOR[fam], []).append(fam.value)
        for colour, fams in seen.items():
            if len(fams) > 1:
                out[f"{tier.value}:{colour}"] = sorted(fams)
    return out

#: Dash patterns cycled within a family, so two structural predicates are
#: distinguishable at the same colour. Solid is reserved for the first/primary
#: predicate in each family. Eight patterns covers the largest families (COMPOSITION and
#: INTERACTION, 8 each after Stage 2's anatomy predicates).
#:
#: **Beyond about five, a dash pattern stops being a reliable cue** at typical edge widths.
#: Two families are at eight, so their last three patterns are decoration rather than signal.
#: What actually carries the distinction there is hover and the predicate filter — which is
#: the right division of labour, because "which piece touches which" is a question a med
#: chemist asks deliberately by isolating one predicate, not by reading eight dash patterns
#: off a hairball. Recording this so nobody later reads the length of this list as a claim
#: about perception.
DASH_CYCLE: list[list[int] | None] = [
    None, [6, 3], [2, 3], [10, 3, 2, 3], [1, 3], [8, 2, 2, 2], [4, 2, 1, 2], [3, 1],
]

#: Families whose edges are hidden until the reader asks for them.
#:
#: Evidence edges are the classic graph-ruining category: correct, essential, and
#: so numerous they bury the signal — every claim links to at least one source.
#: Data edges are hidden for the same reason and because they answer a question
#: the reader asks deliberately ("where do I get the numbers?") rather than
#: incidentally.
#:
#: SYSTEMS and CONTEXT are deliberately **not** hidden despite being new and numerous.
#: The whole reason they were added is that network position and meta-properties are the
#: connections an agent forgets to look for; defaulting them to invisible would restore
#: exactly the blind spot they exist to fix.
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
        "edge_stroke": "predicate family (11 defined, 9 visible by default, 2 grey families opt-in)",
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
        Residue   -> ``residue:uniprot:O75469/Ser247``
        Assay     -> ``assay:chembl:CHEMBL1613777``
        Dataset   -> ``zenodo:10.5281/zenodo.1234567`` , ``hf:owner/name`` ,
                     ``github:owner/repo#path/to/file.csv`` , ``kaggle:comp-slug``
                     (the DataRef id doubles as the node id — see contracts.data)
        Fragment  -> ``fragment:smarts:[CX3](=O)[OX2H1]`` , ``fragment:murcko:<smiles>``
        Method    -> ``method:boltz-2.1``
        PipelineStep -> ``step:pose-selection`` , ``step:sampling``
        Analogy   -> ``analogy:finance/regime-switching-ensemble``
        Domain    -> ``domain:quantitative-finance``

    Stage 2 anatomy ids follow the same rule — derived from what the part *is*, never from
    who found it, so two profilers decomposing the same molecule converge on one node:
        Subpocket -> ``pocket:pdb:1M13/LBD/hydrophobic-lobe``   (PART_OF the parent pocket)
        Fragment  -> ``fragment:murcko:<smiles>`` , ``fragment:smarts:[CX3](=O)[OX2H1]``
        Pharmacophore -> ``pharm:chembl:CHEMBL1200973/acceptor-3``
                         ``pharm:pocket:pdb:1M13/LBD/donor-1``
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


#: Phrases that restate a predicate instead of reading it. Module scope, not a class
#: attribute, because pydantic turns leading-underscore class attributes into
#: ``ModelPrivateAttr`` — a trap this project has already fallen into twice.
_RESTATEMENT = re.compile(
    r"^(?:(?:the\s+)?(?:two\s+)?(?:nodes?|entities|proteins?|compounds?|fragments?|residues?)\s+)?"
    r"(?:are|is|has|have|shares?|shared)\b[^.]{0,40}$",
    re.I,
)


class Edge(BaseModel):
    """A provenanced assertion between two nodes.

    ``commentary`` is the field that makes an edge readable rather than merely true. A
    ``CONTACTS`` edge with a distance and an angle is checkable; what a med chemist needs is
    the sentence saying *what it means* — and that sentence belongs on the edge, because the
    edge is where the pair is asserted. Any view that puts two nodes side by side is really
    asking the edge to explain itself, so the explanation has to live here rather than being
    reconstructed by whatever renders the pair.
    """

    src: str
    predicate: Predicate
    dst: str
    attrs: dict[str, Any] = Field(
        default_factory=dict,
        description="Quantitative payload, e.g. {'tm_score': 0.82, 'aligned_len': 241}.",
    )
    commentary: str | None = Field(
        default=None,
        description=(
            "Why this connection matters, in domain terms — not a restatement of the "
            "predicate. Not 'these two share a motif' but 'both present the same "
            "hydrophobic wall to the ligand, so a pose that buries an apolar group here "
            "scores well in both and the preference does not discriminate between them'. "
            "This is what a side-by-side comparison of the two endpoints shows the reader."
        ),
    )
    confidence: Confidence = Confidence.TENTATIVE
    evidence: list[Evidence] = Field(default_factory=list)
    asserted_by: str
    run_id: str | None = None
    created_utc: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("commentary")
    @classmethod
    def _commentary_says_something(cls, v: str | None) -> str | None:
        """Reject a restatement of the predicate dressed as an explanation.

        The failure this catches is the one every "add a description field" change invites:
        the field gets filled with the predicate in lower case and nobody notices it explains
        nothing, because it is present and grammatical.
        """
        if v is None:
            return None
        v = v.strip()
        if not v:
            return None
        if len(v.split()) < 6 or _RESTATEMENT.match(v):
            raise ValueError(
                f"edge commentary {v!r} restates the connection rather than reading it. Say "
                "what it implies for someone deciding what to do next — which pose, which "
                "template, which substituent — or leave it unset."
            )
        return v

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

    def validate_referential_integrity(
        self,
        known_ids: Iterable[str] = (),
        known_types: dict[str, str] | None = None,
    ) -> list[str]:
        """Return a list of problems. Empty list means the delta is safe to merge.

        Exposed separately from writing so a skill can inspect and fix its own delta
        before touching the graph — but ``write_jsonl`` also calls it by default, so
        a caller cannot skip it by accident.

        ``known_types`` maps already-stored node ids to their type names. Without it,
        predicate type-checking is blind to edges whose endpoints live only in the
        existing graph, which is the common case for an incremental delta.
        """
        problems: list[str] = []
        ids = {n.id for n in self.nodes} | set(known_ids)
        types: dict[str, str] = dict(known_types or {})
        types.update({n.id: n.type.value for n in self.nodes})

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
            # Type-check against the merged view (delta nodes plus already-stored
            # ones), so an incremental delta attaching to existing nodes is checked
            # too — that is the common case, and it used to be unchecked.
            allowed = PREDICATE_DOMAINS.get(e.predicate)
            if allowed:
                src_ok, dst_ok = allowed
                s_type, d_type = types.get(e.src), types.get(e.dst)
                if src_ok and s_type and s_type not in {t.value for t in src_ok}:
                    problems.append(
                        f"edge {e.key}: {e.predicate.value} cannot start at a {s_type}"
                    )
                if dst_ok and d_type and d_type not in {t.value for t in dst_ok}:
                    problems.append(
                        f"edge {e.key}: {e.predicate.value} cannot end at a {d_type}"
                    )
        return problems

    def write_jsonl(self, out_dir: Path, *, validate: bool = True) -> tuple[Path, Path]:
        """Append this delta to the graph files.

        Validates first by default. Passing ``validate=False`` is only correct when
        the caller has already validated against the full graph — which is what
        ``KGStore.merge`` does, since it knows the existing node ids and types and
        this method does not. Writing an unvalidated delta puts dangling edges into
        the source of truth, and they are much harder to find later than to reject now.
        """
        if validate:
            problems = self.validate_referential_integrity()
            if problems:
                raise ValueError(
                    "refusing to write an invalid GraphDelta:\n  "
                    + "\n  ".join(problems)
                    + "\n(if the endpoints exist in the stored graph, call KGStore.merge "
                    "instead — it validates against the full graph)"
                )
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
