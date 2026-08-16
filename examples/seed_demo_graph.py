"""Seed a small demonstration knowledge graph and render it.

Run:
    python examples/seed_demo_graph.py

**On the honesty of this fixture.** The entity identifiers here are real —
UniProt accessions, PDB IDs, and PMC IDs taken from the reference PXR work. The
*similarity scores* are illustrative placeholders, because measuring them means
running Foldseek and RDKit, which is Stage 1's actual job. So every edge carrying
an unmeasured number is written at ``Confidence.SPECULATIVE`` with
``illustrative: True`` in its attrs, and the rendered page says so in its
subtitle. A demo that quietly fabricates numbers would undermine the exact
guarantee the contracts exist to provide.

Replace this with `reagent run stage1` output as soon as the harvest skills run.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from reagent.contracts import (  # noqa: E402
    Confidence,
    Domain,
    Edge,
    Evidence,
    GraphDelta,
    Node,
    NodeType,
    Predicate,
    ProblemSpec,
    SourceType,
    TargetEntity,
    TaskType,
)
from reagent.domains import profile_for  # noqa: E402
from reagent.kg import KGStore  # noqa: E402
from reagent.viz import render  # noqa: E402

RUN = "demo"
BY = "demo-seed"

# Real human nuclear-receptor accessions. The receptor census (which receptors,
# and roughly how many ligand-bound structures each has) comes from the reference
# repo's RCSB harvest of Pfam PF00104.
NUCLEAR_RECEPTORS = [
    ("uniprot:O75469", "PXR (NR1I2)", 70),
    ("uniprot:Q14994", "CAR (NR1I3)", 2),
    ("uniprot:P11473", "VDR (NR1I1)", 48),
    ("uniprot:Q96RI1", "FXR (NR1H4)", 79),
    ("uniprot:P37231", "PPARG", 88),
    ("uniprot:Q07869", "PPARA", 44),
    ("uniprot:Q03181", "PPARD", 50),
    ("uniprot:P03372", "ESR1", 312),
    ("uniprot:P10275", "AR (NR3C4)", 92),
    ("uniprot:P04150", "GR (NR3C1)", 34),
    ("uniprot:P51449", "RORC", 158),
    ("uniprot:P55055", "LXRB (NR1H2)", 12),
    ("uniprot:P41235", "HNF4A", 1),
]

# Promiscuous xenobiotic handlers — deliberately NOT nuclear receptors. These are
# the transfer sources that share the *problem* (a large adaptable pocket) without
# sharing the fold, which is the point of having a promiscuity axis at all.
PROMISCUOUS = [
    ("uniprot:P08684", "CYP3A4", 0.94),
    ("uniprot:P11712", "CYP2C9", 0.81),
    ("uniprot:P10635", "CYP2D6", 0.78),
    ("uniprot:P08183", "P-glycoprotein (ABCB1)", 0.88),
]

# Fold-similarity placeholders. Ordering reflects real phylogeny (CAR and VDR are
# PXR's closest NR1I relatives); the numbers are not measured.
FOLD = {
    "uniprot:Q14994": 0.87, "uniprot:P11473": 0.79, "uniprot:Q96RI1": 0.74,
    "uniprot:P37231": 0.68, "uniprot:Q07869": 0.66, "uniprot:Q03181": 0.65,
    "uniprot:P55055": 0.64, "uniprot:P04150": 0.61, "uniprot:P10275": 0.60,
    "uniprot:P03372": 0.58, "uniprot:P51449": 0.57, "uniprot:P41235": 0.52,
}
SEQ = {
    "uniprot:Q14994": 0.42, "uniprot:P11473": 0.37, "uniprot:Q96RI1": 0.31,
    "uniprot:P37231": 0.25, "uniprot:P04150": 0.22, "uniprot:P03372": 0.19,
}

# Real PXR holo PDB entries from the reference repo's curated list.
PXR_STRUCTURES = ["pdb:1M13", "pdb:1NRL", "pdb:4X1G", "pdb:5A86", "pdb:8SVO"]

# Real pocket anchors and the aromatic subpocket, UniProt O75469 numbering.
ANCHORS = [("Ser247", "polar, agonist-defining"), ("Gln285", "polar"),
           ("His407", "protonatable, flexible helix 10"), ("Arg410", "salt bridge")]
AROMATIC = [("Phe288", "aromatic cage"), ("Trp299", "aromatic cage"),
            ("Tyr306", "aromatic cage")]
# The apolar lining. Present because a hydrophobic lobe whose residues are not nodes is the
# incomplete decomposition `contracts.parts` exists to catch: the sub-region would claim to
# cover residues the graph has never heard of.
HYDROPHOBIC = [("Leu209", "apolar wall"), ("Leu240", "apolar wall"),
               ("Met243", "apolar wall, conformationally mobile")]

# Real PMC identifiers surfaced by a live Paperclip search plus the reference
# repo's citation list.
PAPERS = [
    ("pmc:PMC12690452", "Subtle changes in ligand-receptor interactions alter PXR outcomes", 2025),
    ("pmc:PMC9563780", "PXR ligand-binding pocket architecture", 2022),
    ("pmc:PMC8864553", "Promiscuity of the PXR ligand-binding domain", 2022),
]

COMPOUNDS = [("chembl:CHEMBL432657", "SR12813", 0.0), ("chembl:CHEMBL374478", "Rifampicin", 0.24),
             ("chembl:CHEMBL427448", "Hyperforin", 0.19), ("chembl:CHEMBL46740", "T0901317", 0.28)]


def paper_ev(locator: str = "pmc:PMC9563780") -> Evidence:
    title = next((t for p, t, _ in PAPERS if p == locator), None)
    year = next((y for p, _, y in PAPERS if p == locator), None)
    return Evidence(source_type=SourceType.PAPER, locator=locator, title=title, year=year)


def illustrative(**scores) -> dict:
    """Mark a placeholder measurement as such, in the data itself."""
    return {**scores, "illustrative": True}


def build() -> GraphDelta:
    nodes: list[Node] = []
    edges: list[Edge] = []
    target = "uniprot:O75469"

    nodes.append(Node(id="family:nuclear-receptor", type=NodeType.FAMILY,
                      label="Nuclear receptor (PF00104 LBD)", asserted_by=BY,
                      attrs={"pfam": "PF00104", "ligand_bound_pdb_entries": 1264}, run_id=RUN))
    nodes.append(Node(id="family:NR1I", type=NodeType.FAMILY, label="NR1I subfamily",
                      asserted_by=BY, run_id=RUN))
    nodes.append(Node(id="family:xenobiotic-handler", type=NodeType.FAMILY,
                      label="Xenobiotic-handling proteins", asserted_by=BY, run_id=RUN))

    for pid, label, n_pdb in NUCLEAR_RECEPTORS:
        nodes.append(Node(id=pid, type=NodeType.PROTEIN, label=label, asserted_by=BY, run_id=RUN,
                          attrs={"ligand_bound_pdb_entries": n_pdb}))
        edges.append(Edge(src=pid, predicate=Predicate.MEMBER_OF_FAMILY,
                          dst="family:nuclear-receptor", confidence=Confidence.ESTABLISHED,
                          attrs={"source": "Pfam PF00104", "membership": 1.0},
                          evidence=[paper_ev("pmc:PMC9563780"), paper_ev("pmc:PMC8864553")],
                          asserted_by=BY, run_id=RUN))
    for pid in ("uniprot:O75469", "uniprot:Q14994", "uniprot:P11473"):
        edges.append(Edge(src=pid, predicate=Predicate.MEMBER_OF_FAMILY, dst="family:NR1I",
                          confidence=Confidence.ESTABLISHED, attrs={"membership": 1.0},
                          evidence=[paper_ev("pmc:PMC9563780"), paper_ev("pmc:PMC8864553")],
                          asserted_by=BY, run_id=RUN))

    for pid, tm in FOLD.items():
        edges.append(Edge(src=target, predicate=Predicate.SIMILAR_FOLD_TO, dst=pid,
                          attrs=illustrative(tm_score=tm), confidence=Confidence.SPECULATIVE,
                          commentary=(
                              "Shared fold means the backbone can be borrowed as a template, "
                              "but says nothing about whether the pocket accepts the same "
                              "chemistry — check the pocket axis before transferring a pose."),
                          asserted_by=BY, run_id=RUN))
    for pid, ident in SEQ.items():
        edges.append(Edge(src=target, predicate=Predicate.SIMILAR_SEQUENCE_TO, dst=pid,
                          attrs=illustrative(identity=ident, coverage=0.9),
                          commentary=(
                              "Full-length identity, which is the wrong number for pose "
                              "transfer — the figure that matters is identity across the "
                              "pocket-lining residues, and it can differ from this by "
                              "twenty points in either direction."),
                          confidence=Confidence.SPECULATIVE, asserted_by=BY, run_id=RUN))

    for pid, label, breadth in PROMISCUOUS:
        nodes.append(Node(id=pid, type=NodeType.PROTEIN, label=label, asserted_by=BY, run_id=RUN))
        edges.append(Edge(src=pid, predicate=Predicate.MEMBER_OF_FAMILY,
                          dst="family:xenobiotic-handler", confidence=Confidence.SUPPORTED,
                          attrs={"membership": 1.0}, evidence=[paper_ev("pmc:PMC8864553")],
                          asserted_by=BY, run_id=RUN))
        edges.append(Edge(src=target, predicate=Predicate.PROMISCUOUS_WITH, dst=pid,
                          attrs=illustrative(breadth_score=breadth),
                          confidence=Confidence.TENTATIVE,
                          commentary=(
                              "Both bind chemically unrelated ligands, so both defeat the "
                              "single-conformer shortcut in the same way. That makes this "
                              "protein a useful source of conformational range even at low "
                              "fold similarity, which a family-first search would never "
                              "reach."),
                          evidence=[paper_ev("pmc:PMC8864553")], asserted_by=BY, run_id=RUN))
    # PXR transcriptionally induces CYP3A4 — the reason this pair matters clinically.
    edges.append(Edge(src=target, predicate=Predicate.MODULATES, dst="uniprot:P08684",
                      attrs={"direction": "induces", "mechanism": "transcriptional"},
                      confidence=Confidence.ESTABLISHED,
                      evidence=[paper_ev("pmc:PMC8864553"), paper_ev("pmc:PMC12690452")],
                      asserted_by=BY, run_id=RUN))

    for pdb in PXR_STRUCTURES:
        nodes.append(Node(id=pdb, type=NodeType.STRUCTURE, label=pdb.split(":")[1],
                          asserted_by=BY, run_id=RUN, attrs={"method": "X-ray"}))
        edges.append(Edge(src=target, predicate=Predicate.HAS_STRUCTURE, dst=pdb,
                          confidence=Confidence.ESTABLISHED,
                          evidence=[paper_ev("pmc:PMC9563780"), paper_ev("pmc:PMC12690452")],
                          asserted_by=BY, run_id=RUN))

    pocket = "pocket:pdb:1M13/LBD"
    nodes.append(Node(id=pocket, type=NodeType.POCKET, label="PXR LBD pocket", asserted_by=BY,
                      run_id=RUN, attrs={"volume_A3": 1600, "character": "large, hydrophobic"}))
    edges.append(Edge(src="pdb:1M13", predicate=Predicate.HAS_POCKET, dst=pocket,
                      confidence=Confidence.ESTABLISHED,
                      evidence=[paper_ev("pmc:PMC9563780"), paper_ev("pmc:PMC8864553")],
                      asserted_by=BY, run_id=RUN))
    for resname, role in ANCHORS + AROMATIC + HYDROPHOBIC:
        rid = f"residue:uniprot:O75469/{resname}"
        nodes.append(Node(id=rid, type=NodeType.RESIDUE, label=resname, asserted_by=BY, run_id=RUN,
                          attrs={"role": role}))
        edges.append(Edge(src=pocket, predicate=Predicate.POCKET_LINED_BY, dst=rid,
                          attrs={"role": role}, confidence=Confidence.SUPPORTED,
                          commentary=(
                              f"Lines the site in the role of {role}. Lining is not the same "
                              "as mattering — whether a pose must satisfy this residue is "
                              "settled by recurrence across complexes, not by proximity."),
                          evidence=[paper_ev("pmc:PMC9563780")], asserted_by=BY, run_id=RUN))

    motif = "motif:aromatic-cage/PXR-LBD"
    nodes.append(Node(id=motif, type=NodeType.MOTIF, label="Aromatic cage (Phe/Trp/Tyr)",
                      asserted_by=BY, run_id=RUN,
                      attrs={"members": ["Phe288", "Trp299", "Tyr306"]}))
    edges.append(Edge(src=target, predicate=Predicate.HAS_MOTIF, dst=motif,
                      confidence=Confidence.SUPPORTED, evidence=[paper_ev("pmc:PMC9563780")],
                      asserted_by=BY, run_id=RUN))
    for pid, score in (("uniprot:Q14994", 0.81), ("uniprot:P11473", 0.66), ("uniprot:P08684", 0.59)):
        edges.append(Edge(src=pid, predicate=Predicate.SHARES_MOTIF, dst=motif,
                          attrs=illustrative(score=score), confidence=Confidence.SPECULATIVE,
                          commentary=(
                              "The same aromatic cage is present, so a ligand relying on "
                              "pi-stacking to hold its pose should behave similarly in both. "
                              "A ligand held by hydrogen bonds instead gains nothing from "
                              "this similarity."),
                          asserted_by=BY, run_id=RUN))

    for pid, title, year in PAPERS:
        nodes.append(Node(id=pid, type=NodeType.PAPER, label=title, asserted_by=BY, run_id=RUN,
                          attrs={"year": year}))
        edges.append(Edge(src=target, predicate=Predicate.SUPPORTED_BY, dst=pid,
                          confidence=Confidence.ESTABLISHED,
                          evidence=[paper_ev(pid), paper_ev("pmc:PMC9563780")],
                          asserted_by=BY, run_id=RUN))

    for cid, label, tan in COMPOUNDS:
        nodes.append(Node(id=cid, type=NodeType.COMPOUND, label=label, asserted_by=BY, run_id=RUN))
        edges.append(Edge(src=target, predicate=Predicate.BINDS, dst=cid,
                          attrs={"role": "agonist"}, confidence=Confidence.SUPPORTED,
                          evidence=[paper_ev("pmc:PMC12690452")], asserted_by=BY, run_id=RUN))
        if tan:
            edges.append(Edge(src="chembl:CHEMBL432657", predicate=Predicate.SIMILAR_COMPOUND_TO,
                              dst=cid, attrs=illustrative(tanimoto=tan, fp_type="morgan-r2"),
                              commentary=(
                                  "Fingerprint similarity, so it reflects shared substructure "
                                  "rather than shared binding mode. Two compounds at this "
                                  "Tanimoto can occupy the pocket in opposite orientations, "
                                  "which is exactly what the interaction matrix settles."),
                              confidence=Confidence.SPECULATIVE, asserted_by=BY, run_id=RUN))

    # ---- Stage 2 anatomy, in the SAME graph -----------------------------
    # Not a second store. The point of the merge is that a fragment discovered by
    # decomposing a test compound is one join away from the promiscuous non-family protein a
    # Stage 1 literature axis found — so the med-chem question "does this substituent engage
    # anything that is conserved across the templates?" is a query rather than a project.
    BY2 = "parts-inventory"

    subpockets = [
        ("hydrophobic-lobe", "Hydrophobic lobe", ["Leu209", "Leu240", "Met243"],
         "The lobe that makes this pocket accommodating. A substituent placed here gains "
         "affinity cheaply and gains no selectivity, because every promiscuous relative has "
         "the same feature."),
        ("polar-rim", "Polar rim", ["Ser247", "Gln285"],
         "The only directional handles in the site. A pose that misplaces these is wrong in a "
         "way scoring functions notice, so this is where a restraint earns its keep."),
        ("aromatic-face", "Aromatic face", ["Phe288", "Trp299", "Tyr306"],
         "Pi-stacking surface shared with the other aromatic-cage proteins, so behaviour here "
         "should transfer between them and is the wrong place to look for selectivity."),
    ]
    for slug, label, members, why in subpockets:
        sid = f"{pocket}/{slug}"
        nodes.append(Node(id=sid, type=NodeType.POCKET, label=label, asserted_by=BY2,
                          run_id=RUN, attrs={"members": members, "n_residues": len(members)}))
        edges.append(Edge(src=sid, predicate=Predicate.PART_OF, dst=pocket,
                          attrs={"covers": members, "partition": True},
                          commentary=why, confidence=Confidence.TENTATIVE,
                          evidence=[paper_ev("pmc:PMC9563780")], asserted_by=BY2, run_id=RUN))

    # Two fragments of one test compound, and what each touches. The interesting cell is the
    # measured-empty one: a fragment that reaches a sub-region and engages nothing there.
    frags = [
        ("fragment:murcko:c1ccc2ccccc2c1", "Naphthalene core", "hydrophobic-lobe",
         Predicate.CONTACTS, "residue:uniprot:O75469/Met243", "hydrophobic",
         "Buries against Met243 across every complex examined, so it is load-bearing for "
         "affinity and useless for discriminating between poses."),
        ("fragment:smarts:[CX3](=O)[OX2H1]", "Carboxylate", "polar-rim",
         Predicate.CONTACTS, "residue:uniprot:O75469/Ser247", "hbond_acceptor",
         "The single directional contact this ligand makes. Both profilers see it, which is "
         "why it is the one restraint worth imposing on Stage 3 sampling."),
    ]
    for fid, flabel, sub, pred, resid, kind, why in frags:
        nodes.append(Node(id=fid, type=NodeType.FRAGMENT, label=flabel, asserted_by=BY2,
                          run_id=RUN))
        edges.append(Edge(src="chembl:CHEMBL432657", predicate=Predicate.HAS_FRAGMENT, dst=fid,
                          confidence=Confidence.SUPPORTED, asserted_by=BY2, run_id=RUN))
        edges.append(Edge(src=fid, predicate=Predicate.OCCUPIES, dst=f"{pocket}/{sub}",
                          attrs={"buried_frac": 0.7},
                          commentary=("Sits in this sub-region, which is what makes the "
                                      "contacts below expected rather than incidental."),
                          confidence=Confidence.TENTATIVE, asserted_by=BY2, run_id=RUN))
        edges.append(Edge(src=fid, predicate=pred, dst=resid,
                          attrs={"interaction": kind, "source": "plip+prolif",
                               "structure": "pdb:1M13", "n_sources": 2, "recurrence": 1.0},
                          commentary=why, confidence=Confidence.TENTATIVE,
                          evidence=[paper_ev("pmc:PMC9563780")], asserted_by=BY2, run_id=RUN))

    return GraphDelta(run_id=RUN, asserted_by=BY, nodes=nodes, edges=edges,
                      notes=["Similarity scores are illustrative placeholders, not measurements.",
                             "Stage 2 anatomy is written into the same graph as Stage 1, so a "
                             "fragment and a literature-derived template are one join apart."])


def main() -> int:
    kg_dir = REPO / "kg" / "demo"
    for f in ("nodes.jsonl", "edges.jsonl", "kg.sqlite"):
        (kg_dir / f).unlink(missing_ok=True)

    store = KGStore(kg_dir)
    delta = build()
    problems = store.merge(delta)
    if problems:
        print("Delta rejected:")
        for p in problems:
            print("  -", p)
        return 1

    spec = ProblemSpec(
        run_id=RUN,
        name="Demo — PXR neighbourhood",
        domain=Domain.STRUCTURAL_BIOLOGY,
        task_type=TaskType.COMPLEX_PREDICTION,
        targets=[TargetEntity(id="uniprot:O75469", kind="protein", label="PXR (NR1I2)",
                              organism="human", known_structures=PXR_STRUCTURES)],
        metric={"name": "LDDT-PLI", "direction": "maximize",
                "definition": "OpenStructure ligand_scoring over the predicted complex.",
                "eval_set": "demo"},
        axes=profile_for(Domain.STRUCTURAL_BIOLOGY, TaskType.COMPLEX_PREDICTION),
    )
    spec.write(REPO / "reports" / RUN / "problem.json")

    stats = store.stats()
    print(f"graph: {stats['n_nodes']} nodes, {stats['n_edges']} edges, "
          f"{stats['cited_edge_fraction']:.0%} of edges cited")

    out, viz = render(
        store, spec.primary_target.id, spec.axes,
        REPO / "docs" / "figures" / "demo_kg.html",
        title="PXR neighbourhood — six similarity axes",
        subtitle=("Demo fixture: identifiers are real; similarity scores are illustrative "
                  "placeholders shown at 'speculative' confidence."),
        max_depth=2, repo_root=REPO,
    )
    print(f"rendered: {out.relative_to(REPO)}  ({out.stat().st_size / 1024:.0f} KB, "
          f"{viz.n_elements} elements)")

    unsupported = store.unsupported_edges(Confidence.SUPPORTED)
    print(f"audit: {len(unsupported)} edges claim >= supported with no citation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
