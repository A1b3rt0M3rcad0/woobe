from modules.core.infra.database.models import (
    ApiKeyModel,
    InboxEventModel,
    OutboxEventModel,
    ProjectModel,
)
from modules.core.infra.database.repositories import (
    SQLAlchemyApiKeyRepository,
    SQLAlchemyOutboxEventWriter,
    SQLAlchemyProjectRepository,
)
from modules.core.infra.database.mappers import (
    api_key_entity_to_model,
    api_key_model_to_entity,
    project_entity_to_model,
    project_model_to_entity,
)


class TestCanonicalModelImports:
    def test_project_model_importable(self):
        assert ProjectModel.__tablename__ == "projects"

    def test_api_key_model_importable(self):
        assert ApiKeyModel.__tablename__ == "api_keys"

    def test_outbox_model_importable(self):
        assert OutboxEventModel.__tablename__ == "outbox_events"

    def test_inbox_model_importable(self):
        assert InboxEventModel.__tablename__ == "inbox_events"


class TestCanonicalRepositoryImports:
    def test_project_repository_importable(self):
        assert SQLAlchemyProjectRepository is not None

    def test_api_key_repository_importable(self):
        assert SQLAlchemyApiKeyRepository is not None

    def test_outbox_writer_importable(self):
        assert SQLAlchemyOutboxEventWriter is not None


class TestCanonicalMapperImports:
    def test_project_mappers_importable(self):
        assert callable(project_model_to_entity)
        assert callable(project_entity_to_model)

    def test_api_key_mappers_importable(self):
        assert callable(api_key_model_to_entity)
        assert callable(api_key_entity_to_model)
