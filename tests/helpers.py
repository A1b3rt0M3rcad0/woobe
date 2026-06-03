from datetime import datetime, UTC

import uuid6


_now = datetime.now(UTC)


def fake_uuid() -> str:
    return str(uuid6.uuid7())


# ── Identity factories ────────────────────────────────────────────

def make_user(email="user@test.com", password=b"$2b$12$hash"):
    from modules.identity.domain.entities import User
    return User(
        email=email,
        password=password,
        created_at=_now,
        updated_at=_now,
    )


def make_organization(name="TestOrg", slug="test-org"):
    from modules.identity.domain.entities import Organization
    return Organization(name=name, slug=slug, created_at=_now, updated_at=_now)


def make_organization_member(user_id=None, organization_id=None, role="member"):
    from modules.identity.domain.entities import OrganizationMember
    return OrganizationMember(
        user_id=user_id or uuid6.uuid7(),
        organization_id=organization_id or uuid6.uuid7(),
        role=role,
        joined_at=datetime.now(UTC),
        created_at=_now,
        updated_at=_now,
    )


# ── Core factories ────────────────────────────────────────────────

def make_project(organization_id=None, name="TestProject", slug="test-project"):
    from modules.core.domain.entities import Project
    return Project(
        organization_id=organization_id or uuid6.uuid7(),
        name=name,
        slug=slug,
        created_at=_now,
        updated_at=_now,
    )


def make_api_key(project_id=None, name="TestKey"):
    from modules.core.domain.entities import ApiKey
    return ApiKey(
        project_id=project_id or uuid6.uuid7(),
        name=name,
        key_prefix=b"rai_test12"[0:10].decode(),
        key_hash=b"hash",
        created_by_user_id=uuid6.uuid7(),
        created_at=_now,
    )


# ── AI factories ──────────────────────────────────────────────────

def make_agent(project_id=None, name="TestAgent"):
    from modules.ai.domain.entities import Agent
    from modules.ai.domain.enums import Provider
    return Agent(
        project_id=project_id or uuid6.uuid7(),
        name=name,
        model="gpt-4",
        provider=Provider.openai,
        created_at=_now,
        updated_at=_now,
    )


def make_provider_credential(project_id=None, provider=None):
    from modules.ai.domain.entities import ProviderCredential
    from modules.ai.domain.enums import Provider as ProviderEnum
    return ProviderCredential(
        project_id=project_id or uuid6.uuid7(),
        provider=provider or ProviderEnum.openai,
        name="default",
        encrypted_secret="encrypted:value",
        created_at=_now,
        updated_at=_now,
    )


# ── Knowledge factories ───────────────────────────────────────────

def make_document_collection(project_id=None, name="TestCollection"):
    from modules.knowledge.domain.entities import DocumentCollection
    return DocumentCollection(
        project_id=project_id or uuid6.uuid7(),
        name=name,
        created_at=_now,
        updated_at=_now,
    )


def make_document(project_id=None, collection_id=None):
    from modules.knowledge.domain.entities import Document
    return Document(
        project_id=project_id or uuid6.uuid7(),
        collection_id=collection_id or uuid6.uuid7(),
        title="test.pdf",
        file_name="test.pdf",
        content_type="application/pdf",
        size_bytes=1000,
        storage_key="test/test.pdf",
        created_at=_now,
        updated_at=_now,
    )


# ── Runtime factories ─────────────────────────────────────────────

def make_session(project_id=None, agent_id=None, external_session_id="ext-123"):
    from modules.runtime.domain.entities import Session
    return Session(
        project_id=project_id or uuid6.uuid7(),
        agent_id=agent_id or uuid6.uuid7(),
        external_session_id=external_session_id,
        created_at=_now,
        updated_at=_now,
    )


def make_message(session_id=None, role="user", content="Hello"):
    from modules.runtime.domain.entities import Message
    return Message(
        session_id=session_id or uuid6.uuid7(),
        role=role,
        content=content,
        created_at=_now,
        updated_at=_now,
    )


# ── Tools factories ───────────────────────────────────────────────

def make_tool(project_id=None, agent_id=None, name="http-tool"):
    from modules.tools.domain.entities import Tool
    return Tool(
        project_id=project_id or uuid6.uuid7(),
        agent_id=agent_id or uuid6.uuid7(),
        name=name,
        type="http_mcp",
        config={"url": "https://api.example.com"},
        created_at=_now,
        updated_at=_now,
    )


def make_secret(project_id=None, name="api-key"):
    from modules.tools.domain.entities import Secret
    return Secret(
        project_id=project_id or uuid6.uuid7(),
        name=name,
        type="bearer_token",
        encrypted_value="enc:value",
        created_at=_now,
        updated_at=_now,
    )


# ── Metering factories ────────────────────────────────────────────

def make_usage_event(project_id=None, agent_id=None):
    from modules.metering.domain.entities import UsageEvent
    return UsageEvent(
        project_id=project_id or uuid6.uuid7(),
        agent_id=agent_id or uuid6.uuid7(),
        event_type="llm_request",
        quantity=1,
        unit="request",
        created_at=_now,
        updated_at=_now,
    )


# ── Billing factories ─────────────────────────────────────────────

def make_plan(code="free", name="Free", price_usd=0.0):
    from modules.billing.domain.entities import Plan
    return Plan(code=code, name=name, price_usd=price_usd, created_at=_now, updated_at=_now)


def make_subscription(organization_id=None, plan_id=None):
    from modules.billing.domain.entities import Subscription
    return Subscription(
        organization_id=organization_id or uuid6.uuid7(),
        plan_id=plan_id or uuid6.uuid7(),
        provider="manual",
        provider_subscription_id="sub_123",
        created_at=_now,
        updated_at=_now,
    )


# ── Observability factories ───────────────────────────────────────

def make_trace(project_id=None, agent_id=None):
    from modules.observability.domain.entities import Trace
    return Trace(
        project_id=project_id or uuid6.uuid7(),
        agent_id=agent_id or uuid6.uuid7(),
        status="started",
        created_at=_now,
        updated_at=_now,
    )
