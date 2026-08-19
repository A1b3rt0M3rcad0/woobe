from modules.agent.application.dtos.knowledge_dtos import UpdateCollectionInput, UpdateCollectionOutput
from modules.agent.application.interfaces.repositories import DocumentCollectionRepository
from shared.contracts.errors import ValidationError


class UpdateCollectionUseCase:
    def __init__(self, repo: DocumentCollectionRepository) -> None:
        self.repo = repo

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
