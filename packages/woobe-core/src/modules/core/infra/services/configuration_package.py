"""Owner boundary for portable declarations, with no value reads or writes."""
from uuid import UUID

from sqlalchemy import select

from modules.core.domain.project_configuration import validate_declaration
from modules.core.infra.database.configuration_store import ConfigurationStore
from modules.core.infra.database.models import ProjectEnvironmentKeyModel
from shared.contracts.project_configuration import ConfigurationError
from shared.presentation.contracts import OperationResult, OperationOutcome


async def inspect_configuration_declarations(session, *, project_id, declarations, bindings):
    names = {value.get("existing_key") or key for key, value in bindings.items()}
    rows = (await session.scalars(select(ProjectEnvironmentKeyModel).where(
        ProjectEnvironmentKeyModel.project_id == project_id, ProjectEnvironmentKeyModel.key.in_(names)))).all()
    existing = {row.key: row for row in rows}
    result = {}
    for name, definition in declarations.items():
        kind = definition.get("kind", "secret")
        validate_declaration(name, kind, definition.get("value_format", "token"), definition.get("validation_rules", {}))
        binding = bindings[name]
        destination = binding.get("existing_key") or name
        row = existing.get(destination)
        if binding.get("create"):
            if row is not None:
                raise ConfigurationError("CONFIG_REVISION_CONFLICT")
            result[name] = {"key": name, "kind": kind, "existing": False}
        else:
            if row is None:
                raise ConfigurationError("CONFIG_REFERENCE_NOT_FOUND")
            if (row.kind != kind or row.value_format != definition.get("value_format", "token")
                    or row.validation_rules != definition.get("validation_rules", {})):
                raise ConfigurationError("CONFIG_KIND_MISMATCH")
            result[name] = {"id": str(row.id), "key": row.key, "kind": row.kind,
                "definition_revision": row.definition_revision, "existing": True}
    return result


class DeclareImportedConfiguration:
    def __init__(self, uow, *, encryption_key):
        self.uow, self.encryption_key = uow, encryption_key

    async def __call__(self, request):
        from shared.infra.admin_idempotency import principal_identity
        definition = dict(request.body)
        project_id = UUID(str(definition.pop("project_id")))
        if set(definition) - {"key", "kind", "description", "value_format", "validation_rules"}:
            raise ConfigurationError("CONFIG_DEFINITION_INVALID")
        store = ConfigurationStore(self.uow.session, encryption_key=self.encryption_key)
        data = await store.declare(project_id=project_id, actor=principal_identity(request.principal), origin="import", **definition)
        return OperationResult(outcome=OperationOutcome.CREATED,
            body={"success": True, "message": "created", "data": data})
