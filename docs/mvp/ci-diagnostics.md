# CI diagnostics

The first execution of the mandatory gates after PR 15 reported two failures:

- Backend failed at Ruff before Pyright, migrations, and Pytest.
- Migrations completed single-head validation and upgrade, then failed at Alembic schema drift detection.

The diagnostic workflow changes on this branch preserve failure semantics and upload the complete Ruff and Alembic reports as ephemeral artifacts. These trigger and artifact changes are temporary and must be removed before merge.
