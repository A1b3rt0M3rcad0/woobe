from abc import ABC

from modules.core.application.interfaces.repositories import ApiKeyRepository, ProjectRepository


class TestProjectRepository:
    def test_is_abstract(self):
        assert issubclass(ProjectRepository, ABC)

    def test_has_save_abstract(self):
        assert hasattr(ProjectRepository, "save")
        assert getattr(ProjectRepository.save, "__isabstractmethod__", False)

    def test_has_get_by_id_abstract(self):
        assert hasattr(ProjectRepository, "get_by_id")
        assert getattr(ProjectRepository.get_by_id, "__isabstractmethod__", False)

    def test_has_delete_abstract(self):
        assert hasattr(ProjectRepository, "delete")
        assert getattr(ProjectRepository.delete, "__isabstractmethod__", False)


class TestApiKeyRepository:
    def test_is_abstract(self):
        assert issubclass(ApiKeyRepository, ABC)

    def test_has_save_abstract(self):
        assert getattr(ApiKeyRepository.save, "__isabstractmethod__", False)

    def test_has_get_by_id_abstract(self):
        assert getattr(ApiKeyRepository.get_by_id, "__isabstractmethod__", False)

    def test_has_get_by_key_hash_abstract(self):
        assert getattr(ApiKeyRepository.get_by_key_hash, "__isabstractmethod__", False)
