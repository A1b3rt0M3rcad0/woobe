package cli

import (
	"errors"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/schemacheck"
	"github.com/spf13/cobra"
	"strings"
)

func (a *App) validateInputCommand() {
	var command string
	var pathParams []string
	c := &cobra.Command{Use: "validate-input", Short: "Validate an input body against an advertised or local protocol schema without executing it", Args: cobra.NoArgs, RunE: func(cmd *cobra.Command, _ []string) error {
		if command == "runtime target run" || command == "runtime target stream" {
			if a.ValidateParameters || len(pathParams) > 0 {
				return output.New(9, "Runtime SDK commands have no advertised OpenAPI path or query schema")
			}
			b, e := a.body(true)
			if e != nil {
				return e
			}
			if _, e = decodeRuntimeInput(b); e != nil {
				return output.New(2, e.Error())
			}
			return a.emit(map[string]any{"body_validation": "runtime_protocol_v1", "valid": true, "operation": command, "source": "cli_runtime_protocol", "validation": "supported_schema_subset", "validation_direction": "request", "authorization": "not_evaluated", "executed": false})
		}
		b, e := a.body(!a.ValidateParameters)
		if e != nil {
			return e
		}
		if e = validateMCPPermissions(command, b); e != nil {
			return e
		}
		op, doc, _, def, e := a.serverOperation(cmd.Context(), command)
		if e != nil {
			return e
		}
		if b != nil || !a.ValidateParameters || a.ValidateBody {
			if e = validateBodySchema(doc, def, b); e != nil {
				return e
			}
		}
		parameterStatus := "not_evaluated"
		if a.ValidateParameters {
			values := map[string]string{}
			for _, entry := range pathParams {
				name, value, ok := strings.Cut(entry, "=")
				if !ok || name == "" {
					return output.New(2, "path-param requires name=value")
				}
				if _, exists := values[name]; exists {
					return output.New(2, "duplicate path-param")
				}
				values[name] = value
			}
			for _, name := range []string{"workspace_id", "project_id"} {
				if strings.Contains(op.Path, "{"+name+"}") {
					value := a.Workspace
					if name == "project_id" {
						value = a.Project
					}
					if value != "" {
						if explicit, ok := values[name]; ok && explicit != value {
							return output.New(2, "path-param conflicts with selected context")
						}
						values[name] = value
					}
				}
			}
			q, e := a.query()
			if e != nil {
				return e
			}
			if e = validateOperationParameters(doc, op, values, q); e != nil {
				return e
			}
			parameterStatus = "supported_schema_subset"
		} else if len(pathParams) > 0 {
			return output.New(2, "path-param requires --validate-parameters")
		}
		bodyStatus := "not_evaluated"
		if b != nil || !a.ValidateParameters || a.ValidateBody {
			bodyStatus = "supported_schema_subset"
		}
		return a.emit(map[string]any{"body_validation": bodyStatus, "valid": true, "operation": op.Command, "source": "server_openapi", "schema_sha256": schemaDigest(doc), "validation": "supported_schema_subset", "validation_direction": "request", "path_query_validation": parameterStatus, "authorization": "not_evaluated", "executed": false})
	}}
	c.Flags().StringArrayVar(&pathParams, "path-param", nil, "Path parameter name=value for read-only validation (repeatable)")
	c.Flags().StringVar(&command, "command", "", "Canonical HTTP command")
	_ = c.MarkFlagRequired("command")
	a.Root.AddCommand(c)
}
func schemaError(e error) error {
	var s *schemacheck.Error
	if errors.As(e, &s) {
		code := 2
		if s.Unsupported {
			code = 9
		}
		return output.New(code, s.Error())
	}
	return output.New(9, "schema cannot be evaluated")
}
