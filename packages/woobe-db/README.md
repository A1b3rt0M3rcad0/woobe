# woobe-db

One-shot database package for Woobe. It owns Alembic bootstrap, migration execution and database validation. It may load schema metadata from `woobe-core` (and optional Enterprise extensions), but application/runtime code must not depend on this package.
