"""
Knowledge graph of general structure-based drug design (SBDD) concepts.

Schema
------
Node types: Concept, Method, Paper
Node attrs: type, label, summary, [url, year] (Paper only)

Edge `relation` vocabulary (kept small and consistent so queries stay simple):
    introduces, extends, anchors, identifies, uses_method, informs,
    contributes_to, insufficient_for, causes, fails_under, has_limitation,
    refined_by, rigorous_variant_of, mitigates, discusses, explains, estimates

To extend later (e.g. add a target like PXR as its own layer):
    add nodes with type="Target"/"Residue"/"Ligand" and connect them to the
    Concept layer with relations like "hot_spot_of", "binds", "example_of" -
    the Concept layer here doesn't need to change.
"""

import json
from pathlib import Path

import networkx as nx

G = nx.DiGraph()


def concept(id_, label, summary, source_url=None, source_note=None):
    G.add_node(id_, type="Concept", label=label, summary=summary,
               source_url=source_url, source_note=source_note)


def method(id_, label, summary, source_url=None, source_note=None):
    G.add_node(id_, type="Method", label=label, summary=summary,
               source_url=source_url, source_note=source_note)


def paper(id_, label, summary, url, year):
    G.add_node(id_, type="Paper", label=label, summary=summary, url=url, year=year)


def rel(src, relation, dst, note=""):
    G.add_edge(src, dst, relation=relation, note=note)


# ---- Concepts -----------------------------------------------------------
concept("hot_spot", "Binding hot spot",
        "Small sub-region of a pocket contributing disproportionately to "
        "binding free energy; found via fragment screening or computational "
        "fragment mapping.",
        source_url="https://academic.oup.com/bioinformatics/article/25/5/621/183466")
concept("pharmacophore", "Pharmacophore",
        "3D arrangement of features (H-bond donor/acceptor, hydrophobe, "
        "aromatic, charge) required for a ligand to bind; often built by "
        "anchoring to hot spots.",
        source_url="https://pubmed.ncbi.nlm.nih.gov/18570371/")
concept("water_displacement", "Water displacement",
        "Displacing an ordered, enthalpically unhappy water from the pocket "
        "can yield a large affinity gain independent of the ligand's own "
        "direct interactions.",
        source_note="General medicinal-chemistry knowledge - not tied to a "
        "single paper turned up in search; standard SBDD textbook concept.")
concept("shape_complementarity", "Shape complementarity",
        "Geometric fit between ligand and pocket; necessary but not "
        "sufficient for affinity - overweighted by naive scoring functions.",
        source_note="General medicinal-chemistry knowledge - not tied to a "
        "single paper turned up in search.")
concept("electrostatic_complementarity", "Electrostatic complementarity",
        "Alignment of ligand/pocket charge and H-bond donor-acceptor "
        "patterns; usually the dominant term once shape is roughly satisfied.",
        source_note="General medicinal-chemistry knowledge - not tied to a "
        "single paper turned up in search.")
concept("induced_fit", "Induced fit",
        "Pocket/loop conformational change upon ligand binding; apo "
        "structures can misrepresent the true holo pocket.",
        source_note="General structural-biology knowledge - not tied to a "
        "single paper turned up in search.")
concept("cryptic_pocket", "Cryptic pocket",
        "Binding site not visible/open in the unliganded (apo) structure, "
        "only forms upon ligand engagement.",
        source_note="General structural-biology knowledge - not tied to a "
        "single paper turned up in search.")
concept("pocket_flexibility", "Pocket flexibility / plasticity",
        "How much a pocket's volume/shape varies across structures or an MD "
        "trajectory, not just atomic wobble within one static structure "
        "(e.g. PXR's unusually plastic pocket). Quantified as a plasticity "
        "score (normalized pocket-volume range across superposed structures "
        "or MD frames); drives whether rigid or ensemble docking is valid, "
        "and should discount per-fragment confidence when only one rigid "
        "structure was used.",
        source_note="General structural-biology knowledge, grounded in the "
        "PXR case discussed in this session - not tied to a single paper.")
concept("rigid_receptor_docking", "Rigid-receptor docking (limitation)",
        "Standard docking approximation holding the protein fixed while "
        "sampling only ligand pose/conformation; breaks down under induced "
        "fit or cryptic pockets.",
        source_url="https://pmc.ncbi.nlm.nih.gov/articles/PMC6270832/",
        source_note="Review discusses docking limitations generally; not "
        "specific to this failure mode by name.")
concept("scoring_function_limitations", "Scoring function limitations",
        "Docking scoring functions are fast empirical/knowledge-based "
        "approximations to binding free energy; often poor at ranking hits "
        "by affinity even when pose prediction is good.",
        source_url="https://pmc.ncbi.nlm.nih.gov/articles/PMC6270832/")
concept("binding_free_energy", "Binding free energy (dG)",
        "The thermodynamic quantity determining affinity; decomposes into "
        "enthalpic (H-bonds, vdW, electrostatics) and entropic "
        "(conformational, solvent release) terms.",
        source_note="Standard thermodynamics/textbook concept - not tied to "
        "a single paper turned up in search.")
concept("free_energy_perturbation", "Free energy perturbation (FEP)",
        "Rigorous but expensive alchemical method to compute relative "
        "binding free energy differences between ligands.",
        source_note="General computational-chemistry knowledge - not tied "
        "to a single paper turned up in search.")
concept("druggability", "Druggability",
        "Assessment of whether a pocket is likely to bind a small molecule "
        "with high affinity - based on volume, hydrophobicity, enclosure, "
        "and hot-spot hit-rate in fragment screens.",
        source_url="https://academic.oup.com/bioinformatics/article/25/5/621/183466")
concept("conformational_ensemble_docking", "Ensemble docking",
        "Docking against multiple receptor conformations (from MD, NMR, or "
        "multiple crystal structures) to partly account for flexibility "
        "rigid docking misses.",
        source_note="General computational-chemistry knowledge - not tied "
        "to a single paper turned up in search.")

# ---- Methods --------------------------------------------------------------
method("docking", "Molecular docking",
       "Computational sampling of ligand poses in a binding site with a "
       "scoring-function estimate of affinity; fast first-pass triage.",
       source_url="https://pure.bond.edu.au/ws/files/12803722/"
       "A_practical_guide_to_molecular_docking_and_homology_modelling_for_medicinal_chemists.pdf")
method("fragment_based_screening", "Fragment-based screening",
       "Screening small (~150-250 Da) fragment libraries by NMR/X-ray/SPR "
       "to directly identify hot spots and build up ligands atom-by-atom.",
       source_url="https://academic.oup.com/bioinformatics/article/25/5/621/183466")
method("molecular_dynamics_refinement", "MD refinement",
       "Post-docking molecular dynamics used to relax a docked pose, check "
       "pose stability, and estimate free energy more rigorously "
       "(e.g. MM-GBSA).",
       source_url="https://www.sciencedirect.com/science/article/abs/pii/S0959440X17301100")
method("mdpocket", "MDpocket",
       "fpocket-based tool that tracks cavity volume, shape, and opening/"
       "closing across an MD trajectory or other conformational ensemble, "
       "instead of a single static structure.",
       source_url="https://academic.oup.com/bioinformatics/article/27/23/3276/234086")

# ---- Papers ---------------------------------------------------------------
paper("nakamura2021_hotspots",
      "Exploring protein hotspots by optimized fragment pharmacophores",
      "Nature Communications 2021. Fragment-pharmacophore method for "
      "locating and characterizing protein binding hot spots.",
      "https://www.nature.com/articles/s41467-021-23443-y", 2021)
paper("bioinf2009_hotspots",
      "Fragment-based identification of druggable 'hot spots' of proteins",
      "Bioinformatics 2009. Computational fragment-mapping approach to hot "
      "spot / druggability prediction.",
      "https://academic.oup.com/bioinformatics/article/25/5/621/183466", 2009)
paper("pmc6270832_docking_review",
      "Challenges, Applications, and Recent Advances of Protein-Ligand "
      "Docking in Structure-Based Drug Design",
      "Review covering docking scoring-function and sampling limitations.",
      "https://pmc.ncbi.nlm.nih.gov/articles/PMC6270832/", 2018)
paper("cosb2018_docking_to_md",
      "Protein structure-based drug design: from docking to molecular "
      "dynamics",
      "Current Opinion in Structural Biology review on moving from a naive "
      "dock to MD-based refinement and free-energy estimation.",
      "https://www.sciencedirect.com/science/article/abs/pii/S0959440X17301100",
      2018)
paper("bond_practical_guide",
      "A Practical Guide to Molecular Docking and Homology Modelling for "
      "Medicinal Chemists",
      "Introductory, chemist-facing guide to running and sanity-checking "
      "docking/homology modelling.",
      "https://pure.bond.edu.au/ws/files/12803722/"
      "A_practical_guide_to_molecular_docking_and_homology_modelling_for_medicinal_chemists.pdf",
      2018)

# ---- Edges ------------------------------------------------------------
rel("bioinf2009_hotspots", "introduces", "hot_spot")
rel("nakamura2021_hotspots", "extends", "hot_spot")
rel("bioinf2009_hotspots", "uses_method", "fragment_based_screening")
rel("fragment_based_screening", "identifies", "hot_spot")
rel("hot_spot", "anchors", "pharmacophore")
rel("hot_spot", "informs", "druggability", note="hit-rate in fragment screens")

rel("water_displacement", "contributes_to", "binding_free_energy")
rel("electrostatic_complementarity", "contributes_to", "binding_free_energy")
rel("shape_complementarity", "insufficient_for", "binding_free_energy")

rel("induced_fit", "causes", "cryptic_pocket")
rel("rigid_receptor_docking", "fails_under", "induced_fit")
rel("rigid_receptor_docking", "fails_under", "cryptic_pocket")
rel("rigid_receptor_docking", "fails_under", "pocket_flexibility")
rel("docking", "has_limitation", "rigid_receptor_docking")
rel("docking", "has_limitation", "scoring_function_limitations")
rel("conformational_ensemble_docking", "mitigates", "rigid_receptor_docking")
rel("pocket_flexibility", "extends", "induced_fit",
    note="operationalizes induced fit as a measurable score across "
    "structures/frames, not just a qualitative risk")
rel("pocket_flexibility", "informs", "conformational_ensemble_docking",
    note="plasticity score above threshold makes ensemble docking mandatory")
rel("mdpocket", "identifies", "pocket_flexibility")
rel("docking", "refined_by", "molecular_dynamics_refinement")
rel("molecular_dynamics_refinement", "estimates", "binding_free_energy")
rel("free_energy_perturbation", "rigorous_variant_of",
    "molecular_dynamics_refinement")
rel("free_energy_perturbation", "estimates", "binding_free_energy")

rel("pmc6270832_docking_review", "discusses", "scoring_function_limitations")
rel("pmc6270832_docking_review", "discusses", "docking")
rel("cosb2018_docking_to_md", "discusses", "molecular_dynamics_refinement")
rel("cosb2018_docking_to_md", "discusses", "docking")
rel("bond_practical_guide", "explains", "docking")


def main():
    out_dir = Path(__file__).parent
    data = nx.node_link_data(G, edges="edges")
    (out_dir / "graph.json").write_text(json.dumps(data, indent=2))
    print(f"nodes={G.number_of_nodes()} edges={G.number_of_edges()}")
    print(f"wrote {out_dir / 'graph.json'}")


if __name__ == "__main__":
    main()
