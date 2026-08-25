from __future__ import annotations

from uuid import uuid4

import pytest

from shared.infra.errors import ConflictError
from shared.security.tenancy import TenantAuthorizer


def test_nested_multi_agent_references_are_not_scalar_context_conflicts() -> None:
    project_id = uuid4()
    first_agent_id = uuid4()
    second_agent_id = uuid4()
    body = {
        "project_id": project_id,
        "definition": {
            "nodes": [
                {"agent_id": first_agent_id},
                {"agent_id": second_agent_id},
            ]
        },
    }

    all_identifiers = TenantAuthorizer._identifiers({}, {}, body)
    consistency_identifiers = TenantAuthorizer._consistency_identifiers({}, {}, body)

    assert ("agent_id", first_agent_id) in all_identifiers
    assert ("agent_id", second_agent_id) in all_identifiers
    assert consistency_identifiers == [("project_id", project_id)]
    TenantAuthorizer._require_consistent_identifiers(consistency_identifiers)


def test_top_level_resource_identifier_conflicts_are_still_rejected() -> None:
    first_agent_id = uuid4()
    second_agent_id = uuid4()
    identifiers = TenantAuthorizer._consistency_identifiers(
        {"agent_id": first_agent_id},
        {},
        {"agent_id": second_agent_id},
    )

    with pytest.raises(ConflictError, match="Conflicting agent_id values in request"):
        TenantAuthorizer._require_consistent_identifiers(identifiers)


def test_nested_project_identifiers_remain_visible_to_project_authorization() -> None:
    outer_project_id = uuid4()
    nested_project_id = uuid4()
    body = {
        "project_id": outer_project_id,
        "definition": {
            "metadata": {"project_id": nested_project_id},
        },
    }

    all_identifiers = TenantAuthorizer._identifiers({}, {}, body)
    consistency_identifiers = TenantAuthorizer._consistency_identifiers({}, {}, body)

    assert ("project_id", outer_project_id) in all_identifiers
    assert ("project_id", nested_project_id) in all_identifiers
    assert consistency_identifiers == [("project_id", outer_project_id)]
