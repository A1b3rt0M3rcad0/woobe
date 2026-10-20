package cli

import (
	"bytes"
	"encoding/json"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/manifest"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"github.com/spf13/cobra"
	"os"
	"strings"
)

type checkpoint struct {
	SecretFingerprints    map[string]string         `json:"secret_fingerprints,omitempty"`
	CredentialFingerprint string                    `json:"credential_fingerprint,omitempty"`
	Hash                  string                    `json:"manifest_hash"`
	Origin                string                    `json:"api_url"`
	Workspace             string                    `json:"workspace_id"`
	Project               string                    `json:"project_id"`
	Credential            string                    `json:"credential_ref"`
	Steps                 map[string]string         `json:"steps"`
	Results               map[string]any            `json:"results,omitempty"`
	Reconciliations       map[string]Reconciliation `json:"reconciliations,omitempty"`
}

func (a *App) manifestApplyCommand(g *cobra.Command) {
	var path string
	var skipUnchanged bool
	cmd := &cobra.Command{Use: "apply", Args: cobra.NoArgs, RunE: func(cmd *cobra.Command, _ []string) error {
		if !a.Yes {
			return output.New(2, "apply requires --yes")
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
		if (d.Workspace != "" && v.Workspace != d.Workspace) || (d.Project != "" && v.Project != d.Project) {
			return output.New(6, "manifest scope must match selected context")
		}
		if !a.DryRun {
			release, e := acquireCheckpointLock(path)
			if e != nil {
				return e
			}
			defer release()
		}
		fingerprint, e := a.credentialFingerprint(v)
		if e != nil {
			return e
		}
		secretValues, secretHashes := map[string]string{}, map[string]string{}
		if !a.DryRun {
			for _, step := range d.Steps {
				if skipUnchanged && len(stepSecretNames(step)) > 0 {
					return notAttempted(output.New(9, "skip-unchanged cannot compare protected credential values"))
				}
			}
			secretValues, secretHashes, e = a.manifestSecretSnapshot(d)
			if e != nil {
				return notAttempted(e)
			}
		}
		cp := checkpoint{CredentialFingerprint: fingerprint, Hash: d.Hash(), Origin: v.APIURL, Workspace: v.Workspace, Project: v.Project, Credential: v.Credential, Steps: map[string]string{}, Results: map[string]any{}}
		cp.SecretFingerprints = secretHashes
		if b, err := readCheckpoint(path); err == nil {
			old, err := parseCheckpoint(b)
			if err != nil {
				return output.New(2, "invalid checkpoint")
			}
			if !a.DryRun && !sameSecretSnapshot(old.SecretFingerprints, cp.SecretFingerprints) {
				return output.New(6, "checkpoint protected credential values changed")
			}
			if old.Hash != cp.Hash || old.Origin != cp.Origin || old.Workspace != cp.Workspace || old.Project != cp.Project || old.Credential != cp.Credential || old.CredentialFingerprint != cp.CredentialFingerprint {
				return output.New(6, "checkpoint belongs to another plan or context")
			}
			if old.Steps == nil {
				return output.New(2, "invalid checkpoint steps")
			}
			if e = validateCheckpointPlan(old, d); e != nil {
				return e
			}
			cp = old
			if cp.Results == nil {
				cp.Results = map[string]any{}
			}
		} else if !os.IsNotExist(err) {
			return output.New(2, "cannot read checkpoint")
		}
		save := func() error { return saveCheckpoint(path, cp) }
		if a.DryRun {
			return a.emit(map[string]any{"manifest_hash": d.Hash(), "checkpoint": cp, "executed": false, "validation": "local_plan_only"})
		}
		var schemaDoc map[string]any
		if a.ValidateBody || a.ValidateParameters {
			schemaDoc, e = a.loadServerSchema(cmd.Context())
			if e != nil {
				return notAttempted(e)
			}
		}
		steps, _ := d.Order()
		for _, s := range steps {
			switch cp.Steps[s.ID] {
			case "committed", "reconciled", "unchanged":
				continue
			case "unknown", "in_flight":
				return partialApply(cp, s.ID, "previous write requires remote reconciliation before resume", "unknown", true)
			}

			s, e = manifest.ResolveStep(s, cp.Results)
			if e != nil {
				return stopBeforeWrite(path, cp, s.ID, output.New(2, e.Error()))
			}
			s, e = resolveStepSecrets(s, secretValues)
			if e != nil {
				return stopBeforeWrite(path, cp, s.ID, e)
			}
			if e = validateMCPPermissions(s.Command, s.Body); e != nil {
				return stopBeforeWrite(path, cp, s.ID, e)
			}
			if a.ValidateBody {
				op, _ := a.operation(s.Command)
				def, e := operationDefinition(schemaDoc, op)
				if e == nil {
					e = validateBodySchema(schemaDoc, def, s.Body)
				}
				if e != nil {
					return stopBeforeWrite(path, cp, s.ID, e)
				}
			}
			if a.ValidateParameters {
				op, _ := a.operation(s.Command)
				values, query, e := a.manifestParameterValues(op, s)
				if e == nil {
					e = validateOperationParameters(schemaDoc, op, values, query)
				}
				if e != nil {
					return stopBeforeWrite(path, cp, s.ID, e)
				}
			}
			if skipUnchanged {
				observed, unchanged, e := a.observeUnchanged(cmd.Context(), s)
				if e != nil {
					return stopBeforeWrite(path, cp, s.ID, e)
				}
				if unchanged {
					cp.Results[s.ID] = output.Redact(observed)
					cp.Steps[s.ID] = "unchanged"
					if e = save(); e != nil {
						return stopBeforeWrite(path, cp, s.ID, e)
					}
					continue
				}
			}
			cp.Steps[s.ID] = "in_flight"
			if e = save(); e != nil {
				return stopBeforeWrite(path, cp, s.ID, e)
			}
			childOut := &bytes.Buffer{}
			childErr := &bytes.Buffer{}
			child := New(bytes.NewReader(s.Body), childOut, childErr)
			args := append([]string{}, strings.Fields(s.Command)...)
			args = append(args, s.Args...)
			args = append(args, "--config", a.ConfigPath, "--api-url", v.APIURL, "--timeout", a.Timeout.String(), "--output", "json", "--no-input")
			if a.ContextName != "" {
				args = append(args, "--context", a.ContextName)
			}
			if v.Workspace != "" {
				args = append(args, "--workspace", v.Workspace)
			}
			if v.Project != "" {
				args = append(args, "--project", v.Project)
			}
			if v.Credential != "" {
				args = append(args, "--credential", v.Credential)
			}
			if len(s.Body) > 0 {
				args = append(args, "--file", "-")
			}
			if s.IfMatch != "" {
				args = append(args, "--if-match", s.IfMatch)
			}
			code := child.Execute(cmd.Context(), args)
			childOut = bytes.NewBuffer(scrubSecretJSON(childOut.Bytes(), secretValues))
			if code != 0 {
				cp.Steps[s.ID] = "unknown"
				var env output.Envelope
				if json.Unmarshal(childOut.Bytes(), &env) == nil && env.Error != nil {
					switch env.Error.Outcome {
					case "rejected", "not_attempted":
						cp.Steps[s.ID] = env.Error.Outcome
					}
				}
				if e = save(); e != nil {
					return partialApply(cp, s.ID, "apply failed and checkpoint persistence failed", "unknown", false)
				}
				partial := partialApply(cp, s.ID, "partial apply stopped", cp.Steps[s.ID], true).(*manifestPartial)
				partial.Cause = env.Error
				return partial
			}
			var result output.Envelope
			dec := json.NewDecoder(bytes.NewReader(childOut.Bytes()))
			dec.UseNumber()
			if e = dec.Decode(&result); e != nil {
				return partialApply(cp, s.ID, "operation committed but result could not be checkpointed", "unknown", true)
			}
			data := result.Data
			if env, ok := data.(map[string]any); ok {
				if nested, ok := env["data"]; ok {
					data = nested
				}
			}
			cp.Results[s.ID] = output.Redact(data)
			cp.Steps[s.ID] = "committed"
			if e = save(); e != nil {
				return partialApply(cp, s.ID, "write committed but checkpoint save failed", "committed", false)
			}
		}
		return a.emit(cp)
	}}
	cmd.Flags().BoolVar(&skipUnchanged, "skip-unchanged", false, "Read compatible update targets and checkpoint unchanged supplied fields")
	cmd.Flags().StringVar(&path, "checkpoint", "", "Private checkpoint file, required for apply and resume")
	g.AddCommand(cmd)
}
