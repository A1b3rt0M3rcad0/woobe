from typing import Protocol

from modules.core.application.dtos.imported_environment_dtos import (
    CreateImportedEnvironmentInput,
)


class ImportedEnvironmentRepository(Protocol):
    async def create(self, definition: CreateImportedEnvironmentInput) -> dict: ...


class CreateImportedEnvironmentUseCase:
    def __init__(self, repository: ImportedEnvironmentRepository):
        self._repository = repository

    async def execute(self, definition: CreateImportedEnvironmentInput) -> dict:
        return await self._repository.create(definition)
