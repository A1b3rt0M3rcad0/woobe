from datetime import UTC, datetime
from uuid import uuid4

from modules.agent.application.dtos.skill_dtos import SkillSummary
from modules.agent.domain.skills import Skill, SkillVersion
from modules.agent.presentation.controllers.skill_catalog_controller import skill_summary


def test_skill_summary_exposes_latest_version_metadata():
    project_id = uuid4()
    skill_id = uuid4()
    created_at = datetime(2026, 9, 8, 12, 0, tzinfo=UTC)
    latest = SkillVersion(
        id=uuid4(),
        skill_id=skill_id,
        project_id=project_id,
        version="1.4.0",
        package={
            "name": "invoice-review",
            "description": "Review invoices before approval.",
            "instructions": "Check totals and taxes.",
            "required_tools": ["invoice_lookup"],
            "resources": {"references/checklist.md": "Checklist"},
        },
        package_hash="hash",
        created_at=created_at,
    )
    payload = skill_summary(
        SkillSummary(
            skill=Skill(
                id=skill_id,
                project_id=project_id,
                name="invoice-review",
                created_at=created_at,
            ),
            latest_version=latest,
            version_count=4,
        )
    )

    assert payload["id"] == str(skill_id)
    assert payload["latest_version_id"] == str(latest.id)
    assert payload["latest_version"] == "1.4.0"
    assert payload["latest_description"] == "Review invoices before approval."
    assert payload["latest_required_tools"] == ["invoice_lookup"]
    assert payload["latest_resource_count"] == 1
    assert payload["version_count"] == 4
    assert payload["latest_estimated_instruction_units"] > 0


def test_skill_summary_handles_catalog_entry_without_version():
    project_id = uuid4()
    skill = Skill(project_id=project_id, name="empty-skill")

    payload = skill_summary(
        SkillSummary(skill=skill, latest_version=None, version_count=0)
    )

    assert payload["id"] == str(skill.id)
    assert payload["latest_version_id"] is None
    assert payload["latest_version"] is None
    assert payload["latest_required_tools"] == []
    assert payload["latest_resource_count"] == 0
    assert payload["version_count"] == 0
