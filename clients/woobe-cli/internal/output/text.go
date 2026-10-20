package output

import (
	"encoding/json"
	"fmt"
	"io"
	"strings"
	"text/tabwriter"
)

func orderedKeys(obj map[string]any, preferred []string) []string {
	if len(preferred) == 0 {
		preferred = append([]string{"current", "authenticated", "context", "api_url", "workspace", "project", "credential_source"}, relevantFields...)
	}
	keys := []string{}
	seen := map[string]bool{}
	for _, k := range append(preferred, sortedKeys(obj)...) {
		if _, ok := obj[k]; ok && !seen[k] {
			keys = append(keys, k)
			seen[k] = true
		}
	}
	return keys
}

func renderView(w io.Writer, options Options, value any, err error, evidence map[string]any) error {
	if err != nil {
		e := Normalize(err)
		if _, writeErr := fmt.Fprintf(w, "ERROR %d: %s\n", e.Code, safeText(e.Message)); writeErr != nil {
			return writeErr
		}
		fields := map[string]any{}
		if e.DomainCode != "" {
			fields["domain_code"] = e.DomainCode
		}
		if e.Status != 0 {
			fields["http_status"] = e.Status
		}
		if e.Outcome != "" {
			fields["write_outcome"] = e.Outcome
		}
		if e.RequestID != "" {
			fields["request_id"] = e.RequestID
		}
		if len(e.Diagnostics) > 0 {
			fields["diagnostics"] = Redact(e.Diagnostics)
		}
		if writeErr := detail(w, "", fields); writeErr != nil {
			return writeErr
		}
	}
	if value != nil {
		obj, isObject := value.(map[string]any)
		_, hasWorkspace := obj["workspace"]
		if isObject && hasWorkspace && !options.Wide && len(options.Fields) == 0 && (options.Command == "auth login" || options.Command == "auth status") {
			if e := renderAuth(w, obj); e != nil {
				return e
			}
		} else if rows, ok := value.([]any); ok {
			if e := renderRows(w, rows, options.Fields); e != nil {
				return e
			}
		} else if strings.HasPrefix(options.Command, "schema") || options.Command == "server-schema" {
			// Indented schemas remain authoritative, copyable JSON.
			encoder := json.NewEncoder(w)
			encoder.SetIndent("", "  ")
			if e := encoder.Encode(value); e != nil {
				return e
			}
		} else if obj, ok := value.(map[string]any); ok {
			if len(obj) == 0 {
				if _, e := fmt.Fprintln(w, "Done."); e != nil {
					return e
				}
			} else if e := detail(w, "", obj); e != nil {
				return e
			}
		} else if _, e := fmt.Fprintln(w, encodeCell(value)); e != nil {
			return e
		}
	} else if err == nil {
		if _, e := fmt.Fprintln(w, "Done."); e != nil {
			return e
		}
	}
	if len(evidence) > 0 {
		if e := detail(w, "meta.", evidence); e != nil {
			return e
		}
	}
	if value != nil && !options.Wide && len(options.Fields) == 0 && !strings.HasPrefix(options.Command, "schema") && options.Command != "version" {
		_, e := fmt.Fprintln(w, "Details: --wide | --fields FIELD,... | --output json")
		return e
	}
	return nil
}

func renderAuth(w io.Writer, obj map[string]any) error {
	fields := []struct{ label, path string }{
		{"Connection", "context"}, {"API", "api_url"}, {"Authenticated", "authenticated"},
		{"Workspace", "workspace.name"}, {"Project", "project.name"}, {"State", "state"},
		{"Credential storage", "credential_source"}, {"Available projects", "available_project_count"},
		{"CLI Key", "key_metadata.name"}, {"Key expires", "key_metadata.expires_at"},
	}
	for _, field := range fields {
		if value, ok := lookup(obj, field.path); ok {
			if _, err := fmt.Fprintf(w, "%s: %s\n", field.label, encodeCell(value)); err != nil {
				return err
			}
		}
	}
	if projects, ok := obj["available_projects"].([]any); ok && len(projects) > 0 {
		if err := renderRows(w, projects, []string{"name", "slug", "id"}); err != nil {
			return err
		}
	}
	if obj["state"] == "project_selection_required" {
		_, err := fmt.Fprintln(w, "Choose a project: woobe context project select <name-or-slug>")
		return err
	}
	return nil
}

func renderRows(w io.Writer, rows []any, fields []string) error {
	if len(rows) == 0 {
		_, err := fmt.Fprintln(w, "No results.")
		return err
	}
	columns := map[string]any{}
	objects := true
	for _, row := range rows {
		obj, ok := row.(map[string]any)
		if !ok {
			objects = false
			break
		}
		for key := range obj {
			columns[key] = nil
		}
	}
	tw := tabwriter.NewWriter(w, 0, 4, 2, ' ', 0)
	if !objects {
		for _, row := range rows {
			if _, err := fmt.Fprintln(tw, encodeCell(row)); err != nil {
				return err
			}
		}
	} else {
		keys := orderedKeys(columns, fields)
		if _, err := fmt.Fprintln(tw, strings.ToUpper(strings.Join(keys, "\t"))); err != nil {
			return err
		}
		for _, row := range rows {
			obj := row.(map[string]any)
			cells := make([]string, len(keys))
			for i, key := range keys {
				cells[i] = encodeCell(obj[key])
			}
			if _, err := fmt.Fprintln(tw, strings.Join(cells, "\t")); err != nil {
				return err
			}
		}
	}
	if err := tw.Flush(); err != nil {
		return err
	}
	_, err := fmt.Fprintf(w, "%d results.\n", len(rows))
	return err
}
