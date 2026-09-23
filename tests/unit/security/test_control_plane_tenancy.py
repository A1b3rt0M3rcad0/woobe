from uuid import uuid4

from shared.security.tenancy import TenantAuthorizer


def test_access_project_id_is_treated_as_project_context() -> None:
    project_id = uuid4()

    identifiers = TenantAuthorizer._identifiers(
        {"access_project_id": project_id},
        {},
        {},
    )

    assert identifiers == [("access_project_id", project_id)]


def test_network_id_is_visible_to_tenant_authorization() -> None:
    network_id = uuid4()

    identifiers = TenantAuthorizer._identifiers(
        {"network_id": network_id},
        {},
        {},
    )

    assert identifiers == [("network_id", network_id)]
