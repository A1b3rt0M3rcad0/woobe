from dataclasses import replace
import time
import unicodedata

from modules.artifacts.application.authorization import principal_identity
from modules.artifacts.application.contracts.api import CursorEnvelope
from modules.artifacts.application.contracts.search import ArtifactSearchPage, SearchDocuments
from modules.artifacts.domain.models import Action, ArtifactError, opaque_id
from shared.observability.metrics import runtime_metrics


class ArtifactSearchUseCases:
    def __init__(self, store, authorization, cursors, record_source_use=None):
        self._store, self._authorization, self._cursors = store, authorization, cursors
        self._record_source_use = record_source_use

    async def search(self, request: SearchDocuments):
        started = time.perf_counter()
        if not 1 <= request.limit <= 50:
            raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'Search page size must be between 1 and 50')
        query = unicodedata.normalize('NFKC', request.query) if request.mode == 'text' else request.query.strip()
        query = ' '.join(query.split()) if request.mode == 'text' else query
        if not 2 <= len(query) <= 256 or '\x00' in query:
            raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'Search query must contain 2 to 256 characters')
        if request.mode == 'literal' and len(query) < 3:
            raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'Literal search requires at least 3 characters')
        workspace = await self._authorization.authorize(
            request.principal, request.scope, request.workspace_id, Action.SEARCH)
        pinned_catalog_version = request.catalog_version
        catalog_version = pinned_catalog_version if pinned_catalog_version is not None else workspace.catalog_version
        if not 0 <= catalog_version <= workspace.catalog_version:
            raise ArtifactError('ARTIFACT_INVALID_CURSOR', 'Pinned artifact catalog snapshot is unavailable')
        if request.run_id is not None:
            opaque_id(request.run_id)
            if request.catalog_version is None:
                raise ArtifactError('ARTIFACT_INVALID_CURSOR', 'Run search requires an accepted catalog snapshot')
        fingerprint_context = {
            'project': request.scope.project_id,
            'environment': request.scope.environment.value,
            'workspace': request.workspace_id,
            'principal': principal_identity(request.principal),
            'query': query,
            'mode': request.mode,
        }
        if pinned_catalog_version is not None:
            fingerprint_context['catalog_version'] = pinned_catalog_version
        fingerprint = self._cursors.fingerprint(fingerprint_context)
        cursor = self._cursors.decode(request.cursor, fingerprint=fingerprint, purpose='search') if request.cursor else None
        if (cursor is not None and pinned_catalog_version is not None
                and cursor.catalog_version != pinned_catalog_version) or (cursor is not None
                and (cursor.score_rank is None or cursor.search_version is None)):
            raise ArtifactError('ARTIFACT_INVALID_CURSOR', 'Search cursor is invalid for this catalog')
        if cursor is not None:
            catalog_version = cursor.catalog_version
        scoped = replace(request, query=query, catalog_version=catalog_version,
            after_id=cursor.last_id if cursor else None,
            after_score=cursor.score_rank if cursor else None,
            search_version=cursor.search_version if cursor else None)
        result = await self._store.search(scoped)
        runtime_metrics.observe_artifact_operation(
            operation="search", outcome="success", duration_seconds=time.perf_counter() - started,
        )
        hits = result.hits
        has_more, hits = len(hits) > request.limit, hits[:request.limit]
        if request.run_id is not None and self._record_source_use is not None:
            for hit in hits:
                await self._record_source_use(request.scope, request.workspace_id, request.run_id,
                    catalog_version, hit.value.source)
        next_cursor = self._cursors.encode(CursorEnvelope(scope_fingerprint=fingerprint, purpose='search',
            last_id=hits[-1].cursor_id, catalog_version=catalog_version,
            score_rank=hits[-1].score_rank, search_version=result.search_version)) if has_more and hits else None
        return ArtifactSearchPage(query=query, mode=request.mode, catalog_version=catalog_version,
            items=tuple(hit.value for hit in hits), has_more=has_more, next_cursor=next_cursor)
