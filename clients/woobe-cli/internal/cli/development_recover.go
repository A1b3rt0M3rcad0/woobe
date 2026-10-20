package cli

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/devworkspace"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packageapi"
	"github.com/spf13/cobra"
)

func recoveredDevelopmentBindings(nodes []*devworkspace.Node, state *devworkspace.State, registry packageapi.Registry) (map[string]devworkspace.Binding, int, error) {
	fail := func() (map[string]devworkspace.Binding, int, error) {
		return nil, 0, output.New(9, "Registry cannot prove the complete accepted closure; no local bindings changed")
	}
	expected := map[string]devworkspace.Resource{}
	for _, node := range nodes {
		if node.Resource.Kind != "Provider" {
			expected[node.Resource.UID] = node.Resource
		}
	}
	found := map[string]devworkspace.Binding{}
	stale := 0
	for _, remote := range registry.Resources {
		resource, ok := expected[remote.ResourceUID]
		if !ok {
			continue
		}
		if _, duplicate := found[remote.ResourceUID]; duplicate {
			return fail()
		}
		if remote.Kind != resource.Kind || !packageUUID.MatchString(remote.ResourceID) || !packageUUID.MatchString(remote.OperationID) || !validPackagePrincipal(remote.DefinitionDigest) || remote.GenerationScope != "accepted_native_phase" || remote.AcceptedRevision == nil || remote.Revision == nil || fmt.Sprint(remote.Revision) != fmt.Sprint(remote.AcceptedRevision) {
			return fail()
		}
		if remote.BindingStatus != "unchanged" && remote.BindingStatus != "resource_changed" && remote.BindingStatus != "frozen_snapshot" {
			return fail()
		}
		if remote.Frozen != resource.Frozen {
			return fail()
		}
		snapshot := resource.SnapshotID
		if resource.Frozen && snapshot == "" {
			parts := strings.Split(resource.Path, "/")
			if len(parts) == 3 && parts[0] == "snapshots" && parts[1] == remote.ResourceID {
				snapshot = parts[2]
			}
		}
		if resource.Frozen && (!packageUUID.MatchString(snapshot) || remote.SnapshotID != snapshot || remote.SourceKind == "" || !remote.FrozenEvidenceRetained) {
			return fail()
		}
		existing := state.Bindings[resource.UID]
		if existing.ResourceID != "" && (existing.ResourceID != remote.ResourceID || resource.Frozen && existing.SnapshotID != remote.SnapshotID || existing.Revision != nil && fmt.Sprint(existing.Revision) != fmt.Sprint(remote.AcceptedRevision)) {
			return fail()
		}
		// No source/base claim can be reconstructed from identity-only evidence.
		existing.ResourceID, existing.Revision, existing.Identifiers = remote.ResourceID, remote.AcceptedRevision, remote.Identifiers
		if resource.Frozen {
			existing.SnapshotID, existing.SourceKind = remote.SnapshotID, remote.SourceKind
		}
		found[resource.UID] = existing
		if remote.BindingStatus == "resource_changed" {
			stale++
		}
	}
	if len(found) != len(expected) || len(found) == 0 {
		return fail()
	}
	result := map[string]devworkspace.Binding{}
	for uid, binding := range state.Bindings {
		result[uid] = binding
	}
	for uid, binding := range found {
		result[uid] = binding
	}
	return result, stale, nil
}

func (a *App) developmentBindingRecoveryCommands() {
	for _, kind := range []string{"agent", "network"} {
		command := &cobra.Command{Use: "bindings REFERENCE recover", Args: cobra.ExactArgs(2), Short: "Recover accepted native identities without claiming synchronized YAML", Long: "Reads the authoritative registry and validates every non-Provider dependency before atomically recovering private bindings. Preserves accepted generations, even when the native resource has changed. Does not restore an author base or provider credentials, edit YAML, select heads or change remote environments. Existing contradictory bindings and uncertain writes block recovery. Use --dry-run to inspect first.", Example: "woobe agent '@support' bindings recover --dry-run\nwoobe agent '@support' bindings recover", RunE: func(cmd *cobra.Command, args []string) error {
			if args[1] != "recover" {
				return output.New(2, "Use bindings REFERENCE recover")
			}
			c, err := a.developmentConfig(true)
			if err != nil {
				return err
			}
			unlock, err := c.Lock()
			if err != nil {
				return err
			}
			defer unlock()
			if a.ContextName == "" && os.Getenv("WOOBE_CONTEXT") == "" {
				a.ContextName = c.Context
			}
			control, err := a.client()
			if err != nil {
				return err
			}
			client, err := packageapi.New(control, a.Project)
			if err != nil {
				return err
			}
			state, err := c.ReadState(control.Base, a.Workspace, a.Project)
			if err != nil {
				return err
			}
			if len(state.Pending) != 0 {
				return output.New(9, "Reconcile pending package operations before binding recovery")
			}
			resource, err := developmentReference(c, state, kind, args[0], "")
			if err != nil {
				return err
			}
			graph, err := devworkspace.LoadGraph(c)
			if err != nil {
				return err
			}
			nodes, err := graph.Closure(resource.Key)
			if err != nil {
				return err
			}
			for _, node := range nodes {
				raw, readErr := c.ReadOperationalFile(asacPrivatePath(c, state, node.Resource.UID, "pending"), 16<<20)
				if os.IsNotExist(readErr) {
					continue
				}
				// Every reconciled ASaC writer seals its private checkpoint as
				// an empty object. Presence alone is not an uncertain write.
				var checkpoint map[string]json.RawMessage
				if readErr != nil || json.Unmarshal(raw, &checkpoint) != nil || checkpoint == nil || len(checkpoint) != 0 {
					return output.New(9, "Reconcile uncertain Draft operations before binding recovery")
				}
			}
			capabilities, err := developmentCapabilities(cmd.Context(), client)
			if err != nil {
				return err
			}
			if !capabilities.ASaC.AcceptedBindingGenerations {
				return output.New(9, "Server does not retain accepted native generations")
			}
			registry, err := client.Registry(cmd.Context(), c.RegistryID)
			if err != nil {
				return err
			}
			recovered, stale, err := recoveredDevelopmentBindings(nodes, state, registry)
			if err != nil {
				return err
			}
			if tracking, err := c.ReadTracking(*resource); err == nil && tracking.Origin.Target == state.API && tracking.Origin.Workspace == state.Workspace && tracking.Origin.Project == state.Project && tracking.Origin.ResourceID != recovered[resource.UID].ResourceID {
				return output.New(9, "Recovered root contradicts its durable origin")
			}
			if tracking, err := c.ReadTracking(*resource); err == nil && len(state.Requirements) == 0 {
				state.Requirements = tracking.Requirements
				if state.Requirements == nil {
					state.Requirements = map[string]any{}
				}
			}
			if !a.DryRun {
				state.Bindings = recovered
				if err := c.WriteState(state); err != nil {
					return err
				}
			}
			return a.emit(map[string]any{"resource": resource.Alias, "bindings_recovered": !a.DryRun, "accepted_bindings": len(nodes), "stale_bindings": stale, "author_base": "not_recovered", "credentials_restored": false, "remote_changed": false, "local_files_changed": false, "state_path": filepath.Base(c.StatePath(state.API, state.Workspace, state.Project))})
		}}
		a.group("develop " + kind).AddCommand(command)
	}
}
