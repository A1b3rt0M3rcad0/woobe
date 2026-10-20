package cli

import (
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"sort"
	"strconv"
	"strings"
)

func categoryComparable(v any) (map[string]any, error) {
	obj, ok := v.(map[string]any)
	if !ok {
		return nil, output.New(9, "category comparison requires an object")
	}
	out := map[string]any{}
	for name, value := range obj {
		out[name] = value
	}
	normalize := func(v any) (any, error) {
		list, ok := v.([]any)
		if !ok {
			return nil, output.New(9, "category set requires an array")
		}
		seen := map[string]bool{}
		for _, item := range list {
			s, ok := item.(string)
			if !ok {
				return nil, output.New(9, "category set requires strings")
			}
			seen[s] = true
		}
		values := []string{}
		for s := range seen {
			values = append(values, s)
		}
		sort.Strings(values)
		result := []any{}
		for _, s := range values {
			result = append(result, s)
		}
		return result, nil
	}
	if value, ok := obj["permissions"]; ok {
		value, e := normalize(value)
		if e != nil {
			return nil, e
		}
		out["permissions"] = value
	}
	if value, ok := obj["conditions"]; ok && value != nil {
		conditions, ok := value.(map[string]any)
		if !ok {
			return nil, output.New(9, "category conditions require an object")
		}
		result := map[string]any{}
		for name, values := range conditions {
			switch name {
			case "environments", "interfaces", "target_types", "target_ids":
			default:
				return nil, output.New(9, "category condition comparison is unsupported: "+name)
			}
			normalized, e := normalize(values)
			if e != nil {
				return nil, e
			}
			result[name] = normalized
		}
		out["conditions"] = result
	}
	return out, nil
}
func categoryChanges(current any, desired map[string]any) ([]FieldChange, error) {
	old, e := categoryComparable(current)
	if e != nil {
		return nil, e
	}
	next, e := categoryComparable(desired)
	if e != nil {
		return nil, e
	}
	return fieldChanges(old, next)
}
func configurationChanges(command string, current any, desired map[string]any) ([]FieldChange, error) {
	if command == "workspace authority category update" {
		return categoryChanges(current, desired)
	}
	return fieldChanges(current, desired)
}

func verifyCategoryObservation(current any, meta map[string]string, workspace, id string) error {
	obj, ok := current.(map[string]any)
	if !ok || obj["id"] != id || obj["workspace_id"] != workspace {
		return output.New(6, "observed category differs from selected Workspace/identity")
	}
	etag := meta["etag"]
	prefix := `"category:` + id + `:`
	if !strings.HasPrefix(etag, prefix) || !strings.HasSuffix(etag, `"`) {
		return output.New(9, "category observation requires a strong resource ETag")
	}
	revision, e := strconv.ParseInt(strings.TrimSuffix(strings.TrimPrefix(etag, prefix), `"`), 10, 64)
	if e != nil || revision < 1 || revision > 2147483647 || !revisionEqual(obj["revision"], revision) {
		return output.New(6, "category ETag differs from observed revision")
	}
	return nil
}
