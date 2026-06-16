import inspect

from modules.tools.infra.database.repositories import (
    SQLAlchemyOutboxEventWriter,
    SQLAlchemySecretRepository,
    SQLAlchemyToolRepository,
)
from modules.tools.infra.database import (
    InboxEventModel,
    OutboxEventModel,
    SecretModel,
    ToolModel,
)


class TestToolsRepositoriesImports:
    def test_tool_repository_importable(self):
        assert SQLAlchemyToolRepository is not None

    def test_secret_repository_importable(self):
        assert SQLAlchemySecretRepository is not None

    def test_outbox_writer_importable(self):
        assert SQLAlchemyOutboxEventWriter is not None

    def test_models_importable(self):
        assert ToolModel is not None
        assert SecretModel is not None
        assert OutboxEventModel is not None
        assert InboxEventModel is not None

    def test_models_have_correct_schema(self):
        assert ToolModel.__table_args__["schema"] == "tools"
        assert SecretModel.__table_args__[1]["schema"] == "tools"
        assert OutboxEventModel.__table_args__["schema"] == "tools"
        assert InboxEventModel.__table_args__["schema"] == "tools"

    def test_models_have_correct_tablename(self):
        assert ToolModel.__tablename__ == "tools"
        assert SecretModel.__tablename__ == "secrets"
        assert OutboxEventModel.__tablename__ == "outbox_events"
        assert InboxEventModel.__tablename__ == "inbox_events"

    def test_tool_repository_accepts_session(self):
        sig = inspect.signature(SQLAlchemyToolRepository.__init__)
        assert "session" in sig.parameters

    def test_secret_repository_accepts_session(self):
        sig = inspect.signature(SQLAlchemySecretRepository.__init__)
        assert "session" in sig.parameters
