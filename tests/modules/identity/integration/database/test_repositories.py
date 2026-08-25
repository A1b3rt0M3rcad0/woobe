"""Integration tests for identity database repositories.

These tests verify that the canonical database repositories import correctly
and that the shim paths provide backward compatibility.
"""

from modules.identity.infra.database.models import (
    WorkspaceInviteModel,
    WorkspaceMemberModel,
    WorkspaceModel,
    UserModel,
    UserSessionModel,
)
from modules.identity.infra.database.repositories import (
    SQLAlchemyWorkspaceInviteRepository,
    SQLAlchemyWorkspaceMemberRepository,
    SQLAlchemyWorkspaceRepository,
    SQLAlchemyOutboxEventWriter,
    SQLAlchemyUserRepository,
    SQLAlchemyUserSessionRepository,
)
from modules.identity.infra.database.mappers import (
    workspace_entity_to_model,
    workspace_invite_entity_to_model,
    workspace_invite_model_to_entity,
    workspace_member_entity_to_model,
    workspace_member_model_to_entity,
    workspace_model_to_entity,
    user_entity_to_model,
    user_model_to_entity,
    user_session_entity_to_model,
    user_session_model_to_entity,
)


class TestCanonicalModelImports:
    def test_user_model_importable(self):
        assert UserModel.__tablename__ == "users"
        assert UserModel.__table_args__ == {"schema": "identity"}

    def test_workspace_model_importable(self):
        assert WorkspaceModel.__tablename__ == "workspaces"
        assert {"schema": "identity"}.items() <= WorkspaceModel.__table_args__[1].items()

    def test_workspace_member_model_importable(self):
        assert WorkspaceMemberModel.__tablename__ == "workspace_members"

    def test_workspace_invite_model_importable(self):
        assert WorkspaceInviteModel.__tablename__ == "workspace_invites"

    def test_user_session_model_importable(self):
        assert UserSessionModel.__tablename__ == "user_sessions"


class TestCanonicalRepositoryImports:
    def test_user_repository_importable(self):
        assert SQLAlchemyUserRepository is not None

    def test_workspace_repository_importable(self):
        assert SQLAlchemyWorkspaceRepository is not None

    def test_workspace_member_repository_importable(self):
        assert SQLAlchemyWorkspaceMemberRepository is not None

    def test_workspace_invite_repository_importable(self):
        assert SQLAlchemyWorkspaceInviteRepository is not None

    def test_user_session_repository_importable(self):
        assert SQLAlchemyUserSessionRepository is not None

    def test_outbox_event_writer_importable(self):
        assert SQLAlchemyOutboxEventWriter is not None


class TestCanonicalMapperImports:
    def test_user_mappers_importable(self):
        assert callable(user_model_to_entity)
        assert callable(user_entity_to_model)

    def test_workspace_mappers_importable(self):
        assert callable(workspace_model_to_entity)
        assert callable(workspace_entity_to_model)

    def test_workspace_member_mappers_importable(self):
        assert callable(workspace_member_model_to_entity)
        assert callable(workspace_member_entity_to_model)

    def test_workspace_invite_mappers_importable(self):
        assert callable(workspace_invite_model_to_entity)
        assert callable(workspace_invite_entity_to_model)

    def test_user_session_mappers_importable(self):
        assert callable(user_session_model_to_entity)
        assert callable(user_session_entity_to_model)
