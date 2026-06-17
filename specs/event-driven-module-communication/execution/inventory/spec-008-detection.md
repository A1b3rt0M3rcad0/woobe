# Spec 008 — Detection Evidence

**Date:** 2026-06-16
**Scope:** event-driven-module-communication

| # | Command | Exit code | Result |
|---|---|---|---|
| 1 | `git branch --show-current` | 0 | `development_event-driven-module-communication` |
| 2 | `git merge-base --is-ancestor cd8d5867967fea25ea170bd88ebc9a461ed16c09 HEAD` | 0 | ancestor verified |
| 3 | `git status --short` | 0 | clean |
| 4 | Read `ask_use_case.py` | 0 | 888 lines; contains UsageRecorder + TraceRecorder in ctor + 20+ call sites |
| 5 | Read `ask_agent_composer.py` | 0 | 63 lines; imports MeteringUsageRecorder, ObservabilityTraceRecorder; wraps TransactionalHandler |
| 6 | Read `transactional_handler.py` | 0 | 15 lines; opens UoW for entire request duration |

## Key observations

- `AskAgentUseCase.__init__` receives `trace_recorder: TraceRecorder` and `usage_recorder: UsageRecorder`
- `execute()` calls `trace_recorder.create_trace()`, `trace_recorder.record_event()` (3 sites), `trace_recorder.complete_trace()`, `trace_recorder.fail_trace()`, `usage_recorder.record_llm_request()`
- TransactionalHandler wraps the entire HTTP handler in a single UoW
- AgentExecutionRequestedV1, AgentExecutionCompletedV1, AgentExecutionFailedV1 events already exist with proper payloads
- AgentExecutionRequestedV1 already has `create()` factory method
- UsageRecorder writes to `modules.metering` via dynamic import
- TraceRecorder writes to `modules.observability` via dynamic import
