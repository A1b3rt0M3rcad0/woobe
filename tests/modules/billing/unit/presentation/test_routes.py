from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[5]
ROUTES_FILE = PROJECT_ROOT / "src" / "editions" / "cloud" / "billing" / "presentation" / "routes.py"


class TestBillingRoutes:
    def test_routes_file_exists(self):
        assert ROUTES_FILE.is_file()

    def test_router_prefix_is_billing(self):
        content = ROUTES_FILE.read_text(encoding="utf-8")
        assert 'prefix="/billing"' in content or 'prefix = "/billing"' in content

    def test_has_create_plan_route(self):
        content = ROUTES_FILE.read_text(encoding="utf-8")
        assert 'post("/plans"' in content or 'post("/plans")' in content

    def test_has_list_plans_route(self):
        content = ROUTES_FILE.read_text(encoding="utf-8")
        assert 'get("/plans"' in content or 'get("/plans")' in content

    def test_has_create_subscription_route(self):
        content = ROUTES_FILE.read_text(encoding="utf-8")
        assert 'post("/subscriptions"' in content or 'post("/subscriptions")' in content

    def test_routes_import_from_composers(self):
        content = ROUTES_FILE.read_text(encoding="utf-8")
        assert "composers" in content

    def test_routes_use_request_adapter(self):
        content = ROUTES_FILE.read_text(encoding="utf-8")
        assert "request_adapter" in content
