from shared.infra.objects import CursorPage


class TestCursorPage:
    def test_empty_page(self):
        page = CursorPage(items=[])
        assert page.items == []
        assert page.cursor is None
        assert page.next_cursor is None
        assert page.has_next is False
        assert page.total is None

    def test_with_items(self):
        page = CursorPage(items=[1, 2, 3])
        assert list(page.items) == [1, 2, 3]
        assert len(page.items) == 3

    def test_with_cursor(self):
        page = CursorPage(
            items=["a", "b"],
            cursor="cursor_abc",
            next_cursor="cursor_next",
            has_next=True,
            total=10,
        )
        assert page.cursor == "cursor_abc"
        assert page.next_cursor == "cursor_next"
        assert page.has_next is True
        assert page.total == 10

    def test_generic_with_strings(self):
        page: CursorPage[str] = CursorPage(items=["x", "y", "z"])
        assert isinstance(page.items[0], str)

    def test_generic_with_integers(self):
        page: CursorPage[int] = CursorPage(items=[1, 2, 3])
        assert isinstance(page.items[0], int)

    def test_generic_with_dicts(self):
        page: CursorPage[dict] = CursorPage(items=[{"id": 1}, {"id": 2}])
        assert page.items[0]["id"] == 1

    def test_iteration(self):
        page = CursorPage(items=[10, 20, 30])
        values = [item for item in page.items]
        assert values == [10, 20, 30]

    def test_page_with_mixed_total(self):
        page = CursorPage(items=[1, 2], total=100)
        assert page.total == 100
        assert page.has_next is False
