from copy import deepcopy
from inspect import signature
from uuid import uuid4

from modules.agent.domain.entities import AgentRelease
from modules.agent.domain.enums import ReleaseStatus
from modules.network.application.service import NetworkApplicationService


def _draft(schema: dict) -> AgentRelease:
    release = AgentRelease(
        project_id=uuid4(),
        agent_id=uuid4(),
        version="draft",
        status=ReleaseStatus.draft,
        response_format={"enabled": True, "type": "json", "schema": schema},
        output_schema=schema,
        provider="openai",
        model="gpt-4.1-mini",
    )
    release.snapshot_kind = "draft"
    return release


def test_public_network_service_accepts_preview_concurrency_inputs() -> None:
    parameters = signature(NetworkApplicationService.promote).parameters

    assert "expected_revision" in parameters
    assert "expected_network_version_id" in parameters
    assert "approved_action_ids" in parameters


def test_contract_change_changes_network_promotion_action_id() -> None:
    before = _draft({"message": "string"})
    after = deepcopy(before)
    after.output_schema = {"message": "string", "confidence": "number"}
    after.response_format = {
        "enabled": True,
        "type": "json",
        "schema": after.output_schema,
    }

    before_action = NetworkApplicationService._action_id("stage", before)
    after_action = NetworkApplicationService._action_id("stage", after)

    assert before_action != after_action
