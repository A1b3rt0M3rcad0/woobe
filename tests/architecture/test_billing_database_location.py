from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BILLING_DIR = PROJECT_ROOT / "packages" / "woobe-core" / "src" / "modules" / "billing"


class TestBillingDatabaseLocation:
    def test_database_models_in_canonical_location(self):
        path = BILLING_DIR / "infra" / "database" / "models.py"
        assert path.is_file(), f"Missing: {path}"

    def test_database_repositories_in_canonical_location(self):
        path = BILLING_DIR / "infra" / "database" / "repositories.py"
        assert path.is_file(), f"Missing: {path}"

    def test_database_mappers_in_canonical_location(self):
        path = BILLING_DIR / "infra" / "database" / "mappers.py"
        assert path.is_file(), f"Missing: {path}"

    def test_old_models_path_removed(self):
        path = BILLING_DIR / "infra" / "models.py"
        assert not path.exists(), f"Old path should be removed: {path}"

    def test_old_repositories_path_removed(self):
        path = BILLING_DIR / "infra" / "repositories.py"
        assert not path.exists(), f"Old path should be removed: {path}"

    def test_old_mappers_path_removed(self):
        path = BILLING_DIR / "infra" / "mappers.py"
        assert not path.exists(), f"Old path should be removed: {path}"

    def test_database_init_exports_models(self):
        path = BILLING_DIR / "infra" / "database" / "__init__.py"
        assert path.is_file()
        content = path.read_text(encoding="utf-8")
        assert "PlanModel" in content
        assert "CustomerModel" in content
        assert "SubscriptionModel" in content
        assert "PaymentEventModel" in content
        assert "OutboxEventModel" in content
        assert "InboxEventModel" in content

    def test_database_init_exports_repositories(self):
        path = BILLING_DIR / "infra" / "database" / "__init__.py"
        content = path.read_text(encoding="utf-8")
        assert "SQLAlchemyPlanRepository" in content
        assert "SQLAlchemyCustomerRepository" in content
        assert "SQLAlchemySubscriptionRepository" in content
        assert "SQLAlchemyPaymentEventRepository" in content
        assert "SQLAlchemyOutboxEventWriter" in content
