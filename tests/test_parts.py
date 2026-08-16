"""Stage 2 anatomy: parts accounting, the interaction grid, and edge commentary.

The theme matches Stage 1's: each check exists because a plausible-looking Stage 2 report could
otherwise pass while hiding what it never examined.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from reagent.contracts.kg import (
    PREDICATE_DOMAINS,
    Confidence,
    Edge,
    GraphDelta,
    Node,
    NodeType,
    Predicate,
)
from reagent.contracts.parts import (
    PARTITION_KINDS,
    Anatomy,
    ContactKind,
    ContactObservation,
    InteractionCell,
    InteractionMatrix,
    Part,
    PartKind,
    PartsInventory,
)

# ---------------------------------------------------------------------------
# Parts and atom accounting
# ---------------------------------------------------------------------------


def _inv(**kw) -> PartsInventory:
    base = dict(
        entity_id="chembl:X", entity_kind="compound",
        universe=[str(i) for i in range(10)],
        parts=[
            Part(id="p:scaf", kind=PartKind.SCAFFOLD, of="chembl:X", label="core",
                 covers=[str(i) for i in range(7)]),
            Part(id="p:sub", kind=PartKind.SUBSTITUENT, of="chembl:X", label="methoxy",
                 covers=["7", "8", "9"]),
        ],
    )
    return PartsInventory(**{**base, **kw})


def test_a_complete_inventory_has_no_problems():
    inv = _inv()
    assert inv.coverage == 1.0
    assert inv.unassigned() == []
    assert inv.problems() == []


def test_unassigned_atoms_are_named():
    inv = _inv(universe=[str(i) for i in range(12)])
    assert inv.unassigned() == ["10", "11"]
    assert any("unassigned" in p for p in inv.problems())


def test_partition_kinds_must_say_what_they_cover():
    """A partition member covering nothing breaks the accounting silently."""
    with pytest.raises(ValidationError, match="must tile its entity"):
        Part(id="p:x", kind=PartKind.SCAFFOLD, of="chembl:X", label="core", covers=[])


def test_relation_kinds_may_cover_nothing():
    """A rotatable bond describes a relation, not a region."""
    p = Part(id="p:rb", kind=PartKind.ROTATABLE_BOND, of="chembl:X", label="C3-C4")
    assert p.n_covered == 0
    assert PartKind.ROTATABLE_BOND not in PARTITION_KINDS


def test_atoms_outside_the_universe_are_flagged_as_probable_index_mismatch():
    inv = _inv(parts=[
        Part(id="p:scaf", kind=PartKind.SCAFFOLD, of="chembl:X", label="core",
             covers=[str(i) for i in range(1, 11)]),  # 1-indexed against a 0-indexed universe
    ])
    assert inv.foreign() == ["10"]
    assert any("index-base mismatch" in p for p in inv.problems())


def test_partition_overlap_is_a_bug_but_functional_group_overlap_is_not():
    overlapping = _inv(parts=[
        Part(id="p:a", kind=PartKind.SCAFFOLD, of="chembl:X", label="core",
             covers=[str(i) for i in range(8)]),
        Part(id="p:b", kind=PartKind.SUBSTITUENT, of="chembl:X", label="tail",
             covers=["7", "8", "9"]),   # atom 7 claimed twice
    ])
    assert list(overlapping.partition_overlaps()) == ["7"]
    assert any("two partition parts" in p for p in overlapping.problems())

    # An amide is legitimately both a carbonyl and an N-H.
    fine = _inv(parts=[*_inv().parts,
        Part(id="p:c=o", kind=PartKind.FUNCTIONAL_GROUP, of="chembl:X", label="carbonyl",
             covers=["4", "5"]),
        Part(id="p:nh", kind=PartKind.FUNCTIONAL_GROUP, of="chembl:X", label="N-H",
             covers=["5", "6"]),
    ])
    assert fine.partition_overlaps() == {}
    assert fine.problems() == []


def test_lazy_exclusions_are_rejected():
    inv = _inv(universe=[str(i) for i in range(12)],
               out_of_scope={"10": "not interesting", "11": "n/a"})
    assert inv.unassigned() == []          # excluded counts as accounted for
    assert any("no real reason" in p for p in inv.problems())


def test_a_real_exclusion_passes():
    inv = _inv(universe=[str(i) for i in range(11)], out_of_scope={
        "10": "solvent-exposed methyl; no lining residue within 8 A in any holo structure",
    })
    assert inv.problems() == []


def test_orphan_parents_are_caught():
    inv = _inv(parts=[
        Part(id="p:scaf", kind=PartKind.SCAFFOLD, of="chembl:X", label="core",
             covers=[str(i) for i in range(10)], parent="p:missing"),
    ])
    assert inv.orphan_parents() == ["p:missing"]


def test_an_empty_universe_makes_completeness_uncheckable():
    inv = PartsInventory(entity_id="chembl:X", entity_kind="compound", universe=[])
    assert any("empty universe" in p for p in inv.problems())


def test_part_kind_sides_are_partitioned():
    protein = {k for k in PartKind if k.side == "protein"}
    compound = {k for k in PartKind if k.side == "compound"}
    assert protein and compound
    assert not protein & compound
    assert protein | compound == set(PartKind)


# ---------------------------------------------------------------------------
# The interaction grid
# ---------------------------------------------------------------------------


def _obs(kind=ContactKind.HBOND_ACCEPTOR, source="plip", structure="pdb:1M13"):
    return ContactObservation(kind=kind, structure_id=structure, source=source, distance_a=2.9)


def test_observations_require_the_measured_flag():
    with pytest.raises(ValidationError, match="marked unmeasured"):
        InteractionCell(compound_part="f1", protein_part="s1", observations=[_obs()])


def test_out_of_scope_with_observations_is_contradictory():
    with pytest.raises(ValidationError, match="evidently in scope"):
        InteractionCell(compound_part="f1", protein_part="s1", measured=True,
                        observations=[_obs()], out_of_scope_because="unreachable")


def test_measured_empty_is_a_finding_and_unmeasured_is_not():
    empty = InteractionCell(compound_part="f1", protein_part="s1", measured=True,
                            n_complexes_examined=5)
    unknown = InteractionCell(compound_part="f1", protein_part="s2")
    assert empty.is_empty_finding
    assert not unknown.is_empty_finding


def test_source_count_is_the_confidence_signal():
    one = InteractionCell(compound_part="f1", protein_part="s1", measured=True,
                          observations=[_obs(source="plip")])
    two = InteractionCell(compound_part="f1", protein_part="s1", measured=True,
                          observations=[_obs(source="plip"), _obs(source="prolif")])
    assert one.is_single_source and one.n_sources == 1
    assert not two.is_single_source and two.n_sources == 2


def test_recurrence_counts_distinct_structures():
    cell = InteractionCell(
        compound_part="f1", protein_part="s1", measured=True, n_complexes_examined=4,
        observations=[_obs(structure="pdb:1M13"), _obs(structure="pdb:1M13", source="prolif"),
                      _obs(structure="pdb:1NRL")],
    )
    assert cell.recurrence == pytest.approx(2 / 4)


def test_directional_kinds_are_the_ones_that_constrain_a_pose():
    assert ContactKind.HBOND_ACCEPTOR.is_directional
    assert ContactKind.PI_STACKING.is_directional
    assert not ContactKind.HYDROPHOBIC.is_directional


def _matrix(**kw) -> InteractionMatrix:
    base = dict(
        compound_id="chembl:X", target_id="uniprot:O75469",
        compound_parts=["f1", "f2"], protein_parts=["s1", "s2"],
        profilers=["plip", "prolif"],
        cells=[
            # Two contacts: one both profilers see, one only PLIP does. 50% agreement, which
            # is the healthy band around the ~47% reference — a fixture at 100% would trip
            # the not-independent check, and rightly.
            InteractionCell(compound_part="f1", protein_part="s1", measured=True,
                            n_complexes_examined=3,
                            observations=[_obs(source="plip"), _obs(source="prolif")]),
            InteractionCell(compound_part="f1", protein_part="s2", measured=True,
                            n_complexes_examined=3,
                            observations=[_obs(kind=ContactKind.HYDROPHOBIC, source="plip")]),
            InteractionCell(compound_part="f2", protein_part="s1", measured=True,
                            n_complexes_examined=3),
            InteractionCell(compound_part="f2", protein_part="s2", measured=True,
                            n_complexes_examined=3),
        ],
    )
    return InteractionMatrix(**{**base, **kw})


def test_full_grid_reports_complete_coverage():
    m = _matrix()
    assert m.n_possible == 4
    assert m.cell_coverage == 1.0
    assert m.missing_cells() == []
    assert m.problems() == []


def test_absent_cells_are_worse_than_unmeasured_and_are_named():
    m = _matrix(cells=_matrix().cells[:2])
    assert set(m.missing_cells()) == {("f2", "s1"), ("f2", "s2")}
    assert any("no status at all" in p for p in m.problems())


def test_a_part_engaging_nothing_is_only_reported_when_fully_measured():
    m = _matrix()
    # f2 was measured against both protein parts and engaged neither.
    assert m.parts_touching_nothing() == ["f2"]

    # Drop one of f2's cells: "engages nothing we looked at" is not "engages nothing".
    partial = _matrix(cells=[c for c in _matrix().cells
                             if (c.compound_part, c.protein_part) != ("f2", "s2")])
    assert partial.parts_touching_nothing() == []


def test_one_profiler_is_a_sample_not_a_measurement():
    m = _matrix(profilers=["plip"])
    assert any("47%" in p for p in m.problems())


def test_healthy_agreement_sits_near_the_reference_and_is_not_flagged():
    m = _matrix()
    assert m.profiler_agreement() == pytest.approx(0.5)
    assert not any("agreement" in p for p in m.problems())


def test_suspiciously_high_profiler_agreement_is_flagged():
    """Above the ~47% reference usually means the profilers read the same upstream geometry
    and are not independent — spurious agreement destroys the signal it appears to give."""
    both = [_obs(source="plip"), _obs(source="prolif")]
    m = _matrix(cells=[
        InteractionCell(compound_part=cp, protein_part=pp, measured=True,
                        n_complexes_examined=3, observations=list(both))
        for cp in ("f1", "f2") for pp in ("s1", "s2")
    ])
    assert m.profiler_agreement() == 1.0
    assert any("genuinely independent" in p for p in m.problems())


def test_low_profiler_agreement_is_flagged_as_probable_misconfiguration():
    cells = _matrix().cells
    cells[1] = InteractionCell(compound_part="f1", protein_part="s2", measured=True,
                               n_complexes_examined=3, observations=[_obs(source="plip")])
    cells[2] = InteractionCell(compound_part="f2", protein_part="s1", measured=True,
                               n_complexes_examined=3, observations=[_obs(source="plip")])
    cells[3] = InteractionCell(compound_part="f2", protein_part="s2", measured=True,
                               n_complexes_examined=3, observations=[_obs(source="plip")])
    cells[0] = InteractionCell(compound_part="f1", protein_part="s1", measured=True,
                               n_complexes_examined=3, observations=[_obs(source="plip")])
    m = _matrix(cells=cells)
    assert m.profiler_agreement() == 0.0
    assert any("misconfigured" in p for p in m.problems())


def test_unmeasured_cells_are_distinguished_from_out_of_scope():
    cells = _matrix().cells
    cells[3] = InteractionCell(compound_part="f2", protein_part="s2")
    m = _matrix(cells=cells)
    assert m.unmeasured_cells() == [("f2", "s2")]
    assert m.cell_coverage == 0.75

    cells[3] = InteractionCell(compound_part="f2", protein_part="s2",
                               out_of_scope_because="14 A apart in every holo structure")
    m2 = _matrix(cells=cells)
    assert m2.unmeasured_cells() == []
    assert m2.cell_coverage == 1.0


# ---------------------------------------------------------------------------
# Batch-level completeness
# ---------------------------------------------------------------------------


def _anatomy(**kw) -> Anatomy:
    target_inv = PartsInventory(
        entity_id="uniprot:O75469", entity_kind="protein",
        universe=["residue:Ser247", "residue:Met243"],
        parts=[Part(id="sp:polar", kind=PartKind.SUBPOCKET, of="pocket:X", label="polar rim",
                    covers=["residue:Ser247", "residue:Met243"])],
    )
    base = dict(
        run_id="r1", target_id="uniprot:O75469", target_inventory=target_inv,
        test_batch=["chembl:A", "chembl:B"],
        compound_inventories=[_inv(entity_id="chembl:A"), _inv(entity_id="chembl:B")],
        matrices=[_matrix(compound_id="chembl:A"), _matrix(compound_id="chembl:B")],
    )
    return Anatomy(**{**base, **kw})


def test_a_complete_anatomy_passes():
    a = _anatomy()
    assert a.batch_coverage() == 1.0
    assert a.problems() == []


def test_skipping_test_compounds_is_named():
    a = _anatomy(compound_inventories=[_inv(entity_id="chembl:A")])
    assert a.uninventoried_compounds() == ["chembl:B"]
    assert any("never decomposed" in p for p in a.problems())


def test_a_compound_with_no_matrix_is_named_separately():
    a = _anatomy(matrices=[_matrix(compound_id="chembl:A")])
    assert a.unmatrixed_compounds() == ["chembl:B"]
    assert any("no interaction matrix" in p for p in a.problems())


# ---------------------------------------------------------------------------
# Edge commentary — what a side-by-side view displays
# ---------------------------------------------------------------------------


GOOD = (
    "Both present an acceptor at the same depth, so a pose that misplaces the Ser247 hydrogen "
    "bond is wrong for both."
)


def test_commentary_is_optional():
    e = Edge(src="a:1", predicate=Predicate.PART_OF, dst="b:1", asserted_by="t")
    assert e.commentary is None


def test_a_real_reading_is_accepted():
    e = Edge(src="a:1", predicate=Predicate.CONTACTS, dst="b:1", asserted_by="t",
             commentary=GOOD)
    assert e.commentary.startswith("Both present")


def test_commentary_that_restates_the_predicate_is_rejected():
    for bad in (
        "the two nodes are similar",
        "these proteins share a motif",
        "is related",
        "both are nuclear receptors",
    ):
        with pytest.raises(ValidationError, match="restates the connection"):
            Edge(src="a:1", predicate=Predicate.SHARES_MOTIF, dst="b:1",
                 asserted_by="t", commentary=bad)


def test_blank_commentary_normalises_to_none():
    e = Edge(src="a:1", predicate=Predicate.PART_OF, dst="b:1", asserted_by="t",
             commentary="   ")
    assert e.commentary is None


# ---------------------------------------------------------------------------
# The anatomy predicates live in the same graph as Stage 1
# ---------------------------------------------------------------------------


ANATOMY_PREDICATES = (
    Predicate.PART_OF, Predicate.HAS_PHARMACOPHORE, Predicate.CONTACTS,
    Predicate.OCCUPIES, Predicate.COMPLEMENTARY_TO,
)


def test_every_anatomy_predicate_is_registered():
    for p in ANATOMY_PREDICATES:
        assert p in PREDICATE_DOMAINS, f"{p.value} has no endpoint types"


def test_contacts_cannot_start_at_a_protein():
    """A protein contacting a residue is a category error the type table should catch."""
    delta = GraphDelta(
        run_id="r", asserted_by="t",
        nodes=[
            Node(id="uniprot:X", type=NodeType.PROTEIN, label="X", asserted_by="t"),
            Node(id="residue:X/Ser1", type=NodeType.RESIDUE, label="Ser1", asserted_by="t"),
        ],
        edges=[Edge(src="uniprot:X", predicate=Predicate.CONTACTS, dst="residue:X/Ser1",
                    asserted_by="t")],
    )
    problems = delta.validate_referential_integrity()
    assert any("cannot start at a Protein" in p for p in problems)


def test_a_fragment_contacting_a_residue_is_legal():
    delta = GraphDelta(
        run_id="r", asserted_by="t",
        nodes=[
            Node(id="fragment:smarts:[OH]", type=NodeType.FRAGMENT, label="OH",
                 asserted_by="t"),
            Node(id="residue:X/Ser1", type=NodeType.RESIDUE, label="Ser1", asserted_by="t"),
        ],
        edges=[Edge(src="fragment:smarts:[OH]", predicate=Predicate.CONTACTS,
                    dst="residue:X/Ser1", asserted_by="t",
                    attrs={"interaction": "hbond_acceptor"}, confidence=Confidence.TENTATIVE,
                    commentary=GOOD)],
    )
    assert delta.validate_referential_integrity() == []


def test_part_of_is_deliberately_unrestricted():
    """The hierarchy spans both substrates, so enumerating legal pairs would be a table
    nobody keeps current."""
    assert PREDICATE_DOMAINS[Predicate.PART_OF] == (None, None)
