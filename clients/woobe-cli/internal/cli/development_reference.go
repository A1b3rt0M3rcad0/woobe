package cli

import (
	"os"
	"strings"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
)

// Native UUID operations stay independent from local configuration. Only an
// explicit alias or filesystem reference opts into development resolution.
func (a *App) nativeReference(parameter, value string) (string, error) {
	kind := map[string]string{"agent_id": "Agent", "network_id": "Network", "tool_id": "Tool", "provider_model_id": "Model", "credential_id": "Provider", "skill_version_id": "Skill", "skill_id": "Skill", "collection_id": "Knowledge", "snapshot_id": "Knowledge", "surface_id": "Surface", "prompt_id": "Prompt", "contract_id": "Contract"}[parameter]
	if kind == "" || (!strings.HasPrefix(value, "@") && !strings.ContainsAny(value, "/\\") && value != ".") {
		return value, nil
	}
	c, err := a.developmentConfig(true)
	if err != nil {
		return "", err
	}
	if a.ContextName == "" && os.Getenv("WOOBE_CONTEXT") == "" && c.Context != "" {
		a.ContextName = c.Context
	}
	connection, err := a.resolve()
	if err != nil {
		return "", err
	}
	state, err := c.ReadState(strings.TrimRight(connection.APIURL, "/"), connection.Workspace, connection.Project)
	if err != nil {
		return "", output.New(2, err.Error())
	}
	resource, err := developmentReference(c, state, strings.ToLower(kind), value, "")
	if err != nil {
		return "", output.New(2, "Reference is not registered for "+kind)
	}
	binding := state.Bindings[resource.UID]
	id := binding.ResourceID
	if parameter == "skill_id" || parameter == "collection_id" {
		id = binding.Identifiers[parameter]
	}
	if kind == "Provider" {
		id = state.Credentials[resource.Key]
	}
	if id == "" {
		return "", output.New(2, "Local resource has no native binding in this connection and Project; create or push it first")
	}
	return id, nil
}
