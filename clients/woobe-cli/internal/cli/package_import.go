package cli

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"os"
	"time"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packageapi"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagecheckpoint"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagefmt"
	"github.com/spf13/cobra"
)

func randomPackageIdentity() (string, error) {
	value := make([]byte, 32)
	if _, err := rand.Read(value); err != nil {
		return "", err
	}
	return hex.EncodeToString(value), nil
}

func savePackageObservation(store *packagecheckpoint.Store, checkpoint *packagecheckpoint.Checkpoint, result packageapi.Operation) error {
	if result.ArtifactDigest != checkpoint.ArtifactDigest || result.ProjectID != checkpoint.ProjectID || checkpoint.OperationID != "" && result.OperationID != checkpoint.OperationID || result.Revision < checkpoint.LastRevision {
		return output.New(9, "Package observation changed accepted identity")
	}
	checkpoint.OperationID, checkpoint.LastRevision, checkpoint.LastRemoteState = result.OperationID, result.Revision, result.State
	if checkpoint.State == packagecheckpoint.RequestInFlight || checkpoint.State == packagecheckpoint.OutcomeUnknown {
		if err := checkpoint.Move(packagecheckpoint.Accepted); err != nil {
			return err
		}
		if err := store.Save(*checkpoint); err != nil {
			return err
		}
	}
	state := packagecheckpoint.Observing
	if result.Terminal {
		state = packagecheckpoint.Terminal
	}
	if err := checkpoint.Move(state); err != nil {
		return err
	}
	return store.Save(*checkpoint)
}

func (a *App) packageProtectedSnapshot(bindings map[string]any) (map[string]string, error) {
	result := map[string]string{}
	spec := packagefmt.Object(bindings["spec"])
	for _, group := range []string{"credentials", "project_environment", "secrets"} {
		for _, binding := range packagefmt.Object(spec[group]) {
			name, _ := packagefmt.Object(binding)["protected_ref"].(string)
			if name == "" {
				continue
			}
			if _, ok := result[name]; ok {
				continue
			}
			value, err := a.store().Get(name)
			if err != nil || value == "" {
				return nil, output.New(3, "Protected Package binding is unavailable")
			}
			result[name] = value
		}
	}
	return result, nil
}

func (a *App) packageImportCommands(group *cobra.Command) {
	var planPath, checkpointPath, bindingsPath, savePath, lifecycle, notes, reason string
	var shortcuts []string
	var locked, wait, structural bool
	var deadline time.Duration
	command := &cobra.Command{Use: "import [SOURCE]", Short: "Apply a pinned native Package plan with durable single-request recovery", Args: cobra.MaximumNArgs(1), RunE: func(cmd *cobra.Command, args []string) error {
		if err := packageFlags(cmd, "yes", "idempotency-key", "validate-body", "validate-parameters", "schema-sha256"); err != nil {
			return err
		}
		if (len(args) == 0) == (planPath == "") || deadline <= 0 {
			return output.New(2, "Import requires SOURCE or --plan-file and a positive wait timeout")
		}
		if planPath != "" && (bindingsPath != "" || len(shortcuts) > 0 || savePath != "" || locked || cmd.Flags().Changed("structural") || cmd.Flags().Changed("lifecycle") || notes != "" || reason != "") {
			return output.New(2, "A saved plan cannot be changed by import flags")
		}
		if err := packageLifecycle(lifecycle, notes, reason); err != nil {
			return err
		}
		if a.DryRun {
			if planPath != "" || checkpointPath != "" || savePath != "" || a.ValidateBody || a.ValidateParameters || a.IdempotencyKey != "" || wait {
				return output.New(2, "Offline dry-run cannot use remote plans, checkpoints, waits or schemas")
			}
			bundle, err := loadPackage(args[0], locked)
			if err != nil {
				return err
			}
			defer bundle.Close()
			if err = excludePackageOperationalFiles(args[0], bundle, bindingsPath); err != nil {
				return err
			}
			bindings, err := packagefmt.LoadBindings(bindingsPath, shortcuts, bundle.Graph)
			if err != nil {
				return packageError(err)
			}
			if _, err = packageInstallation(bindings, structural, lifecycle); err != nil {
				return err
			}
			return a.emit(map[string]any{"package_schema_version": bundle.Graph.Manifest["schema_version"], "structural": structural, "artifact_digest": bundle.ArtifactDigest, "inventory": bundle.Inventory, "bindings": bindings, "lifecycle": lifecycle, "executed": false, "authorization": "not_evaluated", "semantic_validation": "server_required"})
		}
		ctx, cancel := context.WithTimeout(cmd.Context(), deadline)
		defer cancel()
		if checkpointPath == "" {
			source := ""
			if len(args) > 0 {
				source = args[0]
			}
			var err error
			checkpointPath, err = a.automaticPackageCheckpoint(ctx, source, planPath, lifecycle)
			if err != nil {
				return err
			}
		}
		a.packageCheckpointPath = checkpointPath
		store, err := packagecheckpoint.Open(checkpointPath)
		if err != nil {
			return err
		}
		defer store.Close()
		cp, readErr := store.Read()
		if readErr != nil && !os.IsNotExist(readErr) {
			return readErr
		}
		var sequence int64
		var progressSecrets map[string]string
		client, err := a.packageClient(ctx, "apply")
		if err != nil {
			return err
		}
		capabilities, err := client.Capabilities(ctx)
		if err != nil {
			return err
		}
		if readErr == nil {
			if cp.APIOrigin != client.Control.Base || cp.ProjectID != client.ProjectID || cp.PrincipalFingerprint != capabilities.PrincipalFingerprint || a.IdempotencyKey != "" && cp.IdempotencyKey != a.IdempotencyKey {
				return output.New(3, "Package checkpoint belongs to different destination authority")
			}
			if cp.State != packagecheckpoint.Prepared {
				var result packageapi.Operation
				if cp.OperationID != "" {
					result, err = client.Status(ctx, cp.OperationID)
				} else {
					result, err = client.Lookup(ctx, cp.IdempotencyKey)
				}
				if err != nil {
					return &output.Error{Code: 9, Message: "Package acceptance remains unknown; reconcile the same checkpoint and key", Outcome: "unknown"}
				}
				if err = savePackageObservation(store, &cp, result); err != nil {
					return err
				}
				if wait {
					result, err = client.Wait(ctx, result, func(next packageapi.Operation) error {
						if err := savePackageObservation(store, &cp, next); err != nil {
							return err
						}
						return a.packageProgress(next, &sequence, progressSecrets)
					})
				}
				return a.emitPackageOperation(result, err)
			}
		}
		var receipt packageapi.PlanReceipt
		var schema map[string]any
		if a.ValidateBody || a.ValidateParameters {
			schema, err = a.loadServerSchema(ctx)
			if err != nil {
				return err
			}
		}
		if readErr == nil && planPath == "" {
			receipt, err = packageapi.LoadPlanReceipt(checkpointPath + ".plan.json")
			if err != nil {
				return err
			}
		} else if planPath != "" {
			receipt, err = packageapi.LoadPlanReceipt(planPath)
			if err != nil {
				return err
			}
		} else {
			bundle, e := loadPackage(args[0], locked)
			if e != nil {
				return e
			}
			defer bundle.Close()
			if e = excludePackageOperationalFiles(args[0], bundle, bindingsPath, savePath, checkpointPath, checkpointPath+".plan.json"); e != nil {
				return e
			}
			bindings, e := packagefmt.LoadBindings(bindingsPath, shortcuts, bundle.Graph)
			if e != nil {
				return packageError(e)
			}
			installationMode, e := packageInstallation(bindings, structural, lifecycle)
			if e != nil {
				return e
			}
			request := packageapi.PlanRequest{InstallationMode: installationMode, Mode: "create", UploadID: "00000000-0000-4000-8000-000000000000", ArtifactDigest: bundle.ArtifactDigest, Bindings: bindings, Lifecycle: lifecycle}
			if notes != "" {
				request.ReleaseNotes = &notes
			}
			if reason != "" {
				request.Reason = &reason
			}
			if schema != nil {
				if e = a.validatePackageRequest(schema, "POST", "/plan", map[string]string{"project_id": client.ProjectID}, nil, request); e != nil {
					return e
				}
			}
			upload, e := client.Upload(ctx, bundle, locked)
			if e != nil {
				return e
			}
			request.UploadID = upload.UploadID
			if schema != nil {
				if e = a.validatePackageRequest(schema, "POST", "/plan", map[string]string{"project_id": client.ProjectID}, nil, request); e != nil {
					return e
				}
			}
			plan, e := client.Plan(ctx, request)
			if e != nil {
				return e
			}
			receipt = packageapi.PlanReceipt{Format: "woobe-package-plan-receipt", SchemaVersion: "1.0", PrincipalFingerprint: capabilities.PrincipalFingerprint, Plan: plan}
			if e = receipt.Save(checkpointPath + ".plan.json"); e != nil {
				return e
			}
			if savePath != "" {
				if e = receipt.Save(savePath); e != nil {
					return e
				}
			}
		}
		plan := receipt.Plan
		if cmd.Flags().Changed("structural") && (plan.InstallationMode == "structural") != structural {
			return output.New(2, "Prepared installation mode differs from the approved plan")
		}
		if err := client.RequireSchema(ctx, plan.PackageSchemaVersion, plan.InstallationMode == "structural"); err != nil {
			return err
		}
		if readErr == nil && planPath == "" {
			bundle, err := loadPackage(args[0], locked)
			if err != nil {
				return err
			}
			defer bundle.Close()
			if bundle.ArtifactDigest != plan.ArtifactDigest {
				return output.New(2, "Prepared source differs from its approved artifact")
			}
			if bindingsPath != "" || len(shortcuts) > 0 {
				bindings, err := packagefmt.LoadBindings(bindingsPath, shortcuts, bundle.Graph)
				if err != nil {
					return packageError(err)
				}
				digest, err := packageapi.BindingsDigest(bindings)
				if err != nil || digest != plan.BindingsDigest {
					return output.New(2, "Prepared bindings differ from their approved identities")
				}
			}
			if cmd.Flags().Changed("lifecycle") && lifecycle != plan.Lifecycle || notes != "" && (plan.ReleaseNotes == nil || notes != *plan.ReleaseNotes) || reason != "" && (plan.Reason == nil || reason != *plan.Reason) {
				return output.New(2, "Prepared lifecycle or audit fields differ from the approved plan")
			}
		}
		if receipt.PrincipalFingerprint != capabilities.PrincipalFingerprint || plan.APIOrigin != client.Control.Base || plan.ProjectID != client.ProjectID {
			return output.New(3, "Approved plan belongs to different destination authority")
		}
		if readErr == nil {
			if cp.PlanID != plan.PlanID || cp.PlanDigest != plan.PlanDigest || cp.ArtifactDigest != plan.ArtifactDigest || cp.UploadID != plan.UploadID || cp.Lifecycle != plan.Lifecycle {
				return output.New(2, "Prepared checkpoint requires its original approved plan")
			}
		} else {
			identity, e := randomPackageIdentity()
			if e != nil {
				return e
			}
			key := a.IdempotencyKey
			if key == "" {
				key = "package-" + identity
			}
			now := time.Now().UTC()
			cp = packagecheckpoint.Checkpoint{Format: "woobe-package-checkpoint", SchemaVersion: "1.0", APIOrigin: plan.APIOrigin, ProjectID: plan.ProjectID, ArtifactDigest: plan.ArtifactDigest, UploadID: plan.UploadID, PlanID: plan.PlanID, PlanDigest: plan.PlanDigest, IdempotencyKey: key, PrincipalFingerprint: receipt.PrincipalFingerprint, RequestIdentity: identity, Lifecycle: plan.Lifecycle, State: packagecheckpoint.Prepared, CreatedAt: now, UpdatedAt: now}
			if e = store.Save(cp); e != nil {
				return e
			}
		}
		values, err := a.packageProtectedSnapshot(plan.Bindings)
		if err != nil {
			return err
		}
		progressSecrets = values
		request := packageapi.ApplyRequest{InstallationMode: plan.InstallationMode, PlanID: plan.PlanID, PlanDigest: plan.PlanDigest, UploadID: plan.UploadID, ArtifactDigest: plan.ArtifactDigest, Bindings: plan.Bindings, ProtectedBindings: values, Lifecycle: plan.Lifecycle, ReleaseNotes: plan.ReleaseNotes, Reason: plan.Reason}
		if schema != nil {
			if err = a.validatePackageRequest(schema, "POST", "/apply", map[string]string{"project_id": client.ProjectID}, nil, request); err != nil {
				return err
			}
		}
		if err = cp.Move(packagecheckpoint.RequestInFlight); err != nil {
			return err
		}
		if err = store.Save(cp); err != nil {
			return err
		}
		result, err := client.Apply(ctx, cp.IdempotencyKey, request)
		if err != nil {
			_ = cp.Move(packagecheckpoint.OutcomeUnknown)
			if e := store.Save(cp); e != nil {
				return output.New(9, "Could not persist Package outcome; reconcile the existing checkpoint")
			}
			failure := *output.Normalize(err)
			// Preserve definitive server rejection and central timeout/interruption
			// codes. The checkpoint still forbids sending Apply again: recovery
			// must reconcile the original identity even after a rejected request.
			if failure.Outcome != "rejected" {
				failure.Outcome = "unknown"
				if failure.Code != 8 && failure.Code != 130 {
					failure.Code = 9
				}
				failure.DomainCode = "PACKAGE_OUTCOME_UNKNOWN"
			}
			failure.Message = "Package Apply was sent once; reconcile the existing checkpoint before any further action"
			return &failure
		}
		if err = savePackageObservation(store, &cp, result); err != nil {
			return err
		}
		if err = a.packageProgress(result, &sequence, progressSecrets); err != nil {
			return err
		}
		if wait {
			result, err = client.Wait(ctx, result, func(next packageapi.Operation) error {
				if err := savePackageObservation(store, &cp, next); err != nil {
					return err
				}
				return a.packageProgress(next, &sequence, progressSecrets)
			})
		}
		// Provider text and identifiers are untrusted after protected resolution.
		encoded, _ := json.Marshal(result)
		_ = json.Unmarshal(scrubSecretJSON(encoded, values), &result)
		if err != nil {
			failure := output.Normalize(err)
			encoded, _ := json.Marshal(failure.Message)
			_ = json.Unmarshal(scrubSecretJSON(encoded, values), &failure.Message)
			err = failure
		}
		return a.emitPackageOperation(result, err)
	}}
	command.Flags().StringVar(&planPath, "plan-file", "", "Private approved plan receipt; exclusive with SOURCE")
	command.Flags().StringVar(&checkpointPath, "checkpoint", "", "Private checkpoint; defaults to CLI state and is reused for the same source/destination")
	command.Flags().StringVar(&bindingsPath, "bindings", "", "Destination bindings file")
	command.Flags().StringArrayVar(&shortcuts, "bind", nil, "Explicit reuse: credential.ALIAS=UUID or configuration.KEY=REMOTE_KEY (schema 2.0)")
	command.Flags().StringVar(&savePath, "save-plan", "", "Save approved private plan exclusively")
	command.Flags().StringVar(&lifecycle, "lifecycle", "draft", "Explicit destination lifecycle")
	command.Flags().StringVar(&notes, "release-notes", "", "Release audit description")
	command.Flags().StringVar(&reason, "reason", "", "Production activation reason")
	command.Flags().BoolVar(&locked, "locked", false, "Require immutable bundle inventory lock")
	command.Flags().BoolVar(&wait, "wait", false, "Observe until terminal state")
	command.Flags().BoolVar(&structural, "structural", false, "Install definitions and remote references without local secrets or deployment")
	command.Flags().DurationVar(&deadline, "wait-timeout", 5*time.Minute, "Total upload, planning, acceptance and observation deadline")
	group.AddCommand(command)
}
