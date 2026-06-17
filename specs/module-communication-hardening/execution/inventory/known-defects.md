# Known defects — Module Communication Hardening

Defect matrix mapping each confirmed defect → characterization test → hardening spec.

## Defects

| ID | Defect | Affected files | Severity | Test | Corrective spec |
|---|---|---|---|---|---|
| D001 | Missing `await` on `outbox.write()` calls — fire-and-forget tasks may not complete before transaction commits | `ask_use_case.py` (×5), `ask_agent_stream_service.py` (×4), `runtime_use_cases.py` (×1) | high | `test_characterization_async_boundaries.py` | 001 |
| D002 | `MeteringUsageRecorder`/`ObservabilityTraceRecorder` adapters still exist and are used by `ask_job_worker.py` | `metering_usage_recorder.py`, `observability_trace_recorder.py`, `ask_job_worker.py` | high | `test_characterization_tool_wiring.py` | 002 |
| D003 | `_legacy_mode` flag still active — prevents clean cutover to Outbox-only path | `ask_use_case.py` | medium | `test_characterization_legacy_mode.py` | 001 |
| D004 | `_do_save_assistant_message` legacy direct-write method still exists | `ask_use_case.py` | medium | `test_characterization_legacy_mode.py` | 001 |
| D005 | Billing/core/identity produce unversioned events (`plan.created`, `customer.created`, etc.) | `billing_use_cases.py`, `create_project_use_case.py`, `create_api_key_use_case.py`, `identity_use_cases.py` | medium | `test_characterization_unversioned_events.py` | 003 |
| D006 | `agent.#` self-subscription routing key still active in inbox consumer | `agent/infra/workers/inbox_consumer.py` | low | `test_characterization_subscriptions.py` | 003 |

## Severity

- **high**: Data loss or incorrect state possible
- **medium**: Architectural violation or inconsistency
- **low**: Redundant path, no functional impact

## Test status

All characterization tests are initially **RED** (known-violation sets document the defects). As corrective specs fix each item, the violation is removed from the known set.

## Target

Zero known defects after spec 009.
