from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import text

from modules.evaluation.application.failure_taxonomy import (
    classify_evaluation_failure,
    summarize_failures,
)
from modules.evaluation.application.human_decision_service import (
    HumanDecisionEvaluationApplicationService,
)


class EvidenceRichEvaluationApplicationService(
    HumanDecisionEvaluationApplicationService
):
    """Enrich Run reads without changing the immutable operational evidence."""

    @staticmethod
    def _target_payload(target) -> dict[str, Any]:
        payload = HumanDecisionEvaluationApplicationService._target_payload(target)
        snapshot = target.snapshot if isinstance(target.snapshot, dict) else {}
        manifest = payload.get("manifest") if isinstance(payload.get("manifest"), dict) else {}
        knowledge = (
            dict(manifest.get("knowledge"))
            if isinstance(manifest.get("knowledge"), dict)
            else {}
        )
        runtime = snapshot.get("runtime_config")
        runtime = runtime if isinstance(runtime, dict) else {}
        rag = runtime.get("rag")
        rag = rag if isinstance(rag, dict) else {}
        knowledge.update(
            {
                "knowledge_version_id": snapshot.get("knowledge_version_id"),
                "vector_snapshot_id": (
                    snapshot.get("vector_snapshot_id")
                    or rag.get("vector_snapshot_id")
                    or runtime.get("vector_snapshot_id")
                    or knowledge.get("vector_snapshot_id")
                ),
                "collection_ids": [
                    str(value) for value in snapshot.get("collection_ids") or []
                ],
                "rag": {
                    "search_strategy": rag.get("search_strategy"),
                    "candidate_k": rag.get("candidate_k"),
                    "top_k": rag.get("top_k"),
                    "min_score": rag.get("min_score"),
                    "grounding_policy": rag.get("grounding_policy"),
                },
            }
        )
        manifest["knowledge"] = knowledge
        payload["manifest"] = manifest
        return payload

    async def _attach_session_turns(self, trials: list[dict[str, Any]]) -> None:
        trial_ids: list[UUID] = []
        for trial in trials:
            try:
                trial_ids.append(UUID(str(trial.get("id"))))
            except (TypeError, ValueError):
                continue
        if not trial_ids:
            return
        async with self._session_factory() as session:
            rows = (
                await session.execute(
                    text(
                        "SELECT id, evaluation_trial_id, position, input_payload, "
                        "output_payload, metrics, status, agent_session_id, network_session_id, "
                        "agent_run_id, network_execution_id, trace_id, failure_code, failure_detail, "
                        "started_at, completed_at "
                        "FROM evaluation.trial_turns "
                        "WHERE evaluation_trial_id = ANY(CAST(:trial_ids AS uuid[])) "
                        "ORDER BY evaluation_trial_id, position"
                    ),
                    {"trial_ids": trial_ids},
                )
            ).mappings().all()
        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            grouped.setdefault(str(row["evaluation_trial_id"]), []).append(
                {
                    "id": str(row["id"]),
                    "position": int(row["position"]),
                    "input_payload": row["input_payload"],
                    "output": row["output_payload"],
                    "metrics": row["metrics"],
                    "status": row["status"],
                    "agent_session_id": str(row["agent_session_id"])
                    if row["agent_session_id"]
                    else None,
                    "network_session_id": str(row["network_session_id"])
                    if row["network_session_id"]
                    else None,
                    "agent_run_id": str(row["agent_run_id"])
                    if row["agent_run_id"]
                    else None,
                    "network_execution_id": str(row["network_execution_id"])
                    if row["network_execution_id"]
                    else None,
                    "trace_id": str(row["trace_id"]) if row["trace_id"] else None,
                    "failure_code": row["failure_code"],
                    "failure_detail": row["failure_detail"],
                    "started_at": row["started_at"].isoformat()
                    if row["started_at"]
                    else None,
                    "completed_at": row["completed_at"].isoformat()
                    if row["completed_at"]
                    else None,
                }
            )
        for trial in trials:
            case = trial.get("case") if isinstance(trial.get("case"), dict) else {}
            input_payload = (
                case.get("input_payload")
                if isinstance(case.get("input_payload"), dict)
                else {}
            )
            interaction_mode = str(
                input_payload.get("interaction_mode") or "single_turn"
            )
            trial["interaction_mode"] = interaction_mode
            trial["turns"] = grouped.get(str(trial.get("id")), [])
            if case:
                case["interaction_mode"] = interaction_mode
                case["turns"] = (
                    input_payload.get("turns", [])
                    if isinstance(input_payload.get("turns"), list)
                    else []
                )

    async def get_run(self, project_id: UUID, run_id: UUID) -> dict[str, Any]:
        payload = await super().get_run(project_id, run_id)
        trials = payload.get("trials") if isinstance(payload.get("trials"), list) else []
        await self._attach_session_turns(trials)
        judge_calls = (
            payload.get("judge_calls")
            if isinstance(payload.get("judge_calls"), list)
            else []
        )
        calls_by_trial = {
            str(item.get("trial_id")): item
            for item in judge_calls
            if isinstance(item, dict)
        }

        runtime_completed = 0
        judge_completed = 0
        conclusive = 0
        target_cost = 0.0
        target_cost_count = 0
        judge_cost = 0.0
        judge_cost_count = 0
        document_ids: set[str] = set()
        chunk_ids: set[str] = set()
        source_count = 0
        observed_collections: set[str] = set()
        output_contract_cases = 0
        output_contract_enforced = 0

        for trial in trials:
            if not isinstance(trial, dict):
                continue
            metrics = trial.get("metrics") if isinstance(trial.get("metrics"), dict) else {}
            runtime_done = bool(metrics.get("runtime_completed") or trial.get("output"))
            if runtime_done:
                runtime_completed += 1
            if trial.get("score") is not None and trial.get("passed") is not None:
                conclusive += 1
            target_value = metrics.get("cost_usd")
            if target_value is not None:
                target_cost += float(target_value)
                target_cost_count += 1
            call = calls_by_trial.get(str(trial.get("id")))
            if call and call.get("status") == "completed" and call.get("structured_result"):
                judge_completed += 1
            if call and call.get("cost_usd") is not None:
                judge_cost += float(call["cost_usd"])
                judge_cost_count += 1

            trial["failure_classification"] = classify_evaluation_failure(
                trial_status=trial.get("status"),
                failure_code=trial.get("failure_code"),
                failure_detail=trial.get("failure_detail"),
                judge_status=call.get("status") if call else None,
                judge_error=call.get("error") if call else None,
                runtime_completed=runtime_done,
            )

            output = trial.get("output") if isinstance(trial.get("output"), dict) else {}
            sources = output.get("sources") if isinstance(output.get("sources"), list) else []
            source_count += len(sources)
            for source in sources:
                if not isinstance(source, dict):
                    continue
                if source.get("document_id"):
                    document_ids.add(str(source["document_id"]))
                if source.get("chunk_id"):
                    chunk_ids.add(str(source["chunk_id"]))
                if source.get("collection_id"):
                    observed_collections.add(str(source["collection_id"]))

            case = trial.get("case") if isinstance(trial.get("case"), dict) else {}
            expected = (
                case.get("expected_contract")
                if isinstance(case.get("expected_contract"), dict)
                else {}
            )
            contract = (
                expected.get("output_contract")
                if isinstance(expected.get("output_contract"), dict)
                else {}
            )
            if contract.get("required"):
                output_contract_cases += 1
            if contract.get("json_required") or contract.get("schema"):
                output_contract_enforced += 1

        configured_collections: set[str] = set()
        configured_vector_snapshots: set[str] = set()
        configured_knowledge_versions: set[str] = set()
        structured_targets = 0
        for target in payload.get("targets", []):
            if not isinstance(target, dict):
                continue
            manifest = target.get("manifest") if isinstance(target.get("manifest"), dict) else {}
            knowledge = manifest.get("knowledge") if isinstance(manifest.get("knowledge"), dict) else {}
            configured_collections.update(str(value) for value in knowledge.get("collection_ids") or [])
            if knowledge.get("vector_snapshot_id"):
                configured_vector_snapshots.add(str(knowledge["vector_snapshot_id"]))
            if knowledge.get("knowledge_version_id"):
                configured_knowledge_versions.add(str(knowledge["knowledge_version_id"]))
            contract = manifest.get("output_contract") if isinstance(manifest.get("output_contract"), dict) else {}
            if contract.get("has_schema"):
                structured_targets += 1

        provenance_warnings: list[dict[str, Any]] = []
        if (
            source_count
            and not configured_collections
            and not configured_vector_snapshots
            and not configured_knowledge_versions
        ):
            provenance_warnings.append(
                {
                    "code": "knowledge_provenance_mismatch",
                    "message": (
                        "The runtime returned RAG sources, but the frozen target manifest does not declare a Knowledge Version, Collections or a Vector Snapshot."
                    ),
                    "severity": "high",
                    "recommended_action": (
                        "Publish a snapshot that freezes the Knowledge or Vector Snapshot provenance before using this evidence for release governance."
                    ),
                }
            )
        if structured_targets and output_contract_enforced == 0:
            provenance_warnings.append(
                {
                    "code": "structured_output_not_covered",
                    "message": (
                        "This historical Suite evaluated semantic behavior only. The target declares Structured Output, but these Test Cases did not validate JSON parsing or the frozen schema."
                    ),
                    "severity": "medium",
                    "recommended_action": (
                        "Create a new Suite version bound to this snapshot. New target-bound versions inherit the exact output schema automatically; this historical Run remains semantic-only evidence."
                    ),
                }
            )

        failure_summary = summarize_failures(trials, judge_calls)
        total = len(trials)
        if conclusive:
            evidence_status = "complete" if conclusive == total else "partial"
        elif runtime_completed:
            evidence_status = "unavailable"
        else:
            evidence_status = "partial" if trials else "unavailable"

        aggregate = payload.get("aggregate_result")
        aggregate = aggregate if isinstance(aggregate, dict) else {}
        try:
            evidence_revision = max(1, int(aggregate.get("evidence_revision") or 1))
        except (TypeError, ValueError):
            evidence_revision = 1

        payload["evidence_revision"] = evidence_revision
        payload["evidence_status"] = evidence_status
        payload["kpis"] = (
            dict(aggregate.get("kpis"))
            if isinstance(aggregate.get("kpis"), dict)
            else None
        )
        payload["evidence_completeness"] = {
            "total_trials": total,
            "runtime_completed": runtime_completed,
            "judge_completed": judge_completed,
            "conclusive_trials": conclusive,
            "inconclusive_trials": max(0, total - conclusive),
        }
        payload["failure_summary"] = failure_summary
        payload["cost_breakdown"] = {
            "target_runtime_cost_usd": target_cost if target_cost_count else None,
            "judge_cost_usd": judge_cost if judge_cost_count else None,
            "total_evaluation_cost_usd": payload.get("measured_total_cost"),
            "target_pricing_coverage_percent": (
                target_cost_count / total * 100 if total else 0
            ),
            "judge_pricing_coverage_percent": (
                judge_cost_count / total * 100 if total else 0
            ),
        }
        payload["knowledge_evidence"] = {
            "configured_knowledge_version_ids": sorted(configured_knowledge_versions),
            "configured_collection_ids": sorted(configured_collections),
            "configured_vector_snapshot_ids": sorted(configured_vector_snapshots),
            "observed_document_ids": sorted(document_ids),
            "observed_chunk_ids": sorted(chunk_ids),
            "observed_collection_ids": sorted(observed_collections),
            "observed_source_count": source_count,
        }
        payload["output_contract_coverage"] = {
            "structured_target_count": structured_targets,
            "cases_requiring_output": output_contract_cases,
            "cases_enforcing_json_or_schema": output_contract_enforced,
        }
        payload["provenance_warnings"] = provenance_warnings
        payload["legacy_comparison"] = payload.get("mode") == "comparison"

        async with self._session_factory() as session:
            row = (
                await session.execute(
                    text(
                        "SELECT evaluation_id, evaluation_protocol_hash, execution_policy "
                        "FROM evaluation.runs WHERE id = :run_id AND project_id = :project_id"
                    ),
                    {"run_id": run_id, "project_id": project_id},
                )
            ).one_or_none()
        payload["evaluation_id"] = str(row.evaluation_id) if row and row.evaluation_id else None
        payload["evaluation_protocol_hash"] = (
            str(row.evaluation_protocol_hash)
            if row and row.evaluation_protocol_hash
            else None
        )
        payload["execution_policy"] = (
            dict(row.execution_policy)
            if row and isinstance(row.execution_policy, dict)
            else payload.get("execution_policy")
        )
        return payload


__all__ = ["EvidenceRichEvaluationApplicationService"]
