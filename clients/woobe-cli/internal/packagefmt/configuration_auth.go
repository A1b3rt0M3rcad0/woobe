package packagefmt

import (
	"regexp"
	"strings"
)

var configurationFieldName = regexp.MustCompile(`^[A-Za-z][A-Za-z0-9_-]{0,127}$`)

// Validate semantic constraints shared with the backend compiler. The JSON
// catalog validates reference shape; this validates the field set and headers.
func validateConfigurationAuthentication(authentication map[string]any, provider bool) bool {
	kind := Text(authentication["type"])
	fields := Object(authentication["fields"])
	if provider && kind != "api_key" {
		return false
	}
	expected := map[string][]string{"api_key": {"api_key"}, "bearer": {"token"}, "basic": {"username", "password"}, "none": {}}
	if names, ok := expected[kind]; ok {
		if len(fields) != len(names) {
			return false
		}
		for _, name := range names {
			if _, exists := fields[name]; !exists {
				return false
			}
		}
	} else if kind != "headers" || len(fields) < 1 || len(fields) > 16 {
		return false
	}
	reserved := map[string]bool{"host": true, "content-length": true, "transfer-encoding": true, "connection": true, "proxy-authorization": true, "proxy-connection": true, "forwarded": true, "x-forwarded-host": true, "x-forwarded-proto": true, "x-forwarded-for": true}
	seen := map[string]bool{}
	for name := range fields {
		lower := strings.ToLower(name)
		if !configurationFieldName.MatchString(name) || seen[lower] || (kind == "headers" && reserved[lower]) {
			return false
		}
		seen[lower] = true
	}
	return true
}
