package cli

import (
	"encoding/json"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/config"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/manifest"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"github.com/spf13/cobra"
	"os"
	"path/filepath"
	"strings"
	"time"
)

type Reconciliation struct {
	ReadCommand string `json:"read_command"`
	ResourceID  string `json:"resource_id,omitempty"`
	RequestID   string `json:"request_id,omitempty"`
	ETag        string `json:"etag,omitempty"`
	ObservedAt  string `json:"observed_at"`
	Evidence    string `json:"evidence"`
}

func acquireCheckpointLock(path string) (func(), error) {
	if e := os.MkdirAll(filepath.Dir(path), 0700); e != nil {
		return nil, e
	}
	f, e := os.OpenFile(path+".lock", os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0600)
	if e != nil {
		if os.IsExist(e) {
			return nil, output.New(6, "checkpoint is locked; confirm no process is using it before removing a stale .lock file")
		}
		return nil, e
	}
	if e = f.Close(); e != nil {
		_ = os.Remove(path + ".lock")
		return nil, e
	}
	return func() { _ = os.Remove(path + ".lock") }, nil
}
func saveCheckpoint(path string, cp checkpoint) error {
	b, e := json.MarshalIndent(cp, "", "  ")
	if e != nil {
		return e
	}
	if len(b) > 32<<20 {
		return output.New(9, "checkpoint exceeds 32 MiB")
	}
	return config.AtomicWrite(path, b, 0600)
}
func (a *App) manifestReconcileCommand(g *cobra.Command) {
	var path, resourceID string
	cmd := &cobra.Command{Use: "reconcile <step-id>", Short: "Read and verify expected remote state before resuming an uncertain step", Args: cobra.ExactArgs(1), RunE: func(cmd *cobra.Command, args []string) error {
		if !a.Yes {
			return output.New(2, "reconcile requires --yes")
		}
		if a.DryRun {
			return output.New(2, "use manifest diff for a read-only preview")
		}
		if path == "" {
			return output.New(2, "--checkpoint required")
		}
		d, e := a.readManifest()
		if e != nil {
			return e
		}
		if e = a.validateManifest(d); e != nil {
			return e
		}
		v, e := a.resolve()
		if e != nil {
			return e
		}
		release, e := acquireCheckpointLock(path)
		if e != nil {
			return e
		}
		defer release()
		b, e := readCheckpoint(path)
		if e != nil {
			return output.New(2, "checkpoint unavailable")
		}
		cp, e := parseCheckpoint(b)
		if e != nil {
			return output.New(2, "invalid checkpoint")
		}
		fingerprint, e := a.credentialFingerprint(v)
		if e != nil {
			return e
		}
		if cp.CredentialFingerprint != fingerprint || cp.Hash != d.Hash() || cp.Origin != v.APIURL || cp.Workspace != v.Workspace || cp.Project != v.Project || cp.Credential != v.Credential {
			return output.New(6, "checkpoint belongs to another plan or context")
		}
		if e = validateCheckpointPlan(cp, d); e != nil {
			return e
		}
		if cp.Steps[args[0]] != "unknown" && cp.Steps[args[0]] != "in_flight" {
			return output.New(6, "only uncertain steps can be reconciled")
		}
		var step manifest.Step
		found := false
		for _, s := range d.Steps {
			if s.ID == args[0] {
				step = s
				found = true
				break
			}
		}
		if !found {
			return output.New(2, "unknown manifest step")
		}
		if len(stepSecretNames(step)) > 0 {
			return output.New(9, "protected credential writes cannot be reconciled from redacted resource projections")
		}
		step, e = manifest.ResolveStep(step, cp.Results)
		if e != nil {
			return output.New(2, e.Error())
		}
		op, _ := a.operation(step.Command)
		if op.Method != "POST" && op.Method != "PATCH" && op.Method != "PUT" {
			return output.New(9, "operation cannot be reconciled as resource state")
		}
		suffix := " update"
		if op.Method == "POST" {
			suffix = " create"
		}
		if !strings.HasSuffix(step.Command, suffix) {
			return output.New(9, "operation has no verified resource getter convention")
		}
		getter, ok := a.operation(strings.TrimSuffix(step.Command, suffix) + " get")
		if !ok || getter.Method != "GET" {
			return output.New(9, "compatible resource getter unavailable")
		}
		readArgs := append([]string{}, step.Args...)
		if op.Method == "POST" {
			if resourceID == "" {
				return output.New(2, "creation reconciliation requires explicit --resource-id")
			}
			readArgs = append(readArgs, resourceID)
		} else if getter.Path != op.Path {
			return output.New(9, "resource getter does not match write target")
		}
		current, meta, e := a.readResource(cmd.Context(), getter, readArgs)
		if e != nil {
			return e
		}
		desired, e := desiredFields(step.Body)
		if e != nil {
			return e
		}
		if len(desired) == 0 {
			return output.New(2, "reconciliation requires nonempty expected resource fields")
		}
		changes, e := fieldChanges(current, desired)
		if e != nil {
			return e
		}
		if len(changes) != 0 {
			return output.New(6, "remote projection does not match all supplied expected fields")
		}
		if op.Method == "POST" {
			obj, ok := current.(map[string]any)
			if !ok || obj["id"] != resourceID {
				return output.New(6, "resource ID does not match returned projection")
			}
		}
		if cp.Results == nil {
			cp.Results = map[string]any{}
		}
		if cp.Reconciliations == nil {
			cp.Reconciliations = map[string]Reconciliation{}
		}
		cp.Results[step.ID] = output.Redact(current)
		cp.Steps[step.ID] = "reconciled"
		cp.Reconciliations[step.ID] = Reconciliation{ReadCommand: getter.Command, ResourceID: resourceID, RequestID: meta["request_id"], ETag: meta["etag"], ObservedAt: time.Now().UTC().Format(time.RFC3339Nano), Evidence: "authorized_read_matches_supplied_expected_fields; original_write_attribution_not_proven"}
		if e = saveCheckpoint(path, cp); e != nil {
			return e
		}
		return a.emit(cp)
	}}
	cmd.Flags().StringVar(&path, "checkpoint", "", "Checkpoint to reconcile")
	cmd.Flags().StringVar(&resourceID, "resource-id", "", "Explicit resource ID for an uncertain creation")
	g.AddCommand(cmd)
}
