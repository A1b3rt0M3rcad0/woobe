package cli

import (
	"context"
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/devworkspace"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packageapi"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagebundle"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagecheckpoint"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagefmt"
	"github.com/spf13/cobra"
)

func (a *App) developmentCommands() {
	group := a.group("develop")
	for _, kind := range []string{"agent", "network"} {
		parent := &cobra.Command{Use: kind, Short: "Develop " + kind + " through local YAML and native Drafts"}
		group.AddCommand(parent)
		for _, action := range []string{"pull", "push", "create", "reconcile", "diff", "validate", "status"} {
			var localPath, alias, env, version string
			var remote bool
			var deadline time.Duration
			command := &cobra.Command{Use: action + " [REFERENCE]", Short: action + " a registered " + kind, Args: cobra.MaximumNArgs(1), Example: "woobe " + kind + " \"@support\" " + action, Long: "Resolve UUID, exact remote name, registered @alias or local path. pull downloads an environment, push always writes Draft. Within a linked artifact folder the reference is optional. JSON/YAML raw API commands remain available.", RunE: func(cmd *cobra.Command, args []string) error {
				if err := packageFlags(cmd, "yes"); err != nil {
					return err
				}
				if deadline <= 0 {
					return output.New(2, "Development deadline must be positive")
				}
				if action != "pull" {
					for _, flag := range []string{"env", "version", "alias"} {
						if cmd.Flags().Changed(flag) {
							return output.New(2, "--"+flag+" is only valid with pull")
						}
					}
				}
				c, err := a.developmentConfig(true)
				if err != nil {
					return err
				}
				unlock, err := c.Lock()
				if err != nil {
					return output.New(2, err.Error())
				}
				defer unlock()
				c, err = devworkspace.Load(c.File)
				if err != nil {
					return output.New(2, err.Error())
				}
				if a.ContextName == "" && os.Getenv("WOOBE_CONTEXT") == "" {
					a.ContextName = c.Context
				}
				reference := ""
				if len(args) > 0 {
					reference = args[0]
				}
				var graph *devworkspace.Graph
				if action != "reconcile" {
					graph, err = devworkspace.LoadGraph(c)
					if err != nil {
						return output.New(2, err.Error())
					}
				}
				ctx, cancel := context.WithTimeout(cmd.Context(), deadline)
				defer cancel()
				var client *packageapi.Client
				var state *devworkspace.State
				if action == "diff" || action == "status" || action == "validate" {
					connection, err := a.resolve()
					if err != nil {
						return err
					}
					state, err = c.ReadState(strings.TrimRight(connection.APIURL, "/"), a.Workspace, a.Project)
					if err != nil {
						return output.New(2, err.Error())
					}
				} else {
					control, err := a.client()
					if err != nil {
						return err
					}
					client, err = packageapi.New(control, a.Project)
					if err != nil {
						return err
					}
					state, err = c.ReadState(client.Control.Base, a.Workspace, client.ProjectID)
					if err != nil {
						return output.New(2, err.Error())
					}
				}
				resource, resolveErr := developmentReference(c, state, kind, reference, localPath)
				if action == "pull" {
					if _, err := developmentCapabilities(ctx, client); err != nil {
						return err
					}
					target := reference
					if resolveErr == nil {
						target = state.Bindings[resource.UID].ResourceID
						if target == "" {
							if tracking, err := c.ReadTracking(*resource); err == nil && tracking.Origin.Target == state.API && tracking.Origin.Workspace == state.Workspace && tracking.Origin.Project == state.Project {
								target = tracking.Origin.ResourceID
							}
						}
					}
					if target == "" || strings.HasPrefix(target, "@") {
						return output.New(2, "Pull needs an existing native UUID or exact name, or a bound alias")
					}
					if !cmd.Flags().Changed("env") {
						env = c.Defaults.PullEnvironment
					}
					if env != "draft" && env != "staging" && env != "release" && env != "production" {
						return output.New(2, "Environment must be draft, staging, release or production")
					}
					if (env == "release") != (version != "") {
						return output.New(2, "Only --env release requires --version")
					}
					targetID, err := a.packageTarget(ctx, client, kind, target)
					if err != nil {
						return err
					}
					receipt, bundle, err := developmentCapture(ctx, client, kind, targetID, env, version)
					if err != nil {
						return err
					}
					defer bundle.Close()
					captured := map[string]devworkspace.CapturedBinding{}
					for key, b := range receipt.ResourceBindings {
						captured[key] = devworkspace.CapturedBinding{ResourceUID: b.ResourceUID, Identifiers: b.Identifiers, OwnerAgentID: b.OwnerAgentID, Frozen: b.Frozen, ExportID: receipt.ExportID, ResourceID: b.ResourceID, Revision: b.Revision, SourceKind: b.SourceKind, SnapshotID: b.SnapshotID}
					}
					if a.DryRun {
						return a.emit(map[string]any{"executed": false, "target_id": targetID, "environment": env, "resources": len(bundle.Graph.Components), "destination": localPath})
					}
					imported, conflicts, err := c.ImportCapture(bundle, state, captured, receipt.CredentialBindings, alias, localPath)
					if err != nil {
						return output.New(2, err.Error())
					}
					if len(conflicts) > 0 {
						_ = a.emit(map[string]any{"conflicts": conflicts, "updated": false})
						return output.New(4, "Pull conflicts with local edits; resolve the listed paths")
					}
					if err = c.BootstrapTracking(*imported, state, env); err != nil {
						return output.New(2, err.Error())
					}
					return a.emit(map[string]any{"pulled": true, "resource": imported.Alias, "path": filepath.Join(c.RootPath(), imported.Path), "environment": env, "resources": len(bundle.Graph.Components), "next_command": "woobe " + kind + " " + fmt.Sprintf("%q", "@"+imported.Alias) + " push"})
				}
				if resolveErr != nil {
					return resolveErr
				}
				bound := state.Bindings[resource.UID]
				if action == "reconcile" {
					return a.developmentReconcile(ctx, client, c, state, resource)
				}
				if action == "create" && bound.ResourceID == "" {
					tracking, readErr := c.ReadTracking(*resource)
					if readErr != nil && !os.IsNotExist(readErr) {
						return output.New(9, readErr.Error())
					}
					if readErr == nil && tracking.Origin.Target == state.API && tracking.Origin.Workspace == state.Workspace && tracking.Origin.Project == state.Project && uuidReference(tracking.Origin.ResourceID) {
						return output.New(9, "Tracking origin identifies an existing native resource in this destination; recover its binding or select its isolated Draft instead of creating a duplicate. Clone explicitly with a new UID to create another resource")
					}
				}
				if action == "create" && bound.ResourceID != "" {
					return output.New(2, "Resource is already bound; use push to edit or clone to create another root")
				}
				if action == "validate" {
					bundle, _, err := graph.Compile(resource.Key, state.Requirements, state.Credentials)
					if err != nil {
						return output.New(2, err.Error())
					}
					defer bundle.Close()
					return a.emit(map[string]any{"valid": true, "resource": resource.Alias, "dependencies": len(bundle.Graph.Components) - 1, "authorization": "not_evaluated", "semantic_validation": "server_required", "executed": false})
				}
				if bound.ResourceID == "" && action != "create" && action != "diff" && action != "status" {
					return output.New(2, "Resource is not bound to this Woobe/Workspace/Project; pull it first or create explicitly")
				}
				if action == "diff" || action == "status" {
					changes, err := graph.ClosureChanges(*resource, state)
					if err != nil {
						return output.New(2, err.Error())
					}
					data := map[string]any{"resource": resource.Alias, "resource_uid": resource.UID, "native_id": bound.ResourceID, "changes": changes, "changed": len(changes) > 0, "scope": "local", "remote_status": "unverified", "write_environment": "draft"}
					if bound.Base == nil {
						data["author_base"] = "not_recovered"
					}
					tracking, trackErr := c.ReadTracking(*resource)
					if trackErr == nil {
						data["origin"] = tracking.Origin
						data["working_revision"] = tracking.Working
						data["tracking_environment"] = tracking.TrackedEnvironment
					} else if !os.IsNotExist(trackErr) {
						return output.New(9, trackErr.Error())
					} else {
						data["origin_status"] = "unknown_origin"
					}
					modified := len(changes) > 0
					if trackErr == nil && tracking.Working != "" {
						record, err := c.ReadRevision(*resource, tracking.Working)
						if err != nil {
							return output.New(9, err.Error())
						}
						digests, err := graph.DefinitionDigests(resource.Key)
						if err != nil {
							return output.New(2, err.Error())
						}
						modified = digests[resource.Key] != record.DefinitionDigest
						if devworkspace.SupportedDefinitionScope(record.DefinitionScope) {
							bundle, _, err := graph.Compile(resource.Key, tracking.Requirements, state.Credentials)
							if err != nil {
								return output.New(2, err.Error())
							}
							definition, _, err := devworkspace.PortableDefinition(bundle)
							bundle.Close()
							if err != nil {
								return output.New(2, err.Error())
							}
							modified = definition != record.DefinitionDigest
						}
						data["changed"] = modified
						data["comparison_base"] = "working_revision"
					}
					codes := []string{}
					if modified {
						codes = append(codes, "local_modified")
					}
					if remote {
						if bound.ResourceID == "" {
							return output.New(2, "Remote status needs a validated native binding")
						}
						draft, err := a.asacCurrent(cmd, kind, bound.ResourceID, "draft")
						if err != nil {
							return err
						}
						data["draft"] = draft
						if bound.Revision != nil && fmt.Sprint(bound.Revision) != fmt.Sprint(draft["draft_generation"]) {
							codes = append(codes, "draft_changed")
						}
						if trackErr == nil && (tracking.TrackedEnvironment == "production" || tracking.TrackedEnvironment == "staging") {
							selection, err := a.asacCurrent(cmd, kind, bound.ResourceID, tracking.TrackedEnvironment)
							if err != nil {
								return err
							}
							data["tracked_selection"] = selection
							if tracking.Origin.SnapshotID != "" && tracking.Origin.SnapshotID != selection["snapshot_id"] {
								codes = append(codes, "tracked_ref_changed")
							}
						}
						data["remote_status"] = "verified"
						data["scope"] = "local_and_remote"
					}
					data["status_codes"] = codes
					return a.emit(data)
				}
				if resource.Frozen {
					return output.New(2, "Frozen Network constituents cannot be pushed; pull the Agent Draft or clone it explicitly")
				}
				if localPath != "" {
					absolute, _ := filepath.Abs(localPath)
					expected, _ := c.ResourcePath(*resource)
					if absolute != expected {
						return output.New(2, "--path must identify the registered artifact; register another folder explicitly")
					}
				}
				bundle, bindings, err := graph.Compile(resource.Key, state.Requirements, state.Credentials)
				if err != nil {
					return output.New(2, err.Error())
				}
				defer bundle.Close()
				targets := map[string]packageapi.DevelopmentTarget{}
				for key := range bundle.Graph.Components {
					node := graph.Nodes[key]
					binding := state.Bindings[node.Resource.UID]
					target := packageapi.DevelopmentTarget{ResourceUID: node.Resource.UID, ResourceID: binding.ResourceID, ExpectedRevision: binding.Revision, SourceExportID: binding.ExportID, SourceComponent: binding.SourceComponent}
					if node.Resource.Frozen {
						target.SnapshotID = binding.SnapshotID
						target.SourceExportID = binding.ExportID
						target.SourceComponent = binding.SourceComponent
					}
					targets[key] = target
				}
				if a.DryRun {
					uploaded, err := client.Upload(ctx, bundle, false)
					if err != nil {
						return err
					}
					plan, err := client.Plan(ctx, packageapi.PlanRequest{InstallationMode: developmentInstallationMode(bindings), Mode: "sync", RegistryID: c.RegistryID, ResourceBindings: targets, UploadID: uploaded.UploadID, ArtifactDigest: bundle.ArtifactDigest, Bindings: bindings, Lifecycle: "draft"})
					if err != nil {
						return err
					}
					changes, err := graph.ClosureChanges(*resource, state)
					if err != nil {
						return output.New(2, err.Error())
					}
					return a.emit(map[string]any{"executed": false, "resource": resource.Alias, "name": packagefmt.Object(graph.Nodes[resource.Key].Document["metadata"])["name"], "environment": "draft", "changes": changes, "effects": plan.Effects, "plan_id": plan.PlanID, "plan_digest": plan.PlanDigest, "semantic_validation": "server_validated"})
				}
				acceptedBases, err := graph.AcceptedBases(bundle)
				if err != nil {
					return output.New(2, err.Error())
				}
				return a.developmentPush(ctx, client, c, state, resource, acceptedBases, bundle.ArtifactDigest, bindings, targets, func() (packageapi.Upload, error) { return client.Upload(ctx, bundle, false) })
			}}
			command.Flags().StringVar(&localPath, "path", "", "Registered artifact folder; pull defaults to the configured root")
			if action == "status" {
				command.Flags().BoolVar(&remote, "remote", false, "Observe Draft and the tracked environment; offline status never claims remote freshness")
			}
			command.Flags().StringVar(&alias, "alias", "", "Local typed alias for a newly registered pull")
			command.Flags().StringVar(&env, "env", "draft", "Pull source: draft, staging, release or production")
			command.Flags().StringVar(&version, "version", "", "Required immutable Release version when --env release")
			command.Flags().DurationVar(&deadline, "deadline", 5*time.Minute, "Total development operation deadline")
			parent.AddCommand(command)
		}
	}
	a.developmentBindingRecoveryCommands()
}
func developmentReference(c *devworkspace.Config, state *devworkspace.State, kind, reference, localPath string) (*devworkspace.Resource, error) {
	if reference != "" {
		if r, err := c.Resolve(kind, reference); err == nil {
			return r, nil
		}
		if state != nil {
			var originMatch *devworkspace.Resource
			for i := range c.Resources {
				r := &c.Resources[i]
				bound := state.Bindings[r.UID].ResourceID
				matches := bound == reference || packageUUID.MatchString(reference) && strings.EqualFold(bound, reference)
				if strings.EqualFold(r.Kind, kind) && matches && !r.Frozen {
					return r, nil
				}
				if strings.EqualFold(r.Kind, kind) && !r.Frozen && packageUUID.MatchString(reference) {
					tracking, err := c.ReadTracking(*r)
					if err == nil && strings.EqualFold(tracking.Origin.ResourceID, reference) && tracking.Origin.Target == state.API && tracking.Origin.Workspace == state.Workspace && tracking.Origin.Project == state.Project {
						if originMatch != nil {
							return nil, output.New(2, "Native UUID has multiple registered origins; use a typed alias")
						}
						originMatch = r
					}
				}
			}
			if originMatch != nil {
				return originMatch, nil
			}
		}
	}
	candidate := localPath
	if candidate == "" && reference != "" {
		candidate = reference
	}
	if candidate == "" {
		candidate, _ = os.Getwd()
	}
	absolute, err := filepath.Abs(candidate)
	if err != nil {
		return nil, err
	}
	var match *devworkspace.Resource
	for i := range c.Resources {
		r := &c.Resources[i]
		if !strings.EqualFold(r.Kind, kind) {
			continue
		}
		folder, _ := c.ResourcePath(*r)
		relative, err := filepath.Rel(folder, absolute)
		if err == nil && (relative == "." || !strings.HasPrefix(relative, ".."+string(filepath.Separator)) && relative != "..") {
			if match != nil {
				return nil, output.New(2, "Folder is linked to multiple artifacts; use a typed alias")
			}
			match = r
		}
	}
	if match != nil {
		return match, nil
	}
	return nil, output.New(2, "Resource is not registered; pull a native UUID/name first")
}
func developmentCapture(ctx context.Context, client *packageapi.Client, kind, id, env, version string) (packageapi.ExportReceipt, *packagebundle.Bundle, error) {
	targetKind := "Agent"
	if kind == "network" {
		targetKind = "Network"
	}
	schema := ""
	caps, err := client.Capabilities(ctx)
	if err != nil {
		return packageapi.ExportReceipt{}, nil, err
	}
	for _, scope := range caps.ASaC.DefinitionDigestScopes {
		if scope == devworkspace.ConfigurationDefinitionScope {
			schema = "2.0"
		}
	}
	receipt, err := client.Export(ctx, packageapi.ExportRequest{PackageSchemaVersion: schema, Kind: targetKind, TargetID: id, Source: &env, Knowledge: "portable", ReleaseVersion: version, Development: true})
	if err != nil {
		return receipt, nil, err
	}
	bundle, err := client.Download(ctx, receipt)
	return receipt, bundle, err
}

func (a *App) developmentPush(ctx context.Context, client *packageapi.Client, c *devworkspace.Config, state *devworkspace.State, resource *devworkspace.Resource, acceptedBases map[string]devworkspace.Binding, digest string, bindings map[string]any, targets map[string]packageapi.DevelopmentTarget, upload func() (packageapi.Upload, error)) error {
	// Reuse the existing pinned-plan import recovery machinery. Never issue another
	// Apply after an unknown outcome; this checkpoint is scoped to content+authority.
	identityBytes, _ := json.Marshal(map[string]any{"artifact_digest": digest, "targets": targets})
	requestDigest := fmt.Sprintf("%x", sha256.Sum256(identityBytes))
	attempt, err := randomPackageIdentity()
	if err != nil {
		return err
	}
	checkpoint := filepath.Join(c.RootPath(), ".state", "push-"+resource.UID+"-"+requestDigest+"-"+attempt+".json")
	if active := state.Pending[resource.UID]; active != "" {
		relative, err := filepath.Rel(filepath.Join(c.RootPath(), ".state"), active)
		if err != nil || relative == ".." || strings.HasPrefix(relative, ".."+string(filepath.Separator)) || filepath.IsAbs(relative) {
			return output.New(2, "Pending checkpoint escapes the development state folder")
		}
		checkpoint = active
	}
	capabilities, err := developmentCapabilities(ctx, client)
	if err != nil {
		return err
	}
	store, err := packagecheckpoint.Open(checkpoint)
	if err != nil {
		return err
	}
	defer store.Close()
	cp, readErr := store.Read()
	var result packageapi.Operation
	if readErr == nil && cp.State != packagecheckpoint.Prepared {
		acceptedBases, err = readDevelopmentBases(c, checkpoint)
		if err != nil {
			return err
		}
		if cp.APIOrigin != client.Control.Base || cp.ProjectID != client.ProjectID || cp.PrincipalFingerprint != capabilities.PrincipalFingerprint {
			return output.New(3, "Push checkpoint belongs to another destination")
		}
		if cp.OperationID != "" {
			result, err = client.Status(ctx, cp.OperationID)
		} else {
			result, err = client.Lookup(ctx, cp.IdempotencyKey)
		}
		if err != nil {
			return output.New(9, "Push acceptance remains unknown; reconcile this checkpoint before another push")
		}
	} else {
		if readErr != nil && !os.IsNotExist(readErr) {
			return readErr
		}
		var plan packageapi.Plan
		if readErr == nil {
			receipt, err := packageapi.LoadPlanReceipt(checkpoint + ".plan.json")
			if err != nil {
				return err
			}
			plan = receipt.Plan
			if cp.ArtifactDigest != digest {
				return output.New(2, "Prepared source changed; retain the approved source")
			}
			acceptedBases, err = readDevelopmentBases(c, checkpoint)
			if err != nil {
				return err
			}
		} else {
			uploaded, err := upload()
			if err != nil {
				return err
			}
			plan, err = client.Plan(ctx, packageapi.PlanRequest{InstallationMode: developmentInstallationMode(bindings), Mode: "sync", RegistryID: c.RegistryID, ResourceBindings: targets, UploadID: uploaded.UploadID, ArtifactDigest: digest, Bindings: bindings, Lifecycle: "draft"})
			if err != nil {
				return err
			}
			receipt := packageapi.PlanReceipt{Format: "woobe-package-plan-receipt", SchemaVersion: "1.0", PrincipalFingerprint: capabilities.PrincipalFingerprint, Plan: plan}
			if err = receipt.Save(checkpoint + ".plan.json"); err != nil {
				return err
			}
			identity, err := randomPackageIdentity()
			if err != nil {
				return err
			}
			now := time.Now().UTC()
			cp = packagecheckpoint.Checkpoint{Format: "woobe-package-checkpoint", SchemaVersion: "1.0", APIOrigin: plan.APIOrigin, ProjectID: plan.ProjectID, ArtifactDigest: digest, UploadID: plan.UploadID, PlanID: plan.PlanID, PlanDigest: plan.PlanDigest, IdempotencyKey: "development-" + identity, PrincipalFingerprint: capabilities.PrincipalFingerprint, RequestIdentity: identity, Lifecycle: "draft", State: packagecheckpoint.Prepared, CreatedAt: now, UpdatedAt: now}
			data, _ := json.Marshal(acceptedBases)
			if err = c.WriteOperationalFile(checkpoint+".base.json", data); err != nil {
				return err
			}
			if err = store.Save(cp); err != nil {
				return err
			}
		}
		if cp.PrincipalFingerprint != capabilities.PrincipalFingerprint {
			return output.New(3, "Push checkpoint belongs to another authority")
		}
		if state.Pending == nil {
			state.Pending = map[string]string{}
		}
		state.Pending[resource.UID] = checkpoint
		if err = c.WriteState(state); err != nil {
			return err
		}
		if err = cp.Move(packagecheckpoint.RequestInFlight); err != nil {
			return err
		}
		if err = store.Save(cp); err != nil {
			return err
		}
		result, err = client.Apply(ctx, cp.IdempotencyKey, packageapi.ApplyRequest{InstallationMode: plan.InstallationMode, PlanID: plan.PlanID, PlanDigest: plan.PlanDigest, UploadID: plan.UploadID, ArtifactDigest: digest, Bindings: plan.Bindings, ProtectedBindings: map[string]string{}, Lifecycle: "draft", ReleaseNotes: plan.ReleaseNotes, Reason: plan.Reason})
		if err != nil {
			_ = cp.Move(packagecheckpoint.OutcomeUnknown)
			_ = store.Save(cp)
			return output.New(9, "Push was sent once; reconcile the retained checkpoint before another operation")
		}
	}
	if err = savePackageObservation(store, &cp, result); err != nil {
		return err
	}
	result, err = client.Wait(ctx, result, func(next packageapi.Operation) error { return savePackageObservation(store, &cp, next) })
	if err != nil || result.State != "succeeded" {
		a.packageCheckpointPath = checkpoint
		if err == nil && result.Terminal && result.State != "succeeded" {
			return &packageOperationFailure{result, output.New(7, "Development write did not complete; run woobe "+strings.ToLower(resource.Kind)+" '@"+resource.Alias+"' reconcile")}
		}
		return a.emitPackageOperation(result, err)
	}
	recovered, err := client.Registry(ctx, c.RegistryID)
	if err != nil {
		return err
	}
	receipt, err := packageapi.LoadPlanReceipt(checkpoint + ".plan.json")
	if err != nil {
		return err
	}
	if receipt.Plan.PlanID != cp.PlanID || receipt.Plan.PlanDigest != cp.PlanDigest || receipt.Plan.RegistryID != c.RegistryID {
		return output.New(9, "Retained plan differs from accepted operation")
	}
	updated, err := acceptedDevelopmentBindings(c, state, acceptedBases, receipt.Plan.ResourceBindings, recovered, result.OperationID, capabilities.ASaC.AcceptedBindingGenerations)
	if err != nil {
		return err
	}
	state.Bindings = updated
	delete(state.Pending, resource.UID)
	if err = c.WriteState(state); err != nil {
		return err
	}
	return a.emit(map[string]any{"pushed": true, "resource": resource.Alias, "environment": "draft", "operation_id": result.OperationID, "configuration_ready": result.ConfigurationReady, "execution_ready": result.ExecutionReady, "resources": len(targets)})
}

func developmentCapabilities(ctx context.Context, client *packageapi.Client) (packageapi.Capabilities, error) {
	capabilities, err := client.Capabilities(ctx)
	if err != nil {
		return capabilities, err
	}
	if err := packageCatalogCompatibility(client, capabilities); err != nil {
		return capabilities, err
	}
	if !validPackagePrincipal(capabilities.PrincipalFingerprint) {
		return capabilities, output.New(9, "Server returned an invalid Package authority fingerprint; run woobe package doctor to inspect the selected API")
	}
	for _, operation := range capabilities.SupportedOperations {
		if operation == "sync" {
			return capabilities, nil
		}
	}
	return capabilities, output.New(9, "This server does not support managed development; upgrade Woobe or use standalone package export/import")
}

func developmentInstallationMode(bindings map[string]any) string {
	if bindings["schema_version"] == "2.0" {
		return "structural"
	}
	return ""
}
