package cli

import (
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"github.com/spf13/cobra"
	"strings"
)

func (a *App) doctorCommand() {
	c := &cobra.Command{Use: "doctor", Short: "Read instance, identity and advertised route diagnostics", Args: cobra.NoArgs, RunE: func(cmd *cobra.Command, _ []string) error {
		client, e := a.client()
		if e != nil {
			return e
		}
		identityPath := "/identity/users/me"
		if client.Token != "" {
			identityPath = "/identity/control-key/me"
		}
		checks := map[string]any{}
		passed := 0
		var doc map[string]any
		for _, check := range []struct{ name, path string }{{"instance", "/identity/instance/status"}, {"identity", identityPath}, {"openapi", "/openapi.json"}} {
			v, h, e := client.Request(cmd.Context(), "GET", check.path, nil, nil)
			if e != nil {
				checks[check.name] = map[string]any{"success": false, "error": output.Normalize(e)}
				continue
			}
			passed++
			checks[check.name] = map[string]any{"success": true, "data": output.Redact(v), "request_id": h.Get("X-Request-ID")}
			if check.name == "openapi" {
				doc, _ = v.(map[string]any)
			}
		}
		routes := []map[string]any{}
		paths, _ := doc["paths"].(map[string]any)
		for _, op := range a.Registry {
			if op.Kind != "http" {
				continue
			}
			route, _ := paths[op.Path].(map[string]any)
			_, advertised := route[strings.ToLower(op.Method)]
			routes = append(routes, map[string]any{"command": op.Command, "advertised": advertised, "authorization": "not_evaluated"})
		}
		result := map[string]any{"client_version": Version, "checks": checks, "routes": routes, "complete": passed == 3, "server_authority_enforcement": "not verified by diagnostic reads"}
		if passed != 3 {
			return &diagnosticPartial{Data: result}
		}
		return a.emit(result)
	}}
	a.Root.AddCommand(c)
}

type diagnosticPartial struct{ Data any }

func (*diagnosticPartial) Error() string { return "diagnostic checks partially failed" }
