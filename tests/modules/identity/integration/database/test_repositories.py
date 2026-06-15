"""Integration tests for identity database repositories.

These tests verify that the canonical database repositories import correctly
and that the shim paths provide backward compatibility.
"""

from modules.identity.infra.database.models import (
    OrganizationInviteModel,
    OrganizationMemberModel,
    OrganizationModel,
    UserModel,
    UserSessionModel,
)
from modules.identity.infra.database.repositories import (
    SQLAlchemyOrganizationInviteRepository,
    SQLAlchemyOrganizationMemberRepository,
    SQLAlchemyOrganizationRepository,
    SQLAlchemyOutboxEventWriter,
    SQLAlchemyUserRepository,
    SQLAlchemyUserSessionRepository,
)
from modules.identity.infra.database.mappers import (
    organization_entity_to_model,
    organization_invite_entity_to_model,
    organization_invite_model_to_entity,
    organization_member_entity_to_model,
    organization_member_model_to_entity,
    organization_model_to_entity,
    user_entity_to_model,
    user_model_to_entity,
    user_session_entity_to_model,
    user_session_model_to_entity,
)


class TestCanonicalModelImports:
    def test_user_model_importable(self):
        assert UserModel.__tablename__ == "users"
        assert UserModel.__table_args__ == {"schema": "identity"}

    def test_organization_model_importable(self):
        assert OrganizationModel.__tablename__ == "organizations"
        assert {"schema": "identity"}.items() <= OrganizationModel.__table_args__[1].items()

    def test_organization_member_model_importable(self):
        assert OrganizationMemberModel.__tablename__ == "organization_members"

    def test_organization_invite_model_importable(self):
        assert OrganizationInviteModel.__tablename__ == "organization_invites"

    def test_user_session_model_importable(self):
        assert UserSessionModel.__tablename__ == "user_sessions"


class TestCanonicalRepositoryImports:
    def test_user_repository_importable(self):
        assert SQLAlchemyUserRepository is not None

    def test_organization_repository_importable(self):
        assert SQLAlchemyOrganizationRepository is not None

    def test_organization_member_repository_importable(self):
        assert SQLAlchemyOrganizationMemberRepository is not None

    def test_organization_invite_repository_importable(self):
        assert SQLAlchemyOrganizationInviteRepository is not None

    def test_user_session_repository_importable(self):
        assert SQLAlchemyUserSessionRepository is not None

    def test_outbox_event_writer_importable(self):
        assert SQLAlchemyOutboxEventWriter is not None


class TestCanonicalMapperImports:
    def test_user_mappers_importable(self):
        assert callable(user_model_to_entity)
        assert callable(user_entity_to_model)

    def test_organization_mappers_importable(self):
        assert callable(organization_model_to_entity)
        assert callable(organization_entity_to_model)

    def test_organization_member_mappers_importable(self):
        assert callable(organization_member_model_to_entity)
        assert callable(organization_member_entity_to_model)

    def test_organization_invite_mappers_importable(self):
        assert callable(organization_invite_model_to_entity)
        assert callable(organization_invite_entity_to_model)

    def test_user_session_mappers_importable(self):
        assert callable(user_session_model_to_entity)
        assert callable(user_session_entity_to_model)
