package output

import (
	"regexp"
	"strings"
)

func Sensitive(k string) bool {
	k = strings.ToLower(strings.ReplaceAll(k, "-", "_"))
	return k == "value" || k == "key" || k == "api_key" || k == "secret" || k == "password" || k == "csrf" || k == "token" || strings.HasSuffix(k, "_secret") || strings.HasSuffix(k, "_token") || k == "authorization" || k == "cookie"
}

var referenceKeyName = regexp.MustCompile(`^[A-Za-z_][A-Za-z0-9_]{0,127}$`)
var referenceFieldName = regexp.MustCompile(`^[A-Za-z][A-Za-z0-9_-]{0,127}$`)
var referenceAliasID = regexp.MustCompile(`^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$`)

// Preserve only the closed authentication-reference wire shape. Arbitrary
// token/key objects, inline values and malformed mixed metadata remain redacted.
func authenticationReferenceMetadata(value any) bool {
	auth, ok := value.(map[string]any)
	if !ok || len(auth) < 1 || len(auth) > 2 {
		return false
	}
	for key := range auth {
		if key != "type" && key != "fields" {
			return false
		}
	}
	kind, _ := auth["type"].(string)
	switch kind {
	case "none", "api_key", "bearer", "basic", "headers":
	default:
		return false
	}
	fields, ok := auth["fields"].(map[string]any)
	if !ok {
		return kind == "none" && auth["fields"] == nil
	}
	if len(fields) > 16 || (kind == "none" && len(fields) != 0) {
		return false
	}
	for name, raw := range fields {
		if !referenceFieldName.MatchString(name) {
			return false
		}
		ref, ok := raw.(map[string]any)
		if !ok {
			return false
		}
		source, _ := ref["source"].(string)
		key, _ := ref["key"].(string)
		if !referenceKeyName.MatchString(key) {
			return false
		}
		if source == "project_environment" && len(ref) == 2 {
			continue
		}
		if source == "legacy_configuration" && len(ref) == 3 {
			alias, _ := ref["alias_id"].(string)
			if referenceAliasID.MatchString(alias) {
				continue
			}
		}
		return false
	}
	return true
}

func copyAuthenticationReferenceMetadata(value any) map[string]any {
	auth := value.(map[string]any)
	result := map[string]any{"type": auth["type"]}
	if fields, ok := auth["fields"].(map[string]any); ok {
		copied := map[string]any{}
		for name, raw := range fields {
			reference := map[string]any{}
			for key, value := range raw.(map[string]any) {
				reference[key] = value
			}
			copied[name] = reference
		}
		result["fields"] = copied
	}
	return result
}
