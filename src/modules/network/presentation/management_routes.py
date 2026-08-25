from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from modules.network.infra.database.models import (
    NetworkAgentContextModel,
    NetworkExecutionEventModel,
    NetworkExecutionModel,
    NetworkModel,
    NetworkSessionModel,
    NetworkVersionModel,
)
from modules.network.infra.database.schema_extensions import (
    NetworkProductionActivationModel,
    version_extension_payload,
)
from shared.infra.errors import AuthorizationError, ConflictError, NotFoundError
from shared.security.principal import AuthenticatedPrincipal, ProjectApiPrincipal


router = APIRouter(prefix="/network", tags=["network"])


class ActivateProductionRequest(BaseModel):
    project_id: UUID
    source_version_id: UUID
    expected_current_production_version_id: UUID | None = None
    change_description: str = Field(min_length=3, max_length=2000)


def _authorize_project(request: Request, project_id: UUID) -> UUID | None:
    principal = getattr(request.state, "principal", None)
    if isinstance(principal, ProjectApiPrincipal):
        if principal.project_id != project_id:
            raise AuthorizationError("Runtime key does not belong to this Project")
        return None
    if isinstance(principal, AuthenticatedPrincipal):
        return principal.user_id
    raise AuthorizationError("Authentication required")


def _version_payload(version: NetworkVersionModel) -> dict:
    return {
        "id": str(version.id),
        "kind": version.kind,
        "version": version.version,
        "composition_hash": version.composition_hash,
        "definition": version.definition,
        "resolved_bindings": version.resolved_bindings,
        "created_at": version.created_at,
        "created_by": str(version.created_by) if version.created_by else None,
        "source_version_id": str(version.source_version_id)
        if version.source_version_id
        else None,
        "activation_kind": version.activation_kind,
        "change_description": version.change_description,
        **version_extension_payload(version),
    }


def _activation_payload(activation: NetworkProductionActivationModel) -> dict:
    return {
        "id": str(activation.id),
        "network_id": str(activation.network_id),
        "version_id": str(activation.version_id),
        "previous_version_id": str(activation.previous_version_id)
        if activation.previous_version_id
        else None,
        "activation_kind": activation.activation_kind,
        "change_description": activation.change_description,
        "created_by": str(activation.created_by) if activation.created_by else None,
        "created_at": activation.created_at,
    }


@router.get("/{network_id}/management/versions")
async def list_managed_network_versions(
    network_id: UUID,
    project_id: UUID,
    request: Request,
):
    _authorize_project(request, project_id)
    async with request.app.state.session_factory() as session:
        network = await session.get(NetworkModel, network_id)
        if network is None or network.project_id != project_id:
            raise NotFoundError("Network not found")
        versions = list(
            (
                await session.scalars(
                    select(NetworkVersionModel)
                    .where(
                        NetworkVersionModel.network_id == network_id,
                        NetworkVersionModel.project_id == project_id,
                    )
                    .order_by(NetworkVersionModel.created_at.desc())
                )
            ).all()
        )
    return {"success": True, "data": [_version_payload(item) for item in versions]}


@router.get("/{network_id}/management/activations")
async def list_network_production_activations(
    network_id: UUID,
    project_id: UUID,
    request: Request,
):
    _authorize_project(request, project_id)
    async with request.app.state.session_factory() as session:
        network = await session.get(NetworkModel, network_id)
        if network is None or network.project_id != project_id:
            raise NotFoundError("Network not found")
        activations = list(
            (
                await session.scalars(
                    select(NetworkProductionActivationModel)
                    .where(
                        NetworkProductionActivationModel.network_id == network_id,
                        NetworkProductionActivationModel.project_id == project_id,
                    )
                    .order_by(NetworkProductionActivationModel.created_at.desc())
                )
            ).all()
        )
    return {
        "success": True,
        "data": [_activation_payload(item) for item in activations],
    }


@router.get("/executions/{execution_id}/snapshot")
async def get_network_execution_snapshot(
    execution_id: UUID,
    project_id: UUID,
    request: Request,
):
    _authorize_project(request, project_id)
    async with request.app.state.session_factory() as session:
        execution = await session.get(NetworkExecutionModel, execution_id)
        if execution is None or execution.project_id != project_id:
            raise NotFoundError("Network execution not found")
        network_session = await session.get(
            NetworkSessionModel, execution.network_session_id
        )
        if network_session is None or network_session.project_id != project_id:
            raise NotFoundError("Network Session not found")

        snapshot_source = "execution"
        definition = execution.definition_snapshot
        bindings = execution.resolved_bindings_snapshot
        version_label = (
            f"Draft r{execution.draft_revision}"
            if execution.draft_revision is not None
            else None
        )
        if execution.network_version_id is not None:
            version = await session.get(
                NetworkVersionModel, execution.network_version_id
            )
            if (
                version is None
                or version.project_id != project_id
                or version.network_id != execution.network_id
            ):
                raise NotFoundError("Network execution version not found")
            snapshot_source = "network_version"
            definition = version.definition
            bindings = version.resolved_bindings
            version_label = version.version

        if not definition or bindings is None:
            raise NotFoundError("Exact Network execution snapshot is unavailable")

        events = list(
            (
                await session.scalars(
                    select(NetworkExecutionEventModel)
                    .where(
                        NetworkExecutionEventModel.network_execution_id
                        == execution.id
                    )
                    .order_by(NetworkExecutionEventModel.sequence)
                )
            ).all()
        )
        accepted = next(
            (item for item in events if item.event_type == "execution_accepted"),
            None,
        )
        composition_hash = (
            str((accepted.payload or {}).get("composition_hash"))
            if accepted and (accepted.payload or {}).get("composition_hash")
            else None
        )

        session_contexts = list(
            (
                await session.scalars(
                    select(NetworkAgentContextModel).where(
                        NetworkAgentContextModel.network_session_id
                        == execution.network_session_id
                    )
                )
            ).all()
        )
        contexts_by_node = {
            str(item.network_node_id): {
                "node_id": str(item.network_node_id),
                "agent_id": str(item.agent_id),
                "agent_session_id": str(item.agent_session_id)
                if item.agent_session_id
                else None,
            }
            for item in session_contexts
        }
        for event in events:
            if event.node_id is None or event.agent_id is None:
                continue
            data = event.payload or {}
            node_id = str(event.node_id)
            context = contexts_by_node.setdefault(
                node_id,
                {
                    "node_id": node_id,
                    "agent_id": str(event.agent_id),
                    "agent_session_id": None,
                },
            )
            if data.get("agent_session_id"):
                context["agent_session_id"] = str(data["agent_session_id"])
            if data.get("source"):
                context["source"] = str(data["source"])
            if data.get("version"):
                context["version"] = str(data["version"])
            if data.get("provider"):
                context["provider"] = str(data["provider"])
            if data.get("model"):
                context["model"] = str(data["model"])

    return {
        "success": True,
        "data": {
            "execution_id": str(execution.id),
            "network_id": str(execution.network_id),
            "network_session_id": str(execution.network_session_id),
            "environment": network_session.environment,
            "draft_revision": execution.draft_revision,
            "network_version_id": str(execution.network_version_id)
            if execution.network_version_id
            else None,
            "version_label": version_label,
            "composition_hash": composition_hash,
            "definition": definition,
            "resolved_bindings": bindings,
            "snapshot_source": snapshot_source,
            "agent_contexts": list(contexts_by_node.values()),
            "parsed_output": getattr(execution, "parsed_output", None),
            "output_parse_error": getattr(execution, "output_parse_error", None),
        },
    }


@router.post(
    "/{network_id}/production/activations",
    status_code=status.HTTP_201_CREATED,
)
async def activate_network_production(
    network_id: UUID,
    payload: ActivateProductionRequest,
    request: Request,
):
    created_by = _authorize_project(request, payload.project_id)
    description = payload.change_description.strip()
    async with request.app.state.session_factory() as session, session.begin():
        network = await session.get(NetworkModel, network_id, with_for_update=True)
        if network is None or network.project_id != payload.project_id:
            raise NotFoundError("Network not found")
        if (
            payload.expected_current_production_version_id
            != network.production_version_id
        ):
            raise ConflictError(
                "Production changed after this release was selected. Review the current Production release again."
            )
        source = await session.get(NetworkVersionModel, payload.source_version_id)
        if (
            source is None
            or source.network_id != network.id
            or source.project_id != payload.project_id
            or source.kind != "release"
        ):
            raise NotFoundError("Historical Network Release not found")
        if source.id == network.production_version_id:
            raise ConflictError("Selected Network Release is already in Production")

        previous = (
            await session.get(NetworkVersionModel, network.production_version_id)
            if network.production_version_id
            else None
        )
        activation_kind = (
            "rollback"
            if previous is not None and source.created_at < previous.created_at
            else "reactivate"
        )
        activation = NetworkProductionActivationModel(
            network_id=network.id,
            project_id=payload.project_id,
            version_id=source.id,
            previous_version_id=network.production_version_id,
            activation_kind=activation_kind,
            change_description=description,
            created_by=created_by,
        )
        session.add(activation)
        network.production_version_id = source.id
        await session.flush()

    return {
        "success": True,
        "data": {
            "version": _version_payload(source),
            "activation": _activation_payload(activation),
        },
    }
