from abc import ABC

from modules.identity.domain.repositories import (
    WorkspaceInviteRepository,
    WorkspaceMemberRepository,
    WorkspaceRepository,
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


class TestWorkspaceRepository:
    def test_is_abstract(self):
        assert issubclass(WorkspaceRepository, ABC)

    def test_has_save_abstract(self):
        assert getattr(WorkspaceRepository.save, "__isabstractmethod__", False)

    def test_has_get_by_id_abstract(self):
        assert getattr(WorkspaceRepository.get_by_id, "__isabstractmethod__", False)

    def test_has_get_by_slug_abstract(self):
        assert getattr(WorkspaceRepository.get_by_slug, "__isabstractmethod__", False)


class TestWorkspaceMemberRepository:
    def test_is_abstract(self):
        assert issubclass(WorkspaceMemberRepository, ABC)

    def test_has_save_abstract(self):
        assert getattr(WorkspaceMemberRepository.save, "__isabstractmethod__", False)

    def test_has_get_by_workspace_and_user_abstract(self):
        assert getattr(
            WorkspaceMemberRepository.get_by_workspace_and_user, "__isabstractmethod__", False
        )


class TestWorkspaceInviteRepository:
    def test_is_abstract(self):
        assert issubclass(WorkspaceInviteRepository, ABC)


class TestUserSessionRepository:
    def test_is_abstract(self):
        assert issubclass(UserSessionRepository, ABC)
