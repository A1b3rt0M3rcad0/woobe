"""Central configuration API. Responses never contain secret material."""
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr

from modules.core.entrypoint import build_project_configuration_service

Environment = Literal["draft", "staging", "production"]
router = APIRouter(prefix="/projects/{project_id}/configuration", tags=["configuration"])


class StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DeclareKey(StrictBody):
    key: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")
    kind: Literal["value", "secret"] = "secret"
    description: str = Field(default="", max_length=2048)
    value_format: Literal["string", "token", "json", "pem", "url"] = "token"
    validation_rules: dict = Field(default_factory=dict)


class PatchKey(StrictBody):
    expected_revision: StrictInt = Field(ge=1)
    description: str | None = Field(default=None, max_length=2048)
    value_format: Literal["string", "token", "json", "pem", "url"] | None = None
    validation_rules: dict | None = None


class WriteValue(StrictBody):
    expected_revision: StrictInt = Field(ge=0)
    value: StrictStr = Field(max_length=262144, repr=False)


class BatchValue(StrictBody):
    key_id: UUID
    environment: Environment
    expected_revision: StrictInt = Field(ge=0)
    value: StrictStr | None = Field(default=None, max_length=262144, repr=False)
    clear: bool = False


class WriteBatch(StrictBody):
    request_id: str = Field(min_length=1, max_length=128)
    operations: list[BatchValue] = Field(min_length=1, max_length=50)


class GrantUse(StrictBody):
    key_id: UUID
    consumer_kind: Literal["provider_credential", "tool", "secret", "mcp_oauth"]
    consumer_scope: str
    destination: str = Field(max_length=2048)
    environments: list[Environment] = Field(min_length=1, max_length=3)
    field_paths: list[str] = Field(min_length=1, max_length=32)
    expected_revision: StrictInt = Field(ge=0)


class ConvertLegacy(StrictBody):
    environments: list[Environment] = Field(min_length=1, max_length=3)
    expected_revision: StrictInt = Field(ge=1)
    expected_values: dict[Environment, StrictInt]


class MigrationPlan(StrictBody):
    source_kind: Literal["provider_credential", "secret", "tool"] = "provider_credential"
    after_id: UUID | None = None
    limit: StrictInt = Field(default=100, ge=1, le=200)


class MigrationBatch(StrictBody):
    expected_revision: StrictInt = Field(ge=1)
    required_processes: list[StrictStr] = Field(min_length=1, max_length=1000)
    old_processes_drained: bool
    limit: StrictInt = Field(default=10, ge=1, le=20)
    pause: bool = False


async def execute(request, project_id, action, **arguments):
    data = await build_project_configuration_service().execute(action, project_id=project_id,
        principal=request.state.principal, **arguments)
    return {"success": True, "message": "ok", "data": data, "meta": {"complete": True}}


@router.get("/capabilities")
async def capabilities(request: Request, project_id: UUID, environment: Environment = "draft"):
    return await execute(request, project_id, "capabilities", environment=environment)


@router.get("/summary")
async def summary(request: Request, project_id: UUID, environment: Environment = "draft",
                  limit: int = Query(default=50, ge=1, le=200), cursor: str | None = Query(default=None, max_length=1024)):
    return await execute(request, project_id, "summary", environment=environment, limit=limit, cursor=cursor)


@router.post("/migrations/preview")
async def migration_preview(request: Request, project_id: UUID, body: MigrationPlan):
    return await execute(request, project_id, "migration_preview", **body.model_dump())


@router.get("/migration-processes")
async def migration_fleet(request: Request, project_id: UUID,
                          offset: int = Query(default=0, ge=0), limit: int = Query(default=100, ge=1, le=200)):
    return await execute(request, project_id, "migration_fleet", offset=offset, limit=limit)


@router.put("/migrations/{migration_id}")
async def migration_create(request: Request, project_id: UUID, migration_id: UUID, body: MigrationPlan):
    return await execute(request, project_id, "migration_create", migration_id=migration_id, **body.model_dump())


@router.get("/migrations/{migration_id}")
async def migration_status(request: Request, project_id: UUID, migration_id: UUID,
                           offset: int = Query(default=0, ge=0), limit: int = Query(default=50, ge=1, le=200)):
    return await execute(request, project_id, "migration_status", migration_id=migration_id, offset=offset, limit=limit)


@router.post("/migrations/{migration_id}/advance")
async def migration_advance(request: Request, project_id: UUID, migration_id: UUID, body: MigrationBatch):
    return await execute(request, project_id, "migration_advance", migration_id=migration_id, **body.model_dump())


@router.get("/legacy-bindings")
async def legacy(request: Request, project_id: UUID, environment: Environment = "draft",
                 limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)):
    return await execute(request, project_id, "legacy_bindings", environment=environment, limit=limit, offset=offset)


@router.post("/legacy-bindings/{alias_id}/convert")
async def convert(request: Request, project_id: UUID, alias_id: UUID, body: ConvertLegacy):
    return await execute(request, project_id, "convert", alias_id=alias_id, **body.model_dump())


@router.get("/keys")
async def list_keys(request: Request, project_id: UUID, environment: Environment = "draft",
                    limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
                    search: str = Query("", max_length=128), kind: Literal["value", "secret"] | None = None,
                    status: Literal["all", "configured", "missing", "legacy", "attention"] | None = None):
    return await execute(request, project_id, "list_keys", environment=environment,
        limit=limit, offset=offset, search=search, kind=kind, status=status)


@router.get("/readiness/{target_kind}/{target_id}")
async def readiness(request: Request, project_id: UUID, target_kind: Literal["agent", "network", "provider_credential", "tool"],
                    target_id: UUID, environment: Environment = "draft", version_id: UUID | None = None):
    return await execute(request, project_id, "readiness", target_kind=target_kind, target_id=target_id,
                         environment=environment, version_id=version_id)


@router.post("/keys")
async def declare(request: Request, project_id: UUID, body: DeclareKey):
    return await execute(request, project_id, "declare", **body.model_dump())


@router.patch("/keys/{key_id}")
async def patch(request: Request, project_id: UUID, key_id: UUID, body: PatchKey):
    changes = body.model_dump(exclude_unset=True)
    return await execute(request, project_id, "patch", key_id=key_id,
        expected_revision=changes.pop("expected_revision"), changes=changes)


@router.delete("/keys/{key_id}")
async def remove(request: Request, project_id: UUID, key_id: UUID, expected_revision: int = Query(ge=1)):
    return await execute(request, project_id, "remove_key", key_id=key_id, expected_revision=expected_revision)


@router.put("/keys/{key_id}/values/{environment}")
async def write(request: Request, project_id: UUID, key_id: UUID, environment: Environment, body: WriteValue):
    return await execute(request, project_id, "write_value", key_id=key_id, environment=environment, **body.model_dump())


@router.delete("/keys/{key_id}/values/{environment}")
async def clear(request: Request, project_id: UUID, key_id: UUID, environment: Environment, expected_revision: int = Query(ge=0)):
    return await execute(request, project_id, "write_value", key_id=key_id, environment=environment,
        expected_revision=expected_revision, clear=True)


@router.post("/value-batches")
async def batch(request: Request, project_id: UUID, body: WriteBatch):
    return await execute(request, project_id, "write_batch", **body.model_dump())


@router.get("/keys/{key_id}/usage")
async def usage(request: Request, project_id: UUID, key_id: UUID,
                limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)):
    return await execute(request, project_id, "usage", key_id=key_id, limit=limit, offset=offset)


@router.post("/use-policies")
async def grant(request: Request, project_id: UUID, body: GrantUse):
    return await execute(request, project_id, "grant_use", **body.model_dump())


@router.get("/keys/{key_id}/use-policies")
async def policies(request: Request, project_id: UUID, key_id: UUID,
                   limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)):
    return await execute(request, project_id, "list_use_policies", key_id=key_id, limit=limit, offset=offset)


@router.delete("/use-policies/{policy_id}")
async def revoke(request: Request, project_id: UUID, policy_id: UUID, expected_revision: int = Query(ge=1)):
    return await execute(request, project_id, "revoke_use", policy_id=policy_id, expected_revision=expected_revision)


class BindConfiguration(StrictBody):
    expected_revision: StrictStr = Field(min_length=1, max_length=128)
    authentication: dict
    route_id: str | None = Field(default=None, min_length=1, max_length=128)


@router.get("/bindings/{target_kind}/{target_id}")
async def binding(request: Request, project_id: UUID, target_kind: Literal["provider_credential", "tool"], target_id: UUID,
                  route_id: str | None = Query(default=None, min_length=1, max_length=128)):
    return await execute(request, project_id, "binding", target_kind=target_kind, target_id=target_id, route_id=route_id)


@router.put("/bindings/{target_kind}/{target_id}")
async def bind(request: Request, project_id: UUID, target_kind: Literal["provider_credential", "tool"], target_id: UUID, body: BindConfiguration):
    return await execute(request, project_id, "bind", target_kind=target_kind, target_id=target_id, **body.model_dump())


class TestConfiguration(StrictBody):
    environment: Environment = "draft"


@router.post("/tests/{target_kind}/{target_id}")
async def test_configuration(request: Request, project_id: UUID, target_kind: Literal["provider_credential", "tool"], target_id: UUID, body: TestConfiguration):
    from modules.agent.entrypoint import build_configuration_tool_preparation, list_available_provider_models_composer
    from shared.presentation.contracts import OperationRequest
    operation = OperationRequest(principal=request.state.principal, path_params={"project_id": project_id, "target_id": target_id, "credential_id": target_id},
        query_params={"project_id": project_id, "environment": body.environment}, body=body.model_dump())
    handler = build_configuration_tool_preparation() if target_kind == "tool" else list_available_provider_models_composer()
    result = await handler(operation)
    if target_kind == "provider_credential":
        return {"success": True, "message": "ok", "data": {"target_kind": target_kind, "target_id": str(target_id), "environment": body.environment,
            "state": "valid", "models_found": len(result.body["data"])}}
    return result.body
