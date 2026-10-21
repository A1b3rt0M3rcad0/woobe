package manifest

import (
	"encoding/json"
	"fmt"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"regexp"
	"sort"
)

var secretName = regexp.MustCompile(`^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,100}$`)

// SecretReference is an exact, local protected-store reference, never a template.
func SecretReference(v any) (string, bool) {
	m, ok := v.(map[string]any)
	if !ok || len(m) != 1 {
		return "", false
	}
	name, ok := m["$secret_ref"].(string)
	return name, ok && secretName.MatchString(name)
}

func SecretReferences(v any) []string {
	names := map[string]bool{}
	var visit func(any)
	visit = func(v any) {
		if name, ok := SecretReference(v); ok {
			names[name] = true
			return
		}
		switch x := v.(type) {
		case map[string]any:
			for _, sub := range x {
				visit(sub)
			}
		case []any:
			for _, sub := range x {
				visit(sub)
			}
		}
	}
	visit(v)
	out := []string{}
	for name := range names {
		out = append(out, name)
	}
	sort.Strings(out)
	return out
}

func rejectSecrets(v any) error {
	switch x := v.(type) {
	case map[string]any:
		if _, exists := x["$secret_ref"]; exists {
			return fmt.Errorf("secret reference must be the whole value of a sensitive field")
		}
		for k, v := range x {
			if output.Sensitive(k) && v != nil {
				if _, ok := SecretReference(v); ok {
					continue
				}
				return fmt.Errorf("manifest secret values are forbidden; use explicit credential operations")
			}
			if e := rejectSecrets(v); e != nil {
				return e
			}
		}
	case []any:
		for _, v := range x {
			if e := rejectSecrets(v); e != nil {
				return e
			}
		}
	}
	return nil
}
func validateBody(b json.RawMessage) error {
	if len(b) == 0 {
		return nil
	}
	var v any
	if e := json.Unmarshal(b, &v); e != nil {
		return e
	}
	return rejectSecrets(v)
}
