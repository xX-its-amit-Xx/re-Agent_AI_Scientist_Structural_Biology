from rdkit import Chem
from rdkit.Chem import AllChem
from rdkit.Chem.Draw import rdMolDraw2D

OUT = "/home/dsch/Downloads/re-Agent_AI_Scientist_Structural_Biology/sbdd_kg"

fragments = [
    ("x0001", "c1ccc2[nH]ccc2c1"),
    ("x0002", "O=C(N)c1ccncc1"),
    ("x0003", "Clc1ccc(cc1)S(=O)(=O)N"),
    ("x0004", "c1ccc(cc1)C(=O)O"),
    ("x0005", "CC(C)n1cnc2c1cccc2"),
    ("x0006", "Nc1ncnc2[nH]ccc12"),
]

for frag_id, smiles in fragments:
    mol = Chem.MolFromSmiles(smiles)
    AllChem.Compute2DCoords(mol)
    drawer = rdMolDraw2D.MolDraw2DCairo(240, 180)
    opts = drawer.drawOptions()
    opts.bondLineWidth = 2
    opts.padding = 0.15
    opts.clearBackground = True
    rdMolDraw2D.PrepareAndDrawMolecule(drawer, mol)
    drawer.FinishDrawing()
    with open(f"{OUT}/fig_frag_{frag_id}.png", "wb") as f:
        f.write(drawer.GetDrawingText())

print("done", len(fragments))
