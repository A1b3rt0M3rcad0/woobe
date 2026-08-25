from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from modules.core.application.dtos.api_key_lifecycle_dtos import RotateApiKeyInput
from modules.core.application.dtos.list_api_keys_dtos import ListApiKeysInput
from modules.core.application.dtos.runtime_api_key_dtos import CreateRuntimeApiKeyInput
from modules.core.application.use_cases.api_key_lifecycle_use_cases import RotateApiKeyUseCase
from modules.core.application.use_cases.create_runtime_api_key_use_case import (
    CreateRuntimeApiKeyUseCase,
)
from modules.core.application.use_cases.list_api_keys_use_case import (
    ListApiKeysByProjectUseCase,
)
from modules.core.domain.entities import ApiKey
from modules.core.domain.enums import (
    ApiKeyKind,
    ApiKeyStatus,
    RuntimeEnvironment,
    RuntimeInterface,
)
from shared.infra.errors import NotFoundError
from shared.security.api_keys import (
    API_KEY_SCOPE_RUNTIME_EXECUTE,
    API_KEY_VERSION,
    LEGACY_API_KEY_VERSION,
)


@pytest.mark.asyncio
async def test_create_runtime_key_binds_agent_environment_and_interfaces() -> None:
    project_id = uuid4()
    agent_id = uuid4()
    user_id = uuid4()
    project_repo = SimpleNamespace(get_by_id=AsyncMock(return_value=SimpleNamespace(id=project_id)))
    target_reader = SimpleNamespace(get_target_project_id=AsyncMock(return_value=project_id))
    api_key_repo = SimpleNamespace()
    api_key_repo.save = AsyncMock(side_effect=lambda key: key)
    outbox = SimpleNamespace(write=AsyncMock())
    use_case = CreateRuntimeApiKeyUseCase(
        project_repo,
        target_reader,
        api_key_repo,
        outbox,
    )

    result = await use_case.execute(
        CreateRuntimeApiKeyInput(
            project_id=project_id,
            name="Customer production",
            agent_id=agent_id,
            environment=RuntimeEnvironment.production,
            interfaces=[RuntimeInterface.http, RuntimeInterface.stream],
            created_by_user_id=user_id,
        )
    )

    saved = api_key_repo.save.await_args.args[0]
    assert saved.kind == ApiKeyKind.runtime
    assert saved.project_id == project_id
    assert saved.agent_id == agent_id
    assert saved.environment == RuntimeEnvironment.production
    assert saved.interfaces == ["http", "stream"]
    assert saved.scopes == [API_KEY_SCOPE_RUNTIME_EXECUTE]
    assert saved.key_version == API_KEY_VERSION
    assert result.key.startswith("woobe_production_")
    assert result.key_prefix.startswith("woobe_production_")
    assert result.agent_id == agent_id
    assert result.environment == RuntimeEnvironment.production
    assert result.interfaces == ["http", "stream"]


@pytest.mark.asyncio
async def test_create_runtime_key_rejects_agent_from_another_project() -> None:
    project_id = uuid4()
    project_repo = SimpleNamespace(get_by_id=AsyncMock(return_value=SimpleNamespace(id=project_id)))
    target_reader = SimpleNamespace(get_target_project_id=AsyncMock(return_value=uuid4()))
    api_key_repo = SimpleNamespace(save=AsyncMock())
    outbox = SimpleNamespace(write=AsyncMock())
    use_case = CreateRuntimeApiKeyUseCase(
        project_repo,
        target_reader,
        api_key_repo,
        outbox,
    )

    with pytest.raises(NotFoundError, match="Agent not found"):
        await use_case.execute(
            CreateRuntimeApiKeyInput(
                project_id=project_id,
                name="Foreign agent",
                agent_id=uuid4(),
                environment=RuntimeEnvironment.staging,
                interfaces=[RuntimeInterface.http],
                created_by_user_id=uuid4(),
            )
        )

    api_key_repo.save.assert_not_awaited()


@pytest.mark.asyncio
async def test_rotation_preserves_binding_and_upgrades_legacy_runtime_key_format() -> None:
    current = ApiKey(
        project_id=uuid4(),
        name="Production integration",
        key_version=LEGACY_API_KEY_VERSION,
        scopes=[API_KEY_SCOPE_RUNTIME_EXECUTE],
        kind=ApiKeyKind.runtime,
        agent_id=uuid4(),
        environment=RuntimeEnvironment.production,
        interfaces=["http", "jobs"],
        created_by_user_id=uuid4(),
    )
    repo = SimpleNamespace()
    repo.get_by_id = AsyncMock(return_value=current)
    repo.update = AsyncMock(side_effect=lambda key: key)
    repo.save = AsyncMock(side_effect=lambda key: key)
    outbox = SimpleNamespace(write=AsyncMock())
    use_case = RotateApiKeyUseCase(repo, outbox)

    result = await use_case.execute(
        RotateApiKeyInput(
            project_id=current.project_id,
            api_key_id=current.id,
            rotated_by_user_id=uuid4(),
            scopes=["traces:read"],
        )
    )

    replacement = repo.save.await_args.args[0]
    assert replacement.kind == ApiKeyKind.runtime
    assert replacement.agent_id == current.agent_id
    assert replacement.environment == RuntimeEnvironment.production
    assert replacement.interfaces == ["http", "jobs"]
    assert replacement.scopes == [API_KEY_SCOPE_RUNTIME_EXECUTE]
    assert replacement.key_version == API_KEY_VERSION
    assert result.key.startswith("woobe_production_")
    assert result.key_prefix.startswith("woobe_production_")
    assert result.agent_id == current.agent_id
    assert result.environment == RuntimeEnvironment.production
    assert result.interfaces == ["http", "jobs"]


@pytest.mark.asyncio
async def test_list_api_keys_exposes_expired_status_from_expiration_timestamp() -> None:
    project_id = uuid4()
    api_key = ApiKey(
        project_id=project_id,
        name="Expired runtime key",
        kind=ApiKeyKind.runtime,
        agent_id=uuid4(),
        environment=RuntimeEnvironment.production,
        interfaces=["http"],
        scopes=[API_KEY_SCOPE_RUNTIME_EXECUTE],
        status=ApiKeyStatus.active,
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
        created_by_user_id=uuid4(),
    )
    repo = SimpleNamespace(list_by_project=AsyncMock(return_value=[api_key]))
    use_case = ListApiKeysByProjectUseCase(repo)

    result = await use_case.execute(ListApiKeysInput(project_id=project_id))

    assert result[0].status == ApiKeyStatus.expired


@pytest.mark.asyncio
async def test_list_api_keys_preserves_legacy_display_prefix() -> None:
    project_id = uuid4()
    api_key = ApiKey(
        project_id=project_id,
        name="Legacy runtime key",
        key_prefix="a" * 12,
        key_version=LEGACY_API_KEY_VERSION,
        kind=ApiKeyKind.runtime,
        agent_id=uuid4(),
        environment=RuntimeEnvironment.staging,
        interfaces=["http"],
        scopes=[API_KEY_SCOPE_RUNTIME_EXECUTE],
        created_by_user_id=uuid4(),
    )
    repo = SimpleNamespace(list_by_project=AsyncMock(return_value=[api_key]))
    use_case = ListApiKeysByProjectUseCase(repo)

    result = await use_case.execute(ListApiKeysInput(project_id=project_id))

    assert result[0].key_prefix == f"rai_live_{'a' * 12}"
