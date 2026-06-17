# Detection evidence — Spec 000

## Command 1: Branch check

```powershell
test "$(git branch --show-current)" = "development_event-driven-module-communication"
```
Exit code: 0

Note: Spec header says `development_module-communication-hardening` (typo). Adapted to actual branch `development_event-driven-module-communication` per runtime.md/MANIFEST.json/README.md.

## Command 2: git status

```powershell
git status --short
```
Exit code: 0
Result: clean

## Command 3: Pattern scan

```powershell
Get-ChildItem -Recurse -Filter "*.py" -Path src, tests | Select-String -Pattern "MeteringUsageRecorder|ObservabilityTraceRecorder|_legacy_mode|agent\.#|outbox\.write\(|_do_save_assistant_message"
```
Exit code: 0

Key findings:

| Pattern | File | Line | Notes |
|---|---|---|---|
| MeteringUsageRecorder | src/modules/agent/infra/adapters/metering_usage_recorder.py | 12 | Adapter still exists |
| ObservabilityTraceRecorder | src/modules/agent/infra/adapters/observability_trace_recorder.py | 13 | Adapter still exists |
| MeteringUsageRecorder | src/modules/agent/infra/workers/ask_job_worker.py | 17 | Import and use in worker |
| ObservabilityTraceRecorder | src/modules/agent/infra/workers/ask_job_worker.py | 18 | Import and use in worker |
| agent.# | src/modules/agent/infra/workers/inbox_consumer.py | 19 | Self-subscription still active |
| _legacy_mode | src/modules/agent/application/use_cases/ask_use_case.py | 106, 111 | Legacy mode flag |
| _do_save_assistant_message | src/modules/agent/application/use_cases/ask_use_case.py | 315, 580, 834 | Legacy direct write |
| outbox.write( | src/modules/agent/application/use_cases/ask_use_case.py | 458, 614, 621, 661, 867 | Missing await |
| outbox.write( | src/modules/agent/application/use_cases/ask_agent_stream_service.py | 121, 408, 453, 460 | Missing await |

## Command 4: Event type scan

```powershell
Get-ChildItem -Recurse -Filter "*.py" -Path src, tests | Select-String -Pattern "agent\.execution\.(started|llm_completed|tool_completed)\.v1|event_type=.*\.created"
```
Exit code: 0

Key findings:

| Event type | Source | Versioned |
|---|---|---|
| agent.execution.started.v1 | metering/observability consumers/handlers | Yes |
| agent.execution.llm_completed.v1 | metering/observability consumers/handlers | Yes |
| agent.execution.tool_completed.v1 | metering/observability consumers/handlers | Yes |
| plan.created | billing use_cases | No |
| customer.created | billing use_cases | No |
| subscription.created | billing use_cases | No |
| project.created | core use_cases | No |
| api_key.created | core use_cases | No |
| user.created | identity use_cases | No |
| organization.created | identity use_cases | No |
| trace.created | observability use_cases | No |
| trace_event.created | observability use_cases | No |
