from typing import Protocol

from modules.artifacts.application.contracts.document_models import DocumentModelBindingRequest, DocumentModelCall, DocumentModelResponse


class DocumentModelBindings(Protocol):
    async def freeze(self, request: DocumentModelBindingRequest): ...
    async def verify(self, snapshot: dict, scope): ...


class DocumentModelGateway(Protocol):
    """Scoped existing-runtime operations; no Run, global secret or chat loop."""
    async def invoke(self, request: DocumentModelCall) -> DocumentModelResponse: ...
