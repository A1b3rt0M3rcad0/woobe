from __future__ import annotations

from modules.tools.domain.entities import Secret, Tool
from modules.tools.domain.enums import RiskLevel, SecretType, ToolStatus, ToolType
from modules.tools.infra.models import SecretModel, ToolModel


def tool_to_model(entity: Tool) -> ToolModel:
    return ToolModel(
        id=entity.id,
        project_id=entity.project_id,
        agent_id=entity.agent_id,
        name=entity.name,
        description=entity.description,
        type=entity.type.value if isinstance(entity.type, ToolType) else entity.type,
        config=entity.config,
        input_schema=entity.input_schema,
        output_schema=entity.output_schema,
        risk_level=entity.risk_level.value if isinstance(entity.risk_level, RiskLevel) else entity.risk_level,
        timeout_ms=entity.timeout_ms,
        status=entity.status.value if isinstance(entity.status, ToolStatus) else entity.status,
    )


def model_to_tool(model: ToolModel) -> Tool:
    return Tool(
        id=model.id,
        project_id=model.project_id,
        agent_id=model.agent_id,
        name=model.name,
        description=model.description,
        type=ToolType(model.type),
        config=model.config,
        input_schema=model.input_schema,
        output_schema=model.output_schema,
        risk_level=RiskLevel(model.risk_level),
        timeout_ms=model.timeout_ms,
        status=ToolStatus(model.status),
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def secret_to_model(entity: Secret) -> SecretModel:
    return SecretModel(
        id=entity.id,
        project_id=entity.project_id,
        name=entity.name,
        type=entity.type.value if isinstance(entity.type, SecretType) else entity.type,
        encrypted_value=entity.encrypted_value,
        data=entity.data,
    )


def model_to_secret(model: SecretModel) -> Secret:
    return Secret(
        id=model.id,
        project_id=model.project_id,
        name=model.name,
        type=SecretType(model.type),
        encrypted_value=model.encrypted_value,
        data=model.data,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )

