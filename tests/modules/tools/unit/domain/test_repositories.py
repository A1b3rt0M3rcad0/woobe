from abc import ABC

from modules.tools.domain.repositories import SecretRepository, ToolRepository


class TestToolRepository:
    def test_is_abstract(self):
        assert issubclass(ToolRepository, ABC)

    def test_has_create_abstract(self):
        assert getattr(ToolRepository.create, "__isabstractmethod__", False)

    def test_has_get_by_id_abstract(self):
        assert getattr(ToolRepository.get_by_id, "__isabstractmethod__", False)

    def test_has_update_abstract(self):
        assert getattr(ToolRepository.update, "__isabstractmethod__", False)

    def test_has_delete_abstract(self):
        assert getattr(ToolRepository.delete, "__isabstractmethod__", False)


class TestSecretRepository:
    def test_is_abstract(self):
        assert issubclass(SecretRepository, ABC)

    def test_has_create_abstract(self):
        assert getattr(SecretRepository.create, "__isabstractmethod__", False)

    def test_has_get_by_id_abstract(self):
        assert getattr(SecretRepository.get_by_id, "__isabstractmethod__", False)

    def test_has_get_by_name_abstract(self):
        assert getattr(SecretRepository.get_by_name, "__isabstractmethod__", False)

    def test_has_update_abstract(self):
        assert getattr(SecretRepository.update, "__isabstractmethod__", False)

    def test_has_delete_abstract(self):
        assert getattr(SecretRepository.delete, "__isabstractmethod__", False)
