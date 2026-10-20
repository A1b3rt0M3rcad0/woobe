package cli

import (
	"encoding/json"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/controlplane"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagecheckpoint"
	"github.com/spf13/cobra"
	"strings"
)

func (a *App) requestCommands() {
	a.Root.AddCommand(&cobra.Command{Use: "request <method> <path>", Short: "Call a public API path with the selected credential", Args: cobra.ExactArgs(2), RunE: func(cmd *cobra.Command, args []string) error {
		method := strings.ToUpper(args[0])
		switch method {
		case "GET", "HEAD", "POST", "PUT", "PATCH", "DELETE":
		default:
			return output.New(2, "unsupported HTTP method")
		}
		b, e := a.body(false)
		if e != nil {
			return e
		}
		return a.call(cmd, method, args[1], b, false)
	}})
}
func (a *App) call(cmd *cobra.Command, method, path string, b []byte, secret bool) (err error) {
	defer func() {
		if err != nil && method != "GET" && method != "HEAD" && output.Normalize(err).Outcome == "" {
			err = notAttempted(err)
		}
	}()
	if e := controlplane.ValidatePath(path); e != nil {
		return e
	}
	c, e := a.client()
	if e != nil {
		return e
	}
	q, e := a.query()
	if e != nil {
		return e
	}
	if a.DryRun {
		return a.emit(map[string]any{"method": method, "path": path, "query": q, "body": json.RawMessage(b), "executed": false})
	}
	if method == "DELETE" && !a.Yes {
		return output.New(2, "destructive operation requires --yes")
	}
	var destination *packagecheckpoint.PrivateDestination
	if secret {
		if a.SecretFile == "" {
			return output.New(2, "issuance requires --secret-file")
		}
		destination, e = packagecheckpoint.PreparePrivateDestination(a.SecretFile)
		if e != nil {
			return e
		}
		defer destination.Close()
	}
	var v any
	if method == "POST" && strings.HasSuffix(path, "/release-tests/run") {
		v, e = a.requestReleaseTest(cmd, c, path, b)
	} else {
		v, _, e = c.Request(cmd.Context(), method, path, q, b)
	}
	if e != nil {
		return e
	}
	if destination != nil {
		// Preserve the native response fields for existing readers, and version
		// the custody format independently of API/envelope schema versions.
		native, ok := v.(map[string]any)
		if !ok {
			return &output.Error{Code: 10, Message: "issuance succeeded but returned an invalid secret envelope", Outcome: "committed"}
		}
		if native["success"] == false {
			return &output.Error{Code: 9, Message: "Issuance response was unsuccessful; secret file was not published", Outcome: "unknown"}
		}
		document := make(map[string]any, len(native)+2)
		for key, value := range native {
			document[key] = value
		}
		document["format"], document["file_schema_version"] = "woobe-issued-secret", "1"
		data, saveErr := json.MarshalIndent(document, "", "  ")
		if saveErr == nil {
			_, saveErr = credentialFromInput(data)
		}
		if saveErr == nil {
			saveErr = destination.Publish(append(data, '\n'))
		}
		if saveErr != nil {
			return &output.Error{Code: 10, Message: "issuance succeeded but private secret publication failed; do not repeat issuance blindly", Outcome: "committed"}
		}
	}
	if method == "POST" && strings.HasSuffix(path, "/release-tests/run") {
		if envelope, ok := v.(map[string]any); ok {
			if outcome, ok := envelope["data"].(map[string]any); ok && outcome["status"] == "failed" {
				return &releaseTestFailure{Data: outcome, Cause: &output.Error{Code: 6, Message: "Agent test failed; inspect validation_errors and actual_output", Outcome: "committed"}}
			}
		}
	}
	return a.emit(v)
}
