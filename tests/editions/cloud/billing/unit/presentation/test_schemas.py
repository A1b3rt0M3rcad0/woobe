from uuid import uuid4

from editions.cloud.billing.presentation.schemas import (
    CreatePlanRequest,
    CreateSubscriptionRequest,
    PlanResponse,
    SubscriptionResponse,
)


class TestCreatePlanRequest:
    def test_valid_request(self):
        req = CreatePlanRequest(code="pro", name="Pro", price_usd=29.99)
        assert req.code == "pro"
        assert req.price_usd == 29.99


class TestPlanResponse:
    def test_valid_response(self):
        resp = PlanResponse(id=uuid4(), code="pro", name="Pro", price_usd=29.99, status="active")
        assert resp.status == "active"


class TestCreateSubscriptionRequest:
    def test_valid_request(self):
        req = CreateSubscriptionRequest(organization_id=uuid4(), customer_id=uuid4(), plan_id=uuid4())
        assert req.provider == "custom"


class TestSubscriptionResponse:
    def test_valid_response(self):
        resp = SubscriptionResponse(id=uuid4(), organization_id=uuid4(), plan_id=uuid4(), status="active")
        assert resp.status == "active"
