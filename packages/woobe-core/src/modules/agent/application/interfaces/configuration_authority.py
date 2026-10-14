"""Owner-selected permissions applied inside every administrative transaction."""

def provider_binding_permissions(request):
    body = request.body if isinstance(request.body, dict) else {}
    permissions = []
    if "authentication" in body:
        permissions.append(("project:environment:bind", None))
    if "secret" in body:
        permissions.append(("project:environment:value:write", "provider:write"))
    return permissions


def provider_rotation_permissions(request):
    return [("project:environment:value:write", "provider:credential:rotate")]


def tool_binding_permissions(request):
    from shared.contracts.project_configuration import tool_configuration_permissions
    body = request.body if isinstance(request.body, dict) else {}
    return tool_configuration_permissions(body.get('config'),
        compatibility_update=request.path_params.get('tool_id') is not None)
