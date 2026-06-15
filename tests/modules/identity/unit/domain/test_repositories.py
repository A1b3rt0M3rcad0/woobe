from abc import ABC

from modules.identity.domain.repositories import (
    OrganizationInviteRepository,
    OrganizationMemberRepository,
    OrganizationRepository,
    UserRepository,
    UserSessionRepository,
)


class TestUserRepository:
    def test_is_abstract(self):
        assert issubclass(UserRepository, ABC)

    def test_has_save_abstract(self):
        assert hasattr(UserRepository, "save")
        assert getattr(UserRepository.save, "__isabstractmethod__", False)

    def test_has_get_by_id_abstract(self):
        assert hasattr(UserRepository, "get_by_id")
        assert getattr(UserRepository.get_by_id, "__isabstractmethod__", False)

    def test_has_get_by_email_abstract(self):
        assert hasattr(UserRepository, "get_by_email")
        assert getattr(UserRepository.get_by_email, "__isabstractmethod__", False)

    def test_has_delete_abstract(self):
        assert hasattr(UserRepository, "delete")
        assert getattr(UserRepository.delete, "__isabstractmethod__", False)


class TestOrganizationRepository:
    def test_is_abstract(self):
        assert issubclass(OrganizationRepository, ABC)

    def test_has_save_abstract(self):
        assert getattr(OrganizationRepository.save, "__isabstractmethod__", False)

    def test_has_get_by_id_abstract(self):
        assert getattr(OrganizationRepository.get_by_id, "__isabstractmethod__", False)

    def test_has_get_by_slug_abstract(self):
        assert getattr(OrganizationRepository.get_by_slug, "__isabstractmethod__", False)


class TestOrganizationMemberRepository:
    def test_is_abstract(self):
        assert issubclass(OrganizationMemberRepository, ABC)

    def test_has_save_abstract(self):
        assert getattr(OrganizationMemberRepository.save, "__isabstractmethod__", False)

    def test_has_get_by_organization_and_user_abstract(self):
        assert getattr(
            OrganizationMemberRepository.get_by_organization_and_user, "__isabstractmethod__", False
        )


class TestOrganizationInviteRepository:
    def test_is_abstract(self):
        assert issubclass(OrganizationInviteRepository, ABC)


class TestUserSessionRepository:
    def test_is_abstract(self):
        assert issubclass(UserSessionRepository, ABC)
