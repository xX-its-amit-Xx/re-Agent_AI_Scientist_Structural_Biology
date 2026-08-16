# The operations

For each: what it does to the file, its **checkable postcondition**, and how it fails. The
postcondition column is the reason typed operations exist — it is what a check can assert and
what free-text coordinate editing does not have.

---

## Rigid, cannot break internal geometry

### `RIGID_TRANSLATE`
**File:** adds a constant vector to every selected atom's x/y/z.
**Params:** `dx`, `dy`, `dz` in Å.
**Postcondition:** all internal distances unchanged; centroid moved by exactly the vector.
**Fails when** the selection is wrong — translating half a ligand tears it apart while leaving
every *checked* internal distance within the moved fragment intact. **Verify the selection covers
the whole rigid body.**
**Use for** a pose in the right sub-pocket sitting 1–2 Å off.

### `RIGID_ROTATE`
**File:** rotation matrix about an axis through a point.
**Params:** `axis`, `angle_deg`, `origin` (defaults to the selection centroid).
**Postcondition:** all internal distances unchanged; RMSD to the original equals the expected
rotation displacement.
**Fails when** the origin defaults to a centroid that is not the intended pivot, which rotates and
translates at once. State the origin.
**Use for** a pose flipped end-to-end in the pocket — common, and a model rarely fixes it.

### `OCCUPANCY_SET`
**File:** rewrites the occupancy column.
**Postcondition:** coordinates byte-identical.
**Fails when** the format's column width is violated. Use a writer, not string slicing.

---

## Changes internal geometry, in a controlled way

### `TORSION_SET`
**File:** rotates one branch about a rotatable bond.
**Params:** the four atoms defining the dihedral, and `angle_deg`.
**Postcondition:** exactly one dihedral changed; all bond lengths and angles unchanged; the
smaller branch moved.
**Fails when** the bond is in a ring — rotating it distorts the ring rather than moving a branch,
and bond lengths *will* change. Check ring membership first.
**Also fails when** it rotates the larger branch, which is geometrically identical and moves the
whole molecule relative to the pocket. Rotate the smaller side.
**Use for** one substituent clashing where a rotation relieves it. The workhorse operation.

### `ROTAMER_SWAP`
**File:** replaces a side chain's coordinates with a library rotamer's.
**Params:** residue, `rotamer_id`.
**Postcondition:** backbone atoms unchanged; side-chain geometry matches the library entry;
chirality preserved.
**Fails when** the backbone drifts, which means the rotamer was applied without superposing on
N-CA-C. Check the backbone is byte-identical.
**Use for** a side chain occluding the ligand where a library rotamer does not. Library-constrained,
so it lands somewhere real — which is why this is safer than a free side-chain adjustment.

### `AMIDE_FLIP`
**File:** 180° rotation about the C–N axis, swapping O and N positions.
**Postcondition:** heavy-atom composition unchanged; the amide plane preserved; O and N swapped.
**Fails when** applied to something that is not an amide, or when the flip is applied to only one
of the two atoms.
**Use for** an amide 180° out. Genuinely common, genuinely hard for a model to fix, and discrete —
so the check is unambiguous.

### `RING_FLIP`
**File:** switches ring pucker — chair to alternate chair, or boat.
**Postcondition:** ring bond lengths and angles within tolerance; ring atoms' relative
configuration preserved; substituent axial/equatorial assignments swapped.
**Fails when** it inverts a stereocentre in the ring, which `chirality_preserved` catches. That
check is the reason this operation is tolerable.

---

## Changes the molecule, not just its shape

**All four of these set `changes_the_graph`, and a submission validator that notices will reject
the entry — which scores zero rather than badly.** Prefer fixing them upstream.

### `PROTONATION_CHANGE`
**File:** adds or removes hydrogens; may change formal charge.
**Postcondition:** heavy-atom coordinates unchanged; formal charge as intended.
**Fails when** the receiving scorer assumes a different protonation than the one written, which
produces phantom clashes. Most apparent clashes are this.
**Better fixed** in input preparation, where it is free.

### `TAUTOMER_CHANGE`
**File:** moves a hydrogen and shifts bond orders.
**Postcondition:** molecular formula unchanged; the intended tautomer canonicalises correctly.
**Fails silently** in formats that do not carry bond orders — the file looks fine and the
downstream tool infers the original tautomer.

### `STEREO_INVERT`
**File:** reflects substituents at a centre.
**Postcondition:** the CIP descriptor changed to the intended one and nothing else did.
**Almost always the wrong operation.** If the stereochemistry is wrong, the *input* was wrong, and
inverting it here fixes one file while the pipeline keeps producing the error. Fix the SMILES
round-trip.

### `ATOM_DELETE`
**File:** removes records.
**Postcondition:** the remaining graph is a valid molecule; no dangling valences; numbering
consistent.
**Legitimate use:** a crystallisation artefact passed in as the ligand — glycerol, PEG, DMSO. That
is a `binder-census` failure being corrected late, and it should be corrected there.
**Fails when** deleting an atom leaves an implicit-hydrogen count that no longer parses.

---

## The escape hatch

### `RAW_COORDINATE`
**File:** direct assignment of x/y/z.
**Postcondition:** none intrinsic. Every check has to carry it.
**Requires** `escalation_note` — enforced — saying why no typed operation expresses the fix.

**This is the operation that took a pose from 3.88 Å to 24.63 Å.** The failure mode is not a
slightly wrong number; it is a model writing plausible-looking coordinates that describe an
impossible molecule, and reporting success. `OptimizationRun.problems()` reports any that
survived, because each one needs a human reviewer rather than an escalation note.

**Before using it, check that the fix is not actually:**

| What it looks like | What it usually is |
|---|---|
| "the ligand needs to be over here" | `RIGID_TRANSLATE` |
| "this group should point the other way" | `TORSION_SET` |
| "this side chain is in the way" | `ROTAMER_SWAP` |
| "the whole pose is wrong" | not surgery — a `pocket_collapsed` or placement failure, and `hypothesis-experiment`'s ladder handles it |

That last row is the important one. **Local refinement cannot fix a placement error** — MD did not
recover a 2 Å translation on the reference case — and neither will editing coordinates by hand.
Reaching for raw coordinates on a badly placed pose is trying to solve a generation problem with a
text editor.

---

## Choosing among them

Least powerful operation that addresses the named defect. In practice:

1. Can a rigid move fix it? Use one — they cannot break internal geometry at all.
2. Is it one substituent? `TORSION_SET`.
3. Is it a protein side chain? `ROTAMER_SWAP`.
4. Is it a discrete flip? `AMIDE_FLIP` or `RING_FLIP`.
5. Is it a graph problem? Fix it upstream, not here.
6. Otherwise it is probably not a surgery problem.

`EditOp.severity` maps these to keep / light / drastic for the medchem tiering, and the
distribution across a pass is a required figure — a pass that is mostly drastic is a pass to
distrust before reading its delta.
