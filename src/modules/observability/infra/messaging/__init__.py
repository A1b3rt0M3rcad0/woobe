from modules.observability.infra.messaging import trace_projector as _trace_projector


_trace_projector._DATA_FIELDS.update(
    {
        "network_id",
        "network_execution_id",
        "network_session_id",
        "network_version_id",
    }
)
