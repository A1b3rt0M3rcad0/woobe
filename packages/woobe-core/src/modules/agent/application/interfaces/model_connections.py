from copy import deepcopy


def fallback_connection_settings(agent):
    """Keep fallback endpoint selection separate from the primary Model endpoint."""
    settings = deepcopy(agent.settings or {})
    snapshot = settings.get("fallback_model_spec") or {}
    settings["base_url"] = (snapshot.get("metadata") or {}).get("base_url")
    settings["model"] = agent.fallback_model
    return settings
