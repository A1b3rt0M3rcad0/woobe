from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[5]
BILLING_DIR = PROJECT_ROOT / "src" / "modules" / "billing"
UOW_FILE = BILLING_DIR / "infra" / "database" / "unit_of_work.py"
COMPOSERS_DIR = BILLING_DIR / "application" / "composers"


class TestBillingUnitOfWork:
    def test_uow_file_exists(self):
        assert UOW_FILE.is_file(), f"BillingUnitOfWork file missing: {UOW_FILE}"

    def test_uow_class_name(self):
        content = UOW_FILE.read_text(encoding="utf-8")
        assert "class BillingUnitOfWork" in content

    def test_uow_extends_unit_of_work(self):
        content = UOW_FILE.read_text(encoding="utf-8")
        assert "UnitOfWork" in content

    def test_uow_has_plans_property(self):
        content = UOW_FILE.read_text(encoding="utf-8")
        assert "def plans" in content
        assert "SQLAlchemyPlanRepository" in content

    def test_uow_has_customers_property(self):
        content = UOW_FILE.read_text(encoding="utf-8")
        assert "def customers" in content
        assert "SQLAlchemyCustomerRepository" in content

    def test_uow_has_subscriptions_property(self):
        content = UOW_FILE.read_text(encoding="utf-8")
        assert "def subscriptions" in content
        assert "SQLAlchemySubscriptionRepository" in content

    def test_uow_has_payment_events_property(self):
        content = UOW_FILE.read_text(encoding="utf-8")
        assert "def payment_events" in content
        assert "SQLAlchemyPaymentEventRepository" in content

    def test_uow_has_outbox_property(self):
        content = UOW_FILE.read_text(encoding="utf-8")
        assert "def outbox" in content
        assert "SQLAlchemyOutboxEventWriter" in content

    def test_uow_has_commit_and_rollback(self):
        content = UOW_FILE.read_text(encoding="utf-8")
        assert "async def commit" in content
        assert "async def rollback" in content

    def test_uow_has_aenter_aexit(self):
        content = UOW_FILE.read_text(encoding="utf-8")
        assert "__aenter__" in content
        assert "__aexit__" in content

    def test_uow_reinitializes_none_on_exit(self):
        content = UOW_FILE.read_text(encoding="utf-8")
        assert "self._plans = None" in content
        assert "self._customers = None" in content
        assert "self._subscriptions = None" in content
        assert "self._payment_events = None" in content
        assert "self._outbox = None" in content

    def test_no_composer_imports_postgres_unit_of_work(self):
        for py_file in sorted(COMPOSERS_DIR.iterdir()):
            if py_file.suffix != ".py" or py_file.name.startswith("__"):
                continue
            source = py_file.read_text(encoding="utf-8")
            assert "PostgresUnitOfWork" not in source, (
                f"{py_file.name} still imports PostgresUnitOfWork"
            )

    def test_all_composers_import_billing_unit_of_work(self):
        for py_file in sorted(COMPOSERS_DIR.iterdir()):
            if py_file.suffix != ".py" or py_file.name.startswith("__"):
                continue
            source = py_file.read_text(encoding="utf-8")
            assert "BillingUnitOfWork" in source, (
                f"{py_file.name} does not import BillingUnitOfWork"
            )
