
import json, sys
from ost.mol.alg.ligand_scoring import LDDTPLIScorer, SCRMSDScorer
from ost.mol.alg.scoring_base import PDBPrep

out = []
for model_path, ref_path, sid in json.load(open(sys.argv[1])):
    try:
        model = PDBPrep(model_path, fault_tolerant=True)
        ref = PDBPrep(ref_path, fault_tolerant=True)
        ml, rl = model.Select("rname=LIG"), ref.Select("rname=LIG")
        scr = SCRMSDScorer(model=model, target=ref, model_ligands=[ml], target_ligands=[rl])
        pli = LDDTPLIScorer(model=model, target=ref, model_ligands=[ml], target_ligands=[rl])
        rows = []
        for i, j in scr.assignment:
            rows.append({
                "LDDT-PLI": float(pli.score_matrix[i, j]),
                "BiSyRMSD": float(scr.score_matrix[i, j]),
                "LDDT-LP": float(scr.aux_matrix[i, j]["lddt_lp"]),
            })
        # rank as the organizers do: best LDDT-PLI, then lowest BiSyRMSD
        rows.sort(key=lambda r: (-r["LDDT-PLI"], r["BiSyRMSD"]))
        out.append({"Molecule Name": sid, **(rows[0] if rows else {})})
    except Exception as e:
        out.append({"Molecule Name": sid, "error": str(e)})
print("@@JSON@@" + json.dumps(out))
