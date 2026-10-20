package cli

import (
	"encoding/json"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/jsoninput"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"github.com/spf13/cobra"
	"net/url"
	"strconv"
)

func (a *App) categoryDiffCommand() {
	var from, to int64
	c := &cobra.Command{Use: "diff category_id", Short: "Compare two explicit immutable category revisions without changing grants", Args: cobra.ExactArgs(1), RunE: func(cmd *cobra.Command, args []string) error {
		if from < 1 || to < 1 || from > 2147483647 || to > 2147483647 {
			return output.New(2, "category revisions must be positive bounded integers")
		}
		if len(a.Query) > 0 {
			return output.New(2, "category diff uses explicit revision flags instead of query overrides")
		}
		if _, e := a.resolve(); e != nil {
			return e
		}
		if a.Workspace == "" {
			return output.New(2, "category diff requires selected Workspace")
		}
		if e := resourceID(args[0]); e != nil {
			return e
		}
		if a.DryRun {
			return a.emit(map[string]any{"category_id": args[0], "workspace_id": a.Workspace, "from_revision": from, "to_revision": to, "comparison": "not_evaluated_dry_run", "executed": false, "grants_changed": false, "schema_fetched": false})
		}
		op, _ := a.operation("workspace authority category get")
		if e := a.requireAdvertised(cmd.Context(), op); e != nil {
			return e
		}
		read := func(rev int64) (any, error) {
			v, _, e := a.readResourceQuery(cmd.Context(), op, args, url.Values{"revision": {strconv.FormatInt(rev, 10)}})
			if e != nil {
				return nil, e
			}
			obj, ok := v.(map[string]any)
			if !ok || obj["id"] != args[0] || obj["workspace_id"] != a.Workspace {
				return nil, output.New(6, "category revision differs from selected identity")
			}
			if n, ok := obj["revision"]; !ok || !revisionEqual(n, rev) {
				return nil, output.New(6, "server returned a different category revision")
			}
			return v, nil
		}
		before, e := read(from)
		if e != nil {
			return e
		}
		after, e := read(to)
		if e != nil {
			return e
		}
		desired, e := categoryDefinition(after)
		if e != nil {
			return e
		}
		changes, e := categoryChanges(before, desired)
		if e != nil {
			return e
		}
		return a.emit(map[string]any{"category_id": args[0], "workspace_id": a.Workspace, "from_revision": from, "to_revision": to, "changes": changes, "comparison": "category_definition", "executed": false, "grants_changed": false, "assignment_migration": "not_performed", "authorization": "reads_succeeded_write_not_evaluated"})
	}}
	c.Flags().Int64Var(&from, "from-revision", 0, "Explicit immutable source revision")
	c.Flags().Int64Var(&to, "to-revision", 0, "Explicit immutable destination revision")
	c.MarkFlagRequired("from-revision")
	c.MarkFlagRequired("to-revision")
	a.group("workspace authority category").AddCommand(c)
}
func revisionEqual(v any, n int64) bool {
	c := &jsoninput.Comparator{}
	equal, e := c.Equal(v, json.Number(strconv.FormatInt(n, 10)))
	return e == nil && equal
}
func categoryDefinition(v any) (map[string]any, error) {
	obj, ok := v.(map[string]any)
	if !ok {
		return nil, output.New(9, "category definition is not an object")
	}
	out := map[string]any{}
	for _, name := range []string{"name", "description", "scope", "permissions", "conditions", "catalog_revision"} {
		value, ok := obj[name]
		if !ok {
			return nil, output.New(9, "category definition is missing "+name)
		}
		out[name] = value
	}
	return out, nil
}
