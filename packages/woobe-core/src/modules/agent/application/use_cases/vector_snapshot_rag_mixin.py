from __future__ import annotations

from typing import Any, Protocol, cast

from modules.agent.application.interfaces.execution_context import current_execution


class _KnowledgeBindingSuper(Protocol):
    async def _load_history(self, message_repo: Any, session: Any) -> list[Any]: ...

    def _apply_release_to_agent(self, agent: Any, release: Any) -> Any: ...

    def _apply_snapshot_override(
        self,
        agent: Any,
        snapshot: dict[str, Any],
    ) -> Any: ...


class VectorSnapshotRAGMixin:
    """Compatibility bridge for Knowledge/runtime snapshot application.

    Retrieval no longer belongs to this mixin. The active RAG execution path is
    exclusively ``RAGRuntimeAdapter -> RAGStrategy``. This class remains in the
    resolver MRO only to preserve release/snapshot Knowledge bindings while that
    resolver hierarchy is kept stable.
    """

    async def _load_history(self, message_repo: Any, session: Any) -> list[Any]:
        parent = cast(_KnowledgeBindingSuper, super())
        history = await parent._load_history(message_repo, session)
        context = current_execution.get()
        if context is not None:
            context.project_id = getattr(session, "project_id", None)
            context.agent_id = getattr(session, "agent_id", None)
            context.session_id = getattr(session, "id", None)
        return history

    def _apply_release_to_agent(self, agent: Any, release: Any) -> Any:
        parent = cast(_KnowledgeBindingSuper, super())
        agent = parent._apply_release_to_agent(agent, release)
        settings = dict(agent.settings or {})

        model_spec_snapshot = getattr(release, "model_spec_snapshot", None)
        if isinstance(model_spec_snapshot, dict):
            settings["model_spec"] = deepcopy(model_spec_snapshot)
            settings["model_spec_frozen"] = True
        else:
            settings.pop("model_spec_frozen", None)

        fallback_model_spec_snapshot = getattr(
            release,
            "fallback_model_spec_snapshot",
            None,
        )
        if isinstance(fallback_model_spec_snapshot, dict):
            settings["fallback_model_spec"] = deepcopy(
                fallback_model_spec_snapshot
            )
            settings["fallback_model_spec_frozen"] = True
        else:
            settings.pop("fallback_model_spec_frozen", None)

        if release.knowledge_version_id is None:
            settings.pop("knowledge_version_id", None)
        else:
            settings["knowledge_version_id"] = str(release.knowledge_version_id)

        if getattr(release, "runtime_config", None) is None:
            settings.pop("runtime_config", None)
        else:
            settings["runtime_config"] = dict(release.runtime_config)

        agent.settings = settings
        return agent

    def _apply_snapshot_override(
        self,
        agent: Any,
        snapshot: dict[str, Any],
    ) -> Any:
        parent = cast(_KnowledgeBindingSuper, super())
        agent = parent._apply_snapshot_override(agent, snapshot)
        settings = dict(agent.settings or {})

        if "model_spec_snapshot" in snapshot:
            model_spec_snapshot = snapshot.get("model_spec_snapshot")
            if isinstance(model_spec_snapshot, dict):
                settings["model_spec"] = deepcopy(model_spec_snapshot)
                settings["model_spec_frozen"] = True
            else:
                settings.pop("model_spec_frozen", None)

        if "fallback_model_spec_snapshot" in snapshot:
            fallback_model_spec_snapshot = snapshot.get(
                "fallback_model_spec_snapshot"
            )
            if isinstance(fallback_model_spec_snapshot, dict):
                settings["fallback_model_spec"] = deepcopy(
                    fallback_model_spec_snapshot
                )
                settings["fallback_model_spec_frozen"] = True
            else:
                settings.pop("fallback_model_spec_frozen", None)

        if "knowledge_version_id" in snapshot:
            value = snapshot.get("knowledge_version_id")
            if value:
                settings["knowledge_version_id"] = str(value)
            else:
                settings.pop("knowledge_version_id", None)

        if "runtime_config" in snapshot:
            runtime_config = snapshot.get("runtime_config")
            if isinstance(runtime_config, dict):
                settings["runtime_config"] = runtime_config
            else:
                settings.pop("runtime_config", None)

        agent.settings = settings
        return agent
