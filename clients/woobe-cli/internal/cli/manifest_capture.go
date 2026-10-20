package cli

import (
	"encoding/json"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/config"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/manifest"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"github.com/spf13/cobra"
	"strings"
)

// Capture is an explicit top-level field selection, never a full projection PATCH.
func (a *App) manifestCaptureCommand(g *cobra.Command) {
	var kind, id, key, destination string
	var fields, parents []string
	c := &cobra.Command{Use: "capture", Short: "Capture explicitly selected readable fields as a resource update intent", Args: cobra.NoArgs, RunE: func(cmd *cobra.Command, _ []string) error {
		var selected manifest.Kind
		for _, k := range manifest.Kinds() {
			if k.Name == kind {
				selected = k
			}
		}
		if selected.Update == "" {
			return output.New(9, "resource kind has no supported update action")
		}
		getter, ok := a.operation(strings.TrimSuffix(selected.Update, " update") + " get")
		writer, writeOK := a.operation(selected.Update)
		if !ok || !writeOK || getter.Method != "GET" || getter.Path != writer.Path {
			return output.New(9, "resource kind has no compatible reader")
		}
		if len(fields) == 0 {
			return output.New(2, "at least one --field is required")
		}
		seenFields := map[string]bool{}
		for _, field := range fields {
			if field == "" || field == "id" || field == "project_id" || field == "workspace_id" || output.Sensitive(field) || seenFields[field] {
				return output.New(2, "selected fields must be unique readable configuration names")
			}
			seenFields[field] = true
		}
		selectedContext, e := a.resolve()
		if e != nil {
			return e
		}
		if selected.Scope == "project" && selectedContext.Project == "" {
			return output.New(2, "capture requires explicit selected project")
		}
		if selected.Scope == "workspace" && selectedContext.Workspace == "" {
			return output.New(2, "capture requires explicit selected workspace")
		}
		parentIDs := map[string]string{}
		for _, p := range parents {
			name, value, ok := strings.Cut(p, "=")
			if !ok || value == "" {
				return output.New(2, "parent must be name=id")
			}
			if _, ok := parentIDs[name]; ok {
				return output.New(2, "duplicate parent")
			}
			parentIDs[name] = value
		}
		if len(parentIDs) != len(selected.Parents) {
			return output.New(2, "exact declared parents are required")
		}
		args := []string{}
		for _, p := range selected.Parents {
			if parentIDs[p] == "" {
				return output.New(2, "missing declared parent")
			}
			args = append(args, parentIDs[p])
		}
		args = append(args, id)
		v, meta, e := a.readResource(cmd.Context(), getter, args)
		if e != nil {
			return e
		}
		obj, ok := v.(map[string]any)
		if !ok || obj["id"] != id {
			return output.New(6, "returned projection does not match explicit resource ID")
		}
		if scope, ok := obj["project_id"]; ok && scope != a.Project {
			return output.New(6, "returned resource differs from selected project")
		}
		if scope, ok := obj["workspace_id"]; ok && scope != a.Workspace {
			return output.New(6, "returned resource differs from selected workspace")
		}
		if selected.Name == "AuthorityCategory" && meta["etag"] == "" {
			return output.New(9, "category capture requires observed ETag")
		}
		if a.IfMatch != "" {
			if meta["etag"] == "" {
				return output.New(9, "capture cannot verify requested revision without ETag")
			}
			if a.IfMatch != meta["etag"] {
				return output.New(6, "capture observed a different revision")
			}
		}
		spec := map[string]any{}
		for _, field := range fields {
			if field == "" || field == "id" || field == "project_id" || field == "workspace_id" || output.Sensitive(field) {
				return output.New(2, "selected field is not eligible for configuration capture")
			}
			if _, ok := spec[field]; ok {
				return output.New(2, "duplicate selected field")
			}
			value, ok := obj[field]
			if !ok {
				return output.New(5, "selected field is absent or inaccessible")
			}
			spec[field] = value
		}
		b, e := json.Marshal(spec)
		if e != nil {
			return e
		}
		d := manifest.ResourceDocument{SchemaVersion: "2", Workspace: a.Workspace, Project: a.Project, Resources: []manifest.Resource{{Key: key, Kind: kind, Action: "update", ResourceID: id, Parents: parentIDs, Spec: b, IfMatch: meta["etag"]}}}
		compiled, e := d.Compile()
		if e != nil {
			return output.New(2, e.Error())
		}
		if e = a.validateManifest(compiled); e != nil {
			return e
		}
		if destination != "" {
			b, e := json.MarshalIndent(d, "", "  ")
			if e != nil {
				return e
			}
			if e = config.AtomicWrite(destination, b, 0600); e != nil {
				return e
			}
		}
		return a.emit(map[string]any{"document": d, "selected_fields": fields, "observation": meta, "configuration_intent": true, "complete": false, "domain_validation": "server_required", "authorization": "read_succeeded_write_not_evaluated"})
	}}
	c.Flags().StringVar(&kind, "kind", "", "Declared resource kind with update and compatible get")
	c.Flags().StringVar(&id, "id", "", "Explicit remote resource ID")
	c.Flags().StringVar(&key, "key", "resource", "Manifest resource key")
	c.Flags().StringVar(&destination, "destination", "", "Optional raw resource manifest destination")
	c.Flags().StringArrayVar(&fields, "field", nil, "Top-level readable configuration field (repeatable)")
	c.Flags().StringArrayVar(&parents, "parent", nil, "Declared parent name=id (repeatable)")
	_ = c.MarkFlagRequired("kind")
	_ = c.MarkFlagRequired("id")
	g.AddCommand(c)
}
