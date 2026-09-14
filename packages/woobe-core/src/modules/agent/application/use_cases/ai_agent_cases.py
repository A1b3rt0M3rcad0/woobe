from typing import Protocol
from uuid import UUID

from modules.agent.application.interfaces.skill_repository import SkillRepository
from modules.agent.application.skill_bindings import freeze_skill_bindings

from modules.agent.application.context_assembler_registry import (
    DEFAULT_CONTEXT_MANAGER_SETTING,
    canonicalize_context_assembler_runtime_config,
)
from modules.agent.application.execution_strategy_config import (
    canonicalize_execution_strategy_runtime_config,
)
from modules.agent.application.dtos.ai_dtos import (
    CreateAgentInput,
    GetAgentInput,
    ListAgentsInput,
    ListAgentsOutput,
    UpdateAgentInput,
    UpdateAgentOutput,
)
from modules.agent.application.dtos.behavior_dtos import canonicalize_behavior_spec
from modules.agent.application.interfaces.outbox import OutboxEventWriter
from modules.agent.application.interfaces.provider_model_repository import (
    ProviderModelRepository,
)
from modules.agent.application.interfaces.repositories import (
    AgentRepository,
    ProviderCredentialRepository,
)
from modules.agent.application.system_instruction_assembler import assemble_system_instructions
from modules.agent.domain.entities import Agent
from modules.agent.domain.enums import CredentialStatus, ProviderModelStatus
from modules.agent.domain.events import AgentCreatedV1, AgentUpdatedV1
from shared.contracts.errors import ConflictError, ValidationError


class NetworkAgentUsageReader(Protocol):
    async def list_draft_references(
        self,
        *,
        project_id: UUID,
        agent_id: UUID,
    ) -> list[dict[str, str]]: ...


class CreateAgentUseCase:
    def __init__(
        self,
        agent_repo: AgentRepository,
        credential_repo: ProviderCredentialRepository,
        outbox: OutboxEventWriter,
        provider_model_repo: ProviderModelRepository | None = None,
        *,
        default_context_manager: str = DEFAULT_CONTEXT_MANAGER_SETTING,
        skill_repo: SkillRepository | None = None,
    ) -> None:
        self._agent_repo = agent_repo
        self._credential_repo = credential_repo
        self._provider_model_repo = provider_model_repo
        self._outbox = outbox
        self._default_context_manager = default_context_manager
        self._skill_repo = skill_repo

    async def execute(self, input_dto: CreateAgentInput) -> Agent:
        agent = Agent(**input_dto.model_dump())
        if agent.behavior_spec is not None:
            agent.behavior_spec = canonicalize_behavior_spec(agent.behavior_spec)
            agent.system_prompt = assemble_system_instructions(
                agent.name, agent.description, agent.behavior_spec
            )
        _force_strict_json_settings(
            agent,
            default_context_manager=self._default_context_manager,
            initialize_context_manager=True,
        )
        await _resolve_implicit_provider_model_bindings(agent, self._provider_model_repo)
        await _resolve_provider_model_bindings(
            agent,
            self._provider_model_repo,
            self._credential_repo,
        )
        if agent.provider_credential_id and not await self._credential_repo.get_by_id(agent.provider_credential_id):
            from modules.agent.domain.errors import CredentialNotFoundError
            raise CredentialNotFoundError(agent.provider_credential_id)
        if "skills" in (agent.settings or {}).get("runtime_config", {}):
            agent.settings["runtime_config"] = await freeze_skill_bindings(
                self._skill_repo, project_id=agent.project_id,
                runtime_config=agent.settings["runtime_config"],
            )
        saved = await self._agent_repo.save(agent)
        await self._outbox.write(AgentCreatedV1.create(
            agent_id=saved.id,
            project_id=saved.project_id,
            name=saved.name,
            provider=saved.provider.value if hasattr(saved.provider, "value") else str(saved.provider),
            model=saved.model,
        ))
        return saved


class UpdateAgentUseCase:
    def __init__(
        self,
        agent_repo: AgentRepository,
        credential_repo: ProviderCredentialRepository,
        outbox: OutboxEventWriter,
        provider_model_repo: ProviderModelRepository | None = None,
        network_usage_reader: NetworkAgentUsageReader | None = None,
        *,
        skill_repo: SkillRepository | None = None,
    ) -> None:
        self._agent_repo = agent_repo
        self._credential_repo = credential_repo
        self._provider_model_repo = provider_model_repo
        self._network_usage_reader = network_usage_reader
        self._skill_repo = skill_repo
        self._outbox = outbox

    async def execute(self, agent_id: UUID, input_dto: UpdateAgentInput) -> UpdateAgentOutput:
        existing = await self._agent_repo.get_by_id(agent_id)
        if not existing:
            from modules.agent.domain.errors import AgentNotFoundError
            raise AgentNotFoundError(agent_id)
        changes = input_dto.model_dump(exclude_unset=True)
        if (
            existing.behavior_spec is not None
            and "system_prompt" in changes
            and "behavior_spec" not in changes
        ):
            raise ConflictError("Update behavior_spec for an Agent with structured Behavior")
        if (
            "behavior_spec" in changes
            and changes["behavior_spec"] is None
            and "system_prompt" not in changes
        ):
            raise ConflictError("Clearing behavior_spec requires explicit legacy system_prompt")
        requested_status = changes.get("status")
        current_status = getattr(existing.status, "value", existing.status)
        next_status = getattr(requested_status, "value", requested_status)
        if (
            requested_status is not None
            and str(current_status) == "active"
            and str(next_status) != "active"
            and self._network_usage_reader is not None
        ):
            references = await self._network_usage_reader.list_draft_references(
                project_id=existing.project_id,
                agent_id=existing.id,
            )
            if references:
                names = ", ".join(item["name"] for item in references[:5])
                remaining = len(references) - min(len(references), 5)
                suffix = f" and {remaining} more" if remaining > 0 else ""
                raise ConflictError(
                    "Agent is referenced by active Network Drafts: "
                    f"{names}{suffix}. Remove it from those Networks before deactivating it."
                )
        for field, value in changes.items():
            setattr(existing, field, value)
        if existing.behavior_spec is not None:
            existing.behavior_spec = canonicalize_behavior_spec(existing.behavior_spec)
            existing.system_prompt = assemble_system_instructions(
                existing.name, existing.description, existing.behavior_spec
            )
        _force_strict_json_settings(existing)
        await _resolve_implicit_provider_model_bindings(existing, self._provider_model_repo)
        await _resolve_provider_model_bindings(
            existing,
            self._provider_model_repo,
            self._credential_repo,
        )
        if "skills" in (existing.settings or {}).get("runtime_config", {}):
            existing.settings["runtime_config"] = await freeze_skill_bindings(
                self._skill_repo, project_id=existing.project_id,
                runtime_config=existing.settings["runtime_config"],
            )
        saved = await self._agent_repo.update(existing)
        await self._outbox.write(AgentUpdatedV1.create(
            agent_id=saved.id,
            project_id=saved.project_id,
            name=saved.name,
            provider=saved.provider.value if hasattr(saved.provider, "value") else str(saved.provider),
            model=saved.model,
        ))
        return UpdateAgentOutput(
            id=saved.id,
            project_id=saved.project_id,
            name=saved.name,
            type=saved.type,
            provider=saved.provider,
            model=saved.model,
            provider_model_id=saved.provider_model_id,
            fallback_provider_model_id=saved.fallback_provider_model_id,
            provider_credential_id=saved.provider_credential_id,
            fallback_credential_id=saved.fallback_credential_id,
            fallback_provider=saved.fallback_provider,
            fallback_model=saved.fallback_model,
            temperature=saved.temperature,
            max_output_tokens=saved.max_output_tokens,
            session_mode=saved.session_mode,
            behavior_spec=getattr(saved, "behavior_spec", None),
            system_prompt=saved.system_prompt,
            description=saved.description,
            status=saved.status,
            settings=saved.settings,
            created_at=saved.created_at,
            updated_at=saved.updated_at,
        )


class ListAgentsUseCase:
    def __init__(self, agent_repo: AgentRepository) -> None:
        self._agent_repo = agent_repo

    async def execute(self, input_dto: ListAgentsInput) -> list[ListAgentsOutput]:
        if not input_dto.project_id:
            return []
        return [
            ListAgentsOutput(
                id=item.id,
                project_id=item.project_id,
                name=item.name,
                description=item.description,
                type=item.type,
                behavior_spec=getattr(item, "behavior_spec", None),
                system_prompt=item.system_prompt,
                provider=item.provider,
                model=item.model,
                provider_model_id=item.provider_model_id,
                fallback_provider_model_id=item.fallback_provider_model_id,
                provider_credential_id=item.provider_credential_id,
                fallback_credential_id=item.fallback_credential_id,
                fallback_provider=item.fallback_provider,
                fallback_model=item.fallback_model,
                temperature=item.temperature,
                max_output_tokens=item.max_output_tokens,
                session_mode=item.session_mode,
                status=item.status,
                settings=item.settings,
                created_at=item.created_at,
                updated_at=item.updated_at,
            )
            for item in await self._agent_repo.list_by_project(input_dto.project_id)
        ]


class GetAgentByIdUseCase:
    def __init__(self, agent_repo: AgentRepository) -> None:
        self._agent_repo = agent_repo

    async def execute(self, input_dto: GetAgentInput) -> Agent:
        from modules.agent.domain.errors import AgentNotFoundError
        item = await self._agent_repo.get_by_id(input_dto.agent_id)
        if not item:
            raise AgentNotFoundError(input_dto.agent_id)
        return item


def _is_embedding_provider_model(provider_model) -> bool:
    metadata = provider_model.metadata or {}
    capability = str(metadata.get("capability") or metadata.get("type") or "").strip().lower()
    if capability:
        return capability in {"embedding", "embeddings"}
    value = f"{provider_model.name} {provider_model.model}".lower()
    return "embed" in value


def _ensure_agent_compatible_provider_model(provider_model) -> None:
    if _is_embedding_provider_model(provider_model):
        raise ConflictError("Provider model is not compatible with agent runtime")


def _force_strict_json_settings(
    agent: Agent,
    *,
    default_context_manager: str = DEFAULT_CONTEXT_MANAGER_SETTING,
    initialize_context_manager: bool = False,
) -> None:
    settings = dict(agent.settings or {})
    if initialize_context_manager or "runtime_config" in settings:
        runtime_config = canonicalize_context_assembler_runtime_config(
            settings.get("runtime_config"),
            default_context_manager=default_context_manager,
            use_current_default_if_missing=initialize_context_manager,
        )
        settings["runtime_config"] = canonicalize_execution_strategy_runtime_config(
            runtime_config
        )
    response_format = settings.get("response_format")
    if not isinstance(response_format, dict):
        agent.settings = settings
        return
    if response_format.get("enabled") is not True or response_format.get("type") != "json":
        agent.settings = settings
        return
    settings["response_format"] = {**response_format, "strict": True}
    agent.settings = settings


async def _resolve_implicit_provider_model_bindings(
    agent: Agent,
    provider_model_repo: ProviderModelRepository | None,
) -> None:
    if provider_model_repo is None:
        return

    if not agent.provider_model_id and agent.provider_credential_id and agent.model:
        candidates = await provider_model_repo.list_by_credential(agent.provider_credential_id)
        matches = [
            item
            for item in candidates
            if item.project_id == agent.project_id
            and item.model.strip() == agent.model.strip()
            and getattr(item.status, "value", item.status) == ProviderModelStatus.active.value
            and not _is_embedding_provider_model(item)
        ]
        if matches:
            agent.provider_model_id = sorted(matches, key=lambda item: str(item.id))[0].id

    if not agent.fallback_provider_model_id and agent.fallback_credential_id and agent.fallback_model:
        candidates = await provider_model_repo.list_by_credential(agent.fallback_credential_id)
        matches = [
            item
            for item in candidates
            if item.project_id == agent.project_id
            and item.model.strip() == agent.fallback_model.strip()
            and getattr(item.status, "value", item.status) == ProviderModelStatus.active.value
            and not _is_embedding_provider_model(item)
        ]
        if matches:
            agent.fallback_provider_model_id = sorted(matches, key=lambda item: str(item.id))[0].id


async def _resolve_provider_model_bindings(
    agent: Agent,
    provider_model_repo: ProviderModelRepository | None,
    credential_repo: ProviderCredentialRepository,
) -> None:
    if provider_model_repo is None:
        return
    if agent.provider_model_id:
        provider_model = await provider_model_repo.get_by_id(agent.provider_model_id)
        if provider_model is None or provider_model.project_id != agent.project_id:
            from modules.agent.domain.errors import ModelConfigNotFoundError
            raise ModelConfigNotFoundError
        if getattr(provider_model.status, "value", provider_model.status) != ProviderModelStatus.active.value:
            raise ValidationError("Provider model must be active")
        _ensure_agent_compatible_provider_model(provider_model)
        credential = await credential_repo.get_by_id(provider_model.provider_credential_id)
        if credential is None or credential.project_id != agent.project_id:
            from modules.agent.domain.errors import CredentialNotFoundError
            raise CredentialNotFoundError(provider_model.provider_credential_id)
        if getattr(credential.status, "value", credential.status) != CredentialStatus.active.value:
            raise ValidationError("Provider credential must be active")
        agent.provider_credential_id = credential.id
        agent.provider = credential.provider
        agent.model = provider_model.model

    if agent.fallback_provider_model_id:
        fallback_model = await provider_model_repo.get_by_id(agent.fallback_provider_model_id)
        if fallback_model is None or fallback_model.project_id != agent.project_id:
            from modules.agent.domain.errors import ModelConfigNotFoundError
            raise ModelConfigNotFoundError
        _ensure_agent_compatible_provider_model(fallback_model)
        credential = await credential_repo.get_by_id(fallback_model.provider_credential_id)
        if credential is None or credential.project_id != agent.project_id:
            from modules.agent.domain.errors import CredentialNotFoundError
            raise CredentialNotFoundError(fallback_model.provider_credential_id)
        agent.fallback_credential_id = credential.id
        agent.fallback_provider = credential.provider
        agent.fallback_model = fallback_model.model
