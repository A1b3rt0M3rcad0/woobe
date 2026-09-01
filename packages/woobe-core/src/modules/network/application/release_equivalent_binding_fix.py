from __future__ import annotations


def install_equivalent_binding_result_fix() -> None:
    from modules.network.application.service import NetworkApplicationService

    if hasattr(NetworkApplicationService, "_equivalent_binding_fix_base_plan"):
        return

    base_plan = NetworkApplicationService._build_promotion_plan

    async def build_plan(self, session, definition, project_id, environment, *, lock=False):
        plan = await base_plan(
            self,
            session,
            definition,
            project_id,
            environment,
            lock=lock,
        )
        for node in plan.get("nodes", []):
            node.setdefault("source_ref", node.get("selected_ref"))
            node.setdefault("source_version", node.get("selected_version"))
            if (
                node.get("result_resolution") == "equivalent_reused"
                and node.get("result_ref")
            ):
                node["selected_ref"] = node["result_ref"]
                node["selected_version"] = node.get("result_version")
        return plan

    NetworkApplicationService._equivalent_binding_fix_base_plan = base_plan  # type: ignore[attr-defined]
    NetworkApplicationService._build_promotion_plan = build_plan  # type: ignore[assignment]
