"""Agent-owned interpretation of configuration dependencies."""
from uuid import UUID
from shared.contracts.project_configuration import ConfigurationDependency, ConfigurationError, compile_authentication


PROVIDER_DESTINATIONS = {
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com",
    "deepseek": "https://api.deepseek.com",
    "openrouter": "https://openrouter.ai/api/v1",
    "google": "https://generativelanguage.googleapis.com",
    "groq": "https://api.groq.com/openai/v1",
}


def provider_destination(credential, base_url=None):
    provider = credential.provider.value if hasattr(credential.provider, "value") else credential.provider
    destination = base_url or (credential.metadata or {}).get("base_url") or PROVIDER_DESTINATIONS.get(provider)
    if not destination:
        raise ConfigurationError("CONFIG_BINDING_INVALID")
    return str(destination)


def provider_dependencies(credential, *, base_url=None, impact=(), require_destination=True):
    authentication = getattr(credential, "authentication", None)
    if authentication is None:
        return []
    compiled = compile_authentication(authentication, allow_legacy=True)
    try:
        destination = provider_destination(credential, base_url)
    except ConfigurationError:
        if require_destination:
            raise
        # An incomplete authoring connection still retains its key references.
        # This empty destination is never used for admission or a usage grant.
        destination = ""
    return [ConfigurationDependency(credential.project_id, "provider_credential", credential.id,
        str(credential.binding_revision), "/authentication/fields/" + field,
        reference["key"], destination, impact=impact,
        legacy_alias_id=UUID(reference["alias_id"]) if reference["source"] == "legacy_configuration" else None)
        for field, reference in compiled["fields"].items()]
