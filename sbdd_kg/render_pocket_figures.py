from pymol import cmd

OUT = "/home/dsch/Downloads/re-Agent_AI_Scientist_Structural_Biology/sbdd_kg"

# ---------------------------------------------------------------------------
# Figure A: pocket conformational overlay (real PXR-LBD structures, 3 states)
# ---------------------------------------------------------------------------
cmd.reinitialize()
cmd.bg_color("white")
cmd.set("ray_opaque_background", 1)

states = [
    ("1ILH", "holo_sr12813", "orange", "SR12813-bound"),
    ("8SVN", "apo", "skyblue", "apo"),
    ("8FPE", "holo_t0bp", "purple", "T0-BP-bound"),
]

for pdb_id, obj, color, _ in states:
    cmd.fetch(pdb_id, obj, type="pdb")
    cmd.remove(f"{obj} and not polymer")
    cmd.remove(f"{obj} and not chain A")

# align everything onto the first (SR12813) structure using a rigid core
# (helices away from AF-2/lid) so the AF-2 helix + lid displacement is what
# remains visible, not just alignment noise
cmd.create("ref", "holo_sr12813")
for pdb_id, obj, color, _ in states[1:]:
    cmd.align(f"{obj} and resi 145-400", "ref and resi 145-400")

cmd.hide("everything")
for pdb_id, obj, color, _ in states:
    cmd.show("cartoon", obj)
    cmd.color(color, obj)
    cmd.color("firebrick" if obj != "apo" else "red", f"{obj} and resi 407-422")  # AF-2 helix
    cmd.color("yellow", f"{obj} and resi 245-260")  # lid

cmd.hide("everything", "ref")
cmd.orient("holo_sr12813")
cmd.zoom("holo_sr12813 and resi 140-434", buffer=8)
cmd.set("cartoon_transparency", 0.35, "apo")
cmd.ray(1500, 1150)
cmd.png(f"{OUT}/fig_pocket_overlay.png", dpi=150)

# ---------------------------------------------------------------------------
# Figure B: per-residue confidence map (B-factor - real crystal, not pLDDT)
# ---------------------------------------------------------------------------
cmd.reinitialize()
cmd.bg_color("white")
cmd.set("ray_opaque_background", 1)
cmd.fetch("1ilh", "target", type="pdb")
cmd.remove("target and not polymer")
cmd.remove("target and not chain A")
cmd.hide("everything")
cmd.show("cartoon", "target")
cmd.spectrum("b", "blue_white_red", "target")
cmd.orient("target")
cmd.ray(1500, 1150)
cmd.png(f"{OUT}/fig_bfactor_confidence.png", dpi=150)

print("done")
