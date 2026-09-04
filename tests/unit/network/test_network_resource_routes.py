from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from woobe_api.http.network.resource_routes import (
    CreateNetworkRequest,
    UpdateNetworkMetadataRequest,
    network_payload,
)


def test_create_network_request_normalizes_metadata() -> None:
    request = CreateNetworkRequest(
        name="  Customer Support  ",
        description="  Handles customer requests.  ",
    )

    assert request.name == "Customer Support"
    assert request.description == "Handles customer requests."


def test_create_network_request_rejects_blank_name() -> None:
    with pytest.raises(ValidationError, match="cannot be blank"):
        CreateNetworkRequest(name="   ")


def test_update_network_metadata_requires_at_least_one_field() -> None:
    with pytest.raises(ValidationError, match="At least one"):
        UpdateNetworkMetadataRequest()


def test_network_payload_exposes_inventory_agent_count() -> None:
    now = datetime.now(UTC)
    project_id = uuid4()
    network_id = uuid4()
    network = SimpleNamespace(
        id=network_id,
        project_id=project_id,
        name="Support",
        description="Support Network",
        draft_definition={
            "nodes": [
                {"id": "entry", "agent_id": str(uuid4())},
                {"id": "specialist", "agent_id": str(uuid4())},
            ]
        },
        draft_revision=3,
        staging_version_id=None,
        production_version_id=None,
        created_at=now,
        updated_at=now,
    )

    payload = network_payload(network)

    assert payload["id"] == str(network_id)
    assert payload["project_id"] == str(project_id)
    assert payload["agent_count"] == 2
    assert payload["draft_revision"] == 3

