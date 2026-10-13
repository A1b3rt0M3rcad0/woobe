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
    body = request.body if isinstance(request.body, dict) else {}
    config = body.get("config")
    if isinstance(config, dict) and "authentication" in config:
        return [("project:environment:bind", None)]
    return []
