from importlib import import_module


def test_evaluation_migrations_are_linear() -> None:
    base = import_module("migrations.versions.0054_evaluations_multi_environment")
    hardening = import_module("migrations.versions.0055_evaluation_execution_hardening")
    attribution = import_module("migrations.versions.0056_evaluation_runtime_attribution")
    authoring = import_module("migrations.versions.0057_evaluation_suite_authoring")
    completion = import_module("migrations.versions.0058_evaluation_operational_completion")
    resume = import_module("migrations.versions.0059_evaluation_authoring_case_resume")
    decisions = import_module("migrations.versions.0060_evaluation_human_decisions")
    revisions = import_module("migrations.versions.0061_evaluation_evidence_revisions")
    catalog = import_module("migrations.versions.0062_evaluation_catalog_and_comparisons")
    decision_basis = import_module("migrations.versions.0063_evaluation_decision_basis")
    evidence_snapshots = import_module("migrations.versions.0064_evaluation_evidence_snapshots")
    sessions = import_module(
        "migrations.versions.0065_evaluation_session_tests_kpis_and_protocol_identity"
    )
    usage = import_module("migrations.versions.0066_run_purpose_and_evaluation_usage")
    frozen_snapshots = import_module(
        "migrations.versions.0067_frozen_evaluation_runtime_snapshots"
    )

    assert base.revision == "0054"
    assert base.down_revision == "0053"
    assert hardening.revision == "0055"
    assert hardening.down_revision == "0054"
    assert attribution.revision == "0056"
    assert attribution.down_revision == "0055"
    assert authoring.revision == "0057"
    assert authoring.down_revision == "0056"
    assert completion.revision == "0058"
    assert completion.down_revision == "0057"
    assert resume.revision == "0059"
    assert resume.down_revision == "0058"
    assert decisions.revision == "0060"
    assert decisions.down_revision == "0059"
    assert revisions.revision == "0061"
    assert revisions.down_revision == "0060"
    assert catalog.revision == "0062"
    assert catalog.down_revision == "0061"
    assert decision_basis.revision == "0063"
    assert decision_basis.down_revision == "0062"
    assert evidence_snapshots.revision == "0064"
    assert evidence_snapshots.down_revision == "0063"
    assert sessions.revision == "0065"
    assert sessions.down_revision == "0064"
    assert usage.revision == "0066"
    assert usage.down_revision == "0065"
    assert frozen_snapshots.revision == "0067"
    assert frozen_snapshots.down_revision == "0066"
