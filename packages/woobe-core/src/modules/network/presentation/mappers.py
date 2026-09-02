from modules.network.application.dtos.observation import NetworkRunObservation


def public_network_failure_message(code: str | None) -> str | None:
    messages = {
        "credential_error": "The Agent provider credential is not ready.",
        "model_binding_error": "The Agent provider model binding is not ready.",
        "runtime_configuration_error": "The Agent runtime configuration is not ready.",
        "agent_context_error": "The Agent session continuity could not be restored.",
        "provider_rate_limited": "The model provider rate-limited this request.",
        "provider_timeout": "The model provider did not answer before the timeout.",
        "empty_model_output": "The Agent completed without producing a public result.",
        "network_timeout_exceeded": "The Network execution exceeded its time budget.",
        "network_max_depth_exceeded": "The Network execution exceeded its maximum depth.",
        "network_max_invocations_exceeded": "The Network execution exceeded its invocation budget.",
        "network_budget_exceeded": "The Network runtime budget was exceeded.",
        "budget_exceeded": "The Network runtime budget was exceeded.",
        "worker_lease_expired": "The Network worker stopped before completion.",
    }
    if code is None:
        return None
    return messages.get(code, "Network execution failed.")


def public_network_run_payload(run: NetworkRunObservation) -> dict:
    return {
        "execution_id": str(run.id),
        "job_id": str(run.id),
        "session_id": str(run.network_session_id),
        "network_id": str(run.network_id),
        "network_version_id": (
            str(run.network_version_id) if run.network_version_id else None
        ),
        "status": run.status,
        "answer": run.output_message,
        "result": (
            run.parsed_output
            if run.parsed_output is not None
            else run.output_message
        ),
        "parsed_output": run.parsed_output,
        "output_parse_error": run.output_parse_error,
        "error": public_network_failure_message(run.failure_code),
        "trace_id": str(run.root_trace_id) if run.root_trace_id else None,
        "created_at": run.created_at,
        "started_at": run.started_at,
        "completed_at": run.completed_at,
    }
