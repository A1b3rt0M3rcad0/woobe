from __future__ import annotations

from typing import Any
from uuid import UUID

from modules.evaluation.application.run_diagnostics_service import (
    EvaluationRunDiagnosticsService,
)


class GovernedEvaluationRunDiagnosticsService(EvaluationRunDiagnosticsService):
    async def get_run_diagnostics(
        self,
        *,
        project_id: UUID,
        run_id: UUID,
    ) -> dict[str, Any]:
        payload = await super().get_run_diagnostics(
            project_id=project_id,
            run_id=run_id,
        )
        calls = payload.get("judge_calls") or []
        governed_markers = sum(
            1
            for call in calls
            if isinstance(call, dict)
            and isinstance(call.get("diagnostics"), dict)
            and call["diagnostics"].get("governed_gateway_version")
            == "governed-judge-v1"
        )
        terminal_calls = sum(
            1
            for call in calls
            if isinstance(call, dict)
            and isinstance(call.get("diagnostics"), dict)
            and call["diagnostics"].get("terminal_failure") is True
        )
        circuit = (
            (payload.get("run") or {}).get("aggregate_result", {}).get(
                "judge_circuit_breaker"
            )
            if isinstance((payload.get("run") or {}).get("aggregate_result"), dict)
            else None
        )
        summary = dict(payload.get("summary") or {})
        summary["governed_gateway_markers"] = governed_markers
        summary["terminal_judge_calls"] = terminal_calls
        summary["judge_circuit_breaker_status"] = (
            circuit.get("status") if isinstance(circuit, dict) else None
        )
        payload["summary"] = summary

        signals = [
            signal
            for signal in payload.get("signals") or []
            if not (
                governed_markers
                and signal.get("code") in {
                    "resilient_gateway_not_observed",
                    "adaptive_gateway_version_not_observed",
                }
            )
        ]
        if calls and governed_markers == 0:
            signals.append(
                {
                    "severity": "warning",
                    "code": "governed_gateway_not_observed",
                    "message": (
                        "No governed-judge-v1 marker was persisted. Restart the Evaluation "
                        "worker before trusting retries or output-budget behavior."
                    ),
                }
            )
        if terminal_calls:
            signals.append(
                {
                    "severity": "error",
                    "code": "terminal_judge_failure",
                    "message": (
                        f"{terminal_calls} Judge call(s) reported a terminal provider failure. "
                        "These calls are not eligible for automatic repair."
                    ),
                }
            )
        if isinstance(circuit, dict) and circuit.get("status") == "open":
            signals.append(
                {
                    "severity": "error",
                    "code": "judge_circuit_breaker_open",
                    "message": (
                        "Judge fan-out was stopped after the canary detected "
                        f"{circuit.get('code') or 'a terminal failure'}."
                    ),
                }
            )
        payload["signals"] = signals
        return payload


__all__ = ["GovernedEvaluationRunDiagnosticsService"]
