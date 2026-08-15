"""Tests for the MCP server, the structure layer, and the 3D comparison renderer.

The protocol tests run the real message flow through ``Server.handle`` rather than a
subprocess, so they are fast and still catch the mistakes that actually break a
client: answering a notification, using JSON-RPC errors for tool failures, and
letting anything reach stdout.

Structure tests use a hand-written miniature PDB rather than the network, so the
suite stays offline and deterministic. The one thing they cannot check is real
biology; that is verified by hand against known structures and recorded in the
report-mcp skill.
"""

from __future__ import annotations

import io
import json

import numpy as np
import pytest

from reagent.mcp import tools as toolmod
from reagent.mcp.server import Server
from reagent.structure import kabsch, needleman_wunsch, parse_pdb, superpose
from reagent.structure.align import pocket_comparison, tm_score

# --------------------------------------------------------------------------
# protocol
# --------------------------------------------------------------------------


def _init(server: Server) -> dict:
    return server.handle({
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2025-06-18",
                   "clientInfo": {"name": "test", "version": "1"}, "capabilities": {}},
    })


def test_initialize_returns_a_usable_handshake():
    r = _init(Server())
    res = r["result"]
    assert r["jsonrpc"] == "2.0" and r["id"] == 1
    assert res["protocolVersion"] == "2025-06-18"
    assert res["serverInfo"]["name"] == "reagent-report"
    assert "tools" in res["capabilities"]
    # The instructions are where a relaying model learns the caveats, so they must
    # actually mention them.
    instr = res["instructions"].lower()
    assert "estimate" in instr and "illustrative" in instr


def test_unknown_protocol_version_falls_back_rather_than_failing():
    s = Server()
    r = s.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                  "params": {"protocolVersion": "1999-01-01"}})
    assert r["result"]["protocolVersion"] == "2025-06-18"


def test_notifications_get_no_reply():
    """Answering a notification is a protocol violation."""
    s = Server()
    _init(s)
    assert s.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    assert s.handle({"jsonrpc": "2.0", "method": "notifications/somethingUnknown"}) is None


def test_unknown_request_gets_a_jsonrpc_error():
    r = Server().handle({"jsonrpc": "2.0", "id": 7, "method": "nope/nope"})
    assert r["error"]["code"] == -32601


def test_every_tool_has_a_strict_schema_and_a_routing_description():
    for t in toolmod.tool_schemas():
        schema = t["inputSchema"]
        assert schema["type"] == "object"
        assert schema["additionalProperties"] is False, (
            f"{t['name']}: a permissive schema silently drops mis-typed arguments"
        )
        assert len(t["description"]) > 60, f"{t['name']}: description too thin to route on"
        for req in schema.get("required", []):
            assert req in schema["properties"], f"{t['name']}: required {req} not declared"


def test_tool_names_match_the_registry():
    assert {t["name"] for t in toolmod.tool_schemas()} == set(toolmod.REGISTRY)


def test_tool_failure_is_a_result_not_a_transport_error():
    """isError reaches the model; a JSON-RPC error may be treated as fatal."""
    s = Server()
    _init(s)
    r = s.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                  "params": {"name": "report_read", "arguments": {"path": "nope.json"}}})
    assert "error" not in r
    assert r["result"]["isError"] is True
    assert "nope.json" in r["result"]["content"][0]["text"]


def test_unknown_tool_lists_the_real_ones():
    s = Server()
    _init(s)
    r = s.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                  "params": {"name": "does_not_exist", "arguments": {}}})
    text = r["result"]["content"][0]["text"]
    assert r["result"]["isError"] is True
    assert "compare_structures" in text, "an unknown-tool error should name the alternatives"


def test_bad_arguments_return_the_schema():
    """The model's next action depends on the error text, so give it the schema."""
    s = Server()
    _init(s)
    r = s.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                  "params": {"name": "explain_edge", "arguments": {"bogus": 1}}})
    text = r["result"]["content"][0]["text"]
    assert r["result"]["isError"] is True
    assert "inputSchema" in text or "predicate" in text


def test_serve_writes_only_protocol_messages_to_stdout():
    """Any non-JSON line on stdout disconnects a real client."""
    msgs = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2025-06-18"}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    ]
    stdin = io.StringIO("".join(json.dumps(m) + "\n" for m in msgs))
    stdout = io.StringIO()
    Server().serve(stdin=stdin, stdout=stdout)
    lines = [ln for ln in stdout.getvalue().splitlines() if ln.strip()]
    assert len(lines) == 2, "the notification must not be answered"
    for ln in lines:
        parsed = json.loads(ln)          # raises if anything non-protocol leaked
        assert parsed["jsonrpc"] == "2.0"


# --------------------------------------------------------------------------
# structure parsing and maths
# --------------------------------------------------------------------------


def _mini_pdb(offset: float = 0.0, seq: str = "AAAAA") -> str:
    """Five residues on a line, plus a small ligand. Enough to exercise the geometry."""
    three = {"A": "ALA", "G": "GLY", "S": "SER", "V": "VAL", "W": "TRP"}
    lines = ["TITLE     MINIATURE TEST STRUCTURE"]
    n = 1
    for i, aa in enumerate(seq, start=1):
        for atom, dx in (("N", -0.5), ("CA", 0.0), ("C", 0.5)):
            x = i * 3.8 + dx + offset
            lines.append(
                f"ATOM  {n:5d}  {atom:<3s} {three[aa]} A{i:4d}    "
                f"{x:8.3f}{0.0:8.3f}{0.0:8.3f}  1.00 50.00           {atom[0]}"
            )
            n += 1
    # A three-atom ligand sitting beside residues 2-4.
    for k, x in enumerate((7.6, 9.5, 11.4)):
        lines.append(
            f"HETATM{n + k:5d}  C{k + 1:<2d} LIG A 900    "
            f"{x + offset:8.3f}{3.0:8.3f}{0.0:8.3f}  1.00 30.00           C"
        )
    lines.append("END")
    return "\n".join(lines)


def test_parse_pdb_reads_residues_and_ligands():
    st = parse_pdb(_mini_pdb(), "test:1", "unit test")
    assert st.title == "MINIATURE TEST STRUCTURE"
    assert st.longest_chain() == "A"
    assert len(st.chains["A"]) == 5
    assert st.sequence("A") == "AAAAA"
    r = st.chains["A"][0]
    assert r.label == "Ala1" and r.ca is not None and set(r.atoms) == {"N", "CA", "C"}
    assert len(st.ligands) == 1 and st.ligands[0].name3 == "LIG"


def test_solvent_is_not_treated_as_a_ligand():
    pdb = _mini_pdb() + "\nHETATM 9001  O   HOH A 950      5.000   5.000   5.000  1.00 20.00           O"
    st = parse_pdb(pdb, "test:1", "unit test")
    assert any(lg.name3 == "HOH" for lg in st.ligands)
    assert st.primary_ligand() is None, "a 3-atom ligand is below the size floor"


def test_residues_near_uses_all_points_not_a_centroid():
    """The centroid of an extended ligand is far from most of its contacts."""
    st = parse_pdb(_mini_pdb(), "test:1", "unit test")
    lig = st.ligands[0]
    from_centroid = st.residues_near(lig.centroid, 4.0)
    from_all_atoms = st.residues_near(lig.coords, 4.0)
    assert len(from_all_atoms) >= len(from_centroid)


def test_kabsch_recovers_a_known_rigid_transform():
    rng = np.random.default_rng(0)
    P = rng.normal(size=(12, 3)) * 5
    theta = 0.7
    R_true = np.array([[np.cos(theta), -np.sin(theta), 0],
                       [np.sin(theta), np.cos(theta), 0], [0, 0, 1]])
    t_true = np.array([3.0, -2.0, 1.5])
    Q = (P - t_true) @ R_true          # so that Q @ R_true.T + t_true == P
    R, t, rmsd = kabsch(P, Q)
    assert rmsd < 1e-8
    assert np.allclose(Q @ R.T + t, P, atol=1e-8)
    assert np.isclose(np.linalg.det(R), 1.0), "must be a rotation, never a reflection"


def test_kabsch_refuses_to_reflect():
    """A reflection would fit mirror-image coordinates and report a false low RMSD."""
    P = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]], dtype=float)
    Q = P.copy()
    Q[:, 2] *= -1                      # mirrored through the xy-plane
    R, _t, _rmsd = kabsch(P, Q)
    assert np.linalg.det(R) > 0


def test_needleman_wunsch_aligns_and_handles_gaps():
    pairs = needleman_wunsch("ACGT", "ACGT")
    assert pairs == [(0, 0), (1, 1), (2, 2), (3, 3)]

    pairs = needleman_wunsch("AAGAA", "AAAA")
    matched = [(i, j) for i, j in pairs if i is not None and j is not None]
    assert len(matched) == 4, "one insertion should leave four matched positions"
    assert any(j is None for _i, j in pairs), "the extra residue must be a gap"

    assert needleman_wunsch("", "ABC") == []


def test_tm_score_is_bounded_and_monotonic():
    perfect = tm_score(np.zeros(100), 100)
    assert 0.99 <= perfect <= 1.0
    far = tm_score(np.full(100, 50.0), 100)
    assert far < 0.02
    # Closer is always better.
    assert tm_score(np.full(50, 1.0), 100) > tm_score(np.full(50, 4.0), 100)
    assert tm_score(np.zeros(10), 10) == 0.0, "undefined below 16 residues"


def test_superpose_identical_structures_is_exact():
    a = parse_pdb(_mini_pdb(), "test:a", "unit")
    b = parse_pdb(_mini_pdb(offset=25.0), "test:b", "unit")
    aln = superpose(a, b)
    assert aln.n_aligned == 5
    assert aln.n_close == 5
    assert aln.rmsd < 1e-6, "a pure translation must superpose exactly"
    assert aln.seq_identity == 1.0
    assert aln.is_estimate, "the method is always labelled an estimate"
    assert any("not a structural alignment" in c for c in aln.caveats)


def test_superpose_moves_b_into_a_frame():
    a = parse_pdb(_mini_pdb(), "test:a", "unit")
    b = parse_pdb(_mini_pdb(offset=25.0), "test:b", "unit")
    aln = superpose(a, b)
    coords_b, _ = b.ca_coords("A")
    coords_a, _ = a.ca_coords("A")
    assert np.allclose(aln.apply_to(coords_b), coords_a, atol=1e-6)


def test_superpose_warns_on_low_sequence_identity():
    a = parse_pdb(_mini_pdb(seq="AAAAA"), "test:a", "unit")
    b = parse_pdb(_mini_pdb(seq="WWWWW"), "test:b", "unit")
    aln = superpose(a, b)
    assert aln.seq_identity == 0.0
    assert any("sequence identity is only" in c for c in aln.caveats)


def test_superpose_refuses_when_there_is_nothing_to_align():
    """Refusing is the correct answer; a fabricated superposition would not be.

    Chain selection runs first, so a structure with no usable chain is rejected there
    rather than at the later C-alpha check. Both are valid refusals; what matters is
    that neither fabricates a superposition.
    """
    a = parse_pdb(_mini_pdb(seq="AAAAA"), "test:a", "unit")

    empty = parse_pdb("TITLE     EMPTY\nEND", "test:b", "unit")
    with pytest.raises(ValueError, match="no chain of at least"):
        superpose(a, empty)

    # Two residues cannot support a rigid fit; Kabsch needs three points.
    tiny = parse_pdb(_mini_pdb(seq="AA"), "test:tiny", "unit")
    with pytest.raises(ValueError, match="no chain of at least"):
        superpose(tiny, a)

    # Residues present, but backbone-only without C-alpha, and an explicit chain so
    # the candidate search is bypassed and the C-alpha guard is what fires.
    no_ca = parse_pdb(
        "ATOM      1  N   ALA A   1       0.000   0.000   0.000  1.00 50.00           N\n"
        "ATOM      2  C   ALA A   1       1.000   0.000   0.000  1.00 50.00           C\nEND",
        "test:c", "unit",
    )
    assert no_ca.chains["A"], "the residue should parse even with no CA"
    with pytest.raises(ValueError, match="no C-alpha atoms"):
        superpose(a, no_ca, chain_a="A", chain_b="A")


def test_predicted_model_adds_a_confidence_caveat():
    a = parse_pdb(_mini_pdb(), "test:a", "AlphaFold DB X (predicted)")
    b = parse_pdb(_mini_pdb(offset=4.0), "test:b", "unit")
    aln = superpose(a, b)
    assert any("predicted model" in c for c in aln.caveats)


def test_pocket_comparison_reports_absence_rather_than_faking_it():
    a = parse_pdb(_mini_pdb(), "test:a", "unit")
    b = parse_pdb(_mini_pdb(offset=25.0), "test:b", "unit")
    aln = superpose(a, b)
    pc = pocket_comparison(a, b, aln)
    # The miniature ligand is below the size floor, so there is no pocket to compare.
    assert pc["ligand_a"] is None or "note" in pc
    if "note" in pc:
        assert "No pocket pair to compare" in pc["note"]
        assert "no chain in this structure has a bound ligand" in pc["note"]


# --------------------------------------------------------------------------
# the 3D comparison page
# --------------------------------------------------------------------------


def test_compare_page_is_self_contained(tmp_path, monkeypatch):
    import re

    from reagent.viz.compare_3d import render

    repo = tmp_path
    (repo / "assets" / "vendor").mkdir(parents=True)
    (repo / "assets" / "vendor" / "3Dmol-min.js").write_text(
        "window.$3Dmol = {createViewerGrid(){}, createViewer(){}};", encoding="utf-8"
    )

    a = parse_pdb(_mini_pdb(seq="AGSVW"), "test:a", "unit")
    b = parse_pdb(_mini_pdb(seq="AGSVW", offset=12.0), "test:b", "unit")
    aln = superpose(a, b)
    out, viz = render(a, b, aln, repo / "cmp.html", pocket={}, repo_root=repo)

    html = out.read_text(encoding="utf-8")
    assert not re.findall(r"__[A-Z_]+__", html), "no unreplaced template tokens"
    assert not re.findall(r'(?:src|href)="https?://', html), "no external resources"
    app = html.split("</script>")[1]
    assert "$3Dmol.download" not in app, "must never fetch coordinates at runtime"
    assert len(re.findall(r"\$3Dmol\.createViewerGrid\s*\(", app)) == 1, (
        "createViewerGrid appends a canvas; calling it twice orphans one"
    )
    assert viz.interactive and viz.focal_node is None
    assert viz.color_maps and viz.color_maps[0].channel == "cartoon_color"


def test_strip_waters_and_transform_preserve_record_structure():
    from reagent.viz.compare_3d import strip_waters, transform_pdb

    pdb = _mini_pdb() + "\nHETATM 9001  O   HOH A 950      5.000   5.000   5.000  1.00 20.00           O"
    stripped = strip_waters(pdb)
    assert "HOH" not in stripped
    assert stripped.count("ATOM  ") == pdb.count("ATOM  ")

    a = parse_pdb(_mini_pdb(), "test:a", "unit")
    b = parse_pdb(_mini_pdb(offset=25.0), "test:b", "unit")
    aln = superpose(a, b)
    moved = transform_pdb(_mini_pdb(offset=25.0), aln)
    reparsed = parse_pdb(moved, "test:moved", "unit")
    # Every coordinate line must survive the rewrite, and land on top of A.
    assert len(reparsed.chains["A"]) == 5
    ca_moved, _ = reparsed.ca_coords("A")
    ca_a, _ = a.ca_coords("A")
    assert np.allclose(ca_moved, ca_a, atol=1e-2)


def test_conservation_classes_partition_by_distance():
    from reagent.viz.compare_3d import CONSERVED, DIVERGENT, EQUIVALENT, SHIFTED, _classify

    assert _classify(1.0, True) == CONSERVED
    assert _classify(1.0, False) == EQUIVALENT
    assert _classify(7.0, True) == SHIFTED
    assert _classify(20.0, True) == DIVERGENT


# --------------------------------------------------------------------------
# chain selection — the bugs that made multi-copy and heterodimer crystals
# silently produce empty pocket comparisons
# --------------------------------------------------------------------------


def _two_chain_pdb() -> str:
    """Chains B and D are identical copies; only D holds a ligand.

    This is the shape of a real crystal with several copies of one protein, and the
    case that used to break: dedup-by-sequence kept B, so the holo copy never got
    scored and the pocket comparison came back empty.
    """
    lines = []
    n = 1
    for chain, dz in (("B", 0.0), ("D", 60.0)):
        for i in range(1, 9):
            for atom, dx in (("N", -0.5), ("CA", 0.0), ("C", 0.5)):
                lines.append(
                    f"ATOM  {n:5d}  {atom:<3s} ALA {chain}{i:4d}    "
                    f"{i * 3.8 + dx:8.3f}{0.0:8.3f}{dz:8.3f}  1.00 50.00           {atom[0]}"
                )
                n += 1
    # An 8-atom ligand beside chain D only.
    for k in range(8):
        lines.append(
            f"HETATM{n + k:5d}  C{k + 1:<2d} LIG D 900    "
            f"{8.0 + k * 1.2:8.3f}{3.0:8.3f}{60.0:8.3f}  1.00 30.00           C"
        )
    lines.append("END")
    return "\n".join(lines)


def test_candidate_chains_keeps_the_holo_copy_of_identical_chains():
    st = parse_pdb(_two_chain_pdb(), "test:multi", "unit")
    from reagent.structure.align import _candidate_chains

    assert st.sequence("B") == st.sequence("D"), "the fixture needs identical copies"
    cands = _candidate_chains(st, min_len=5)
    assert cands == ["D"], (
        f"expected the ligand-bearing copy, got {cands} — dedup must not discard the "
        "holo chain in favour of an apo one"
    )


def test_primary_ligand_never_borrows_another_chains_ligand():
    """Attributing chain D's ligand to chain B would be a straightforwardly false claim."""
    st = parse_pdb(_two_chain_pdb(), "test:multi", "unit")
    assert st.primary_ligand("D") is not None
    assert st.primary_ligand("B") is None
    # Unqualified, the largest ligand anywhere is still fine.
    assert st.primary_ligand() is not None


def test_chains_with_ligands_reports_where_to_look():
    st = parse_pdb(_two_chain_pdb(), "test:multi", "unit")
    assert st.chains_with_ligands() == {"D": ["LIG"]}


def test_apo_chain_pocket_note_names_the_holo_chain():
    """An empty pocket must explain itself, or it reads as 'the pockets differ'."""
    holo = parse_pdb(_two_chain_pdb(), "test:multi", "unit")
    query = parse_pdb(_mini_pdb(seq="AAAAAAAA"), "test:q", "unit")
    aln = superpose(query, holo, chain_a="A", chain_b="B")   # force the apo copy
    pc = pocket_comparison(query, holo, aln)
    assert "note" in pc
    assert "chain B is apo" in pc["note"]
    assert "chain(s) D" in pc["note"], "the note must say where a ligand does sit"
    assert "re-run" in pc["note"], "and what to do about it"


def test_superpose_lands_on_the_holo_copy():
    st_a = parse_pdb(_mini_pdb(seq="AAAAAAAA"), "test:a", "unit")
    st_b = parse_pdb(_two_chain_pdb(), "test:b", "unit")
    aln = superpose(st_a, st_b)
    assert aln.chain_b == "D", "should land on the holo copy"


def test_automatic_chain_choice_is_disclosed():
    """Two DIFFERENT sequences mean a real choice was made, which must be stated.

    Identical copies collapse to one candidate, so there is nothing to disclose; a
    heterodimer is the case where the choice changes the answer.
    """
    st_a = parse_pdb(_mini_pdb(seq="AAAAAAAA"), "test:a", "unit")
    hetero = _two_chain_pdb().replace(" ALA D", " TRP D")   # chain D now differs
    st_b = parse_pdb(hetero, "test:b", "unit")
    assert st_b.sequence("B") != st_b.sequence("D")
    aln = superpose(st_a, st_b)
    assert any("chains were chosen automatically" in c for c in aln.caveats), (
        "an automatic chain choice must be disclosed, since it changes the answer"
    )
