package cli

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"path/filepath"
	"strings"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/devworkspace"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packageapi"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagecheckpoint"
)

func developmentCheckpointPath(c *devworkspace.Config, path string) error {
	relative, err := filepath.Rel(filepath.Join(c.RootPath(), ".state"), path)
	if err != nil || relative == "." || relative == ".." || strings.HasPrefix(relative, ".."+string(filepath.Separator)) || filepath.IsAbs(relative) {
		return output.New(2, "Pending checkpoint escapes the development state folder")
	}
	return nil
}

func readDevelopmentBases(c *devworkspace.Config, path string) (map[string]devworkspace.Binding, error) {
	data, err := c.ReadOperationalFile(path+".base.json", 16<<20)
	if err != nil {
		return nil, output.New(9, "Accepted local base is unavailable; preserve this operation for reconciliation")
	}
	decoder := json.NewDecoder(bytes.NewReader(data))
	decoder.UseNumber()
	decoder.DisallowUnknownFields()
	var bases map[string]devworkspace.Binding
	if decoder.Decode(&bases) != nil || bases == nil {
		return nil, output.New(9, "Invalid accepted local base")
	}
	var trailing any
	if decoder.Decode(&trailing) != io.EOF {
		return nil, output.New(9, "Accepted base contains trailing JSON")
	}
	return bases, nil
}

// Reconciliation deliberately does not load author descriptors. Broken YAML
// or edits made after a timeout must never prevent observing an accepted write.
// This path cannot upload, plan or apply another operation.
func (a *App) developmentReconcile(ctx context.Context, client *packageapi.Client, c *devworkspace.Config, state *devworkspace.State, resource *devworkspace.Resource) error {
	path := state.Pending[resource.UID]
	if path == "" {
		return a.emit(map[string]any{"resource": resource.Alias, "pending": false, "executed": false})
	}
	if err := developmentCheckpointPath(c, path); err != nil {
		return err
	}
	capabilities, err := developmentCapabilities(ctx, client)
	if err != nil {
		return err
	}
	store, err := packagecheckpoint.Open(path)
	if err != nil {
		return err
	}
	defer store.Close()
	cp, err := store.Read()
	if err != nil {
		return err
	}
	if cp.APIOrigin != client.Control.Base || cp.ProjectID != client.ProjectID || cp.PrincipalFingerprint != capabilities.PrincipalFingerprint {
		return output.New(3, "Checkpoint belongs to another destination or authority")
	}
	if cp.State == packagecheckpoint.Prepared {
		if !a.DryRun {
			delete(state.Pending, resource.UID)
			if err := c.WriteState(state); err != nil {
				return err
			}
		}
		return a.emit(map[string]any{"resource": resource.Alias, "state": "not_sent", "reconciled": !a.DryRun, "remote_executed": false})
	}
	var result packageapi.Operation
	if cp.OperationID != "" {
		result, err = client.Status(ctx, cp.OperationID)
	} else {
		result, err = client.Lookup(ctx, cp.IdempotencyKey)
	}
	if err != nil {
		return output.New(9, "Acceptance remains unknown; preserve this checkpoint and retry reconcile")
	}
	if a.DryRun {
		return a.emit(map[string]any{"operation": result, "executed": false, "pending": true})
	}
	if err = savePackageObservation(store, &cp, result); err != nil {
		return err
	}
	if !result.Terminal {
		return a.emit(map[string]any{"operation": result, "pending": true, "next_command": "woobe package status " + result.OperationID})
	}
	bases, err := readDevelopmentBases(c, path)
	if err != nil {
		return err
	}
	receipt, err := packageapi.LoadPlanReceipt(path + ".plan.json")
	if err != nil {
		return err
	}
	if receipt.Plan.PlanID != cp.PlanID || receipt.Plan.PlanDigest != cp.PlanDigest || receipt.Plan.RegistryID != c.RegistryID {
		return output.New(9, "Retained plan differs from accepted operation")
	}
	registry, err := client.Registry(ctx, c.RegistryID)
	if err != nil {
		return err
	}
	if result.State == "succeeded" {
		updated, err := acceptedDevelopmentBindings(c, state, bases, receipt.Plan.ResourceBindings, registry, result.OperationID, capabilities.ASaC.AcceptedBindingGenerations)
		if err != nil {
			return err
		}
		state.Bindings = updated
		delete(state.Pending, resource.UID)
		if err := c.WriteState(state); err != nil {
			return err
		}
		return a.emit(map[string]any{"resource": resource.Alias, "reconciled": true, "pending": false, "operation_id": result.OperationID, "state": result.State})
	}
	approved := map[string]packageapi.DevelopmentTarget{}
	for _, target := range receipt.Plan.ResourceBindings {
		approved[target.ResourceUID] = target
	}
	completed := map[string]bool{}
	for _, remote := range registry.Resources {
		target, exists := approved[remote.ResourceUID]
		if !exists || bases[remote.ResourceUID].Base == nil {
			continue
		}
		if target.DefinitionDigest == "" || remote.DefinitionDigest != target.DefinitionDigest || remote.OperationID != result.OperationID || (capabilities.ASaC.AcceptedBindingGenerations && (remote.GenerationScope != "accepted_native_phase" || remote.AcceptedRevision == nil || fmt.Sprint(remote.Revision) != fmt.Sprint(remote.AcceptedRevision))) {
			// A committed prepare phase owns the native root even if a later
			// phase failed. Retain identity without accepting the author base.
			if remote.OperationID == result.OperationID && remote.ResourceID != "" && (remote.Kind == "Agent" || remote.Kind == "Network") {
				local := state.Bindings[remote.ResourceUID]
				local.ResourceID, local.Revision = remote.ResourceID, remote.Revision
				state.Bindings[remote.ResourceUID] = local
			}
			continue
		}
		local := state.Bindings[remote.ResourceUID]
		if remote.ResourceID != "" {
			local.ResourceID = remote.ResourceID
		}
		local.Identifiers = remote.Identifiers
		local.Revision, local.Base, local.Supports = remote.Revision, bases[remote.ResourceUID].Base, bases[remote.ResourceUID].Supports
		state.Bindings[remote.ResourceUID] = local
		completed[remote.ResourceUID] = true
	}
	delete(state.Pending, resource.UID)
	if err = c.WriteState(state); err != nil {
		return err
	}
	return a.emit(map[string]any{"resource": resource.Alias, "operation_id": result.OperationID, "state": result.State, "reconciled": true, "completed_resources": len(completed), "pending": false, "next_command": "woobe " + strings.ToLower(resource.Kind) + " '@" + resource.Alias + "' diff"})
}
