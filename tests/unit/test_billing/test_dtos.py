from uuid import UUID

from pydantic import ValidationError
import pytest

from modules.billing.service.dtos import (
    CreatePlanInput,
    CreatePlanOutput,
    CreateCustomerInput,
    CreateCustomerOutput,
    CreateSubscriptionInput,
    CreateSubscriptionOutput,
    CreatePaymentEventInput,
    CreatePaymentEventOutput,
)


class TestCreatePlanInput:
    def test_valid(self):
        dto = CreatePlanInput(code="pro", name="Pro", price_usd=29.99)
        assert dto.code == "pro"
        assert dto.price_usd == 29.99
        assert dto.billing_interval == "monthly"
        assert dto.status == "active"

    def test_missing_required(self):
        with pytest.raises(ValidationError):
            CreatePlanInput()


class TestCreatePlanOutput:
    def test_valid(self):
        uid = UUID("00000000-0000-0000-0000-000000000001")
        dto = CreatePlanOutput(plan_id=uid)
        assert dto.plan_id == uid


class TestCreateCustomerInput:
    def test_valid(self):
        dto = CreateCustomerInput(
            organization_id=UUID("00000000-0000-0000-0000-000000000001"),
        )
        assert dto.provider == "custom"
        assert dto.email == ""

    def test_missing_organization_id(self):
        with pytest.raises(ValidationError):
            CreateCustomerInput()


class TestCreateCustomerOutput:
    def test_valid(self):
        uid = UUID("00000000-0000-0000-0000-000000000001")
        dto = CreateCustomerOutput(customer_id=uid)
        assert dto.customer_id == uid


class TestCreateSubscriptionInput:
    def test_valid(self):
        dto = CreateSubscriptionInput(
            organization_id=UUID("00000000-0000-0000-0000-000000000001"),
            customer_id=UUID("00000000-0000-0000-0000-000000000002"),
            plan_id=UUID("00000000-0000-0000-0000-000000000003"),
        )
        assert dto.provider == "custom"
        assert dto.status == "active"

    def test_missing_required(self):
        with pytest.raises(ValidationError):
            CreateSubscriptionInput()


class TestCreateSubscriptionOutput:
    def test_valid(self):
        uid = UUID("00000000-0000-0000-0000-000000000001")
        dto = CreateSubscriptionOutput(subscription_id=uid)
        assert dto.subscription_id == uid


class TestCreatePaymentEventInput:
    def test_valid(self):
        dto = CreatePaymentEventInput(
            provider="stripe",
            provider_event_id="evt_001",
            event_type="invoice.paid",
        )
        assert dto.provider == "stripe"
        assert dto.subscription_id is None

    def test_missing_required(self):
        with pytest.raises(ValidationError):
            CreatePaymentEventInput()


class TestCreatePaymentEventOutput:
    def test_valid(self):
        uid = UUID("00000000-0000-0000-0000-000000000001")
        dto = CreatePaymentEventOutput(event_id=uid)
        assert dto.event_id == uid
