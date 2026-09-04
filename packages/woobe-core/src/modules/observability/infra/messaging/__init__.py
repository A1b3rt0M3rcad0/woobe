from modules.observability.infra.messaging.trace_projector import _DATA_FIELDS


_DATA_FIELDS.update(
    {
        "network_id",
        "network_execution_id",
        "network_session_id",
        "network_version_id",
    }
)
