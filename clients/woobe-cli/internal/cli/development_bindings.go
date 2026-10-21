package cli

import (
	"fmt"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/devworkspace"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packageapi"
)

// Validate the whole accepted closure before changing any local base. A later
// registry operation must never supply a generation for this operation's YAML.
func acceptedDevelopmentBindings(c *devworkspace.Config, state *devworkspace.State, bases map[string]devworkspace.Binding, approved map[string]packageapi.DevelopmentTarget, registry packageapi.Registry, operation string, sealed bool) (map[string]devworkspace.Binding, error) {
	fail := func() (map[string]devworkspace.Binding, error) {
		return nil, output.New(9, "Registry no longer proves this operation's accepted bindings; preserve the checkpoint and reconcile before another push")
	}
	kinds := map[string]string{}
	for _, resource := range c.Resources {
		kinds[resource.UID] = resource.Kind
	}
	expected := map[string]packageapi.DevelopmentTarget{}
	for _, target := range approved {
		if target.ResourceUID == "" || expected[target.ResourceUID].ResourceUID != "" || bases[target.ResourceUID].Base == nil {
			return fail()
		}
		expected[target.ResourceUID] = target
	}
	if len(expected) == 0 {
		return fail()
	}
	updates := map[string]devworkspace.Binding{}
	for _, remote := range registry.Resources {
		target, exists := expected[remote.ResourceUID]
		if !exists {
			continue
		}
		if _, duplicate := updates[remote.ResourceUID]; duplicate {
			return fail()
		}
		if remote.OperationID != operation || remote.ResourceID == "" || remote.Revision == nil || remote.Kind != kinds[remote.ResourceUID] || target.DefinitionDigest == "" || remote.DefinitionDigest != target.DefinitionDigest {
			return fail()
		}
		if (remote.Kind == "Agent" || remote.Kind == "Network") && target.ResourceID != "" && target.ResourceID != remote.ResourceID {
			return fail()
		}
		if sealed && (remote.GenerationScope != "accepted_native_phase" || remote.AcceptedRevision == nil || fmt.Sprint(remote.Revision) != fmt.Sprint(remote.AcceptedRevision) || remote.BindingStatus == "binding_incomplete") {
			return fail()
		}
		if target.SnapshotID != "" && sealed && (!remote.Frozen || remote.SnapshotID != target.SnapshotID) {
			return fail()
		}
		local := state.Bindings[remote.ResourceUID]
		local.ResourceID, local.Revision, local.Identifiers = remote.ResourceID, remote.Revision, remote.Identifiers
		local.Base, local.Supports = bases[remote.ResourceUID].Base, bases[remote.ResourceUID].Supports
		updates[remote.ResourceUID] = local
	}
	if len(updates) != len(expected) {
		return fail()
	}
	result := map[string]devworkspace.Binding{}
	for uid, binding := range state.Bindings {
		result[uid] = binding
	}
	for uid, binding := range updates {
		result[uid] = binding
	}
	// Providers have author identity but are lowered to credential requirements,
	// rather than independently materialized native registry resources.
	for uid, base := range bases {
		if kinds[uid] == "Provider" {
			local := result[uid]
			local.Base, local.Supports = base.Base, base.Supports
			result[uid] = local
		}
	}
	return result, nil
}
