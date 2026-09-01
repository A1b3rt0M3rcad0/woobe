from __future__ import annotations

from typing import Generic, TypeVar

T = TypeVar("T")


class CursorPage(Generic[T]):
    def __init__(
        self,
        items: list[T],
        cursor: str | None = None,
        next_cursor: str | None = None,
        has_next: bool = False,
        total: int | None = None,
    ) -> None:
        self.items = items
        self.cursor = cursor
        self.next_cursor = next_cursor
        self.has_next = has_next
        self.total = total
