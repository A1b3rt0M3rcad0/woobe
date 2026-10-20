package cli

import (
	"bytes"
	"encoding/hex"
	"encoding/json"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/jsoninput"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/manifest"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"io"
	"os"
)

func parseCheckpoint(b []byte) (checkpoint, error) {
	var cp checkpoint
	if len(b) > 32<<20 || jsoninput.Validate(b) != nil {
		return cp, output.New(2, "invalid checkpoint JSON")
	}
	d := json.NewDecoder(bytes.NewReader(b))
	d.UseNumber()
	d.DisallowUnknownFields()
	if d.Decode(&cp) != nil || cp.Steps == nil {
		return cp, output.New(2, "invalid checkpoint")
	}
	for _, s := range cp.Steps {
		switch s {
		case "committed", "reconciled", "unchanged", "rejected", "not_attempted", "unknown", "in_flight":
		default:
			return cp, output.New(2, "invalid checkpoint step status")
		}
	}
	for name, fingerprint := range cp.SecretFingerprints {
		if _, ok := manifest.SecretReference(map[string]any{"$secret_ref": name}); !ok {
			return cp, output.New(2, "invalid checkpoint protected reference")
		}
		if decoded, e := hex.DecodeString(fingerprint); e != nil || len(decoded) != 32 {
			return cp, output.New(2, "invalid checkpoint credential fingerprint")
		}
	}
	return cp, nil
}

func readCheckpoint(path string) ([]byte, error) {
	f, e := os.Open(path)
	if e != nil {
		return nil, e
	}
	defer f.Close()
	b, e := io.ReadAll(io.LimitReader(f, 32<<20+1))
	if e != nil {
		return nil, e
	}
	if len(b) > 32<<20 {
		return nil, output.New(2, "checkpoint exceeds 32 MiB")
	}
	return b, nil
}

func validateCheckpointPlan(cp checkpoint, d manifest.Document) error {
	secretNames := map[string]bool{}
	for _, step := range d.Steps {
		for _, name := range stepSecretNames(step) {
			secretNames[name] = true
		}
	}
	if len(secretNames) != len(cp.SecretFingerprints) {
		return output.New(2, "checkpoint protected references differ from plan")
	}
	for name := range cp.SecretFingerprints {
		if !secretNames[name] {
			return output.New(2, "checkpoint protected reference outside plan")
		}
	}
	ids := map[string]bool{}
	for _, s := range d.Steps {
		ids[s.ID] = true
	}
	for id := range cp.Steps {
		if !ids[id] {
			return output.New(2, "checkpoint contains a step outside the plan")
		}
	}
	for id := range cp.Results {
		if !ids[id] {
			return output.New(2, "checkpoint result outside the plan")
		}
	}
	for id := range cp.Reconciliations {
		if !ids[id] || cp.Steps[id] != "reconciled" {
			return output.New(2, "checkpoint reconciliation has no matching reconciled step")
		}
	}
	for id, state := range cp.Steps {
		if terminalState(state) {
			if _, ok := cp.Results[id]; !ok {
				return output.New(2, "terminal checkpoint step has no saved result")
			}
		}
	}
	for _, step := range d.Steps {
		if terminalState(cp.Steps[step.ID]) {
			for _, dep := range step.DependsOn {
				if !terminalState(cp.Steps[dep]) {
					return output.New(2, "terminal step has an incomplete checkpoint dependency")
				}
			}
		}
	}
	return nil
}

func terminalState(state string) bool {
	return state == "committed" || state == "reconciled" || state == "unchanged"
}
