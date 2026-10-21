package cli

import (
	"context"
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"github.com/spf13/cobra"
	"strings"
)

func (a *App) serverOperation(ctx context.Context, command string) (Operation, map[string]any, map[string]any, map[string]any, error) {
	op, ok := a.operation(command)
	if !ok || op.Kind != "http" {
		return op, nil, nil, nil, output.New(2, "server schema requires a canonical HTTP operation")
	}
	doc, e := a.loadServerSchema(ctx)
	if e != nil {
		return op, nil, nil, nil, e
	}
	path, definition, _, e := advertisedOperation(doc, op)
	if e != nil {
		return op, nil, nil, nil, e
	}
	return op, doc, path, definition, nil
}
func (a *App) remoteSchemaCommand() {
	var operation string
	c := &cobra.Command{Use: "server-schema", Short: "Retrieve authoritative OpenAPI operation and components", Args: cobra.NoArgs, RunE: func(cmd *cobra.Command, _ []string) error {
		op, doc, path, definition, e := a.serverOperation(cmd.Context(), operation)
		if e != nil {
			return e
		}
		return a.writeOutput(a.Out, map[string]any{"operation": op, "definition": definition, "path_parameters": path["parameters"], "components": doc["components"], "openapi_version": doc["openapi"], "source": "server_openapi"}, nil, nil, nil)
	}}
	c.Flags().StringVar(&operation, "command", "", "Canonical HTTP command")
	_ = c.MarkFlagRequired("command")
	a.Root.AddCommand(c)
}

func (a *App) loadServerSchema(ctx context.Context) (map[string]any, error) {
	client, e := a.client()
	if e != nil {
		return nil, e
	}
	v, _, e := client.Request(ctx, "GET", "/openapi.json", nil, nil)
	if e != nil {
		return nil, e
	}
	doc, ok := v.(map[string]any)
	if !ok {
		return nil, output.New(9, "invalid server OpenAPI")
	}
	if a.SchemaSHA != "" && a.SchemaSHA != schemaDigest(doc) {
		return nil, output.New(6, "advertised schema snapshot differs from expected SHA-256")
	}
	return doc, nil
}
func operationDefinition(doc map[string]any, op Operation) (map[string]any, error) {
	_, def, _, e := advertisedOperation(doc, op)
	return def, e
}

// Template names are transport metadata; literal segments and method must match.
func advertisedOperation(doc map[string]any, op Operation) (map[string]any, map[string]any, string, error) {
	paths, _ := doc["paths"].(map[string]any)
	selected := op.Path
	if _, exists := paths[selected]; !exists {
		selected = ""
		for candidate, raw := range paths {
			if placeholders.ReplaceAllString(candidate, "{}") != placeholders.ReplaceAllString(op.Path, "{}") {
				continue
			}
			path, ok := raw.(map[string]any)
			if !ok {
				continue
			}
			if _, ok := path[strings.ToLower(op.Method)].(map[string]any); !ok {
				continue
			}
			if selected != "" {
				return nil, nil, "", output.New(9, "ambiguous advertised operation template")
			}
			selected = candidate
		}
	}
	path, _ := paths[selected].(map[string]any)
	def, ok := path[strings.ToLower(op.Method)].(map[string]any)
	if !ok {
		return nil, nil, "", output.New(9, "operation not advertised by server")
	}
	if _, exists := path["$ref"]; exists {
		return nil, nil, "", output.New(9, "referenced OpenAPI path items are not supported")
	}
	return path, def, selected, nil
}

func schemaDigest(doc map[string]any) string {
	b, _ := json.Marshal(doc)
	return fmt.Sprintf("%x", sha256.Sum256(b))
}
