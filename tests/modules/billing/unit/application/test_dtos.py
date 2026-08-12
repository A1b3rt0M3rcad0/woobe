from datetime import datetime, timezone
from uuid import uuid4

from editions.cloud.billing.application.dtos.billing_dtos import (
    CreateCustomerInput,
    CreateCustomerOutput,
    CreatePaymentEventInput,
    CreatePaymentEventOutput,
    CreatePlanInput,
    CreatePlanOutput,
    CreateSubscriptionInput,
    CreateSubscriptionOutput,
    GetOrganizationSubscriptionOutput,
    ListActivePlansOutput,
)


class TestCreatePlanInput:
    def test_valid_input(self):
        dto = CreatePlanInput(code="pro", name="Professional", price_usd=29.99)
        assert dto.code == "pro"
        assert dto.price_usd == 29.99


class TestCreatePlanOutput:
    def test_valid_output(self):
        dto = CreatePlanOutput(plan_id=uuid4())
        assert dto.plan_id is not None


class TestCreateCustomerInput:
    def test_valid_input(self):
        dto = CreateCustomerInput(organization_id=uuid4())
        assert dto.provider == "custom"


class TestCreateCustomerOutput:
    def test_valid_output(self):
        dto = CreateCustomerOutput(customer_id=uuid4())
        assert dto.customer_id is not None


class TestCreateSubscriptionInput:
    def test_valid_input(self):
        dto = CreateSubscriptionInput(organization_id=uuid4(), customer_id=uuid4(), plan_id=uuid4())
        assert dto.status == "active"


class TestCreateSubscriptionOutput:
    def test_valid_output(self):
        dto = CreateSubscriptionOutput(subscription_id=uuid4())
        assert dto.subscription_id is not None


class TestCreatePaymentEventInput:
    def test_valid_input(self):
        dto = CreatePaymentEventInput(provider="stripe", provider_event_id="evt_123", event_type="invoice.paid")
        assert dto.provider == "stripe"


class TestCreatePaymentEventOutput:
    def test_valid_output(self):
        dto = CreatePaymentEventOutput(event_id=uuid4())
        assert dto.event_id is not None


class TestListActivePlansOutput:
    def test_valid_output(self):
        dto = ListActivePlansOutput(id=uuid4(), code="pro", name="Pro", price_usd=29.99, status="active")
        assert dto.code == "pro"


class TestGetOrganizationSubscriptionOutput:
    def test_valid_output(self):
        now = datetime.now(timezone.utc)
        dto = GetOrganizationSubscriptionOutput(
            id=uuid4(), organization_id=uuid4(), plan_id=uuid4(),
            status="active", current_period_end=now,
        )
        assert dto.status == "active"
