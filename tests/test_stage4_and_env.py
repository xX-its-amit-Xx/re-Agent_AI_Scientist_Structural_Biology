"""Stage 4 optimisation and the onboarding gate.

Two clusters of guards. Stage 4's exist because every operation there can improve a pose or wreck
it, and one measured number governs them: an agentic free re-draw took a pose from 3.88 A to
24.63 A. Onboarding's exist because a missing capability produces a silently smaller answer
rather than an error.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from reagent.contracts.environment import (
    AuthFlow,
    ComputeKind,
    ComputeTarget,
    DownloadPolicy,
    Onboarding,
    OnboardingStep,
    ResourceBudget,
    SecretSpec,
    SecretStatus,
    SecretVault,
    StorageMount,
    StoragePlan,
    StorageTier,
    probe_resources,
    redact,
)
from reagent.contracts.evidence import Evidence, SourceType
from reagent.contracts.optimize import (
    Capability,
    CoordinateEdit,
    EditOp,
    GeometryCheck,
    OptimizationRun,
    Refinement,
    ScoringFunction,
    ScoringPanel,
    ToolBinding,
    ToolRegistry,
    sha256_of,
)

# ---------------------------------------------------------------------------
# Tooling is provider-agnostic
# ---------------------------------------------------------------------------


def _registry() -> ToolRegistry:
    return ToolRegistry(bindings=[
        ToolBinding(capability=Capability.DOCK, provider="tamarind", metered=True,
                    unit_cost="~40 s and $0.02 per pose, measured on a 12-pose pilot"),
        ToolBinding(capability=Capability.MINIMIZE, provider="openmm", verified=True),
    ])


def test_an_unbound_capability_is_a_finding_not_a_skipped_step():
    probs = _registry().problems([Capability.DOCK, Capability.MINIMIZE, Capability.MD])
    assert any("no provider bound for ['molecular_dynamics']" in p for p in probs)


def test_a_bound_but_unverified_provider_is_flagged():
    probs = _registry().problems([Capability.DOCK])
    assert any("never successfully run" in p for p in probs)


def test_metered_capabilities_are_surfaced_before_they_run():
    probs = _registry().problems([Capability.DOCK])
    assert any("metered capabilities" in p for p in probs)


def test_a_verified_provider_wins_over_an_unverified_one_for_the_same_capability():
    reg = ToolRegistry(bindings=[
        ToolBinding(capability=Capability.DOCK, provider="unverified-thing"),
        ToolBinding(capability=Capability.DOCK, provider="vina-local", verified=True),
    ])
    assert reg.provider_for(Capability.DOCK).provider == "vina-local"


def test_docking_and_md_are_metered_by_default_and_geometry_checks_are_not():
    assert Capability.DOCK.is_metered_by_default
    assert Capability.MD.is_metered_by_default
    assert not Capability.GEOMETRY_CHECK.is_metered_by_default


# ---------------------------------------------------------------------------
# Coordinate editing
# ---------------------------------------------------------------------------


def _checks(**kw) -> GeometryCheck:
    base = dict(bond_lengths_ok=True, bond_angles_ok=True, planarity_ok=True,
                chirality_preserved=True, no_new_clashes=True, graph_unchanged=True,
                file_parses=True, checked_by="rdkit")
    return GeometryCheck(**{**base, **kw})


WHY = ("Relieves a 0.9 A overlap between the ligand carbonyl O and Leu240 CD1 by rotating the "
       "C7-C8 torsion by 40 degrees")


def _edit(**kw) -> CoordinateEdit:
    base = dict(id="E1", op=EditOp.TORSION_SET, target="ligand HYF chain A", why=WHY,
                checks=_checks(), minimized_after=True)
    return CoordinateEdit(**{**base, **kw})


def test_a_typed_verified_minimised_edit_is_accepted():
    e = _edit()
    assert e.severity == "light"


def test_an_unchecked_field_is_not_a_pass():
    with pytest.raises(ValidationError, match="Absence of a check is not a pass"):
        _edit(checks=GeometryCheck(bond_lengths_ok=True))


def test_a_failed_check_must_be_a_revert():
    with pytest.raises(ValidationError, match="A failed check is a revert"):
        _edit(checks=_checks(no_new_clashes=False))


def test_a_reverted_edit_may_carry_its_failure():
    e = _edit(checks=_checks(no_new_clashes=False), reverted=True)
    assert e.reverted and e.checks.failures == ["no_new_clashes"]


def test_a_non_rigid_edit_must_be_minimised_after():
    with pytest.raises(ValidationError, match="may not be the last thing to touch the file"):
        _edit(minimized_after=False)


def test_a_rigid_edit_needs_no_minimisation():
    e = _edit(op=EditOp.RIGID_TRANSLATE, minimized_after=False,
              why="Moves the pose 1.4 A along the pocket axis into the lobe the graph assigns it")
    assert e.op.preserves_internal_geometry


def test_raw_coordinates_require_an_escalation_note():
    with pytest.raises(ValidationError, match=r"3\.88 A to 24\.63 A"):
        _edit(op=EditOp.RAW_COORDINATE)


def test_raw_coordinates_with_an_escalation_note_are_permitted():
    e = _edit(op=EditOp.RAW_COORDINATE,
              escalation_note="no typed operation expresses a coordinated two-torsion change")
    assert e.op.needs_escalation


def test_an_edit_claiming_blindness_may_not_cite_the_answer():
    with pytest.raises(ValidationError, match="feels identical from the inside"):
        _edit(informed_by=[Evidence(source_type=SourceType.COMPUTATION,
                                    locator="eval/reference_pose_item12.pdb")])


def test_sighted_editing_is_allowed_when_declared():
    e = _edit(blind_to_reference=False,
              informed_by=[Evidence(source_type=SourceType.COMPUTATION,
                                    locator="eval/reference_pose_item12.pdb")])
    assert not e.blind_to_reference


def test_graph_changing_ops_are_identified():
    for op in (EditOp.PROTONATION_CHANGE, EditOp.TAUTOMER_CHANGE, EditOp.STEREO_INVERT,
               EditOp.ATOM_DELETE):
        assert op.changes_the_graph, op.value
    assert not EditOp.TORSION_SET.changes_the_graph


def test_hashes_detect_an_edit_that_did_nothing():
    text = "ATOM      1  C   LIG A 435       1.000   2.000   3.000\n"
    assert sha256_of(text) == sha256_of(text)
    assert sha256_of(text) != sha256_of(text.replace("1.000", "1.400"))


# ---------------------------------------------------------------------------
# Refinement
# ---------------------------------------------------------------------------


def test_ligand_only_relaxation_is_rejected_outright():
    with pytest.raises(ValidationError, match="degrading the ground truth itself"):
        Refinement(id="R1", capability=Capability.MINIMIZE, provider="openmm",
                   scope="ligand alone", ligand_only=True)


def test_unrestrained_minimisation_is_rejected():
    with pytest.raises(ValidationError, match="Use restraints"):
        Refinement(id="R2", capability=Capability.MINIMIZE, provider="openmm",
                   scope="ligand in the pocket", restrained=False)


def test_a_restrained_in_pocket_minimisation_is_accepted():
    r = Refinement(id="R3", capability=Capability.MINIMIZE, provider="openmm",
                   scope="ligand plus pocket side chains", n_items=14,
                   gated_on="12 held-out holo complexes")
    assert r.restrained and not r.ligand_only


def test_md_may_be_unrestrained_because_scope_carries_it():
    r = Refinement(id="R4", capability=Capability.MD, provider="tamarind",
                   scope="ligand plus pocket, 10 ns", restrained=False)
    assert r.capability is Capability.MD


# ---------------------------------------------------------------------------
# Scoring panel
# ---------------------------------------------------------------------------


def test_a_scorer_that_reads_the_input_rather_than_the_pose_is_flagged():
    panel = ScoringPanel(functions=[
        ScoringFunction(name="affinity-head", kind="learned", scores_the_candidate=False,
                        normalised_within=True, beat_baseline=True),
    ])
    assert any("rank inputs rather than candidates" in p for p in panel.problems())


def test_unnormalised_cross_function_comparison_is_flagged():
    panel = ScoringPanel(functions=[
        ScoringFunction(name="vina", kind="physics", normalised_within=False,
                        beat_baseline=True),
    ])
    assert any("most confident rather than most correct" in p for p in panel.problems())


def test_an_untested_scorer_is_guilty_until_it_beats_the_incumbent():
    panel = ScoringPanel(functions=[
        ScoringFunction(name="strain", kind="physics", normalised_within=True),
    ])
    assert panel.untested() == ["strain"]
    assert any("guilty until it beats" in p for p in panel.problems())


def test_voting_needs_an_argument():
    panel = ScoringPanel(aggregation="vote", functions=[
        ScoringFunction(name="a", kind="physics", normalised_within=True, beat_baseline=True),
        ScoringFunction(name="b", kind="physics", normalised_within=True, beat_baseline=True),
    ])
    assert any("not evidence" in p for p in panel.problems())


def test_a_scorer_that_lost_to_the_baseline_is_unusable():
    f = ScoringFunction(name="loser", kind="learned", normalised_within=True,
                        beat_baseline=False)
    assert not f.is_usable


# ---------------------------------------------------------------------------
# The run
# ---------------------------------------------------------------------------


def _run(**kw) -> OptimizationRun:
    base = dict(
        run_id="s4-01", tools=_registry(),
        capabilities_needed=[Capability.MINIMIZE],
        edits=[_edit()],
        refinements=[Refinement(id="R", capability=Capability.MINIMIZE, provider="openmm",
                                scope="ligand plus pocket side chains", n_items=14,
                                gated_on="12 held-out holo complexes")],
        baseline_metric="mean LDDT-PLI 0.5640",
        final_metric="mean LDDT-PLI 0.5613",
        delta="-0.0027, bootstrap CI [-0.012, +0.007] — inside the noise",
    )
    return OptimizationRun(**{**base, **kw})


def test_a_disciplined_run_reports_no_problems():
    assert _run().problems() == []


def test_adoption_requires_a_held_out_gate():
    with pytest.raises(ValidationError, match="does not ship"):
        _run(adopted=True)


def test_adoption_with_a_gate_is_permitted():
    r = _run(adopted=True, adoption_gate="beat the incumbent on 12 held-out complexes, "
                                         "non-overlapping bootstrap intervals")
    assert r.adopted


def test_edits_with_no_measured_delta_are_flagged():
    assert any("indistinguishable from a harmful one" in p
               for p in _run(delta=None).problems())


def test_graph_changing_edits_that_survived_are_named():
    e = _edit(id="E-graph", op=EditOp.ATOM_DELETE,
              why="Removes a glycerol that was passed in as the ligand by the input builder")
    assert any("scores zero rather than badly" in p for p in _run(edits=[e]).problems())


def test_surviving_raw_coordinate_edits_need_a_reviewer():
    e = _edit(id="E-raw", op=EditOp.RAW_COORDINATE,
              escalation_note="a coordinated two-torsion change has no typed equivalent")
    assert any("24.63 A pose" in p for p in _run(edits=[e]).problems())


def test_sighted_edits_are_named_so_they_cannot_reach_a_submission_quietly():
    e = _edit(id="E-sighted", blind_to_reference=False)
    r = _run(edits=[e])
    assert r.sighted_edits() == ["E-sighted"]
    assert any("measures the guidance rather than the edit" in p for p in r.problems())


def test_blanket_refinement_is_flagged():
    r = _run(refinements=[Refinement(
        id="R", capability=Capability.MINIMIZE, provider="openmm", scope="all atoms",
        targeted_at="all", gated_on="held-out set")])
    assert any("Target the tail" in p for p in r.problems())


def test_ungated_refinement_is_flagged():
    r = _run(refinements=[Refinement(
        id="R", capability=Capability.MINIMIZE, provider="openmm",
        scope="ligand plus pocket")])
    assert any("held-out gate" in p for p in r.problems())


def test_severity_and_op_breakdowns_ignore_reverts():
    r = _run(edits=[_edit(id="A"), _edit(id="B", checks=_checks(planarity_ok=False),
                                        reverted=True)])
    assert sum(r.by_severity().values()) == 1
    assert r.reverted() == ["B"]


# ---------------------------------------------------------------------------
# Secrets
# ---------------------------------------------------------------------------


def test_a_secret_spec_holds_a_name_and_never_a_value():
    assert "value" not in SecretSpec.model_fields


def test_secret_names_must_look_like_env_vars():
    with pytest.raises(ValidationError, match="holds a name, never a value"):
        SecretSpec(name="my-secret-value", purpose="something important here",
                   obtain_from="somewhere")


def test_status_resolves_from_the_environment_without_returning_the_value():
    s = SecretSpec(name="MODAL_TOKEN_SECRET", purpose="Serverless GPU compute for co-folding",
                   obtain_from="modal token new")
    assert s.status({}) is SecretStatus.MISSING
    assert s.status({"MODAL_TOKEN_SECRET": "changeme"}) is SecretStatus.PLACEHOLDER
    assert s.status({"MODAL_TOKEN_SECRET": "as-abc-123"}) is SecretStatus.PRESENT


def test_a_leaked_credential_in_a_contract_field_is_rejected():
    with pytest.raises(ValidationError, match="looks like an actual credential"):
        SecretVault(specs=[SecretSpec(
            name="GH_TOKEN",
            purpose="ghp_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa is the token to use",
            obtain_from="github settings")])


def test_redaction_keeps_only_a_short_suffix():
    assert redact("sk-proj-abcdef123456789") == "*" * 19 + "6789"
    assert redact("ab") == "**"


def test_an_ungitignored_env_is_the_irreversible_failure():
    v = SecretVault(specs=[SecretSpec(name="K_EY", purpose="something needed here",
                                      obtain_from="x")], gitignored=False)
    assert any("must be rotated, not deleted" in p for p in v.problems({}))


def test_the_deny_rule_is_reported_as_preventing_an_accident_not_an_intent():
    v = SecretVault(specs=[SecretSpec(name="K_EY", purpose="something needed here",
                                      obtain_from="x")], agent_read_denied=False)
    assert any("does not prevent a determined one" in p for p in v.problems({}))


def test_the_template_contains_names_and_no_values():
    v = SecretVault(specs=[SecretSpec(
        name="TAMARIND_API_KEY", purpose="Hosted docking and molecular dynamics",
        obtain_from="account settings", scope_note="submit-only")])
    tpl = v.template()
    assert "TAMARIND_API_KEY=" in tpl
    assert "submit-only" in tpl
    for line in tpl.splitlines():
        if "=" in line and not line.startswith("#"):
            assert line.endswith("="), line


def test_auth_flow_tells_the_user_to_run_it_themselves():
    f = AuthFlow(service="modal", start_command="modal token new",
                 verify_command="modal profile current")
    assert "! modal token new" in f.instruction
    assert "never handles the token" in f.instruction


# ---------------------------------------------------------------------------
# Compute, storage, resources
# ---------------------------------------------------------------------------


def test_a_hosted_notebook_does_not_suit_a_long_run_however_large_its_gpu():
    nb = ComputeTarget(name="colab", kind=ComputeKind.HOSTED_NOTEBOOK, gpu="A100 40GB",
                       idle_timeout_min=90, verified=True)
    assert not nb.suits_long_runs
    assert any("unsuitable" in p for p in nb.problems())


def test_a_slurm_target_warns_about_the_login_node():
    c = ComputeTarget(name="explorer", kind=ComputeKind.SSH_CLUSTER, scheduler="slurm",
                      verified=True)
    assert any("login node" in p for p in c.problems())
    assert c.suits_long_runs


def test_a_network_backed_hot_mount_is_the_expensive_confusion():
    plan = StoragePlan(mounts=[
        StorageMount(path="O:/scratch", tier=StorageTier.HOT, free_gb=5000,
                     network_backed=True),
        StorageMount(path="O:/cold", tier=StorageTier.COLD, free_gb=5000, network_backed=True),
    ])
    assert any("look like a slow model" in p for p in plan.problems())


def test_a_hot_mount_below_the_floor_is_flagged():
    plan = StoragePlan(mounts=[
        StorageMount(path="C:/Temp", tier=StorageTier.HOT, free_gb=2.0),
        StorageMount(path="O:/cold", tier=StorageTier.COLD, free_gb=5000, network_backed=True),
    ], min_free_gb=10.0)
    assert any("fails late and leaves partial artifacts" in p for p in plan.problems())


def test_no_cold_mount_means_the_working_disk_fills():
    plan = StoragePlan(mounts=[StorageMount(path="C:/Temp", tier=StorageTier.HOT, free_gb=50)])
    assert any("accumulate on the working disk" in p for p in plan.problems())


def test_ram_is_usually_the_binding_constraint():
    b = ResourceBudget(total_cpus=16, available_ram_gb=32, per_worker_ram_gb=6)
    assert b.workers() == 4
    assert b.binding_constraint() == "ram"


def test_cpu_binds_when_memory_is_plentiful():
    b = ResourceBudget(total_cpus=8, available_ram_gb=128, per_worker_ram_gb=2)
    assert b.workers() == 6
    assert b.binding_constraint() == "cpu"


def test_workers_never_drops_below_one():
    b = ResourceBudget(total_cpus=1, available_ram_gb=1, reserve_ram_gb=0.5,
                       per_worker_ram_gb=64)
    assert b.workers() == 1


def test_an_overestimated_per_worker_footprint_is_flagged_because_it_serialises_silently():
    b = ResourceBudget(total_cpus=32, available_ram_gb=16, per_worker_ram_gb=64)
    assert b.workers() == 1
    assert any("silently serialises" in p for p in b.problems())


def test_probe_reports_a_usable_budget():
    b = probe_resources(".")
    assert b.workers() >= 1
    assert b.total_cpus >= 1


def test_downloads_without_checksums_are_the_worst_failure_mode():
    d = DownloadPolicy(verify_checksum=False)
    assert any("parses and is wrong" in p for p in d.problems())


def test_downloads_landing_on_hot_storage_are_flagged():
    d = DownloadPolicy(destination_tier=StorageTier.HOT)
    assert any("smallest one" in p for p in d.problems())


# ---------------------------------------------------------------------------
# The gate
# ---------------------------------------------------------------------------


def _onboarding(**kw) -> Onboarding:
    base = dict(
        vault=SecretVault(specs=[SecretSpec(
            name="TAMARIND_API_KEY", purpose="Hosted docking and molecular dynamics",
            obtain_from="account settings", scope_note="submit-only", optional=True)],
            gitignored=True, agent_read_denied=True),
        storage=StoragePlan(mounts=[
            StorageMount(path="C:/Temp", tier=StorageTier.HOT, free_gb=50),
            StorageMount(path="O:/cold", tier=StorageTier.COLD, free_gb=5000,
                         network_backed=True)]),
        resources=ResourceBudget(total_cpus=16, available_ram_gb=64),
        compute=[ComputeTarget(name="explorer", kind=ComputeKind.SSH_CLUSTER,
                               scheduler="slurm", verified=True)],
        problem_spec_path="reports/demo/problem.json",
        data_refs=["zenodo:10.5281/zenodo.1234567"],
    )
    return Onboarding(**{**base, **kw})


def test_a_complete_onboarding_is_ready():
    o = _onboarding()
    assert o.ready({})
    assert o.blocking({}) == []


def test_no_problem_blocks():
    o = _onboarding(problem_spec_path=None)
    assert not o.ready({})
    assert any("nothing to attack" in b for b in o.blocking({}))


def test_no_data_blocks():
    o = _onboarding(data_refs=[])
    assert any("no training or test data" in b for b in o.blocking({}))


def test_a_missing_required_secret_blocks():
    o = _onboarding(vault=SecretVault(specs=[SecretSpec(
        name="MODAL_TOKEN_SECRET", purpose="Serverless GPU compute for co-folding",
        obtain_from="modal token new", optional=False)], gitignored=True))
    assert any("required secrets" in b for b in o.blocking({}))


def test_an_incomplete_signin_blocks():
    o = _onboarding(auth_flows=[AuthFlow(service="modal", start_command="modal token new")])
    assert any("sign-in not completed" in b for b in o.blocking({}))


def test_a_missing_optional_secret_does_not_block():
    """The pipeline degrades rather than refusing — Stages 0-2 need no credentials."""
    assert _onboarding().ready({})


def test_local_only_is_legitimate_and_recorded_as_a_limitation():
    o = _onboarding(compute=[])
    assert o.ready({})
    assert any("record it as a limitation" in p for p in o.problems({}))


def test_no_target_suited_to_a_long_run_is_flagged():
    o = _onboarding(compute=[ComputeTarget(
        name="colab", kind=ComputeKind.HOSTED_NOTEBOOK, idle_timeout_min=90, verified=True)])
    assert any("idle timeouts" in p for p in o.problems({}))


def test_completed_steps_tracks_each_stage_of_setup():
    done = _onboarding().completed_steps({})
    assert OnboardingStep.PROBLEM in done
    assert OnboardingStep.DATA in done
    assert OnboardingStep.RESOURCES in done


def test_every_onboarding_step_states_its_question():
    for step in OnboardingStep:
        assert step.question.endswith("?")


def test_capabilities_lists_only_verified_targets():
    o = _onboarding(compute=[
        ComputeTarget(name="explorer", kind=ComputeKind.SSH_CLUSTER, verified=True),
        ComputeTarget(name="unverified", kind=ComputeKind.SERVERLESS, verified=False),
    ])
    caps = o.capabilities()
    assert any("explorer" in c for c in caps)
    assert not any("unverified" in c for c in caps)
