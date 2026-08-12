from alembic.config import Config
from alembic.script import ScriptDirectory


def _script_directory() -> ScriptDirectory:
    return ScriptDirectory.from_config(Config("alembic.ini"))


def test_migration_graph_has_one_head() -> None:
    assert _script_directory().get_heads() == ["0055"]


def test_revision_identifiers_are_unique() -> None:
    revisions = list(
        _script_directory().walk_revisions(base="base", head="heads")
    )
    identifiers = [revision.revision for revision in revisions]
    assert len(identifiers) == len(set(identifiers))
