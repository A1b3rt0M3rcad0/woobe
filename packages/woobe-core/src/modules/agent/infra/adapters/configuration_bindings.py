"""Agent-owned interpretation of configuration dependencies."""
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


def provider_dependencies(credential, *, base_url=None, impact=()):
    authentication = getattr(credential, "authentication", None)
    if authentication is None:
        return []
    compiled = compile_authentication(authentication)
    destination = provider_destination(credential, base_url)
    return [ConfigurationDependency(credential.project_id, "provider_credential", credential.id,
        str(credential.binding_revision), "/authentication/fields/" + field,
        reference["key"], destination, impact=impact)
        for field, reference in compiled["fields"].items()]
