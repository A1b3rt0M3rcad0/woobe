from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from modules.network.infra.database import models as network_models
from modules.network.infra.database.models import (
    NetworkExecutionModel,
    NetworkInvocationModel,
    NetworkSessionModel,
    NetworkVersionModel,
)
from shared.infra.database.base import BaseModel


def _install_column(model: Any, name: str, column: Any) -> None:
    if not hasattr(model, name):
        setattr(model, name, column)


_install_column(
    NetworkVersionModel, "source_draft_revision", mapped_column(Integer, nullable=True)
)
_install_column(
    NetworkVersionModel,
    "source_staging_version_id",
    mapped_column(
        Uuid(as_uuid=True), ForeignKey("network.network_versions.id"), nullable=True
    ),
)
_install_column(
    NetworkVersionModel,
    "entry_agent_id",
    mapped_column(Uuid(as_uuid=True), nullable=True),
)
_install_column(
    NetworkVersionModel,
    "entry_agent_release_id",
    mapped_column(
        Uuid(as_uuid=True), ForeignKey("agent.agent_releases.id"), nullable=True
    ),
)
_install_column(
    NetworkVersionModel,
    "entry_agent_release_version",
    mapped_column(String(64), nullable=True),
)
_install_column(
    NetworkVersionModel, "public_output_contract", mapped_column(JSONB, nullable=True)
)
_install_column(
    NetworkVersionModel,
    "public_output_contract_hash",
    mapped_column(String(64), nullable=True),
)
_install_column(
    NetworkVersionModel,
    "effective_external_context_contract",
    mapped_column(JSONB, nullable=True),
)
_install_column(
    NetworkVersionModel, "agent_release_manifest", mapped_column(JSONB, nullable=True)
)
_install_column(
    NetworkVersionModel,
    "agent_release_manifest_hash",
    mapped_column(String(64), nullable=True),
)
_install_column(
    NetworkVersionModel,
    "runtime_settings_hash",
    mapped_column(String(64), nullable=True),
)
_install_column(
    NetworkVersionModel, "release_fingerprint", mapped_column(String(64), nullable=True)
)
_install_column(
    NetworkVersionModel, "change_kind", mapped_column(String(32), nullable=True)
)

if "ix_network_versions_release_fingerprint" not in {
    index.name for index in NetworkVersionModel.__table__.indexes
}:
    Index(
        "ix_network_versions_release_fingerprint",
        NetworkVersionModel.__table__.c.network_id,
        NetworkVersionModel.__table__.c.release_fingerprint,
    )
_install_column(
    NetworkSessionModel,
    "external_context_session_values",
    mapped_column(JSONB, nullable=True),
)
_install_column(
    NetworkExecutionModel, "parsed_output", mapped_column(JSONB, nullable=True)
)
_install_column(
    NetworkExecutionModel, "output_parse_error", mapped_column(Text, nullable=True)
)
_install_column(
    NetworkExecutionModel,
    "external_context_snapshot",
    mapped_column(JSONB, nullable=True),
)
_install_column(
    NetworkInvocationModel, "parsed_output", mapped_column(JSONB, nullable=True)
)
_install_column(
    NetworkInvocationModel, "output_parse_error", mapped_column(Text, nullable=True)
)


class NetworkProductionActivationModel(BaseModel):
    __tablename__ = "network_production_activations"
    __table_args__ = (
        Index(
            "ix_network_production_activations_network_created",
            "network_id",
            "created_at",
        ),
        CheckConstraint(
            "activation_kind IN ('publish', 'reactivate', 'rollback')",
            name="ck_network_production_activations_kind",
        ),
        {"schema": "network"},
    )

    network_id: Mapped[UUID] = mapped_column(ForeignKey("network.networks.id"))
    project_id: Mapped[UUID]
    version_id: Mapped[UUID] = mapped_column(ForeignKey("network.network_versions.id"))
    previous_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("network.network_versions.id"), nullable=True
    )
    activation_kind: Mapped[str] = mapped_column(String(32))
    change_description: Mapped[str] = mapped_column(Text)
    created_by: Mapped[UUID | None]


setattr(
    network_models, "NetworkProductionActivationModel", NetworkProductionActivationModel
)


def _uuid_text(version: NetworkVersionModel, name: str) -> str | None:
    value = getattr(version, name, None)
    return str(value) if value else None


def version_extension_payload(version: NetworkVersionModel) -> dict[str, Any]:
    return {
        "source_draft_revision": getattr(version, "source_draft_revision", None),
        "source_staging_version_id": _uuid_text(version, "source_staging_version_id"),
        "entry_agent_id": _uuid_text(version, "entry_agent_id"),
        "entry_agent_release_id": _uuid_text(version, "entry_agent_release_id"),
        "entry_agent_release_version": getattr(
            version, "entry_agent_release_version", None
        ),
        "public_output_contract": getattr(version, "public_output_contract", None),
        "public_output_contract_hash": getattr(
            version, "public_output_contract_hash", None
        ),
        "effective_external_context_contract": getattr(
            version, "effective_external_context_contract", None
        ),
        "agent_release_manifest": getattr(version, "agent_release_manifest", None),
        "agent_release_manifest_hash": getattr(
            version, "agent_release_manifest_hash", None
        ),
        "runtime_settings_hash": getattr(version, "runtime_settings_hash", None),
        "release_fingerprint": getattr(version, "release_fingerprint", None),
        "change_kind": getattr(version, "change_kind", None),
    }
