from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.evaluation.application.preflight import (
    EvaluationPreflight,
    EvaluationPreflightService,
    ToolRiskItem,
)
from modules.evaluation.presentation.dependencies import require_evaluation_user
from shared.infra.errors import AuthorizationError, ConflictError
from shared.security.principal import AuthenticatedPrincipal, ProjectApiPrincipal


def _request(principal):
    return SimpleNamespace(state=SimpleNamespace(principal=principal))


def test_control_plane_user_can_administer_evaluations() -> None:
    now = datetime.now(timezone.utc)
    principal = AuthenticatedPrincipal(
        user_id=uuid4(),
        session_id=uuid4(),
        issued_at=now,
        expires_at=now + timedelta(hours=1),
    )

    assert require_evaluation_user(_request(principal), uuid4()) == principal.user_id


def test_runtime_key_cannot_administer_evaluations() -> None:
    principal = ProjectApiPrincipal(
        api_key_id=uuid4(),
        project_id=uuid4(),
        key_prefix="woobe_test",
        authenticated_at=datetime.now(timezone.utc),
    )

    with pytest.raises(AuthorizationError):
        require_evaluation_user(_request(principal), principal.project_id)


def test_high_risk_tool_requires_explicit_approval() -> None:
    tool_id = uuid4()
    preflight = EvaluationPreflight(
        tools=(
            ToolRiskItem(
                id=tool_id,
                name="delete_customer",
                risk_level="high",
                source="agent:release-v1",
            ),
        ),
        requires_acknowledgement=True,
        blocked_high_risk_tool_ids=(tool_id,),
    )

    with pytest.raises(ConflictError):
        EvaluationPreflightService.enforce(
            preflight,
            acknowledge_tool_side_effects=True,
        )


def test_medium_risk_tool_requires_side_effect_acknowledgement() -> None:
    preflight = EvaluationPreflight(
        tools=(
            ToolRiskItem(
                id=uuid4(),
                name="send_email",
                risk_level="medium",
                source="agent:staging-v2",
            ),
        ),
        requires_acknowledgement=True,
        blocked_high_risk_tool_ids=(),
    )

    with pytest.raises(ConflictError):
        EvaluationPreflightService.enforce(
            preflight,
            acknowledge_tool_side_effects=False,
        )

    EvaluationPreflightService.enforce(
        preflight,
        acknowledge_tool_side_effects=True,
    )
