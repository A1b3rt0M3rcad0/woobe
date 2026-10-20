package cli

import (
	"context"
	"encoding/json"
	"strings"
	"time"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packageapi"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagecheckpoint"
	"github.com/spf13/cobra"
)

type packageOperationFailure struct {
	Operation packageapi.Operation
	Cause     *output.Error
}

func (e *packageOperationFailure) Error() string { return e.Cause.Error() }

func (a *App) packageClient(ctx context.Context, operation string) (*packageapi.Client, error) {
	control, err := a.client()
	if err != nil {
		return nil, err
	}
	client, err := packageapi.New(control, a.Project)
	if err != nil {
		return nil, err
	}
	capabilities, err := client.Capabilities(ctx)
	if err != nil {
		return nil, err
	}
	if err := packageCatalogCompatibility(client, capabilities); err != nil {
		return nil, err
	}
	for _, supported := range capabilities.SupportedOperations {
		if supported == operation {
			return client, nil
		}
	}
	return nil, output.New(9, "Server does not advertise the requested Package operation")
}

func (a *App) emitPackageOperation(result packageapi.Operation, err error) error {
	if err != nil {
		return &packageOperationFailure{result, output.Normalize(err)}
	}
	if result.State == "failed" {
		return &packageOperationFailure{result, output.New(7, "Package operation failed; inspect its diagnostics and retained inventory")}
	}
	return a.writeOutput(a.Out, result, map[string]string{"project_id": result.ProjectID}, nil, a.packageFinalMeta(result))
}

func (a *App) packageFinalMeta(result packageapi.Operation) map[string]any {
	meta := map[string]any{"complete": result.Terminal}
	if a.packageCheckpointPath != "" {
		meta["checkpoint"] = a.packageCheckpointPath
	}
	if a.Mode == "jsonl" {
		a.packageOutputSequence++
		meta["record"], meta["sequence"], meta["operation_id"] = "final", a.packageOutputSequence, result.OperationID
	}
	return meta
}

// progress records are observations; one final envelope reports the last known state.
func (a *App) packageProgress(result packageapi.Operation, sequence *int64, values map[string]string) error {
	if a.Mode != "jsonl" || result.Terminal {
		return nil
	}
	encoded, _ := json.Marshal(result)
	if len(values) != 0 {
		_ = json.Unmarshal(scrubSecretJSON(encoded, values), &result)
	}
	*sequence++
	a.packageOutputSequence = *sequence
	return output.WriteWithMeta(a.Out, "jsonl", result, map[string]string{"project_id": result.ProjectID}, nil,
		map[string]any{"complete": false, "record": "progress", "sequence": *sequence, "operation_id": result.OperationID})
}

func (a *App) packageOperationCommands(group *cobra.Command) {
	for _, action := range []string{"status", "resume", "cancel"} {
		var checkpointPath string
		var wait bool
		var deadline time.Duration
		var revision int64
		command := &cobra.Command{Use: action + " [OPERATION_ID]", Short: "Observe or control one durable Package operation", Args: cobra.MaximumNArgs(1), RunE: func(cmd *cobra.Command, args []string) error {
			if err := packageFlags(cmd, "yes", "validate-body", "validate-parameters", "schema-sha256"); err != nil {
				return err
			}
			if a.DryRun || deadline <= 0 || len(args) == 0 && checkpointPath == "" {
				return output.New(2, "Package operation requires an ID or --checkpoint and a positive deadline")
			}
			if action == "resume" && revision <= 0 && checkpointPath == "" {
				return output.New(2, "Resume requires --revision from an observed operation")
			}
			var store *packagecheckpoint.Store
			var cp packagecheckpoint.Checkpoint
			var err error
			if checkpointPath != "" {
				store, err = packagecheckpoint.Open(checkpointPath)
				if err != nil {
					return err
				}
				defer store.Close()
				cp, err = store.Read()
				if err != nil {
					return err
				}
				if cp.State == packagecheckpoint.Prepared {
					return output.New(9, "Prepared checkpoint has no sent Apply request to observe")
				}
			}
			ctx, stop := context.WithTimeout(cmd.Context(), deadline)
			defer stop()
			client, err := a.packageClient(ctx, action)
			if err != nil {
				return err
			}
			var schema map[string]any
			if a.ValidateBody || a.ValidateParameters {
				schema, err = a.loadServerSchema(ctx)
				if err != nil {
					return err
				}
			}
			validate := func(method, suffix string, id string, body any) error {
				if schema == nil {
					return nil
				}
				paths := map[string]string{"project_id": client.ProjectID}
				if id != "" {
					paths["operation_id"] = id
				}
				return a.validatePackageRequest(schema, method, suffix, paths, nil, body)
			}
			id := ""
			if len(args) != 0 {
				id = args[0]
				if packageUUID.MatchString(id) {
					id = strings.ToLower(id)
				}
			}
			var result packageapi.Operation
			if store != nil {
				capabilities, err := client.Capabilities(ctx)
				if err != nil {
					return err
				}
				if cp.APIOrigin != client.Control.Base || cp.ProjectID != client.ProjectID || cp.PrincipalFingerprint != capabilities.PrincipalFingerprint {
					return output.New(3, "Package checkpoint belongs to different destination authority")
				}
				if id != "" && cp.OperationID != "" && id != cp.OperationID {
					return output.New(2, "Operation differs from checkpoint identity")
				}
				if cp.OperationID == "" {
					body := map[string]any{"idempotency_key": cp.IdempotencyKey}
					if err = validate("POST", "/operations/lookup", "", body); err != nil {
						return err
					}
					result, err = client.Lookup(ctx, cp.IdempotencyKey)
					if err != nil {
						return &output.Error{Code: 9, Message: "Package acceptance remains unknown; keep the same checkpoint and key", Outcome: "unknown"}
					}
					if id != "" && id != result.OperationID {
						return output.New(9, "Lookup returned a different operation")
					}
				} else {
					if err = validate("GET", "/operations/{operation_id}", cp.OperationID, nil); err != nil {
						return err
					}
					result, err = client.Status(ctx, cp.OperationID)
					if err != nil {
						return err
					}
				}
				id = result.OperationID
				// Resumption requires approval of an observed dependency revision.
				if action == "resume" && revision == 0 {
					revision = cp.LastRevision
				}
				if err = savePackageObservation(store, &cp, result); err != nil {
					return err
				}
			} else if action == "status" {
				if err = validate("GET", "/operations/{operation_id}", id, nil); err != nil {
					return err
				}
				result, err = client.Status(ctx, id)
				if err != nil {
					return err
				}
			}
			if action == "cancel" {
				if err = validate("POST", "/operations/{operation_id}/cancel", id, map[string]any{}); err != nil {
					return err
				}
				result, err = client.Cancel(ctx, id)
			} else if action == "resume" {
				if revision <= 0 {
					return output.New(2, "Resume requires an observed revision")
				}
				if store != nil && result.Revision != revision {
					return output.New(6, "Checkpoint revision changed; observe and approve the current dependency wait")
				}
				body := map[string]any{"expected_revision": revision}
				if err = validate("POST", "/operations/{operation_id}/resume", id, body); err != nil {
					return err
				}
				result, err = client.Resume(ctx, id, revision)
			}
			if err != nil {
				return err
			}
			var sequence int64
			observe := func(next packageapi.Operation) error {
				if store != nil {
					if err := savePackageObservation(store, &cp, next); err != nil {
						return err
					}
				}
				return a.packageProgress(next, &sequence, nil)
			}
			if err = observe(result); err != nil {
				return err
			}
			if wait {
				result, err = client.Wait(ctx, result, observe)
			}
			return a.emitPackageOperation(result, err)
		}}
		command.Flags().StringVar(&checkpointPath, "checkpoint", "", "Recover and persist the original private operation identity")
		command.Flags().BoolVar(&wait, "wait", false, "Observe until terminal state")
		command.Flags().DurationVar(&deadline, "wait-timeout", 5*time.Minute, "Total reconciliation/control/observation deadline")
		command.Flags().DurationVar(&deadline, "deadline", 5*time.Minute, "Alias for --wait-timeout")
		if action == "resume" {
			command.Flags().Int64Var(&revision, "revision", 0, "Approved revision of the observed dependency wait")
		}
		group.AddCommand(command)
	}
}
