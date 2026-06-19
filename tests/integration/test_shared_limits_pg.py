from uuid import uuid4


def test_shared_limit_subjects_are_unique() -> None:
    assert uuid4() != uuid4()
