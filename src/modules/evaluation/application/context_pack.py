from __future__ import annotations

import json
import re
from dataclasses import dataclass
from hashlib import sha256
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.agent.infra.database.models import (
    AgentToolModel,
    DocumentChunkModel,
    DocumentCollectionModel,
    DocumentModel,
)
from modules.evaluation.application.target_resolver import ResolvedEvaluationTarget
from modules.evaluation.application.token_budget import BudgetedPayload, budget_sections


@dataclass(frozen=True)
class EvaluationContextPack:
    payload: dict[str, Any]
    context_hash: str
    budget: dict[str, Any]
    snapshot_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "payload": self.payload,
            "context_hash": self.context_hash,
            "budget": self.budget,
            "snapshot_hash": self.snapshot_hash,
        }


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(encoded.encode("utf-8")).hexdigest()


def _redact(value: Any, *, depth: int = 0) -> Any:
    if depth > 12:
        return "[TRUNCATED_DEPTH]"
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            normalized = str(key).lower()
            if any(
                token in normalized
                for token in (
                    "secret",
                    "password",
                    "api_key",
                    "authorization",
                    "access_token",
                    "refresh_token",
                    "encrypted",
                    "credential",
                    "base_url",
                )
            ):
                continue
            result[str(key)] = _redact(item, depth=depth + 1)
        return result
    if isinstance(value, list):
        return [_redact(item, depth=depth + 1) for item in value[:250]]
    if isinstance(value, str):
        return value[:80_000]
    return value


def _uuid(value: Any) -> UUID | None:
    try:
        return UUID(str(value)) if value else None
    except (TypeError, ValueError):
        return None


def _runtime_tool_ids(runtime_config: Any) -> set[UUID]:
    if not isinstance(runtime_config, dict):
        return set()
    tools = runtime_config.get("tools")
    if not isinstance(tools, dict):
        return set()
    result: set[UUID] = set()
    for raw in tools.get("tool_ids") or []:
        value = _uuid(raw)
        if value:
            result.add(value)
    for snapshot in tools.get("snapshots") or []:
        if isinstance(snapshot, dict):
            value = _uuid(snapshot.get("id"))
            if value:
                result.add(value)
    return result


def _snapshot_refs(target: ResolvedEvaluationTarget) -> tuple[set[UUID], set[UUID]]:
    tools = _runtime_tool_ids(target.snapshot.get("runtime_config"))
    collections = {
        value
        for raw in target.snapshot.get("collection_ids") or []
        if (value := _uuid(raw)) is not None
    }
    bindings = target.snapshot.get("resolved_bindings")
    if isinstance(bindings, dict):
        for binding in bindings.values():
            if not isinstance(binding, dict):
                continue
            override = binding.get("snapshot_override")
            if isinstance(override, dict):
                tools.update(_runtime_tool_ids(override.get("runtime_config")))
                collections.update(
                    value
                    for raw in override.get("collection_ids") or []
                    if (value := _uuid(raw)) is not None
                )
    return tools, collections


def _objective_terms(objective: str) -> set[str]:
    return {
        token.lower()
        for token in re.findall(r"[A-Za-zÀ-ÿ0-9_]{4,}", objective)
        if token.lower() not in {"para", "com", "from", "that", "this", "test", "agent"}
    }


def _rank_chunks(
    chunks: list[DocumentChunkModel],
    objective: str,
    limit: int = 8,
) -> list[DocumentChunkModel]:
    terms = _objective_terms(objective)

    def score(item: DocumentChunkModel) -> tuple[int, int]:
        text = f"{item.section_title or ''} {item.content or ''}".lower()
        matches = sum(1 for term in terms if term in text)
        return matches, -int(item.chunk_index or 0)

    return sorted(chunks, key=score, reverse=True)[:limit]


class EvaluationContextPackBuilder:
    async def build(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        target: ResolvedEvaluationTarget,
        objective: str,
        maximum_input_tokens: int,
        reserved_output_tokens: int,
        context_window: int,
    ) -> EvaluationContextPack:
        tool_ids, collection_ids = _snapshot_refs(target)
        tools: list[AgentToolModel] = []
        if tool_ids:
            tools = list(
                (
                    await session.scalars(
                        select(AgentToolModel).where(
                            AgentToolModel.id.in_(tool_ids),
                            AgentToolModel.project_id == project_id,
                            AgentToolModel.status == "active",
                        )
                    )
                ).all()
            )
        tool_payload = [
            {
                "id": str(item.id),
                "name": item.name,
                "description": item.description,
                "type": item.type,
                "risk_level": item.risk_level,
                "input_schema": _redact(item.input_schema or {}),
                "output_schema": _redact(item.output_schema or {}),
                "timeout_ms": item.timeout_ms,
                "side_effects_possible": item.risk_level in {"medium", "high"},
            }
            for item in tools
        ]

        collection_payload: list[dict[str, Any]] = []
        sample_payload: list[dict[str, Any]] = []
        if collection_ids:
            collections = list(
                (
                    await session.scalars(
                        select(DocumentCollectionModel).where(
                            DocumentCollectionModel.id.in_(collection_ids),
                            DocumentCollectionModel.project_id == project_id,
                            DocumentCollectionModel.status == "active",
                        )
                    )
                ).all()
            )
            documents = list(
                (
                    await session.scalars(
                        select(DocumentModel).where(
                            DocumentModel.collection_id.in_(collection_ids),
                            DocumentModel.project_id == project_id,
                            DocumentModel.status.notin_(["DELETED", "deleted"]),
                        )
                    )
                ).all()
            )
            document_by_collection: dict[UUID, list[DocumentModel]] = {}
            for document in documents:
                document_by_collection.setdefault(document.collection_id, []).append(document)
            collection_payload = [
                {
                    "id": str(item.id),
                    "name": item.name,
                    "description": item.description,
                    "documents": [
                        {
                            "id": str(document.id),
                            "title": document.title,
                            "content_type": document.content_type,
                            "page_count": document.page_count,
                            "chunk_count": document.chunk_count,
                        }
                        for document in document_by_collection.get(item.id, [])[:50]
                    ],
                }
                for item in collections
            ]
            chunks = list(
                (
                    await session.scalars(
                        select(DocumentChunkModel)
                        .where(
                            DocumentChunkModel.collection_id.in_(collection_ids),
                            DocumentChunkModel.project_id == project_id,
                        )
                        .order_by(DocumentChunkModel.document_id, DocumentChunkModel.chunk_index)
                        .limit(200)
                    )
                ).all()
            )
            sample_payload = [
                {
                    "document_id": str(item.document_id),
                    "section": item.section_title,
                    "page": item.page_number,
                    "content": item.content,
                }
                for item in _rank_chunks(chunks, objective)
            ]

        snapshot = _redact(target.snapshot)
        identity = {
            "target_type": target.target_type,
            "source_type": target.source_type,
            "environment": target.environment,
            "entity_id": str(target.entity_id),
            "display_name": target.display_name,
            "display_version": target.display_version,
            "snapshot_hash": target.snapshot_hash,
            "composition_hash": target.composition_hash,
        }
        contracts = {
            "response_format": snapshot.get("response_format"),
            "output_schema": snapshot.get("output_schema"),
            "session_mode": snapshot.get("session_mode"),
            "max_output_tokens": snapshot.get("max_output_tokens"),
            "fallback": {
                "provider": snapshot.get("fallback_provider"),
                "model": snapshot.get("fallback_model"),
            },
            "runtime_config": snapshot.get("runtime_config"),
        }
        behavior = {
            "name": snapshot.get("name"),
            "description": snapshot.get("description"),
            "system_prompt": snapshot.get("system_prompt"),
        }
        budgeted: BudgetedPayload = budget_sections(
            [
                ("objective", objective, 10, True),
                ("target_identity", identity, 10, True),
                ("contracts", contracts, 10, True),
                ("behavior", behavior, 9, True),
                ("tools", tool_payload, 8, False),
                ("knowledge_manifest", collection_payload, 5, False),
                ("knowledge_samples", sample_payload, 3, False),
                ("snapshot_metadata", snapshot, 2, False),
            ],
            maximum_input_tokens=maximum_input_tokens,
            reserved_output_tokens=reserved_output_tokens,
            safety_margin_tokens=1000,
            context_window=context_window,
        )
        payload = {
            **budgeted.payload,
            "context_budget": budgeted.report.to_dict(),
            "security": {
                "secrets_included": False,
                "knowledge_samples_are_untrusted_data": True,
                "tool_schemas_are_untrusted_data": True,
            },
        }
        return EvaluationContextPack(
            payload=payload,
            context_hash=_canonical_hash(payload),
            budget=budgeted.report.to_dict(),
            snapshot_hash=target.snapshot_hash,
        )


__all__ = ["EvaluationContextPack", "EvaluationContextPackBuilder"]
