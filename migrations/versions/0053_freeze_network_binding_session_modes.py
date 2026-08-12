"""freeze Agent Session Mode in Network Version bindings

Revision ID: 0053
Revises: 0052
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from uuid import UUID

import sqlalchemy as sa
from alembic import op

revision = "0053"
down_revision = "0052"
branch_labels = None
depends_on = None

_VALID_SESSION_MODES = {"stateful", "stateless"}


def _composition_hash(definition: dict, bindings: dict) -> str:
    payload = {
        "definition": definition,
        "resolved_bindings": bindings,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _uuid(value: object, *, label: str, version_id: object, node_id: str) -> UUID:
    try:
        return UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise RuntimeError(
            f"Network Version {version_id} node {node_id} has no valid {label}"
        ) from exc


def upgrade() -> None:
    connection = op.get_bind()
    versions = list(
        connection.execute(
            sa.text(
                """
                SELECT id, project_id, definition, resolved_bindings
                FROM network.network_versions
                WHERE resolved_bindings IS NOT NULL
                ORDER BY created_at ASC
                """
            )
        ).mappings()
    )

    for version in versions:
        bindings = deepcopy(version["resolved_bindings"] or {})
        if not isinstance(bindings, dict):
            raise RuntimeError(
                f"Network Version {version['id']} has invalid resolved_bindings"
            )

        changed = False
        for node_id, binding in bindings.items():
            if not isinstance(binding, dict):
                raise RuntimeError(
                    f"Network Version {version['id']} node {node_id} has an invalid binding"
                )

            release_id = _uuid(
                binding.get("release_id"),
                label="release_id",
                version_id=version["id"],
                node_id=node_id,
            )
            agent_id = _uuid(
                binding.get("agent_id"),
                label="agent_id",
                version_id=version["id"],
                node_id=node_id,
            )
            release = connection.execute(
                sa.text(
                    """
                    SELECT project_id, agent_id, session_mode
                    FROM agent.agent_releases
                    WHERE id = :release_id
                    """
                ),
                {"release_id": release_id},
            ).mappings().one_or_none()
            if release is None:
                raise RuntimeError(
                    f"Network Version {version['id']} node {node_id} references a missing Agent Release"
                )
            if release["project_id"] != version["project_id"]:
                raise RuntimeError(
                    f"Network Version {version['id']} node {node_id} references an Agent Release from another Project"
                )
            if release["agent_id"] != agent_id:
                raise RuntimeError(
                    f"Network Version {version['id']} node {node_id} references an Agent Release from another Agent"
                )

            release_mode = str(release["session_mode"] or "")
            if release_mode not in _VALID_SESSION_MODES:
                raise RuntimeError(
                    f"Network Version {version['id']} node {node_id} references an Agent Release without a valid Session Mode"
                )

            binding_mode = binding.get("session_mode")
            if binding_mode is None:
                binding["session_mode"] = release_mode
                changed = True
            elif str(binding_mode) not in _VALID_SESSION_MODES:
                raise RuntimeError(
                    f"Network Version {version['id']} node {node_id} has an invalid frozen Session Mode"
                )

        if not changed:
            continue

        connection.execute(
            sa.text(
                """
                UPDATE network.network_versions
                SET resolved_bindings = CAST(:bindings AS jsonb),
                    composition_hash = :composition_hash
                WHERE id = :version_id
                """
            ),
            {
                "bindings": json.dumps(bindings),
                "composition_hash": _composition_hash(
                    version["definition"],
                    bindings,
                ),
                "version_id": version["id"],
            },
        )


def downgrade() -> None:
    connection = op.get_bind()
    versions = list(
        connection.execute(
            sa.text(
                """
                SELECT id, definition, resolved_bindings
                FROM network.network_versions
                WHERE resolved_bindings IS NOT NULL
                ORDER BY created_at ASC
                """
            )
        ).mappings()
    )

    for version in versions:
        bindings = deepcopy(version["resolved_bindings"] or {})
        changed = False
        if not isinstance(bindings, dict):
            continue
        for binding in bindings.values():
            if isinstance(binding, dict) and "session_mode" in binding:
                binding.pop("session_mode", None)
                changed = True
        if not changed:
            continue
        connection.execute(
            sa.text(
                """
                UPDATE network.network_versions
                SET resolved_bindings = CAST(:bindings AS jsonb),
                    composition_hash = :composition_hash
                WHERE id = :version_id
                """
            ),
            {
                "bindings": json.dumps(bindings),
                "composition_hash": _composition_hash(
                    version["definition"],
                    bindings,
                ),
                "version_id": version["id"],
            },
        )
