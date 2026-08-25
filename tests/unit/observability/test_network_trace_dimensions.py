from uuid import uuid4

from modules.observability.domain.entities import Trace
from modules.observability.infra.database.mappers import trace_entity_to_model
from modules.observability.infra.messaging.trace_projector import _DATA_FIELDS


def test_trace_projector_preserves_network_dimension_fields() -> None:
    assert {
        "network_id",
        "network_execution_id",
        "network_session_id",
        "network_version_id",
    }.issubset(_DATA_FIELDS)


def test_trace_mapper_derives_network_dimensions_from_projected_data() -> None:
    project_id = uuid4()
    network_id = uuid4()
    execution_id = uuid4()
    session_id = uuid4()
    version_id = uuid4()

    model = trace_entity_to_model(
        Trace(
            project_id=project_id,
            data={
                "network_id": str(network_id),
                "network_execution_id": str(execution_id),
                "network_session_id": str(session_id),
                "network_version_id": str(version_id),
            },
        )
    )

    assert model.network_id == network_id
    assert model.network_execution_id == execution_id
    assert model.network_session_id == session_id
    assert model.network_version_id == version_id
