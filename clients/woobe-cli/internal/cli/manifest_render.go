package cli

import (
	"bytes"
	"encoding/json"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/manifest"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
)

// Only validated local plans may preserve markers. Remote data uses normal redaction.
func (a *App) emitManifestPlan(data any) error {
	b, e := json.Marshal(data)
	if e != nil {
		return e
	}
	var value any
	dec := json.NewDecoder(bytes.NewReader(b))
	dec.UseNumber()
	if e = dec.Decode(&value); e != nil {
		return e
	}
	var redact func(any) any
	redact = func(v any) any {
		switch x := v.(type) {
		case map[string]any:
			out := map[string]any{}
			for k, sub := range x {
				if output.Sensitive(k) {
					if _, ok := manifest.SecretReference(sub); ok {
						out[k] = sub
					} else {
						out[k] = "[REDACTED]"
					}
				} else {
					out[k] = redact(sub)
				}
			}
			return out
		case []any:
			for i, sub := range x {
				x[i] = redact(sub)
			}
			return x
		}
		return v
	}
	return a.writeOutput(a.Out, redact(value), map[string]string{"workspace_id": a.Workspace, "project_id": a.Project}, nil, nil)
}
