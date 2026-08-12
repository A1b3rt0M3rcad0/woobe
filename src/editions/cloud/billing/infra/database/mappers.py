from editions.cloud.billing.domain.entities import Customer, PaymentEvent, Plan, Subscription
from editions.cloud.billing.domain.enums import (
    BillingInterval,
    BillingProvider,
    PaymentEventStatus,
    PlanStatus,
    SubscriptionStatus,
)
from editions.cloud.billing.infra.database.models import (
    CustomerModel,
    PaymentEventModel,
    PlanModel,
    SubscriptionModel,
)


def plan_entity_to_model(entity: Plan) -> PlanModel:
    return PlanModel(
        id=entity.id,
        code=entity.code,
        name=entity.name,
        price_usd=entity.price_usd,
        billing_interval=entity.billing_interval.value if isinstance(entity.billing_interval, BillingInterval) else entity.billing_interval,
        limits=entity.limits,
        status=entity.status.value if isinstance(entity.status, PlanStatus) else entity.status,
    )


def plan_model_to_entity(model: PlanModel) -> Plan:
    return Plan(
        id=model.id,
        code=model.code,
        name=model.name,
        price_usd=model.price_usd,
        billing_interval=BillingInterval(model.billing_interval),
        limits=model.limits,
        status=PlanStatus(model.status),
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def customer_entity_to_model(entity: Customer) -> CustomerModel:
    return CustomerModel(
        id=entity.id,
        organization_id=entity.organization_id,
        provider=entity.provider.value if isinstance(entity.provider, BillingProvider) else entity.provider,
        provider_customer_id=entity.provider_customer_id,
        email=entity.email,
        data=entity.data,
    )


def customer_model_to_entity(model: CustomerModel) -> Customer:
    return Customer(
        id=model.id,
        organization_id=model.organization_id,
        provider=BillingProvider(model.provider),
        provider_customer_id=model.provider_customer_id,
        email=model.email,
        data=model.data,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def subscription_entity_to_model(entity: Subscription) -> SubscriptionModel:
    return SubscriptionModel(
        id=entity.id,
        organization_id=entity.organization_id,
        customer_id=entity.customer_id,
        plan_id=entity.plan_id,
        provider=entity.provider.value if isinstance(entity.provider, BillingProvider) else entity.provider,
        provider_subscription_id=entity.provider_subscription_id,
        status=entity.status.value if isinstance(entity.status, SubscriptionStatus) else entity.status,
        current_period_start=entity.current_period_start,
        current_period_end=entity.current_period_end,
        trial_ends_at=entity.trial_ends_at,
        canceled_at=entity.canceled_at,
    )


def subscription_model_to_entity(model: SubscriptionModel) -> Subscription:
    return Subscription(
        id=model.id,
        organization_id=model.organization_id,
        customer_id=model.customer_id,
        plan_id=model.plan_id,
        provider=BillingProvider(model.provider),
        provider_subscription_id=model.provider_subscription_id,
        status=SubscriptionStatus(model.status),
        current_period_start=model.current_period_start,
        current_period_end=model.current_period_end,
        trial_ends_at=model.trial_ends_at,
        canceled_at=model.canceled_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def payment_event_entity_to_model(entity: PaymentEvent) -> PaymentEventModel:
    return PaymentEventModel(
        id=entity.id,
        provider=entity.provider.value if isinstance(entity.provider, BillingProvider) else entity.provider,
        provider_event_id=entity.provider_event_id,
        event_type=entity.event_type,
        payload=entity.payload,
        status=entity.status.value if isinstance(entity.status, PaymentEventStatus) else entity.status,
        processed_at=entity.processed_at,
    )


def payment_event_model_to_entity(model: PaymentEventModel) -> PaymentEvent:
    return PaymentEvent(
        id=model.id,
        provider=BillingProvider(model.provider),
        provider_event_id=model.provider_event_id,
        event_type=model.event_type,
        payload=model.payload,
        status=PaymentEventStatus(model.status),
        processed_at=model.processed_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )
