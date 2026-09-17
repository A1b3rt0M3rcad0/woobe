from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

import uuid6

from modules.network.domain.enums import (
    NetworkEnvironment,
    NetworkExecutionStatus,
    NetworkInvocationStatus,
    NetworkSessionStatus,
    NetworkVersionKind,
)


@dataclass(frozen=True)
class NetworkLimits:
    max_depth: int = 4
    max_invocations: int = 16
    timeout_seconds: int = 90
    tool_result_max_chars: int = 16_000


@dataclass(frozen=True)
class AgentBindingSelector:
    source: str = "draft"
    release_id: UUID | None = None

    @classmethod
    def from_dict(cls, value: Any) -> AgentBindingSelector:
        raw = value if isinstance(value, dict) else {}
        source = str(raw.get("source") or "draft").strip().lower()
        if source not in {"draft", "staging", "release"}:
            raise ValueError("Agent binding source must be draft, staging or release")
        release_value = raw.get("release_id")
        release_id = UUID(str(release_value)) if release_value else None
        if source == "draft" and release_id is not None:
            raise ValueError("Draft Agent binding cannot include release_id")
        if source != "draft" and release_id is None:
            raise ValueError(f"{source.title()} Agent binding requires release_id")
        return cls(source=source, release_id=release_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "release_id": str(self.release_id) if self.release_id else None,
        }


@dataclass(frozen=True)
class NetworkNode:
    id: UUID
    agent_id: UUID
    label: str
    capability_description: str = ""
    position: dict[str, float] = field(default_factory=dict)
    binding: AgentBindingSelector = field(default_factory=AgentBindingSelector)


@dataclass(frozen=True)
class NetworkEdge:
    id: UUID
    source_node_id: UUID
    target_node_id: UUID


@dataclass(frozen=True)
class NetworkDefinition:
    root_node_id: UUID
    nodes: tuple[NetworkNode, ...]
    edges: tuple[NetworkEdge, ...]
    limits: NetworkLimits = field(default_factory=NetworkLimits)
    session_mode: str = "stateful"
    schema_version: int = 2

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> NetworkDefinition:
        settings = value.get("settings") or {}
        return cls(
            root_node_id=UUID(str(value["root_node_id"])),
            nodes=tuple(
                NetworkNode(
                    id=UUID(str(item["id"])),
                    agent_id=UUID(str(item["agent_id"])),
                    label=str(item.get("label") or "Agent"),
                    capability_description=str(
                        item.get("capability_description") or ""
                    ).strip(),
                    position=dict(item.get("position") or {}),
                    binding=AgentBindingSelector.from_dict(item.get("binding")),
                )
                for item in value.get("nodes", [])
            ),
            edges=tuple(
                NetworkEdge(
                    id=UUID(str(item["id"])),
                    source_node_id=UUID(str(item["source_node_id"])),
                    target_node_id=UUID(str(item["target_node_id"])),
                )
                for item in value.get("edges", [])
            ),
            limits=NetworkLimits(
                max_depth=int(settings.get("max_depth", 4)),
                max_invocations=int(settings.get("max_invocations", 16)),
                timeout_seconds=int(settings.get("timeout_seconds", 90)),
                tool_result_max_chars=int(settings.get("tool_result_max_chars", 16_000)),
            ),
            session_mode=str(settings.get("session_mode", "stateful")),
            schema_version=2,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 2,
            "root_node_id": str(self.root_node_id),
            "nodes": [
                {
                    "id": str(node.id),
                    "agent_id": str(node.agent_id),
                    "label": node.label,
                    "capability_description": node.capability_description,
                    "position": node.position,
                    "binding": node.binding.to_dict(),
                }
                for node in self.nodes
            ],
            "edges": [
                {
                    "id": str(edge.id),
                    "source_node_id": str(edge.source_node_id),
                    "target_node_id": str(edge.target_node_id),
                }
                for edge in self.edges
            ],
            "settings": {
                "session_mode": self.session_mode,
                "max_depth": self.limits.max_depth,
                "max_invocations": self.limits.max_invocations,
                "timeout_seconds": self.limits.timeout_seconds,
                "tool_result_max_chars": self.limits.tool_result_max_chars,
            },
        }


@dataclass
class Network:
    project_id: UUID
    name: str
    description: str = ""
    draft_definition: dict[str, Any] = field(default_factory=dict)
    draft_revision: int = 0
    staging_version_id: UUID | None = None
    production_version_id: UUID | None = None
    id: UUID = field(default_factory=uuid6.uuid7)
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class NetworkVersion:
    network_id: UUID
    project_id: UUID
    kind: NetworkVersionKind
    version: str
    definition: dict[str, Any]
    resolved_bindings: dict[str, Any]
    composition_hash: str
    created_by: UUID | None = None
    rollback_of_version_id: UUID | None = None
    id: UUID = field(default_factory=uuid6.uuid7)
    created_at: datetime | None = None


@dataclass
class NetworkSession:
    network_id: UUID
    network_version_id: UUID | None
    project_id: UUID
    environment: NetworkEnvironment
    title: str = "New Network session"
    tenant_id: str | None = None
    user_id: str | None = None
    external_session_id: str | None = None
    status: NetworkSessionStatus = NetworkSessionStatus.ACTIVE
    id: UUID = field(default_factory=uuid6.uuid7)
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class NetworkExecution:
    network_id: UUID
    network_version_id: UUID | None
    network_session_id: UUID
    project_id: UUID
    input_message: str
    draft_revision: int | None = None
    definition_snapshot: dict[str, Any] | None = None
    resolved_bindings_snapshot: dict[str, Any] | None = None
    status: NetworkExecutionStatus = NetworkExecutionStatus.QUEUED
    idempotency_key: str | None = None
    output_message: str | None = None
    root_trace_id: UUID | None = None
    attempt: int = 0
    lease_owner: str | None = None
    lease_generation: int = 0
    lease_expires_at: datetime | None = None
    heartbeat_at: datetime | None = None
    cancel_requested_at: datetime | None = None
    failure_code: str | None = None
    failure_detail: str | None = None
    last_event_sequence: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    id: UUID = field(default_factory=uuid6.uuid7)
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class NetworkInvocation:
    network_execution_id: UUID
    network_session_id: UUID
    node_id: UUID
    agent_id: UUID
    depth: int
    parent_invocation_id: UUID | None = None
    agent_session_id: UUID | None = None
    trace_id: UUID | None = None
    status: NetworkInvocationStatus = NetworkInvocationStatus.PENDING
    input_message: str = ""
    output_message: str | None = None
    error: str | None = None
    id: UUID = field(default_factory=uuid6.uuid7)
    created_at: datetime | None = None
    updated_at: datetime | None = None
