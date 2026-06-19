# Runtime boundary cleanup

This specification tracks the removal of the remaining architecture exceptions around runtime execution.

## Current exceptions

- `ask_use_case.py` owns the concrete `AgentUnitOfWork` transaction boundary and receives an async SQLAlchemy session factory.
- `ask_agent_stream_service.py` assembles SSE cancellation, tool execution and persistence adapters.
- `instrumented_execution_finalizer.py` persists the assistant message and transactional Outbox events atomically.
- `shared/workers/discovery.py` resolves module worker registries through dynamic plugin discovery rather than static module imports.

## Removal criteria

The exceptions can be removed only when all of the following are true:

1. Runtime use cases depend exclusively on application/domain ports.
2. UnitOfWork, repository and provider construction moves to a dedicated composition root without moving domain logic into composers.
3. Streaming cancellation and transactional finalization retain the same integration-test coverage.
4. Worker discovery uses a registry or entry-point mechanism that does not require module-name literals in shared code.
5. The architecture suites pass with the corresponding allowlist entries deleted.

These entries are architecture exceptions, not accepted test failures. The backend gate must execute plain `pytest` and require zero failures.
