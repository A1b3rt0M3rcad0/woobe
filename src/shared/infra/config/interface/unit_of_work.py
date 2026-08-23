from abc import abstractmethod

from sqlalchemy.ext.asyncio import AsyncSession

from shared.contracts.unit_of_work import UnitOfWork as TransactionUnitOfWork


class UnitOfWork(TransactionUnitOfWork):
    """Legacy SQLAlchemy-aware UoW surface for non-migrated modules."""

    @property
    @abstractmethod
    def session(self) -> AsyncSession: ...
