from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from modules.agent.application.dtos.skill_dtos import ImportSkillInput
from modules.agent.application.skill_packages import parse_skill_package
from modules.agent.application.use_cases.skill_cases import SkillCatalog
from modules.agent.domain.skills import SkillVersion, skill_package_hash
from shared.contracts.errors import ConflictError


@pytest.mark.asyncio
async def test_import_reuses_exact_package_on_later_skill_and_version_pages():
    project, skill_id = uuid4(), uuid4()
    incoming = ImportSkillInput(
        version="1.0.0",
        skill_md="---\nname: invoice-review\ndescription: Review invoices\n---\nCheck totals",
        resources={"references/checklist.md": "Check tax"},
        required_tools=["invoice.lookup"],
    )
    package = parse_skill_package(incoming)
    version = SkillVersion(
        project_id=project,
        skill_id=skill_id,
        version=incoming.version,
        package=package,
        package_hash=skill_package_hash(package),
    )
    repo = AsyncMock()
    other = SimpleNamespace(
        skill=SimpleNamespace(id=uuid4(), name="invoice-review-helper")
    )
    selected = SimpleNamespace(
        skill=SimpleNamespace(id=skill_id, name="invoice-review")
    )
    repo.list_skills.side_effect = [[other] * 100, [selected]]
    repo.list_versions.side_effect = [
        [SimpleNamespace(version="0.9.0")] * 100,
        [version],
    ]
    actual, created = await SkillCatalog(repo).resolve_import(project, incoming)
    assert actual is version and created is False
    assert repo.list_skills.await_args.kwargs["offset"] == 100
    assert repo.list_versions.await_args.kwargs["offset"] == 100
    repo.create_version.assert_not_awaited()
    repo.create_skill.assert_not_awaited()
    changed = deepcopy(version)
    changed.package["resources"]["references/checklist.md"] = (
        "Different immutable bytes"
    )
    repo.list_skills.side_effect = None
    repo.list_skills.return_value = [selected]
    repo.list_versions.side_effect = None
    repo.list_versions.return_value = [changed]
    with pytest.raises(ConflictError):
        await SkillCatalog(repo).resolve_import(project, incoming)
    repo.create_version.assert_not_awaited()
