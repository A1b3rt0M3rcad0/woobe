package cli

import (
	"reflect"
	"testing"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/devworkspace"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packageapi"
)

func TestAcceptedBindingsRequireTheOriginalCompleteOperation(t *testing.T) {
	config := &devworkspace.Config{Resources: []devworkspace.Resource{{UID: "root", Kind: "Agent"}, {UID: "model", Kind: "Model"}}}
	state := &devworkspace.State{Bindings: map[string]devworkspace.Binding{"root": {ResourceID: "agent", Revision: 1, Base: map[string]any{"old": true}}}}
	original := state.Bindings["root"]
	bases := map[string]devworkspace.Binding{"root": {Base: map[string]any{"new": true}}, "model": {Base: map[string]any{"model": true}}}
	approved := map[string]packageapi.DevelopmentTarget{"agent": {ResourceUID: "root", ResourceID: "agent", DefinitionDigest: "root-digest"}, "model": {ResourceUID: "model", DefinitionDigest: "model-digest"}}
	good := []packageapi.RegistryBinding{{ResourceUID: "root", Kind: "Agent", ResourceID: "agent", OperationID: "original", DefinitionDigest: "root-digest", Revision: 7, AcceptedRevision: 7, CurrentRevision: 8, GenerationScope: "accepted_native_phase", BindingStatus: "resource_changed"}, {ResourceUID: "model", Kind: "Model", ResourceID: "new-model", OperationID: "original", DefinitionDigest: "model-digest", Revision: 3, AcceptedRevision: 3, GenerationScope: "accepted_native_phase", BindingStatus: "unchanged"}}
	cases := map[string]func([]packageapi.RegistryBinding) []packageapi.RegistryBinding{
		"later operation": func(v []packageapi.RegistryBinding) []packageapi.RegistryBinding {
			v[1].OperationID = "later"
			return v
		},
		"wrong definition": func(v []packageapi.RegistryBinding) []packageapi.RegistryBinding {
			v[1].DefinitionDigest = "other"
			return v
		},
		"missing dependency": func(v []packageapi.RegistryBinding) []packageapi.RegistryBinding { return v[:1] },
		"duplicate identity": func(v []packageapi.RegistryBinding) []packageapi.RegistryBinding { return append(v, v[1]) },
		"wrong native root": func(v []packageapi.RegistryBinding) []packageapi.RegistryBinding {
			v[0].ResourceID = "duplicate-agent"
			return v
		},
		"wrong kind": func(v []packageapi.RegistryBinding) []packageapi.RegistryBinding { v[1].Kind = "Tool"; return v },
		"unsealed phase": func(v []packageapi.RegistryBinding) []packageapi.RegistryBinding {
			v[1].GenerationScope = "unsealed_native_binding"
			return v
		},
		"current substituted": func(v []packageapi.RegistryBinding) []packageapi.RegistryBinding { v[0].Revision = 8; return v },
	}
	for name, mutate := range cases {
		t.Run(name, func(t *testing.T) {
			remote := mutate(append([]packageapi.RegistryBinding(nil), good...))
			if updated, err := acceptedDevelopmentBindings(config, state, bases, approved, packageapi.Registry{Resources: remote}, "original", true); err == nil || updated != nil {
				t.Fatal("accepted inconsistent evidence", updated, err)
			}
			if !reflect.DeepEqual(state.Bindings["root"], original) || len(state.Bindings) != 1 {
				t.Fatal("failed validation changed state", state)
			}
		})
	}
	updated, err := acceptedDevelopmentBindings(config, state, bases, approved, packageapi.Registry{Resources: good}, "original", true)
	if err != nil || updated["root"].Revision != 7 || updated["model"].ResourceID != "new-model" {
		t.Fatal("lost accepted generation or copy-on-write dependency", updated, err)
	}
	if !reflect.DeepEqual(state.Bindings["root"], original) {
		t.Fatal("validation mutated state")
	}
	// A frozen constituent is identified by its exact snapshot, not just Agent ID.
	frozenTarget := approved["agent"]
	frozenTarget.SnapshotID = "release-a"
	approved["agent"] = frozenTarget
	frozen := append([]packageapi.RegistryBinding(nil), good...)
	frozen[0].Frozen, frozen[0].SnapshotID = true, "release-b"
	if _, err := acceptedDevelopmentBindings(config, state, bases, approved, packageapi.Registry{Resources: frozen}, "original", true); err == nil {
		t.Fatal("accepted another frozen snapshot")
	}
	frozen[0].SnapshotID = "release-a"
	if _, err := acceptedDevelopmentBindings(config, state, bases, approved, packageapi.Registry{Resources: frozen}, "original", true); err != nil {
		t.Fatal("refused exact frozen snapshot", err)
	}
}
