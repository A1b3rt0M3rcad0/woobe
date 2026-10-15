"""Explicit reconciliation of prepared remote evidence with installed definitions.

Provider I/O belongs to the discovery handler before this short transaction.
Apply is atomic and creates/reuses definitions; adoption remains an explicit Draft edit.
"""

from copy import deepcopy
from dataclasses import replace

from modules.agent.application.dtos.ai_dtos import CreateProviderModelInput
from modules.agent.application.use_cases.ai_provider_model_cases import (
    CreateProviderModelUseCase,
)
from modules.agent.domain.model_spec import (
    ModelSpec,
    effective_model_semantic_fingerprint,
    model_spec_hash,
)
from modules.agent.domain.provider_identity import canonical_provider_key
from shared.contracts.errors import ValidationError
from modules.agent.application.dtos.provider_model_reconciliation_dtos import (
    ReconciliationScope,
    ReconciliationSelection,
    ApplyProviderModelReconciliationInput,
)
from modules.agent.domain.catalog_reconciliation import (
    catalog_digest as _digest,
    reconciliation_conflict as _conflict,
)


def model_revision(item):
    return _digest(
        {
            "id": item.id,
            "name": item.name,
            "model": item.model,
            "credential": item.provider_credential_id,
            "spec": item.spec,
            "metadata": {
                key: value
                for key, value in (item.metadata or {}).items()
                if key != "catalog_observation"
            },
            "status": str(item.status),
            "updated_at": item.updated_at,
        }
    )


def _candidate(scope, credential, remote, installed=None, configuration_revision=None):
    raw_spec = remote.model_spec or remote.raw.get("woobe_model_spec")
    revision = model_revision(installed) if installed else None
    common = {
        "model_id": remote.id,
        "label": remote.label,
        "installed_spec": installed.spec if installed else None,
        "installed_model_id": str(installed.id) if installed else None,
        "expected_model_revision": revision,
        "expected_credential_revision": credential.binding_revision,
        "normalization_issues": remote.normalization_issues,
    }
    digest = _digest(
        {
            "scope": scope.model_dump(),
            "credential_revision": credential.binding_revision,
            "model_revision": revision,
            "catalog": remote.model_dump(),
            "configuration_revision": configuration_revision,
        }
    )
    common["candidate_digest"] = digest
    expected_operation = {
        "generation": "language.generate",
        "embedding": "embedding.create",
    }.get(scope.capability)
    if (
        raw_spec is None
        or remote.normalization_status == "unsupported_execution"
        or (
            expected_operation
            and expected_operation not in (raw_spec.get("operations") or [])
        )
    ):
        return {
            **common,
            "state": "unsupported/unclassified",
            "change_kind": "unsupported/unclassified",
            "proposed_spec": None,
        }, None
    metadata = deepcopy(installed.metadata or {}) if installed else {}
    # The explicit normalized override set is authoritative. Old catalog fields are
    # evidence, not fresh overrides that can mask new provider values.
    if (
        "model_spec_overrides" in metadata
        or metadata.get("capability_source") == "provider_catalog"
    ):
        for key in ("capabilities", "pricing", "context_window", "max_output_tokens"):
            metadata.pop(key, None)
    metadata.update(
        model_spec_baseline=raw_spec, provider_model_raw=deepcopy(remote.raw)
    )
    metadata.pop("model_spec", None)
    definition = CreateProviderModelUseCase.prepare_definition(
        CreateProviderModelInput(
            project_id=scope.project_id,
            provider_credential_id=credential.id,
            name=installed.name if installed else remote.label,
            model=remote.id,
            model_type=raw_spec["model_type"],
            spec=raw_spec,
            metadata=metadata,
        ),
        credential,
    )
    proposed = ModelSpec.from_dict(definition.spec)
    kind = "new"
    if installed:
        if installed.spec is None:
            kind = "semantic_changed"
        else:
            current = ModelSpec.from_dict(installed.spec)
            if effective_model_semantic_fingerprint(
                current
            ) == effective_model_semantic_fingerprint(proposed):
                if model_spec_hash(current) == model_spec_hash(proposed):
                    kind = "unchanged"
                elif (
                    replace(current, display_name=proposed.display_name).as_dict()
                    == proposed.as_dict()
                ):
                    kind = "display_only_changed"
                else:
                    kind = "provenance_only_changed"
            elif effective_model_semantic_fingerprint(
                replace(current, pricing=proposed.pricing)
            ) == effective_model_semantic_fingerprint(proposed):
                kind = "pricing_changed"
            else:
                kind = "semantic_changed"
    manual = bool(metadata.get("model_spec_overrides"))
    definition.metadata["catalog_observation"] = {
        "candidate_digest": digest,
        "model_spec": deepcopy(raw_spec),
        "source": remote.source,
        "normalization_status": remote.normalization_status,
    }
    return {
        **common,
        "state": "manually_overridden" if manual else kind,
        "change_kind": kind,
        "proposed_spec": definition.spec,
        "semantic_fingerprint": effective_model_semantic_fingerprint(proposed),
    }, definition


class PreviewProviderModelReconciliationUseCase:
    def __init__(self, models):
        self.models = models

    async def execute(
        self, scope, credential, remote_models, configuration_revision=None
    ):
        local = [
            item
            for item in await self.models.list_by_credential(credential.id)
            if item.project_id == scope.project_id
        ]
        expected_operation = {
            "generation": "language.generate",
            "embedding": "embedding.create",
        }.get(scope.capability)
        if expected_operation:
            from modules.agent.application.interfaces.model_spec_compatibility import (
                LegacyModelSpecResolver,
            )

            local = [
                item
                for item in local
                if expected_operation
                in (
                    ModelSpec.from_dict(item.spec)
                    if item.spec
                    else LegacyModelSpecResolver().resolve(
                        item, provider=str(credential.provider)
                    )
                ).operations
            ]
            if scope.capability == "generation":
                # Comparison retains diagnostic evidence excluded by the picker.
                remote_models = [
                    item
                    for item in remote_models
                    if "embedding.create" not in item.operations
                ]
        result = []
        remote_ids = set()
        for remote in remote_models:
            remote_ids.add(remote.id)
            matches = [
                item
                for item in local
                if item.model == remote.id and str(item.status) != "archived"
            ]
            for installed in matches or [None]:
                result.append(
                    _candidate(
                        scope, credential, remote, installed, configuration_revision
                    )[0]
                )
        for item in local:
            if item.model not in remote_ids:
                result.append(
                    {
                        "model_id": item.model,
                        "label": item.name,
                        "installed_model_id": str(item.id),
                        "state": "not_discovered",
                        "change_kind": "not_discovered",
                        "proposed_spec": None,
                    }
                )
        return {
            "provider": canonical_provider_key(credential.provider),
            "environment": scope.environment,
            "expected_credential_revision": credential.binding_revision,
            "expected_configuration_revision": configuration_revision,
            "items": result,
        }


class ApplyProviderModelReconciliationUseCase:
    def __init__(self, models, credentials):
        self.models, self.credentials = models, credentials

    async def execute(
        self,
        dto,
        remote_models,
        discovery_credential_revision,
        configuration_revision=None,
    ):
        if dto.expected_configuration_revision != configuration_revision:
            _conflict(
                "CONFIGURATION_REVISION_CONFLICT",
                "Environment configuration changed; compare again",
            )
        credential = await self.credentials.lock_by_id(dto.provider_credential_id)
        if (
            credential is None
            or credential.project_id != dto.project_id
            or str(credential.status) != "active"
            or credential.binding_revision != dto.expected_credential_revision
            or credential.binding_revision != discovery_credential_revision
        ):
            _conflict(
                "CREDENTIAL_REVISION_CONFLICT",
                "Credential changed or was revoked; compare again",
            )
        remote_by_id = {item.id: item for item in remote_models}
        prepared = []
        seen = set()
        for selection in dto.selections:
            key = (selection.model_id, selection.installed_model_id)
            if key in seen:
                raise ValidationError("Duplicate reconciliation selection")
            seen.add(key)
            remote = remote_by_id.get(selection.model_id)
            if remote is None:
                _conflict(
                    "CATALOG_CANDIDATE_CHANGED",
                    "Model was not discovered; compare again",
                )
            installed = (
                await self.models.lock_by_id(selection.installed_model_id)
                if selection.installed_model_id
                else None
            )
            if selection.installed_model_id and (
                installed is None
                or installed.project_id != dto.project_id
                or installed.provider_credential_id != credential.id
                or installed.model != selection.model_id
            ):
                _conflict(
                    "MODEL_REVISION_CONFLICT",
                    "Installed Model binding changed; compare again",
                )
            if selection.expected_model_revision != (
                model_revision(installed) if installed else None
            ):
                _conflict(
                    "MODEL_REVISION_CONFLICT", "Installed Model changed; compare again"
                )
            scope = ReconciliationScope(
                **dto.model_dump(include=set(ReconciliationScope.model_fields))
            )
            candidate, definition = _candidate(
                scope, credential, remote, installed, configuration_revision
            )
            if selection.candidate_digest != candidate["candidate_digest"]:
                _conflict(
                    "CATALOG_CANDIDATE_CHANGED",
                    "Catalog evidence changed; compare again",
                )
            if definition is None:
                raise ValidationError(
                    "Select only normalized executable model definitions"
                )
            prepared.append((candidate, definition))
        # All preconditions are checked before any write. The credential row lock
        # serializes simultaneous applies; the existing unique constraint is retained.
        existing = await self.models.list_by_credential(credential.id)
        for candidate, definition in prepared:
            if any(
                item.spec_hash == definition.spec_hash and str(item.status) != "active"
                for item in existing
            ):
                _conflict(
                    "MODEL_DEFINITION_UNAVAILABLE",
                    "An identical definition is inactive; reactivate it explicitly before reuse",
                )
        results = []
        for candidate, definition in prepared:
            fingerprint = candidate["semantic_fingerprint"]
            reused = next(
                (
                    item
                    for item in existing
                    if item.spec
                    and str(item.status) == "active"
                    and item.model == definition.model
                    and effective_model_semantic_fingerprint(
                        ModelSpec.from_dict(item.spec)
                    )
                    == fingerprint
                ),
                None,
            )
            if reused:
                reused = await self.models.lock_by_id(reused.id)
                if (
                    reused is None
                    or str(reused.status) != "active"
                    or not reused.spec
                    or reused.project_id != dto.project_id
                    or reused.provider_credential_id != credential.id
                    or effective_model_semantic_fingerprint(
                        ModelSpec.from_dict(reused.spec)
                    )
                    != fingerprint
                ):
                    _conflict(
                        "MODEL_REVISION_CONFLICT",
                        "Reusable definition changed; compare again",
                    )
                observation = definition.metadata["catalog_observation"]
                evidence_updated = (reused.metadata or {}).get(
                    "catalog_observation"
                ) != observation
                if evidence_updated:
                    await self.models.record_catalog_observation(reused.id, observation)
                results.append(
                    {
                        "model_id": candidate["model_id"],
                        "result": "reused",
                        "provider_model_id": str(reused.id),
                        "evidence_updated": evidence_updated,
                    }
                )
                continue
            saved = await self.models.save(definition)
            existing.append(saved)
            results.append(
                {
                    "model_id": candidate["model_id"],
                    "result": "created",
                    "provider_model_id": str(saved.id),
                }
            )
        return {
            "items": results,
            "adoption": "Select the resulting Model explicitly on the Agent Draft",
        }
