from __future__ import annotations

import base64
import json
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import and_, func, or_, select

from modules.agent.infra.database.provider_model_repositories import ProviderModelModel
from modules.evaluation.application.operational_service import (
    OperationalEvaluationApplicationService,
)
from modules.evaluation.infra.database.models import (
    EvaluationAuthoringCallModel,
    EvaluationDatasetModel,
    EvaluationDatasetVersionModel,
    EvaluationRunModel,
    EvaluationSuiteModel,
    EvaluationSuiteVersionModel,
    EvaluationTargetModel,
    EvaluationTestCaseModel,
)
from shared.infra.errors import NotFoundError, ValidationError


def _encode_cursor(created_at: datetime, row_id: UUID) -> str:
    raw = json.dumps(
        {"created_at": created_at.isoformat(), "id": str(row_id)},
        separators=(",", ":"),
    ).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_cursor(value: str | None) -> tuple[datetime, UUID] | None:
    if not value:
        return None
    try:
        padded = value + "=" * (-len(value) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
        return datetime.fromisoformat(str(payload["created_at"])), UUID(str(payload["id"]))
    except Exception as exc:
        raise ValidationError("Invalid pagination cursor") from exc


def _cursor_filter(model, decoded: tuple[datetime, UUID] | None):
    if decoded is None:
        return None
    created_at, row_id = decoded
    return or_(
        model.created_at < created_at,
        and_(model.created_at == created_at, model.id < row_id),
    )


class CompletedEvaluationApplicationService(OperationalEvaluationApplicationService):
    """Final MVP facade for operational Evaluation reads and lifecycle actions."""

    async def _dataset_item(self, session, dataset: EvaluationDatasetModel) -> dict[str, Any]:
        version = (
            await session.get(EvaluationDatasetVersionModel, dataset.current_version_id)
            if dataset.current_version_id
            else None
        )
        case_count = int(
            await session.scalar(
                select(func.count(EvaluationTestCaseModel.id)).where(
                    EvaluationTestCaseModel.dataset_version_id == dataset.current_version_id
                )
            )
            or 0
        )
        item = self._dataset_payload(dataset, version, case_count)
        item.update(
            {
                "archived_at": dataset.archived_at,
                "archived_by": str(dataset.archived_by) if dataset.archived_by else None,
                "authoring_source": version.authoring_source if version else "manual",
                "source_snapshot_hash": version.source_snapshot_hash if version else None,
                "source_context_hash": version.source_context_hash if version else None,
                "authoring_metadata": version.authoring_metadata if version else None,
            }
        )
        return item

    async def _suite_item(self, session, suite: EvaluationSuiteModel) -> dict[str, Any]:
        version = (
            await session.get(EvaluationSuiteVersionModel, suite.current_version_id)
            if suite.current_version_id
            else None
        )
        item = self._suite_payload(suite, version)
        dataset_version = (
            await session.get(EvaluationDatasetVersionModel, version.dataset_version_id)
            if version
            else None
        )
        case_count = int(
            await session.scalar(
                select(func.count(EvaluationTestCaseModel.id)).where(
                    EvaluationTestCaseModel.dataset_version_id
                    == (version.dataset_version_id if version else None)
                )
            )
            or 0
        )
        item.update(
            {
                "dataset_id": (
                    str(dataset_version.dataset_id)
                    if dataset_version is not None
                    else None
                ),
                "case_count": case_count,
                "archived_at": suite.archived_at,
                "archived_by": str(suite.archived_by) if suite.archived_by else None,
                "authoring_source": (
                    dataset_version.authoring_source
                    if dataset_version is not None
                    else "manual"
                ),
                "source_snapshot_hash": (
                    dataset_version.source_snapshot_hash
                    if dataset_version is not None
                    else None
                ),
                "source_context_hash": (
                    dataset_version.source_context_hash
                    if dataset_version is not None
                    else None
                ),
                "authoring_metadata": (
                    dataset_version.authoring_metadata
                    if dataset_version is not None
                    else None
                ),
                "parent_version_id": (
                    str(version.parent_version_id)
                    if version and version.parent_version_id
                    else None
                ),
                "change_description": version.change_description if version else None,
            }
        )
        item["staleness"] = await self._suite_staleness(
            session,
            project_id=suite.project_id,
            item=item,
        )
        return item

    async def list_datasets_operational(
        self,
        project_id: UUID,
        *,
        include_archived: bool = False,
    ) -> list[dict[str, Any]]:
        async with self._session_factory() as session:
            statement = select(EvaluationDatasetModel).where(
                EvaluationDatasetModel.project_id == project_id
            )
            if not include_archived:
                statement = statement.where(EvaluationDatasetModel.status != "archived")
            rows = list(
                (
                    await session.scalars(
                        statement.order_by(
                            EvaluationDatasetModel.updated_at.desc(),
                            EvaluationDatasetModel.id.desc(),
                        )
                    )
                ).all()
            )
            return [await self._dataset_item(session, row) for row in rows]

    async def list_suites(
        self,
        project_id: UUID,
        *,
        include_archived: bool = False,
    ) -> list[dict[str, Any]]:
        async with self._session_factory() as session:
            statement = select(EvaluationSuiteModel).where(
                EvaluationSuiteModel.project_id == project_id
            )
            if not include_archived:
                statement = statement.where(EvaluationSuiteModel.status != "archived")
            rows = list(
                (
                    await session.scalars(
                        statement.order_by(
                            EvaluationSuiteModel.updated_at.desc(),
                            EvaluationSuiteModel.id.desc(),
                        )
                    )
                ).all()
            )
            return [await self._suite_item(session, row) for row in rows]

    async def list_datasets_page(
        self,
        project_id: UUID,
        *,
        limit: int,
        cursor: str | None,
        include_archived: bool = False,
    ) -> dict[str, Any]:
        limit = min(max(int(limit), 1), 200)
        decoded = _decode_cursor(cursor)
        async with self._session_factory() as session:
            statement = select(EvaluationDatasetModel).where(
                EvaluationDatasetModel.project_id == project_id
            )
            if not include_archived:
                statement = statement.where(EvaluationDatasetModel.status != "archived")
            condition = _cursor_filter(EvaluationDatasetModel, decoded)
            if condition is not None:
                statement = statement.where(condition)
            rows = list(
                (
                    await session.scalars(
                        statement.order_by(
                            EvaluationDatasetModel.created_at.desc(),
                            EvaluationDatasetModel.id.desc(),
                        ).limit(limit + 1)
                    )
                ).all()
            )
            return await self._page_payload(
                rows,
                limit=limit,
                builder=lambda row: self._dataset_item(session, row),
            )

    async def list_suites_page(
        self,
        project_id: UUID,
        *,
        limit: int,
        cursor: str | None,
        include_archived: bool = False,
    ) -> dict[str, Any]:
        limit = min(max(int(limit), 1), 200)
        decoded = _decode_cursor(cursor)
        async with self._session_factory() as session:
            statement = select(EvaluationSuiteModel).where(
                EvaluationSuiteModel.project_id == project_id
            )
            if not include_archived:
                statement = statement.where(EvaluationSuiteModel.status != "archived")
            condition = _cursor_filter(EvaluationSuiteModel, decoded)
            if condition is not None:
                statement = statement.where(condition)
            rows = list(
                (
                    await session.scalars(
                        statement.order_by(
                            EvaluationSuiteModel.created_at.desc(),
                            EvaluationSuiteModel.id.desc(),
                        ).limit(limit + 1)
                    )
                ).all()
            )
            return await self._page_payload(
                rows,
                limit=limit,
                builder=lambda row: self._suite_item(session, row),
            )

    async def list_runs_page(
        self,
        project_id: UUID,
        *,
        limit: int,
        cursor: str | None,
    ) -> dict[str, Any]:
        limit = min(max(int(limit), 1), 200)
        decoded = _decode_cursor(cursor)
        async with self._session_factory() as session:
            statement = select(EvaluationRunModel).where(
                EvaluationRunModel.project_id == project_id
            )
            condition = _cursor_filter(EvaluationRunModel, decoded)
            if condition is not None:
                statement = statement.where(condition)
            rows = list(
                (
                    await session.scalars(
                        statement.order_by(
                            EvaluationRunModel.created_at.desc(),
                            EvaluationRunModel.id.desc(),
                        ).limit(limit + 1)
                    )
                ).all()
            )

            async def build(run: EvaluationRunModel) -> dict[str, Any]:
                targets = list(
                    (
                        await session.scalars(
                            select(EvaluationTargetModel).where(
                                EvaluationTargetModel.evaluation_run_id == run.id
                            )
                        )
                    ).all()
                )
                item = self._run_payload(run, targets)
                item["execution_policy"] = run.execution_policy or {}
                return item

            return await self._page_payload(rows, limit=limit, builder=build)

    @staticmethod
    async def _page_payload(rows, *, limit: int, builder) -> dict[str, Any]:
        has_more = len(rows) > limit
        page = rows[:limit]
        items = [await builder(row) for row in page]
        return {
            "items": items,
            "next_cursor": (
                _encode_cursor(page[-1].created_at, page[-1].id)
                if has_more and page
                else None
            ),
            "has_more": has_more,
        }

    async def archive_suite(
        self,
        project_id: UUID,
        suite_id: UUID,
        user_id: UUID | None,
    ) -> dict[str, Any]:
        await super().archive_suite(project_id, suite_id, user_id)
        async with self._session_factory() as session:
            row = await session.get(EvaluationSuiteModel, suite_id)
            if row is None or row.project_id != project_id:
                raise NotFoundError("Evaluation Suite not found")
            return await self._suite_item(session, row)

    async def restore_suite(self, project_id: UUID, suite_id: UUID) -> dict[str, Any]:
        await super().restore_suite(project_id, suite_id)
        async with self._session_factory() as session:
            row = await session.get(EvaluationSuiteModel, suite_id)
            if row is None or row.project_id != project_id:
                raise NotFoundError("Evaluation Suite not found")
            return await self._suite_item(session, row)

    async def create_composed_suite_version(self, **kwargs) -> dict[str, Any]:
        project_id: UUID = kwargs["project_id"]
        authoring_source = str(kwargs.get("authoring_source") or "manual")
        metadata = dict(kwargs.get("authoring_metadata") or {})
        judge_provider_model_id = kwargs.get("judge_provider_model_id")
        async with self._session_factory() as session:
            if judge_provider_model_id is not None:
                model = await session.get(ProviderModelModel, judge_provider_model_id)
                if (
                    model is None
                    or model.project_id != project_id
                    or model.status != "active"
                ):
                    raise NotFoundError("Judge Provider Model not found or inactive")
            if authoring_source == "ai_generated":
                call_id = metadata.get("authoring_call_id")
                if not call_id:
                    raise ValidationError(
                        "AI-generated Suite version requires authoring_call_id"
                    )
                try:
                    call = await session.get(
                        EvaluationAuthoringCallModel,
                        UUID(str(call_id)),
                    )
                except (TypeError, ValueError) as exc:
                    raise ValidationError("authoring_call_id is invalid") from exc
                if (
                    call is None
                    or call.project_id != project_id
                    or call.status != "completed"
                ):
                    raise ValidationError(
                        "AI authoring call was not completed for this Project"
                    )
                if kwargs.get("source_snapshot_hash") != call.target_snapshot_hash:
                    raise ValidationError(
                        "Suite source_snapshot_hash does not match its authoring call"
                    )
                if kwargs.get("source_context_hash") != call.context_hash:
                    raise ValidationError(
                        "Suite source_context_hash does not match its authoring call"
                    )
        return await super().create_composed_suite_version(**kwargs)

    async def get_run(self, project_id: UUID, run_id: UUID) -> dict[str, Any]:
        payload = await super().get_run(project_id, run_id)
        async with self._session_factory() as session:
            run = await session.get(EvaluationRunModel, run_id)
            if run is None or run.project_id != project_id:
                raise NotFoundError("Evaluation Run not found")
            payload["execution_policy"] = run.execution_policy or {}
            for item in payload.get("trials", []):
                network_execution_id = item.get("network_execution_id")
                trace_id = item.get("trace_id") or item.get("root_trace_id")
                if network_execution_id:
                    item["execution_reference"] = {
                        "kind": "network_execution",
                        "network_execution_id": network_execution_id,
                        "trace_id": trace_id,
                    }
                elif trace_id:
                    item["execution_reference"] = {
                        "kind": "agent_trace",
                        "trace_id": trace_id,
                    }
                else:
                    item["execution_reference"] = None
        return payload

    async def list_runs(self, project_id: UUID, limit: int = 100) -> list[dict[str, Any]]:
        values = await super().list_runs(project_id, limit=limit)
        async with self._session_factory() as session:
            run_ids = [UUID(str(item["id"])) for item in values]
            rows = (
                list(
                    (
                        await session.scalars(
                            select(EvaluationRunModel).where(
                                EvaluationRunModel.id.in_(run_ids)
                            )
                        )
                    ).all()
                )
                if run_ids
                else []
            )
            by_id = {str(item.id): item for item in rows}
            for item in values:
                row = by_id.get(str(item["id"]))
                item["execution_policy"] = row.execution_policy if row else {}
        return values

    async def _suite_staleness(
        self,
        session,
        *,
        project_id: UUID,
        item: dict[str, Any],
    ) -> dict[str, Any]:
        source_hash = item.get("source_snapshot_hash")
        if not source_hash:
            return {
                "status": "generic",
                "source_snapshot_hash": None,
                "current_snapshot_hash": None,
            }
        metadata = (
            item.get("authoring_metadata")
            if isinstance(item.get("authoring_metadata"), dict)
            else {}
        )
        reference = (
            metadata.get("reference_target")
            if isinstance(metadata.get("reference_target"), dict)
            else None
        )
        call = None
        call_id = metadata.get("authoring_call_id")
        if call_id:
            try:
                call = await session.get(
                    EvaluationAuthoringCallModel,
                    UUID(str(call_id)),
                )
            except (TypeError, ValueError):
                call = None
        if reference is None and call is not None and call.project_id == project_id:
            reference = {
                "target_type": call.target_type,
                "source_type": call.target_source_type,
                "entity_id": str(call.target_entity_id),
                "version_id": (
                    str(call.target_version_id) if call.target_version_id else None
                ),
            }
        if reference is None:
            return {
                "status": "current_unknown",
                "source_snapshot_hash": source_hash,
                "current_snapshot_hash": None,
            }
        source_type = str(reference.get("source_type") or "draft")
        version_id = reference.get("version_id") if source_type == "release" else None
        try:
            resolved = await self._target_resolver.resolve(
                session,
                project_id=project_id,
                target_type=str(reference.get("target_type") or "agent"),
                source_type=source_type,
                entity_id=UUID(str(reference["entity_id"])),
                version_id=UUID(str(version_id)) if version_id else None,
            )
        except Exception:
            return {
                "status": "target_unavailable",
                "source_snapshot_hash": source_hash,
                "current_snapshot_hash": None,
            }
        return {
            "status": "current" if resolved.snapshot_hash == source_hash else "stale",
            "source_snapshot_hash": source_hash,
            "current_snapshot_hash": resolved.snapshot_hash,
            "target_type": resolved.target_type,
            "entity_id": str(resolved.entity_id),
            "source_type": source_type,
            "display_version": resolved.display_version,
        }


__all__ = ["CompletedEvaluationApplicationService"]
