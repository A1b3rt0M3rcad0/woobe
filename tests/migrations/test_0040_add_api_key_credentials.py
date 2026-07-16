"""Tests for migration 0040: logical API key credentials."""

import importlib


def _get_migration():
    return importlib.import_module("migrations.versions.0040_add_api_key_credentials")


def test_migration_revision_chain():
    migration = _get_migration()
    assert migration.revision == "0040"
    assert migration.down_revision == "0039"


def test_api_key_model_exposes_logical_credential_metadata():
    from modules.core.infra.database.models import ApiKeyModel

    assert ApiKeyModel.__table__.columns["credential_id"].nullable is False
    assert ApiKeyModel.__table__.columns["description"].nullable is True
    assert "ix_core_api_keys_credential_created" in {
        index.name for index in ApiKeyModel.__table__.indexes
    }
