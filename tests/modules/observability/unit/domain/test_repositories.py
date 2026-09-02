from abc import ABC

from modules.observability.application.interfaces.repositories import (
    TraceEventRepository,
    TraceRepository,
)


class TestTraceRepository:
    def test_is_abstract(self):
        assert issubclass(TraceRepository, ABC)
        assert getattr(TraceRepository.save, "__isabstractmethod__", False)
        assert getattr(TraceRepository.get_by_id, "__isabstractmethod__", False)
        assert getattr(TraceRepository.delete, "__isabstractmethod__", False)
        assert getattr(TraceRepository.paginate_by_project, "__isabstractmethod__", False)


class TestTraceEventRepository:
    def test_is_abstract(self):
        assert issubclass(TraceEventRepository, ABC)
        assert getattr(TraceEventRepository.save, "__isabstractmethod__", False)
        assert getattr(TraceEventRepository.get_by_id, "__isabstractmethod__", False)
        assert getattr(TraceEventRepository.delete, "__isabstractmethod__", False)
        assert getattr(TraceEventRepository.paginate_by_trace, "__isabstractmethod__", False)
