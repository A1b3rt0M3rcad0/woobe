from importlib import import_module


def test_evaluation_migrations_are_linear() -> None:
    base = import_module("migrations.versions.0054_evaluations_multi_environment")
    hardening = import_module("migrations.versions.0055_evaluation_execution_hardening")
    attribution = import_module("migrations.versions.0056_evaluation_runtime_attribution")
    authoring = import_module("migrations.versions.0057_evaluation_suite_authoring")
    completion = import_module("migrations.versions.0058_evaluation_operational_completion")
    resume = import_module("migrations.versions.0059_evaluation_authoring_case_resume")

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
