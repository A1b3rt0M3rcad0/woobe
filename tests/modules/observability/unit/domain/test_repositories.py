from abc import ABC

from modules.observability.domain.repositories import TraceEventRepository, TraceRepository


class TestTraceRepository:
    def test_is_abstract(self):
        assert issubclass(TraceRepository, ABC)

    def test_has_save_abstract(self):
        assert getattr(TraceRepository.save, "__isabstractmethod__", False)

    def test_has_get_by_id_abstract(self):
        assert getattr(TraceRepository.get_by_id, "__isabstractmethod__", False)

    def test_has_delete_abstract(self):
        assert getattr(TraceRepository.delete, "__isabstractmethod__", False)

    def test_has_paginate_by_project_abstract(self):
        assert getattr(TraceRepository.paginate_by_project, "__isabstractmethod__", False)


class TestTraceEventRepository:
    def test_is_abstract(self):
        assert issubclass(TraceEventRepository, ABC)

    def test_has_save_abstract(self):
        assert getattr(TraceEventRepository.save, "__isabstractmethod__", False)

    def test_has_get_by_id_abstract(self):
        assert getattr(TraceEventRepository.get_by_id, "__isabstractmethod__", False)

    def test_has_delete_abstract(self):
        assert getattr(TraceEventRepository.delete, "__isabstractmethod__", False)

    def test_has_paginate_by_trace_abstract(self):
        assert getattr(TraceEventRepository.paginate_by_trace, "__isabstractmethod__", False)
