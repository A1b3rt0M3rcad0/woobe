package cli

import (
	"bytes"
	"context"
	"encoding/json"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/jsoninput"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/manifest"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"github.com/spf13/cobra"
	"net/url"
	"sort"
	"strings"
)

type FieldChange struct {
	Field   string `json:"field"`
	Present bool   `json:"current_present"`
	Current any    `json:"current,omitempty"`
	Desired any    `json:"desired"`
}

func desiredFields(body []byte) (map[string]any, error) {
	var obj map[string]any
	dec := json.NewDecoder(bytes.NewReader(body))
	dec.UseNumber()
	if e := dec.Decode(&obj); e != nil || obj == nil {
		return nil, output.New(2, "state comparison requires an object body")
	}
	return obj, nil
}
func fieldChanges(current any, desired map[string]any) ([]FieldChange, error) {
	obj, ok := current.(map[string]any)
	if !ok {
		return nil, output.New(9, "resource does not expose an object projection")
	}
	changes := []FieldChange{}
	comparator := &jsoninput.Comparator{}
	for k, v := range desired {
		old, present := obj[k]
		equal, err := comparator.Equal(old, v)
		if err != nil {
			return nil, output.New(9, err.Error())
		}
		if !present || !equal {
			if output.Sensitive(k) {
				old = "[REDACTED]"
				v = "[REDACTED]"
			}
			changes = append(changes, FieldChange{Field: k, Present: present, Current: old, Desired: v})
		}
	}
	sort.Slice(changes, func(i, j int) bool { return changes[i].Field < changes[j].Field })
	return changes, nil
}
func unwrap(v any) any {
	if env, ok := v.(map[string]any); ok {
		if data, ok := env["data"]; ok {
			return data
		}
	}
	return v
}
func (a *App) operation(command string) (Operation, bool) {
	for _, op := range a.Registry {
		if op.Command == command {
			return op, true
		}
	}
	return Operation{}, false
}
func (a *App) readResource(ctx context.Context, op Operation, args []string) (any, map[string]string, error) {
	if op.Kind != "http" || op.Method != "GET" || len(args) != len(op.Params) {
		return nil, nil, output.New(2, "read operation and exact resource arguments required")
	}
	return a.readResourceQuery(ctx, op, args, nil)
}
func (a *App) readResourceQuery(ctx context.Context, op Operation, args []string, query url.Values) (any, map[string]string, error) {
	if op.Kind != "http" || op.Method != "GET" || len(args) != len(op.Params) {
		return nil, nil, output.New(2, "read operation and exact resource arguments required")
	}
	c, e := a.client()
	if e != nil {
		return nil, nil, e
	}
	path := op.Path
	for _, scope := range []struct{ name, id string }{{"workspace_id", a.Workspace}, {"project_id", a.Project}} {
		if strings.Contains(path, "{"+scope.name+"}") {
			if e := resourceID(scope.id); e != nil {
				return nil, nil, e
			}
			path = strings.ReplaceAll(path, "{"+scope.name+"}", url.PathEscape(scope.id))
		}
	}
	for i, p := range op.Params {
		if e := resourceID(args[i]); e != nil {
			return nil, nil, e
		}
		path = strings.ReplaceAll(path, "{"+p+"}", url.PathEscape(args[i]))
	}
	q := url.Values{}
	for name, values := range query {
		q[name] = append([]string(nil), values...)
	}
	if op.QueryScope != "" {
		id := a.Project
		if op.QueryScope == "workspace_id" {
			id = a.Workspace
		}
		if id == "" {
			return nil, nil, output.New(2, op.QueryScope+" required")
		}
		q.Set(op.QueryScope, id)
	}
	v, h, e := c.Request(ctx, "GET", path, q, nil)
	if e != nil {
		return nil, nil, e
	}
	return unwrap(v), map[string]string{"etag": h.Get("ETag"), "request_id": h.Get("X-Request-ID")}, nil
}
func (a *App) manifestDiff(ctx context.Context, d manifest.Document) ([]map[string]any, error) {
	if e := a.validateManifest(d); e != nil {
		return nil, e
	}
	v, e := a.resolve()
	if e != nil {
		return nil, e
	}
	if (d.Workspace != "" && v.Workspace != d.Workspace) || (d.Project != "" && v.Project != d.Project) {
		return nil, output.New(6, "manifest scope must match selected context")
	}
	steps, _ := d.Order()
	out := []map[string]any{}
	for _, s := range steps {
		op, _ := a.operation(s.Command)
		row := map[string]any{"step_id": s.ID, "operation": op, "authorization": "not_evaluated"}
		if len(s.DependsOn) > 0 {
			row["status"] = "deferred_until_dependencies_resolved"
			out = append(out, row)
			continue
		}
		if op.Method == "POST" {
			row["status"] = "planned_create"
			row["existence"] = "not_evaluated"
			out = append(out, row)
			continue
		}
		getter, ok := a.operation(strings.TrimSuffix(s.Command, " update") + " get")
		if op.Method == "GET" {
			getter = op
			ok = true
		}
		if !ok || getter.Method != "GET" || getter.Path != op.Path {
			return nil, output.New(9, "no compatible resource reader for "+s.Command)
		}
		current, meta, e := a.readResource(ctx, getter, s.Args)
		if e != nil {
			return nil, e
		}
		if s.Command == "workspace authority category update" {
			if e := verifyCategoryObservation(current, meta, a.Workspace, s.Args[0]); e != nil {
				return nil, e
			}
		}
		if s.IfMatch != "" && meta["etag"] == "" {
			return nil, output.New(9, "resource diff cannot verify if_match without an observed ETag")
		}
		if s.IfMatch != "" && s.IfMatch != meta["etag"] {
			return nil, output.New(6, "resource ETag differs from expected revision")
		}
		row["observation"] = meta
		if op.Method == "GET" {
			row["status"] = "read"
			row["current"] = current
		} else {
			desired, e := desiredFields(s.Body)
			if e != nil {
				return nil, e
			}
			changes, e := configurationChanges(s.Command, current, desired)
			if e != nil {
				return nil, e
			}
			row["changes"] = changes
			row["status"] = "unchanged"
			if len(changes) > 0 {
				row["status"] = "changed"
			}
		}
		out = append(out, row)
	}
	return out, nil
}
func (a *App) manifestDiffCommand(g *cobra.Command) {
	g.AddCommand(&cobra.Command{Use: "diff", Args: cobra.NoArgs, RunE: func(cmd *cobra.Command, _ []string) error {
		d, e := a.readManifest()
		if e != nil {
			return e
		}
		diff, e := a.manifestDiff(cmd.Context(), d)
		if e != nil {
			return e
		}
		return a.emit(map[string]any{"manifest_hash": d.Hash(), "operations": diff, "authorization": "not_evaluated", "complete": true, "comparison": "supplied_fields_only"})
	}})
}
