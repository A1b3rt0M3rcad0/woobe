from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import BigInteger, case, cast, exists, func, literal_column, or_, select

from modules.artifacts.application.authorization import principal_identity
from modules.artifacts.application.contracts.api import SourceReference
from modules.artifacts.application.contracts.search import (
    SearchDocuments, SearchHit, SearchQueryResult, ArtifactSearchResult,
)
from modules.artifacts.domain.models import Action, ArtifactError
from modules.artifacts.infra.database.catalog import CatalogRepository
from modules.artifacts.infra.database.models import (
    ArtifactWorkspaceModel as Workspace, GrantModel, HeadHistoryModel as Head, RevisionModel as Revision,
)
from modules.artifacts.infra.database.representation_models import (
    ArtifactRepresentationSetModel as Generation,
    ArtifactSourceBlockModel as Block,
    ArtifactSourceSegmentModel as Segment,
)


def _literal_pattern(query: str) -> str:
    escaped = query.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
    return f'%{escaped}%'


def _bounded_snippet(value: str, query: str, *, match_location: str) -> str:
    if len(value) <= 512:
        return value
    needle = query.casefold()
    haystack = value.casefold()
    start = haystack.find(needle) if match_location == 'path' else -1
    if start < 0:
        for term in query.split():
            start = haystack.find(term.casefold())
            if start >= 0:
                break
    if start < 0:
        start = 0
    start = max(0, start - 192)
    end = min(len(value), start + 510)
    result = ('…' if start else '') + value[start:end] + ('…' if end < len(value) else '')
    return result[:512]


class ArtifactSearchRepository:
    def __init__(self, uow):
        self._uow, self._catalog = uow, CatalogRepository(uow)

    async def search(self, request: SearchDocuments) -> SearchQueryResult:
        catalog_version = request.catalog_version
        if catalog_version is None:
            raise ValueError('Search requires an immutable catalog version')
        workspace = await self._catalog.workspace_row(request.scope, request.workspace_id)
        search_version = request.search_version if request.search_version is not None else workspace.search_version
        if (catalog_version > workspace.catalog_version or catalog_version < 0
                or search_version > workspace.search_version or search_version < 0):
            raise ArtifactError('ARTIFACT_INVALID_CURSOR', 'Search snapshot is unavailable')

        # Keep path discovery available before extraction has run. A generation
        # cutoff pins whichever canonical text generation is visible on paging.
        principal_id = principal_identity(request.principal)
        permitted = exists(select(GrantModel.id).where(
            GrantModel.project_id == Workspace.project_id,
            GrantModel.environment == Workspace.environment,
            GrantModel.principal_id == principal_id,
            GrantModel.revoked.is_(False),
            GrantModel.actions.contains([Action.SEARCH.value]),
            or_(GrantModel.expires_at.is_(None), GrantModel.expires_at > datetime.now(UTC)),
            or_(GrantModel.workspace_id == Workspace.id,
                GrantModel.external_namespace == Workspace.external_namespace),
        ))
        head_visible = (Head.from_catalog_version <= catalog_version) & or_(
            Head.until_catalog_version.is_(None), Head.until_catalog_version > catalog_version)
        latest_generation = (select(
            Generation.id.label('generation_id'), Head.artifact_id.label('artifact_id'),
            Head.revision_id.label('revision_id'),
            Generation.coverage, Generation.generation_number, Generation.published_search_version,
            Revision.sha256.label('source_sha256'), Head.path, Head.kind,
            func.row_number().over(partition_by=(Head.artifact_id, Head.revision_id), order_by=(
                Generation.published_search_version.desc().nullslast(), Generation.generation_number.desc().nullslast(),
                Generation.id.desc().nullslast())).label('generation_rank'),
        ).select_from(Head)
            .join(Workspace, Workspace.id == Head.workspace_id)
            .join(Revision, (Revision.workspace_id == Head.workspace_id)
                & (Revision.artifact_id == Head.artifact_id) & (Revision.id == Head.revision_id))
            .outerjoin(Generation, (Generation.workspace_id == Head.workspace_id)
                & (Generation.artifact_id == Head.artifact_id) & (Generation.revision_id == Head.revision_id)
                & (Generation.status == 'ready') & (Generation.published_search_version <= search_version))
            .where(Workspace.project_id == UUID(request.scope.project_id),
                Workspace.environment == request.scope.environment.value,
                Workspace.id == request.workspace_id, Workspace.status.in_(['active', 'archived']),
                permitted, Head.kind == 'file', Head.deleted.is_(False), head_visible)
        ).subquery('latest_search_generation')

        path_words = func.regexp_replace(latest_generation.c.path, '[^[:alnum:]]+', ' ', 'g')
        normalized_path = func.normalize(path_words, literal_column('NFKC'))
        path_vector = func.to_tsvector(literal_column("'simple'::regconfig"), normalized_path)
        if request.mode == 'text':
            parsed = func.websearch_to_tsquery('simple', request.query)
            content_match = Segment.search_vector.op('@@')(parsed)
            path_match = path_vector.op('@@')(parsed)
            score = cast(func.floor((func.coalesce(func.ts_rank(Segment.search_vector, parsed), 0)
                + func.ts_rank(path_vector, parsed)) * 1_000_000), BigInteger)
        else:
            pattern = _literal_pattern(request.query)
            content_match = Segment.search_normalized.ilike(pattern, escape='\\')
            path_match = latest_generation.c.path.ilike(pattern, escape='\\')
            score = case((path_match, 1_000_000), else_=999_999).cast(BigInteger)
        snippet = case((path_match, latest_generation.c.path), else_=Segment.search_text)
        location = case((path_match, 'path'), else_='content')
        block_key = case((path_match, 'path'), else_=Segment.block_id)
        cursor_id = case((path_match, latest_generation.c.artifact_id), else_=Segment.id)
        coverage = case((latest_generation.c.generation_id.is_not(None), latest_generation.c.coverage),
            else_='unsupported')
        matches = (select(
            cursor_id.label('cursor_id'), Segment.block_id, Block.source_locator,
            Block.sha256.label('block_sha256'), latest_generation.c.generation_id.label('representation_set_id'),
            latest_generation.c.source_sha256, coverage.label('coverage'),
            latest_generation.c.artifact_id, latest_generation.c.revision_id,
            latest_generation.c.path, snippet.label('matched_text'),
            location.label('match_location'), score.label('score_rank'),
        ).select_from(latest_generation)
            .outerjoin(Segment, Segment.representation_set_id == latest_generation.c.generation_id)
            .outerjoin(Block, (Block.workspace_id == request.workspace_id)
                & (Block.representation_set_id == latest_generation.c.generation_id)
                & (Block.block_id == Segment.block_id))
            .where(latest_generation.c.generation_rank == 1,
                or_(content_match, path_match))
            .distinct(latest_generation.c.artifact_id, latest_generation.c.revision_id, block_key)
            .order_by(latest_generation.c.artifact_id, latest_generation.c.revision_id,
                block_key, score.desc(), cursor_id)
        ).subquery('search_matches')
        page = select(matches)
        if request.after_id is not None:
            if request.after_score is None:
                raise ArtifactError('ARTIFACT_INVALID_CURSOR', 'Search cursor is incomplete')
            page = page.where(or_(matches.c.score_rank < request.after_score,
                (matches.c.score_rank == request.after_score) & (matches.c.cursor_id > request.after_id)))
        page = page.order_by(matches.c.score_rank.desc(), matches.c.cursor_id).limit(request.limit + 1)
        rows = (await self._uow.session.execute(page)).mappings().all()
        results = []
        for row in rows:
            source = SourceReference.model_validate({
                'artifact_id': row.artifact_id,
                'revision_id': row.revision_id,
                'source_sha256': row.source_sha256,
                'representation_set_id': row.representation_set_id,
                'locator': ({**row.source_locator, 'block_id': row.block_id}
                    if row.match_location == 'content' else None),
                'excerpt_sha256': row.block_sha256 if row.match_location == 'content' else None,
            })
            results.append(SearchHit(cursor_id=row.cursor_id, score_rank=row.score_rank,
                value=ArtifactSearchResult(artifact_id=row.artifact_id, revision_id=row.revision_id,
                    path=row.path, kind='file', match_location=row.match_location,
                    snippet=_bounded_snippet(row.matched_text, request.query,
                        match_location=row.match_location), coverage=row.coverage, source=source)))
        return SearchQueryResult(search_version=search_version, hits=tuple(results))
