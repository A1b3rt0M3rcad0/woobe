package cli

import (
	"context"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"strings"
)

// OpenAPI advertisement establishes route availability only. The actual request
// still authenticates and authorizes on the server with the selected principal.
func (a *App) requireAdvertised(ctx context.Context, op Operation) error {
	c, e := a.client()
	if e != nil {
		return e
	}
	doc, _, e := c.Request(ctx, "GET", "/openapi.json", nil, nil)
	if e != nil {
		return &output.Error{Code: 9, Message: "extension route cannot be verified from server OpenAPI", Cause: e, Outcome: "not_attempted"}
	}
	root, ok := doc.(map[string]any)
	if !ok {
		return output.New(9, "server OpenAPI document is invalid")
	}
	paths, ok := root["paths"].(map[string]any)
	if !ok {
		return output.New(9, "server OpenAPI paths unavailable")
	}
	route, ok := paths[op.Path].(map[string]any)
	if !ok {
		return output.New(9, "extension route not advertised by server")
	}
	method, ok := route[strings.ToLower(op.Method)].(map[string]any)
	if !ok || len(method) == 0 {
		return output.New(9, "extension method not advertised by server")
	}
	return nil
}
