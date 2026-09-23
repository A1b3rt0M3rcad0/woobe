from modules.agent.application.dtos.knowledge_dtos import UpdateCollectionInput, UpdateCollectionOutput
from modules.agent.application.interfaces.repositories import (
    AgentCollectionRepository,
    DocumentCollectionRepository,
)
from modules.agent.domain.enums import CollectionStatus
from shared.contracts.errors import ConflictError, ValidationError


class UpdateCollectionUseCase:
    def __init__(
        self,
        repo: DocumentCollectionRepository,
        agent_collection_repo: AgentCollectionRepository | None = None,
    ) -> None:
        self.repo = repo
        self._agent_collection_repo = agent_collection_repo

    async def execute(self, input_dto: UpdateCollectionInput) -> UpdateCollectionOutput:
        collection = await self.repo.get_by_id(input_dto.collection_id)

        if "name" in input_dto.model_fields_set:
            name = (input_dto.name or "").strip()
            if not name:
                raise ValidationError("Collection name is required")
            collection.name = name

        if "description" in input_dto.model_fields_set:
            description = (input_dto.description or "").strip()
            collection.description = description or None

        if "status" in input_dto.model_fields_set and input_dto.status is not None:
            if input_dto.status == CollectionStatus.DELETED:
                if self._agent_collection_repo is not None:
                    links = await self._agent_collection_repo.list_by_collection(
                        collection.id
                    )
                    if links:
                        raise ConflictError(
                            "Collection is still attached to one or more Agents"
                        )
            collection.status = input_dto.status

        updated = await self.repo.update(collection)

        return UpdateCollectionOutput(
            id=updated.id,
            project_id=updated.project_id,
            name=updated.name,
            description=updated.description,
            status=updated.status,
            created_at=updated.created_at,
            updated_at=updated.updated_at,
        )
