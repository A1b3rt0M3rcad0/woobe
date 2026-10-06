from __future__ import annotations

from datetime import UTC, datetime, timedelta
from hashlib import sha256
import hmac
import json
import re
from uuid import UUID, uuid4

from sqlalchemy import or_, select, text

from modules.package.domain.errors import PackageError
from modules.package.domain.operations import (
    TERMINAL_STATES,
    transition,
)
from modules.package.infra.models import (
    PackageOperationModel,
    PackagePlanModel,
    PackageUploadModel,
)
from modules.package.infra.receipts import authorize_phase
from shared.infra.admin_idempotency import principal_identity
from shared.infra.crypto import decrypt_secret, encrypt_secret
from shared.security.principal import AuthenticatedPrincipal, ControlPlanePrincipal


def canonical_bytes(value):
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def as_utc(value):
    return value.replace(tzinfo=value.tzinfo or UTC)


def encode_principal(principal, encryption_key):
    if isinstance(principal, AuthenticatedPrincipal):
        kind = "human"
    elif isinstance(principal, ControlPlanePrincipal):
        kind = "control"
    else:
        raise PackageError(
            "PACKAGE_AUTHORITY_REQUIRED", "Administrative authentication is required"
        )
    return encrypt_secret(
        json.dumps({"kind": kind, "claims": principal.model_dump(mode="json")}),
        encryption_key,
    )


def decode_principal(ciphertext, encryption_key):
    document = json.loads(decrypt_secret(ciphertext, encryption_key))
    model = {"human": AuthenticatedPrincipal, "control": ControlPlanePrincipal}[
        document["kind"]
    ]
    return model.model_validate(document["claims"])


class PackageOperationRepository:
    def __init__(
        self, session_factory, *, encryption_key: str, plan_validator, lease_seconds=120
    ):
        self.session_factory, self.encryption_key = session_factory, encryption_key
        self.lease_seconds = lease_seconds
        self.plan_validator = plan_validator

    def protected_fingerprint(self, project_id, payload):
        material = (
            b"woobe-package-operation@1.0\n"
            + str(project_id).encode()
            + b"\n"
            + canonical_bytes(payload)
        )
        return hmac.digest(self.encryption_key.encode(), material, "sha256")

    @staticmethod
    def key_digest(key):
        if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", key):
            raise PackageError(
                "PACKAGE_IDEMPOTENCY_REQUIRED", "A bounded idempotency key is required"
            )
        return sha256(key.encode()).digest()

    async def _authorize(self, session, principal, operation, *, write=False):
        if operation is None or operation.actor != principal_identity(principal):
            raise PackageError(
                "PACKAGE_OPERATION_NOT_FOUND", "Operation is unavailable"
            )
        plan = await session.get(PackagePlanModel, operation.plan_id)
        if plan is None:
            raise PackageError(
                "PACKAGE_PLAN_NOT_FOUND", "Operation plan is unavailable"
            )
        permissions = (
            plan.document["required_permissions"] if write else ["project:read"]
        )
        for permission in sorted(set(permissions)):
            await authorize_phase(session, principal, operation.project_id, permission)

    async def accept(self, *, project_id: UUID, principal, key: str, payload: dict):
        """Accept and pin the protected request atomically; never silently replan."""
        identity, key_digest = principal_identity(principal), self.key_digest(key)
        fingerprint = self.protected_fingerprint(project_id, payload)
        encoded = canonical_bytes(payload).decode()
        if len(encoded.encode()) > 2 << 20:
            raise PackageError("PACKAGE_LIMIT_EXCEEDED", "Apply request exceeds 2 MiB")
        async with self.session_factory.begin() as session:
            if session.bind.dialect.name == "postgresql":
                material = canonical_bytes(
                    [str(project_id), identity, key_digest.hex()]
                )
                lock = int.from_bytes(sha256(material).digest()[:8], "big", signed=True)
                await session.execute(
                    text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock}
                )
            existing = (
                await session.execute(
                    select(PackageOperationModel)
                    .where(
                        PackageOperationModel.project_id == project_id,
                        PackageOperationModel.actor == identity,
                        PackageOperationModel.key_digest == key_digest,
                    )
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if existing is not None:
                await self._authorize(session, principal, existing, write=True)
                if not hmac.compare_digest(existing.payload_fingerprint, fingerprint):
                    raise PackageError(
                        "PACKAGE_IDEMPOTENCY_CONFLICT",
                        "Idempotency key is bound to a different request",
                    )
                return existing, True
            plan = await session.get(PackagePlanModel, UUID(payload["plan_id"]))
            if plan is None or plan.project_id != project_id or plan.actor != identity:
                raise PackageError("PACKAGE_PLAN_NOT_FOUND", "Plan is unavailable")
            for permission in sorted(set(plan.document["required_permissions"])):
                await authorize_phase(session, principal, project_id, permission)
            if as_utc(plan.expires_at) <= datetime.now(UTC):
                raise PackageError("PACKAGE_PLAN_EXPIRED", "Approved plan has expired")
            pins = {
                "plan_digest": plan.plan_digest,
                "upload_id": str(plan.upload_id),
                "artifact_digest": plan.artifact_digest,
                "lifecycle": plan.document["lifecycle"],
            }
            if any(payload.get(field) != value for field, value in pins.items()):
                raise PackageError(
                    "PACKAGE_PLAN_MISMATCH",
                    "Apply request differs from the approved plan",
                )
            upload = await session.get(PackageUploadModel, plan.upload_id)
            if upload is None or as_utc(upload.expires_at) <= datetime.now(UTC):
                raise PackageError(
                    "PACKAGE_UPLOAD_EXPIRED", "Uploaded package has expired"
                )
            # Owner revisions, capability identities and bindings are rechecked
            # in the acceptance transaction against the pinned plan.
            await self.plan_validator(session, plan, payload)
            record = PackageOperationModel(
                project_id=project_id,
                actor=identity,
                key_digest=key_digest,
                payload_fingerprint=fingerprint,
                payload_ciphertext=encrypt_secret(encoded, self.encryption_key),
                principal_ciphertext=encode_principal(principal, self.encryption_key),
                artifact_digest=plan.artifact_digest,
                upload_id=plan.upload_id,
                plan_id=plan.id,
                lifecycle=payload["lifecycle"],
                phases_total=len(plan.document["effects"]),
                state="accepted",
            )
            session.add(record)
            await session.flush()
            return record, False

    async def get(self, *, project_id, principal, operation_id):
        async with self.session_factory() as session:
            record = await session.get(PackageOperationModel, operation_id)
            if record is None or record.project_id != project_id:
                raise PackageError(
                    "PACKAGE_OPERATION_NOT_FOUND", "Operation is unavailable"
                )
            await self._authorize(session, principal, record)
            return record

    async def lookup(self, *, project_id, principal, key):
        async with self.session_factory() as session:
            record = (
                await session.execute(
                    select(PackageOperationModel).where(
                        PackageOperationModel.project_id == project_id,
                        PackageOperationModel.actor == principal_identity(principal),
                        PackageOperationModel.key_digest == self.key_digest(key),
                    )
                )
            ).scalar_one_or_none()
            await self._authorize(session, principal, record)
            return record

    async def claim(self, *, project_id=None):
        now = datetime.now(UTC)
        async with self.session_factory.begin() as session:
            project_filter = (
                []
                if project_id is None
                else [PackageOperationModel.project_id == project_id]
            )
            record = (
                await session.execute(
                    select(PackageOperationModel)
                    .where(
                        PackageOperationModel.state.in_(
                            [
                                "accepted",
                                "resolving",
                                "materializing",
                                "verifying",
                                "cancelling",
                            ]
                        ),
                        or_(
                            PackageOperationModel.lease_until.is_(None),
                            PackageOperationModel.lease_until <= now,
                        ),
                        *project_filter,
                    )
                    .order_by(PackageOperationModel.created_at)
                    .limit(1)
                    .with_for_update(skip_locked=True)
                )
            ).scalar_one_or_none()
            if record is None:
                return None
            record.lease_token, record.lease_until = (
                uuid4(),
                now + timedelta(seconds=self.lease_seconds),
            )
            if record.state == "accepted":
                record.state = "resolving"
            record.revision += 1
            await session.flush()
            return record

    async def advance(self, operation_id, lease_token, target, **changes):
        permitted = {
            "phase",
            "dependencies",
            "diagnostics",
            "configuration_ready",
            "execution_ready",
            "lifecycle_state",
        }
        if set(changes) - permitted:
            raise ValueError("Unsupported operation update")
        async with self.session_factory.begin() as session:
            record = (
                await session.execute(
                    select(PackageOperationModel)
                    .where(PackageOperationModel.id == operation_id)
                    .with_for_update()
                )
            ).scalar_one()
            if (
                record.lease_token != lease_token
                or record.lease_until is None
                or as_utc(record.lease_until) <= datetime.now(UTC)
            ):
                raise PackageError(
                    "PACKAGE_OPERATION_FENCED",
                    "Operation no longer accepts this worker",
                )
            record.state = transition(record.state, target).value
            for field, value in changes.items():
                setattr(record, field, value)
            if record.state == "succeeded" and (
                not record.configuration_ready
                or record.phases_completed != record.phases_total
            ):
                raise PackageError(
                    "PACKAGE_OPERATION_INCOMPLETE",
                    "Operation has not verified all declared phases",
                )
            record.revision += 1
            if record.state in TERMINAL_STATES or record.state == "waiting_dependency":
                record.lease_token = record.lease_until = None
            else:
                record.lease_until = datetime.now(UTC) + timedelta(
                    seconds=self.lease_seconds
                )
            await session.flush()
            return record

    async def cancel(self, *, project_id, principal, operation_id):
        async with self.session_factory.begin() as session:
            record = (
                await session.execute(
                    select(PackageOperationModel)
                    .where(PackageOperationModel.id == operation_id)
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if record is None or record.project_id != project_id:
                raise PackageError(
                    "PACKAGE_OPERATION_NOT_FOUND", "Operation is unavailable"
                )
            await self._authorize(session, principal, record, write=True)
            if record.state not in TERMINAL_STATES:
                record.state = transition(record.state, "cancelling").value
                record.lease_token = record.lease_until = None
                record.revision += 1
            return record

    async def resume(self, *, project_id, principal, operation_id, expected_revision):
        """Wake an existing dependency wait without changing its approved request."""
        async with self.session_factory.begin() as session:
            record = (
                await session.execute(
                    select(PackageOperationModel)
                    .where(PackageOperationModel.id == operation_id)
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if record is None or record.project_id != project_id:
                raise PackageError(
                    "PACKAGE_OPERATION_NOT_FOUND", "Operation is unavailable"
                )
            await self._authorize(session, principal, record, write=True)
            if record.revision != expected_revision:
                raise PackageError(
                    "PACKAGE_REVISION_CONFLICT",
                    "Operation changed after it was observed",
                )
            if record.state != "waiting_dependency":
                raise PackageError(
                    "PACKAGE_OPERATION_STATE", "Only a dependency wait can be resumed"
                )
            record.state = transition(record.state, "resolving").value
            record.principal_ciphertext = encode_principal(
                principal, self.encryption_key
            )
            record.lease_token = record.lease_until = None
            record.revision += 1
            await session.flush()
            return record
