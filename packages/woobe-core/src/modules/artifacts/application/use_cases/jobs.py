import time

from modules.artifacts.application.authorization import ArtifactAuthorization, principal_identity
from modules.artifacts.application.contracts.document_models import DocumentModelBindingRequest
from modules.artifacts.application.contracts.jobs import ProcessingJobResult
from modules.artifacts.application.contracts.profiles import SelectProcessingProfile
from modules.artifacts.application.ports.jobs import ProcessingJobStore
from modules.artifacts.application.processing_registry import ProcessingRegistry
from modules.artifacts.domain.models import Action, ArtifactError, ArtifactRef
from shared.observability.metrics import runtime_metrics


class ProcessingJobUseCases:
    def __init__(self, jobs: ProcessingJobStore, catalog, profiles,
                 authorization: ArtifactAuthorization, registry: ProcessingRegistry, representations=None, indexes=None, model_bindings=None, model_calls=None):
        self._jobs, self._catalog, self._profiles = jobs, catalog, profiles
        self._authorization, self._registry = authorization, registry
        self._representations, self._indexes = representations, indexes
        self._model_bindings, self._model_calls = model_bindings, model_calls

    async def request(self, request):
        started = time.perf_counter()
        definition = request.definition
        await self._authorization.authorize(request.principal, request.scope, request.workspace_id, Action.PROCESS)
        replay = await self._jobs.lookup(request, principal_identity(request.principal))
        if replay is not None:
            return replay
        selection = await self._profiles.select(SelectProcessingProfile(request.principal, request.scope,
            request.workspace_id, definition.profile_id, definition.profile_revision))
        source = await self._catalog.revision(request.scope, request.workspace_id,
            ArtifactRef(request.artifact_id, definition.revision_id))
        if source.content_state != 'available':
            raise ArtifactError('SOURCE_UNAVAILABLE', 'Artifact source revision content is unavailable')
        recipe = selection['recipe']
        binding = None
        if recipe.model is not None:
            if self._model_bindings is None:
                raise ArtifactError('MODEL_BINDING_UNAVAILABLE', 'Governed model binding is unavailable')
            binding = await self._model_bindings.freeze(DocumentModelBindingRequest(
                request.principal, request.scope, request.workspace_id, recipe.model))
        readiness = self._registry.readiness(recipe, content_type=source.content_type, model_binding_ready=binding is not None)
        if not readiness['ready']:
            raise ArtifactError('PROCESSOR_UNAVAILABLE', 'Requested processing recipe is unavailable')
        if recipe.mode != 'store_only' and source.size_bytes > recipe.limits.max_bytes:
            raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'Original exceeds the selected processing recipe limit')
        profile = selection['profile']
        arguments = (request, source, recipe, profile.id if profile else None, profile.revision if profile else None)
        result = await self._jobs.request(*arguments, **({'model_binding': binding} if binding is not None else {}))
        runtime_metrics.observe_artifact_operation(
            operation="processing", outcome="success", duration_seconds=time.perf_counter() - started,
        )
        return result

    async def read(self, request):
        await self._authorization.authorize(request.principal, request.scope, request.workspace_id, Action.READ)
        return await self._jobs.read(request, principal_identity(request.principal))

    async def cancel(self, request):
        await self._authorization.authorize(request.principal, request.scope, request.workspace_id, Action.PROCESS)
        return await self._jobs.cancel(request, principal_identity(request.principal))

    async def deliver(self, request):
        return await self._jobs.deliver(request)

    async def claim(self, request):
        return await self._jobs.claim(request)

    async def _authorize_lease(self, lease):
        await self._jobs.guard(lease)
        workspace = await self._authorization.authorize(lease.principal, lease.scope, lease.workspace_id, Action.PROCESS)
        source = await self._catalog.revision(lease.scope, workspace.id,
            ArtifactRef(lease.source.artifact_id, lease.source.revision_id))
        if lease.recipe.model is not None:
            if self._model_bindings is None or lease.model_binding is None:
                raise ArtifactError('MODEL_BINDING_UNAVAILABLE', 'Accepted model binding is unavailable')
            await self._model_bindings.verify(lease.model_binding, lease.scope)
        readiness = self._registry.readiness(lease.recipe, content_type=source.content_type,
            model_binding_ready=lease.model_binding is not None)
        if not readiness['ready']:
            raise ArtifactError('PROCESSOR_UNAVAILABLE', 'Pinned processing recipe is unavailable')
        return workspace, source

    async def prepare(self, phase):
        workspace, source = await self._authorize_lease(phase.lease)
        return {'source': source, 'storage_profile': workspace.storage_profile}

    async def heartbeat(self, phase):
        return await self._jobs.heartbeat(phase)

    async def checkpoint(self, phase):
        await self._authorize_lease(phase.lease)
        return await self._jobs.checkpoint(phase)

    async def finish(self, phase):
        started = time.perf_counter()
        if phase.publication is not None:
            await self._representations.lock_scope(phase.lease.scope, phase.lease.workspace_id)
        replay = await self._jobs.terminal_ack(phase)
        if replay is not None:
            return replay
        if phase.status == 'succeeded':
            await self._authorize_lease(phase.lease)
            ProcessingJobResult.model_validate(phase.result)
            if phase.publication is not None:
                if phase.result['mode'] == 'extract_index' and (self._indexes is None or not phase.publication.get('document_index_id')):
                    raise ArtifactError('REPRESENTATION_NOT_READY', 'Indexed extraction requires its coherent document index')
                await self._representations.commit_ready(phase.lease, phase.publication, phase.result)
                if phase.result['mode'] == 'extract_index':
                    await self._indexes.commit_ready(phase.lease, phase.publication, phase.result)
        result = await self._jobs.finish(phase)
        runtime_metrics.observe_artifact_operation(
            operation="index" if phase.publication is not None else "processing",
            outcome="success" if phase.status == 'succeeded' else "uncertain" if phase.status == 'uncertain' else "error",
            duration_seconds=time.perf_counter() - started,
        )
        return result

    async def reserve_output(self, request):
        await self._representations.lock_scope(request.lease.scope, request.lease.workspace_id)
        await self._authorize_lease(request.lease)
        return await self._representations.reserve(request)

    async def record_output(self, request):
        # Accounting acknowledges previously admitted I/O even after authority
        # changes. It cannot publish or admit another write.
        return await self._representations.record(request)

    async def prepare_bundle(self, request):
        await self._representations.lock_scope(request.lease.scope, request.lease.workspace_id)
        _, source = await self._authorize_lease(request.lease)
        return await self._representations.prepare(request, source)

    async def metadata_bundle(self, request):
        await self._representations.lock_scope(request.lease.scope, request.lease.workspace_id)
        await self._authorize_lease(request.lease)
        return await self._representations.metadata(request)

    async def seal_bundle(self, request):
        await self._representations.lock_scope(request.lease.scope, request.lease.workspace_id)
        await self._authorize_lease(request.lease)
        return await self._representations.seal(request)

    async def prepare_index(self, request):
        await self._representations.lock_scope(request.lease.scope, request.lease.workspace_id)
        await self._authorize_lease(request.lease)
        return await self._indexes.prepare(request)

    async def metadata_index(self, request):
        await self._representations.lock_scope(request.lease.scope, request.lease.workspace_id)
        await self._authorize_lease(request.lease)
        return await self._indexes.metadata(request)

    async def seal_index(self, request):
        await self._representations.lock_scope(request.lease.scope, request.lease.workspace_id)
        await self._authorize_lease(request.lease)
        return await self._indexes.seal(request)

    async def admit_model(self, phase):
        from modules.artifacts.application.services.document_models import model_input, SYSTEM_INSTRUCTION
        await self._authorize_lease(phase.call.lease)
        payload, fingerprint = model_input(phase.call)
        return await self._model_calls.admit(phase.call.lease, operation_key=phase.call.call_id,
            operation=phase.call.operation, input_fingerprint=fingerprint,
            input_bytes=len(payload.encode()) + len(SYSTEM_INSTRUCTION.encode()),
            max_output_tokens=phase.call.max_output_tokens)

    async def model_configuration(self, phase):
        lease = phase.call.lease
        await self._authorize_lease(lease)
        snapshot = lease.model_binding
        # Return only stored accepted metadata through the trusted worker reader.
        return {**snapshot['configuration'], 'project_id': lease.scope.project_id,
            'environment': lease.scope.environment.value, 'operation_kind': 'artifact_processing',
            'operation_id': lease.id}

    async def dispatch_model(self, phase):
        await self._authorize_lease(phase.call.lease)
        return await self._model_calls.dispatched(phase.call.lease, phase.receipt['id'], phase.receipt['nonce'])

    async def observe_model(self, phase):
        started = time.perf_counter()
        result = await self._model_calls.observed(phase.call.lease,
            call_id=phase.receipt['id'], nonce=phase.receipt['nonce'], usage=phase.usage,
            output=phase.output, error_code=phase.error_code, uncertain=phase.uncertain)
        runtime_metrics.observe_artifact_operation(
            operation="model_call",
            outcome="uncertain" if phase.uncertain else "error" if phase.error_code else "success",
            duration_seconds=time.perf_counter() - started,
        )
        return result
