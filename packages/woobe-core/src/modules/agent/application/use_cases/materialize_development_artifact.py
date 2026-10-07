"""Preserve immutable author artifacts when synchronizing a changed Draft."""

import hashlib
import json

from modules.agent.application.interfaces.repositories import (
    AgentPromptRepository,
    AgentContractRepository,
)

from shared.contracts.errors import ConflictError


class MaterializeDevelopmentArtifact:
    def __init__(
        self,
        repository: AgentPromptRepository | AgentContractRepository,
        create,
        output_type,
        fields,
    ):
        self._repository = repository
        self._create = create
        self._output_type = output_type
        self._fields = tuple(fields)

    async def execute(self, input_dto):
        expected = input_dto.model_dump(mode="json")
        version = input_dto.version
        existing = await self._repository.get_by_version(input_dto.agent_id, version)
        if existing is not None and not self._matches(existing, input_dto):
            payload = {field: expected[field] for field in self._fields}
            payload["author_version"] = version
            digest = hashlib.sha256(
                json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            version = "dev-" + digest[:28]
            existing = await self._repository.get_by_version(
                input_dto.agent_id, version
            )
        if existing is not None:
            if existing.project_id != input_dto.project_id or not self._matches(
                existing, input_dto
            ):
                raise ConflictError(
                    "Development artifact version conflicts with existing content"
                )
            return self._output_type(
                **{
                    field: getattr(existing, field)
                    for field in self._output_type.model_fields
                }
            )
        return await self._create.execute(
            input_dto.model_copy(update={"version": version})
        )

    def _matches(self, artifact, input_dto):
        return all(
            getattr(artifact, field) == getattr(input_dto, field)
            for field in self._fields
        )
