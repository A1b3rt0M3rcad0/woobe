from pathlib import Path
from uuid import uuid4

from modules.agent.application.dtos.skill_dtos import ImportSkillInput
from modules.agent.application.interfaces.context_policy import SkillContextPolicy
from modules.agent.application.skill_packages import parse_skill_package
from modules.agent.application.skill_runtime import SkillRuntime
from modules.agent.domain.skills import SkillVersion, skill_package_hash

SKILL_DIR = (
    Path(__file__).parents[3]
    / "docs"
    / "skills"
    / "artifact-document-exploration"
)
ARTIFACT_TOOLS = {
    "woobe_artifact_list",
    "woobe_artifact_inspect",
    "woobe_artifact_outline",
    "woobe_artifact_read",
    "woobe_artifact_search",
    "woobe_artifact_write",
}
REQUIRED_READ_TOOLS = ARTIFACT_TOOLS - {"woobe_artifact_write"}


def _published_package():
    skill_md = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    resources = {
        f"references/{path.name}": path.read_text(encoding="utf-8")
        for path in sorted((SKILL_DIR / "references").glob("*.md"))
    }
    return parse_skill_package(
        ImportSkillInput(
            version="1.0.0",
            skill_md=skill_md,
            resources=resources,
            required_tools=sorted(REQUIRED_READ_TOOLS),
        )
    )


def _version(package):
    value = SkillVersion(
        skill_id=uuid4(),
        project_id=uuid4(),
        version="1.0.0",
        package=package,
        package_hash=skill_package_hash(package),
    )
    return value


def test_document_exploration_skill_is_a_valid_versioned_package():
    package = _published_package()

    assert package["name"] == "artifact-document-exploration"
    assert package["required_tools"] == sorted(REQUIRED_READ_TOOLS)
    assert set(package["required_tools"]) <= ARTIFACT_TOOLS
    assert "64 KiB" in package["instructions"]
    assert "SourceRef" in package["instructions"]
    resource = package["resources"]["references/citations-and-coverage.md"]
    assert "complete" in resource
    assert "coverage" in resource.lower()


def test_document_exploration_skill_activation_requires_every_bound_tool():
    version = _version(_published_package())
    runtime = SkillRuntime(
        [version.snapshot()],
        SkillContextPolicy(),
        REQUIRED_READ_TOOLS - {"woobe_artifact_search"},
    )

    result = runtime.execute(
        "skills_activate",
        {"skill_version_id": str(version.id)},
        tool_call_id="activate",
    )

    assert result["success"] is False
    assert "woobe_artifact_search" in result["error"]
    assert runtime.contributions()[1:] == []


def test_document_exploration_skill_activation_and_resource_read_are_run_local():
    version = _version(_published_package())
    runtime = SkillRuntime(
        [version.snapshot()], SkillContextPolicy(), set(ARTIFACT_TOOLS)
    )
    activated = runtime.execute(
        "skills_activate",
        {"skill_version_id": str(version.id)},
        tool_call_id="activate",
    )
    reference = runtime.execute(
        "skills_read_resource",
        {
            "skill_version_id": str(version.id),
            "path": "references/citations-and-coverage.md",
        },
        tool_call_id="read-reference",
    )

    assert activated["success"] is True
    assert reference["success"] is True
    assert len(runtime.contributions()) == 3
    assert all(item["trust"] in {"system-controlled", "installed-procedure", "reference-data"} for item in runtime.contributions())
