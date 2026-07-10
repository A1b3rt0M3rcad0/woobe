from uuid import uuid4

import pytest
from pydantic import ValidationError

from modules.core.application.dtos.create_api_key_dtos import CreateApiKeyInput


def test_project_key_creation_requires_explicit_scopes() -> None:
    with pytest.raises(ValidationError, match="scopes"):
        CreateApiKeyInput(
            project_id=uuid4(),
            name="Operational reader",
            scopes=[],
            created_by_user_id=uuid4(),
        )
