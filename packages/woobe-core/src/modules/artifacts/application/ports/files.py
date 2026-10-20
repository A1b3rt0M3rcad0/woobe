from typing import Protocol

from modules.artifacts.application.contracts.files import FileSnapshot, MutateFile, ReadFile
from modules.artifacts.domain.models import Artifact, Scope


class FileStore(Protocol):
    async def read(self, request: ReadFile) -> FileSnapshot: ...
    async def page(self, scope: Scope, workspace_id: str, *, directory: str,
                   catalog_version: int, after: str | None, limit: int) -> tuple[Artifact, ...]: ...
    async def mutate(self, request: MutateFile, subject: str) -> Artifact: ...
