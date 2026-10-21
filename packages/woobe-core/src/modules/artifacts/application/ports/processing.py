from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from typing import Protocol

from modules.artifacts.application.contracts.jobs import JobLease, ProcessingJobResult
from modules.artifacts.application.contracts.processing import ProcessingRecipe
from modules.artifacts.domain.models import Revision
from shared.contracts.object_storage import ObjectStorage


@dataclass(frozen=True)
class ProcessingExecution:
    lease: JobLease
    source: Revision
    storage: ObjectStorage
    checkpoints: dict[str, dict]
    reauthorize: Callable[[], Awaitable[dict]]
    publication_phase: Callable[[str, object], Awaitable[dict]] | None = None
    transient: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ProcessingStage:
    name: str
    execute: Callable[[ProcessingExecution], Awaitable[dict]]


class ProcessingPipeline(Protocol):
    def stages(self, recipe: ProcessingRecipe) -> tuple[ProcessingStage, ...]: ...
    def result(self, context: ProcessingExecution) -> ProcessingJobResult: ...


class PdfPageRenderer(Protocol):
    async def render(self, revision: Revision, content: AsyncIterator[bytes], recipe: ProcessingRecipe,
                     *, page_index: int, dpi: int, max_pixels: int) -> bytes: ...
