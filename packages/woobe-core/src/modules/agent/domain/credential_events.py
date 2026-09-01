from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

import uuid6

from modules.agent.domain.events import AgentDomainEvent


@dataclass(frozen=True)
class AgentProviderCredentialRotatedV1(AgentDomainEvent):
    event_type: str = "agent.credential.rotated.v1"
    event_version: int = 1
    routing_key: str = "agent.credential.rotated.v1"

    @classmethod
    def create(
        cls,
        *,
        credential_id: UUID,
        project_id: UUID,
        provider: str,
        rotated_by_user_id: UUID,
        rotated_at: datetime,
        operation_id: UUID,
        correlation_id: UUID | None = None,
        causation_id: UUID | None = None,
        metadata: dict | None = None,
    ) -> "AgentProviderCredentialRotatedV1":
        idempotency_key = cls.compute_idempotency_key(
            aggregate_type="credential",
            aggregate_id=credential_id,
            event_type="agent.credential.rotated.v1",
            discriminator=str(operation_id),
        )
        return cls(
            payload={
                "aggregate_type": "credential",
                "aggregate_id": str(credential_id),
                "operation_id": str(operation_id),
                "credential_id": str(credential_id),
                "project_id": str(project_id),
                "provider": provider,
                "rotated_by_user_id": str(rotated_by_user_id),
                "rotated_at": rotated_at.isoformat(),
            },
            idempotency_key=idempotency_key,
            correlation_id=correlation_id or uuid6.uuid7(),
            causation_id=causation_id,
            metadata=metadata,
        )
